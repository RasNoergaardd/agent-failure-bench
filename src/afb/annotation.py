"""The annotation record: one error occurrence in one trajectory.

This is the judge's output contract, defined by `research/annotation-guidelines.md`.
The same record is what the TRAIL agreement study compares against expert labels
and what the coverage analysis counts when revising the taxonomy.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from afb import taxonomy

# Built from the taxonomy file so the allowed values cannot drift from it.
CognitiveFunction = StrEnum(
    "CognitiveFunction",
    {value.upper(): value for value in taxonomy.cognitive_functions().values()},
)

Severity = Literal["low", "medium", "high"]
Confidence = Literal["certain", "probable", "speculative"]


class Annotation(BaseModel):
    """One error occurrence, located in the trajectory and classified on both axes."""

    id: Annotated[str, Field(min_length=1)]
    """Judge-assigned, unique within the trajectory, e.g. `a1`. Referenced by `cascade_of`."""

    trajectory_id: Annotated[str, Field(min_length=1)]
    taxonomy_version: str = taxonomy.DEFAULT_VERSION

    event_span: tuple[int, int]
    """Event indices `[start, end]` where the error manifests, usually a single event."""

    cognitive_function: CognitiveFunction
    error_type: Annotated[str, Field(min_length=1)]
    """A taxonomy code such as `RFL-1`, or the escape hatch `NEW-?`."""

    severity: Severity
    root_cause: bool
    cascade_of: str | None = None
    """Id of the root-cause annotation this error propagated from, if any."""

    rationale: Annotated[str, Field(min_length=1)]
    """One to three sentences quoting the evidence in the trajectory."""

    confidence: Confidence
    proposed_category: str | None = None
    """Free text describing the missing category. Only with the escape hatch."""

    @model_validator(mode="after")
    def _check(self) -> Self:
        version = self.taxonomy_version
        escape_hatch = taxonomy.escape_hatch_code(version)
        start, end = self.event_span

        if start < 0:
            raise ValueError(f"event_span starts at {start}, indices are non-negative")
        if end < start:
            raise ValueError(f"event_span {self.event_span} ends before it starts")

        if self.error_type == escape_hatch:
            if not self.proposed_category:
                raise ValueError(f"{escape_hatch} requires proposed_category")
        else:
            entry = taxonomy.error_types(version).get(self.error_type)
            if entry is None:
                raise ValueError(
                    f"{self.error_type!r} is not a code in taxonomy {version}; "
                    f"use {escape_hatch} if no category fits"
                )
            expected = taxonomy.cognitive_functions(version)[entry["function"]]
            if self.cognitive_function != expected:
                raise ValueError(
                    f"{self.error_type} belongs to {expected}, "
                    f"not {self.cognitive_function}"
                )
            if self.proposed_category:
                raise ValueError(
                    f"proposed_category is only for {escape_hatch}, "
                    f"but error_type is {self.error_type}"
                )

        if self.root_cause and self.cascade_of is not None:
            raise ValueError("a root cause does not cascade from another annotation")
        if self.cascade_of == self.id:
            raise ValueError(f"annotation {self.id} cascades from itself")

        return self


class Provenance(BaseModel):
    """Who produced an annotation set, and under what configuration.

    Constitution principle 6 requires every annotation to record its annotator.
    It becomes load-bearing once more than one judge model has run the same
    split: without it, two result files are indistinguishable, and a resumed run
    can silently blend two annotators into one dataset.

    `attempts_used` and `finish_reasons` describe the repair loop in
    `afb.judge.judge`. A first attempt cut off mid-JSON is repaired into a
    *smaller* annotation set, which records as a success and would otherwise be
    invisible — one of the candidate explanations for the judge's
    under-detection.
    """

    judge_model: str
    """The annotator, per principle 6. A model id, not a family name."""

    taxonomy_version: str = taxonomy.DEFAULT_VERSION
    guidelines_digest: str | None = None
    """SHA-256 of `research/annotation-guidelines.md` as the judge read it."""

    char_budget: int | None = None
    temperature: float | None = None

    attempts_used: int = 1
    finish_reasons: list[str | None] = Field(default_factory=list)
    """One entry per attempt, in order. `length` means the response was cut off."""

    @property
    def repaired(self) -> bool:
        """Whether this set came from a retry rather than the first response."""
        return self.attempts_used > 1

    @property
    def truncated(self) -> bool:
        """Whether any attempt hit the token ceiling instead of finishing."""
        return any(reason == "length" for reason in self.finish_reasons)


class AnnotationSet(BaseModel):
    """Every annotation the judge produced for one trajectory.

    A failed trajectory typically carries several; a successful one can also carry
    annotations, for errors the agent recovered from.
    """

    trajectory_id: Annotated[str, Field(min_length=1)]
    annotations: list[Annotation]

    provenance: Provenance | None = None
    """Optional so the runs recorded before it existed still load unchanged.

    Absent means "annotator not recorded", which is a known gap in runs A and B
    rather than a licence to omit it: `afb.judge.judge` always sets it.
    """

    @model_validator(mode="after")
    def _check(self) -> Self:
        ids = [a.id for a in self.annotations]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"annotation ids are not unique: {sorted(duplicates)}")

        for annotation in self.annotations:
            if annotation.trajectory_id != self.trajectory_id:
                raise ValueError(
                    f"annotation {annotation.id} belongs to trajectory "
                    f"{annotation.trajectory_id}, not {self.trajectory_id}"
                )
            if annotation.cascade_of is not None and annotation.cascade_of not in ids:
                raise ValueError(
                    f"annotation {annotation.id} cascades from "
                    f"{annotation.cascade_of!r}, which does not exist"
                )

        return self
