# Plan 001 — Failure Taxonomy

1. **Ground in sources** — extract full category lists from TRAIL (arXiv:2505.08638) and AgentErrorTaxonomy (arXiv:2509.25370 + AgentDebug repo) into `research/related-work.md`. ✅ 2026-07-09
2. **Draft v0** — merge: AET's five modules as the cognitive-function axis; TRAIL + AET types deduplicated beneath them; add terminal-specific types; exclude inapplicable ones with rationale. Every type gets definition + example + decision rule + provenance. ✅ 2026-07-09 (`research/taxonomy-v0.md`)
3. **Operationalize** — write `research/annotation-guidelines.md`: procedure, root-cause heuristic, tie-breakers, severity scale, location conventions. ✅ 2026-07-09
4. **Encode** — taxonomy registry + `TaxonomyLabel` model in `afb.models` (with spec 002), including the `NEW-?` escape hatch.
5. **Validate empirically** — via spec 004: annotate pilot trajectories, run coverage analysis (per-category counts, `NEW-?` notes, tie-breaker friction log kept by the annotator).
6. **Revise to v1** — new file `research/taxonomy-v1.md`; revision log cites pilot counts for every change. User (Rasmus) signs off before v1 drives further annotation.

**Key design decision:** the cognitive-function axis comes from AgentErrorTaxonomy (not TRAIL's three groups) because the research question explicitly asks for *cognitive function*, and AET's modules map cleanly onto a terminal agent's loop (recall context → read output → decide → type command → harness). TRAIL contributes fine-grained types, the location+severity annotation pattern, and (later) the judge-agreement gold standard.

**Risk:** taxonomy too fine-grained for reliable human agreement at pilot scale → mitigation: the coverage analysis also reports confusion pairs from double-annotated trajectories; merging is a legitimate v1 outcome.
