# Constitution — Agent Failure Bench

Non-negotiable principles for this project. Every spec, implementation, and experiment must comply. Amendments to this document require an explicit, dated changelog entry at the bottom.

## Purpose

This repository answers the research question: *How can a benchmark be designed to both measure the performance of agentic AI systems and systematically explain the causes of their failures?* Everything built here must serve a research subquestion; code with no traceable link to one does not belong.

## Principles

### 1. Spec before code
No feature is implemented without an approved spec in `specs/NNN-*/spec.md`. Specs state requirements and acceptance criteria; `plan.md` states the approach; `tasks.md` tracks execution. Code that deviates from its spec means either the code or the spec is wrong — fix one, in the same change.

### 2. Taxonomy changes are versioned and empirically justified
The failure taxonomy (`research/taxonomy-v*.md`) is a research artifact, not a config file. Categories are added, removed, merged, or redefined **only** through a new version with a revision-log entry citing the empirical evidence (e.g., "category X unused across 42 pilot trajectories", "7 annotations required the 'no fitting category' escape hatch with pattern Y"). This discipline is what lets subquestion 1 claim categories were "added or removed empirically."

### 3. Annotations are reproducible from raw data
Every annotation must reference a stored, immutable trajectory by id and event span. Raw harness output is preserved alongside the normalized form; the normalized form must be re-derivable from the raw form by the ingest code. Never hand-edit normalized trajectories.

### 4. Every experiment run is pinned
A run is only citable if its configuration is recorded: harness (Harbor) version, benchmark (Terminal-Bench) version and task list, agent name and version, LLM model id, date, and any seeds or step/time budgets. Unpinned runs are exploratory and must not enter the dataset.

### 5. Failures are the object of study
Success rate is a summary statistic; the unit of analysis is the failed trajectory. Design decisions (data model, tooling, sampling) optimize for making failures inspectable, classifiable, and comparable — not for maximizing benchmark scores.

### 6. Distinguish observation from interpretation
The data model stores what happened (events, outputs, test results) separately from judgments about it (annotations, labels, root-cause flags). An annotation always records its annotator (human id or judge model id) — human and LLM-judge labels are never conflated. This separation is a precondition for subquestion 2 (judge–human agreement).

## Changelog

- 2026-07-09: Initial version.
