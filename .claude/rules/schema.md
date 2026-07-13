---
paths:
  - "data/**"
  - "scripts/**"
  - "tools/**"
  - "logs/**"
  - "src/**"
---

# Data Contracts (project-wide)

Every data format in the project + where it lives and how it's read/written. Raw data is
immutable (§structure). Future direction: unify into one lightweight store (ADR-010).

## Storage map
| Artifact | Path | Format | Written by | Read by |
|---|---|---|---|---|
| Raw MedQuAD | `data/Medical_Q&A/*.csv`, `data/medical_by_source/*.jsonl` | CSV/JSONL | source | cleaner, runner |
| Cleaned records | `data/clean/*_clean.jsonl` | JSONL | `tools/dataset` | assessor, RAG, LoRA |
| Readiness report | `data/clean/*_report.json` | JSON | assessor | user |
| Memory store | `logs/experiments/*/**.jsonl` | JSONL | `src/simplified/memory.py` | loop |
| FAISS index + ids | `*.index` (binary), `*.ids.json` | FAISS/JSON | memory.py | loop |
| Experiment summary | `logs/experiments/*/summary.jsonl` | JSONL | runner | notebook, docs |
| Per-round debug | `logs/experiments/*/debug_per_round.jsonl` | JSONL | logger | analysis |
| Run debug | `logs/simplified/debug/*.json` | JSON | debug_logger | analysis |
| Configs | `config/*.yml`, `logs/experiments/*/configs/*.yml` | YAML | user/runner | loop |

## Record shapes (current, real)

**Raw MedQuAD** — `{id, question, answer, source|topic}`

**Cleaned record** (non-destructive) —
`{id, domain, question, answer, answer_raw, cleaning_flags[], word_len, is_template, split}`
Rules: keep `answer_raw`; append a `cleaning_flags` entry per transform; `is_template=true` → excluded from `heldout`.

**Memory episode** (`memory.py`) —
`{id(hex), question, teaching_feedback, attempts, success_count, success_rate, scores{exact_match,rouge_l,semantic_sim,blind_score,comparison_score,final}, timestamp}`
Paired with `*.ids.json` (array mapping FAISS row → id) + `*.index` (binary embeddings).
⚠️ `gt_memory_store.jsonl` variant stores the ground-truth **as** `teaching_feedback` ("Reference Answer…") — this is the leakage path (ADR-001, §0.2). Keep it out of any measure-mode run.

**Experiment summary** (`summary.jsonl`, one line per run) —
`{experiment_id, phase, num_questions, passed_count, pass_rate, seed, metrics{exact_match,rouge_l,semantic_similarity,blind_judge,comparison_judge}, avg_rounds, memory_hits, memory_hit_rate, student_tokens_total, teacher_tokens_total, student_teacher_tokens, timestamp, config_used{}}`

**Per-round debug** (`debug_per_round.jsonl`) —
`{phase, experiment_id, question_id, question_idx, round, question, answer, scores{}, final_score, passed, memory_used, time_ms, timestamp}`

**Readiness report** — see `rubric.md` (dimensions{score,band}, volume, overall, verdict, before/after, fixes).

## Future: unified lightweight store — SQLite (ADR-010, Proposed)
**Why:** data is scattered across JSONL + JSON + FAISS + YAML → hard to navigate, query, and hand to others. A single DB is easier for everyone.
**Choice:** **SQLite** — in Python **stdlib** (`sqlite3`, zero install), single portable file, universally known, GUI via DB Browser, trivial `pandas.read_sql`/`to_sql`, and RAG vector search via the light `sqlite-vec` extension. (DuckDB = optional analytics companion; can query the same files for heavy aggregation.)
**Proposed tables:** `records`(cleaned Q&A), `memory_episodes`, `experiments`, `rounds`, `readiness_reports`, `embeddings`(vec). JSONL stays the source of truth until migration; **migration is deferred until after the cleaning phase** (todo).
