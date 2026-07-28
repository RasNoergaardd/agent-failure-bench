"""Ingest of the TRAIL benchmark: gated traces plus expert annotations.

TRAIL (arXiv:2505.08638) supplies the expert labels the judge is scored against
in RQ2. Its traces are OpenTelemetry span trees produced by smolagents, so this
module flattens them into the normalized `Trajectory` of `afb.trajectory` and
parses the expert annotations alongside.

The expert labels stay in TRAIL's own vocabulary here. Translating its categories
into this project's taxonomy is a research decision and belongs with the
agreement study, not with ingest.

The dataset is gated: accept the terms on the hub and set `HF_TOKEN`. Its terms
forbid resharing, so downloads go to `data/`, which is not tracked by git.
"""

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Iterator

import pyarrow.parquet as pq
from pydantic import BaseModel, Field

from afb.trajectory import Event, EventKind, Outcome, Trajectory

REPO = "PatronusAI/TRAIL"
SPLIT_FILES = {
    "gaia": "data/gaia-00000-of-00001-33a2e72d362d688a.parquet",
    "swe_bench": "data/swe_bench-00000-of-00001-91aa04220f7198b4.parquet",
}
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "trail"

SPAN_KIND_TO_EVENT_KIND = {
    "LLM": EventKind.AGENT,
    "TOOL": EventKind.ACTION,
    "CHAIN": EventKind.SYSTEM,
    "AGENT": EventKind.SYSTEM,
}
"""OpenInference span kinds. Spans without one are scaffolding, so `SYSTEM`."""


class TrailError(BaseModel):
    """One expert-annotated error, in TRAIL's own vocabulary.

    Unknown fields are ignored: a few published annotations contain unescaped
    quotes that split one description into stray keys.
    """

    category: str
    """TRAIL's category, e.g. `Tool-related`. Not yet mapped to this taxonomy."""

    location: str = ""
    """The span id TRAIL located the error on."""

    event_index: int | None = None
    """That span's position in the flattened trajectory, once resolved."""

    evidence: str = ""
    description: str = ""
    impact: str = ""
    """TRAIL's HIGH / MEDIUM / LOW, the scale our severity was adapted from."""


class TrailLabels(BaseModel):
    trace_id: str = ""
    """Absent from five published GAIA labels; filled from the trace when missing."""

    errors: list[TrailError] = Field(default_factory=list)
    scores: list[dict[str, Any]] = Field(default_factory=list)
    """TRAIL's trace-level reliability, security and instruction-adherence ratings."""


def download(split: str, dest_dir: Path = DATA_DIR) -> Path:
    """Fetch one split's parquet file, unless it is already cached."""
    dest = dest_dir / f"{split}.parquet"
    if dest.exists():
        return dest

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError(
            f"{dest} is not cached and HF_TOKEN is not set; TRAIL is gated. "
            "Accept the terms on the hub and export HF_TOKEN, or set it in .env"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/{SPLIT_FILES[split]}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request) as response, dest.open("wb") as file:
        while chunk := response.read(1 << 20):
            file.write(chunk)
    return dest


TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _parse_json(raw: str) -> dict:
    """Parse a published JSON string, repairing trailing commas.

    One GAIA label ships with a trailing comma before `]`, which is invalid JSON.
    The repair is syntactic only and never changes annotation content.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(TRAILING_COMMA.sub(r"\1", raw))


def iter_raw(split: str, dest_dir: Path = DATA_DIR) -> Iterator[tuple[dict, dict]]:
    """Yield `(trace, labels)` pairs, both parsed from their JSON strings."""
    table = pq.read_table(download(split, dest_dir), columns=["trace", "labels"])
    for trace, labels in zip(table["trace"], table["labels"]):
        yield _parse_json(trace.as_py()), _parse_json(labels.as_py())


def _flatten(root: dict) -> list[dict]:
    """Spans in depth-first preorder, which is the order they started in."""
    ordered: list[dict] = []

    def visit(span: dict) -> None:
        ordered.append(span)
        for child in span.get("child_spans") or []:
            visit(child)

    visit(root)
    return ordered


def _content(span: dict) -> str:
    """The span rendered for the judge: its name, then its input and output."""
    attributes = span.get("span_attributes") or {}
    parts = [str(span.get("span_name", "span"))]
    for label, key in (("input", "input.value"), ("output", "output.value")):
        if (value := attributes.get(key)) is not None:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def _task_instruction(spans: list[dict]) -> str:
    """The task text, which smolagents records as `{"task": ...}` on the agent run."""
    for span in spans:
        raw = (span.get("span_attributes") or {}).get("input.value")
        if not isinstance(raw, str):
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("task"), str):
            return parsed["task"]
    return ""


def to_trajectory(trace: dict, split: str) -> Trajectory:
    """Flatten one TRAIL trace into a normalized trajectory, one span per event."""
    root = trace["spans"][0]
    spans = _flatten(root)
    attributes_of = lambda span: span.get("span_attributes") or {}

    events = [
        Event(
            index=index,
            kind=SPAN_KIND_TO_EVENT_KIND.get(
                attributes_of(span).get("openinference.span.kind"), EventKind.SYSTEM
            ),
            content=_content(span),
            source_ref=span.get("span_id"),
            metadata={
                "span_name": span.get("span_name"),
                "openinference_kind": attributes_of(span).get("openinference.span.kind"),
                "timestamp": span.get("timestamp"),
                "status_code": span.get("status_code"),
            },
        )
        for index, span in enumerate(spans)
    ]

    return Trajectory(
        trajectory_id=root.get("trace_id") or trace.get("trace_id"),
        source="trail",
        task_instruction=_task_instruction(spans),
        events=events,
        outcome=Outcome.UNKNOWN,
        metadata={"split": split, "service_name": root.get("service_name")},
    )


def to_labels(labels: dict, trajectory: Trajectory) -> TrailLabels:
    """Parse expert annotations and resolve each span id to an event index."""
    index_of = {
        event.source_ref: event.index for event in trajectory.events if event.source_ref
    }
    parsed = TrailLabels.model_validate(labels)
    parsed.trace_id = parsed.trace_id or trajectory.trajectory_id
    for error in parsed.errors:
        error.event_index = index_of.get(error.location)
    return parsed


def load(split: str, dest_dir: Path = DATA_DIR) -> Iterator[tuple[Trajectory, TrailLabels]]:
    """Yield every trace in a split as a trajectory with its expert annotations."""
    for trace, labels in iter_raw(split, dest_dir):
        trajectory = to_trajectory(trace, split)
        yield trajectory, to_labels(labels, trajectory)
