---
name: structure-audit-2026-08
description: 2026-08-07 structure audit verdict FAIL; propose-only redesign at docs/plan/STRUCTURE_PROPOSAL.md, now at v2 after the user rejected v1's naming, awaiting approval
metadata:
  type: project
---

The 2026-08-07 repo structure audit returned **FAIL** and produced a propose-only redesign at
`docs/plan/STRUCTURE_PROPOSAL.md`, revised to **v2** the same day after the user rejected v1's
naming convention. **Nothing has been moved** — approval comes first.

Three headline problems: (1) `.claude/rules/structure.md` v2 no longer describes the repo — it
lists 6 deleted legacy paths and omits ~14 that exist (the 9 root `runs*/` dirs,
`data/{rag,wixqa,processed,calibration}`, `tools/rag/`, `src/tlw/analysis/`); (2) 13
`scripts/wixqa_*.py` hardcode an absolute machine ROOT (§0.3); (3) `README.md:90` claims run logs
are committed when none are.

Two settled judgement calls worth not re-deriving. **Keep the package name `tlw`:** 158 import
sites, ~25 docs, 8 agent files — and the conda env is *also* named `tlw`, hardcoded in the frozen
§0.5 Constitution line, so a clean rename is impossible without user approval; the real fix is one
sentence expanding the acronym. **`tests/` needs a tidy, not a rework:** test names already
describe behaviour and the four `conftest.py` files each have a distinct documented job; the real
issues are a missing mirror for `tools/rag/`, `__init__.py` in only 4 of 10 dirs, and a `sys.path`
hack replaceable by a 7-line `pytest.ini`.

**Why:** the P3 experiment layer grew fast during the RAG/LoRA studies with no layout rule covering
it, so artifacts landed at repo root with insider names. Three Accepted ADRs constrain the fix —
ADR-017 (canonical tree), ADR-023 (run-output location), ADR-016 (experiment-config naming) — each
needing a *new superseding ADR*, never an edit (§0.6).

**How to apply:** before any new structure audit, check whether the proposal was approved and
executed (does `runs/<study>/` exist? is `structure.md` at v3?). If executed, the findings above
are stale — re-audit against the new `structure.md`. If still pending, do not re-litigate; ask what
changed. See [[feedback-naming-must-read-as-english]] and [[repo-recurring-offenders]].
