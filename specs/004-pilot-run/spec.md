# Spec 004 — Pilot Run & Empirical Taxonomy Validation

**Purpose:** collect real Terminus 2 trajectories on Terminal-Bench 2.0, annotate them with taxonomy v0, and produce the evidence that drives the v0 → v1 revision — the empirical half of subquestion 1.

## Requirements

- **R1 — Pinned run configuration.** A committed config file records: Harbor version, dataset (`terminal-bench/terminal-bench-2`) and task list, agent (Terminus 2 + version), LLM model id, budgets/timeouts, date, concurrency. A run script (`scripts/run_pilot.sh` or `afb pilot` subcommand) executes exactly that config. Unpinned exploratory runs go to `data/raw/scratch/` and never enter the dataset (constitution §4).
- **R2 — Sample.** Target **30–50 trajectories** with failures oversampled (failures are the object of study): first a screening pass over a task subset to find tasks where Terminus 2 fails, then repeated runs concentrated there. Include ≥5 successful trajectories (recovered-error annotation, and baseline for subquestion 3 later). Spread over ≥10 distinct tasks and ≥3 Terminal-Bench task categories so taxonomy coverage isn't hostage to one task type. Repeated runs of the same task are explicitly welcome — they seed the variance analysis (subquestion 3).
- **R3 — Full ingest.** Every collected run is parsed by the spec 002 ingest into `data/trajectories/`; zero silent skips; raw output preserved under `data/raw/` (gitignored) with hashes referenced from the normalized files.
- **R4 — Annotation.** All failed trajectories annotated by Rasmus with the tool (spec 003) under the guidelines; ≥20% of them double-annotated after a ≥1-week gap or by a second person if available, for an agreement estimate (report percent agreement + Cohen's κ on cognitive function; note the limits of self-agreement if no second annotator).
- **R5 — Coverage analysis** (`afb.analysis`): per-category annotation counts; unused categories; `NEW-?` occurrences with their proposed descriptions; root-cause vs. cascade distribution; per-cognitive-function distribution; confusion/friction notes from the annotator. Output: a markdown report committed to `research/pilot-report.md`.
- **R6 — Taxonomy revision.** `research/taxonomy-v1.md` written from the report: every added category traces to `NEW-?` evidence or unclassifiable failures; every removed/merged category to zero/near-zero usage or systematic confusion; retentions of unused categories need explicit rationale (e.g., "structurally expected under different agents"). This satisfies spec 001 R5.

## Acceptance criteria

- [ ] Committed pinned config + run script; rerunning the script reproduces the run setup exactly (modulo LLM stochasticity).
- [ ] 30–50 normalized trajectories in `data/trajectories/`, ≥10 tasks, ≥3 categories, ≥5 successes, all parseable.
- [ ] All failed trajectories annotated; double-annotation subset done; agreement numbers in the report.
- [ ] `research/pilot-report.md` with all R5 statistics.
- [ ] `research/taxonomy-v1.md` with evidence-cited revision log; Rasmus sign-off.

## Non-goals

- LLM-judge annotation (subquestion 2), formal variance analysis (subquestion 3), other agents (subquestion 5) — though the collected data should be reusable for all three.

## Open questions (resolve before running)

- Which LLM backs Terminus 2 for the pilot (cost vs. failure-richness trade-off — a mid-tier model fails more interestingly than a frontier one; decide with Rasmus when Harbor is installed and per-task cost is measurable).
- Local Docker vs. remote executor (`--env daytona`) — decide from a 2-task smoke run.
