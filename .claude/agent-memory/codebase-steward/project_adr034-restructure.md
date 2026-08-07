---
name: adr034-restructure-status
description: ADR-034 repo restructure (runs/<study>/, indexes/, reports/) is approved but NOT executed; a safety audit found 2 BLOCKERs that need user decisions first
metadata:
  type: project
---

As of 2026-08-07 the ADR-034 restructure (phases 1–5) is **approved and specified but not
executed**. The pre-execution safety audit is `docs/plan/MIGRATION_CHECKLIST.md`; the design is
`docs/plan/STRUCTURE_PROPOSAL.md` v2.

Two items block execution and require the user (§0.6 — they contradict an Accepted ADR or a
written spec, so no agent may resolve them alone):

1. **`runs_hardtail/` must not be deleted.** ADR-034 decision (5) approves deleting it as having
   "zero SSOT references" — true of the *directory name*, false of its *numbers*:
   `docs/RAG_RELIABILITY_ANALYSIS.md:16-17` is computed from it (recomputed exactly:
   per-attempt 0.606/0.640/+0.034, pass@5 0.89/0.74).
2. **The duplicated `runs_rag/trackA_full_armA_*` baseline must be kept** — it is the `3B` label in
   the `--rag` report, and `discover_runs` cannot see across study directories.

**Why:** the restructure exists to make the portfolio reproducible from a clone (§0.1/§0.3); both
items would destroy evidence in the name of tidiness.

**How to apply:** if a future session is asked to execute the restructure, read
`docs/plan/MIGRATION_CHECKLIST.md` §P0 first and confirm those decisions were taken. Do not trust
`STRUCTURE_PROPOSAL.md`'s step lists alone — the checklist corrects several of them. Verify the
status is still current (`git log`, `ls runs*`) before acting: if `runs/teaching-loop-medquad/`
exists, execution has already begun.

Related: [[guard-and-windows-path-gotchas]]
