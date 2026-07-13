# Dataset Readiness Assessor

Turn a raw Q&A dataset into a **cleaned** dataset + a **readiness report** (fit for
`rag` / `lora` / `eval`). Transparent, config-driven (`cleaning_config.yaml`), reproducible.
Backed by `.claude/rules/rubric.md` (dimensions) and `schema.md` (contracts).

All commands run in the `tlw` conda env, from repo root. Use the full-path interpreter (§0.5):
`& "C:\Users\ham25\.conda\envs\tlw\python.exe" …`

## Pipeline
| Stage | Command | Output |
|---|---|---|
| 1 · Clean | `-m tools.dataset.cli --all` | `data/clean/<d>_clean.jsonl` + `_report.json` |
| 2 · Assess | `-m tools.dataset.assessor --input data/clean/<d>_clean.jsonl --target lora` | `_readiness_<target>.md/.json` |
| 3 · Split | `-m tools.dataset.split --input data/clean/<d>_clean.jsonl` | `<d>_train.jsonl` + `<d>_heldout.jsonl` |
| 4 · Verify all | `scripts/assess_all.py --target lora` | cross-domain readiness table |
| 5 · UI (opt) | `-m pip install streamlit` then `-m streamlit run tools/dataset/app.py` | drag-and-drop web app |

Judge (D4 quality): `--judge none` (default in sweeps, model-free) · `groq` (Llama, fast) · `ollama` (local Qwen).

## Design guarantees
- **Non-destructive** — every record keeps `answer_raw` + `cleaning_flags` (`schema.md`).
- **Deterministic & seeded** → reproducible.
- **Held-out integrity** — excludes `is_template` records, stratified by question type (§0.2).
- **Transparent scoring** — 7-dimension rubric with per-target weights, not a black-box %.
- Raw data (`data/Medical_Q&A/`, `data/medical_by_source/`) is immutable; outputs → `data/clean/`.

## Files
| File | Role |
|---|---|
| `cleaning_config.yaml` | all rules & thresholds |
| `cleaner.py` | load → fix_question → strip_boilerplate → relabel → filter → dedup |
| `report.py` | model-free before/after metrics |
| `embeddings.py` | MiniLM: near-dup (D3), diversity (D6), relevance (D7) |
| `judge.py` | D4 quality judge (Groq / Ollama) |
| `assessor.py` | D1–D7 → weighted overall + volume gate + verdict |
| `split.py` | train / held-out split |
| `cli.py` | cleaning entry point |
| `app.py` | Streamlit UI |
