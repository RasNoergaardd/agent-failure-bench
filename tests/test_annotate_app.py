"""Smoke tests for the annotation TUI (spec 003) using Textual's test pilot."""

from textual.widgets import DataTable

from afb.annotate.app import AnnotateApp, AnnotationForm, InstructionScreen
from afb.annotate.store import AnnotationStore


def make_app(tmp_path, trajectory) -> AnnotateApp:
    return AnnotateApp(trajectory, AnnotationStore(tmp_path, trajectory, "human:test"))


async def test_app_mounts_with_all_events(tmp_path, sample_trajectory):
    app = make_app(tmp_path, sample_trajectory)
    async with app.run_test(size=(120, 40)):
        events = app.query_one("#events", DataTable)
        assert events.row_count == len(sample_trajectory.events)


async def test_instruction_overlay_opens_and_closes(tmp_path, sample_trajectory):
    app = make_app(tmp_path, sample_trajectory)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("i")
        assert isinstance(app.screen, InstructionScreen)
        await pilot.press("escape")
        assert not isinstance(app.screen, InstructionScreen)


async def test_annotation_form_opens_with_cursor_span(tmp_path, sample_trajectory):
    app = make_app(tmp_path, sample_trajectory)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("n")
        assert isinstance(app.screen, AnnotationForm)
        assert app.screen.span == (0, 0)
        await pilot.press("escape")
        assert not isinstance(app.screen, AnnotationForm)


async def test_span_mark_flows_into_form(tmp_path, sample_trajectory):
    app = make_app(tmp_path, sample_trajectory)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("s")            # mark span start at event 0
        await pilot.press("down", "down") # move cursor to event 2
        await pilot.press("n")
        assert isinstance(app.screen, AnnotationForm)
        assert app.screen.span == (0, 2)
