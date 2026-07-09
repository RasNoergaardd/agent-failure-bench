# Tasks 002 — Trajectory Data Model & Ingest

- [x] `afb/models/taxonomy.py`: `CognitiveFunction` enum, error-code registry, `TaxonomyLabel` (2026-07-09)
- [x] `afb/models/trajectory.py`: `Event`, `Trajectory` with index/outcome validation (2026-07-09; `instruction` field added for spec 003 R1)
- [x] `afb/models/annotation.py`: `FailureAnnotation` with span/escape-hatch/annotator validation (2026-07-09)
- [x] `afb/cli.py`: `afb schema` subcommand (JSON Schema export) (2026-07-09)
- [x] `tests/test_models.py`: happy paths, every validation rule, round-trip (2026-07-09)
- [x] `tests/test_taxonomy_sync.py`: registry codes == codes parsed from `research/taxonomy-v0.md` (2026-07-09)
- [ ] (pilot session) Run one Harbor task; write `harbor-format-notes.md` from the observed output
- [ ] (pilot session) `afb/ingest/harbor.py` + golden-file test with a committed sample run
