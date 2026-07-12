# Agent Failure Bench

A framework that both **measures** the performance of agentic AI systems on terminal-based tasks and **systematically explains the causes of their failures**. DTU project course, 2026. This repository is the project's research documentation — there is no code here.

Agents run on [Terminal-Bench 2.0](https://www.tbench.ai) via the [Harbor](https://www.harborframework.com) harness. Failures are classified by an **LLM-as-judge** — validated against the expert annotations of the [TRAIL](https://arxiv.org/abs/2505.08638) benchmark — using a versioned two-axis taxonomy: **cognitive function** (memory / reflection / planning / action / system) × **error type**, plus location in the trajectory, adapted from TRAIL and [AgentErrorTaxonomy](https://arxiv.org/abs/2509.25370).

## Research questions

1. **Taxonomy** — how can existing agent failure taxonomies (TRAIL, AgentErrorTaxonomy) be adapted into a two-axis taxonomy — cognitive function and error type, located in the trajectory — for terminal-based tasks?
2. **Judge validity** — how accurately can an LLM-as-judge classify agent failures, measured as agreement with expert annotations on the TRAIL benchmark?
3. **Systematic vs. stochastic** — can variation across repeated runs distinguish systematic from stochastic agent failures?
4. *(If time permits)* — do failure profiles differ across agents on the same tasks?

## Contents

- `constitution.md` — binding research principles (versioned taxonomy, pinned runs, observation vs. interpretation)
- `research/related-work.md` — TRAIL, AgentErrorTaxonomy, and how this project builds on them
- `research/taxonomy-v0.md` — the failure taxonomy (versioned; revisions require empirical evidence)
- `research/annotation-guidelines.md` — operational definitions and decision rules; used verbatim as the LLM-judge rubric

The repo currently holds only what answers research question 1; documents for RQ2–RQ4 (experiment designs, TRAIL scoring mapping) are added when work on those questions starts.