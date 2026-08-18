# Annotation Guidelines

How the annotator applies `taxonomy-v0.md` to a normalized trajectory. The annotator is the **LLM judge** (validated in RQ2) — there is no human annotation in this project. This document is used verbatim as the judge's instructions, so every rule must be explicit and mechanical — no unstated conventions.

## What you annotate

One **annotation** = one error occurrence:

| Field | Value |
|---|---|
| `trajectory_id` | The trajectory being annotated |
| `event_span` | `[start, end]` event indices where the error *manifests* (usually a single event) |
| `cognitive_function` | `memory` / `reflection` / `planning` / `action` / `system` |
| `error_type` | Taxonomy code (e.g., `RFL-1`) or `NEW-?` |
| `severity` | `low` / `medium` / `high` (see scale below) |
| `root_cause` | `true` for the earliest correctable error (see heuristic) |
| `cascade_of` | Annotation id of the root cause this error propagated from, if any |
| `rationale` | 1–3 sentences quoting the evidence in the trajectory |
| `confidence` | `certain` / `probable` / `speculative` |
| `proposed_category` | Free text, only with `NEW-?` |

A failed trajectory typically gets several annotations (TRAIL average: ~5.7). A *successful* trajectory can also carry annotations (errors the agent recovered from) — annotate those too; they matter for the stochastic-vs-systematic analysis (RQ3).

## Procedure

1. **Read the task first.** Read the instruction and, if available, the oracle/test criteria before reading any agent behavior, and note the explicit constraints.
2. **First pass — comprehension.** Read the whole trajectory without labeling. Note the agent's apparent plan and where the outcome diverged from the goal.
3. **Second pass — mark candidate errors.** Walk events in order; mark every event where something is objectively wrong per a taxonomy definition. Quote the evidence.
4. **Classify each candidate.** Choose the cognitive function with the ordered test below, then the error type within it. Apply the decision rules in the taxonomy; use the tie-breakers below if two labels still fit.
5. **Identify the root cause.** Apply the root-cause heuristic; set `root_cause: true` on exactly one annotation per independent failure chain (a trajectory can rarely have two independent chains). Link downstream consequences via `cascade_of`.
6. **Severity pass.** Assign severity per the scale.
7. **Completeness check.** If the task failed, at least one annotation must exist whose severity is `high` or whose chain explains the failure. If you cannot produce one, either the failure is SYS-3 (environment defect — needs evidence) or the taxonomy has a gap → use `NEW-?`.
8. **Re-check pass.** Before returning, re-read your own annotations. If every annotation carries the same cognitive function, or the same error type, take the strongest one and re-run the ordered function test on it from step 1. A trajectory whose errors are genuinely all one faculty is possible; one produced by settling on a label early is more likely. Change the label only if the test now gives a different answer — do not vary labels for the sake of variety.

## Choosing the cognitive function

Apply these tests **in order** and stop at the first one that holds. Do not skip
ahead: the tests are ordered so that the faculty which failed *first* is the one
you name, and a later test can always be made to sound plausible about an error
the earlier test already claimed.

1. **System** — did something outside the agent's control fail on its own terms:
   the harness stopped it, a tool crashed, a dependency was absent, the provider
   errored, a budget or wall-clock limit was reached? Requires evidence that this
   happened regardless of what the agent chose.
2. **Memory** — was the information the agent needed already present earlier in
   *this* trajectory, in the instruction or in an event it observed, and did the
   agent act as if it were not? See the memory triggers below.
3. **Reflection** — did the agent misread, misjudge, or fail to check the result
   of something it had just done? The evidence is an observation the agent
   reacted to incorrectly, or an available check it never ran.
4. **Action** — was the intention correct but the execution wrong: malformed
   syntax, wrong arguments, a badly formed artifact? Ask whether a competent
   operator with the *same* intention would have typed something different. If
   yes, this is action, not planning.
5. **Planning** — could this course of action not have achieved the goal *even if
   every step had been executed perfectly*? Planning requires that positive
   showing.

If none of the five holds, use `NEW-?`. **Planning is not the residual bucket.**
An error you cannot place under tests 1–4 is not thereby a planning error; say
so with the escape hatch instead.

## Evidence requirements for the broad codes

Three codes can be made to fit almost any failed trajectory. Each requires
specific evidence, and without it the code does not apply:

| Code | You must be able to quote |
|---|---|
| PLN-1 Task misunderstanding | (a) the specific requirement in the task instruction, **and** (b) the agent's own statement or action that contradicts it. "The task failed, so the agent misunderstood it" is circular and inadmissible. |
| PLN-5 Infeasible strategy | the property of *this* environment that makes the chosen approach impossible, not merely unsuccessful. |
| RFL-3 Verification omission | the concrete check that was available and skipped, named specifically ("never ran the test suite that the task ships"), not "did not verify its work". |

## Memory triggers

Label memory when any of these patterns is present. They are positive triggers:
look for them actively rather than reaching for memory only when nothing else fits.

- The instruction stated a requirement, the agent acknowledged or satisfied it
  earlier, and a later event contradicts it → **MEM-3**.
- Information appeared in an earlier event and the agent later re-derives it,
  re-explores it, or asks the environment for it again → **MEM-1**.
- The agent asserts a fact about what it observed that no event in the
  trajectory supports → **MEM-2**.

## Root-cause heuristic

> The root cause is the **earliest** annotated error such that, had it been corrected at that point (counterfactually, with everything before it unchanged), the task would plausibly have succeeded within the remaining budget.

- Work backwards from the failure, then forwards from the start; they should meet at the same event.
- Mechanical terminal events are usually symptoms: a failing command (ACT-x) whose intention was already doomed points back to the PLN/MEM/RFL error that formed the intention.
- SYS-1 (budget exhaustion) is almost never a root cause — ask what consumed the budget.
- If two candidate root causes are both plausible, prefer the earlier one and set `confidence: probable` on both.

## Tie-breakers for common confusions

| Confusion | Rule |
|---|---|
| MEM-1 vs RFL-1 | Was the information in an *earlier* event (memory) or in the output the agent is reacting to *right now* (reflection)? |
| MEM-2 vs RFL-5 | False claim about what was *observed* (MEM-2) vs. about a *check the agent performed* (RFL-5). |
| MEM-3 vs PLN-1/PLN-2 | Did the agent ever behave consistently with the requirement? Yes → MEM-3 (drift). No → PLN-1 if misread, PLN-2 if ignored. Both PLN codes still require their quoted evidence above. |
| PLN-1 vs ACT-3 | Was the goal itself wrong (PLN-1) or the goal right and the command wrong (ACT-3)? A correct plan carried out with wrong arguments is ACT-3. |
| PLN-1 vs PLN-3 | A single wrong reading of the task is PLN-1. Repeating an approach that has already failed is PLN-3, even when the original reading was also wrong — annotate both and link the repetition with `cascade_of`. |
| RFL-2 vs RFL-3 | Did the agent *judge* progress incorrectly (RFL-2) or simply never run an available check (RFL-3)? RFL-3 requires naming the concrete check that was skipped. |
| ACT-2 vs PLN-5 | Wrong instrument for a feasible step (ACT-2) vs. a step no instrument could perform in this environment (PLN-5). |
| ACT-1/3/5 among themselves | Shell-syntax malformed → ACT-1. Command runs but wrong args → ACT-3. Produced *artifact* malformed → ACT-5. |
| PLN-3 vs RFL-4 | The repetition itself is PLN-3; a wrong *diagnosis* driving varied-but-misdirected fixes is RFL-4. Both can co-occur (RFL-4 as root cause, PLN-3 as cascade). |
| Any agent error vs SYS-3 | Before labeling SYS-3, state what evidence shows a correct agent would also have failed (e.g., missing dependency with no offline alternative). |

## Severity scale (adapted from TRAIL)

- **high** — this error, alone, is sufficient to fail the task (or did).
- **medium** — materially reduced success probability or wasted a significant fraction (>~20%) of the budget, but was survivable.
- **low** — local mistake, quickly recovered, negligible effect on the outcome.

## Location conventions

- Annotate the error where it **manifests** — the first event containing direct evidence, not where its consequences appear.
- Omission errors (RFL-3) are located at the last event where performing the check was still natural — typically the event before task completion/submission.
- Spans longer than one event are for genuinely distributed errors (e.g., a PLN-3 loop spans all its iterations).

## Hygiene

- Annotate only from the trajectory and task materials. Do not consult the agent's model identity, other trajectories of the same task, or leaderboard context while labeling (bias).
- One judge pass per trajectory; judge validity comes solely from the TRAIL agreement study (RQ2).
- Rationales must quote or index concrete evidence — a rationale that can't cite an event is `confidence: speculative`.
