# Agent Team & Ownership

Eight specialists. The **project-coordinator** sequences work; **housekeeping** audits
structure. User-facing questions/approvals stay with the main thread (subagents cannot ask
the user). Every agent follows the skeleton in ADR-008 and the §0 Constitution.

## Output archetypes (ADR-008)
- **R (Review/Audit):** `VERDICT` + `FINDINGS[BLOCKER/MAJOR/MINOR]` + `NOT VERIFIED` + `EVIDENCE LOG`.
- **B (Build/Change):** `SUMMARY` + `CHANGES` + `EVIDENCE` + `VERIFICATION` + `DECISIONS` + `NOT DONE/RISKS`.
- **P (Plan/Dispatch):** `PLAN` + `STEPS(→owner)` + `SEQUENCE` + `RISKS` + `NEEDS-USER-DECISION`.

| Agent | Archetype | Owns | Model |
|---|---|---|---|
| **project-coordinator** | P | SSOT (todo/ADRs/index), planning, dispatch | opus |
| **program-architect** | B | architecture, ADRs, tech choices (with evidence) | opus |
| **data-engineer** | B | dataset pipeline: cleaner, Readiness Assessor, splits, `tools/dataset/` | sonnet |
| **prompt-engineer** | B | student/teacher/judge prompts, anti-GT-leakage | opus |
| **qa-engineer** | R | tests, verification, eval integrity, readiness checks | sonnet |
| **ops-engineer** | B | env/deps/GPU/conda, run, reproducibility | sonnet |
| **codebase-steward** | B (R for pure reviews) | code quality, conventions, refactors | sonnet |
| **housekeeping** | R | structure audit vs `structure.md`, junk detection | haiku |

## Dispatch guidance
Data → **data-engineer** · prompts → **prompt-engineer** · env/GPU → **ops-engineer** ·
tests/verify → **qa-engineer** · refactor/quality → **codebase-steward** · design/tech
choices → **program-architect** · planning/SSOT → **project-coordinator** · structure
audit → **housekeeping**. Housekeeping dispatches a fixer only when explicitly asked.
