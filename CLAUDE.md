# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Agent Failure Bench (`afb`): a research project (DTU project course) building a benchmark that both measures agentic AI performance on terminal-based tasks and systematically explains failure causes. Agents run on **Terminal-Bench 2.0** via the **Harbor** harness; their trajectories are ingested, normalized, and annotated with a two-axis failure taxonomy (**cognitive function × error type**, plus trajectory location).

## Development is spec-driven

Read `constitution.md` first — its principles are binding (spec-before-code, versioned taxonomy revisions, reproducible annotations, pinned experiment runs).

- `specs/NNN-<feature>/` holds `spec.md` (requirements + acceptance criteria), `plan.md` (approach), `tasks.md` (execution checklist). Implement only what a spec covers; update the spec in the same change if reality diverges.
- `research/` holds research artifacts: `taxonomy-v*.md` (the failure taxonomy — versioned, never edited in place), `annotation-guidelines.md`, `related-work.md`.

## Commands

```sh
uv sync                 # install/refresh environment
uv run pytest           # run all tests
uv run pytest tests/test_models.py -k <name>   # single test
uv run afb --help       # CLI entry point (afb.cli:main)
```

## Architecture

Pipeline: **run → ingest → annotate → analyze**, all sharing the Pydantic models in `src/afb/models/`.

- `src/afb/models/` — core schemas: `Trajectory` (one agent run: task, agent, model, outcome, events), `Event` (one step: command / output / reasoning / tool-call), `TaxonomyLabel` (cognitive function × error type), `FailureAnnotation` (label + event span + root-cause flag + annotator + rationale). Everything downstream depends on these; change them only via spec 002.
- `src/afb/ingest/` — parses raw Harbor run output into normalized `Trajectory` objects (spec 002). Raw output is preserved; normalized form must be re-derivable.
- `src/afb/annotate/` — Textual TUI for humans to step through a trajectory and attach `FailureAnnotation`s (spec 003).
- `src/afb/analysis/` — category-coverage statistics over annotations, driving empirical taxonomy revisions (spec 004).
- `data/trajectories/`, `data/annotations/` — normalized, version-controlled datasets. `data/raw/` is gitignored.

Key invariant: observations (trajectories) and interpretations (annotations) are separate objects linked by trajectory id + event span, and every annotation records its annotator (human or judge-model id) — required for the LLM-judge agreement study.

## Research context

The taxonomy adapts **TRAIL** (arXiv 2505.08638; error types under reasoning / system-execution / planning-coordination) and **AgentErrorTaxonomy** (arXiv 2509.25370; five cognitive modules: memory, reflection, planning, action, system). See `research/related-work.md` for details and `research/taxonomy-v0.md` for the current taxonomy. When citing facts about these works, use those documents rather than memory.
