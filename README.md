# Agent Failure Bench

A framework that both **measures** the performance of agentic AI systems on terminal-based tasks and **systematically explains the causes of their failures**. DTU project course, 2026.

Agents run on [Terminal-Bench 2.0](https://www.tbench.ai) via the [Harbor](https://www.harborframework.com) harness. Failures are classified by an **LLM-as-judge** — validated against the expert annotations of the [TRAIL](https://arxiv.org/abs/2505.08638) benchmark — using a versioned two-axis taxonomy: **cognitive function** (memory / reflection / planning / action / system) × **error type**, plus location in the trajectory, adapted from TRAIL and [AgentErrorTaxonomy](https://arxiv.org/abs/2509.25370).

## Research question

> How can a benchmark be designed to both measure the performance of agentic AI systems and systematically explain the causes of their failures?

Answered through four subquestions:

1. **Taxonomy** — how can existing agent failure taxonomies (TRAIL, AgentErrorTaxonomy) be adapted into a two-axis taxonomy — cognitive function and error type, located in the trajectory — for terminal-based tasks?
2. **Judge validity** — how accurately can an LLM-as-judge classify agent failures, measured as agreement with expert annotations on the TRAIL benchmark? There is no human annotation anywhere in the project — the validated judge is the sole annotator.
3. **Systematic vs. stochastic** — can variation across repeated runs distinguish systematic from stochastic agent failures?
4. *(If time permits)* — do failure profiles differ across agents on the same tasks?

## Research documents

- `constitution.md` — binding research principles (versioned taxonomy, pinned runs, observation vs. interpretation)
- `research/related-work.md` — TRAIL, AgentErrorTaxonomy, and how this project builds on them
- `research/taxonomy-v0.md` — the failure taxonomy (versioned; revisions require empirical evidence)
- `research/annotation-guidelines.md` — operational definitions and decision rules; used verbatim as the LLM-judge rubric
- `research/trail-mapping.md` — how TRAIL's expert categories translate into taxonomy v0, and what that makes scoreable

## Code

Python ≥ 3.12, managed with `uv`. Install with `uv sync`.

| Module | Role |
|---|---|
| `afb/taxonomy.py` + `data/taxonomy-v0.yaml` | the taxonomy as data; the single source every other module reads |
| `afb/annotation.py` | the judge's output contract, validating both axes and the escape hatch |
| `afb/trajectory.py` | the normalized trajectory: an ordered list of events, whatever the source |
| `afb/prompt.py` | assembles the judge prompt from the taxonomy, the guidelines verbatim, and a trajectory |
| `afb/judge.py` | the judge itself, over any OpenAI-compatible endpoint (self-hosted vLLM or a gateway) |
| `afb/trail.py` | TRAIL ingest: span trees flattened to trajectories, plus expert annotations |
| `afb/mapping.py` + `data/trail-mapping-v0.yaml` | TRAIL categories translated into taxonomy codes |
| `afb/agreement.py` | subquestion 2: judge validity against the experts |
| `afb/coverage.py` | subquestion 1: escape-hatch and unused-code evidence for the next taxonomy version |
| `afb/harbor.py` | Terminal-Bench runs ingested into the same trajectory format, reading Harbor's ATIF trajectory files |
| `afb/runs.py` | subquestions 3 and 4: systematic vs. stochastic, and failure profiles per agent |

### Usage

```bash
afb taxonomy                                    # the taxonomy and its TRAIL mapping status
afb prompt --split gaia --index 0 --out p.txt   # exactly what the judge is asked
afb judge-trail --split gaia                    # label TRAIL traces (resumable)
afb agreement --judged results/judged-trail-gaia-<model>.jsonl --confusion
afb coverage  --judged results/judged-trail-gaia-<model>.jsonl
afb judge-runs --runs <harbor-results-dir>      # label Terminal-Bench runs
afb variance  --runs <dir> --judged results/judged-runs-<model>.jsonl
afb profiles  --runs <dir> --judged results/judged-runs-<model>.jsonl
```

Output paths carry the judge model, because several models are run over the same
data to separate judge capacity from taxonomy quality, and `--resume` is on by
default. `afb` refuses to append one model's labels to another's.

The judge endpoint is configuration, not code: `AFB_JUDGE_BASE_URL`,
`AFB_JUDGE_MODEL`, and `AFB_JUDGE_API_KEY` (falling back to
`OPENROUTER_API_KEY`). `AFB_JUDGE_TEMPERATURE` pins sampling, which a self-hosted
model needs since vLLM otherwise honours the checkpoint's default.
`AFB_JUDGE_MAX_TOKENS` and `AFB_JUDGE_EXTRA_BODY` cover reasoning models, whose
thinking is billed against the same budget as the answer:
`AFB_JUDGE_EXTRA_BODY='{"chat_template_kwargs": {"enable_thinking": false}}'`
turns it off on vLLM.

Every stored annotation set records its annotator — judge model, taxonomy
version, guidelines digest, char budget, temperature, and the attempts and
finish reasons behind it — as constitution principle 6 requires.

### Data

TRAIL is gated and its terms forbid resharing, so `data/` and `results/` are not tracked. Accept the terms on the hub, set `HF_TOKEN`, and the ingest downloads and caches the splits on first use.

### Tests

`uv run pytest`. The TRAIL tests skip automatically when the dataset has not been downloaded.
