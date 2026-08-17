"""Persistence for judge output.

Judging costs money and time, so labels are written once and every analysis
reads them back. One JSON object per line, one line per trajectory, so a long
run can be appended to and inspected while it is still going.
"""

import json
from pathlib import Path
from typing import Iterable, Iterator

from afb.annotation import AnnotationSet


def append(path: Path, annotation_set: AnnotationSet) -> None:
    """Add one judged trajectory, creating the file if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(annotation_set.model_dump_json() + "\n")


def save(path: Path, sets: Iterable[AnnotationSet]) -> int:
    """Write a whole corpus, replacing any existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8") as file:
        for annotation_set in sets:
            file.write(annotation_set.model_dump_json() + "\n")
            written += 1
    return written


def load(path: Path) -> list[AnnotationSet]:
    """Read a corpus of judged trajectories."""
    return list(iter_load(path))


def iter_load(path: Path) -> Iterator[AnnotationSet]:
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                yield AnnotationSet.model_validate(json.loads(line))


def judged_ids(path: Path) -> set[str]:
    """Trajectories already judged, so an interrupted run can resume."""
    if not path.exists():
        return set()
    return {annotation_set.trajectory_id for annotation_set in iter_load(path)}


def judge_models(path: Path) -> set[str | None]:
    """The annotators already present in a file.

    `None` stands for a set written before provenance was recorded. Used to stop
    a resume from blending two judge models into one dataset, which would make
    the agreement figures attributable to neither.
    """
    if not path.exists():
        return set()
    return {
        annotation_set.provenance.judge_model if annotation_set.provenance else None
        for annotation_set in iter_load(path)
    }
