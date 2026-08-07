# P3 — Track B: RAG + LoRA Product (PLANNED 2026-07-16, after Track-A results)

**Status: active planning.** P3 is now broken down because Track-A results exist (ADR-024) and
they point the direction. This file is the P3 index; each task has a full spec `docs/plan/T3.*.md`.

## What Track A decided that shapes P3 (ADR-024 — do not relitigate)
- **Teacher-in-the-loop is dead as a runtime feature:** C−B = +0.003 [−0.021,+0.029], p=1.00.
  Do NOT build a teacher-improves-student-at-inference product.
- **Self-refinement is the real, cheap, local gain:** B−A = +0.091 [+0.051,+0.133], p<0.0001.
  It costs only extra student rounds (no teacher, no cloud) → keep it in the product.
- **reference-match ≠ correctness** (flat semantic while correctness rose) → RAG eval must judge
  *grounded correctness*, never phrase-similarity to a gold answer (repeat of the ADR-001 trap).
- **The loop's honest role = offline factory** (ADR-003/024): it GENERATES + CURATES data for RAG
  and LoRA; it is not a runtime component.

## Locked already (ADR-015) — inputs to every P3 task
- Product = small LOCAL model, deep in one domain, for SMEs. Floor **3B**, ceiling **7B**,
  1B = stretch only. RAG = knowledge, LoRA = style/format, loop = offline factory.
- Corpus exists: `data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_clean.jsonl` (n=631,
  RAG readiness **READY 93.4**, `..._readiness_rag.json`); held-out 125 reserved and never trained on.
- Seam is ready: Config Contract slot D `memory.type ∈ {none, faiss, rag}` — `rag` is reserved
  and deliberately UNregistered (`src/tlw/registries.py:16` fails loud until T3.3 builds it).

## Ownership (assigned now per ADR-021's deferral — no new agents)
retrieval corpus/index → **data-engineer** · RAG backend block → **codebase-steward** · grounded
eval → **qa-engineer** · training runs → **ops-engineer** · design/ADRs → **program-architect**.
Frontend stays unowned until the P3-C gate.

## Sub-tracks & sequence (RAG first — user decision 2026-07-16)

**P3-A — RAG (detailed now; this is where we start):**
```
T3.1 RAG blueprint (paper) → T3.2 corpus+retriever → T3.3 rag backend (slot D) ┐
                                                     T3.4 grounded-QA eval ─────┴→ T3.5 RAG ablation + report
```
- **T3.1** RAG architecture + grounded-eval design on paper (+ADR). Docs only.
- **T3.2** Build the retrieval corpus + index from `data/clean/` Diabetes.
- **T3.3** Implement slot-D `type: rag` backend (retrieve passages → grounding context, not answers).
- **T3.4** Grounded-QA eval block: faithfulness/groundedness + blind correctness; independent judge.
- **T3.5** RAG ablation (3B, 3B+RAG, 7B, 7B+RAG) on held-out 125 → `docs/RAG_RESULTS.md` + ADR.
  **GATE ✋** — the RAG number decides how much LoRA matters (P3-B scope).

**P3-B — LoRA (light specs; firm up AFTER the T3.5 gate):**
- **T3.6** LoRA data generation via the loop-factory + self-refine (curated pairs).
- **T3.7** QLoRA 4-bit fine-tune of the 3B on RTX 4060 8GB (style/format, LIMA-scale).
- **T3.8** Combined product eval: 3B+RAG+LoRA vs baselines vs big model, held-out.

**P3-C — Product surface (placeholder):** minimal local chat UI for the SME use case; storage
upgrade (revisit ADR-010 SQLite/sqlite-vec). Unowned; planned at the hub after T3.8.

## Why RAG before LoRA (evidence, not preference)
Ovadia et al. 2024 (EMNLP, "Fine-Tuning or Retrieval?"): RAG beats fine-tuning for injecting
factual knowledge. Track A confirmed the loop does NOT add knowledge (C−B≈0). So knowledge must
come from RAG; LoRA only teaches style — and how much style-tuning helps can only be judged once
RAG has closed (or not closed) the knowledge gap. Measure RAG first, let it scope LoRA.
