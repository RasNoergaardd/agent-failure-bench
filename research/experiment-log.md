# Experiment log

Pinned runs and the decisions they drove, per `constitution.md` principles 4
(every run is pinned) and 6 (observation separate from interpretation).

Each run records **what was measured** under *Observation*. What it was taken to
*mean*, and what changed as a result, is recorded separately under *Decisions*
further down, so a later re-reading of the numbers is not contaminated by the
interpretation placed on them at the time.

Runs marked **exploratory** are not citable.

---

## Run 2026-07-30-A — judge validation against TRAIL, swe_bench

| Field | Value |
|---|---|
| Purpose | RQ2, establish judge agreement with TRAIL expert annotations |
| Judge model | `Qwen/Qwen3-14B-AWQ` (4-bit AWQ) |
| Serving stack | vLLM, self-hosted, one A100-PCIE-40GB, DTU HPC `gpua100` |
| vLLM version | *unrecorded, see gaps below* |
| Sampling | temperature 0, max_tokens 8192 |
| Context | `--max-model-len 40960`, prompt char budget 100 000 |
| Taxonomy | v0 (`src/afb/data/taxonomy-v0.yaml`) |
| TRAIL mapping | v0 (`src/afb/data/trail-mapping-v0.yaml`) |
| Match tolerance | 0 events |
| Data | TRAIL `swe_bench` split, all 31 traces |
| LSF job | 28984526, 2026-07-30 11:48:06 to 11:57:54 CEST |
| Output | `results/judged-trail-swe_bench.jsonl` (gitignored) |

### Observation

Pipeline: 31 of 31 traces judged, 0 failures. 5 of 26 newly judged traces
received 0 annotations.

| Metric | Value |
|---|---|
| expert errors / scoreable | 256 / 238 |
| judge annotations | 77 |
| escape hatch used | 0 |
| matched pairs | 24 |
| localization precision / recall / F1 | 0.312 / 0.101 / 0.152 |
| function accuracy (n=24) | 0.125 |
| function kappa | −0.077 |
| code accuracy (n=14) | 0.143 |
| severity accuracy | 0.458 |

Confusion, expert function to judge function: memory→action 9, action→planning 4,
memory→reflection 4, action→action 3, memory→planning 2, action→reflection 1,
action→system 1. Only memory and action appear on the expert axis.

Codes never used: MEM-1, MEM-2, MEM-3, RFL-4, RFL-5, ACT-4, ACT-6, SYS-1, SYS-2,
SYS-4, SYS-5.

---

## Run 2026-07-30-B — judge validation against TRAIL, gaia

Identical configuration to run A except:

| Field | Value |
|---|---|
| Data | TRAIL `gaia` split, all 117 traces |
| LSF job | 28984528, 2026-07-30, finished 12:19:31 CEST |
| Output | `results/judged-trail-gaia.jsonl` (gitignored) |

### Observation

Pipeline: 117 of 117 traces judged, 0 failures. 30 of 117 traces received 0
annotations.

| Metric | Value |
|---|---|
| expert errors / scoreable | 585 / 510 |
| judge annotations | 193 |
| escape hatch used | 0 |
| matched pairs | 67 |
| localization precision / recall / F1 | 0.347 / 0.131 / 0.191 |
| function accuracy (n=67) | 0.149 |
| function kappa | −0.084 |
| code accuracy (n=63) | 0.048 |
| severity accuracy | 0.537 |

Per-function recall over matched pairs: memory 0/23, action 1/15, reflection
6/15, planning 3/12, system 0/2.

Code usage: RFL-3 47, ACT-5 30, PLN-1 29, PLN-5 20, PLN-3 14, ACT-3 11, RFL-5 9,
RFL-2 8, SYS-3 7, MEM-2 6, PLN-2 5, RFL-1 2, ACT-1 2, MEM-1 1, PLN-4 1, ACT-2 1.
Never used: MEM-3, RFL-4, ACT-4, ACT-6, SYS-1, SYS-2, SYS-4, SYS-5.

---

## Sensitivity check — match tolerance (run A configuration, 5-trace subset)

Re-scoring the same stored labels while varying how far apart an expert error
and a judge annotation may sit and still be treated as the same error.

| tolerance | matched | localization F1 | function accuracy | kappa |
|---|---|---|---|---|
| 0 | 5 | 0.20 | 0.20 | 0.048 |
| 1 | 8 | 0.32 | 0.125 | −0.077 |
| 2 | 10 | 0.40 | 0.10 | −0.098 |
| 3 | 10 | 0.40 | 0.00 | −0.190 |

Localization F1 rises monotonically while function accuracy falls monotonically.

---

## Sensitivity check — TRAIL mapping variants (2026-07-31)

Re-scoring the stored labels of runs A and B under three readings of
Instruction Non-compliance. No new inference; `afb agreement --mapping`.

| mapping | Instruction Non-compliance is | swe_bench accuracy / kappa | gaia accuracy / kappa |
|---|---|---|---|
| v0 | memory (MEM-3) | 0.125 / −0.077 | 0.149 / −0.084 |
| v1 | planning (PLN-2) | 0.167 / −0.176 | 0.149 / −0.100 |
| v2 | no function claimed | 0.214 / −0.020 | 0.159 / −0.083 |

Function-decidable pairs fall from 24 to 14 (swe_bench) and 67 to 63 (gaia)
under v2, so the category accounts for 10 of 24 and 4 of 67 matched pairs.

### Matched pairs by TRAIL category, both splits pooled (91 pairs)

13 of 91 pairs agree on cognitive function; 5 of 77 code-decidable pairs agree
on the error code. Disagreement is distributed across every category rather
than concentrated in one. The largest single rows:

| TRAIL category | expert function | judge code | n |
|---|---|---|---|
| Language-only | memory | RFL-3 | 7 |
| Instruction Non-compliance | memory | ACT-3 | 5 |
| Tool-related | reflection | RFL-3 | 5 (function agrees) |
| Tool-related | reflection | MEM-2 | 4 |
| Tool Selection Errors | action | RFL-3 | 4 |

RFL-3 appears as the judge's code in **23 of 91 matched pairs**, drawn from
eight different TRAIL categories. ACT-5 appears in 15, drawn from six.

---

## Diagnostic — baselines and prompt length (2026-08-17)

No new inference. Both parts re-read the stored labels and the prompts that
produced them, in the manner of the sensitivity checks above.

### Baselines on the classification axes

Runs A and B reported accuracy with no reference point. `afb agreement` now
prints uniform chance (the size of the label space) and the majority-class rate
(the expert marginal, which is the best a rater can do while ignoring the
trajectory).

| Split | axis | judge | uniform chance | majority class | n |
|---|---|---|---|---|---|
| swe_bench | function | 0.125 | 0.200 | 0.625 | 24 |
| swe_bench | code | 0.143 | 0.042 | 0.643 | 14 |
| gaia | function | 0.149 | 0.200 | 0.343 | 67 |
| gaia | code | 0.048 | 0.042 | 0.238 | 63 |

On the cognitive-function axis the judge scores **below uniform chance on both
splits**, and far below always answering the majority class. On the code axis it
is above the 1-in-24 chance rate but roughly a quarter of the majority rate.

All other run A and B figures reproduce unchanged under the new code.

### Prompt length against zero-annotation traces

Fixed prompt overhead, everything preceding the trajectory, is 18 297 characters
(taxonomy 8 379, guidelines 5 853, output schema 3 242, task instructions 823),
roughly 4 600 tokens. Runs A and B used `CHAR_BUDGET=100000` inside
`--max-model-len 40960` with `max_tokens 8192`.

| Split | prompt chars, min / median / max | over 100k | traces |
|---|---|---|---|
| swe_bench | 18 522 / 87 752 / 104 300 | 2 | 31 |
| gaia | 43 259 / 60 037 / 122 732 | 12 | 117 |

Comparing the traces that returned nothing against those that returned at least
one annotation:

| Split | group | n | median prompt chars | median events |
|---|---|---|---|---|
| swe_bench | zero annotations | 5 | 85 485 | 34 |
| swe_bench | annotated | 26 | 87 769 | 32 |
| gaia | zero annotations | 30 | 60 052 | 15 |
| gaia | annotated | 87 | 59 983 | 15 |

The two groups are indistinguishable on both length measures.

### Provenance recorded from here on

`research/annotation-guidelines.md` is unchanged since 2026-07-12, before runs A
and B, so its digest
`bc2c95ecbc427329647a5bd63fddd65c612d61092f4a2907b673e40d8d0744af` is the
procedure those runs used and they remain comparable with later ones. Annotation
sets now carry the judge model id, taxonomy version, guidelines digest, char
budget, temperature, attempts used and per-attempt finish reasons, which
principle 6 requires and runs A and B lack.

---

## Capacity ladder — swe_bench (2026-08-17)

D6 required judge capacity to be varied before any guideline revision. No paid
frontier inference is available to this project, so capacity is varied across
self-hosted open-weight judges instead. Taxonomy v0, mapping v0, tolerance 0,
temperature 0, char budget 100 000, swe_bench, in every rung.

| Rung | Judge | Thinking | max_tokens | vLLM | LSF job |
|---|---|---|---|---|---|
| A | Qwen3-14B-AWQ | not controlled | 8192 | unrecorded | 28984526 |
| C | Qwen3-14B-AWQ | on | 14336 | 0.26.0 | 29128736 |
| D | Qwen3-32B-AWQ | off | 8192 | 0.27.1 | 29132516 |
| E | Qwen3-14B-AWQ | off | 8192 | 0.27.1 | 29132705 |

### Observation

| Rung | traces | annotations | matched | F1 | function acc | decidable |
|---|---|---|---|---|---|---|
| A | 31/31 | 77 | 24 | 0.152 | 0.125 | 24 |
| C | 31/31 | 84 | 17 | 0.106 | 0.118 | 17 |
| D | 31/31 | 268 | 75 | 0.296 | 0.080 | 75 |
| E | 30/31 | 229 | 40 | 0.175 | 0.075 | 40 |

Uniform chance on the function axis is 0.200 throughout. No rung reaches it.

**D and E are the controlled pair**: identical serving stack, thinking setting
and token budget, differing only in model size. From E to D, matched pairs rise
40 → 75 and localization F1 0.175 → 0.296, while function accuracy moves 0.075 →
0.080 (3 of 40 against 6 of 75).

Rung D confusion, expert function against judge function, 75 pairs: action →
planning 34, memory → planning 22, planning → planning 6, memory → reflection 5,
action → reflection 3, memory → action 2, planning → reflection 2, reflection →
planning 1. The judge names planning in 63 of 75 pairs; the experts name it in 8.
Answering "action" for every pair would have scored 37/75 = 0.493.

Rung D code usage, 268 annotations: PLN-1 143, PLN-3 50, RFL-1 27, PLN-5 15,
ACT-3 14, ACT-5 8, RFL-2 5, ACT-1 3, PLN-4 2, RFL-3 1. Fourteen of 24 codes
unused, including all three memory codes and all five system codes.

**The dominant code differs by rung.** RFL-3 in run A (47 of 193 on gaia,
6 of 77 here), PLN-5 and PLN-3 in rung C (18 and 16 of 84), PLN-1 in rung D
(143 of 268, 53%). Rung D used RFL-3 once.

### Gaps in this ladder

- **Rung E judged 30 of 31 traces.** The failure was not diagnosed before the
  guidelines were revised, so E's figures rest on a subset that excludes one
  trace and are not exactly comparable to D's.
- **Rungs A and C ran vLLM 0.26.0; D and E ran 0.27.1** (torch 2.11.0 → 2.13.0),
  because the virtual environment was rebuilt when the caches moved to
  `/work3/s225786`. A against E is therefore not a clean thinking-on/off
  comparison. D against E is clean.
- **Run A's thinking mode was never set.** Rung C (thinking on) produced 84
  annotations and rung E (thinking off) produced 229, so run A's 77 is
  consistent with thinking having been on by default. Runs A and B were
  therefore probably thinking-on runs, which was not recorded at the time.
- **A run at max_tokens 16384 (job 29128252) is discarded**: 5 of 31 traces
  exceeded the 40 960-token context and failed, and the five were the longest,
  so the surviving 26 are a biased subset. A subsequent attempt to raise
  `--max-model-len` to 49152 (job 29128633) was refused by vLLM, since 40960 is
  Qwen3's `max_position_embeddings` and cannot be exceeded safely.

---

## Guidelines revision (2026-08-17)

`research/annotation-guidelines.md` changed from digest
`bc2c95ec…0744af` to `a095d868…dc55c`. Prompt overhead grows from 18 297 to
24 680 characters (~4 574 to ~6 170 tokens); the longest swe_bench prompt is now
~27 670 tokens, which leaves room for 8 192 output tokens inside the 40 960
context but no longer for 14 336.

Four changes, each traceable to an observation above:

1. **An ordered test for the cognitive function axis.** The file previously told
   the judge to "choose cognitive function first" and gave no procedure for
   doing so; all eight tie-breakers were code-versus-code. The axis without a
   decision rule is the axis scoring 0.080.
2. **Planning is no longer reachable as a residual.** The test requires a
   positive showing that the approach could not have worked even if executed
   perfectly, and directs unplaceable errors to `NEW-?` instead.
3. **Evidence requirements for PLN-1, PLN-5 and RFL-3**, the three codes that can
   be narrated onto any failed trajectory. PLN-1 now requires quoting both the
   requirement and the contradicting agent statement, and explicitly rejects the
   circular reading "the task failed, so the agent misunderstood it".
4. **Positive triggers for memory**, plus a re-check pass when every annotation
   in a trajectory carries the same function or code.

The taxonomy itself is unchanged. Under principle 2 a category change needs a new
version, and under D3 the evidence for one must come from Terminal-Bench rather
than TRAIL; these are decision rules for applying v0, which
`CLAUDE.md` assigns to the guidelines.

No base rate was written into the guidelines. Telling the judge how often experts
use each function would fit the prompt to the evaluation set and invalidate the
agreement study.

---

## Run 2026-08-18 — guidelines v1, Qwen3-32B-AWQ, swe_bench

The first test of the revised guidelines. Rung D's configuration exactly, with
only the guidelines digest changed, so the pair is controlled.

| Field | Value |
|---|---|
| Judge model | `Qwen/Qwen3-32B-AWQ` |
| Serving stack | vLLM 0.27.1, torch 2.13.0+cu130, one A100-PCIE-40GB |
| Sampling | temperature 0, max_tokens 8192, thinking off |
| Context | `--max-model-len 40960`, prompt char budget 100 000 |
| Guidelines | `a095d868…dc55c` (rung D used `bc2c95ec…0744af`) |
| Taxonomy / mapping | v0 / v0 |
| Data | TRAIL `swe_bench`, all 31 traces |
| Output | `results/judged-trail-swe_bench-qwen3-32b-awq-guidelines-v1.jsonl` |
| LSF job | 29135597 |

### Observation

31 of 31 traces judged. 157 annotations, against rung D's 268.

| Metric | guidelines v0 (rung D) | guidelines v1 |
|---|---|---|
| judge annotations | 268 | 157 |
| matched pairs | 75 | 51 |
| unmatched judge annotations | 193 | 101 |
| localization precision | 0.280 | 0.336 |
| localization recall | 0.315 | 0.225 |
| localization F1 | 0.296 | 0.269 |
| function-decidable pairs | 75 | 51 |
| function accuracy | 0.080 | 0.157 |
| function majority class | 0.712 | 0.451 |
| function kappa | *unrecorded* | −0.013 |
| code accuracy / decidable | *unrecorded* | 0.062 / 32 |
| severity accuracy | *unrecorded* | 0.431 |

The localization change is a precision-for-recall trade, which is what an
evidence requirement should produce: precision rises 0.280 → 0.336 while recall
falls 0.315 → 0.225, and spurious annotations fall from 193 to 101. F1 moves
0.296 → 0.269, so the classification gain cost little localization.

Confusion, expert function to judge function, 51 pairs: action → planning 18,
memory → planning 16, memory → action 6, planning → planning 4, action → action
4, system → planning 1, memory → reflection 1, planning → action 1.

Code usage: PLN-1 61, ACT-3 36, PLN-3 30, PLN-5 14, ACT-5 7, RFL-1 4, RFL-3 2,
RFL-2 1, PLN-4 1, ACT-1 1. Fourteen codes unused, including all three memory
codes and all five system codes. Escape hatch not used.

Re-scored under mapping v2, no new inference: function accuracy 0.250 over 32
decidable pairs.

### Gaps

- Kappa, code accuracy and severity accuracy were not captured for rung D, so
  those three rows compare against nothing. Recoverable without inference by
  re-running `afb agreement` against rung D's stored labels.

---

## Category breakdown and guidelines v2 (2026-08-18)

`afb agreement --by-category` reports the TRAIL category behind each matched
pair, which `--confusion` cannot: confusion shows the function the *mapping*
assigned, and that assignment was itself in question.

### Observation — guidelines-v1 run, 51 matched pairs

| TRAIL category | expert function | pairs | agreeing | judge's labels |
|---|---|---|---|---|
| Formatting Errors | action | 22 | 4 | planning 18, action 4 |
| Instruction Non-compliance | memory | 19 | 0 | planning 14, action 4, reflection 1 |
| Context Handling Failures | memory | 4 | 0 | action 2, planning 2 |
| Resource Abuse | planning | 3 | 2 | planning 2, action 1 |
| Incorrect Problem Identification | planning | 2 | 2 | planning 2 |
| Resource Exhaustion | system | 1 | 0 | planning 1 |

### The memory question is answered, and it is mostly not about memory

Of the 23 pairs the mapping calls memory, **19 are Instruction Non-compliance**
and only 4 are Context Handling Failures. Removing those 19 gives exactly the 32
function-decidable pairs that mapping v2 reports, confirming D8's arithmetic
directly rather than by inference.

So the standing gap "memory is never used" is, on this split, 83% the contested
mapping and 4 pairs of genuine disagreement. It is not grounds for another
revision of the memory rules: tuning the prompt against those 19 pairs would be
tuning against a mapping decision, not against judge behaviour. The memory
triggers added in guidelines v1 are left in place and not extended.

### The largest genuine disagreement is Formatting Errors

22 of 51 pairs, 4 agreeing, and the judge answers planning 18 times. This is not
a mapping artifact: Formatting Errors maps cleanly to ACT-5, whose definition
already covers "a produced artifact is malformed relative to its format
requirements". The judge sees a bad result and reasons backwards to a bad plan.

Guidelines v2 (`cf52da01…9ab7d30`) therefore adds one rule and sharpens two:

- Step 4 of the function test now states that a wrongly formed output is an
  action error **even when the work behind it was also wrong**, and that the
  artifact is judged against its format requirement before asking whether the
  agent answered the right question.
- A PLN-1 versus ACT-5 tie-breaker: wrong *shape* is ACT-5, wrong *question* is
  PLN-1, and a bad result is not by itself evidence of a bad plan.
- The ACT-1/3/5 tie-breaker now says the artifact includes the task's final
  answer, not only files the agent wrote.

The longest swe_bench prompt is now ~27 878 tokens, leaving 8 192 output tokens
inside the 40 960 ceiling.

### Methodological risk: three revisions against one split

Guidelines v1 and v2 were both written after inspecting swe_bench results, which
is iterative fitting to the evaluation set. Two things limit the damage, and
both must be stated in the report rather than relied on silently:

1. Every rule added so far enforces a distinction the taxonomy **already**
   defines — ACT-5's definition already says "malformed relative to its format
   requirements". The revisions make v0's own boundaries operational; they do
   not introduce categories fitted to TRAIL.
2. **`gaia` has not been used for any revision.** All 117 gaia traces were last
   judged on 2026-07-30 under guidelines v0, and no gaia result has informed a
   rule. It is therefore a held-out split, and the final guidelines must be
   validated on it before any agreement figure is reported as the project's
   answer to RQ2.

---

## Harbor format verification (2026-08-18)

The first real `harbor run` executed for this project, to settle the open
question of what Terminal-Bench output actually looks like. Harbor 0.18.0,
Docker environment, `oracle` agent, task `terminal-bench/circuit-fibsqrt` from
the local task cache, one trial, reward 1.0, 1m34s. The oracle runs the task's
reference solution, so this cost no inference.

### Observation

Harbor writes one directory per trial, and what the pipeline needs is split
across two files:

```
<jobs-dir>/<job>/<trial>/result.json            verdict, task name, agent identity
<jobs-dir>/<job>/<trial>/agent/trajectory.json  what the agent did (ATIF)
<jobs-dir>/<job>/<trial>/verifier/              reward.txt, ctrf.json, test-stdout.txt
```

The trajectory file is **ATIF** (Agent Trajectory Interchange Format), Harbor's
documented interchange schema, defined as Pydantic models in
`harbor.models.trajectories`. A trajectory holds `steps`; each step has a
`source` of `system`, `user` or `agent`, a `message`, optional
`reasoning_content` and `tool_calls`, and an `observation` holding the results
of those calls. The task instruction is not repeated in `result.json`: it is the
first step, with `source: user`.

The `oracle` agent writes **no** trajectory file, so this run produced a valid
result record and nothing to annotate.

### The previous parser was wrong and returned nothing

`afb/harbor.py` was written against a guessed format, recorded as such in
`CLAUDE.md`. Every field was wrong:

| What the pipeline needs | The guess | Harbor actually writes |
|---|---|---|
| events | `messages` / `steps` / `turns` in the same record | `steps`, in a **different file** from the verdict |
| outcome | flat `resolved` / `passed` / `reward` | `verifier_result.rewards.reward` |
| task id | `task_id` as a string | `task_name`; `task_id` exists but is an object |
| agent | flat `agent` | `agent_info.name` |
| instruction | flat `instruction` | the first `source: user` step |
| command / output | flat `command` and `output` keys | `tool_calls[]` and `observation.results[]` |

Because `load_file` skipped any record without an events key, a real trial
produced **zero** trajectories rather than a visible error. The synthetic
`results/smoke-runs/` fixtures were written in the guessed shape, so they had
been exercising a format Harbor never emits.

### Consequence

`afb/harbor.py` is rewritten against ATIF, and `tests/fixtures/harbor-trial/`
pins the format: its `agent/trajectory.json` was generated by Harbor's own
Pydantic models, so the fixture is schema-authoritative rather than another
assumption, and its `result.json` is a real `harbor run` output. Twelve of the
codes' behaviours are covered, including the verdict cases, an unknown ATIF
version (warn, do not drop), and a trial with no trajectory (skip, do not fail).

Two decisions inside the parser are worth recording because they affect later
analysis. A trial carrying `exception_info` is `UNKNOWN`, not `FAILURE`, since a
crashed trial is not the agent failing the task and must not be counted as one
in the RQ3 variance analysis. And an omitted image is rendered as a visible
`[image omitted: …]` marker, on the same principle as the character-elision
marker in `afb/prompt.py`: the judge must never infer an agent's omission from
content this pipeline removed.

### Still open

No agent run with a real model has gone through Harbor. The verification above
used `oracle` precisely because it needs no inference, which is also why it
produced no trajectory. The ATIF parsing is therefore verified against Harbor's
schema but not yet against a trajectory Harbor produced from a live agent.

---

## Run 2026-08-19 — guidelines v2, Qwen3-32B-AWQ, swe_bench

The test of the v2 revision. The guidelines-v1 run's configuration exactly, with
only the guidelines digest changed, so the pair is controlled.

| Field | Value |
|---|---|
| Judge model | `Qwen/Qwen3-32B-AWQ` |
| Serving stack | vLLM 0.27.1, torch 2.13.0+cu130, one A100-PCIE-40GB |
| Sampling | temperature 0, max_tokens 8192, thinking off |
| Context | `--max-model-len 40960`, prompt char budget 100 000 |
| Guidelines | `cf52da01…9ab7d30` (v1 run used `a095d868…dc55c`) |
| Taxonomy / mapping | v0 / v0 |
| Data | TRAIL `swe_bench`, all 31 traces |
| Output | `results/judged-trail-swe_bench-qwen3-32b-awq-guidelines-v2.jsonl` |
| LSF job | 29150843 |

### Observation

31 of 31 traces judged. 152 annotations, against v1's 157.

| Metric | v0 (rung D) | v1 | v2 |
|---|---|---|---|
| judge annotations | 268 | 157 | 152 |
| matched pairs | 75 | 51 | 46 |
| unmatched judge annotations | 193 | 101 | 106 |
| localization precision | 0.280 | 0.336 | 0.303 |
| localization recall | 0.315 | 0.225 | 0.193 |
| localization F1 | 0.296 | 0.269 | 0.236 |
| function-decidable pairs | 75 | 51 | 46 |
| function accuracy | 0.080 | 0.157 | 0.087 |
| function majority class | 0.712 | 0.451 | 0.587 |
| function kappa | *unrecorded* | −0.013 | −0.064 |
| code accuracy / decidable | *unrecorded* | 0.062 / 32 | 0.000 / 25 |
| severity accuracy | *unrecorded* | 0.431 | 0.391 |

Re-scored under mapping v2, no new inference: function accuracy 0.160 over 25
decidable pairs, kappa −0.134. The v1 run scored 0.250 over 32 pairs there.

Confusion, expert function to judge function, 46 pairs: memory → planning 15,
action → planning 13, memory → action 11, action → action 3, system → planning
1, memory → reflection 1, planning → action 1, planning → planning 1.

**The block v2 targeted did not move.** Formatting Errors, the category the
revision was written for:

| | pairs | judge says action | rate |
|---|---|---|---|
| v1 | 22 | 4 | 0.182 |
| v2 | 16 | 3 | 0.188 |

Per-category, v2, 46 pairs: Instruction Non-compliance n=21 agree 0/21 (planning
13, action 7, reflection 1); Formatting Errors n=16 agree 3/16 (planning 13,
action 3); Context Handling Failures n=5 agree 0/5 (action 4, planning 1);
Resource Abuse n=2 agree 1/2; Resource Exhaustion n=1 agree 0/1; Language-only
n=1 agree 0/1.

### The revision sequence is inside its own noise

Agreeing pairs across the three guideline versions, same model, same split, same
mapping v0: **4/50 (v0), 8/51 (v1), 4/46 (v2)**. Under mapping v2: 8/32 (v1),
4/25 (v2).

No pair of these differs significantly on counts this small. The apparent v1 gain
recorded in D8 is not distinguishable from a lucky draw, and v2 — a further,
narrower change in the same direction, aimed at a block that a fifth of the
pairs sit in — moved that block by 0.6 percentage points.

### Gaps

- Rung D's kappa, code accuracy and severity accuracy are still uncaptured, so
  three rows of the table above compare against nothing. Recoverable without
  inference.
- The v1 and v2 denominators differ (51 against 46 pairs), so the two
  per-category tables are not composed identically. The Formatting Errors rate
  is a within-category comparison and is unaffected.

---

## Runs 2026-08-19/20 — generation probe, Qwen3.8-27B, swe_bench, all three guideline versions

D7 discharged D6's frontier requirement with a capacity ladder of Qwen3 models
and concluded that capacity was not the cause of the classification failure.
`Qwen/Qwen3.8-27B` is the closest available substitute for the frontier judge D6
actually asked for: a newer generation, hybrid linear/full attention, 262 144
native context. It is **not** a rung on that ladder — at 27B it has *fewer*
parameters than Qwen3-32B-AWQ, so it varies generation, not capacity, and it is
recorded separately for that reason.

Having run it once under v2, the other two guideline versions were replayed under
the same judge, which is the comparison the 32B sequence could not supply: three
prompts, one model, everything else fixed.

| Field | Value |
|---|---|
| Judge model | `Qwen/Qwen3.8-27B`, BF16, no quantization |
| Serving stack | vLLM 0.27.1, torch 2.13.0+cu130, two A100-PCIE-40GB, TP=2 |
| Sampling | temperature 0, max_tokens 8192, thinking off |
| Context | `--max-model-len 40960`, prompt char budget 100 000 |
| Taxonomy / mapping | v0 / v0, re-scored under mapping v2 |
| Data | TRAIL `swe_bench`, all 31 traces |
| LSF jobs | 29150863 (v2), 29154273 (v0), 29154274 (v1) |

Guideline versions are replayed from git refs, each verified to reproduce its
recorded digest: `257b897` → `bc2c95ec…` (v0), `b868c33` → `a095d868…` (v1),
`1100de7` → `cf52da01…` (v2).

### Observation

31 of 31 traces judged in all three runs.

| Metric | v0 | v1 | v2 |
|---|---|---|---|
| judge annotations | 78 | 78 | 82 |
| matched pairs | 41 | 40 | 42 |
| localization precision | 0.526 | 0.513 | 0.512 |
| localization recall | 0.172 | 0.168 | 0.176 |
| localization F1 | 0.259 | 0.253 | 0.263 |
| function accuracy (mapping v0) | **0.244** | 0.175 | 0.167 |
| function kappa (mapping v0) | **0.111** | 0.045 | 0.050 |
| function accuracy (mapping v2) | **0.310** | 0.250 | 0.240 |
| function kappa (mapping v2) | **0.158** | 0.077 | 0.095 |
| code accuracy / decidable | 0.034 / 29 | 0.042 / 24 | 0.040 / 25 |
| severity accuracy | **0.537** | 0.450 | 0.429 |

Agreeing pairs behind those rates: 10, 7, 7 under mapping v0; 9, 6, 6 under
mapping v2.

**The unrevised guidelines score highest on every classification measure.** The
ordering is the same under both mappings and repeats on the severity axis, which
is scored independently of the function mapping.

Formatting Errors, the category guidelines v2 was written to fix:

| guidelines | pairs | judge says action | rate |
|---|---|---|---|
| v0 | 18 | 8 | 0.444 |
| v1 | 15 | 4 | 0.267 |
| v2 | 16 | 4 | 0.250 |

Confusion under v0, 41 pairs: action → action 8, memory → reflection 8, action →
planning 7, memory → planning 5, memory → system 4, memory → action 4, action →
reflection 3, memory → memory 1, planning → planning 1.

Per-category under v0: Formatting Errors n=18 agree 8/18; Instruction
Non-compliance n=12 agree 1/12; Context Handling Failures n=10 agree 0/10
(reflection 8, system 2); Resource Abuse n=1 agree 1/1.

### Against the Qwen3-32B-AWQ runs

Same guidelines v2, same split, same sampling; BF16 against AWQ 4-bit.

| Metric | Qwen3-32B-AWQ | Qwen3.8-27B |
|---|---|---|
| judge annotations | 152 | 82 |
| localization precision | 0.303 | 0.512 |
| function accuracy (mapping v0) | 0.087 | 0.167 |
| function kappa (mapping v0) | −0.064 | +0.050 |
| function kappa (mapping v2) | −0.134 | +0.095 |

Every Qwen3-32B run to date returned a negative kappa (−0.013, −0.064, −0.134).
All three Qwen3.8 runs are positive (0.111, 0.045, 0.050). Memory, unused in
every previous run in the project, is used once in each.

Localization precision is 0.512–0.526 across all three guideline versions, a
spread of 0.014, against 0.280–0.336 across the 32B's three. Localization tracks
the model and is nearly insensitive to the prompt.

### Gaps

- BF16 against AWQ 4-bit is confounded with the generation change. The
  Quark-quantized 4-bit build that would have separated them fails to load under
  vLLM 0.27.1 (`AttributeError` in the Quark weight loader), so this is not
  currently separable on this stack.
- 10 correct against 7 and 7, on ~41 pairs, is not significant in isolation. The
  claim rests on the direction repeating across two mappings, the severity axis
  and the targeted category, not on the size of any single difference.
- `function_beats_chance` is a bare `>` comparison, not a significance test. 9 of
  29 against an expected 5.8 is roughly 1.4 standard deviations and may not be
  reported as the judge beating chance.

---

## Decisions

### D1 — match tolerance fixed at 0 events (2026-07-30)

**Evidence:** the sensitivity check above.

**Reasoning:** loosening the window buys matches whose labels disagree, so the
apparent F1 gain is produced entirely by pairing unrelated annotations. There is
no recoverable "right error, wrong index" effect. Reporting the tolerance-2 F1
of 0.40 would overstate agreement.

**Consequence:** all agreement figures are reported at tolerance 0, with this
table published as a sensitivity analysis.

### D2 — kappa demoted to a secondary statistic (2026-07-30)

**Evidence:** runs A and B, function kappa −0.077 and −0.084.

**Reasoning:** Cohen's kappa assumes both raters draw labels from comparable
distributions. The judge never emits MEM-3 and, on swe_bench, no memory code at
all, so the marginal correction dominates the statistic. A reader would take
"negative kappa" to mean systematic inversion, which is not what the confusion
matrix shows.

**Consequence:** per-function recall and the confusion matrix are the primary
evidence. Kappa is reported with this caveat attached.

### D3 — TRAIL is not evidence for taxonomy revision (2026-07-30)

**Evidence:** runs A and B, 19 of 24 codes unused on swe_bench and 8 of 24 on
gaia; `coverage` proposes them for removal.

**Reasoning:** TRAIL traces are GAIA and SWE-Bench agent traces, not terminal
runs. ACT-6 (destructive action), SYS-1 (budget exhaustion) and SYS-2 (timeout)
describe failure modes this data largely cannot exercise, and RFL-3, ACT-1 and
ACT-6 were added specifically for terminal tasks. Removing them on this evidence
would delete the terminal-specific contribution of the taxonomy using data that
cannot test it.

**Consequence:** TRAIL validates the judge (RQ2). Taxonomy revision evidence
(RQ1) must come from Terminal-Bench runs. The removal-candidates output is
ignored until then.

### D4 — the 0% escape-hatch rate is not evidence of taxonomy completeness (2026-07-30)

**Evidence:** 0 of 270 annotations used `NEW-?`, while RFL-3 alone accounts for
47 of 193 gaia annotations (24%).

**Reasoning:** "the agent failed to verify" can be asserted of almost any failing
trajectory. With a catch-all category available the judge never needs the escape
hatch, so a 0% rate is equally consistent with the taxonomy being complete and
with one category being too permissive.

**Consequence:** escape-hatch rate is not cited as coverage validation until
RFL-3's decision rule is tightened.

### D5 — MEM-3 mapping identified as the dominant source of disagreement (2026-07-30)

**Evidence:** expert-memory errors scored 0 correct out of 38 matched pairs
across both runs (0/15 swe_bench, 0/23 gaia). MEM-3 was used 0 times in 270
annotations, while MEM-1 and MEM-2 were used on gaia. `trail-mapping-v0.yaml`
routes TRAIL's most common swe_bench category, Instruction Non-compliance
(88 of 256 errors), to MEM-3.

**Reasoning:** the judge is not refusing the memory *function*, it is
specifically never reaching for MEM-3 "Instruction drift". `research/trail-mapping.md`
recorded this category as contested (MEM-3 versus PLN-2, which sit under
different cognitive functions) **before** these runs, so revisiting it is not
post-hoc fitting.

**Consequence:** the alternative mapping is to be tested and **both mappings
reported as a sensitivity analysis**, in the manner of D1. Selecting whichever
mapping maximises agreement, and reporting only that, would be circular.

### D6 — D5 is superseded: the mapping is not the dominant cause (2026-07-31)

**Evidence:** the mapping sensitivity check above, and the per-category
breakdown of all 91 matched pairs.

**Reasoning:** D5 predicted that the MEM-3 mapping drove the disagreement.
Testing it refuted that. Every reading of Instruction Non-compliance leaves
function accuracy between 0.125 and 0.214 and kappa negative, and the category
covers only 4 of gaia's 67 matched pairs, so it cannot account for gaia's 23
incorrect memory pairs. Those come instead from Language-only and Context
Handling Failures, which the judge labels RFL-3 or ACT-5.

The real pattern is that the judge's labels are **diffuse rather than
systematically shifted**. It concentrates on a few attractor categories — RFL-3
in 23 of 91 pairs across eight distinct TRAIL categories, ACT-5 in 15 across six
— instead of discriminating between them. No mapping change can repair that,
because the mapping only renames the expert side.

**Consequence:** D5's sensitivity analysis stands and is reported, but its
hypothesis is withdrawn. Two candidate causes remain and are not yet separable:
the decision rules in `research/annotation-guidelines.md` are not discriminative
enough, or Qwen3-14B-AWQ lacks the capacity to apply them. Running one split
against a frontier model separates these, and must happen before any taxonomy
or guideline revision, since revising rules against a judge that cannot follow
them would encode the model's limits into the taxonomy.

**Kept from D5:** v0 remains the mapping of record. v2 scores highest but was
adopted for the reason `research/trail-mapping.md` gave before any run — the
category is undecidable on the function axis — not because it scores best.

### D7 — D6's gate is discharged: capacity is not the cause of the classification failure (2026-08-17)

> **Superseded by D9 (2026-08-20).** Qwen3.8-27B, with fewer parameters than this
> ladder's top rung, returns 0.244 against the 32B's 0.087 on identical
> guidelines. The ladder varied parameter count within one generation, which is
> not the axis the judge is limited by.

**Evidence:** the capacity ladder above, rungs D and E in particular.

**Reasoning:** D6 left two candidate causes and forbade revising anything until
they were separated — the guidelines are not discriminative enough, or
Qwen3-14B-AWQ lacks the capacity to apply them. D6 asked for a frontier model;
none is available, so capacity was varied within the self-hosted range instead.

Doubling the judge from 14B to 32B, with every other variable fixed, separates
the two axes rather than lifting both:

- **Localization is capacity-limited.** Matched pairs 40 → 75, F1 0.175 → 0.296,
  with precision roughly held. The larger judge genuinely finds more of the
  errors the experts found.
- **Classification is not.** Function accuracy 0.075 → 0.080, both below the
  0.200 uniform baseline and far below the 0.588–0.712 majority-class rate.

The second candidate is therefore refuted for the classification axis: more
capacity buys localization and buys nothing on either label axis.

Two further observations point at the rules rather than the model. The judge
collapses onto a single answer — planning in 63 of 75 matched pairs, where
answering "action" throughout would have scored 0.493 — and **the identity of
the sink category changes with the model** (RFL-3 in run A, PLN-5/PLN-3 in rung
C, PLN-1 in rung D). A taxonomy whose definitions constrained the choice would
produce a similar distribution regardless of which model applied it.

**Consequence:** guideline revision is unblocked and has been carried out
(above). The revised guidelines must now be tested by re-running rung D's exact
configuration, since the whole ladder was labelled under the old digest. Until
that run exists, no claim about the revision's effect is supported.

**Limitation, to be stated in the report:** the ladder spans 14B to 32B. A
plateau across that range does not exclude a frontier judge behaving
differently, and TRAIL reports only 5.0% joint accuracy for Gemini 2.5 Pro on
this split, so the attainable ceiling is low in absolute terms. The claim
supported here is that capacity does not explain the classification failure
*within the range this project can serve*.

### D8 — the guidelines revision helped; the mapping was manufacturing part of the disagreement (2026-08-18)

**Evidence:** the guidelines-v1 run above, and its re-scoring under mapping v2.

**Reasoning, part one — the revision worked, partially.** Against rung D, the
same judge under the revised guidelines moves function accuracy 0.080 → 0.157,
cuts annotation volume 268 → 157, drops PLN-1 from 143 to 61, and moves 22
annotations into ACT-3, which is where the new PLN-1-versus-ACT-3 tie-breaker
sends a correct plan carried out with wrong arguments. The evidence requirements
and the tie-breakers did what they were written to do.

The cost is a precision-for-recall trade on localization, not a regression:
precision 0.280 → 0.336, recall 0.315 → 0.225, F1 0.296 → 0.269, with spurious
annotations falling 193 → 101. Since D7 established localization as the axis
that already works and classification as the one that does not, buying 0.077 of
function accuracy for 0.027 of F1 is the trade worth making.

The memory triggers did **not** work. Memory is still used zero times in 157
annotations, while the experts label 23 of 51 matched pairs memory.

**Reasoning, part two — much of the remaining gap is the mapping, not the judge.**
Re-scoring the same labels under mapping v2 gives:

| mapping | correct | function-decidable | accuracy |
|---|---|---|---|
| v0 | 8 | 51 | 0.157 |
| v2 | 8 | 32 | 0.250 |

The numerator is unchanged. The denominator falls by 19, and all 19 dropped
pairs were ones the judge got wrong under v0. They are Instruction
Non-compliance, which `research/trail-mapping.md` identified before any run as
the largest ambiguity, ambiguous specifically at the cognitive-function level,
because taxonomy v0 splits it into MEM-3 and PLN-2, which sit under different
functions, and TRAIL records no distinction that recovers which. A share of what
every run so far has reported as judge disagreement is therefore the mapping
asserting a function that the expert label does not determine.

**Consequence:** RQ2's function-axis figure is reported as the pre-registered
instruction in `research/trail-mapping.md` requires — the decidable subset and
the contested category separately, never pooled into one number. v0 remains the
mapping of record for continuity with runs A and B, and v2 continues to be
reported alongside it, as D1 does for match tolerance.

This is deliberately **not** "adopt v2 because it scores best". The reason for
treating the category as function-undecidable was written down before any
judging happened, and D6 already declined to adopt v2 on score grounds. The
0.250 figure is a consequence of that prior decision, not a reason for it.

**What this does not support.** 8 of 32 against an expected 6.4 at a 0.200
chance rate is roughly 0.7 standard deviations: the first figure this project
has produced above chance, and not distinguishable from chance at this n. It may
not be described as the judge beating chance. The honest statement is that the
revision moved the function axis from clearly below chance to indistinguishable
from it, on 32 decidable pairs.

**Still open:** memory remains unused, and it is now the largest single block of
disagreement under either mapping. Whether that is the judge, the guidelines, or
a further mapping artefact is not yet separated.

> **Superseded by D9 (2026-08-20): both revisions are harmful under a judge that
> does not share the 32B's error pattern.** The note below stands as written.
>
> **Part one is under review as of 2026-08-19.** The guidelines-v2 run returns
> function accuracy 0.087 (mapping v0) and 0.160 (mapping v2), below v1 on both,
> making the three-version sequence 4/50, 8/51, 4/46. On those counts the v1 gain
> claimed above is not distinguishable from sampling noise. Part two, the
> denominator argument, is arithmetic on a fixed numerator and is unaffected.
> The decision is left standing pending the Qwen3.8-27B probe rather than
> rewritten, per the constitution's rule that decisions are superseded by dated
> entries and never edited away.

---

### D9 — D7 and D8 are superseded: the ladder varied the wrong thing, and the guideline revisions were fitted to one judge (2026-08-20)

**Evidence:** the three Qwen3.8-27B runs above, and the guidelines-v2 run on
Qwen3-32B-AWQ.

**Part one — D7 is wrong about capacity.** D7 concluded that capacity was not the
cause of the classification failure, because function accuracy stayed flat
(0.075 → 0.080) from Qwen3-14B-AWQ to Qwen3-32B-AWQ while localization rose. A
27B model — *fewer* parameters than the 32B — returns 0.244 against the 32B's
0.087 on identical guidelines, lifts localization precision 0.303 → 0.512, and
turns kappa positive for the first time in the project.

The ladder's inference was sound given what it varied. What it varied was
parameter count inside one model generation, and that is not the axis the judge
is limited by. D7's own stated limitation — that a plateau across 14B–32B cannot
exclude a jump from a stronger model — is what actually happened, and it happened
at a *smaller* parameter count than the top rung. Capacity is not refuted as a
factor; it was never tested.

**Part two — D8 is wrong about the revision.** D8 recorded that guidelines v1
helped, on 0.080 → 0.157 in the 32B. Under one judge holding everything else
fixed, the ordering is now:

| guidelines | function acc (map v0) | function acc (map v2) | severity acc | Formatting Errors |
|---|---|---|---|---|
| v0 (unrevised) | 0.244 | 0.310 | 0.537 | 8/18 |
| v1 | 0.175 | 0.250 | 0.450 | 4/15 |
| v2 | 0.167 | 0.240 | 0.429 | 4/16 |

Both revisions are harmful to this judge, monotonically, and the worst damage is
in Formatting Errors — the exact category v2's tie-breaker was written to fix,
which drops from 0.444 to 0.250.

**The mechanism, and the methodological consequence.** Both revisions were
written by reading the 32B's confusion matrix and category breakdown. They encode
corrections for that model's specific error pattern — PLN-1 overuse, planning as
a residual bucket — and a judge without that pattern is pushed off correct labels
by rules aimed at a fault it does not have. The ordered function test in v1 is
the clearest case: it exists to stop planning being reached by default, and on a
model that was not defaulting to planning it diverts Formatting Errors into
reflection instead.

This is the failure D6 warned about, arriving from an unexpected direction. D6
gated revision behind a stronger judge so that the taxonomy would not encode a
weak model's limits. The gate was discharged by proxy in D7 and revision
proceeded — against the weak model's limits, which is what D6 was protecting
against.

**Consequence for the guidelines.** v0 is restored as the version of record for
reporting. v1 and v2 are retained in git and remain readable by
`GUIDELINES_REF`, and their digests stay in this log, but no figure in the report
is drawn from them. This is not "adopt whichever scores best": the reason is that
v1 and v2 were derived from a single judge's errors on a single split and have
now been shown not to transfer, which disqualifies them as general decision rules
regardless of score.

**Consequence for method.** A prompt revision derived from judge A's failures is
not evidence about the guidelines; it is evidence about judge A. Any future
revision must be validated on a judge other than the one whose errors motivated
it, and on a split other than the one it was read from. This is now a standing
requirement, not a suggestion.

**What this does not support.** The best figure the project has is 9 of 29 under
mapping v2, against 5.8 expected at a 0.200 chance rate — roughly 1.4 standard
deviations, on 31 traces. It may not be described as the judge beating chance,
and 10-against-7 across guideline versions is not significant in isolation. The
defensible statements are that the function axis has moved from clearly below
chance to indistinguishable from it, that kappa has changed sign, and that the
ordering across guideline versions repeats on four independent measures.

**Still open:** memory remains the dominant block of disagreement — 22 of 41
pairs under v0, of which 1 agrees. Context Handling Failures is now the sharpest
case: 10 pairs, expert says memory, the judge says reflection 8 times. That every
judge and every guideline version disagrees the same way is the signature of a
mapping problem rather than a judge problem, and it is not yet separated. Nothing
here has been checked on `gaia`.

---

### D10 — the TRAIL mapping is closed (2026-08-20)

**Evidence:** the pre-registration in `research/trail-mapping.md`, the sensitivity
comparison of v0/v1/v2 recorded above, and the contested categories identified in
D8 and D9.

**Decision.** `src/afb/data/trail-mapping-v{0,1,2}.yaml` are final. v0 remains the
mapping of record and v2 continues to be reported beside it as a sensitivity
variant, as D1 does for match tolerance and D8 requires for the function axis. No
further mapping version will be created for this project.

**Reasoning.** The mapping's methodological value is that it was written before
any judging happened, so the correspondences it asserts were not chosen to
produce a score. That is a one-time asset and it is spent by the first edit made
after seeing results. Every figure in this log is now known: which categories
carry the disagreement, and which direction a remap would move the numbers. An
edit from here could not be distinguished from tuning the target to the judge,
whatever the intent behind it, and would have to be disclosed as such.

Closing the mapping is therefore the conservative choice, not the convenient one.
It costs accuracy on the reported figures — D8 showed that a share of the
recorded disagreement is the mapping asserting a function the expert label does
not determine — and the project accepts that cost rather than the alternative.

**Consequence for the contested categories.** Two categories are known to be
contested and are reported, not remapped:

| Category | Mapping | Observation |
|---|---|---|
| Instruction Non-compliance | MEM-3 in v0, PLN-2 in v1, function-undecidable in v2 | The ambiguity was recorded before any run. Excluded from function scoring under v2, per D8. |
| Context Handling Failures | MEM-1 in all three variants | 10 matched pairs under Qwen3.8/v0, 0 agree; the judge answers reflection 8 times. The same direction appears under Qwen3-32B and under all three guideline versions. |

Context Handling Failures is the sharper case precisely because no mapping
variant explores it: it is MEM-1 in v0, v1 and v2 alike, so the existing
sensitivity analysis cannot see it. Two judge generations and three prompts
disagree with it in the same direction. That is reported as an observation about
the correspondence between TRAIL's categories and a cognitive-function axis, and
it belongs in the report's discussion of what an expert-annotated tool-calling
benchmark can and cannot validate about a terminal taxonomy.

**What this does not decide.** Whether TRAIL's label or the judge's is correct for
those ten pairs is not settled here, and closing the mapping does not assert that
MEM-1 is right. It asserts that this project will not adjudicate it by editing
the target after the fact. Reading those traces remains worth doing for the
discussion; it is no longer a precondition for anything.

**Consequence for scoring.** Mapping is applied when labels are scored, not when
they are produced, so every stored `results/judged-trail-*.jsonl` can be
re-scored under any variant at no inference cost. Closing the mapping constrains
which variants exist, not what may be recomputed from labels already collected.

---

## Known gaps

- **vLLM version not captured** for runs A and B, which principle 4 requires
  ("serving stack version"). Both runs used the same venv at
  `$HOME/afb-work/.venv-hpc` on the DTU cluster, so it is recoverable via
  `pip show vllm` there until that venv changes. The job script should echo it.
- **Judge under-detection partly explained.** 1.65 annotations per trace on gaia
  against 4.36 scoreable expert errors, and 26% of gaia traces returned nothing.
  Truncation is **excluded** as the cause: the 2026-08-17 diagnostic shows the
  traces that returned nothing are no longer than the ones that did (gaia median
  prompt 60 052 against 59 983 characters; swe_bench 85 485 against 87 769).
  Remaining candidates are the guidelines' evidence threshold, the model's
  capacity, and the repair loop, which until now recorded a response cut off
  mid-JSON as a success. `Provenance.truncated` and `Provenance.attempts_used`
  make the third testable on the next run; they cannot be recovered for runs A
  and B.
- **Judge capacity separated from taxonomy quality — reopened by D9.** D7 closed
  this on a ladder that varied parameter count within one model generation.
  Qwen3.8-27B then beat the 32B on every classification measure with fewer
  parameters, so the axis that matters has not been isolated. What is now
  established is narrower: localization tracks the model and is nearly
  insensitive to the prompt (precision spread 0.014 across three guideline
  versions), while classification responds to both.
- **Memory is the dominant block of disagreement — closed as an action item by
  D10, retained as an observation.** Under Qwen3.8 with guidelines v0, 22 of 41
  matched pairs are expert=memory and 1 agrees; Context Handling Failures alone
  is 10 pairs, 0 agreeing, with the judge answering reflection 8 times. The
  mapping is closed, so this is reported rather than fixed. Reading those traces
  is still worth doing for the discussion.
- **Every guideline revision was fitted to one judge on one split — D9.** v1 and
  v2 were written from the 32B's errors on `swe_bench` and are harmful to a
  judge that does not share that error pattern. No revision may be validated on
  the judge whose errors motivated it, or on the split it was read from.
- **Nothing has been checked on `gaia` since 2026-07-30.** The held-out split has
  informed no rule, which is the only protection the project has against the
  fitting described above. The final configuration must be validated there before
  any RQ2 figure is reported.
- **No agent has run through Harbor with a real model.** The format is verified
  against Harbor's ATIF schema (2026-08-18) but not against a live agent's
  output, and D3 makes real terminal runs a precondition for RQ1's taxonomy
  revision evidence, as well as for RQ3 and RQ4.
- **The taxonomy and mappings were untracked until 2026-08-18.** `.gitignore`
  carried an unanchored `data/`, so `src/afb/data/` was excluded and no commit
  before `81cfde9` fully determined what any judge run read. Runs A through E
  and the guidelines-v1 run are pinned by their recorded configuration but not
  by a committed taxonomy file; the files were unchanged over that period, so
  the records stand, but the guarantee was absent.

---

## Superseded / exploratory

- **2026-07-29, LSF job 28980525** — first end-to-end judge run, swe_bench, 5
  traces. Exploratory. Superseded by run A, which includes these 5 traces.
- **2026-07-30, LSF jobs 28984359, 28984360, 28984412, 28984413** — four aborted
  submissions. Configuration passed as a shell prefix did not reach the compute
  node, so two jobs silently re-ran the 5-trace exploratory configuration, and
  two resolved the repository path incorrectly. No data produced. Fixed by
  passing configuration through `bsub -env` and moving all path defaults into
  `scripts/judge_trail.sh`; the script now aborts rather than running a
  configuration that was not requested.
