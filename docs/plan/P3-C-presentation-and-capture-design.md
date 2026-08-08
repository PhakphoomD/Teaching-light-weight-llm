# P3-C — What we present, and therefore what the demo must capture

**Purpose of this doc (hub, 2026-08-07):** work *backwards* from "what the portfolio must show" to
"what T3.15 (the demo) must record", so the demo isn't just a chat box — it is an **instrumented
chat that re-demonstrates the paper's findings on live queries**, feeding T3.16 (figures) and T3.17
(narrative). Design first, build second.

---

## Master table — measure / purpose / design, in narrative order (CONFIRMED + LOCKED 2026-08-07)

Every value below traces to a committed log (§0.1/§0.4). **Control rule:** everything the demo
(beat 6) captures must surface as a value in some beat — nothing captured that isn't presented.

| # Narrative beat | measure / show (value) | purpose | design / source |
|---|---|---|---|
| **0. HOOK** | delivery **+0.130 vs retriever +0.025 (5×)** + "we caught our own wrong numbers" | grab a skimming reviewer in 10s | one hero figure (delivery lever) from RAG_LAW |
| **1. Painpoint / business** | 3B alone: WixQA **0.163** / MedQuAD 0.821 · demo: **latency + tokens + cloud=$0** | the SME problem + a small local model is viable | baselines from logs · demo captures latency/tokens live (§5) |
| **2. Data cleaning** | 12,428→**10,024** clean, noise→0, dedup · readiness rag **93.4** | rigor from the data stage (reusable tool) | `data/clean/*_report.json` + readiness |
| **3. V1 (original system)** | loop+memory architecture · the numbers V1 *claimed* **25→83→100** | set up the twist (it looked great) | archived `logs/experiments/phase5-6/summary.jsonl` |
| **4. What went wrong (honest core)** | the **real leaked record** (`teaching_feedback`=the answer) · metric ~70% similarity-weighted · corrected real gain self-refine **+0.091** | integrity signal — caught own error | exhibit from `logs/experiments/phase6/gt_memory_store.jsonl` + re-measure from `runs/teaching-loop-medquad` |
| **5. Current work & results** | loop teacher **+0.003**/self-refine **+0.091** · RAG-MedQuAD **−0.005**/7B **−0.069** (tug-of-war) · WixQA **+0.152** (gold **+0.273**/missed +0.004) · dose-response hit 0.55→**0.665**, P(pass\|retrieved)≈**0.400** invariant · delivery coverage 0.412→**0.655**, pass **0.340→0.470**, extraction **88→61%** · Loop+RAG **−0.015** (no compound) · LoRA **−0.292** | full evidence chain → the 3-stage law | all from committed logs via analysis scripts → figures (T3.16) |
| **6. Demo** | compare-mode 3 lanes (no-RAG/RAG · narrow/wide · ±refine) · set selector (gold-retrieved↔missed) · **real before→after answers** | proof it runs + re-demonstrates findings live | T3.15 instrumented demo (§5/5a/5b) → `reports/rag-wixqa/demo-showcase.jsonl` |
| **7. What this demonstrates** | honest eval · caught own leakage · scope discipline · mechanistic reasoning · **347 tests + reproduce-from-clone** | the hire signal | ADR-034 (reproducible) + test count |

**Two honesty guards locked into the plan:**
- Beats 3–4: the V1 "25→83→100" appears ONLY as "claimed, then shown false" — never on the same
  axis as V2 (different units: similarity+leakage vs blind correctness). See §5c.
- Beat 5: WixQA headline is 3-seed with CI, but **Loop+RAG (−0.015) is single-seed/subset — label it
  "directional"** wherever shown.

---

## 1. Objective & painpoint (the *why* — narrative beat 1)
- SMEs / individuals need domain AI but can't afford big models or cloud, and can't send private
  data out. They need a **small model that runs on ordinary hardware, deep in ONE domain**, for Q&A.
- Original bet: use a **big-model teacher loop + memory** to teach a small model, so at deployment
  only the small model is needed. Medical chosen: correctness matters, not hyper-niche.

## 2. Principles / method (the *how* — the discipline that makes it credible)
- **§0.1 honesty** (every number → a log), **§0.2 no GT leakage** (the flaw that broke V1),
  **§0.3 reproducible**, **§0.4 evidence-backed**.
- **Config-driven six-slot system** — swap model / RAG / memory / prompt / judge by YAML, no code edits.
- **Two-testbed design** — MedQuAD (tests the *model*; saturated) vs WixQA (tests *RAG*; real gap).
- **Measure offline before spending** — hit-rate@k, answer-coverage@budget predicted end-to-end with 0 LLM calls.
- **Separate correctness from reference-similarity** — never merge (the V1 mistake).

## 3. The experiment arc → what measured → what we got (the evidence chain)
| # | Experiment | Metric measured | Result (with source) |
|---|---|---|---|
| V1 | original loop + memory | hybrid similarity "pass-rate" | "25→83→100" — **an artefact** of GT leakage + similarity metric (retired, ADR-024) |
| Track A | 4-arm loop ablation (MedQuAD) | correctness pass@≥4, C−B / B−A + CI | teacher **+0.003** (nothing); self-refine **+0.091** (real) |
| RAG-MedQuAD | 3B/7B ± RAG | pass@≥4 delta + CI, tug-of-war split | 3B **−0.005** (null), 7B **−0.069** (hurts); fixed 37 / broke 39 |
| Fair-tests | aspect-rerank, 24× corpus, prompt | pass@≥4 | all fail → null is **structural** (ADR-029) |
| WixQA | 3B ± RAG | pass@≥3, hit-rate, gold-split | **+0.152**; gold-retrieved **+0.273** / missed +0.004; hit-rate **0.55** |
| Dose-response | retriever ladder | offline hit-rate@k → e2e pass | retrieval is the bottleneck; P(pass\|retrieved)≈**0.400** invariant; hit 0.55→**0.665** |
| Delivery | grounding window | in-context answer-coverage → pass | coverage 0.412→**0.655**; pass **0.340→0.470 (+0.130)**; extraction **88%→61%** |
| Loop+RAG | self-refine + RAG | pass@≥3, ref-coverage, extraction | **does NOT compound** (−0.015); oracle 0.609 vs blind-gate 0.571 |
| LoRA | QLoRA gold-SFT | pass@≥4 delta + CI | **−0.292** (style transfer backfires) |

## 4. The values we present (the portfolio-worthy set → maps to T3.16 figures)
1. **The honesty arc** — V1 "25→83→100" (leakage) vs the real self-refine **+0.091**.
2. **The unified law as a 3-stage pipeline** — retrieval 0.55→0.665 · delivery 0.412→0.655 ·
   extraction 88%→**61%** (the new bottleneck).
3. **The delivery lever** — **+0.130 vs +0.025 (≈5×)**, at zero inference cost. *The single headline.*
4. **Two testbeds** — MedQuAD −0.005 (null) vs WixQA +0.152 (positive): same technique, opposite result.
5. **Dose-response** — hit-rate → pass toward the **0.409** anchor.
6. **The tug-of-war** — every "add more" helps deficient answers, hurts adequate ones (3 replications).
7. **LoRA −0.292** — the honest negative.
8. **The demo** — live proof the small local system runs.

## 5. → What the DEMO (T3.15) must CAPTURE (working backwards from §4)
The demo is a live WixQA RAG chat. To make it *re-demonstrate the findings*, log per query:
- `question`, `answer`
- **retrieval:** retrieved passage ids + **similarity + rank**, and whether a confident hit occurred
- **delivery:** which chunk was grounded on + the **grounding window** used (narrow vs wide)
- **sources shown** to the user (trust; there is no gold at inference)
- **latency + token count** (the SME cost story — a real value to present)
- if self-refine toggle on: **rounds + before/after answer**

**The demo's killer feature (design decision) = a per-query "compare" mode** that runs the SAME
question three ways and shows them side by side:
| lane | shows which finding |
|---|---|
| **no-RAG** vs **+RAG** | the +0.152 knowledge lift, live ("watch RAG fix this answer") |
| **narrow (900)** vs **wide chunk-centred (2400)** grounding | the delivery +0.130 lever, live |
| +RAG vs +RAG+self-refine (optional) | self-refine doesn't compound (honest) |

**A curated showcase set (~6–8 WixQA questions)** picked to include: (a) gold-retrieved → RAG fixes
it; (b) gold-missed → RAG honestly can't; (c) a case where the wide window is what makes it correct.
These become the narrative's live examples (T3.17) and a small captured results file for a figure.

### 5a. Switchable question SETS (user request) — the mechanism made visible
The demo has a **set selector** so a viewer flips between:
- **gold-retrieved set** (RAG helps, ~+0.27) vs **gold-missed set** (RAG ~0, honest)
- optionally **WixQA (gap) vs a MedQuAD sample (saturated)** — RAG helps on one, not the other
Switching sets and watching the SAME system help here but not there demonstrates the law live: *it
is not "RAG", it is whether retrieval delivered the answer.* This is the single clearest way to show
the root cause.

### 5b. Capture example ANSWERS (user request) — the before→after exhibits
For every showcase question, **persist the actual answers** from each compare-lane —
`{question, no_rag_answer, rag_answer, narrow_answer, wide_answer, refine_before/after, judge_scores}`
— to a small tracked file (`reports/rag-wixqa/demo-showcase.jsonl` or similar). These concrete
"went from wrong → right when the answer text reached the prompt" pairs are the most persuasive
exhibits in the narrative (T3.17), and a figure can be built from them.

### 5c. The V1 → V2 before/after (user request) — do it HONESTLY, not as a scoreboard
The intent (show how the system evolved) is right, but two honesty constraints (senior call):
- **V1 is not live-runnable** — its code was deleted in T2.9 (`git` history only). So there is no
  live "V1 lane". Use the **immutable archived logs** as exhibits instead.
- **Never put "V1 83% vs V2 X%" on one axis** — they measured *different things* (V1 = similarity to
  a reference *with* ground-truth leakage; V2 = blind correctness). Showing them as two bar heights
  would be exactly the misleading optics the rebuild exists to reject (§0.1).
- **The honest, stronger version = a MECHANISM contrast**, shown in the narrative (T3.17), using the
  real archived exhibit: `logs/experiments/phase6/gt_memory_store.jsonl` contains a record whose
  `teaching_feedback` literally *is* the reference answer ("Reference Answer for similar question… Correct
  Answer: …"). Show that record → "this is what V1's 'memory' stored; the model echoed the answer key,
  and the similarity metric rewarded it → that is the fake 100%." Then V2 on the same question: no
  gold at inference, RAG grounds on a KB passage, the model must actually answer. **Before/after =
  leaky-vs-leak-proof method, not score-vs-score.** (Optional demo "V1-flaw mode" may *reconstruct*
  the echo from the archived leaked memory, clearly labelled "reconstructing the V1 leak" — never
  presented as a real V1 run.)

## 6. → What T3.16 (figures) consumes
The §4 value set = the figure list (already in `T3.16`), regenerated from committed logs — PLUS one
optional figure from the demo's own captured log (its live hit-rate / narrow-vs-wide on the showcase
set), tying the demo to the paper.

## 7. → What T3.17 (narrative) consumes
Each narrative beat (P3-C outline) pulls a specific value: beat 4 (what went wrong) → value 1; beat 5
(results) → values 2–7 + figures; beat 6 (demo) → the demo GIF + the compare-mode examples.

---

## Open decision for the hub before building T3.15
- **Confirm the capture list (§5) and the compare-mode** as the demo's core — this is what makes it
  a portfolio piece rather than a toy. Everything T3.15 records should serve a value in §4.
- Confirm the curated showcase set is drawn ONLY from WixQA (KB articles are the legitimate source;
  no gold answer at inference, §0.2).
