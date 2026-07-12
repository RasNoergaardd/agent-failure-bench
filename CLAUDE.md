# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## What this project is

Agent Failure Bench: a DTU 3-week project course (2026) designing a framework that measures agentic AI performance on terminal-based tasks and systematically explains failure causes. Agents run on **Terminal-Bench 2.0** via the **Harbor** harness; failures are classified with a two-axis taxonomy (**cognitive function × error type**, plus trajectory location) by an **LLM-as-judge**, validated against the TRAIL benchmark's expert annotations.

**This repository is documentation only.** It holds the research questions, taxonomy, guidelines, and experiment designs — no code. Earlier implementation work (Pydantic models, Harbor ingest, annotation TUI, specs, JSON schemas) was removed in the 2026-07-12 scope reset and lives in git history. Do not add code here; there is no manual annotation in scope — the annotator is the validated LLM judge.

## Ground rules

Read `constitution.md` first — its principles are binding (design-before-execution, versioned taxonomy revisions, pinned experiment runs, observation separate from interpretation). Amendments require a dated changelog entry.

- `research/taxonomy-v*.md` is versioned and never edited in place; changes require a new version with empirical evidence.
- `research/annotation-guidelines.md` doubles as the LLM-judge prompt — keep it operational (definitions, examples, decision rules), not narrative.
- `research/experiment-design.md` defines the studies for the research questions (see README) and the 3-week timeline.
- `research/harbor-format-notes.md` records the *observed* Harbor output format; anything marked UNOBSERVED must not be asserted as fact.

## Research context

The taxonomy adapts **TRAIL** (arXiv 2505.08638; error types under reasoning / system-execution / planning-coordination) and **AgentErrorTaxonomy** (arXiv 2509.25370; five cognitive modules: memory, reflection, planning, action, system). When citing facts about these works, use `research/related-work.md` and `research/taxonomy-v0.md` rather than memory.

Infrastructure facts for experiment planning: models can be self-hosted (vLLM on a DTU GPU cluster); Harbor itself needs Docker and runs locally against the served endpoint.
