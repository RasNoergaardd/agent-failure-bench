# Plan 003 — Annotation Tool

1. **Skeleton**: Textual app in `afb/annotate/app.py`; `afb annotate` subcommand in `afb/cli.py`. Three-pane layout: event list (left), event detail (right), annotation summary bar (bottom). Task instruction behind a hotkey overlay.
2. **Annotation form**: modal screen driven by the taxonomy registry (functions → filtered error types with inline definitions). Validation via the `FailureAnnotation` model itself — the form is a thin shell over Pydantic errors.
3. **Persistence**: load/save `data/annotations/<trajectory_id>.<annotator>.json`; atomic write (tmp file + rename); save on every annotation change, not on quit.
4. **Polish for throughput**: single-key bindings (n = new annotation at cursor, e = edit, d = delete, r = toggle root-cause, i = instruction overlay), span selection with shift-movement.
5. **Manual acceptance run**: Rasmus annotates one real pilot trajectory; friction notes feed both tool fixes and the guidelines (tie-breaker gaps discovered here go into the spec 001 friction log).

Depends on: spec 002 models implemented; at least one real normalized trajectory (pilot session) for the acceptance run. Build steps 1–4 against a synthetic fixture trajectory first so the tool is ready when pilot data lands.

**Design choice:** no editing of past annotations' trajectory references — annotations are keyed to immutable event indices (spec 002 R2), so the tool refuses to open an annotation file whose trajectory hash doesn't match.
