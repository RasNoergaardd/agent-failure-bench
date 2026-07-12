# Experiment Design

How the research questions are answered empirically. Every run that enters the analysis must satisfy the constitution's pinning principle (§4).

## Study 1 — Judge validation on TRAIL (RQ2)

**Question:** how accurately can an LLM-as-judge classify agent failures, measured as agreement with expert annotations on the TRAIL benchmark?

- **Data:** the published TRAIL dataset (arXiv 2505.08638; ~148 expert-annotated traces from GAIA and SWE-Bench). No annotation is produced by us — TRAIL's expert labels are the gold standard. Verify dataset access and license early; this study gates everything downstream.
- **Judge:** the taxonomy (`taxonomy-v*.md`) plus `annotation-guidelines.md` used verbatim as the judge prompt (the guidelines were written to be usable this way). The judge outputs, per failure: cognitive function, error type, event span (location), and a rationale.
- **Candidates:** at least one self-hosted open-weight model (vLLM on the DTU cluster) and one frontier API model, so the result doubles as an open-vs-frontier judge comparison.
- **Metrics:** percent agreement and Cohen's κ on the cognitive-function axis; agreement on error type within matching function; location accuracy (span overlap / step distance). Report per-category confusion.
- **Decision rule:** the judge model used in Study 2 is the cheapest candidate whose agreement is acceptable; if none is, that is itself a finding and Study 2 results are reported with the caveat quantified here.

## Study 2 — Systematic vs. stochastic failures (RQ3)

**Question:** can variation across repeated runs distinguish systematic from stochastic agent failures?

- **Runs:** Terminus 2 on Terminal-Bench 2.0 via Harbor (local Docker; raw output format documented in `harbor-format-notes.md`). Screening pass to find tasks where the agent fails at intermediate rates, then **k tasks × n repeats** concentrated there (target order: 15–20 tasks × 8–10 repeats). Agent backend: self-hosted open-weight model — a mid-tier model fails more, and failures are the object of study (constitution §5).
- **Pinning:** one committed config per run batch — Harbor version, task list, agent + model id, budgets, date. Unpinned runs are exploratory and excluded.
- **Labeling:** every failed trajectory is labeled by the Study-1-validated judge. Annotator id = judge model id, recorded on every annotation (constitution §6).
- **Analysis:** per-task success-rate variance; per-task failure-category distribution across repeats. A failure mode is *systematic* if the same (function, error type) recurs across repeats of a task well above chance; *stochastic* if repeats fail in unrelated categories or intermittently succeed. Also report taxonomy coverage (unused categories, escape-hatch usage) as evidence for a future taxonomy revision (constitution §2).

## Stretch — Cross-agent comparison (RQ4)

If time permits: rerun the Study 2 task set with a second Harbor-supported agent under an identical pinned config and compare failure profiles per task. Tasks where all agents fail in the same category suggest task-rooted causes; divergent profiles suggest agent-specific weaknesses.

## Judge validity

There is no human annotation anywhere in this project. The judge's sole validation is Study 1 (agreement with TRAIL's published expert labels); Study 2's labels inherit that validity, quantified by Study 1's metrics.

## Timeline (3 weeks)

1. **Week 1:** taxonomy v0 finalized as judge rubric; Study 1 (TRAIL agreement) run and analyzed.
2. **Week 2:** screening + repeated runs; judge labeling of all failures.
3. **Week 3:** variance analysis, writing. Stretch study only if weeks 1–2 finish early.
