# Spec 002 — Trajectory Data Model & Ingest

**Purpose:** the shared representation everything else builds on — normalized agent trajectories (observations) and failure annotations (interpretations), plus the parser from raw Harbor output. Serves all subquestions; the observation/interpretation separation is required by `constitution.md` §6 and by the judge-agreement study (subquestion 2).

## Requirements

### Models (`afb.models`)

- **R1 — `Trajectory`**: `trajectory_id`, `task_id`, `task_source` (e.g., `terminal-bench-2.0`), `instruction` (the task statement shown to the agent; optional if the raw source lacks it — but the annotation tool needs it, spec 003 R1), `agent` (name + version), `model` (LLM id; optional — non-LLM agents like Harbor's oracle have none), `run_config` (pinned per constitution §4: harness version, budgets, date, seeds if any), `outcome` (`success` / `failure` / `error`, plus raw test results), `events: list[Event]`, `raw_ref` (path/hash of preserved raw source).
- **R2 — `Event`**: `index` (0-based, contiguous), `role` (`agent` / `environment` / `harness`), `kind` (`reasoning` / `command` / `output` / `tool_call` / `system`), `content` (text), `timestamp` (optional — only if raw source has it). Annotation spans reference these indices, so indices are immutable once a trajectory is stored.
- **R3 — `TaxonomyLabel`**: `cognitive_function` (enum of 5), `error_type` (code validated against the taxonomy registry, or `NEW-?`), `taxonomy_version` (e.g., `v0`). Registry is generated from / checked against `research/taxonomy-v*.md` (spec 001 R6).
- **R4 — `FailureAnnotation`**: `annotation_id`, `trajectory_id`, `event_span` (`[start, end]`, validated against the trajectory's event count), `label: TaxonomyLabel`, `severity`, `root_cause: bool`, `cascade_of` (optional annotation id), `rationale`, `confidence` (`certain` / `probable` / `speculative`), `proposed_category` (required iff error_type is `NEW-?`), `annotator` (`human:<id>` or `judge:<model-id>`), `created_at`.
- **R5 — Serialization**: JSON on disk (`data/trajectories/*.json`, `data/annotations/*.json`); JSON Schema export via a CLI (`uv run afb schema`) for the thesis appendix. Round-trip (load → dump → load) must be lossless.

### Ingest (`afb.ingest`)

- **R6 — Harbor parser**: converts one Harbor run directory into `Trajectory` objects. **The raw format must be inspected from a real `harbor run` before implementation — do not guess it** (the Harbor docs do not document the output layout; verified 2026-07-09). The parser preserves a reference to the raw source (R1 `raw_ref`) and never mutates raw files.
- **R7 — Robustness**: handles success, failure, and crashed/aborted runs; unparseable runs fail loudly with the run id, never silently skipped.

## Acceptance criteria

- [ ] All models implemented with Pydantic v2; validation errors on: non-contiguous event indices, spans out of range, unknown taxonomy codes (except `NEW-?`), `NEW-?` without `proposed_category`, unknown annotator prefix.
- [ ] Round-trip property test passes for `Trajectory` and `FailureAnnotation`.
- [ ] `uv run afb schema` writes JSON Schema files for the public models.
- [ ] Parser ingests every trajectory from the pilot run (spec 004) — success and failure runs — with zero silent skips.
- [ ] A parsed trajectory is re-derivable: re-running ingest on the same raw source yields an identical normalized file.

## Non-goals

- Parsing other agents' formats (Claude Code, Codex CLI) — design `Event` generically enough, but implement Terminus 2 only.
- Databases; flat JSON files are sufficient at this scale and diff cleanly in git.
