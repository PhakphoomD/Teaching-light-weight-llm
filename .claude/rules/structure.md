# Canonical Repo Structure

Source of truth for **housekeeping**. Layout follows ML project best practices
(cookiecutter-data-science + Real Python `src` layout). Items marked *(planned)* are the
agreed target (ADR-009) but not yet created — do NOT flag them as missing junk.

```
Teaching-light-weight-llm-based-project/
├── .claude/                    # Claude env: CLAUDE.md, rules/, agents/, settings
├── config/                     # YAML configs (system + prompts)
├── data/
│   ├── Medical_Q&A/            # raw MedQuAD CSVs — IMMUTABLE
│   ├── medical_by_source/      # per-domain JSONL (derived) — treat as raw
│   ├── clean/                  # cleaned + split outputs (tool-generated)
│   ├── interim/                # (planned) intermediate transforms
│   └── processed/              # (planned) final train/heldout ready for modeling
├── db/                         # (planned) unified SQLite store (ADR-010)
├── docs/
│   └── adr/                    # (planned) full ADR files; summaries in rules/decisions.md
├── logs/experiments/           # phase results (summary.jsonl, memory, faiss, debug)
├── models/                     # (planned) LoRA adapters, encoders (git-ignored, large)
├── notebooks/                  # analysis notebooks
├── reports/                    # (planned) generated figures/reports; reports/figures/
├── scripts/                    # standalone stage scripts (import from src/)
├── src/                        # importable library (simplified/, providers/, core/, eval/, utils/)
├── tests/                      # (planned) unit/integration tests, mirrors src/
├── tools/dataset/              # Dataset Readiness Assessor + cleaner
├── simplified_teaching_loop.py # main loop
├── simplified_experiment_runner.py
├── requirements.txt / environment.yml
└── README.md
```

## Placement rules
- `data/Medical_Q&A/` and `data/medical_by_source/` are **immutable** — never edit; derive forward into `data/clean/` → (planned) `data/processed/`.
- Reusable tools → `tools/`; one-off stage scripts → `scripts/` (import shared logic from `src/`).
- Library/importable code → `src/`; app entrypoints stay at root.
- Analysis prose → `docs/`; machine artifacts (jsonl, index, db) → `logs/`, `data/`, `db/`.
- Tests mirror `src/` under `tests/`.

## Junk / smell checklist (housekeeping flags these)
- Debug dumps, `*.tmp`, editor backups, stray `__pycache__/` not git-ignored.
- Files claiming to be "clean" that still contain raw boilerplate (e.g. `medical_all_clean.jsonl` still has 1,439 HPO hits — misnamed).
- Hardcoded absolute paths in committed configs (e.g. `C:\Users\...\Desktop\...` in `logs/experiments/*/configs/*.yml`).
- Duplicated data files with no clear owner.
- Numbers in `docs/`/`README` that disagree with `logs/experiments/*/summary.jsonl`.
- New reusable code placed at repo root instead of `src/` or `tools/`.
