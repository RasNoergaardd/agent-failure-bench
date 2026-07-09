# Plan 004 — Pilot Run & Empirical Taxonomy Validation

Prerequisites: specs 002 (models + ingest) and 003 (annotation tool) implemented; Docker + Harbor installed locally.

1. **Smoke run** — install Harbor (`uv tool install harbor` or per docs), verify with the oracle agent, then run Terminus 2 on 2 tasks. Deliverables: `harbor-format-notes.md` (unblocks the 002 parser), per-task cost estimate, local-vs-remote decision, model choice with Rasmus.
2. **Screening pass** — 1 run each over ~20 tasks spread across ≥5 Terminal-Bench categories; identify failing tasks.
3. **Collection pass** — repeated runs on failing tasks (3–5 runs each on a handful — doubles as subquestion 3 seed data) until 30–50 total with ≥5 successes. Pin everything in `pilot-config.*` before this pass.
4. **Ingest + verify** — parse all runs, check acceptance criteria R3, commit normalized trajectories.
5. **Annotation campaign** — Rasmus annotates all failures per the guidelines, keeping a friction log; schedule the ≥20% re-annotation ≥1 week later.
6. **Coverage analysis** — implement `afb.analysis.coverage` (counts per category/function, `NEW-?` list, root-cause/cascade stats, agreement) emitting `research/pilot-report.md`.
7. **Revision** — draft `taxonomy-v1.md` from the report; review with Rasmus; sign off.

**Sequencing note:** step 1 can start as soon as 002's models exist (parser is written against real output from this step); the annotation tool (003) only needs to be ready by step 5.

**Cost control:** decide model + budget caps at step 1; hard cap total pilot spend and record actuals in the report.
