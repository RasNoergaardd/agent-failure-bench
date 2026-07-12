# Failure Taxonomy v0 (draft — pre-validation)

**Status:** v0, not yet empirically validated. Judge-labeled runs on Terminal-Bench 2.0 (designed when RQ2–RQ3 work starts) will test this taxonomy; v1 will add/remove/merge categories with evidence cited in the revision log below. Per `constitution.md` §2, never edit categories in place — revise via a new version.

## Structure

A failure label has two classification axes plus qualifiers, answering research question 1's requirement that each failure be classified by **the failing cognitive function** and **its location in the trajectory**:

1. **Cognitive function** (Axis A): which faculty of the agent failed — `memory`, `reflection`, `planning`, `action`, `system`. Adapted from AgentErrorTaxonomy (arXiv:2509.25370); definitions rewritten for single-agent terminal work.
2. **Error type** (within a function): the fine-grained failure mode, merged from TRAIL (arXiv:2505.08638) and AgentErrorTaxonomy, with terminal-specific additions. Codes are `<FN>-<n>` (e.g., `RFL-2`).
3. **Location**: the event index (or span `[start, end]`) in the normalized trajectory where the error manifests.
4. **Qualifiers**: `severity` (low / medium / high impact on task outcome — TRAIL's scale), `root_cause` (bool — is this the earliest error that, if corrected, plausibly changes the outcome?), `cascade_of` (optional link to the root-cause annotation this error propagated from — AgentDebug's cascade insight).

Every error type below lists: definition, a terminal-task example, a decision rule for hard cases, and provenance (`TRAIL:…`, `AET:…`, or `NEW` = added for terminal tasks).

## MEM — Memory

*Retaining and recalling information available earlier in the session: the task instruction, previously observed file contents, command outputs, environment facts.*

### MEM-1 Context loss
- **Definition:** The agent fails to use information it demonstrably observed earlier (re-explores known state, contradicts an earlier observation, asks the environment for what it already saw).
- **Example:** `cat config.yaml` showed the port is 8081; ten steps later the agent hardcodes 8080.
- **Decision rule:** The information must have appeared verbatim in an earlier event. If it was never observed, consider MEM-2 (fabrication) or PLN-1 (misunderstanding).
- **Provenance:** AET: memory retrieval failure; TRAIL: context handling failures.

### MEM-2 Recall fabrication
- **Definition:** The agent "recalls" an observation that never occurred — a file, flag, output, or environment fact it treats as previously seen.
- **Example:** "As we saw, the tests are in `tests/unit/`" when no such listing ever happened (directory is `test/`).
- **Decision rule:** Distinguish from RFL-5 (fabricated *evaluation* of a real action) and from general world-knowledge errors in planning (PLN-5). MEM-2 requires a false claim about *session history*.
- **Provenance:** AET: memory/hallucination; TRAIL: hallucination (text-only), narrowed to session history.

### MEM-3 Instruction drift
- **Definition:** A requirement stated in the task instruction is silently dropped or simplified away as the trajectory progresses.
- **Example:** Task says "solution must not modify `main.py`"; after a failed attempt, the agent edits `main.py`.
- **Decision rule:** If the constraint was never acted on from the start, prefer PLN-2 (constraint ignored at planning time). MEM-3 requires early compliance followed by later violation.
- **Provenance:** AET: over-simplification; TRAIL: instruction non-compliance.

## RFL — Reflection

*Evaluating one's own actions and their outcomes: reading command output, judging progress, diagnosing errors.*

### RFL-1 Output misinterpretation
- **Definition:** The agent misreads the content of a command's actual output (exit codes, error messages, test results, file contents).
- **Example:** `pytest` prints `2 failed, 8 passed`; the agent responds "all tests pass."
- **Decision rule:** The output must contain the correct information legibly. If the output was truncated/garbled by the harness, consider SYS-4/SYS-3.
- **Provenance:** TRAIL: tool output misinterpretation; AET: outcome misinterpretation.

### RFL-2 Progress misjudgment
- **Definition:** The agent's assessment of overall task progress is wrong — declares completion, or continues down a failed path believing it works — without misreading any specific output (else RFL-1).
- **Example:** Agent finishes after making the code compile, though the task asked for a passing test suite it never ran.
- **Provenance:** AET: progress misjudge.

### RFL-3 Verification omission
- **Definition:** A cheap, available check that would have revealed an error is never run (task tests, re-reading an edited file, `--dry-run`).
- **Example:** Agent edits a script and submits without executing it once, though it is executable in the container.
- **Decision rule:** Only label when a concrete check existed and was feasible within remaining budget. This is an *omission* error: locate it at the last event before the missed check was needed (typically just before completion).
- **Provenance:** NEW (terminal). Motivated by terminal tasks having executable oracles the agent can run itself.

### RFL-4 Causal misattribution
- **Definition:** The agent notices a failure but blames the wrong cause, and its fix targets that wrong cause.
- **Example:** Import error is due to a missing `__init__.py`; the agent reinstalls the package three times.
- **Provenance:** AET: causal misattribution.

### RFL-5 Evaluation fabrication
- **Definition:** The agent asserts the result of a check it never performed ("I ran the tests and they pass" with no such event).
- **Decision rule:** vs. RFL-2: RFL-5 fabricates a specific verification event; RFL-2 is an unjustified but honest judgment.
- **Provenance:** AET: reflection/hallucination; TRAIL: hallucination (tool-related).

## PLN — Planning

*Choosing what to do: interpreting the task, forming a strategy, respecting constraints.*

### PLN-1 Task misunderstanding
- **Definition:** The agent solves a different problem than the one specified, from the outset or at a decision point.
- **Example:** Task: "make the failing test pass without changing the test"; agent rewrites the test.
- **Decision rule:** vs. MEM-3: misunderstanding is present at first contact with the requirement; drift is a later regression from earlier correct behavior.
- **Provenance:** TRAIL: incorrect problem identification.

### PLN-2 Constraint ignorance
- **Definition:** The plan violates an explicit task constraint (forbidden files, required language/tool, resource limits) from the start.
- **Provenance:** AET: constraint ignorance.

### PLN-3 Redundant looping
- **Definition:** The agent repeats (near-)identical actions without incorporating their results — retry loops, circular exploration, re-running a failing command unchanged expecting different results.
- **Example:** Runs the same failing `make` five times with no intervening change.
- **Decision rule:** ≥3 near-identical attempts with no state change. The *loop* is PLN-3; the reason it can't diagnose the failure may be a separate RFL-4.
- **Provenance:** AET: inefficient plan; TRAIL: resource abuse.

### PLN-4 Goal deviation
- **Definition:** The agent pursues subgoals irrelevant to the task (side explorations, unrequested refactors) at material cost to the budget.
- **Provenance:** TRAIL: goal deviation.

### PLN-5 Infeasible strategy
- **Definition:** The plan requires capabilities or resources the environment does not offer (unavailable network, missing tools it assumes exist, interactive programs it can't drive).
- **Example:** Plan hinges on `pip install` in an offline container; agent commits to it despite the first failure.
- **Decision rule:** The first *attempt* may be reasonable exploration; label PLN-5 when the agent commits to the infeasible path after evidence of infeasibility.
- **Provenance:** AET: impossible action (planning-level).

## ACT — Action

*Translating an intention into a concrete command or edit.*

### ACT-1 Command construction error
- **Definition:** Malformed shell syntax: quoting, escaping, pipes, heredocs, invalid flag syntax.
- **Example:** Unescaped `$` in a double-quoted sed script silently expands to nothing.
- **Provenance:** NEW (terminal); generalizes AET: format error to shell commands.

### ACT-2 Wrong command/tool selection
- **Definition:** A well-formed command that is the wrong instrument for the intended step.
- **Example:** Uses `grep` on a binary file where `strings`/`xxd` was needed; the intention (inspect the file) was right.
- **Provenance:** TRAIL: tool selection error.

### ACT-3 Parameter error
- **Definition:** Right command, wrong arguments: paths, flags, targets, ordering.
- **Example:** `cp src dst` reversed; `chmod 644` where `755` was needed.
- **Provenance:** AET: parameter error.

### ACT-4 Plan–action mismatch
- **Definition:** The executed action does not implement the agent's own stated intention.
- **Example:** Says "I'll only add a null check to `parse()`" but the edit also rewrites `validate()`.
- **Decision rule:** Requires an explicit stated intention in a nearby event to compare against.
- **Provenance:** AET: misalignment.

### ACT-5 Artifact format error
- **Definition:** A produced artifact (file, code, config, final answer) is malformed relative to its format requirements — syntax errors in written code, invalid YAML/JSON, wrong answer format.
- **Provenance:** TRAIL: formatting errors; AET: format error.

### ACT-6 Destructive action
- **Definition:** An action that irreversibly damages needed state: deleting/overwriting required files, killing needed processes, corrupting the environment such that the task becomes harder or impossible.
- **Example:** `git checkout .` wipes the agent's own uncommitted fix.
- **Provenance:** NEW (terminal). Terminal agents have unusually high destructive capability; neither source taxonomy isolates this.

## SYS — System

*Failures outside the agent's cognition: harness limits, environment defects, provider errors. These establish that not every failed trajectory implies an agent error.*

### SYS-1 Budget exhaustion
- **Definition:** The run ends by hitting the step/turn budget while the agent is still making plausible progress.
- **Decision rule:** If the budget was consumed by a PLN-3 loop, the root cause is PLN-3 and SYS-1 is its cascade.
- **Provenance:** AET: step limit.

### SYS-2 Timeout
- **Definition:** Wall-clock or per-command timeout terminates progress (long builds, hanging interactive prompts).
- **Provenance:** TRAIL: timeout issues.

### SYS-3 Environment defect
- **Definition:** The task environment itself is broken or underspecified: missing dependencies the task assumes, broken image, flaky services, ambiguous task statement with contradictory oracle.
- **Decision rule:** Label only with evidence the defect is environmental (e.g., the documented oracle solution would also fail).
- **Provenance:** TRAIL: environment setup errors; AET: environment error.

### SYS-4 Model/API failure
- **Definition:** LLM-provider-level failures: API errors, context-window overflow, truncated generations, harness-garbled I/O.
- **Provenance:** TRAIL: API/system issues; AET: LLM limit.

### SYS-5 Resource exhaustion
- **Definition:** The container runs out of memory/disk/CPU in a way not attributable to a specific agent mistake (else the mistake, e.g., ACT-3, is the root cause).
- **Provenance:** TRAIL: resource exhaustion.

## Escape hatch

If no category fits, annotate with code `NEW-?` plus a free-text description of the proposed category. `NEW-?` usage is tracked by the coverage analysis and is the primary empirical signal for *adding* categories in v1.

## Deliberately excluded from source taxonomies (removal candidates confirmed at v1)

| Source category | Why excluded from v0 |
|---|---|
| TRAIL: task orchestration errors | Multi-agent coordination; this project is single-agent. Future work. |
| TRAIL: incorrect tool definition | Terminal-Bench agents get a shell, not bespoke tool definitions; harness-side defects fall under SYS-3. |
| TRAIL: poor information retrieval | RAG-pipeline specific; terminal analogues are covered by MEM-1/RFL-1/PLN-3. |
| TRAIL: auth/rate-limit subcodes | Collapsed into SYS-4; per-status-code granularity earns no analysis value at this project's scale. |

Later studies can *reinstate* any of these if `NEW-?` annotations or unclassifiable failures show they were needed — that outcome is itself an empirical finding for research question 1.

## Revision log

| Version | Date | Change | Evidence |
|---|---|---|---|
| v0 | 2026-07-09 | Initial draft merged from TRAIL + AgentErrorTaxonomy with 3 terminal-specific additions (RFL-3, ACT-1, ACT-6) and 4 exclusions | Literature only (`related-work.md`); no trajectory data yet |
