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

---

## Known gaps

- **vLLM version not captured** for runs A and B, which principle 4 requires
  ("serving stack version"). Both runs used the same venv at
  `$HOME/afb-work/.venv-hpc` on the DTU cluster, so it is recoverable via
  `pip show vllm` there until that venv changes. The job script should echo it.
- **Judge under-detection unexplained.** 1.65 annotations per trace on gaia
  against 4.36 scoreable expert errors, and 26% of gaia traces returned nothing.
  Not yet established whether this is the prompt, the model's capacity, or the
  guidelines' evidence threshold.
- **Judge capacity not separated from taxonomy quality.** Joint accuracy is
  roughly 0.6–0.8%, against the 5.0% TRAIL reports for Gemini 2.5 Pro on
  swe_bench. Qwen3-14B-AWQ is far smaller, so no conclusion about the taxonomy
  can be drawn until one split is run against a frontier model.

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
