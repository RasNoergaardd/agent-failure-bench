# Results reported in the paper

Every figure in the report is computed from these files. Run configurations are pinned in `research/experiment-log.md`.

## Judge labels

| File | What it is | LSF job |
|---|---|---|
| `judged-trail-gaia-qwen3.8-27b-guidelines-257b897.jsonl` | Qwen3.8-27B labels on the held-out TRAIL gaia split, 115 of 117 traces | 29163236, 29209305 |
| `judged-trail-swe_bench-qwen3.8-27b-guidelines-257b897.jsonl` | The same judge on the TRAIL swe_bench development split | 29154273 |
| `judged-runs-2026-08-30-qwen3.8-27b-ctx98304.jsonl` | Labels on the full benchmark run, 89 trajectories, 348 annotations | 29299961 |
| `judged-runs-repeats-qwen3.8-27b-ctx98304.jsonl` | Labels on the variation run, 118 of 120 trajectories, 457 annotations | 29309083 |

The two TRAIL files have the `rationale` field removed from every annotation. That text paraphrases the gated TRAIL traces, whose terms forbid resharing. Everything the agreement measures use is kept.

## Agent run outcomes

| File | Run | LSF job |
|---|---|---|
| `harbor-full-benchmark-result.json` | All 89 Terminal-Bench 2.0 tasks once, 0 solved | 29270416 |
| `harbor-variation-result.json` | First 12 tasks, ten attempts each, 0 solved | 29299964 |
| `harbor-sensitivity-result.json` | All 89 tasks at 131072 context and timeout multiplier 4, 0 solved | 29350039 |

These are Harbor's job-level summaries. The trajectories themselves are too large to track.

## Reproducing the reported numbers

```bash
afb agreement --judged report-results/judged-trail-gaia-qwen3.8-27b-guidelines-257b897.jsonl --splits gaia --confusion   # needs TRAIL access
afb coverage  --judged report-results/judged-runs-2026-08-30-qwen3.8-27b-ctx98304.jsonl
afb coverage  --judged report-results/judged-runs-repeats-qwen3.8-27b-ctx98304.jsonl
```

`afb variance` needs the variation run's trajectories as well as its labels, so it runs on the cluster where they are stored.
