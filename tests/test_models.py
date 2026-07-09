"""Tests for the spec 002 data models: validation rules and JSON round-trips."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from afb.models import (
    ESCAPE_HATCH,
    CognitiveFunction,
    Confidence,
    Event,
    EventKind,
    EventRole,
    FailureAnnotation,
    Outcome,
    RunConfig,
    Severity,
    TaxonomyLabel,
    Trajectory,
    check_span,
)


def make_events(n: int) -> list[Event]:
    return [
        Event(index=i, role=EventRole.AGENT, kind=EventKind.COMMAND, content=f"cmd {i}")
        for i in range(n)
    ]


def make_trajectory(n_events: int = 3, **overrides) -> Trajectory:
    kwargs = dict(
        trajectory_id="t-001",
        task_id="fix-broken-build",
        task_source="terminal-bench-2.0",
        agent="terminus-2",
        model="test-model",
        run_config=RunConfig(harness="harbor", harness_version="0.0.0", run_date="2026-07-09"),
        outcome=Outcome.FAILURE,
        events=make_events(n_events),
    )
    kwargs.update(overrides)
    return Trajectory(**kwargs)


def make_annotation(**overrides) -> FailureAnnotation:
    kwargs = dict(
        annotation_id="a-001",
        trajectory_id="t-001",
        event_span=(1, 1),
        label=TaxonomyLabel(cognitive_function=CognitiveFunction.REFLECTION, error_type="RFL-1"),
        severity=Severity.HIGH,
        rationale="Agent read '2 failed' as all tests passing (event 1).",
        confidence=Confidence.CERTAIN,
        annotator="human:rasmus",
        created_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )
    kwargs.update(overrides)
    return FailureAnnotation(**kwargs)


class TestTaxonomyLabel:
    def test_valid_code(self):
        label = TaxonomyLabel(cognitive_function=CognitiveFunction.ACTION, error_type="ACT-3")
        assert label.taxonomy_version == "v0"

    def test_unknown_code_rejected(self):
        with pytest.raises(ValidationError, match="unknown error_type"):
            TaxonomyLabel(cognitive_function=CognitiveFunction.ACTION, error_type="ACT-99")

    def test_function_mismatch_rejected(self):
        with pytest.raises(ValidationError, match="belongs to"):
            TaxonomyLabel(cognitive_function=CognitiveFunction.MEMORY, error_type="ACT-1")

    def test_escape_hatch_allowed_under_any_function(self):
        for fn in CognitiveFunction:
            TaxonomyLabel(cognitive_function=fn, error_type=ESCAPE_HATCH)


class TestTrajectory:
    def test_contiguous_indices_required(self):
        events = make_events(3)
        events[2] = events[2].model_copy(update={"index": 5})
        with pytest.raises(ValidationError, match="contiguous"):
            make_trajectory(events=events)

    def test_round_trip(self):
        t = make_trajectory(n_events=4, outcome=Outcome.SUCCESS, raw_ref="data/raw/t-001")
        assert Trajectory.model_validate_json(t.model_dump_json()) == t


class TestFailureAnnotation:
    def test_round_trip(self):
        a = make_annotation()
        assert FailureAnnotation.model_validate_json(a.model_dump_json()) == a

    def test_inverted_span_rejected(self):
        with pytest.raises(ValidationError, match="event_span"):
            make_annotation(event_span=(2, 1))

    def test_blank_rationale_rejected(self):
        with pytest.raises(ValidationError, match="rationale"):
            make_annotation(rationale="   ")

    def test_bad_annotator_rejected(self):
        with pytest.raises(ValidationError, match="annotator"):
            make_annotation(annotator="rasmus")

    def test_escape_hatch_requires_proposed_category(self):
        label = TaxonomyLabel(cognitive_function=CognitiveFunction.PLANNING, error_type=ESCAPE_HATCH)
        with pytest.raises(ValidationError, match="proposed_category"):
            make_annotation(label=label)
        make_annotation(label=label, proposed_category="Premature abstraction of the task")

    def test_proposed_category_forbidden_without_escape_hatch(self):
        with pytest.raises(ValidationError, match="escape hatch"):
            make_annotation(proposed_category="should not be here")

    def test_root_cause_cannot_cascade(self):
        with pytest.raises(ValidationError, match="root-cause"):
            make_annotation(root_cause=True, cascade_of="a-000")


class TestCheckSpan:
    def test_in_range_ok(self):
        check_span(make_annotation(event_span=(0, 2)), make_trajectory(n_events=3))

    def test_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            check_span(make_annotation(event_span=(0, 3)), make_trajectory(n_events=3))

    def test_wrong_trajectory_rejected(self):
        with pytest.raises(ValueError, match="targets trajectory"):
            check_span(make_annotation(trajectory_id="t-999"), make_trajectory())
