# Harbor run output format (observed)

Observed from a real run on 2026-07-09: Harbor **0.18.0**, dataset `terminal-bench/terminal-bench-2`, agent `oracle`, local Docker, 2 tasks (`circuit-fibsqrt`, `make-mips-interpreter`), both reward 1.0. Command:

```sh
harbor run -d terminal-bench/terminal-bench-2 -a oracle -l 2 -n 1 -o data/raw/smoke-oracle --job-name smoke-oracle -y -q
```

Everything below is from inspecting that output. Anything not yet observed is marked **UNOBSERVED** — per spec 002 R6, do not code against it until seen.

## Directory layout

```
<jobs-dir>/<job-name>/                  # "job" = one harbor run invocation
├── config.json                         # resolved JobConfig
├── job.log
├── lock.json                           # schema_version 2; harbor.version pin lives here
├── result.json                         # aggregate stats (n trials, mean reward)
└── <task>__<suffix>/                   # one "trial" dir per task attempt, e.g. circuit-fibsqrt__ZAV5p9S
    ├── config.json                     # trial config
    ├── lock.json                       # trial pin: task name/digest/source, agent, environment
    ├── result.json                     # ← the envelope the parser reads (see below)
    ├── trial.log                       # harness-side log
    ├── agent/                          # agent-specific logs — format depends on the agent
    │   └── oracle.txt                  # oracle: single EMPTY file (no trajectory; replays reference solution)
    ├── verifier/
    │   ├── ctrf.json                   # CTRF-format pytest report: summary + per-test status/duration
    │   ├── reward.txt                  # "1" (observed); presumably "0" on failure — UNOBSERVED
    │   └── test-stdout.txt             # raw pytest stdout
    └── artifacts/manifest.json
```

## Trial `result.json` fields that matter to us

| Field | Observed value/shape | Maps to `Trajectory` |
|---|---|---|
| `trial_name` | `circuit-fibsqrt__ZAV5p9S` | `trajectory_id` |
| `task_name` | `terminal-bench/circuit-fibsqrt` | `task_id` |
| `source` | `terminal-bench/terminal-bench-2` | `task_source` |
| `task_id.ref`, `task_checksum` | sha256 digests | `run_config.extra` (pins) |
| `agent_info` | `{name: "oracle", version: "1.0.0", model_info: null}` | `agent`, `agent_version`, `model` |
| `verifier_result.rewards.reward` | `1.0` | `outcome` (see mapping) |
| `exception_info` | `null` | `outcome` (see mapping) |
| `started_at` / `finished_at` + per-phase blocks (`environment_setup`, `agent_setup`, `agent_execution`, `verifier`) | ISO timestamps | `run_config.extra` / analysis later |
| `agent_result` | all-null for oracle (`n_input_tokens`, `cost_usd`, `rollout_details`, …) | cost tracking later (spec 004) |
| `step_results` | `null` for oracle | possibly episode data for real agents — UNOBSERVED |

Harness version: job-level `lock.json` → `harbor.version` (`"0.18.0"`).

## Outcome mapping (parser rule)

- `exception_info != null` → `Outcome.ERROR`
- else `reward >= 1.0` → `Outcome.SUCCESS`
- else → `Outcome.FAILURE`

Only SUCCESS observed so far; the failure/error shapes must be confirmed against the first failing Terminus 2 run before the pilot dataset is ingested.

## Task instruction

**Not present anywhere in the run output.** Task definitions live in the registry; fetch with:

```sh
harbor tasks download terminal-bench/<name>   # → <name>/instruction.md, task.toml, tests/, solution/, environment/
```

The parser therefore accepts an optional tasks directory to resolve `instruction.md` per task; without it, `Trajectory.instruction` stays `None`.

## Agent trajectory (events) — the critical open item

The `agent/` directory content is **agent-specific**. The oracle produces no trajectory at all (empty `oracle.txt`, `rollout_details: null`) — so this smoke run pins down the *trial envelope* but **not** the event-stream format. **UNOBSERVED: the `agent/` layout for `terminus-2`** — the event extractor for it must be written from the first real Terminus 2 run (needs an LLM API key). Until then the parser has a per-agent extractor registry: `oracle` → zero events; any unknown agent → loud error (spec 002 R7 — no silent skips, no guessed formats).

## Consequences for the data model

- `Trajectory.model` must be optional: agents can run without an LLM (oracle: `model_info: null`). Spec 002 R1 updated accordingly.
