"""Ingest of Terminal-Bench 2.0 runs executed through Harbor.

This is the deployment side of the framework: the same normalized `Trajectory`
the judge was validated on, produced from real terminal runs instead of TRAIL
traces.

Harbor writes each trial as a directory, and what this module needs is split
across two files inside it:

    <job>/<trial>/result.json          outcome, task name, agent identity
    <job>/<trial>/agent/trajectory.json    what the agent actually did

The trajectory file is **ATIF** (Agent Trajectory Interchange Format), Harbor's
documented interchange schema, so the field names here are read off that spec
rather than guessed: a trajectory carries `steps`, each step has a `source`, a
`message`, optional `tool_calls`, and an `observation` holding the results of
those calls. `ATIF_VERSIONS` records the versions this parser was written
against; a newer one is accepted with a warning rather than dropped, since the
format has so far only added optional fields.

A trial whose agent produced no trajectory file (the `oracle` and `nop` agents,
or a crash before the first step) is skipped: there is nothing to annotate.
"""

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from afb.trajectory import Event, EventKind, Outcome, Trajectory

ATIF_VERSIONS = frozenset(
    {
        "ATIF-v1.0", "ATIF-v1.1", "ATIF-v1.2", "ATIF-v1.3",
        "ATIF-v1.4", "ATIF-v1.5", "ATIF-v1.6", "ATIF-v1.7",
    }
)
"""ATIF revisions this parser has been checked against (Harbor 0.18.0)."""

TRAJECTORY_NAME = "trajectory.json"
AGENT_DIR = "agent"
RESULT_NAME = "result.json"

SOURCE_TO_KIND = {
    "agent": EventKind.AGENT,
    "user": EventKind.OBSERVATION,
    "system": EventKind.SYSTEM,
}
"""ATIF `Step.source` is one of exactly these three."""


@dataclass(frozen=True, slots=True)
class Trial:
    """One Harbor trial directory, before normalization."""

    path: Path
    result: dict[str, Any]
    atif: dict[str, Any]


def _text(value: Any) -> str:
    """Render an ATIF message or observation content.

    Either may be a plain string or an array of content parts (ATIF v1.6 added
    multimodal). An image part has no text, so it is named rather than dropped
    silently — the judge must not infer an omission from something this module
    removed.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for part in value:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "image":
                    source = part.get("source") or {}
                    parts.append(f"[image omitted: {source.get('media_type', 'unknown')}]")
                elif text := part.get("text"):
                    parts.append(text)
        return "\n".join(parts)
    return json.dumps(value, ensure_ascii=False)


def _command(call: dict[str, Any]) -> str:
    """Render one tool call as the line a terminal reader would recognize.

    Terminal agents put the shell command in an argument whose name varies by
    agent (`command`, `cmd`, `input`). A single-argument call is rendered as
    that value alone; anything else keeps its JSON so no argument is lost.
    """
    name = call.get("function_name") or "tool"
    arguments = call.get("arguments") or {}
    if not isinstance(arguments, dict):
        return f"{name}: {json.dumps(arguments, ensure_ascii=False)}"

    for key in ("command", "cmd", "input", "code", "script"):
        if (value := arguments.get(key)) and isinstance(value, str):
            extra = {k: v for k, v in arguments.items() if k != key}
            suffix = f"  # {json.dumps(extra, ensure_ascii=False)}" if extra else ""
            return f"{value}{suffix}"
    if len(arguments) == 1:
        (only,) = arguments.values()
        if isinstance(only, str):
            return f"{name}: {only}"
    return f"{name}: {json.dumps(arguments, ensure_ascii=False)}"


def _events(steps: list[Any]) -> Iterator[tuple[EventKind, str]]:
    """Flatten ATIF steps into the ordered events the judge annotates.

    One step can produce several events, which is how a terminal trajectory
    actually reads: the agent says something, runs one or more commands, and
    sees their output. Reasoning is kept, labelled, because a judge classifying
    a *reflection* failure needs to see what the agent believed.
    """
    for step in steps:
        if not isinstance(step, dict):
            continue
        kind = SOURCE_TO_KIND.get(str(step.get("source", "")).strip().lower(), EventKind.AGENT)

        if reasoning := _text(step.get("reasoning_content")):
            yield EventKind.AGENT, f"[reasoning] {reasoning}"
        if message := _text(step.get("message")):
            yield kind, message

        for call in step.get("tool_calls") or []:
            if isinstance(call, dict):
                yield EventKind.ACTION, _command(call)

        observation = step.get("observation") or {}
        for result in observation.get("results") or []:
            if isinstance(result, dict) and (content := _text(result.get("content"))):
                yield EventKind.OBSERVATION, content


def _outcome(result: dict[str, Any]) -> Outcome:
    """The verdict from Harbor's verifier.

    Terminal-Bench ships automated tests, so this is unambiguous when present:
    `verifier_result.rewards.reward` is 1.0 for a pass. An exception recorded on
    the trial means the trial did not complete, which is not the same as the
    agent failing the task — that is UNKNOWN, so it cannot be silently counted
    as an agent failure in the RQ3 variance analysis.
    """
    if result.get("exception_info"):
        return Outcome.UNKNOWN
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    if "reward" not in rewards:
        return Outcome.UNKNOWN
    try:
        return Outcome.SUCCESS if float(rewards["reward"]) >= 1.0 else Outcome.FAILURE
    except (TypeError, ValueError):
        return Outcome.UNKNOWN


def _agent_name(result: dict[str, Any], atif: dict[str, Any]) -> str | None:
    """Agent identity, preferring the trial record over the trajectory's own."""
    info = result.get("agent_info") or {}
    if name := info.get("name"):
        return str(name)
    return (atif.get("agent") or {}).get("name")


def _model_name(result: dict[str, Any], atif: dict[str, Any]) -> str | None:
    """The model behind the agent, which RQ4 compares profiles across."""
    info = (result.get("agent_info") or {}).get("model_info") or {}
    if isinstance(info, dict) and (name := info.get("model_name")):
        return str(name)
    return (atif.get("agent") or {}).get("model_name")


def _instruction(steps: list[Any]) -> str:
    """The task instruction, which ATIF carries as the first user step.

    Harbor does not repeat the instruction in `result.json`; the agent receives
    it as the opening prompt, so that step is where it lives.
    """
    for step in steps:
        if isinstance(step, dict) and str(step.get("source", "")).lower() == "user":
            return _text(step.get("message"))
    return ""


def to_trajectory(trial: Trial) -> Trajectory:
    """Convert one Harbor trial into a normalized trajectory."""
    version = trial.atif.get("schema_version")
    if version and version not in ATIF_VERSIONS:
        warnings.warn(
            f"{trial.path}: unrecognized ATIF version {version!r}; "
            f"this parser was written against {max(ATIF_VERSIONS)}. "
            "Check the step schema before trusting these events.",
            stacklevel=2,
        )

    steps = trial.atif.get("steps") or []
    if not isinstance(steps, list):
        raise ValueError(f"{trial.path}: ATIF 'steps' is {type(steps).__name__}, expected a list")

    events = [
        Event(index=index, kind=kind, content=content)
        for index, (kind, content) in enumerate(
            (kind, content) for kind, content in _events(steps) if content.strip()
        )
    ]

    task_id = trial.result.get("task_name") or trial.path.name
    trial_name = trial.result.get("trial_name") or trial.path.name
    return Trajectory(
        trajectory_id=f"{task_id}::{trial_name}",
        source="harbor",
        task_instruction=_instruction(steps),
        events=events,
        outcome=_outcome(trial.result),
        metadata={
            "task_id": task_id,
            "run_id": trial_name,
            "agent": _agent_name(trial.result, trial.atif),
            "model": _model_name(trial.result, trial.atif),
            "trial_path": str(trial.path),
            "session_id": trial.atif.get("session_id"),
        },
    )


def read_trial(path: Path) -> Trial | None:
    """Read one trial directory, or None if it holds no annotatable trajectory.

    Returns None rather than raising for the ordinary cases — an agent that
    writes no trajectory (`oracle`, `nop`), or a directory that is not a trial —
    so a whole job does not fail on one such entry.
    """
    result_path, atif_path = path / RESULT_NAME, path / AGENT_DIR / TRAJECTORY_NAME
    if not result_path.is_file() or not atif_path.is_file():
        return None

    result = json.loads(result_path.read_text(encoding="utf-8"))
    atif = json.loads(atif_path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or not isinstance(atif, dict):
        return None
    return Trial(path=path, result=result, atif=atif)


def load_dir(root: Path) -> list[Trajectory]:
    """Every annotatable trial under a Harbor jobs or job directory.

    Accepts either level: the directory passed to `harbor run -o`, which holds
    one directory per job, or a single job directory holding trials. Trials are
    returned in a stable order so a judged file can be re-derived.
    """
    trials = [
        trial
        for candidate in sorted(p for p in root.rglob("*") if p.is_dir())
        if (trial := read_trial(candidate)) is not None
    ]
    if not trials and (trial := read_trial(root)) is not None:
        trials = [trial]
    return [to_trajectory(trial) for trial in trials]
