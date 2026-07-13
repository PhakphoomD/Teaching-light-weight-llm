# P3 — Track B: RAG + LoRA Product (DELIBERATELY NOT PLANNED YET)

**Status: placeholder. Do not invent or start P3 tasks.**

## Why empty (hub decision, 2026-07-13)
Detailed P3 planning before Track-A results exist would be guessing — the exact failure mode
of the old roadmap. T2.8's verdict (is the loop effect real, and how big?) determines the
loop's role in the product "factory", which reshapes every P3 task.

## What is already locked (ADR-015 — do not relitigate in spokes)
- Product = small LOCAL model, deep in one domain, for SMEs/general users.
- Model floor **3B** (Qwen2.5-3B / Llama-3.2-3B class — must run on ordinary home PCs),
  quality ceiling **7B** (Qwen2.5-7B, ADR-014). **1B = stretch experiment only** (extractive
  answerer over RAG), never the main bet.
- Architecture direction: RAG = knowledge, small LoRA = style/format (LIMA logic, ADR-003),
  loop = offline data-generation + evaluation factory, NOT a runtime component.
- Memory/RAG store must satisfy the T1.3 honesty contract (no answer-key memorization
  presented as learning).

## Expected P3 shape (sketch only — the hub will break this down after T2.8)
RAG block over `data/clean/` corpus → grounded-QA eval (faithfulness) → 3B vs 7B comparison →
LoRA data generation via the loop → QLoRA fine-tune on RTX 4060 8GB → combined eval
(small+RAG+LoRA vs baseline vs big model) → user-facing app (FE) + storage upgrade (ADR-010
SQLite decision revisited).

## Trigger
After T2.8: user returns to the hub with `docs/TRACK_A_RESULTS.md`; hub plans P3 micro-tasks
in the same format as P0–P2.
