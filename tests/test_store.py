"""Tests for the annotation store (spec 003 R4-R5): persistence, hash guard, atomicity."""

from datetime import datetime, timezone

import pytest

from afb.annotate.store import AnnotationSet, AnnotationStore, TrajectoryMismatch, trajectory_hash
from afb.models import (
    CognitiveFunction,
    Confidence,
    FailureAnnotation,
    Severity,
    TaxonomyLabel,
)


def make_annotation(trajectory, span=(8, 8), error_type="ACT-1", **overrides) -> FailureAnnotation:
    kwargs = dict(
        annotation_id="a-test1",
        trajectory_id=trajectory.trajectory_id,
        event_span=span,
        label=TaxonomyLabel(cognitive_function=CognitiveFunction.ACTION, error_type=error_type),
        severity=Severity.HIGH,
        root_cause=True,
        rationale="Unset $DECIMALS in double-quoted sed expands to nothing (event 8).",
        confidence=Confidence.CERTAIN,
        annotator="human:test",
        created_at=datetime(2026, 7, 9, tzinfo=timezone.utc),
    )
    kwargs.update(overrides)
    return FailureAnnotation(**kwargs)


def test_load_empty_set_when_no_file(tmp_path, sample_trajectory):
    store = AnnotationStore(tmp_path, sample_trajectory, "human:test")
    annotation_set = store.load()
    assert annotation_set.annotations == []
    assert annotation_set.trajectory_hash == trajectory_hash(sample_trajectory)
    assert not store.path.exists()


def test_save_load_round_trip(tmp_path, sample_trajectory):
    store = AnnotationStore(tmp_path, sample_trajectory, "human:test")
    annotation_set = store.load()
    annotation_set.annotations.append(make_annotation(sample_trajectory))
    store.save(annotation_set)
    assert store.path.name == "fixture-001.test.json"
    assert AnnotationStore(tmp_path, sample_trajectory, "human:test").load() == annotation_set


def test_hash_guard_refuses_changed_trajectory(tmp_path, sample_trajectory):
    store = AnnotationStore(tmp_path, sample_trajectory, "human:test")
    store.save(store.load())
    changed = sample_trajectory.model_copy(update={"instruction": "a different instruction"})
    with pytest.raises(TrajectoryMismatch, match="hash mismatch"):
        AnnotationStore(tmp_path, changed, "human:test").load()


def test_save_rejects_out_of_range_span(tmp_path, sample_trajectory):
    store = AnnotationStore(tmp_path, sample_trajectory, "human:test")
    annotation_set = store.load()
    annotation_set.annotations.append(
        make_annotation(sample_trajectory, span=(0, len(sample_trajectory.events)))
    )
    with pytest.raises(ValueError, match="out of range"):
        store.save(annotation_set)
    assert not store.path.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_failed_save_leaves_previous_file_intact(tmp_path, sample_trajectory):
    store = AnnotationStore(tmp_path, sample_trajectory, "human:test")
    good = store.load()
    good.annotations.append(make_annotation(sample_trajectory))
    store.save(good)
    before = store.path.read_text()

    bad = good.model_copy(deep=True)
    bad.annotations.append(
        make_annotation(
            sample_trajectory,
            span=(99, 99),
            annotation_id="a-bad",
            root_cause=False,
        )
    )
    with pytest.raises(ValueError):
        store.save(bad)
    assert store.path.read_text() == before
    assert not list(tmp_path.glob("*.tmp"))
