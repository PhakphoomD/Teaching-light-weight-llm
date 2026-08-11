---
name: run-pipeline
description: Run the dataset cleaning pipeline (tools/dataset) the reproducible way and report real before/after numbers. Use when asked to clean data, re-run the cleaner, or verify data/clean/ outputs.
---

# Run the dataset cleaning pipeline

Authority: `00-index §0.3` (reproducible), `§0.5` (python path), `rules/schema.md`, `rules/rubric.md`.

## The one command
```powershell
& "$env:TLW_PYTHON" -m tools.dataset.cli --all   # or the full path from §0.5
```
Run from the repo root. Single domain: replace `--all` with `--domain <name>`.

## Before running
- Rules live in `tools/dataset/cleaning_config.yaml` — change behavior there, not in code.
- Inputs are `data/medical_by_source/*.jsonl` (immutable — the guard hook enforces this);
  outputs go to `data/clean/`.

## After running
1. Capture stdout — it contains the per-domain before/after counts.
2. Compare against the last known baseline (Stage 1: 12,428 → 10,024 across 7 domains,
   noise → 0%; see `rules/todo.md`). Explain any delta.
3. Spot-check 3–5 cleaned records against their raw counterparts (answer_raw preserved,
   flags recorded — `schema.md` contract).
4. Report real numbers only (§0.1); if the run failed, report the failure.
