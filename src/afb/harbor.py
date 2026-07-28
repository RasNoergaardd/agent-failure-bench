"""Ingest of Terminal-Bench 2.0 runs executed through Harbor.

This is the deployment side of the framework: the same normalized `Trajectory`
the judge was validated on, produced from real terminal runs instead of TRAIL
traces.

The field names Harbor writes are declared in `FIELDS` rather than scattered
through the code, because they are the one thing here that is not verified
against real data yet. Point `FIELDS` at whatever a real run directory contains
and the rest of the pipeline is unaffected. `load_dir` accepts both chat-shaped
records (role and content) and command-shaped records (command and output),
since terminal harnesses commonly emit either.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from afb.trajectory import Event, EventKind, Outcome, Trajectory


@dataclass(frozen=True, slots=True)
class Fields:
    """Where the values live in a run record. Adjust to match a real Harbor run."""

    instruction: tuple[str, ...] = ("instruction", "task", "prompt", "problem_statement", "task_description")
    events: tuple[str, ...] = ("messages", "trajectory", "steps", "events", "turns")
    outcome: tuple[str, ...] = ("resolved", "passed", "success", "is_resolved", "reward")
    task_id: tuple[str, ...] = ("task_id", "task", "instance_id", "id")
    agent: tuple[str, ...] = ("agent", "agent_name", "model")
    run_id: tuple[str, ...] = ("run_id", "trial_name", "attempt", "seed")

    role: tuple[str, ...] = ("role", "type", "kind")
    content: tuple[str, ...] = ("content", "text", "message", "thought")
    command: tuple[str, ...] = ("command", "action", "cmd", "input")
    output: tuple[str, ...] = ("output", "observation", "result", "stdout")


FIELDS = Fields()

ROLE_TO_KIND = {
    "assistant": EventKind.AGENT,
    "agent": EventKind.AGENT,
    "ai": EventKind.AGENT,
    "thought": EventKind.AGENT,
    "action": EventKind.ACTION,
    "command": EventKind.ACTION,
    "tool_call": EventKind.ACTION,
    "tool": EventKind.OBSERVATION,
    "observation": EventKind.OBSERVATION,
    "tool_result": EventKind.OBSERVATION,
    "user": EventKind.OBSERVATION,
    "system": EventKind.SYSTEM,
    "harness": EventKind.SYSTEM,
    "error": EventKind.SYSTEM,
}


def _first(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """The first present key, so one adapter serves several harness versions."""
    return next((record[key] for key in keys if record.get(key) not in (None, "")), None)


def _outcome(value: Any) -> Outcome:
    """Terminal-Bench ships automated tests, so the verdict is unambiguous."""
    if value is None:
        return Outcome.UNKNOWN
    if isinstance(value, str):
        value = value.strip().lower() in {"true", "pass", "passed", "resolved", "success", "1"}
    return Outcome.SUCCESS if bool(value) else Outcome.FAILURE


def _events(records: list[Any]) -> Iterator[tuple[EventKind, str]]:
    """Flatten harness records into typed events.

    A record carrying both a command and its output becomes two events, which is
    how a terminal trajectory actually reads.
    """
    for record in records:
        if isinstance(record, str):
            yield EventKind.AGENT, record
            continue
        if not isinstance(record, dict):
            continue

        role = str(_first(record, FIELDS.role) or "").strip().lower()
        content = _first(record, FIELDS.content)
        command = _first(record, FIELDS.command)
        output = _first(record, FIELDS.output)

        if content is not None and command is None and output is None:
            yield ROLE_TO_KIND.get(role, EventKind.AGENT), _text(content)
            continue
        if content is not None:
            yield ROLE_TO_KIND.get(role, EventKind.AGENT), _text(content)
        if command is not None:
            yield EventKind.ACTION, _text(command)
        if output is not None:
            yield EventKind.OBSERVATION, _text(output)


def _text(value: Any) -> str:
    """Render a content value, which may be a string or structured message parts."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [
            part.get("text", "") if isinstance(part, dict) else str(part) for part in value
        ]
        return "\n".join(p for p in parts if p)
    return json.dumps(value, ensure_ascii=False)


def to_trajectory(record: dict[str, Any], trajectory_id: str | None = None) -> Trajectory:
    """Convert one Harbor run record into a normalized trajectory."""
    raw_events = _first(record, FIELDS.events) or []
    if not isinstance(raw_events, list):
        raise ValueError(f"expected a list of events, got {type(raw_events).__name__}")

    events = [
        Event(index=index, kind=kind, content=content)
        for index, (kind, content) in enumerate(_events(raw_events))
        if content.strip()
    ]
    for index, event in enumerate(events):
        event.index = index

    task_id = _first(record, FIELDS.task_id) or "unknown-task"
    run_id = _first(record, FIELDS.run_id)
    return Trajectory(
        trajectory_id=trajectory_id or f"{task_id}::{run_id or 'run'}",
        source="harbor",
        task_instruction=_text(_first(record, FIELDS.instruction) or ""),
        events=events,
        outcome=_outcome(_first(record, FIELDS.outcome)),
        metadata={
            "task_id": task_id,
            "run_id": run_id,
            "agent": _first(record, FIELDS.agent),
        },
    )


def load_file(path: Path) -> list[Trajectory]:
    """Read one JSON or JSONL file, which may hold one run or many."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix == ".jsonl":
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        records = payload if isinstance(payload, list) else [payload]

    trajectories = []
    for position, record in enumerate(records):
        if not isinstance(record, dict) or _first(record, FIELDS.events) is None:
            continue
        stem = path.stem if len(records) == 1 else f"{path.stem}-{position}"
        trajectories.append(to_trajectory(record, trajectory_id=None) if _first(record, FIELDS.task_id)
                            else to_trajectory(record, trajectory_id=stem))
    return trajectories


def load_dir(root: Path) -> list[Trajectory]:
    """Every run under a Harbor results directory, in a stable order."""
    paths = sorted(p for p in root.rglob("*") if p.suffix in {".json", ".jsonl"})
    return [trajectory for path in paths for trajectory in load_file(path)]
