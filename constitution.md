# Constitution — Agent Failure Bench

Non-negotiable principles for this project. Every document and experiment must comply. Amendments to this document require an explicit, dated changelog entry at the bottom.

## Purpose

This repository answers the research question: *How can a benchmark be designed to both measure the performance of agentic AI systems and systematically explain the causes of their failures?* The repository is **documentation only** — research questions, taxonomy, guidelines, and experiment designs. Every document must serve a research question; anything with no traceable link to one does not belong.

## Principles

### 1. Design before execution
No experiment runs before its design is written down (`research/experiment-design.md`): what is measured, on what data, with which metrics, and what decision the result feeds. Results that deviate from the design mean either the run or the design was wrong — record which, in the same change.

### 2. Taxonomy changes are versioned and empirically justified
The failure taxonomy (`research/taxonomy-v*.md`) is a research artifact, not a config file. Categories are added, removed, merged, or redefined **only** through a new version with a revision-log entry citing the empirical evidence (e.g., "category X unused across 42 trajectories", "escape hatch used 7 times with pattern Y").

### 3. Annotations are reproducible from raw data
Every annotation must reference a stored, immutable trajectory by id and event span. Raw harness output is preserved; any normalized form must be re-derivable from it. Never hand-edit trajectories.

### 4. Every experiment run is pinned
A run is only citable if its configuration is recorded: harness (Harbor) version, benchmark (Terminal-Bench) version and task list, agent name and version, LLM model id (including self-hosted weights + serving stack version), date, and any seeds or step/time budgets. Unpinned runs are exploratory and must not enter the dataset.

### 5. Failures are the object of study
Success rate is a summary statistic; the unit of analysis is the failed trajectory. Design decisions (sampling, model choice, tooling) optimize for making failures inspectable, classifiable, and comparable — not for maximizing benchmark scores.

### 6. Distinguish observation from interpretation
What happened (events, outputs, test results) is stored separately from judgments about it (annotations, labels, root-cause flags). An annotation always records its annotator (the judge model id). This separation is a precondition for the judge-agreement study (RQ2).

## Changelog

- 2026-07-09: Initial version.
- 2026-07-12: Scope reset for the 3-week timeline. Repository reduced to documentation only (code, schemas, and specs removed; recoverable in git history). Manual annotation dropped — the sole annotator is an LLM judge validated against TRAIL's published expert annotations. Principle 1 reworded from "Spec before code" to "Design before execution"; principles 3 and 6 reworded to be implementation-free. Purpose section updated accordingly.
- 2026-07-12 (b): Human spot-check removed — the project contains **no** human annotation of any kind; judge validity rests solely on the TRAIL agreement study. Principle 6 amended (human annotator id dropped).
