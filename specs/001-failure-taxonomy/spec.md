# Spec 001 — Failure Taxonomy

**Research subquestion:** *How can existing agent failure taxonomies (TRAIL, AgentErrorTaxonomy) be adapted and operationalized for terminal-based tasks, such that each failure is classified by both the failing cognitive function and its location in the trajectory — and which categories must be added or removed empirically?*

**Artifacts:** `research/taxonomy-v*.md` (the taxonomy), `research/annotation-guidelines.md` (its operationalization), the `TaxonomyLabel` model (spec 002), the revision log.

## Requirements

- **R1 — Two classification axes.** Every failure label records (a) the failing **cognitive function** — `memory`, `reflection`, `planning`, `action`, `system`, adapted from AgentErrorTaxonomy's five modules — and (b) its **location** in the trajectory as an event index or span. Fine-grained **error types** are nested under cognitive functions and merged from TRAIL + AgentErrorTaxonomy (see `research/related-work.md` §4 for the mapping).
- **R2 — Complete label schema.** A label = (cognitive function, error type, event span, severity ∈ {low, medium, high}, root-cause flag, optional cascade link). Matches TRAIL's location+impact annotation and AgentDebug's root-cause/cascade distinction.
- **R3 — Operational definitions.** Every error type has: a definition, a terminal-task example, and — wherever two types can be confused — a decision rule. The annotation guidelines add tie-breakers and a mechanical root-cause heuristic. Test: the guidelines must be usable verbatim as LLM-judge instructions (subquestion 2).
- **R4 — Terminal-specific adaptation.** Categories added for terminal tasks (v0: RFL-3 verification omission, ACT-1 command construction, ACT-6 destructive action) and inapplicable source categories excluded (v0: task orchestration, incorrect tool definition, poor information retrieval, per-status API subcodes) — each with stated rationale.
- **R5 — Empirical revision mechanism.** The taxonomy is versioned. v0 → v1 changes come only from pilot evidence: `NEW-?` escape-hatch usage (signals additions), zero-usage categories (signals removals/merges), and systematic tie-breaker failures (signals redefinitions). Every change gets a revision-log entry citing counts from the pilot coverage analysis.
- **R6 — Machine-readable form.** The taxonomy is encoded as an enum/registry in `afb.models` so annotations validate against it; the markdown document and the code registry must not diverge (test enforces the code registry matches a parsed list of codes from the markdown, or the registry is the single source and the doc is checked against it).

## Acceptance criteria

- [ ] `research/taxonomy-v0.md` exists with all error types satisfying R3 and provenance for each (TRAIL id / AET id / NEW).
- [ ] `research/annotation-guidelines.md` exists; a person unfamiliar with the project can label a trajectory using only it + the taxonomy.
- [ ] `TaxonomyLabel` in code validates codes against the registry; unknown codes rejected except the `NEW-?` escape hatch.
- [ ] After the pilot (spec 004): `taxonomy-v1.md` exists with a revision log where every add/remove/merge cites empirical counts.
- [ ] Every category used at least once in the pilot **or** explicitly retained/removed with rationale — no silent categories.

## Non-goals

- Multi-agent failure modes (subquestion 5 scope).
- Automated (LLM-judge) classification — that is subquestion 2, built on top of this spec's artifacts.
