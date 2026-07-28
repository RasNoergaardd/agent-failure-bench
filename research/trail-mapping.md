# TRAIL Mapping (v0)

How TRAIL's expert categories are translated into taxonomy v0 for the agreement
study of research question 2. The machine-readable table is
`src/afb/data/trail-mapping-v0.yaml`; this document holds the reasoning. Like the
taxonomy, a version is never edited in place.

## Why a mapping is needed

The judge does not replicate TRAIL's setup. It labels with this project's
terminal taxonomy, which merges and deduplicates the categories of TRAIL and
AgentErrorTaxonomy and adds terminal-specific error types. TRAIL's experts
labelled with TRAIL's own categories. Agreement between the two therefore
requires an explicit bridge, and the bridge is a research artifact: it decides
what "the judge was right" means.

The mapping direction is TRAIL to taxonomy v0, never the reverse. Taxonomy codes
with no TRAIL counterpart (RFL-2, RFL-3, RFL-4, ACT-1, ACT-3, ACT-4, ACT-6,
MEM-3 vs PLN-2, PLN-5, SYS-1) are exactly the terminal-specific and
AgentErrorTaxonomy-derived additions. Their absence from TRAIL is expected, not
a defect, and it is the reason agreement with TRAIL bounds judge competence
rather than proving taxonomy completeness.

## Status of each category

Each TRAIL category carries one of three statuses.

- **mapped** — corresponds to exactly one taxonomy code. Scoreable on both axes.
- **ambiguous** — spans several codes, so only the cognitive function is
  decidable. Scoreable on the function axis only.
- **out_of_scope** — deliberately excluded by taxonomy v0. Not scoreable; a
  judge cannot be marked wrong for failing to produce a category the taxonomy
  does not contain.

Counts over the published annotations, all 148 traces:

| Status | Categories | Expert errors |
|---|---|---|
| mapped | 17 | 592 |
| ambiguous | 1 | 156 |
| out_of_scope | 3 | 93 |
| unknown | 0 | 0 |

So 592 of 841 expert errors (70%) can be scored at the error-code level, and 748
(89%) at the cognitive-function level.

## Contested decisions

**Instruction Non-compliance is ambiguous, and expensively so.** It is the
single largest ambiguity, 156 errors. Taxonomy v0 splits this failure by *when*
it happens: MEM-3 is drift after early compliance, PLN-2 is ignoring the
constraint from the start. TRAIL records no such distinction, so the code cannot
be recovered from the label. Worse, the two candidates sit under different
cognitive functions, memory and planning, so even function-level agreement is
contested. The table records `function: memory` because MEM-3 carries TRAIL's
instruction non-compliance as its provenance, but any agreement figure over this
category should be reported separately rather than pooled.

**Poor Information Retrieval and Task Orchestration are out of scope by
construction.** v0 excludes the first as RAG-pipeline specific and the second as
multi-agent, and this project is single-agent. Together they account for 86
expert errors that no judge running v0 could produce. Excluding them is not a
convenience: counting them as judge misses would measure the taxonomy's scope
decision, not the judge's accuracy.

**Hallucination is split by target.** TRAIL separates Language-only from
Tool-related hallucination. v0 splits the same phenomenon by faculty: MEM-2 is a
false claim about session history, RFL-5 is a false claim about a check the agent
performed. The correspondence is clean in practice because a fabricated tool
result is a fabricated evaluation.

**API and service failures are collapsed.** Authentication Errors, Service
Errors, Rate Limiting and Resource Not Found all map to SYS-4, since v0 judged
per-status-code granularity to earn no analysis value at this project's scale.
Agreement on SYS-4 therefore tests a coarser distinction than TRAIL's.

**Incorrect Memory Usage is undocumented.** It appears twice in the swe_bench
split and in no TRAIL table. It is mapped to MEM-1 as the nearest v0 code.

## Normalization

Category strings in the published data are not a controlled vocabulary. The
raw values include case variants (`Goal deviation`, `Language-Only`), singular
and plural forms (`Formatting Error`), leading whitespace, and at least one
typo (`Instruction non complience`). Lookup therefore normalizes by collapsing
whitespace, casefolding and dropping a trailing plural, then falls back to
closest-match against known spellings at a 0.88 cutoff.

All 841 published errors resolve under these rules, with no unknown categories.
Any future unknown is reported rather than dropped, since an unmappable expert
category is evidence about the mapping, not noise.
