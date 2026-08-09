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
| **qa-engineer** | R | tests, verification, eval integrity, readiness checks, **ablation statistics (C−B with 95% CI — T1.4/T2.8)** | sonnet |
| **ops-engineer** | B | env/deps/GPU/conda, run, reproducibility | sonnet |
| **codebase-steward** | B (R for pure reviews) | code quality, conventions, refactors | sonnet |
| **housekeeping** | R | structure audit vs `structure.md`, junk detection | haiku |

## Dispatch guidance
Data → **data-engineer** · prompts → **prompt-engineer** · env/GPU/enforcement (guard,
settings) → **ops-engineer** · tests/verify/**ablation statistics** → **qa-engineer** ·
refactor/quality → **codebase-steward** · design/tech choices/ADRs → **program-architect** ·
planning/SSOT → **project-coordinator** · structure audit → **housekeeping**. Housekeeping
dispatches a fixer only when explicitly asked.

## Renovation phase (ADR-015) — task ownership
The renovation is complete (`todo.md` is the dated log): Track A honest ablation → Track B
product. P2 owners: config loader/registries T2.1–T2.2 → **ops-engineer**/**codebase-steward**;
eval block T2.3 → **qa-engineer**+**prompt-engineer**; loop block T2.4 → **codebase-steward**+
**prompt-engineer**; memory block T2.5 → **data-engineer**; runner + runs T2.6–T2.7 →
**ops-engineer**+**qa-engineer**; analysis/report T2.8 → **qa-engineer**; demolition T2.9 →
**codebase-steward**+**housekeeping**.

## Future ownership (P3 — deliberately unassigned until P3 planning, ADR-015)
Ablation **statistics** is folded into **qa-engineer** (no new role — cheapest structure that
covers P2). **RAG engineering** and **LoRA/QLoRA training** have no owner yet by design: P3 is
not broken down until after T2.8 results exist. When P3 is planned, assign them to existing
agents with updated charters (data-engineer for retrieval corpus, ops-engineer for training runs)
or add roles then — do **not** create P3 agents now. Frontend/app: unowned, out of P0–P2 scope.
