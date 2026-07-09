# Plan 002 — Trajectory Data Model & Ingest

1. **Models first** (no external dependency): `afb/models/taxonomy.py` (registry + `TaxonomyLabel`), `afb/models/trajectory.py` (`Trajectory`, `Event`), `afb/models/annotation.py` (`FailureAnnotation`). Pydantic v2, strict field validation per spec R1–R4.
2. **Schema export**: `afb.cli` with a `schema` subcommand using `model_json_schema()`.
3. **Tests**: construction happy paths, each validation rule as a failing case, JSON round-trip.
4. **Ingest — discovery step**: run `harbor run -d terminal-bench/terminal-bench-2 -a oracle` (or a single Terminus 2 task) locally; inspect the output directory layout and log format; document findings in `specs/002-trajectory-data-model/harbor-format-notes.md` before writing the parser.
5. **Ingest — implementation**: `afb/ingest/harbor.py` mapping the observed format → `Event` stream; golden-file test using one committed sample raw run (small task, trimmed if large).

Steps 1–3 are this session's scope; steps 4–5 need Docker + Harbor installed and belong to the pilot session (spec 004 kickoff).

**Design choices:**
- Event `kind` kept coarse (5 values) — fine-grained typing lives in annotations, not observations.
- `annotator` as a prefixed string (`human:rasmus`, `judge:claude-sonnet-5`) rather than an enum: keeps humans and judges in one field, distinguishable by prefix, no schema change when adding judges.
- Taxonomy registry as code constant with a doc-sync test (single source of truth: the code; the test parses codes out of the markdown and compares sets).
