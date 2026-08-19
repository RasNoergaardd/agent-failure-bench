"""Assembly of the LLM judge's prompt.

The prompt is the research artifact validated in RQ2, so it is built here and
nowhere else: the taxonomy comes from `afb/data/taxonomy-v*.yaml` and the
procedure comes verbatim from `research/annotation-guidelines.md`. Neither text
is paraphrased in code, so what the judge reads is what the paper describes.

This module is pure. It performs no model call.
"""

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from afb import taxonomy
from afb.annotation import AnnotationSet
from afb.trajectory import Trajectory

GUIDELINES_PATH = Path(__file__).resolve().parents[2] / "research" / "annotation-guidelines.md"
"""Read from the repo, not copied into the package, so there is only one copy."""

GUIDELINES_ENV = "AFB_GUIDELINES_PATH"
"""Override for the guidelines file, so a run can replay a superseded version.

The guidelines are edited in place and identified by digest, which means an
earlier version exists only as a git object. Comparing versions under one judge
therefore needs a way to point at an extracted copy without checking it out over
the working tree, where a second concurrent job would read it by mistake.
"""


def guidelines_path() -> Path:
    return Path(os.environ.get(GUIDELINES_ENV) or GUIDELINES_PATH)


@lru_cache
def guidelines_text() -> str:
    """The annotation guidelines, verbatim, as the judge's procedure."""
    return guidelines_path().read_text(encoding="utf-8").strip()


@lru_cache
def guidelines_digest() -> str:
    """SHA-256 of the guidelines, recorded with every run.

    The taxonomy is versioned and never edited in place, so its version string
    identifies it. The guidelines are edited in place, yet they are the artifact
    under test in RQ2: two runs are only comparable if the judge read the same
    procedure. A digest is the only thing that establishes that after the fact.
    """
    return hashlib.sha256(guidelines_text().encode("utf-8")).hexdigest()


def render_taxonomy(version: str = taxonomy.DEFAULT_VERSION) -> str:
    """The taxonomy as text for the judge.

    Provenance and the exclusions table are omitted: they justify how the
    taxonomy was built and are not needed to apply it.
    """
    data = taxonomy.load(version)
    types_by_function: dict[str, list[dict[str, Any]]] = {}
    for entry in data["error_types"]:
        types_by_function.setdefault(entry["function"], []).append(entry)

    lines = [f"# Failure taxonomy {data['version']}", ""]
    for function in data["cognitive_functions"]:
        lines += [
            f"## {function['code']} - {function['name']} (cognitive_function: "
            f"{function['name'].lower()})",
            function["scope"].strip(),
            "",
        ]
        for entry in types_by_function.get(function["code"], []):
            lines.append(f"### {entry['code']} {entry['name']}")
            lines.append(f"Definition: {entry['definition'].strip()}")
            if example := entry.get("example"):
                lines.append(f"Example: {example.strip()}")
            if rule := entry.get("decision_rule"):
                lines.append(f"Decision rule: {rule.strip()}")
            lines.append("")

    hatch = data["escape_hatch"]
    lines += [
        f"## {hatch['code']} - escape hatch",
        hatch["rule"].strip(),
        f"Requires the field `{hatch['requires_field']}`.",
        "",
    ]
    return "\n".join(lines).strip()


DEFAULT_CHAR_BUDGET = 200_000
"""Roughly 50k tokens of trajectory. Real traces reach 400k characters."""

MIN_EVENT_CHARS = 600
"""Never shrink an event below this, however many events there are."""


def _truncate(text: str, limit: int) -> str:
    """Keep the head and tail of an event, marking what was removed.

    The marker matters: an agent's error must not be inferred from output this
    module deleted, so elision is always visible to the judge.
    """
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    omitted = len(text) - head - tail
    return f"{text[:head]}\n... [{omitted} characters omitted by the harness] ...\n{text[-tail:]}"


def render_trajectory(trajectory: Trajectory, char_budget: int = DEFAULT_CHAR_BUDGET) -> str:
    """The trajectory as text, with the event indices `event_span` refers to.

    Long command output is truncated per event so that a trajectory of any
    length fits a context window, while every event keeps an index and a
    beginning and end.
    """
    per_event = max(MIN_EVENT_CHARS, char_budget // max(1, len(trajectory.events)))
    lines = [
        f"# Trajectory {trajectory.trajectory_id}",
        f"Source: {trajectory.source}",
        f"Recorded outcome: {trajectory.outcome.value}",
        "",
        "## Task instruction",
        _truncate(trajectory.task_instruction.strip(), per_event),
        "",
        f"## Events (indices 0 to {len(trajectory.events) - 1})",
        "",
    ]
    for event in trajectory.events:
        lines += [
            f"[{event.index}] {event.kind.value.upper()}",
            _truncate(event.content.strip(), per_event),
            "",
        ]
    return "\n".join(lines).strip()


def output_schema() -> str:
    """The required output format, as the JSON schema of `AnnotationSet`."""
    return json.dumps(AnnotationSet.model_json_schema(), indent=2)


TASK_INSTRUCTIONS = """\
You are annotating one agent trajectory from a terminal-based task.

Apply the taxonomy and the guidelines below exactly as written. Classify each
error you find on both axes, cognitive function and error type, and locate it by
the event indices shown in the trajectory.

Rules for your output:
- Return one JSON object matching the schema in "Output format". Return nothing else.
- Use taxonomy_version "{version}", and the trajectory_id given in the Trajectory section.
- Give every annotation a short unique id, a1, a2, a3 and so on. `cascade_of` refers to one of those ids.
- Use only error type codes defined in the taxonomy. If nothing fits, use "{escape_hatch}" and fill in proposed_category.
- Quote the evidence from the trajectory in every rationale. If you cannot cite an event, set confidence to "speculative".
"""
"""Deliberately free of per-trajectory values.

Everything before the trajectory is identical across a run, so a provider's
prompt cache can serve it. Interpolating the trajectory id here would change the
prefix on every call and defeat that.
"""


def build(
    trajectory: Trajectory,
    version: str = taxonomy.DEFAULT_VERSION,
    char_budget: int = DEFAULT_CHAR_BUDGET,
) -> str:
    """The complete judge prompt for one trajectory."""
    sections = [
        TASK_INSTRUCTIONS.format(
            version=version, escape_hatch=taxonomy.escape_hatch_code(version)
        ),
        render_taxonomy(version),
        f"# Annotation guidelines\n\n{guidelines_text()}",
        f"# Output format\n\n```json\n{output_schema()}\n```",
        render_trajectory(trajectory, char_budget),
    ]
    return "\n\n---\n\n".join(section.strip() for section in sections)
