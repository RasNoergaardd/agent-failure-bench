# Tasks 002 — Trajectory Data Model & Ingest

- [x] `afb/models/taxonomy.py`: `CognitiveFunction` enum, error-code registry, `TaxonomyLabel` (2026-07-09)
- [x] `afb/models/trajectory.py`: `Event`, `Trajectory` with index/outcome validation (2026-07-09; `instruction` field added for spec 003 R1)
- [x] `afb/models/annotation.py`: `FailureAnnotation` with span/escape-hatch/annotator validation (2026-07-09)
- [x] `afb/cli.py`: `afb schema` subcommand (JSON Schema export) (2026-07-09)
- [x] `tests/test_models.py`: happy paths, every validation rule, round-trip (2026-07-09)
- [x] `tests/test_taxonomy_sync.py`: registry codes == codes parsed from `research/taxonomy-v0.md` (2026-07-09)
- [x] Run Harbor oracle on 2 tasks; write `harbor-format-notes.md` from the observed output (2026-07-09)
- [x] `afb/ingest/harbor.py` + `afb ingest` CLI + golden-file test with a committed sample trial (2026-07-09)
- [ ] Terminus 2 event extractor for `EVENT_EXTRACTORS` — blocked on first real Terminus 2 run (needs LLM API key); agent/ format must be observed first, per harbor-format-notes.md
- [ ] Confirm failure/error result shapes (reward 0, exception_info) against a real failing run before pilot ingest
