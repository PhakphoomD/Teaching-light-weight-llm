# What the V1 notebook said, in its own words

> **Recovered, not written.** `notebooks/experiment.ipynb` was deleted on 2026-08-08 because all 44
> of its code cells import modules that T2.9 removed — it raised `ModuleNotFoundError` on its first
> cell and had been dead for months. But it also held **24 markdown cells of design rationale**, and
> a first audit wrongly reported there was nothing worth keeping. This file is those cells,
> recovered from git commit `b5440a6` and reproduced verbatim, so the reasoning behind the original
> experiments survives its code.
>
> **Read it as evidence, not as findings.** Every result asserted below was later re-measured and
> most did not survive; the corrections are in
> [reports/tables/tab-04-v1-retraction.md](../../reports/tables/tab-04-v1-retraction.md). The value
> here is the *intent* — what each phase was trying to establish, and why the design looked
> reasonable to the person writing it. That is what makes the failure legible rather than merely
> embarrassing.

---

## The phases, as they were designed

### Phase 0 — Warm-up memory pool

> Build a diverse memory pool using the full medical dataset (100 questions). This memory will be
> used as reference in Phase 1 to prove memory-based learning.
>
> **Strategy:** Run all 100 questions with teacher feedback enabled · Enable memory storage to build
> comprehensive pool · Use moderate settings (3 rounds max) · Memory threshold 0.75 to match Medical
> dataset characteristics

### Phase 1 — Proof of learning

> Compare student performance WITH vs WITHOUT memory from Phase 0. Use 20-question subset to
> demonstrate memory-based learning effect.
>
> **Strategy:** Experiment A uses Phase 0 memory · Experiment B has no memory (top_k=0) · Both use
> the same 20 questions · **If memory helps, Experiment A should show higher scores with fewer
> rounds**

*Note the shape of that last sentence: the success criterion is written before the run, but as a
prediction the design is expected to confirm rather than as a test it could fail. The logs show
memory scoring lower than no-memory (0.85 against 0.90) and the write-up reported it the other way
round.*

### Phase 2 — Teacher feedback style comparison

> Compare different teacher feedback strategies to find the most effective teaching approach. All
> experiments use the same questions and memory settings for fair comparison.
>
> **Strategies:** **Principle** — Constitutional AI style, focuses on principles (truthfulness,
> harmlessness) · **Simple (CoT)** — chain-of-thought reasoning, step-by-step analysis · **Orca** —
> detailed explanation with specific guidance based on ground truth
>
> **Goal:** Determine which teacher feedback style helps the student learn most effectively.

*"based on ground truth" is doing a great deal of work in that third bullet. This is the phase that
selected the house prompt style, and the style it selected is the one that shows the teacher the
reference answer.*

### Phase 3 — Hyperparameter tuning

> Fine-tune pass threshold and temperature settings with best feedback style from Phase 2. Use
> shared memory for fair comparison.
>
> **Parameters:** `pass_threshold: {0.75, 0.80, 0.85}` · `student_temperature: {0.0, 0.2}` ·
> `teacher_temperature: {0.2, 0.3}`
>
> **Note:** Uses best feedback style discovered in Phase 2 (expected: orca)

*The search space is stated honestly here — two student temperatures, not the three the write-up
later claimed. And the pass threshold is listed as a tunable parameter alongside temperature, which
is exactly the problem: the metric the result is reported in was itself being tuned.*

### Phase 4 — Domain transfer testing

> Test memory transfer across different medical domains (sources). Each domain gets its own memory
> to test domain-specific learning.
>
> **Domains:** Cancer QA · Diabetes QA · Disease Control · Growth Hormone

*Four domains, named. The write-up later reported results for "Heart/Lung" and "Genetic", which are
not in this list and not in the logs.*

### Phase 5 — Final validation

> Run full dataset with best configuration from previous phases. Compare baseline vs optimized
> system performance.
>
> **Configurations:** Baseline — single-round, no teacher, no memory · Optimized — best settings
> from Phases 1-3 with memory enabled

*This is the comparison that produced the headline. Note that "optimized" bundles teacher, memory,
tuned hyper-parameters and the ORCA prompt into one arm — so the resulting number cannot attribute
the gain to any of them. Splitting that bundle into one-variable-at-a-time arms is what the rebuild
did, and it is how the teacher was found to contribute nothing.*

### Phase 6 — Ground-truth memory injection, "Training via Memory"

> **Concept:** Instead of Fine-tuning the model, we store Ground Truth (Q + Correct Answer) in
> Memory.
> - Similar to an "Open-book Exam" — the Student has correct answers available in Memory
> - No GPU required, no weight updates
> - Knowledge can be added or removed dynamically at any time
>
> **Hypothesis:** If Memory contains Ground Truth, the Student should pass from Round 1.
>
> **Experiments:** P6A — No Memory (Baseline) · P6B — With Ground Truth Memory

> **Phase 6 variant — same questions test (perfect memory match).** Use the same questions that
> exist in Memory (Similarity = 1.0). This proves that with exact Ground Truth available, the
> Student passes from Round 1. Similar to "memorization" but achieved through Memory retrieval
> instead of Fine-tuning.

*This is the single most important cell in the notebook, and it should be read carefully rather
than mocked. The idea is not absurd — retrieval-augmented generation is, in a sense, an open-book
exam, and "no GPU, knowledge is dynamic" is a real advantage. The error is in what the book
contains. An open-book exam where the book is the marked answer script is not an exam. The
hypothesis was confirmed exactly as written — the student did pass from round 1, 100% of the time —
and the confirmation is what should have raised the alarm. A system that scores 100% has usually
found a way to read the answers.*

---

## The summary table the notebook ended on

| Phase | Purpose | Key finding *(as claimed)* |
|---|---|---|
| **Phase 0** | Warm-up memory pool | Created 20 teaching experiences for memory |
| **Phase 1** | Memory vs no memory | Results similar (config not optimized) |
| **Phase 2** | Tune feedback style | Found: `orca` style works best |
| **Phase 3** | Grid search hyperparameters | Found: PT=0.80, ST=0.0, TT=0.3 |
| **Phase 4** | Cross-domain memory | Memory retrieves by domain correctly |
| **Phase 5** | Full validation (100 Q) | **25% → 83%** with Teaching + Memory |
| **Phase 6** | Ground-truth memory | "Training via Memory" — no fine-tune needed |

> ### Key Contribution
> **"Training via Memory"** — a lightweight alternative to fine-tuning: store verified Q&A pairs in
> a vector database · model retrieves similar examples at inference · no GPU, no weight updates,
> knowledge is dynamic

*Worth noticing: the notebook's own Phase 1 row says "results similar", while the published document
turned the same runs into a +5.0-point win for memory. The overstatement entered at the write-up
stage, not at the notebook stage.*

*And the "Key Contribution" is, stripped of the framing, a description of retrieval-augmented
generation — with the reference answers in the corpus. Remove the answers from the corpus and put
real source documents in instead, and it becomes the system the rebuild actually shipped, where it
is worth +0.152 on a domain the model does not know. The instinct was sound; the corpus was not.*

---

## Cost model

> **Model pricing (USD):** Llama 3.3 70B Versatile — $0.59 per 1M input, $0.79 per 1M output ·
> Llama 3.1 8B Instant — $0.05 per 1M input, $0.08 per 1M output
>
> **Exchange rate:** 1 USD = 1.53 AUD

*These rates are the basis of the cost figures in the retired write-up. They are reproduced here
because the token counts alone are not a cost — recomputed spend appears in
[reports/tables/tab-18-what-it-cost.md](../../reports/tables/tab-18-what-it-cost.md).*

> **Projection analysis: scaling to 1,000 questions.** Based on our experimental results, this
> section projects the expected performance, token usage and costs when scaling to 1,000 medical
> questions.

*The projection extrapolated the 83% and the 100% forward. Both were later retracted, so the
projection has no surviving basis and is not reproduced.*

---

## What was in the code cells, and why none of it was kept

44 code cells: helper functions for config/JSONL/paths, dataset loading and sampling, an experiment
runner, one driver per phase, and matplotlib blocks for the per-phase charts. All of it imports
`simplified_teaching_loop`, `src.simplified.teacher_feedback` or `src.utils.prompt_loader` — three
modules deleted in T2.9 — so the notebook could not run. Its charting job is now done by
`scripts/make_figures.py`, which regenerates every figure from committed logs and is covered by
tests that compare each drawn value against what the documents publish.
