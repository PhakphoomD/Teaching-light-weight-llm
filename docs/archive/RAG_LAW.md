> ## 📁 Superseded — kept for the record
>
> **This document has been replaced by [`docs/EXPERIMENT_RESULTS.md`](../EXPERIMENT_RESULTS.md).**
>
> It is not wrong; it is narrower. It was written as a result-first account of one finding — that
> retrieval resolves into retrieval, delivery and extraction — and the project has since needed a
> single record covering the objectives, the decisions behind them, the original system and its
> retraction, and every measurement rather than the headline ones. Keeping both would have meant two
> places for the same numbers to drift apart, which is the failure mode this project exists to
> correct.
>
> Two values below were corrected on 2026-08-08 before archiving: the share of the expert answer's
> content reaching the prompt read **36%** where it should read **41%** (the median had been
> substituted for the mean while the surrounding arithmetic used the mean), and the test count was
> stale. Everything else stands and reconciles against its logs.
>
> Nothing here has been deleted. The correction is part of the honest record.

---

# When does a small local LLM actually get better? — the unified result

**Task T3.12** · Written 2026-08-06 · Every number traces to a committed run log (Constitution §0.1/§0.4).
Read time ≈ 10 minutes.

---

## The one-paragraph version

A small local model (3B) was given the three interventions people usually reach for — an LLM
**teacher in the loop**, **RAG**, and **LoRA fine-tuning** — and each was measured on held-out data
with pre-registered statistics, on a codebase rebuilt so that ground-truth leakage is structurally
impossible. **The teacher added nothing. LoRA on reference answers actively hurt. RAG did nothing on
one testbed and a large amount on another** — and that contradiction turned out to be the real
finding. RAG's value is not a property of RAG; it is a property of *whether the answer-bearing text
reaches the model*. That resolves into a three-stage pipeline — **retrieval → delivery → extraction** —
each with its own measurable bottleneck. The largest single win in the whole project (+13 points) came
not from a better model or a better retriever, but from fixing **how much of the retrieved article was
actually put in the prompt**.

---

## 1. The law

> **RAG helps if and only if the retrieved text actually contains the answer — and the model can use
> it.** The RAG concept is not the variable; *delivery of evidence* is.

Stated as a pipeline, because each stage was measured separately:

| stage | question it answers | metric | measured range | what fixes it |
|---|---|---|---|---|
| **1. Retrieval** | is the answer-bearing document found at all? | hit-rate@k | 0.550 → 0.665 | chunking, stronger encoder |
| **2. Delivery** | does the answer text actually reach the prompt? | answer-coverage in context | 0.412 → 0.655 | wider, chunk-centred grounding window |
| **3. Extraction** | does the model use what it can see? | extraction ratio | 88% → **61%** | *unsolved — the current bottleneck* |

A failure at any stage makes the stages after it irrelevant. This is why the same technique ("RAG")
produced −0.005 in one setting and +0.152 in another.

---

## 2. Evidence chain

Each row is a separate pre-registered experiment. Effects are pass-rate differences with 95% paired
cluster-bootstrap CIs and exact McNemar p-values.

### 2.1 The loop: the teacher adds nothing; self-refinement is the part that worked

MedQuAD (medical QA), 125 held-out questions × 3 seeds × 4 arms, student `qwen2.5:3b`, blind judge.

| arm | pass rate | headline effect | verdict |
|---|---|---|---|
| A — single pass | 0.821 | — | baseline |
| B — self-refinement | 0.912 | **B − A = +0.091** [+0.051, +0.133], p < 0.0001 | ✅ real |
| C — independent teacher | 0.915 | **C − B = +0.003** [−0.021, +0.029], p = 1.00 | ❌ nothing |
| D — teacher sees the reference | 0.940 | *labelled leakage ceiling — not a result* | ⚠️ |

The pre-renovation project had reported this loop as "25% → 83%". The rebuilt measurement shows the
real iterate-gain is **+9 points, and it comes from the model critiquing itself**, not from the
teacher. Arm D is reported only as the ceiling reachable *by cheating*; one D run aborted mid-flight
when the leakage guard caught a genuine 12-token ground-truth echo — the seal working as designed.
→ `docs/TRACK_A_RESULTS.md`, ADR-024

**Consequence:** the teacher-in-the-loop was removed from the product. Knowledge has to come from
somewhere else — which is why RAG was tested next.

### 2.2 RAG on MedQuAD: no effect — and the null is structural

Same held-out protocol, retrieval over the training split.

| pair | effect | verdict |
|---|---|---|
| 3B + RAG − 3B | **−0.005** [−0.067, +0.056], p = 0.91 | no net effect |
| 7B + RAG − 7B | **−0.069** [−0.120, −0.019], p = 0.0004 | **RAG significantly hurts the stronger model** |
| 3B + RAG vs plain 7B | −0.088 [−0.136, −0.043] | retrieval cannot substitute for model size |

The null hides a **tug-of-war**: RAG fixed 37 question-seed pairs and broke 39. The breakages
concentrated on questions the baseline already answered correctly (distraction); the fixes
concentrated on the hardest ones (~38% recovery on the questions that failed in all three seeds).

Three "give RAG a fair shot" objections were then tested and all failed: an **aspect-aware reranker**
(0.760, *worse*), a **24× larger corpus** (9,798 passages → 0.816, still below the 0.864 baseline),
and a **different student prompt** (0.840 vs 0.864, p = 0.58). **The null is structural, not a
tuning artefact:** in a leak-free single-source evaluation the corpus cannot contain the held-out
answer, and same-topic passages act as distractors.
→ `docs/RAG_RESULTS.md`, ADR-027 / ADR-029

### 2.3 RAG on WixQA: +0.152, and the lift is provably the retrieved data

Second testbed chosen deliberately for the opposite property: **WixQA** — 6,221 real Wix help-centre
articles + 200 expert-written QA pairs (arXiv:2505.08643, MIT). The 3B has no parametric knowledge of
a proprietary product, and the knowledge base is the *legitimate* source, so grounding on it is
intended behaviour rather than leakage.

**Precondition check first:** the 3B scored **0.163** without retrieval (versus 0.821 on MedQuAD) —
a real knowledge gap, which is what justified building the index at all.

| | pass@≥3 |
|---|---|
| 3B, no RAG | 0.163 |
| 3B + RAG (top-3) | **0.315** |
| **effect** | **+0.152** [+0.090, +0.213], McNemar p = 5.2e-11 (3 seeds, 600 paired replicates) |

**The causal split — the same run, cut by whether the gold article was actually retrieved:**

| subset | n | baseline | +RAG | effect |
|---|---|---|---|---|
| gold **retrieved** | 110 | 0.127 | **0.400** | **+0.273** |
| gold **missed** | 90 | 0.207 | 0.211 | +0.004 ≈ 0 |

Same model, same prompt, same judge — the *only* difference is whether the retrieved passage
contained the answer. **The lift is the data.**
→ `docs/WIXQA_RESULTS.md`, ADR-030

### 2.4 The dose-response: retrieval quality demonstrated as the bottleneck

A within-run split is suggestive; a dose-response is a demonstration. An **offline** retriever ladder
(7 variants, ranked by hit-rate@k with zero LLM calls) produced a winner, which was then run
end-to-end with **everything except the retriever held fixed**.

| retriever | hit-rate@3 | → pass@≥3 | mixture prediction |
|---|---|---|---|
| none | 0.000 | 0.163 | — |
| MiniLM, whole article | 0.550 | 0.315 | 0.315 (exact) |
| BGE + chunking | 0.665 | 0.340 | 0.337 |

Pass rate rose **monotonically** with hit-rate and matched a mixture model built from the §2.3
conditionals. The mechanism is visible in the invariant: **P(pass | gold retrieved) stayed at
0.400 → 0.411 across both retrievers.** A better retriever changes *how often* the answer is found,
not what it is worth when found.

**Honest limit:** the aggregate difference between the two retrievers is **not statistically
significant** (+0.025 [−0.030, +0.078], p = 0.27) — expected, because it is bounded by the 0.400
ceiling. The proof is the *pattern* (monotonic dose-response + invariant conditional + prediction
match), not the size of a single jump.

Also honest, from the ladder: **BM25 alone was worse** (0.465), **hybrid BM25+dense fusion hurt** the
strong dense retriever (0.605 < 0.665), and a **cross-encoder reranker was a wash at k = 3** (0.640) —
it improves recall@10 but trades away top-3 precision.
→ `docs/WIXQA_RESULTS.md` §Dose-response

### 2.5 Delivery: the biggest lever, and it was hiding in our own prompt code

Before testing the final intervention, an offline audit asked a question that had been assumed away:
*when the gold article is retrieved, is the answer actually in the prompt?*

| | |
|---|---|
| median gold article length | 3,555 chars |
| what the grounding code showed | **first 900 chars** |
| gold articles exceeding the cap | **92.5%** |
| share of the article the model saw | **25%** |
| share of the expert answer's content in the **full** article | **72%** |
| share of the expert answer's content **actually shown** | **41%** | *(mean; an earlier draft quoted the **median** 36% here while the surrounding arithmetic used the mean — corrected 2026-08-08 against reports/rag-wixqa/context-window-coverage.json, where `coverage_gold_mean` = 0.412 and `coverage_gold_median` = 0.362)*

So "gold retrieved" did **not** mean "answer in context" — we were discarding 31 points of answer
coverage in our own prompt builder. Worse, the retriever matched at *chunk* granularity while the
grounding code showed the *article head*, throwing away the retriever's own localisation.

An offline 2×2 ladder (position × budget, zero LLM calls) selected a **chunk-centred 2,400-char
window** (coverage 0.412 → **0.655**, 90% of the achievable ceiling), which was then run end-to-end
with **only the grounding window changed** — retrieval reused verbatim.

| metric | before | after | effect |
|---|---|---|---|
| **pass@≥3 (aggregate)** | 0.340 | **0.470** | **+0.130** [+0.072, +0.188], p = 3.5e-08 |
| gold-retrieved subset | 0.411 | 0.534 | +0.123 |
| gold-missed subset | 0.199 | 0.343 | +0.144 |
| answer length | 152 words | **144 words** | *shorter* |
| **extraction ratio** | 88% | **61%** | −27 pts |

Four things follow:

1. **Delivery outweighed retrieval as a lever: +0.130 versus +0.025**, from a prompt-construction
   change with **no extra inference cost**.
2. **It is not "writing more"** — answers got shorter while covering more of the reference. The gain
   is better fact *selection*.
3. **The 0.400 "payoff when retrieved" was not a model ceiling.** It was invariant across retrievers
   but rose to 0.534 once the answer actually reached the prompt.
4. **Even gold-missed questions improved (+0.144)** — with a 900-char window we were also seeing too
   little of the *other* retrieved articles. "Gold article" is a dataset annotation, not the only
   usable source.

**The new bottleneck is now measured:** extraction ratio fell to **61%**, i.e. the model leaves ~39%
of the answer content that is sitting in its context unused.
→ `docs/WIXQA_RESULTS.md` §Grounding delivery

### 2.6 Loop + RAG: the system, finally run together — and it does not compound

Self-refinement (§2.1) and RAG (§2.3) target different failure modes, and had never been run
together. Two grounded refinement rounds were added on top of the repaired grounding, with the
retrieved context supplied to **both** the critique and the rewrite step of **every** round.

| metric | single-pass | + self-refine | effect |
|---|---|---|---|
| reference-coverage (continuous) | 0.414 | **0.445** | **+0.031** [+0.018, +0.047] ✅ |
| extraction ratio | 63% | 68% | +5 pts |
| **pass@≥3** | 0.571 | 0.556 | **−0.015** [−0.068, +0.038], p = 0.77 |
| mean judge score | 2.35 | 2.35 | 0.00 |

**The mechanism works and the outcome does not.** Refinement pulls significantly more of the
reference's content into the answer — and none of it reaches the judged bar.

**Why — the same tug-of-war, now for iteration:**

| answer's prior score | n | mean change | improved / worsened |
|---|---|---|---|
| 0–1 (wrong) | 22 | **+0.35** | 6 / 0 |
| 2 | 35 | 0.00 | 3 / 3 |
| **3 (already correct)** | **74** | **−0.11** | **0 / 7** |

57% of cases were already adequate, so the gains on weak answers were cancelled by damage to good
ones. This is the same shape as §2.2's RAG tug-of-war.

**Selective application has real headroom — and the small model cannot unlock it:**

| policy | pass@≥3 |
|---|---|
| single-pass | 0.571 |
| always refine | 0.556 |
| **oracle: refine only weak answers** | **0.609 (+0.038)** |
| **implementable: refine when the model says it is incomplete** | 0.571 (**+0.000**) |

The 3B called its own answer "complete" **59%** of the time, including when it was wrong. This
replicates the identical result from selective RAG (oracle +0.099, cheap gates fail). **In both
cases the missing component is a reliable gate, not a better intervention** — consistent with Huang
et al. (ICLR 2024), who show intrinsic self-correction is unreliable without an external signal.
→ `docs/WIXQA_RESULTS.md` §Loop+RAG, ADR-032

### 2.7 LoRA: fine-tuning on reference answers made it worse

QLoRA 4-bit (r = 16, 2 epochs) on 506 (question → reference answer) pairs, evaluated on the same
held-out 125 with the same judge.

**3B + LoRA − 3B = −0.292** [−0.360, −0.224]. The training itself succeeded (loss 1.98 → 0.99, and
the outputs visibly adopt the reference's phrasing) — **the style transfer is exactly the problem**:
answers became 30–45% shorter, and the evaluation rewards completeness. The training objective
(imitate a terse reference) diverged from the evaluation objective (answer completely).
→ `docs/PRODUCT_RESULTS.md`, ADR-028

---

## 3. Two testbeds, on purpose

| | MedQuAD | WixQA |
|---|---|---|
| what it tests | the **model** | **RAG** |
| baseline | 0.821 — near-saturated | 0.163 — real knowledge gap |
| RAG effect | −0.005 (none) | +0.152 |
| what it proves | when a model already knows a domain, no lever helps: loop ≈ 0, RAG ≈ 0, LoRA −0.29 | when it does not, retrieval works — and its value is gated by delivery |

Neither testbed alone supports the law. Together they do: **the same technique, opposite results,
explained by one variable.**

---

## 4. The recurring pattern (three independent replications)

Every "add more" intervention in this project behaved the same way:

| intervention | helps | hurts | net |
|---|---|---|---|
| RAG passages (MedQuAD) | hard questions (+38% recovery) | easy ones (distraction) | ≈ 0 |
| Wider context (WixQA) | most cases | some, via distraction | **+0.130** |
| Self-refinement (WixQA) | weak answers (+0.35) | already-correct ones (−0.11) | ≈ 0 |

**Interventions pay off where the answer is deficient and tax it where it is already adequate.** The
net depends on the mix — which is why a *selective* policy beat an always-on one in both cases where
it was simulated, and why the unsolved problem is the **gate**, not the intervention.

---

## 5. What this means for building the product

1. **Only add RAG where a real knowledge gap exists.** Verify with a no-RAG baseline *before*
   building an index. A high baseline means RAG will not help and may hurt.
2. **Spend the first engineering effort on delivery, not on the retriever.** Getting more of the
   right passage into the prompt was worth 5× a retriever upgrade and costs nothing at inference.
3. **Use the retriever's own localisation.** If retrieval matches a chunk, ground on that chunk —
   not the head of its document (+0.071 coverage for +7% prompt size).
4. **Do not ship always-on self-refinement.** ~3× the inference cost for no measurable gain.
5. **Do not blanket-fine-tune on reference answers.** A strong instruct model is already well
   aligned; naive SFT trades completeness for brevity (−0.292).
6. **Measure offline before spending.** Hit-rate@k and answer-coverage@budget both predicted
   end-to-end behaviour with zero LLM calls, and both prevented expensive dead ends.
7. **Set the target at "correct", not "expert-complete".** The strictest bar was structurally
   unreachable here — even the full source article contains only ~72% of the expert answer's content.

---

## 6. Limitations (stated plainly)

- **Two domains, one model size, one judge family.** All headline numbers use a 3B student and a
  Llama-family reference-comparing (WixQA) or blind (MedQuAD) judge. Different sizes or judges could
  shift magnitudes; the *directions* are supported by within-run splits, which are more robust.
- **§2.6 is a single seed on a labelled subset** (n = 133, gold-retrieved). The 3-seed run was
  deliberately not executed after the pilot showed a null — the pre-registered gate stopping an
  expensive run is the intended behaviour, but it leaves that null directional rather than CI-tight.
- **§2.4's aggregate retriever effect is not significant** (+0.025 [-0.030, +0.078], p = 0.27). The proof rests on the
  dose-response pattern and the invariant conditional, and is described that way throughout.
- **LoRA used 2 seeds**, not 3. Better recipes (mixed general data, fewer epochs, DPO on
  completeness) were not tested — the finding is about *naive gold-SFT*, not about LoRA in principle.
- **Judge validity.** The MedQuAD judge failed a calibration probe at both candidate models; the
  response was to raise the pass bar and keep a *single consistent* judge across arms, so differences
  remain interpretable even where absolute levels are not. The WixQA judge compares against the
  reference — legitimate for a closed domain (only the judge sees the reference; the student never
  does), but it is not a general-purpose correctness oracle.
- **Predictions were wrong twice**, and both were recorded before running: the grounding repair was
  predicted at ~0.36 (actual **0.470**, outside the stated range) and self-refinement at +3 points
  (actual **−1.5**). Both errors came from over-trusting a confounded observational correlation —
  which is precisely why the paired interventional tests were run.

---

## 7. How to verify any number here

Every result recomputes from committed logs:

```bash
# Track A (loop ablation)
python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad

# RAG on MedQuAD
python -m src.tlw.analysis --runs-dir runs/rag-medquad --rag

# WixQA: 3-seed headline, dose-response, grounding, Loop+RAG
python scripts/wixqa/analyze_three_seeds.py
python scripts/wixqa/analyze_dose_response.py
python scripts/wixqa/analyze_grounding.py \
    --control 'runs/rag-wixqa/3-rag-better-retriever/seed*.jsonl' \
    --treat   'runs/rag-wixqa/4-rag-wider-context/seed*.jsonl' \
    --label-control head900 --label-treat chunk2400
```

Test suite: `python -m pytest tests/ -q`. *(The count stated here when this document was archived is not maintained; the live figure is regenerated into `reports/tables/tab-19-methodology-and-integrity.md`.)*

---

## 8. Sources

**Findings** — ADR-024 (loop), ADR-027 (MedQuAD RAG null), ADR-028 (LoRA), ADR-029 (fair-test),
ADR-030 (WixQA positive), ADR-031 (P3-E), ADR-032 (Loop+RAG scope), all in `.claude/rules/decisions.md`.
**Reports** — `TRACK_A_RESULTS.md`, `RAG_RESULTS.md`, `WIXQA_RESULTS.md`, `PRODUCT_RESULTS.md`,
`RAG_RELIABILITY_ANALYSIS.md`.

**Literature the design draws on and, in two cases, tests:**

| work | role here |
|---|---|
| Lewis et al. 2020, *RAG* (arXiv:2005.11401) | the architecture |
| Ovadia et al. 2024, *Fine-Tuning or Retrieval?* (arXiv:2312.05934) | RAG before fine-tuning for knowledge — supported (RAG +0.152 vs LoRA −0.292) |
| Zhou et al. 2023, *LIMA* (arXiv:2305.11206) | fine-tuning teaches style, not knowledge — supported, painfully (§2.7) |
| Cuconasu et al. 2024 (arXiv:2401.14887) | retrieved-context quality decides RAG outcomes — central to §2.5 |
| Liu et al. 2024, *Lost in the Middle* (arXiv:2307.03172) | position within context matters — matches the chunk-centring result |
| Madaan et al. 2023, *Self-Refine* (NeurIPS 2023, arXiv:2303.17651) | the Stage-2 method — **did not transfer to a 3B** (§2.6) |
| Huang et al. 2024, *LLMs Cannot Self-Correct Reasoning Yet* (ICLR 2024, arXiv:2310.01798) | predicts exactly the failure observed: the model cannot judge its own output (59% false "complete") |
| Shinn et al. 2023, *Reflexion* (arXiv:2303.11366) | why grounding was kept in every refinement round |
| Xiao et al. 2023, *BGE* (arXiv:2309.07597) | the winning encoder |
| Es et al. 2023, *RAGAS* (arXiv:2309.15217) | groundedness as a diagnostic, never a pass gate |
| Ben Abacha & Demner-Fushman 2019, *MedQuAD* | testbed 1 |
| Cohen et al. 2025, *WixQA* (arXiv:2505.08643) | testbed 2 |
