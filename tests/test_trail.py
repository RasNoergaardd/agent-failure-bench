"""Tests against the real TRAIL data.

TRAIL is gated and must not be committed, so these skip unless the parquet files
have been downloaded to `data/trail/`.
"""

import pytest

from afb import mapping, prompt, trail
from afb.mapping import Status
from afb.trajectory import EventKind

CARD_COUNTS = {"gaia": 117, "swe_bench": 31}
CARD_ERRORS = 841

pytestmark = pytest.mark.skipif(
    not (trail.DATA_DIR / "gaia.parquet").exists(),
    reason="TRAIL not downloaded; run `afb prompt` once with HF_TOKEN set",
)


@pytest.fixture(scope="module")
def corpus():
    return {split: list(trail.load(split)) for split in CARD_COUNTS}


def test_counts_match_the_dataset_card(corpus):
    for split, expected in CARD_COUNTS.items():
        assert len(corpus[split]) == expected
    assert sum(len(labels.errors) for cases in corpus.values() for _, labels in cases) == CARD_ERRORS


def test_every_span_becomes_one_event(corpus):
    def count(span):
        return 1 + sum(count(child) for child in span.get("child_spans") or [])

    for split in CARD_COUNTS:
        for raw_trace, _ in list(trail.iter_raw(split))[:20]:
            trajectory = trail.to_trajectory(raw_trace, split)
            assert len(trajectory.events) == count(raw_trace["spans"][0])


def test_expert_locations_resolve_to_the_right_event(corpus):
    resolved = unresolved = 0
    for cases in corpus.values():
        for trajectory, labels in cases:
            for error in labels.errors:
                if error.event_index is None:
                    unresolved += 1
                    continue
                assert trajectory.events[error.event_index].source_ref == error.location
                resolved += 1
    assert resolved == 838  # three published locations name spans absent from their trace
    assert unresolved == 3


def test_events_follow_span_start_order(corpus):
    for cases in corpus.values():
        for trajectory, _ in cases:
            stamps = [e.metadata.get("timestamp") for e in trajectory.events]
            assert all(a <= b for a, b in zip(stamps, stamps[1:]) if a and b)


def test_every_expert_category_maps(corpus):
    statuses = {Status.MAPPED: 0, Status.AMBIGUOUS: 0, Status.OUT_OF_SCOPE: 0}
    for cases in corpus.values():
        for _, labels in cases:
            for error in labels.errors:
                result = mapping.map_category(error.category)
                assert result.status is not Status.UNKNOWN, error.category
                statuses[result.status] += 1
    assert statuses[Status.MAPPED] == 592
    assert statuses[Status.AMBIGUOUS] == 156
    assert statuses[Status.OUT_OF_SCOPE] == 93


def test_prompt_fits_the_budget_for_the_largest_trace(corpus):
    longest = max(
        (t for cases in corpus.values() for t, _ in cases), key=lambda t: len(t.events)
    )
    text = prompt.build(longest, char_budget=200_000)
    assert len(longest.events) > 100
    assert len(text) < 260_000  # trajectory budget plus taxonomy and guidelines


def test_kinds_cover_both_splits(corpus):
    for split, cases in corpus.items():
        kinds = {event.kind for trajectory, _ in cases for event in trajectory.events}
        assert EventKind.AGENT in kinds and EventKind.SYSTEM in kinds
