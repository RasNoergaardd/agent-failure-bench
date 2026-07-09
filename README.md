# Agent Failure Bench

A benchmark framework that both **measures** the performance of agentic AI systems on terminal-based tasks and **systematically explains the causes of their failures**. DTU project course, 2026.

Agents run on [Terminal-Bench 2.0](https://www.tbench.ai) via the [Harbor](https://www.harborframework.com) harness; trajectories are normalized, then annotated with a versioned failure taxonomy that classifies each failure by **cognitive function** (memory / reflection / planning / action / system) and **location in the trajectory**, adapted from [TRAIL](https://arxiv.org/abs/2505.08638) and [AgentErrorTaxonomy](https://arxiv.org/abs/2509.25370).

## Layout

- `constitution.md` — binding project principles
- `specs/` — feature specs driving all development (spec-driven)
- `research/` — research artifacts: taxonomy (versioned), annotation guidelines, related work
- `src/afb/` — models · ingest · annotation TUI · analysis
- `data/` — normalized trajectories and annotations

## Development

```sh
uv sync
uv run pytest
uv run afb schema     # export JSON Schemas
```

See `CLAUDE.md` for architecture details.
