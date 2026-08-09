# P3-E Capstone Plan (v2) — T3.14 (Loop+RAG) + T3.12 (RAG-Law write-up)

> **Amendment, 2026-08-09 — this document is not purely pre-run, and the reader should know which
> parts are which.**
>
> Written before the runs: §1–§5 and §7, including the predictions in §5 (two of which came out
> wrong, published as wrong in [Table 16](../../reports/tables/tab-16-predictions-vs-outcomes.md)),
> and **§6, the decision rules — which fired and stopped the three-seed run.**
>
> Appended after the corresponding step ran, and labelled as such where it appears: the Stage-1
> offline ladder result under §3, and the Stage-2 pilot verdict. Their headings carry their own run
> dates.
>
> Nothing was removed to tidy this up. A plan that gets edited after the result is worth less than
> one that says where it was edited.

**Status:** planning, revised 2026-07-25 after a pre-run review · **Owners:** ops + qa (T3.14),
qa + main thread (T3.12) · **Supplements** `T3.14-loop-rag-capstone.md` / `T3.12-rag-law-writeup.md`.
Every number below traces to a run log or ADR (§0.1/§0.4). **v2 supersedes v1** — v1's plan ran
self-refine first; a pre-run diagnostic found that would have tested it under a broken premise (§2).

---

## 1. Established evidence (the baseline this builds on)

| finding | number (95% CI) | source |
|---|---|---|
| Teacher loop adds nothing | C−B = +0.003 [−0.021, +0.029], p=1.00 | ADR-024 |
| Self-refine is the surviving loop leg (MedQuAD, ≥4) | B−A = +0.091 [+0.051, +0.133] | ADR-024 |
| MedQuAD RAG null (no gap to fill) | −0.005 [−0.067, +0.056] | ADR-027 |
| LoRA gold-SFT hurts | −0.292 [−0.360, −0.224] | ADR-028 |
| WixQA RAG positive, 3 seeds | +0.152 [+0.090, +0.213], p=5e-11 | T3.9 |
| Retriever ladder winner | `bge_chunk` hit@3 0.665 (+11.5pt) | T3.10 |
| **Dose-response (final, 600/600)** | hit 0→0.55→0.665 ⇒ pass 0.163→0.315→**0.340** (pred 0.337) | T3.11 |
| **Gold-split, retriever-invariant** | retrieved **0.400 / 0.411**, missed 0.211 / 0.199 | T3.9 / T3.11 |

**Bottleneck #1 (proven):** retrieval quality. **Bottleneck #2 (the open question):** even when the
gold article is retrieved, pass caps at ~0.41 and pass@≥4 ≈ 0.01. T3.14 must explain *why*.

---

## 2. Pre-run diagnostic — three findings that reshaped this plan

Computed offline from existing logs (`runs_wixqa/rag_bge_chunk__seed*.jsonl`,
`retrieval_log_bge_chunk.jsonl`, `data/wixqa/kb_corpus.jsonl`); zero LLM calls.

**F1 — The failure mode is fact *selection*, not answer length.** On gold-retrieved (n=399), student
answers median **153 words** vs expert reference median **125 words** — the model already writes *more*
than the reference and is still judged incomplete. Length does not separate scores (score 1/2/3 all
median ~154–160 words; the four score-4 answers are the *shortest*, median 48). **Implication:**
"write more" (self-refine's usual effect) is unlikely to help, and 41.6% of answers already sit near
the 256-token ceiling, so appended detail would be truncated. A refine step must **rewrite within
budget**, not append.

**F2 — We truncate the answer out of the prompt ourselves (the big one).** Grounding shows only the
**first 900 chars** of each article, but gold articles have median **3,555 chars** — **92.5% exceed the
cap**, and the student sees a median **25.3%** of the gold article. Measured on answer content-words:
the **full** gold article covers **72%** of the expert answer, but **what we show covers only 36%** —
we discard **31 points** of answer coverage, and **65% of gold-retrieved questions lose >20 points**.
**Implication:** "gold retrieved" ≠ "answer in context." Testing self-refine first would ask the model
to add facts that were never in its prompt — a null would be uninterpretable (confounded).

**F2b — A design mismatch makes F2 worse and is nearly free to fix.** `bge_chunk` retrieves at
**chunk** granularity — we know exactly which 180-word passage matched — but we then ground on the
**article head** (chars 0–900), discarding the retriever's own localisation. If the matching chunk sits
mid-article, we show the student a part of the article that is *not* the part that matched.

**F3 — pass@≥4 is a near-unreachable bar here, so it is a weak primary metric.** The judge's 4 =
"all key facts from the reference present." But the full gold article covers only ~72% of the
reference's content — so ~28% is unattainable **even with the entire article in context**. With a
floor of 0.010 and a hard ceiling, pass@≥4 has very little statistical power. It stays as a directional
secondary; §4 adds a continuous completeness metric with real power.

**Ambiguity that must be resolved by experiment, not assertion.** Bucketing gold-retrieved replicates
by shown-coverage is *suggestive but confounded*: top tercile (66% coverage) pass@≥3 = **0.511** vs
bottom tercile (21%) = **0.353**, yet the overall Pearson r(coverage, score) = **+0.025** ≈ 0 and mean
score barely moves (2.04→2.21). High-coverage questions are plausibly also *easier* (short reference).
**Therefore we cannot claim truncation causes the ceiling from observational data — it requires a
paired interventional test** (same questions, wider grounding), which is exactly Stage 1 below.

---

## 3. Revised structure: T3.14 in two gated stages

The ~0.41 ceiling has three candidate causes. They must be separated in the right order, cheapest and
most-confounding first:

| candidate cause | test | stage |
|---|---|---|
| (a) the answer isn't in the prompt (truncation/localisation) | widen + relocate grounding, same questions | **Stage 1** |
| (b) the 3B can't assemble a complete answer from context | self-refine on top of repaired grounding | **Stage 2** |
| (c) the judge bar is unattainable (F3) | continuous coverage metric + PASS≥3 headline | built into §4 |

Running Stage 2 before Stage 1 is the v1 error: a self-refine null would be attributable to (a), not (b).

### Stage 1 — Grounding repair (prerequisite; resolves the confound)
**Change exactly one thing vs T3.11:** what text from the retrieved articles is placed in the prompt.
Everything else fixed (retriever `bge_chunk`, top-k 3, student, judge, bars, seeds).

Variants (offline-rankable first, see §4):
- **G1 `head900`** — current T3.11 behaviour (the control).
- **G2 `chunk-centred`** — ground on the **matched chunk ± 1 neighbour** (uses the retriever's own
  localisation; fixes F2b) at a comparable char budget.
- **G3 `wide`** — raise the per-article budget (≈2,400 chars ⇒ ~3× coverage) — direct test of F2.

**Cheap gate before any LLM call:** compute **answer-coverage@budget** (fraction of the reference
answer's content words present in the grounding block) offline — the exact analogue of T3.10's offline
hit-rate ladder. *Honesty note:* the reference answer is used **only by the analyst to score coverage
offline**, never at runtime to select content — the same legitimate status as using gold article-ids to
score hit-rate (§0.2 preserved).

#### Stage-1 offline result (RUN 2026-07-25, `scripts/wixqa/build_grounding_ladder.py`, 0 LLM calls)

2×2 factorial over the 200 questions; coverage = fraction of the expert answer's content words present
in the **gold article's** grounding text (block-level coverage in `grounding_table.json`):

| variant | answer-coverage | Δ vs T3.11 | prompt size |
|---|---|---|---|
| `head900` (= T3.11 control) | 0.412 | — | 2,640 chars |
| `chunk900` | 0.482 | **+0.071** | 2,818 chars (**+7% cost**) |
| `head2400` | 0.612 | +0.201 | 5,830 chars |
| **`chunk2400`** | **0.655** | **+0.244** | 6,175 chars |
| *ceiling (full gold article)* | *0.726* | | |

**Both levers are real and separable:** budget dominates (+0.201), and **chunk-centring adds +0.071 at
essentially no extra cost** (+7% prompt) — confirming F2b, the retriever's localisation was being
discarded. `chunk2400` reaches **90% of the achievable ceiling**.

→ **GATE: PASSED** (target ≥0.55; `chunk2400` = 0.655, `head2400` = 0.612). **`chunk2400` advances**
to the e2e pilot; `chunk900` is retained as the cheap "free-lunch" candidate for the product
recommendation if the wide variant proves too costly or distracting.

**Context-truncation safety check (done before any e2e run):** the largest variant is ~6.2k chars =
**1,323 tokens**, and a needle-at-prompt-start test confirmed Ollama processes it **without truncation**
under the default context — so `num_ctx` is left unchanged from T3.11 (no new variable).

#### Stage-1 e2e PILOT result (RUN 2026-08-06; `chunk2400` vs `head900`, seed 42, gold-retrieved n=133, all judged)

Paired on the same 133 questions; retrieval reused from T3.11 so the grounding window is provably the
only change.

| metric | `head900` (control) | `chunk2400` | delta |
|---|---|---|---|
| **reference-coverage** (continuous, judge-free) | 0.385 | **0.414** | **+0.029 [+0.005, +0.053] — CI excludes 0** |
| **pass@≥3** | 0.421 | **0.511** | **+0.090 [−0.008, +0.188]**, McNemar p=0.096 (fixed 28 / broke 16) |
| pass@≥4 | 0.015 | 0.015 | +0.000 — **flat, as F3 predicted** |
| mean judge score | 2.13 | 2.31 | +0.18 |
| catastrophe rate (≤1) | 0.241 | **0.165** | −0.076 |
| answer length | 147 w | 141 w | −6 w (not "just writing more") |
| **extraction ratio** (answer-cov ÷ context-cov) | **93%** | **63%** | −30pt |

**Reading (three findings):**
1. **The truncation defect was real and partly binding.** Repairing it moved the continuous metric
   **significantly** (+0.029, CI excludes 0) and pass@≥3 by **+9pt** directionally (p=0.096 at a single
   seed — the 3-seed run is needed for significance). Fewer catastrophes, and *not* by writing more.
2. **The model cannot exploit most of the extra context.** We raised context coverage by **+0.244** and
   only **+0.029** reached the answer — extraction efficiency falls **93% → 63%**. At `head900` the
   model used ~all it was given (context was binding); at `chunk2400` **the model is now binding.**
   This is the quantitative statement of bottleneck #2.
3. **F3 confirmed:** pass@≥4 is 0.015 in *both* arms — structurally unreachable, so it cannot serve as
   a primary metric. The continuous coverage metric is what carries statistical power here.

→ **PILOT VERDICT: GO** to the full 3-seed Stage-1 run (200 questions × 3 seeds, unbiased aggregate).
The ~37% of available answer-content the model leaves unused is also **precisely the target Stage 2
(self-refine) would attack** — so Stage 2 becomes *more* motivated, not less.

### Stage 2 — Self-refine on top of the best grounding (the actual T3.14 question)
Self-Refine (Madaan et al., NeurIPS 2023, arXiv:2303.17651) as **arm B**
(`src/tlw/loop/strategies.py:120`), teacher permanently dead (ADR-024). Three method requirements:

1. **Grounding must persist across rounds** (implementation blocker): arm B's `refine` prompt
   (`strategies.py:154`) passes only `{question, previous_answer, feedback}` — it **drops the passages
   after round 1**. A `grounded_refine` variant is required, or the model refines from memory and
   re-opens the knowledge gap RAG just closed. Verify by inspecting a real round-2 prompt.
2. **No gold in the control flow (§0.2).** WixQA's only usable judge is reference-comparing, so it must
   **not** gate iteration (that would let gold-proximity decide how many rounds a question gets).
   **Primary policy: fixed rounds (1 initial + 2 refine), judged once offline.** Also log a **blind**
   self-assessment ("is this complete? YES/NO") each round so the early-stop policy can be evaluated
   **offline from the same generation run** — both policies, one run, no extra cost.
3. **Rewrite, don't append** (from F1): critique = *"list concrete facts in the REFERENCE CONTEXT the
   draft omits or states vaguely"*; refine = *"rewrite the answer within the same length, adding those
   facts and keeping what is already correct."* Both steps see the retrieved context — this is
   **grounded** refinement (Reflexion-style external signal, Shinn et al., arXiv:2303.11366), not the
   *intrinsic* self-correction Huang et al. (ICLR 2024, arXiv:2310.01798) showed to be unreliable —
   which is precisely why requirement (1) is non-negotiable.

**Efficiency:** Stage 2's round-1 is identical to Stage 1's winning run, so round-1 answers/judgments
are **reused**; only refine rounds are generated and only final answers are judged.

---

## 4. Measurement

- **Headline:** pass@≥3 (ADR-030 bar), **overall and split by gold-retrieved / gold-missed**, paired by
  (question, seed) with the pre-registered `src/tlw/analysis` (paired cluster bootstrap 95% CI + exact
  McNemar).
- **Completeness (new, and the fix for F3):** **reference-coverage of the answer** = fraction of the
  expert answer's content words present in the student's answer. Continuous, judge-free, free to
  compute, and not floored at 0.01 — it has the statistical power pass@≥4 lacks. Report mean ± CI.
  pass@≥4 is retained as a directional secondary only.
- **Diagnostics:** answer-coverage@budget (Stage-1 gate), faithfulness/groundedness (RAGAS-style,
  Es et al., arXiv:2309.15217) to detect drift during refinement, score-0/1 catastrophe rate, per-seed
  spread, and mean judge score (finer-grained than a binary bar).
- **Tooling:** `scripts/wixqa/build_grounding_ladder.py` (Stage-1 offline coverage), extend
  `wixqa_run3seed_retriever.py` with a `--grounding` mode, `scripts/wixqa/run_self_refine.py` (Stage 2),
  reuse `wixqa_judge.py` (resumable/TPD-graceful) and `wixqa_dose_analyze.py` (new rows).

---

## 5. Predictions (pre-registered, with reasoning and honest uncertainty)

**Stage 1 — grounding repair.** Offline, coverage should rise substantially (36% → 55–70%) because
the full article holds 72% and we currently show a quarter of it. **End-to-end effect is genuinely
uncertain and I expect it to be modest:** the observational correlation is ~0 (§2), the top-tercile
+16pt is confounded by difficulty, and more context also adds distraction — the tug-of-war ADR-027
measured on MedQuAD, where extra passages *hurt* a 3B.

| metric (gold-retrieved) | now | predicted | range |
|---|---|---|---|
| pass@≥3 | 0.411 | **0.45** | 0.38–0.52 (a *decrease* is possible via distraction) |
| pass@≥4 | 0.010 | 0.03 | 0.01–0.06 |
| aggregate pass@≥3 | 0.340 | **0.36** | 0.32–0.41 |

**Stage 2 — self-refine on repaired grounding.** F1 lowers v1's optimism materially: the model already
writes more than the reference, so the win must come from *substituting better facts*, not adding text.

| metric (gold-retrieved) | Stage-1 base | predicted | range |
|---|---|---|---|
| pass@≥3 | ~0.45 | **0.47** | 0.42–0.53 |
| pass@≥4 | ~0.03 | **0.06** | 0.02–0.11 |
| reference-coverage (mean) | ~0.45 | **+0.04** | +0.00 to +0.09 |

**Expected combined end state:** aggregate pass@≥3 **0.34 → ~0.38** (0.32–0.44), pass@≥4 **0.01 →
~0.04** (0.01–0.08). **Statistical expectation, stated up front:** with 600 paired replicates a ~+4pt
aggregate move is **borderline-to-not significant** — as in T3.11, the interpretable signals will be
(i) the **gold-retrieved subset** (n≈400), (ii) the **continuous coverage metric**, and (iii) the
**mechanism pattern** (effects concentrated where gold is retrieved, absent where it is missed).

**Probability of a null/negative overall: ~35–45%** (raised from v1's 25–35% because of F1). A null is
a real result: combined with F2/F3 it yields the paper-grade conclusion — *retrieval is necessary but
not sufficient; below a model-capability floor, neither wider context nor iteration produces
expert-complete answers, so the honest product target is "correct" (PASS≥3), not "expert-complete."*

---

## 6. Pre-registered decision rules (so the result cannot be rationalised after the fact)

| observation | conclusion | product recommendation |
|---|---|---|
| Stage-1 coverage ↑ **and** gold-retrieved pass@≥3 ↑ ≥ +5pt, CI excludes 0 | ceiling was partly **our truncation**, not model capability | fix grounding budget/localisation — cheap, no runtime cost |
| Stage-1 coverage ↑ but pass flat/down | more context ≠ better answers (distraction, ADR-027 replicated on WixQA) | keep tight grounding; the ceiling is the model |
| Stage-2 gold-retrieved pass@≥4 ↑ ≥ +5pt with CI excluding 0 | RAG + self-refine **compound** (knowledge + completeness) | ship self-refine despite ~3× inference cost |
| Stage-2 lift < +2pt or CI spans 0 | self-refine does **not** compound here | ship single-pass RAG; spend the compute on a bigger base model |

---

## 7. Cost, sequence, and risk

| step | compute | Groq judge calls | wall-clock driver |
|---|---|---|---|
| 1. Stage-1 offline coverage ladder | seconds, local | **0** | — |
| 2. Stage-1 pilot (best variant, n=50, seed 42) | ~50 local gens | ~50 | minutes |
| 3. Stage-1 full (3 seeds) *if the pilot holds* | 600 local gens | ~600 | **Groq TPD 500K/day (org-wide) ≈ 1–2 days** |
| 4. Stage-2 pilot (n=50 on gold-retrieved) | ~150 local gens | ~50 | minutes |
| 5. Stage-2 full (3 seeds) *if the pilot holds* | ~1,200 local gens | ~600 | **≈ 1–2 days** |
| 6. T3.12 write-up + T3.13 stale-doc retirement | — | 0 | ~half a day |

**Discipline:** each expensive step is gated by a cheap one (offline metric → pilot → full run) —
the same de-risking that made T3.10/T3.11 efficient. **Known constraints:** the shared Groq daily cap
(use the resumable judge + finalizer pattern) and the shared 8 GB GPU (auto-resume when free; never
disrupt the user's other session).

**Risks:** (i) grounding drops after round 1 → §3 Stage-2 requirement (1), verified on a real prompt;
(ii) over-editing degrades good answers → rewrite-in-budget prompt + the blind-stop policy evaluated
offline; (iii) more context → distraction (ADR-027) → that is a legitimate finding, pre-registered in
§6; (iv) budget/GPU contention → gates + resumable tooling.

---

## 8. T3.12 — Unified write-up (`docs/RAG_LAW.md` + ADR)

**The law, in final form:**
> **RAG helps a small local model iff the retrieved passage actually contains the answer.** The first
> bottleneck is **retrieval quality** (proven by dose-response). The second is **delivery** — whether
> the answer-bearing text actually reaches the prompt, and whether the small model can assemble a
> complete answer from it. Neither is a limitation of the RAG concept.

**Structure (each claim = number + CI + source):** (1) thesis + two-testbed design (MedQuAD tests the
*model*; WixQA tests *RAG* where a gap exists) → (2) loop adds no knowledge, self-refine is the only
surviving leg (ADR-024) → (3) MedQuAD null is structural (ADR-027/029) → (4) WixQA positive +0.152
(T3.9) with the causal gold-split → (5) **dose-response proof** (T3.10/T3.11: hit 0.55→0.665 ⇒ pass
0.315→0.340, prediction within 0.003, P(pass|retrieved) invariant) → (6) **the system**: Stage-1/2
results + the delivery findings F1–F3 → (7) product implications, limitations, `reconcile-numbers`.

**Literature grounding:** Lewis 2020 (2005.11401, RAG) · Ovadia 2024 (2312.05934, RAG>FT for
knowledge) · Zhou/LIMA 2023 (2305.11206, FT teaches style) · Mallen 2023 (2212.10511, long-tail) ·
Cuconasu 2024 (2401.14887, retrieved-context quality decides RAG) · Liu 2024 (2307.03172, position
sensitivity — relevant to F2/F2b) · Madaan 2023 (2303.17651, Self-Refine) · Huang 2024 (2310.01798,
intrinsic self-correction is weak) · Shinn 2023 (2303.11366, Reflexion) · Es 2023 (2309.15217, RAGAS)
· Xiao 2023 (2309.07597, BGE) · Cormack 2009 (RRF) · WixQA (2505.08643).

**Acceptance:** self-contained, readable in <10 min, every number traced to a log, `reconcile-numbers`
passes, ADR logged, and **T3.13** (retire the stale `docs/PROJECT_OVERVIEW_AND_RESULTS.md`, a live
§0.1 violation) completed before any commit.
