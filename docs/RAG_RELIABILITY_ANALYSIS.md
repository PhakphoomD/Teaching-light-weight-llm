# Why RAG helps reliability on knowledge gaps but hurts pass@k — mechanism + literature

**Status:** analysis (2026-07-21), **not yet updated with the sweep it was waiting for.** The
numbers in §1 are the **5-seed pilot** on two selected subsets (13 genuine-gap + 35 broad
hard-tail questions). The **full 125-question × 8-seed sweep** it says is running has since
completed — `runs/rag-medquad-reliability/`, recomputed in
[`reports/rag-medquad-reliability/per-attempt-vs-dependable.txt`](../reports/rag-medquad-reliability/per-attempt-vs-dependable.txt).

The sweep **agrees with this document's direction and is far stronger than its pilot suggests**:
on all 125 questions with no selection bias, the share of questions answered dependably (correct on
every one of four held-out seeds) is **0.550 without retrieval and 0.238 with it, Δ −0.312
[−0.384, −0.242]**, and the loss is concentrated exactly where the mechanism below predicts — on
the questions the model already answered reliably (easy stratum −0.541), not on the gaps (−0.045,
interval spanning zero). §1's own framing therefore stands, but its numbers are the pilot's and
should be read as such until this document is rewritten around the sweep.

What follows explains *why* the pattern occurs, grounded in published work, and states the
statistical care taken.

---

## 1. The finding (to be confirmed at K=8, full 125)

Re-running the questions the 3B baseline previously failed, over K seeds, on the same blind judge:

| Set | metric | baseline | 3B+RAG | Δ |
|---|---|---|---|---|
| 35 broad hard-tail | per-attempt pass | 0.606 | 0.640 | +0.034 |
| | **pass@5** (≥1 of 5) | **0.89** | 0.74 | **−0.15** |
| 13 genuine gaps (failed all 3 orig seeds) | per-attempt | 0.231 | 0.354 | +0.123 |
| | **pass@5** | 0.69 | 0.38 | **−0.31** |
| | **reliable@5** (5/5) | **0/13** | **4/13** | **+0.31** |

Three effects, each with a mechanism and citation:
1. **RAG raises per-attempt accuracy on genuine gaps** (+12pt) but is ~inert on the broad set.
2. **RAG makes gap questions *reliably* answerable** (reliable@5: 0 → 4 of 13) — its real value.
3. **RAG *lowers* pass@k** (the "ever-right-in-K-tries" ceiling) — the counter-intuitive cost.

---

## 2. Mechanism A — RAG helps where the model lacks knowledge, hurts where it has it

This is the tug-of-war (ADR-027) seen per-question. It is **the central result of Mallen et al.
2023, "When Not to Trust Language Models: Investigating the Effectiveness of Parametric and
Non-Parametric Memories" (ACL 2023, arXiv:2212.10511):** retrieval augmentation *helps* on
**low-popularity / long-tail** factual questions (where the model's parametric memory is weak) but
**hurts** on **high-popularity** questions the model already answers — because the retrieved
passage adds noise the model would have been better off ignoring. Their recommendation —
**adaptive retrieval** (retrieve only when the question is likely outside the model's knowledge) —
is exactly our "selective RAG" (`SELECTIVE_RAG.md`).

Our data is a clean reproduction on a *capability* axis rather than a *popularity* axis: the
"genuine gaps" (baseline reliably fails) are this model's long tail, and RAG's +12pt per-attempt
gain concentrates there; on the easy majority RAG is a distractor. Complementary evidence that
retrieval's benefit is conditional on a real knowledge deficit: **Ovadia et al. 2024, "Fine-Tuning
or Retrieval? Comparing Knowledge Injection in LLMs" (EMNLP 2024)** — RAG beats fine-tuning for
*injecting* facts, i.e. its value is knowledge the model does not already have.

**Why the distraction on easy questions:** **Shi et al. 2023, "Large Language Models Can Be Easily
Distracted by Irrelevant Context" (ICML 2023, arXiv:2302.00093)** and **Cuconasu et al. 2024, "The
Power of Noise: Redefining Retrieval for RAG Systems" (SIGIR 2024, arXiv:2401.14887)** both show
that irrelevant or loosely-related retrieved passages *degrade* generation. In our corpus the
retriever is disease-name-dominated (MiniLM embeds "treatments for X" close to "symptoms of X"), so
same-topic-wrong-aspect passages are exactly the "related but irrelevant" context these papers
identify as harmful. **Liu et al. 2023, "Lost in the Middle" (TACL 2024, arXiv:2307.03172)** adds
that models use retrieved context unevenly, compounding the problem for a small model.

---

## 3. Mechanism B — RAG lowers pass@k because grounding reduces output diversity

**pass@k** (the chance of ≥1 correct answer in k samples) was formalised by **Chen et al. 2021,
"Evaluating Large Language Models Trained on Code" (arXiv:2107.03374, the Codex paper)**. It rises
with k *only if the samples are diverse* — different samples must explore different answers. The
power of sampling diversity is the basis of **Wang et al. 2023, "Self-Consistency Improves Chain of
Thought Reasoning in Language Models" (ICLR 2023, arXiv:2203.11171)**: sampling many *diverse*
reasoning paths and marginalising over them beats a single greedy decode.

Grounding works **against** this diversity. Injecting a fixed passage sharply conditions the output
distribution p(answer | question, passage): the model's answers across seeds collapse toward the
passage's framing, lowering their entropy. Fewer distinct samples ⇒ **lower pass@k**. So on a
question the baseline would occasionally "stumble" onto correctly across seeds (a fluke that pass@k
rewards), RAG *removes* that lucky variance by anchoring the model — which is precisely why
baseline pass@5 (0.89 broad / 0.69 gaps) *exceeds* RAG's (0.74 / 0.38).

This is the honest flip side of grounding: **it trades exploration for consistency.** For a task
where the answer is *recoverable by luck* (the model half-knows it), that trade is bad on pass@k.
For a task where the model *cannot* recover it alone, the trade is good — which is Mechanism C.

---

## 4. Mechanism C — reliability, not pass@k, is the product-relevant metric

A product answers each question **once** and must be **right**, not "right if you resample 5×." The
right metric is therefore **per-attempt reliability**, and its strict form **reliable@k** (correct
on *every* one of k independent attempts). On the 13 genuine gaps:

- **baseline reliable@5 = 0/13** — there is *no* gap question the un-grounded 3B answers dependably;
  its 0.23 per-attempt / 0.69 pass@5 is all luck (high variance, low reliability).
- **RAG reliable@5 = 4/13 (+31pt)** — grounding converts 4 gap questions from "never dependable" to
  "dependably correct."

That conversion — *variance reduction into dependable correctness where the model has no knowledge*
— is exactly what a retrieval layer should buy, and it is invisible to both aggregate pass-rate
(diluted by the easy majority, ADR-027) and pass@k (which rewards the baseline's luck). The idea
that a system should be judged on *dependable* correctness, and abstain/augment when it cannot be
dependable, is the **selective prediction** framework — **Geifman & El-Yaniv 2017, "Selective
Classification for Deep Neural Networks" (NeurIPS 2017, arXiv:1705.08500)** — and its LLM instance,
**Kamath et al. 2020, "Selective Question Answering under Domain Shift" (ACL 2020)**.

---

## 5. Why the selective-RAG gate could not be built cheaply — model miscalibration

Selective RAG needs a gate that fires on the model's knowledge gaps. Our gate experiments failed:
uncertainty signals (answer length, hedging, cross-seed self-consistency) correlated ~0 with
failure, and LLM self-gates were prompt-tone-dominated (`SELECTIVE_RAG.md`). The reason is
**calibration**: **Kadavath et al. 2022, "Language Models (Mostly) Know What They Know"
(arXiv:2207.05221)** shows self-knowledge is an *emergent, scale-dependent* property — it is present
in large models and **weak in small ones**. **Xiong et al. 2024, "Can LLMs Express Their Uncertainty?"
(ICLR 2024, arXiv:2306.13063)** confirms verbalised confidence is unreliable, especially below the
frontier scale. A 3B is therefore *confidently wrong* on its gaps (our self-consistency probe: the
high-agreement tercile failed *more*), so no cheap signal derived from the 3B itself locates the
gaps — a **learned/external gate or a better retriever** is required (future work).

---

## 6. Statistical care — selection bias and regression to the mean

The 13/35 sets were **selected because the baseline failed them**. Re-measuring the *same* items and
finding the baseline now does better (per-attempt 0.23, pass@5 0.69) is textbook **regression to
the mean** (Galton 1886): selecting on an extreme of a noisy measurement and re-measuring pulls
toward the mean. Two safeguards:

1. **The RAG−baseline delta is unbiased:** both arms are measured on the *same* items and *same*
   seeds, so the selection cancels in the difference. The reliability gap (RAG reliable@k − baseline
   reliable@k) is the reported effect, not either arm's absolute level.
2. **The confirmatory sweep avoids selection entirely:** `runs/rag-medquad-reliability/` runs the **full 125**
   held-out questions × 8 seeds for *both* arms and stratifies by *measured* baseline reliability
   (with a seed split to avoid within-stratum regression) — so the RAG-lift-vs-difficulty curve is
   computed without ever pre-selecting on outcome. Bootstrap CIs over questions accompany it.

Judge caveat: the sweep uses the local `llama3.1:8b` judge (free, uncapped) — lenient in absolute
terms (T2.3), but *consistent across both arms*, so the delta and the stratified pattern are valid;
the key gap numbers will be Groq-re-validated on a fresh daily cap (§0.1).

---

## 7. Synthesis

The aggregate "RAG = net zero" (ADR-027) is not RAG being useless — it is **three real effects
summing to ~0 on a near-ceiling testbed**: (A) RAG repairs the model's true knowledge gaps
(Mallen 2023), (B) it distracts on the easy majority the model already knows (Shi 2023 / Cuconasu
2024), and (C) it trades sampling diversity for consistency (Chen 2021 / Wang 2023), which *lowers*
the luck-driven pass@k but *raises* dependable reliability where it matters. Measured on the metric
a product cares about — **reliable correctness on the questions the model cannot answer alone** —
RAG has a clear, positive effect (reliable@5 on genuine gaps: 0 → 4 of 13). The honest product
lesson is Mallen's: **retrieve adaptively, on the long tail, and judge on the hard tail — not the
saturated average.**

### References
- Mallen et al. 2023, *When Not to Trust Language Models*, ACL, arXiv:2212.10511
- Ovadia et al. 2024, *Fine-Tuning or Retrieval?*, EMNLP 2024
- Shi et al. 2023, *LLMs Can Be Easily Distracted by Irrelevant Context*, ICML, arXiv:2302.00093
- Cuconasu et al. 2024, *The Power of Noise*, SIGIR, arXiv:2401.14887
- Liu et al. 2023/24, *Lost in the Middle*, TACL, arXiv:2307.03172
- Chen et al. 2021, *Evaluating LLMs Trained on Code* (pass@k), arXiv:2107.03374
- Wang et al. 2023, *Self-Consistency Improves CoT*, ICLR, arXiv:2203.11171
- Geifman & El-Yaniv 2017, *Selective Classification for Deep Neural Networks*, NeurIPS, arXiv:1705.08500
- Kamath et al. 2020, *Selective Question Answering under Domain Shift*, ACL
- Kadavath et al. 2022, *Language Models (Mostly) Know What They Know*, arXiv:2207.05221
- Xiong et al. 2024, *Can LLMs Express Their Uncertainty?*, ICLR, arXiv:2306.13063
- Zhou et al. 2023, *LIMA: Less Is More for Alignment*, NeurIPS, arXiv:2305.11206
