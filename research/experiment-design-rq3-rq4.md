# Experiment design: subquestions 3 and 4

Written before any Terminal-Bench run, as principle 1 requires. `afb/runs.py`
already implements the analysis; what follows fixes the parameters it will be run
with, and says what would count as an answer, so that neither can be chosen after
seeing the numbers.

- **Subquestion 3.** Can variation across repeated runs distinguish systematic
  from stochastic agent failures?
- **Subquestion 4.** Do failure profiles differ across agents on the same tasks?
  Marked *if time permits* in the report, and treated here as conditional on 3
  completing.

## The precondition nothing else survives without

**The agent must sample.** At temperature 0 a repeated run reproduces the
previous one, every recurrence rate is 0 or 1, and subquestion 3 asks a question
its own data cannot answer. This is the opposite of the judge's requirement,
where temperature is pinned to 0 precisely so that a rerun reproduces.

So the two roles take opposite settings, and both are recorded:

| Role | Temperature | Why |
|---|---|---|
| Agent (Terminus 2 driving Qwen3.8-27B) | the checkpoint's own default, recorded per run | Variation is the object of study, and the default is the condition a benchmark result would be reported under |
| Judge (Qwen3.8-27B) | 0 | An annotation must be reproducible from its recorded configuration |

Using the checkpoint default rather than an invented value keeps the measured
variance the variance a user of this model would actually meet. The value is read
from `generation_config.json` and echoed by the job script, because a variance
figure means nothing without it.

## Design

**Repeats.** 10 per task. With the systematic threshold at 0.8 a code must
recur in at least 8 of 10 runs, so the rate has 11 distinguishable levels. At 5
repeats it has 6, and the threshold falls between 4/5 and 5/5, which makes the
systematic set hypersensitive to a single run.

**Tasks.** Set by budget, not chosen. The first real agent run measures wall
time per trial; the task count is then the largest *n* with `n × 10 × t` inside
the GPU allocation, tasks drawn in the dataset's own order rather than picked.
Drawing in a fixed order matters because picking tasks after seeing which ones
the agent fails would select for the effect being measured.

**What is counted.** `afb/runs.py` counts a code once per run however often it
was annotated, so a retry loop annotated five times is one finding. Trials that
raise are excluded rather than counted as failures, consistent with the decision
in `afb/harbor.py` that a trial carrying `exception_info` is `UNKNOWN`: a crashed
trial is the harness failing, not the agent, and counting it would inflate
apparent stochasticity.

**The threshold is a free parameter and is treated as one.** 0.8 is a
convention, not a finding. It is reported with a sensitivity check at 0.6 and
1.0, in the manner D1 established for match tolerance. If the systematic share
moves substantially across that range, the honest conclusion is that the split
is threshold-driven and the analysis does not support a clean division.

## What would count as an answer

Subquestion 3 asks whether repetition *distinguishes* the two, not what the
split is. It is answered affirmatively when both hold:

1. The systematic and stochastic sets are non-trivially populated, so the method
   separates rather than assigning everything to one side.
2. The split survives the threshold sensitivity check.

A result where nearly every code is systematic is still an answer, but a
different one: it would say the agent's failures on these tasks are properties of
the agent, and that repetition was not needed to see them. A result where nearly
every code is stochastic, with unstable outcomes, says single-run benchmark
numbers are not measuring what they appear to.

The outcome axis is reported alongside the code axis. `TaskVariance.outcome_is_stable`
records whether the pass or fail verdict itself varied across repeats, which is a
claim about Terminal-Bench as a measuring instrument and is independent of any
judge label.

## Subquestion 4, if reached

Hold the model fixed and vary the scaffolding, because varying the model answers
a question about models rather than agents. Terminus 2 against a second Harbor
agent that accepts an `api_base`, on the same tasks, at the same repeat count.
`afb/runs.py` already normalises profiles so agents with different run counts
compare.

The comparison is a distribution over cognitive functions, not a success rate.
Two agents with equal success rates failing for different reasons is the result
worth having, and is the one a success-rate benchmark cannot report.

## Threats to validity, recorded now rather than discovered later

**Agent and judge are the same model.** Qwen3.8-27B drives the agent and also
labels the trajectory. A model may be systematically blind to the class of
mistake it tends to make, which would bias the failure profile in a direction no
agreement study on TRAIL would reveal, since there the judge labels traces it did
not produce. This is stated as a limitation. Separating them needs a second model
that fits the hardware, and the capacity ladder found none that classifies
adequately.

**PRoot changes the environment.** The cluster has no container runtime, so
tasks run through udocker, which provides no PID namespace and drops
`--containall`, `--writable-tmpfs` and `--fakeroot`. A task sensitive to process
isolation may behave differently than it would under Docker, so any absolute
Terminal-Bench figure from this project is not directly comparable to a published
leaderboard number. Variance across repeats, which is what subquestion 3
measures, is affected far less, because every repeat meets the same environment.

**Judge accuracy bounds everything downstream.** RQ2 has so far produced a
function-axis accuracy indistinguishable from chance. A systematic-versus-
stochastic split computed from those labels inherits that error. The split is
therefore also computed on the *outcome* axis, which needs no judge at all, so
that at least one version of the subquestion-3 answer is independent of judge
quality.
