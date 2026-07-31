"""The LLM judge: the project's only annotator.

Expert annotation does not scale, roughly 110 minutes per trace in TRAIL, so an
LLM produces the labels. Its accuracy is established against TRAIL's expert
annotations before its labels are used anywhere else.

The client speaks the OpenAI chat-completions protocol, which both a self-hosted
vLLM server and hosted gateways implement, so the judge model is a configuration
choice rather than a code change. Only the standard library is used for HTTP.

Judging is deliberately separated from calling: `parse` turns a raw model
response into validated annotations and is testable without a network.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from afb import prompt, taxonomy
from afb.annotation import AnnotationSet
from afb.trajectory import Trajectory

FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
THINKING = re.compile(r"<(think|thinking)>.*?</\1>", re.DOTALL | re.IGNORECASE)
"""Reasoning models emit these; their braces would corrupt a naive JSON scan."""

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"


class JudgeError(RuntimeError):
    """The judge could not produce valid annotations for a trajectory."""


@dataclass(slots=True)
class JudgeConfig:
    """Where the judge runs. Pinned per experiment, per `constitution.md`."""

    base_url: str = field(default_factory=lambda: os.environ.get("AFB_JUDGE_BASE_URL", DEFAULT_BASE_URL))
    model: str = field(default_factory=lambda: os.environ.get("AFB_JUDGE_MODEL", DEFAULT_MODEL))
    api_key_env: str = "AFB_JUDGE_API_KEY"
    temperature: float | None = field(
        default_factory=lambda: (
            float(value) if (value := os.environ.get("AFB_JUDGE_TEMPERATURE")) else None
        )
    )
    """Omitted by default, since recent Anthropic models reject it outright.

    Set `AFB_JUDGE_TEMPERATURE=0` for a self-hosted model: vLLM otherwise honours
    the checkpoint's `generation_config.json`, and Qwen3 ships temperature 0.6.
    A sampling judge is not reproducible, and its variance would be mistaken for
    agent variance in the repeated-run analysis.
    """

    max_tokens: int = 8192
    timeout: float = 300.0
    attempts: int = 3
    """Total tries per trajectory, including the repair attempt after invalid output."""

    char_budget: int = prompt.DEFAULT_CHAR_BUDGET
    taxonomy_version: str = taxonomy.DEFAULT_VERSION

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env) or os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise JudgeError(
                f"no API key: set {self.api_key_env} (or OPENROUTER_API_KEY) in the environment"
            )
        return key


def extract_json(response: str) -> dict[str, Any]:
    """Pull the JSON object out of a model response.

    Models wrap JSON in prose or fences even when told not to, so this is
    tolerant. It is not tolerant about what the JSON contains: that is the
    annotation model's job.
    """
    text = THINKING.sub("", response).strip()
    if match := FENCE.search(text):
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise JudgeError(f"no JSON object in response: {response[:200]!r}")
        return json.loads(text[start : end + 1])


def parse(response: str, trajectory: Trajectory) -> AnnotationSet:
    """Validate a raw judge response against the annotation contract.

    Also checks what a single annotation cannot: that every span lies inside
    this trajectory.
    """
    payload = extract_json(response)
    payload.setdefault("trajectory_id", trajectory.trajectory_id)
    for annotation in payload.get("annotations") or []:
        if isinstance(annotation, dict):
            annotation.setdefault("trajectory_id", trajectory.trajectory_id)

    result = AnnotationSet.model_validate(payload)
    for annotation in result.annotations:
        start, end = annotation.event_span
        if end >= len(trajectory.events):
            raise ValueError(
                f"annotation {annotation.id} spans [{start}, {end}] but the "
                f"trajectory has {len(trajectory.events)} events"
            )
    return result


def _post(config: JudgeConfig, messages: list[dict[str, str]]) -> str:
    """One chat-completions call, returning the assistant's text."""
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "max_tokens": config.max_tokens,
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise JudgeError(f"{error.code} from {config.base_url}: {error.read()[:300]!r}") from error
    return payload["choices"][0]["message"]["content"]


def judge(
    trajectory: Trajectory,
    config: JudgeConfig | None = None,
    complete: Callable[[JudgeConfig, list[dict[str, str]]], str] = _post,
) -> AnnotationSet:
    """Annotate one trajectory.

    On invalid output the validation error is fed back to the model, which is
    the cheapest repair available and keeps malformed responses out of the data.
    `complete` is injectable so the pipeline can be exercised without a network.
    """
    config = config or JudgeConfig()
    text = prompt.build(trajectory, config.taxonomy_version, config.char_budget)
    messages = [{"role": "user", "content": text}]
    last_error: Exception | None = None

    for attempt in range(config.attempts):
        try:
            response = complete(config, messages)
            return parse(response, trajectory)
        except (JudgeError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if isinstance(error, JudgeError) and "no API key" in str(error):
                raise
            messages = messages[:1] + [
                {"role": "assistant", "content": locals().get("response", "")[:4000]},
                {
                    "role": "user",
                    "content": (
                        f"That response was rejected: {error}\n"
                        "Return only the corrected JSON object, matching the schema exactly."
                    ),
                },
            ]
            if attempt + 1 < config.attempts:
                time.sleep(2**attempt)

    raise JudgeError(f"{trajectory.trajectory_id}: no valid annotations after "
                     f"{config.attempts} attempts ({last_error})")
