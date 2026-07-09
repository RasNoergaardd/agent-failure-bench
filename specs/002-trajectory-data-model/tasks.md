# Tasks 002 — Trajectory Data Model & Ingest

- [ ] `afb/models/taxonomy.py`: `CognitiveFunction` enum, error-code registry, `TaxonomyLabel`
- [ ] `afb/models/trajectory.py`: `Event`, `Trajectory` with index/outcome validation
- [ ] `afb/models/annotation.py`: `FailureAnnotation` with span/escape-hatch/annotator validation
- [ ] `afb/cli.py`: `afb schema` subcommand (JSON Schema export)
- [ ] `tests/test_models.py`: happy paths, every validation rule, round-trip
- [ ] `tests/test_taxonomy_sync.py`: registry codes == codes parsed from `research/taxonomy-v0.md`
- [ ] (pilot session) Run one Harbor task; write `harbor-format-notes.md` from the observed output
- [ ] (pilot session) `afb/ingest/harbor.py` + golden-file test with a committed sample run
