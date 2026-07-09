"""Textual TUI for human failure annotation (spec 003).

Layout: event table (left) + event detail (right) + annotations table (bottom).
The annotation form is a modal driven by the taxonomy registry; all label rules
are enforced by the Pydantic models — the form just surfaces their errors.
Annotations are saved (atomically) after every change, not on quit.
"""

import uuid
from datetime import datetime, timezone

from pydantic import ValidationError
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TextArea,
)

from afb.models import (
    ESCAPE_HATCH,
    CognitiveFunction,
    Confidence,
    FailureAnnotation,
    Severity,
    TaxonomyLabel,
    Trajectory,
    check_span,
    error_types_for,
)
from afb.annotate.store import AnnotationSet, AnnotationStore


def _preview(content: str, width: int = 64) -> str:
    first_line = content.strip().splitlines()[0] if content.strip() else ""
    return first_line[:width] + ("…" if len(first_line) > width else "")


def _type_options(function_value: str) -> list[tuple[str, str]]:
    fn = CognitiveFunction(function_value)
    options = [f"{code} — {name}" for code, name in error_types_for(fn).items()]
    return [(label, label.split(" ")[0]) for label in options] + [
        (f"{ESCAPE_HATCH} — propose a new category", ESCAPE_HATCH)
    ]


class InstructionScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,i", "close", "Close")]

    def __init__(self, instruction: str | None):
        super().__init__()
        self.instruction = instruction or "(no task instruction recorded on this trajectory)"

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="instruction-dialog"):
            yield Label("Task instruction", id="instruction-title")
            yield Static(self.instruction)
            yield Button("Close (esc)", id="instruction-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, question: str):
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self.question)
            with Horizontal(classes="buttons"):
                yield Button("Yes", variant="error", id="confirm-yes")
                yield Button("No", variant="primary", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class AnnotationForm(ModalScreen[FailureAnnotation | None]):
    """Create or edit one FailureAnnotation. Dismisses with the annotation, or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        trajectory: Trajectory,
        span: tuple[int, int],
        cascade_targets: list[str],
        annotator: str,
        existing: FailureAnnotation | None = None,
    ):
        super().__init__()
        self.trajectory = trajectory
        self.span = existing.event_span if existing else span
        self.cascade_targets = cascade_targets
        self.annotator = annotator
        self.existing = existing

    def compose(self) -> ComposeResult:
        ex = self.existing
        fn_value = ex.label.cognitive_function.value if ex else CognitiveFunction.PLANNING.value
        with VerticalScroll(id="form-dialog"):
            yield Label("Edit annotation" if ex else "New annotation", id="form-title")
            with Horizontal(classes="row"):
                yield Label("Span:")
                yield Input(value=str(self.span[0]), id="span-start", classes="span-input")
                yield Input(value=str(self.span[1]), id="span-end", classes="span-input")
            yield Label("Cognitive function")
            yield Select(
                [(fn.value, fn.value) for fn in CognitiveFunction],
                value=fn_value,
                allow_blank=False,
                id="fn-select",
            )
            yield Label("Error type")
            yield Select(
                _type_options(fn_value),
                value=ex.label.error_type if ex else Select.NULL,
                id="type-select",
            )
            yield Input(
                value=(ex.proposed_category or "") if ex else "",
                placeholder=f"proposed new category (required with {ESCAPE_HATCH})",
                id="proposed-category",
            )
            with Horizontal(classes="row"):
                yield Label("Severity")
                yield Select(
                    [(s.value, s.value) for s in Severity],
                    value=ex.severity.value if ex else Select.NULL,
                    id="severity-select",
                )
                yield Label("Confidence")
                yield Select(
                    [(c.value, c.value) for c in Confidence],
                    value=ex.confidence.value if ex else Select.NULL,
                    id="confidence-select",
                )
            with Horizontal(classes="row"):
                yield Checkbox("root cause", value=ex.root_cause if ex else False, id="root-cause")
                yield Label("cascade of")
                yield Select(
                    [(t, t) for t in self.cascade_targets],
                    value=(ex.cascade_of if ex and ex.cascade_of in self.cascade_targets else Select.NULL),
                    id="cascade-select",
                )
            yield Label("Rationale (quote the evidence)")
            yield TextArea(ex.rationale if ex else "", id="rationale")
            yield Label("", id="form-error")
            with Horizontal(classes="buttons"):
                yield Button("Save", variant="primary", id="form-save")
                yield Button("Cancel", id="form-cancel")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "fn-select" and event.value is not Select.NULL:
            self.query_one("#type-select", Select).set_options(_type_options(str(event.value)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "form-cancel":
            self.dismiss(None)
        elif event.button.id == "form-save":
            self._save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _fail(self, message: str) -> None:
        self.query_one("#form-error", Label).update(message)

    def _save(self) -> None:
        try:
            start = int(self.query_one("#span-start", Input).value)
            end = int(self.query_one("#span-end", Input).value)
        except ValueError:
            self._fail("span start/end must be integers")
            return
        fn = self.query_one("#fn-select", Select).value
        error_type = self.query_one("#type-select", Select).value
        severity = self.query_one("#severity-select", Select).value
        confidence = self.query_one("#confidence-select", Select).value
        for value, name in ((error_type, "error type"), (severity, "severity"), (confidence, "confidence")):
            if value is Select.NULL:
                self._fail(f"{name} is required")
                return
        cascade = self.query_one("#cascade-select", Select).value
        proposed = self.query_one("#proposed-category", Input).value.strip()
        try:
            annotation = FailureAnnotation(
                annotation_id=self.existing.annotation_id if self.existing else f"a-{uuid.uuid4().hex[:8]}",
                trajectory_id=self.trajectory.trajectory_id,
                event_span=(start, end),
                label=TaxonomyLabel(
                    cognitive_function=CognitiveFunction(str(fn)),
                    error_type=str(error_type),
                ),
                severity=Severity(str(severity)),
                root_cause=self.query_one("#root-cause", Checkbox).value,
                cascade_of=None if cascade is Select.NULL else str(cascade),
                rationale=self.query_one("#rationale", TextArea).text,
                confidence=Confidence(str(confidence)),
                proposed_category=proposed or None,
                annotator=self.annotator,
                created_at=self.existing.created_at if self.existing else datetime.now(timezone.utc),
            )
            check_span(annotation, self.trajectory)
        except (ValidationError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                self._fail("; ".join(e["msg"] for e in exc.errors()))
            else:
                self._fail(str(exc))
            return
        self.dismiss(annotation)


class AnnotateApp(App[None]):
    TITLE = "afb annotate"

    CSS = """
    #body { height: 1fr; }
    #events { width: 45%; }
    #detail-scroll { width: 55%; border-left: solid $accent; padding: 0 1; }
    #annotations { height: 30%; border-top: solid $accent; }
    InstructionScreen, ConfirmScreen, AnnotationForm { align: center middle; }
    #instruction-dialog, #confirm-dialog { width: 70%; max-height: 70%;
        background: $surface; border: thick $accent; padding: 1 2; }
    #form-dialog { width: 80%; max-height: 90%;
        background: $surface; border: thick $accent; padding: 1 2; }
    #form-title, #instruction-title { text-style: bold; }
    #form-error { color: $error; }
    .span-input { width: 8; }
    .row { height: auto; }
    .buttons { height: auto; padding-top: 1; }
    #rationale { height: 5; }
    """

    BINDINGS = [
        Binding("n", "new_annotation", "New annotation"),
        Binding("s", "mark_span", "Mark span start"),
        Binding("e", "edit_annotation", "Edit"),
        Binding("d", "delete_annotation", "Delete"),
        Binding("i", "instruction", "Instruction"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, trajectory: Trajectory, store: AnnotationStore):
        super().__init__()
        self.trajectory = trajectory
        self.store = store
        self.annotation_set: AnnotationSet = store.load()
        self.span_mark: int | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            with Horizontal(id="body"):
                yield DataTable(id="events", cursor_type="row")
                with VerticalScroll(id="detail-scroll"):
                    yield Static("", id="detail")
            yield DataTable(id="annotations", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = (
            f"{self.trajectory.trajectory_id} · {self.trajectory.task_id} · "
            f"outcome: {self.trajectory.outcome.value} · annotator: {self.store.annotator}"
        )
        events = self.query_one("#events", DataTable)
        events.add_columns("#", "role", "kind", "content")
        for event in self.trajectory.events:
            events.add_row(
                str(event.index), event.role.value, event.kind.value, _preview(event.content),
            )
        annotations = self.query_one("#annotations", DataTable)
        annotations.add_columns("id", "span", "code", "severity", "RC", "cascade of", "confidence")
        self._refresh_annotations()
        if self.trajectory.events:
            self._show_event(0)
        events.focus()

    # ── event detail ────────────────────────────────────────────────

    def _show_event(self, index: int) -> None:
        event = self.trajectory.events[index]
        header = f"[b]event {event.index}[/b] · {event.role.value} · {event.kind.value}"
        self.query_one("#detail", Static).update(f"{header}\n\n{event.content}")

    def on_data_table_row_highlighted(self, message: DataTable.RowHighlighted) -> None:
        if message.data_table.id == "events" and message.cursor_row is not None:
            self._show_event(message.cursor_row)

    # ── annotations table ───────────────────────────────────────────

    def _refresh_annotations(self) -> None:
        table = self.query_one("#annotations", DataTable)
        table.clear()
        for a in self.annotation_set.annotations:
            table.add_row(
                a.annotation_id,
                f"[{a.event_span[0]}, {a.event_span[1]}]",
                a.label.error_type,
                a.severity.value,
                "●" if a.root_cause else "",
                a.cascade_of or "",
                a.confidence.value,
            )

    def _selected_annotation_index(self) -> int | None:
        table = self.query_one("#annotations", DataTable)
        if not self.annotation_set.annotations or table.cursor_row is None:
            return None
        return min(table.cursor_row, len(self.annotation_set.annotations) - 1)

    def _persist(self) -> None:
        self.store.save(self.annotation_set)
        root_causes = [a for a in self.annotation_set.annotations if a.root_cause]
        if len(root_causes) > 1:
            self.notify(
                f"{len(root_causes)} root-cause annotations — allowed only for independent "
                "failure chains (guidelines, step 5)",
                severity="warning",
            )

    # ── actions ─────────────────────────────────────────────────────

    def action_mark_span(self) -> None:
        cursor = self.query_one("#events", DataTable).cursor_row
        if cursor is not None:
            self.span_mark = cursor
            self.notify(f"span start marked at event {cursor}; press n to annotate the span")

    def action_new_annotation(self) -> None:
        cursor = self.query_one("#events", DataTable).cursor_row or 0
        if self.span_mark is not None:
            span = (min(self.span_mark, cursor), max(self.span_mark, cursor))
            self.span_mark = None
        else:
            span = (cursor, cursor)
        self.push_screen(
            AnnotationForm(
                trajectory=self.trajectory,
                span=span,
                cascade_targets=[a.annotation_id for a in self.annotation_set.annotations],
                annotator=self.store.annotator,
            ),
            self._on_form_result,
        )

    def action_edit_annotation(self) -> None:
        index = self._selected_annotation_index()
        if index is None:
            self.notify("no annotation selected", severity="warning")
            return
        existing = self.annotation_set.annotations[index]
        self.push_screen(
            AnnotationForm(
                trajectory=self.trajectory,
                span=existing.event_span,
                cascade_targets=[
                    a.annotation_id
                    for a in self.annotation_set.annotations
                    if a.annotation_id != existing.annotation_id
                ],
                annotator=self.store.annotator,
                existing=existing,
            ),
            self._on_form_result,
        )

    def action_delete_annotation(self) -> None:
        index = self._selected_annotation_index()
        if index is None:
            self.notify("no annotation selected", severity="warning")
            return
        annotation = self.annotation_set.annotations[index]

        def _confirmed(result: bool | None) -> None:
            if result:
                self.annotation_set.annotations.pop(index)
                self._persist()
                self._refresh_annotations()

        self.push_screen(
            ConfirmScreen(f"Delete annotation {annotation.annotation_id} ({annotation.label.error_type})?"),
            _confirmed,
        )

    def action_instruction(self) -> None:
        self.push_screen(InstructionScreen(self.trajectory.instruction))

    def _on_form_result(self, annotation: FailureAnnotation | None) -> None:
        if annotation is None:
            return
        existing_ids = [a.annotation_id for a in self.annotation_set.annotations]
        if annotation.annotation_id in existing_ids:
            self.annotation_set.annotations[existing_ids.index(annotation.annotation_id)] = annotation
        else:
            self.annotation_set.annotations.append(annotation)
        self._persist()
        self._refresh_annotations()
