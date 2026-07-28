"""The normalized trajectory: the judge's input contract.

Terminal tasks are fully observable, so a trajectory is an ordered list of events.
Both TRAIL traces (for the agreement study) and Harbor runs (for the experiments)
are converted into this shape, so the judge that is validated is the same judge
that is deployed. Parsers for those two sources come later; this module only
fixes what they must produce.

Event indices are the coordinate system `Annotation.event_span` refers to.
"""

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import BaseModel, Field, model_validator


class EventKind(StrEnum):
    """The four kinds of event in an agent loop, named so both sources fit.

    A shell command and an OpenTelemetry tool-call span are both `ACTION`; a
    command's stdout and a tool result are both `OBSERVATION`.
    """

    AGENT = "agent"
    """What the agent produced itself: reasoning, stated intentions, messages."""

    ACTION = "action"
    """A concrete action the agent took: a shell command, a tool call."""

    OBSERVATION = "observation"
    """What came back from the environment: command output, tool result."""

    SYSTEM = "system"
    """The harness speaking: budget notices, truncation, provider errors."""


class Outcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"
    """For sources without an automated verdict. Terminal-Bench always has one."""


class Event(BaseModel):
    """One step of the trajectory, rendered as text for the judge to read."""

    index: Annotated[int, Field(ge=0)]
    kind: EventKind
    content: str
    source_ref: str | None = None
    """Identifier in the original format, e.g. an OpenTelemetry span id."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Source-specific extras kept out of `content`, e.g. exit codes, timestamps."""


class Trajectory(BaseModel):
    """One agent run on one task, normalized.

    Per `annotation-guidelines.md`, the judge reads `task_instruction` before any
    agent behaviour, so it is a field of its own rather than the first event.
    """

    trajectory_id: Annotated[str, Field(min_length=1)]
    source: Annotated[str, Field(min_length=1)]
    """Where this was converted from, e.g. `trail` or `harbor`."""

    task_instruction: str
    events: Annotated[list[Event], Field(min_length=1)]
    outcome: Outcome = Outcome.UNKNOWN
    metadata: dict[str, Any] = Field(default_factory=dict)
    """Run-level extras, e.g. agent name, model, task id, budget."""

    @model_validator(mode="after")
    def _indices_are_positional(self) -> Self:
        """Indices must be 0-based and contiguous, else `event_span` is ambiguous."""
        expected = list(range(len(self.events)))
        actual = [e.index for e in self.events]
        if actual != expected:
            raise ValueError(
                f"event indices must be 0..{len(self.events) - 1} in order, got {actual}"
            )
        return self

    def span(self, start: int, end: int) -> list[Event]:
        """The events an `Annotation.event_span` points at."""
        if not 0 <= start <= end < len(self.events):
            raise IndexError(
                f"span [{start}, {end}] is outside trajectory of "
                f"{len(self.events)} events"
            )
        return self.events[start : end + 1]
