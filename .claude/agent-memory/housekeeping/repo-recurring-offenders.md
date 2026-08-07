---
name: repo-recurring-offenders
description: The checks that repeatedly find real problems in this repo — run these first to make a structure audit fast
metadata:
  type: project
---

The audit patterns that keep paying off here. Run these first; they found every BLOCKER/MAJOR in the
2026-08-07 pass ([[structure-audit-2026-08]]).

1. **`git check-ignore` on every artifact dir.** The `.gitignore` pattern `runs/` matches only the
   directory literally named `runs` — eight sibling `runs_*` roots leaked out untracked. Always test
   ignore status per directory; never assume a pattern covers siblings.
2. **`grep -rn "ROOT\s*=\s*Path("` across `scripts/`.** Two conventions coexist: the correct
   `Path(__file__).resolve().parents[1]` and a hardcoded `C:/Users/ham25/...` literal. New scripts
   written fast during experiments tend to copy the wrong one.
3. **Cross-file imports inside `scripts/`** (`grep -rn "from scripts\." scripts/*.py`). Library code
   keeps growing inside driver scripts; there is no `scripts/__init__.py`, so it works only by
   PEP-420 accident.
4. **`md5sum` matching run dirs across sibling run roots.** Baselines get copied between studies to
   "avoid conflation" and then diverge in provenance.
5. **Docs claiming a run "is running".** Long-running sweeps finish but the status prose does not get
   updated — a §0.1 drift that greps for as `is running` / `to be confirmed` in `docs/*.md`.
6. **`find src/<pkg>` after a demolition task.** T2.9 deleted sources but left `__pycache__`-only
   ghost directories, so the tree still *looks* like the legacy core exists.

**Why:** this project's failure mode is not messy code — `src/tlw/` is clean and tested. It is that
the *experiment layer* (scripts, run outputs, indices) grows faster than the rules describing it.

**How to apply:** open the file for every hit (§0.4); a filename alone is never evidence. Before
proposing a move, price it: `grep -rno "<path>" --include="*.md" .` — inbound-link count decides
whether the move earns its cost. References inside `.claude/rules/decisions.md` are §0.6-sensitive
and should be left alone.
