# Spec 003 — Annotation Tool

**Purpose:** a terminal UI for humans to apply the taxonomy (spec 001) to normalized trajectories (spec 002), producing `FailureAnnotation` records. Produces the expert annotations for subquestions 1 (taxonomy validation) and 2 (judge-agreement gold standard).

## Requirements

- **R1 — Load & navigate.** `uv run afb annotate <trajectory.json>` opens a Textual TUI: event list with index/role/kind, a detail pane showing full event content (commands and outputs rendered legibly, long outputs scrollable), and the task instruction always reachable (annotators must read it first, per guidelines).
- **R2 — Label at event/span level.** From any event: create an annotation — select span (defaults to current event), cognitive function, error type (filtered by chosen function, with definitions shown inline from the taxonomy registry), severity, root-cause flag, cascade link (pick from existing annotations), rationale (required), confidence.
- **R3 — Escape hatch.** `NEW-?` is always offered; choosing it requires a `proposed_category` description. The tool must not force-fit: picking `NEW-?` must be no harder than picking a real category.
- **R4 — Persistence & resume.** Annotations save to `data/annotations/<trajectory_id>.<annotator>.json` (validated `FailureAnnotation` list). Reopening a partially annotated trajectory restores existing annotations for review/edit/delete. Writes are atomic (no corrupt files on crash).
- **R5 — Integrity.** The tool never modifies trajectory files. Annotator id is taken from `--annotator` (required, `human:<id>` enforced). Root-cause uniqueness per chain is warned about (not hard-blocked — guidelines allow rare multi-chain cases).
- **R6 — Throughput.** Keyboard-driven; annotating a typical failed pilot trajectory takes < ~15 minutes excluding reading time.

## Acceptance criteria

- [ ] End-to-end: open a real pilot trajectory, create/edit/delete annotations incl. one `NEW-?`, quit, reopen, state restored.
- [ ] Output file validates against the spec 002 schema (checked on every save).
- [ ] Attempting to annotate out-of-range spans or omit rationale is rejected in-UI.
- [ ] Trajectory file byte-identical before/after an annotation session.
- [ ] Rasmus annotates one real failed trajectory in under 15 minutes (excluding reading) and reports no blocking friction.

## Non-goals

- Multi-user/concurrent annotation, web UI, database.
- Displaying LLM-judge annotations side-by-side (subquestion 2 tooling; keep the data model ready but not the UI).
