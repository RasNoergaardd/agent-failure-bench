"""Failure annotation: the interpretation side of the data model (spec 002 R4).

Annotations reference immutable trajectories by id and event span, and always
record their annotator (human:<id> or judge:<model-id>) so human and LLM-judge
labels are never conflated (constitution §6).
"""

import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, model_validator

from afb.models.taxonomy import ESCAPE_HATCH, TaxonomyLabel
from afb.models.trajectory import Trajectory

_ANNOTATOR_RE = re.compile(r"^(human|judge):.+$")


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(str, Enum):
    CERTAIN = "certain"
    PROBABLE = "probable"
    SPECULATIVE = "speculative"


class FailureAnnotation(BaseModel):
    annotation_id: str
    trajectory_id: str
    event_span: tuple[int, int]
    label: TaxonomyLabel
    severity: Severity
    root_cause: bool = False
    cascade_of: str | None = None
    rationale: str
    confidence: Confidence
    proposed_category: str | None = None
    annotator: str
    created_at: datetime

    @model_validator(mode="after")
    def _check(self) -> "FailureAnnotation":
        start, end = self.event_span
        if start < 0 or end < start:
            raise ValueError(f"invalid event_span {self.event_span}: need 0 <= start <= end")
        if not self.rationale.strip():
            raise ValueError("rationale must not be empty")
        if not _ANNOTATOR_RE.match(self.annotator):
            raise ValueError(
                f"annotator {self.annotator!r} must be 'human:<id>' or 'judge:<model-id>'"
            )
        is_escape = self.label.error_type == ESCAPE_HATCH
        if is_escape and not (self.proposed_category or "").strip():
            raise ValueError(f"{ESCAPE_HATCH} annotations require proposed_category")
        if not is_escape and self.proposed_category is not None:
            raise ValueError("proposed_category is only allowed with the escape hatch")
        if self.root_cause and self.cascade_of is not None:
            raise ValueError("a root-cause annotation cannot itself cascade from another")
        return self


def check_span(annotation: FailureAnnotation, trajectory: Trajectory) -> None:
    """Validate an annotation's span against its trajectory (spec 002 R4).

    Kept outside the model because an annotation is stored separately from its
    trajectory; callers (annotation tool, ingest checks) run this at load/save time.
    """
    if annotation.trajectory_id != trajectory.trajectory_id:
        raise ValueError(
            f"annotation {annotation.annotation_id} targets trajectory "
            f"{annotation.trajectory_id!r}, not {trajectory.trajectory_id!r}"
        )
    _, end = annotation.event_span
    if end >= len(trajectory.events):
        raise ValueError(
            f"event_span {annotation.event_span} out of range for trajectory "
            f"{trajectory.trajectory_id!r} with {len(trajectory.events)} events"
        )
