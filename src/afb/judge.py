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
from afb.annotation import AnnotationSet, Provenance
from afb.trajectory import Trajectory

FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
THINKING = re.compile(r"<(think|thinking)>.*?</\1>", re.DOTALL | re.IGNORECASE)
"""Reasoning models emit these; their braces would corrupt a naive JSON scan."""

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"


@dataclass(frozen=True, slots=True)
class Completion:
    """One model response, and why generation stopped.

    `finish_reason` is what separates a judge that found nothing from one that
    was cut off mid-JSON. Both reach `parse`; only the second is a truncation,
    and without this the repair loop turns it into a quietly smaller result.
    """

    text: str
    finish_reason: str | None = None


class JudgeError(RuntimeError):
    """The judge could not produce valid annotations for a trajectory."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable
        """False when re-sending the same request cannot succeed.

        Retrying costs another full-price call, and these prompts are large, so
        a hopeless retry is expensive rather than merely slow.
        """


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

    max_tokens: int = field(
        default_factory=lambda: int(os.environ.get("AFB_JUDGE_MAX_TOKENS", 8192))
    )
    """Raise this for a model that thinks: reasoning is billed against the same
    budget as the response, so a thinking model can exhaust it before the JSON
    is closed. A truncated response fails `parse` and costs a second request."""
    timeout: float = 300.0
    attempts: int = 3
    """Total tries per trajectory, including the repair attempt after invalid output."""

    char_budget: int = prompt.DEFAULT_CHAR_BUDGET
    taxonomy_version: str = taxonomy.DEFAULT_VERSION

    extra_body: dict[str, Any] = field(default_factory=dict)
    """Merged into the request, for fields outside the OpenAI schema.

    Set from `AFB_JUDGE_EXTRA_BODY` as a JSON object. The reasoning switch lives
    here: vLLM takes `{"chat_template_kwargs": {"enable_thinking": false}}`,
    which no portable field expresses.
    """

    def __post_init__(self) -> None:
        # An explicit argument wins; the environment only fills a gap. Bad JSON
        # here would otherwise reach the server as a silently dropped setting,
        # and a ladder rung that did not actually change its reasoning mode is
        # worse than one that failed to start.
        raw = os.environ.get("AFB_JUDGE_EXTRA_BODY")
        if self.extra_body or not raw:
            return
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise JudgeError(
                f"AFB_JUDGE_EXTRA_BODY is not valid JSON: {error}", retryable=False
            ) from error
        if not isinstance(parsed, dict):
            raise JudgeError(
                f"AFB_JUDGE_EXTRA_BODY must be a JSON object, got {type(parsed).__name__}",
                retryable=False,
            )
        self.extra_body = parsed

    def provenance(self, attempts_used: int, finish_reasons: list[str | None]) -> Provenance:
        """What this configuration should record about itself, per principle 6."""
        return Provenance(
            judge_model=self.model,
            taxonomy_version=self.taxonomy_version,
            guidelines_digest=prompt.guidelines_digest(),
            char_budget=self.char_budget,
            temperature=self.temperature,
            attempts_used=attempts_used,
            finish_reasons=finish_reasons,
        )

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env) or os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise JudgeError(
                f"no API key: set {self.api_key_env} (or OPENROUTER_API_KEY) in the environment",
                retryable=False,
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


def _post(config: JudgeConfig, messages: list[dict[str, str]]) -> Completion:
    """One chat-completions call, returning the assistant's text and stop reason."""
    request_body: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "max_tokens": config.max_tokens,
    }
    if config.temperature is not None:
        request_body["temperature"] = config.temperature
    if config.extra_body:
        # Reasoning is toggled per serving stack, not by the OpenAI schema: vLLM
        # reads `chat_template_kwargs`, gateways use their own field. Passing it
        # through keeps the ladder's thinking arm a configuration choice.
        request_body.update(config.extra_body)
    request = urllib.request.Request(
        f"{config.base_url.rstrip('/')}/chat/completions",
        data=json.dumps(request_body).encode(),
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

    if error := payload.get("error"):
        raise JudgeError(f"{config.model} returned an error: {error}")
    if not (choices := payload.get("choices")):
        raise JudgeError(f"{config.model} returned no choices: {str(payload)[:300]}")

    choice = choices[0]
    finish_reason = choice.get("finish_reason")
    # A gateway may answer 200 with a null content: the model produced only
    # reasoning, was cut off, or declined. Report which, rather than handing
    # None downstream where it surfaces as a TypeError in the JSON scan.
    if (content := choice.get("message", {}).get("content")) is None:
        raise JudgeError(
            f"{config.model} returned no content "
            f"(finish_reason={finish_reason!r}, "
            f"usage={payload.get('usage')}). "
            "A thinking model spends the same budget on reasoning and on the "
            f"answer, so raise AFB_JUDGE_MAX_TOKENS above {config.max_tokens}.",
            retryable=False,
        )
    return Completion(content, finish_reason)


def judge(
    trajectory: Trajectory,
    config: JudgeConfig | None = None,
    complete: Callable[[JudgeConfig, list[dict[str, str]]], Completion | str] = _post,
) -> AnnotationSet:
    """Annotate one trajectory.

    On invalid output the validation error is fed back to the model, which is
    the cheapest repair available and keeps malformed responses out of the data.
    `complete` is injectable so the pipeline can be exercised without a network;
    it may return a bare string when the stop reason is not of interest.

    The returned set carries its `provenance`, so a stored label always names the
    model that produced it and how many attempts it took.
    """
    config = config or JudgeConfig()
    text = prompt.build(trajectory, config.taxonomy_version, config.char_budget)
    messages = [{"role": "user", "content": text}]
    last_error: Exception | None = None
    finish_reasons: list[str | None] = []
    previous = ""

    for attempt in range(config.attempts):
        try:
            response = complete(config, messages)
            if isinstance(response, str):
                response = Completion(response)
            finish_reasons.append(response.finish_reason)
            previous = response.text
            result = parse(response.text, trajectory)
        except (JudgeError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if isinstance(error, JudgeError) and not error.retryable:
                raise
            messages = messages[:1] + [
                {"role": "assistant", "content": previous[:4000]},
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
        else:
            return result.model_copy(
                update={"provenance": config.provenance(attempt + 1, finish_reasons)}
            )

    raise JudgeError(f"{trajectory.trajectory_id}: no valid annotations after "
                     f"{config.attempts} attempts ({last_error})")
