"""Normalized agent trajectory: the observation side of the data model (spec 002 R1-R2).

Trajectories record what happened; judgments about what happened live in
FailureAnnotation (annotation.py) and reference events here by index. Event
indices are therefore immutable once a trajectory is stored.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class EventRole(str, Enum):
    AGENT = "agent"
    ENVIRONMENT = "environment"
    HARNESS = "harness"


class EventKind(str, Enum):
    REASONING = "reasoning"
    COMMAND = "command"
    OUTPUT = "output"
    TOOL_CALL = "tool_call"
    SYSTEM = "system"


class Outcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"  # run crashed/aborted before producing a verdict


class Event(BaseModel):
    index: int = Field(ge=0)
    role: EventRole
    kind: EventKind
    content: str
    timestamp: datetime | None = None


class RunConfig(BaseModel):
    """Pinned run configuration (constitution §4). Runs without one are exploratory
    and must not enter the dataset."""

    harness: str
    harness_version: str
    run_date: str
    extra: dict[str, str] = Field(default_factory=dict)


class Trajectory(BaseModel):
    trajectory_id: str
    task_id: str
    task_source: str
    instruction: str | None = None
    agent: str
    agent_version: str | None = None
    model: str | None = None  # None for non-LLM agents (e.g. Harbor's oracle)
    run_config: RunConfig
    outcome: Outcome
    test_output: str | None = None
    events: list[Event]
    raw_ref: str | None = None

    @model_validator(mode="after")
    def _check_event_indices(self) -> "Trajectory":
        for expected, event in enumerate(self.events):
            if event.index != expected:
                raise ValueError(
                    f"event indices must be contiguous from 0; "
                    f"expected {expected}, got {event.index}"
                )
        return self
