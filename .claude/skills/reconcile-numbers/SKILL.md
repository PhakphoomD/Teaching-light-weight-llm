---
name: reconcile-numbers
description: Honesty audit (§0.1) — verify every number reported in README.md and docs/ against its source log in logs/experiments/*/summary.jsonl. Use before any milestone, report, or commit that touches documentation, or when the user asks "are these numbers real?".
---

# Reconcile reported numbers with logs

Authority: `00-index §0.1` (honesty), `§0.4` (evidence). Known offenders are listed in
`rules/todo.md → Housekeeping backlog` (e.g. "25%→83%" in README vs 33%→84% in logs).

## Procedure
1. Collect claims: `Grep` for `%`, `accuracy`, `score`, `→` in `README.md` and `docs/**/*.md`.
   Record each as `(file:line, claimed value, what it claims to measure)`.
2. For each claim, find its source: the matching `logs/experiments/*/summary.jsonl` (read with
   the tlw python or the Read tool — never edit these files).
3. Recompute the number from the log (count/mean exactly as the doc describes it).
4. Classify: **MATCH** / **MISMATCH** (doc ≠ log) / **UNSOURCED** (no log exists — this is a §0.1
   finding, not a pass).
5. Fix docs to match logs (never the reverse — `logs/experiments/` is write-protected by the
   guard hook). If a number is unsourced, delete it or mark it clearly as unverified.
6. Report a table: claim | doc value | log value | source file | action taken.

## Rules
- Reproduce, don't eyeball: paste the command + output used to recompute each number.
- A weak real number beats a strong stale one — never "smooth over" a downgrade.
- If a log is missing/ambiguous, say NOT VERIFIED; do not guess.
