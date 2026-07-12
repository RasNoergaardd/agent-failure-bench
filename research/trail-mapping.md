# TRAIL ↔ Taxonomy-v0 Mapping

Scoring instrument for RQ2 (judge validity). TRAIL's gold annotations use TRAIL's categories; our judge outputs taxonomy-v0 codes. Agreement is scored through this table: a judge label **agrees** with a TRAIL gold label if the gold category appears in the judge code's mapped set below. The mapping is derived from the provenance lines in `taxonomy-v0.md`; it is a methodological choice and is cited as such in the report.

## TRAIL category → taxonomy-v0 code(s)

| TRAIL category | Our code(s) | Note |
|---|---|---|
| Hallucination (text-only) | MEM-2 | Narrowed to false claims about session history |
| Hallucination (tool-related) | RFL-5 | Fabricated verification/tool results |
| Tool output misinterpretation | RFL-1 | |
| Incorrect problem identification | PLN-1 | |
| Tool selection error | ACT-2 | |
| Formatting errors | ACT-5, ACT-1 | ACT-1 if the malformed output is the shell command itself |
| Instruction non-compliance | MEM-3, PLN-2 | MEM-3 if compliance drifted; PLN-2 if ignored from the start |
| Context handling failures | MEM-1 | |
| Resource abuse | PLN-3 | |
| Goal deviation | PLN-4 | |
| Environment setup errors | SYS-3 | |
| API/system issues | SYS-4 | |
| Resource exhaustion | SYS-5 | |
| Timeout issues | SYS-2 | |
| Poor information retrieval | — | Excluded from v0; nearest are MEM-1 / RFL-1 / PLN-3 (scored as disagreement) |
| Incorrect tool definition | — | Excluded from v0; harness-side defects fall under SYS-3 (scored as disagreement) |
| Task orchestration errors | — | Excluded from v0 (multi-agent); scored as disagreement |

## Taxonomy-v0 codes with no TRAIL counterpart

These come from AgentErrorTaxonomy or are terminal-specific additions; on TRAIL data the judge should rarely emit them, and when it does, the label counts as disagreement with any TRAIL gold category:

| Our code | Origin |
|---|---|
| RFL-2 progress misjudgment, RFL-4 causal misattribution, ACT-3 parameter error, ACT-4 plan–action mismatch, PLN-5 infeasible strategy, SYS-1 budget exhaustion | AgentErrorTaxonomy only |
| RFL-3 verification omission, ACT-6 destructive action | NEW (terminal-specific) |

## Scoring rules (Study 1)

1. **Function-level agreement:** map the TRAIL gold category to our code(s), take the code's cognitive function; judge agrees if its function matches. Multi-mapped golds (e.g., instruction non-compliance) agree on either function.
2. **Type-level agreement:** judge's code must be in the gold category's mapped set.
3. **Location:** scored independently per TRAIL's convention (span match), unaffected by this table.
4. Gold labels in the three unmapped TRAIL categories are reported separately and excluded from the headline agreement figure (the judge cannot express them by construction).
