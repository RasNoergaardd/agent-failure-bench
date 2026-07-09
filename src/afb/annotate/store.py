"""Persistence for annotation sessions (spec 003 R4-R5).

Annotations live in data/annotations/<trajectory_id>.<annotator-id>.json, one
file per (trajectory, annotator) pair. The file records a hash of the trajectory
it was made against; a mismatch means the trajectory changed and the annotations'
event spans can no longer be trusted, so loading refuses (spec 003 R5).
"""

import hashlib
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

from afb.models import FailureAnnotation, Trajectory, check_span


def trajectory_hash(trajectory: Trajectory) -> str:
    return hashlib.sha256(trajectory.model_dump_json().encode()).hexdigest()


class AnnotationSet(BaseModel):
    trajectory_id: str
    trajectory_hash: str
    annotator: str
    annotations: list[FailureAnnotation] = []


class TrajectoryMismatch(Exception):
    """The annotation file was made against a different version of this trajectory."""


class AnnotationStore:
    """Loads and atomically saves the AnnotationSet for one (trajectory, annotator) pair."""

    def __init__(self, annotations_dir: Path, trajectory: Trajectory, annotator: str):
        self.trajectory = trajectory
        self.annotator = annotator
        annotator_id = annotator.split(":", 1)[1]
        self.path = annotations_dir / f"{trajectory.trajectory_id}.{annotator_id}.json"

    def load(self) -> AnnotationSet:
        """Load existing annotations, or start an empty set. Refuses on hash mismatch."""
        expected = trajectory_hash(self.trajectory)
        if not self.path.exists():
            return AnnotationSet(
                trajectory_id=self.trajectory.trajectory_id,
                trajectory_hash=expected,
                annotator=self.annotator,
            )
        annotation_set = AnnotationSet.model_validate_json(self.path.read_text())
        if annotation_set.trajectory_hash != expected:
            raise TrajectoryMismatch(
                f"{self.path} was annotated against a different version of trajectory "
                f"{self.trajectory.trajectory_id!r} (hash mismatch); refusing to load"
            )
        if annotation_set.trajectory_id != self.trajectory.trajectory_id:
            raise TrajectoryMismatch(
                f"{self.path} targets trajectory {annotation_set.trajectory_id!r}, "
                f"not {self.trajectory.trajectory_id!r}"
            )
        return annotation_set

    def save(self, annotation_set: AnnotationSet) -> None:
        """Validate every annotation against the trajectory, then write atomically."""
        for annotation in annotation_set.annotations:
            check_span(annotation, self.trajectory)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(annotation_set.model_dump_json(indent=2) + "\n")
            os.replace(tmp_path, self.path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
