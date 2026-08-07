# Product Results — does QLoRA fine-tuning help the small model? (T3.8)

**Status:** complete (2026-07-23) · **Owner:** qa + ops
**One-line verdict:** No — **naive QLoRA SFT on the domain's reference answers HURT the 3B by
~29 points** (0.868 → 0.576, 95% CI [−0.360, −0.224]). Not because the training failed — it
succeeded at transferring the reference *style* — but because that style (terse NIH text) conflicts
with what the eval rewards (completeness). Fine-tuning taught the model to be *briefer*, and the
"correct AND complete" bar punishes brevity. This closes the RAG+LoRA product question: on this
near-ceiling testbed, **neither RAG (knowledge) nor LoRA (style) improves the aggregate.**

---

## 1. Method

- **Base:** `Qwen/Qwen2.5-3B-Instruct` (HF), 4-bit NF4. **Adapter:** QLoRA r=16 on attention+MLP
  projections, 2 epochs on the RTX 4060 8GB (loss 1.98→0.99, token-acc 0.59→0.75, 23 min, T3.7).
- **Training data (T3.6):** 506 (TRAIN question → TRAIN gold NIH answer) pairs — standard
  instruction SFT. Recipe pivoted from the spec's "loop-factory" because the loop yields no
  distillable signal here (self-refine doesn't engage on the near-ceiling train set; RAG hurts,
  ADR-027). Held-out excluded (verified by id + question).
- **Eval:** base 3B vs 3B+LoRA on the **held-out 125**, both on the **same HF-inference stack**
  (adapter on/off — so the delta isolates LoRA), 2 seeds, temperature 0.3. Correctness = the
  **validated Groq blind judge** (T3.9: κ=0.54 vs a careful anchor; the local judge was rejected),
  score≥4. Paired bootstrap CI over questions. 0 judge fallbacks (clean, consistent judge).

---

## 2. Result

| Arm | Pass-rate (score≥4) |
|---|---|
| 3B base (HF) | 0.868 |
| 3B+LoRA | 0.576 |
| **LoRA − base** | **−0.292, 95% CI [−0.360, −0.224]** (significant) |

(The HF base 0.868 sits a little above the Ollama-stack base 0.821 of the RAG table — a
different inference stack; the LoRA−base delta on the *same* HF stack is the clean comparison.)

---

## 3. Mechanism — the style transfer succeeded and that is exactly why it hurt

The fine-tune did what LIMA (Zhou et al. 2023, *LIMA: Less Is More for Alignment*, NeurIPS,
arXiv:2305.11206) predicts SFT does — **it transferred the reference answers' style/format**. Direct
comparison of base vs LoRA answers (greedy) shows the LoRA model **adopting the NIH gold phrasing**
("the pituitary is a small, pea-sized gland…", "A health care provider diagnoses X by…") and
producing **consistently ~30–45% shorter answers** (e.g. 178→95, 158→26, 152→122, 174→141 words).

But the MedQuAD gold answers are **terse, templated NIH sections**, and the eval bar is score≥4 =
"correct **AND complete**". So teaching the 3B to imitate the terse references made it **less
complete**, and the completeness bar punished it. The base `Qwen2.5-3B-Instruct` was already
RLHF-tuned to be thorough/helpful; SFT on terse references **partially undid that thoroughness** —
a **catastrophic-forgetting / alignment-tax** effect (Luo et al. 2023, *An Empirical Study of
Catastrophic Forgetting in LLMs during Continual Fine-tuning*, arXiv:2308.08747; the "alignment
tax" of Ouyang et al. 2022, *InstructGPT*, arXiv:2203.02155). The training objective (imitate the
terse gold) **diverged from the eval objective** (complete answers), so optimizing the former hurt
the latter.

Nuance (not all one-directional): on a few questions the terser LoRA was *more* on-point than the
base — e.g. "How many people are affected by Acromegaly?" where the base gave a generic
non-answer and the LoRA gave a concrete number. But the aggregate is a clear, large negative:
brevity loses far more "complete" points than directness gains.

---

## 4. The combined RAG+LoRA product picture (ADR-003's thesis, tested honestly)

ADR-003 proposed: **RAG = knowledge, LoRA = style, loop = offline factory.** Tested on this domain:

| Lever | What it should add | Measured effect | Why |
|---|---|---|---|
| Loop / teacher | runtime improvement | **≈ 0** (C−B, ADR-024) | self-refine is the only gain; teacher adds nothing |
| RAG | domain knowledge | **≈ 0 (3B), −7pt (7B)** (ADR-027) | near-ceiling baseline → tiny knowledge gap; distraction cancels repair |
| LoRA | answer style | **−29pt** (this doc) | reference style (terse) ≠ eval objective (complete) → style transfer backfires |

**On a near-ceiling factual-recall testbed, none of the three levers improves the aggregate** —
each for an honest, mechanistic reason. The value that *does* exist is on the **hard tail**: RAG
converts genuine knowledge-gap questions from "never reliably answered" to "reliably answered"
(`RAG_RELIABILITY_ANALYSIS.md`). The product lesson is **selective/targeted application on the hard
tail, judged by an objective the training targets actually match** — not blanket RAG or naive SFT.

---

## 5. Limitations
- **Single domain, near-ceiling baseline** (0.87) — small headroom for any lever; do not generalize
  the magnitudes to harder tasks.
- **Recipe.** Naive gold-SFT is the simplest recipe and it backfired; better recipes untested here
  (distill a model that already has the *desired* complete style; mix general instruction data to
  prevent forgetting; fewer epochs / lower LR / KL-regularization; DPO on completeness).
- **Judge at the 3-vs-4 line.** κ=0.54 (T3.9) — good but sub-0.6; the effect is large enough
  (−29pt) to survive judge uncertainty, but the absolute pass-rates are soft.
- **2 seeds** (not 3) for the LoRA eval — CI is over 125 questions × 2 seeds.

---

## 6. Verdict (see the T3.8 ADR)

QLoRA fine-tuning is **feasible and worked technically** on the 4060 (a real end-to-end 4-bit
fine-tune), but **naive SFT on terse reference answers is the wrong recipe** — it optimizes style
imitation at the expense of the completeness the task rewards, degrading a strong instruct base by
29 points. The honest product conclusion for a small local medical-QA model on this domain: **do
not blanket-fine-tune on reference answers; the base instruct model is already strong, and the
gains (if any) live on the hard tail via targeted retrieval, not aggregate style-tuning.**

### Reproduce
```
python scripts/build_lora_data.py                                  # T3.6 data (506 pairs)
HF_HUB_OFFLINE=1 python scripts/train_lora.py --epochs 2           # T3.7 QLoRA adapter
HF_HUB_OFFLINE=1 python scripts/eval_lora.py --adapter models/lora_diabetes --seeds 1,2  # T3.8
```
Numbers from `runs_lora/lora_eval_result.json` (2026-07-23), validated Groq judge.
