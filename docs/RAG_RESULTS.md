# RAG Results — Does retrieval help a small local model on domain QA?

**Status:** Headline complete (full pre-registered run, 2026-07-16) · **Owner:** ops + qa-engineer
**One-line verdict:** On this MedQuAD Diabetes held-out set, adding RAG to a 3B model has **no
net effect on correctness** — but not because nothing happens. RAG **fixes about as many
knowledge-gap questions as it breaks** by distracting the model on questions it already knew
(**3B+RAG − 3B = −0.5%, 95% CI [−6.7%, +5.6%], McNemar p = 0.91**; 39 broken, 37 fixed). The
loop-style null of Track A repeats here with a richer mechanism: retrieval is a **tug-of-war**,
not an inert component.

---

## 1. Method (pre-registered in `docs/protocol/2026-07-16-rag-medquad-protocol.md`, ADR-026)

Four-arm ablation was planned; this run reports the **headline pair** (the user-approved scope):

| Arm | Student | Retrieval (slot D) | Role |
|---|---|---|---|
| **3B** | `qwen2.5:3b` (local) | none | baseline (reused from Track A, arm A — `small-model-no-rag`) |
| **3B+RAG** | `qwen2.5:3b` (local) | `rag`, top-k 3, floor 0.35 | **the treatment** |

- **Single-pass** answering (`arm A`, `max_rounds 1`) so retrieval is the *only* variable — no
  self-refine, no teacher (Track A already settled those, ADR-024).
- **Judge = Groq `llama-3.1-8b-instant`, blind, 0–4 correctness, PASS iff score ≥ 4** — the
  **identical judge and bar as the Track-A full run**, so these numbers are directly comparable.
  100% of the 375 headline judge calls ran on Groq (0 fallbacks) → one consistent judge across
  both arms.
- **Data** = 125 held-out Diabetes questions, **3 seeds {13, 42, 123}**, student temp 0.3.
- **Retrieval corpus** = the Diabetes TRAIN split, built held-out-free (`tools/rag/`): 506 → drop
  58 cosine near-dups (RAG-L2a) + 34 verbatim-block/template twins (RAG-L2b) → **414 passages**
  indexed (MiniLM + FAISS). Grounding passages enter the *first* answer prompt; a run-time
  per-passage leak filter (RAG-L3) dropped 30 residual passages across the run (never shown to
  the student).
- **Headline stat** (pre-registered, rag-medquad-protocol §6): pass-rate difference **3B+RAG − 3B** with a 95%
  **paired cluster-bootstrap** CI (cluster = question, 3 seeds pooled, 10,000 resamples), exact
  McNemar alongside, Wilson per-arm descriptive. Correctness, reference_match, and faithfulness
  are **never merged** (ADR-019).

---

## 2. Headline result

| Comparison | Estimate | 95% CI (paired cluster bootstrap) | McNemar | Reading |
|---|---|---|---|---|
| **3B+RAG − 3B** | **−0.005** | **[−0.067, +0.056]** | b=37 (RAG fixed), c=39 (RAG broke), **p=0.91** | **No net effect.** RAG breaks about as many as it fixes. |

Per-arm pass-rate (Wilson 95% CI, n=375 question-runs):

| Arm | Pass-rate | Wilson 95% CI | seed 13 | seed 42 | seed 123 |
|---|---|---|---|---|---|
| 3B | **0.821** | [0.779, 0.857] | 0.832 | 0.864 | 0.768 |
| 3B+RAG | **0.816** | [0.774, 0.852] | 0.824 | 0.800 | 0.824 |

Per-seed deltas: −0.008, −0.064, +0.056 (spread straddles zero — the effect is
generation-sensitive, consistent with a near-zero true effect). The CI is tight around zero and
McNemar p = 0.91: **RAG neither helps nor hurts the 3B on this set, on net.**

---

## 3. The mechanism — a tug-of-war (the real finding)

The null headline hides two large, opposing effects. Pooling all 375 question-seed pairs:

| Outcome | Count | Where it lands |
|---|---|---|
| both pass | 269 | — |
| both fail | 30 | — |
| **RAG BROKE** (baseline passed, RAG failed) | **39** | **35 of 39 on questions the baseline passed in ALL 3 seeds** (easy) |
| **RAG FIXED** (baseline failed, RAG passed) | **37** | **0 on easy; all 37 on questions the baseline failed**, concentrated on the hardest (15 on the all-3-seeds-fail set ≈ 38% recovery) |

So retrieval **hurts easy questions and helps hard ones**, and the two nearly cancel:
- **Distraction on easy questions.** For a question the 3B already answers correctly, grounding
  on a *related-but-wrong-aspect* passage (MiniLM retrieval is dominated by the disease name, so
  "treatments for X" retrieves "symptoms of X") pulls the model off its correct answer — dropping
  it from "complete" (score 4) to "partial" (3). 35 of the 39 breaks are here.
- **Knowledge-fill on hard questions.** For a question the 3B *can't* answer, a retrieved passage
  supplies the missing fact and the answer becomes correct. All 37 fixes are on baseline-failed
  questions; recovery on the genuine knowledge-gap set is ~38% (independently reproduced by a
  hard-subset probe: 5/13 at seed 42).

This is the documented RAG failure/benefit split (Ovadia 2024 — RAG helps *when a knowledge gap
exists*; Cuconasu "Power of Noise" 2024 — irrelevant retrieved context hurts). This testbed has
a near-ceiling baseline (0.82), so the gap is small and the two effects roughly balance.

---

## 4. Secondary views (diagnostics — never gate pass/fail, ADR-019)

- **reference_match** stays essentially flat (3B: sem 0.715 / rouge 0.192; 3B+RAG: sem 0.706 /
  rouge 0.224) — as in Track A, semantic similarity to the gold answer does not track correctness
  and is not the headline.
- **faithfulness** (RAGAS-style groundedness of the answer in its retrieved passages; diagnostic
  only, §0.2-safe): **≈ 0.81** over the parsed subset — BUT with a **61% null-rate** (228/375): the
  local `llama3.1:8b` faithfulness judge frequently failed to emit parseable claim counts, so this
  is **weak/indicative only**, not a reliable diagnostic at this judge quality. Directionally, a
  high groundedness (~0.81) *alongside* a flat correctness delta is the metric flagging "grounded,
  but grounded in the wrong thing" on the broken cases — consistent with the §3 mechanism. A
  stronger faithfulness judge would be needed to make this column trustworthy; the headline does
  not rest on it (ADR-019).
- **Cost.** Judge: 375 Groq calls, 0 fallbacks, ~187K tokens. Student: local, free. No teacher,
  no 70B. Headline end-to-end ≈ 42 min of local+Groq compute.

---

## 5. A note on the grounding prompt (a finding in itself)

A "hardened" grounding prompt — explicitly telling the model to *ignore* irrelevant passages and
*not mention* them — **backfired** on the 3B (pilot pass-rate 0.80 → 0.56). The small model
fixated on passage-relevance and prefaced answers with "the passage does not cover this…",
dropping completeness. A 3B cannot reliably follow "use-if-relevant-else-ignore-silently." The
run above uses the simpler v1 prompt (passages as optional background). Prompt-engineering did not
rescue RAG here — the effect is structural (no knowledge gap + small-model distractibility), not a
wording problem.

---

## 6. Limitations (state claims narrowly)

- **All four arms complete** (§8): 3B, 3B+RAG, 7B, 7B+RAG — the 7B pair answers the ceiling
  questions (RAG hurts the stronger model more; retrieval can't lift a 3B to a 7B).
- **Single domain, near-ceiling baseline.** MedQuAD Diabetes held-out is largely definitional and
  the 3B baseline is already 0.82 at score≥4 — so the knowledge gap RAG could fill is small by
  construction. On a harder / genuinely knowledge-gapped testbed the balance could tip positive
  (the hard-subset ~38% recovery is the evidence). Do not generalize the *net-zero* to other
  domains or harder question mixes.
- **Retrieval quality is topic-not-aspect.** MiniLM embeddings are dominated by the disease name,
  so same-disease-wrong-aspect passages are retrieved at high similarity — the similarity floor
  cannot separate them (broken cases sit at 0.70–0.85, same as good ones). A better retriever /
  re-ranker is untested here.
- **Judge validity at the 3-vs-4 line.** Inherited from Track A (teaching-loop-protocol §3.3 calibrated the
  ≥3 boundary, not the ≥4 bar used here). The **difference** 3B+RAG − 3B is robust to a consistent
  judge; the absolute pass-rates are softer.

---

## 7. Verdict and implication for P3-B (see ADR-027)

**Grounding a model indiscriminately does not help on this domain, and hurts more as the base model
gets stronger** (3B: −0.5%, ns; 7B: −6.9%, significant): it recovers the questions the model
doesn't know and breaks the ones it does, and the stronger the model the fewer it doesn't know, so
distraction wins. The actionable lesson is not "RAG is useless" but **"RAG must be *selective*"** — ground only when the model is uncertain or
retrieval is confident, not on every query, so the hard-question gains are kept without paying the
easy-question distraction tax. For the Track-B product: a naive always-on RAG layer will not move
the aggregate number; a **confidence-gated / uncertainty-triggered** RAG (and/or a better
domain-aware retriever) is where the measured value is. This scopes P3-B: LoRA (style) and any RAG
in the product should assume RAG's role is *targeted knowledge repair*, not a blanket accuracy
lift — and the eval that matters is on the **hard tail**, not the near-saturated average.

---

## 8. The full 4-arm table (2026-07-21, clean single Groq judge)

The 7B / 7B+RAG ceiling pair completed (originally corrupted by a Groq daily-cap exhaustion; the
7B+RAG runs were re-judged on a fresh, consistent Groq judge once the cap reset — student answers
were untouched, `scripts/rag/rejudge.py --only-nulls`). All four arms are now judged by the same Groq
`llama-3.1-8b-instant`, score≥4:

| Arm | Pass-rate | Wilson 95% CI | RAG delta (paired bootstrap, McNemar) |
|---|---|---|---|
| 3B | 0.821 | [0.779, 0.857] | — |
| 3B+RAG | 0.816 | [0.774, 0.852] | **−0.005** [−0.067, +0.056], p=0.91 (fixed 37 / broke 39) |
| 7B | 0.904 | [0.870, 0.930] | — |
| 7B+RAG | 0.835 | [0.794, 0.869] | **−0.069** [−0.120, −0.019], p=0.0004 (fixed 13 / broke 39) |

**RAG hurts the 7B *more* than the 3B, and significantly so** (7B CI excludes 0). And **3B+RAG
(0.816) < plain 7B (0.904)** — 3B+RAG − 7B = −0.088 [−0.136, −0.043] — so retrieval **cannot** lift
a 3B to a 7B's level on this domain. The mechanism is the same tug-of-war (§3), scaled by base
model strength: the stronger the model, the **fewer** knowledge gaps exist for RAG to fill (7B
fails ~10% vs 3B's ~18%) while the distraction tax on the easy majority is unchanged — so the
better the base model, the more RAG's distraction dominates its repair. **Both rag-medquad-protocol §3
secondary questions answer *no*:** RAG does not help a stronger model (it hurts more), and it does
not let a small model reach a big one. faithfulness for the 7B+RAG arm was not computed (diagnostic
only; the story is unaffected).

## 9. Follow-up: selective RAG

- **Selective RAG (the actionable direction from §7).** The oracle bound is **+9.9 points**
  (0.821 → 0.920 if grounding fired only on the 17.9% of questions the baseline fails) — the
  knowledge is there; the whole problem is the *gate*. But cheap gates do not reach it:
  model-uncertainty signals (answer length, hedging, cross-seed self-consistency) correlate ~0 with
  failure (the 3B is *confidently* wrong), and an 8B "verify-then-ground" LLM gate is bimodal-useless
  (99% fire on a lenient prompt, 0% on a strict one — it follows the prompt's tone, not the content).
  A strong-reasoner (70B) gate is the last cheap test, queued for the Groq reset. Full detail:
  `reports/rag-medquad/selective-gating-analysis.md`. Working hypothesis: selective RAG needs a *learned* gate or an
  *aspect-aware retriever*, not an LLM self-gate.

---

### Reproduce

```
# 1. Build the held-out-free index (§0.3):
HF_HUB_OFFLINE=1 python -m tools.rag.cli \
  --source  data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl \
  --exclude data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl \
  --out     indexes/medquad-diabetes-train
# 2. 3B+RAG, per seed ∈ {13,42,123} (the 3B baseline is the Track-A arm-A run,
#    copied into this study as small-model-no-rag):
EXPERIMENT_PARAMS_SEED=<seed> HF_HUB_OFFLINE=1 \
  python run.py --config experiments/rag-medquad/small-model-with-rag.yml \
  --data data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_heldout.jsonl \
  --no-faithfulness --judge-fallback local:llama3.1:8b --runs-dir runs/rag-medquad
# 3. Headline + tug-of-war:
python -m src.tlw.analysis --runs-dir runs/rag-medquad --rag
# 4. Faithfulness diagnostic (offline, local judge):
HF_HUB_OFFLINE=1 python scripts/rag/faithfulness.py --runs-dir runs/rag-medquad --judge local:llama3.1:8b
```

All numbers above were computed from `runs/rag-medquad/small-model-with-rag__seed{13,42,123}__*/` and
the reused `runs/rag-medquad/small-model-no-rag__seed{13,42,123}__*/` (3B baseline) on 2026-07-16
via `src/tlw/analysis` (paired cluster bootstrap + exact McNemar + Wilson).
