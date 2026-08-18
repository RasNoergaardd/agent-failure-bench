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
- **Judge capacity not separated from taxonomy quality.** Joint accuracy is
  roughly 0.6–0.8%, against the 5.0% TRAIL reports for Gemini 2.5 Pro on
  swe_bench, and the function axis is below uniform chance on both splits.
  Qwen3-14B-AWQ is far smaller, so no conclusion about the taxonomy can be drawn
  until judge capacity is varied. D6 called for a frontier model; no paid
  inference is available to this project, so the substitute is a capacity ladder
  of self-hosted open-weight judges over one split. That run is pending.

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
