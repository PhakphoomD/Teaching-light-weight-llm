# LoRA SFT dataset — Diabetes (T3.6)

- **Pairs:** 506  (question -> gold reference answer)
- **Source:** `Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl` (TRAIN split only)
- **Recipe:** gold-SFT (instruction tuning on the domain reference answers).
  Rationale: the loop-factory recipe yields no distillable signal on this
  near-ceiling testbed (self-refine doesn't engage; RAG hurts, ADR-027), so the
  target is the reference answers — teaching answer style/format (LIMA).
- **Answer length (words):** min 20, median 125, max 346
- **Anti-leak (§0.2):** held-out 125 excluded by id AND question; verified 0 held-out here.
- **Filters skipped:** {'template': 0, 'len': 0, 'dup': 0, 'heldout': 0, 'empty': 0}
- **Expected result (T3.8):** modest/null held-out gain — LoRA teaches style, not
  the held-out-specific knowledge (LIMA); reported honestly.
