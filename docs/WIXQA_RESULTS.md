# WixQA RAG — 3-seed result + retrieval instrument (T3.9, P3-E)

**Task:** T3.9 (`docs/plan/T3.9-wixqa-instrument-3seed.md`) · **Owners:** data-engineer + qa-engineer ·
**Depends on / anchors:** ADR-030 (the single-seed +13pt WixQA positive) · **Status:** FINAL — all
600/600 replicates judged (2026-07-24); numbers below are locked.

This turns ADR-030's **single-seed** WixQA result into a **3-seed result with a confidence interval**, and
builds the **per-question retrieval instrument** (hit-rate harness) that the P3-E dose-response proof needs
(`docs/plan/P3-E-retrieval-proof.md`). It is **variant #1** of the retriever ladder (MiniLM / whole-article).

---

## 1. Headline

**3B + RAG − 3B baseline = +0.152, 95% CI [+0.090, +0.213]** (paired cluster bootstrap over 200 questions,
seeds pooled), **McNemar exact p = 5.2e-11** (b = 143 rag✓/base✗, c = 52 rag✗/base✓; n_pairs = 600).
PASS = judge score ≥ 3 ("correct"), the ADR-030 headline bar.

The ADR-030 point estimate (**+0.130**, single-seed) sits **inside** this CI; the 3-seed mean is slightly
higher. **The +13pt is now a CI-backed claim, not a single point.** Per-seed deltas are tight and all
positive: seed13 **+0.160**, seed42 **+0.130**, seed123 **+0.165**.

| arm | seed 13 | seed 42 | seed 123 | pooled (Wilson 95%) |
|---|---|---|---|---|
| baseline (no RAG) | 0.160 | 0.175 | 0.155 | **0.163** [0.136, 0.195] (n=600) |
| 3B + RAG (top-3) | 0.320 | 0.305 | 0.320 | **0.315** [0.279, 0.353] (n=600) |

All 600 replicates (200 questions × 3 seeds × 2 arms) are judged; the paired analysis has 600 complete
(question, seed) pairs.

---

## 2. Retrieval instrument + hit-rate (the P3-E foundation)

A per-question retrieval record is emitted to `runs/rag-wixqa/retrieval_log.jsonl` (seed-independent — retrieval
is a deterministic embedding→FAISS lookup, unaffected by the student's sampling seed):

```
{idx, question, gold_article_ids, retrieved_ids[top_k], sims[top_k], gold_rank(or -1), gold_retrieved:bool, top_sim}
```

**Retrieval hit-rate (gold KB article in top-3) = 110/200 = 0.550.** This reproduces ADR-030's 55% **exactly**,
and cross-checks against the published seed-42 run with **zero** `retrieved_ids` mismatches (200/200) — the
instrument reads the same index and returns identical retrievals. This 0.55 is the ceiling the dose-response
(T3.10/T3.11) will try to raise.

---

## 3. Gold-split: the unified law holds across all 3 seeds

Splitting each RAG replicate by whether the gold KB article was actually retrieved (pooled over seeds):

| subset | n questions | baseline | 3B + RAG | delta |
|---|---|---|---|---|
| **gold-RETRIEVED** | 110 | 0.127 | **0.400** | **+0.273** (≈ +27pt, ×3.1) |
| **gold-MISSED** | 90 | 0.207 | **0.211** | **+0.004** (≈ 0 — no lift without the right article) |

This is the causal core of ADR-030, now confirmed at 3 seeds: **RAG helps iff retrieval holds the answer.**
The +27pt where gold is retrieved vs ≈0 where it is missed — same model, prompt, and judge; the only
difference is whether the retrieved passage contained the answer → **the lift is the data.** (The
gold-missed cell was −4pt in the ADR-030 single seed; pooled over 3 seeds it is +0.4pt — i.e. statistically
indistinguishable from zero either way; the robust, large signal is the **contrast** between the two rows.)
The aggregate **+0.152 is exactly the 0.55·(+0.273) + 0.45·(+0.004) mixture** of these two regimes, so
raising the hit-rate must raise the aggregate toward the 0.400 gold-retrieved anchor (the P3-E claim).

---

## 4. Method (what was held fixed, for comparability)

- **Student** = `qwen2.5:3b` (Ollama, local, blind — never sees the gold answer), temperature 0.3, max 256
  tokens. Seeded via Ollama `options.seed` = {13, 42, 123} so draws are distinct-but-reproducible (§0.3).
- **Retriever** = MiniLM (`all-MiniLM-L6-v2`) + FAISS `IndexFlatIP` over the **6,221 KB articles only**
  (`indexes/wixqa-help-centre/`, `anti_leak: none` — the KB is the legitimate source; the 200 expert QA answers are
  never indexed). top-k = 3, whole-article passages capped at 900 chars in the grounding block.
- **Judge** = Groq `llama-3.1-8b-instant`, **reference-comparing** (`JUDGE_SYS`, temp 0, scores 0–4 vs the
  gold). §0.2-legal for a closed domain: only the **judge** sees the gold; the student stays blind. Family
  Llama ≠ student family Qwen.
- **Prompts, retrieval config, and judge are byte-identical to the ADR-030 scripts**
  (`scripts/wixqa_{baseline,rag}.py`); the only new variable across the three runs is the seed.
- **Stats** = the pre-registered `src/tlw/analysis/stats.py` (paired cluster bootstrap, 10k resamples,
  seed 0 + exact McNemar + Wilson) — the same machinery behind Track-A and `docs/RAG_RESULTS.md`.

Secondary: **pass@≥4 ("complete") = baseline 0.000 / RAG 0.010** (pooled). A 3B grounded on one article is
almost never rated *complete* vs the expert answer — this is the untouched completeness floor that the
Loop+RAG capstone (T3.14, ADR-032) targets.

---

## 5. Reproduce

```bash
# 1. generate (local, free) — seeds 13 & 123, both arms (seed 42 reuses the ADR-030 files verbatim)
HF_HUB_OFFLINE=1 python scripts/wixqa_run3seed.py --arm rag      --seed 13
HF_HUB_OFFLINE=1 python scripts/wixqa_run3seed.py --arm rag      --seed 123
HF_HUB_OFFLINE=1 python scripts/wixqa_run3seed.py --arm baseline --seed 13
HF_HUB_OFFLINE=1 python scripts/wixqa_run3seed.py --arm baseline --seed 123
# 2. judge (Groq, resumable; stops on the daily cap, resume after reset)
HF_HUB_OFFLINE=1 python scripts/wixqa_judge.py --glob 'runs/rag-wixqa/*/seed*.jsonl'
# 3. analyze
python scripts/wixqa_analyze.py
```

Run files: `runs/rag-wixqa/1-no-rag/seed{13,42,123}.jsonl` and `runs/rag-wixqa/2-rag-basic/seed{13,42,123}.jsonl`
(seed 42 in each is the ADR-030 draw, reused verbatim) + `runs/rag-wixqa/retrieval_log.jsonl`.
Each step directory carries a `manifest.json` with its exact condition. Every number above is computed live from these by
`scripts/wixqa_analyze.py` (§0.1/§0.4).

---

## 6. Honesty & limits

- **Judge budget (resolved).** Judging 6×200 answers exceeds the org-wide Groq `llama-3.1-8b-instant`
  daily token cap (TPD 500K); the run hit it at "Used 499992" with 66 baseline seed-123 replicates left.
  Generation was decoupled (local, free) from a **resumable, budget-graceful judger** that stops cleanly on
  the daily-cap 429 and resumes idempotently — the final 66 were scored on the **same Groq judge** after the
  reset (a local judge was deliberately **not** substituted — that would confound the comparison; per the
  todo lesson "batch across days"). The near-final (534-replicate) numbers moved negligibly to the final 600
  (+0.148→+0.152), confirming the design's stability.
- **Seed 42 = the ADR-030 draw** (unseeded, temperature 0.3), reused verbatim for exact continuity with the
  published +13pt; seeds 13/123 are Ollama-seeded. All three are valid samples from the same temp-0.3
  distribution — mixing seeded/unseeded draws does not bias a per-question paired bootstrap.
- **Directionality of the split is within-run** (same model/judge), so it is robust to seed; the aggregate
  hit-rate 0.55 is the ceiling capping it. A better retriever (T3.10) is the lever, not the RAG concept.
- **Single retriever variant** (MiniLM / whole-article). This is the ladder's variant #1; T3.10 tests
  chunking / stronger encoders / hybrid retrieval to move the hit-rate.

---

# Retriever ladder (T3.10) — offline hit-rate@k + the go/no-go gate

**Task:** T3.10 (`docs/plan/T3.10-retriever-ladder-offline.md`) · **Owner:** data-engineer · **Depends on:**
T3.9 · **Status:** DONE 2026-07-24 — **GATE = GO**, `bge_chunk` advances to T3.11.

Purely offline de-risk (the T2.7-pilot discipline applied to retrieval): rank stronger retrievers over the
SAME 6,221-article KB by **article-level hit-rate@k** (gold KB article in the top-k articles), **no LLM
generation, no judge calls**. Deterministic (exact FAISS IP + deterministic BM25); tool
`scripts/wixqa_retriever_ladder.py`; table `indexes/retriever_ladder/hitrate_table.json`. KB-only seal
re-verified (indexed items = 6,221 KB articles; gold article-ids used only to SCORE; QA answers never
indexed; each variant re-asserts it at load).

## Hit-rate@k table (200 questions; ceiling = 1.00, all gold in KB)

| variant | @1 | **@3** | @5 | @10 | MRR | Δ@3 vs baseline |
|---|---|---|---|---|---|---|
| **`bge_chunk`** ⭐ | 0.420 | **0.665** | 0.750 | 0.845 | 0.570 | **+0.115** |
| `minilm_chunk` | 0.390 | 0.645 | 0.740 | 0.840 | 0.540 | +0.095 |
| `bge_chunk_rerank` | 0.365 | 0.640 | 0.785 | 0.880 | 0.537 | +0.090 |
| `bge_whole` | 0.395 | 0.620 | 0.705 | 0.825 | 0.532 | +0.070 |
| `hybrid_rrf` (bge_chunk⊕bm25) | 0.395 | 0.605 | 0.705 | 0.790 | 0.529 | +0.055 |
| `minilm_whole` (T3.9 baseline) | 0.320 | 0.550 | 0.680 | 0.800 | 0.474 | — |
| `bm25` (lexical) | 0.280 | 0.465 | 0.525 | 0.620 | 0.396 | −0.085 |

Config: chunks = 180-word windows, 40 overlap, title-prefixed; encoders `all-MiniLM-L6-v2` (384d) vs
`BAAI/bge-base-en-v1.5` (768d, query-instruction prefix); reranker `cross-encoder/ms-marco-MiniLM-L-6-v2`
over the top-20; hybrid = reciprocal-rank fusion (k0=60).

## What each lever did (honest, incl. the negatives)

- **Chunking is the dominant lever (+0.095 alone).** Whole-article MiniLM embeds only the first ~256 tokens,
  but KB articles run long (p90 = 5,452 chars, max 51,119) — so a whole-article vector silently drops most
  of a long article's answer content. Indexing at chunk granularity fixes exactly that.
- **Stronger encoder helps and stacks:** `bge_whole` +0.070; combined **`bge_chunk` = 0.665, +0.115** — best
  at @1/@3, and best MRR. This is the winner.
- **BM25 alone is weak (−0.085)** and **hybrid RRF *hurts* the strong dense** (0.605 < 0.665): fusing the
  weaker lexical signal drags a good dense retriever down on this KB. Lexical fusion is not worth it here.
- **Cross-encoder reranking is a wash at k=3** (0.640 < 0.665): it improves deeper recall (@5 0.785, @10
  0.880) but trades away top-3 precision — not what a RAG top-3 setting wants. Dropped.
- **Practical ceiling:** even `bge_chunk` reaches only @10 = 0.845, so ~15% of gold articles are genuinely
  hard to surface from the question alone (question↔article vocabulary mismatch). The retriever lever has
  real but bounded headroom on this KB — honest, and it does not threaten the law.

## GATE decision → GO

`bge_chunk` beats the baseline by **+11.5pt hit-rate@3 (0.550 → 0.665)** — a meaningful, clean lift → **it
advances to T3.11**. `minilm_chunk` (0.645, chunking-only, no encoder swap) is carried as a cheaper middle
dose point, so T3.11 has ≥3 hit-rate levels: **0.550** (already run in T3.9), **0.645**, **0.665**.

## Prediction the dose-response will test (T3.11)

The T3.9 within-run conditionals are P(pass | gold retrieved) = **0.400** and P(pass | gold missed) =
**0.211**. If those hold as the retriever moves questions between the two regimes, aggregate pass =
hit·0.400 + (1−hit)·0.211. This mixture **reproduces the measured T3.9 point exactly** (hit 0.550 → 0.315),
so it is the pre-registered prediction:

| hit-rate@3 | predicted aggregate pass@≥3 |
|---|---|
| 0.550 (baseline) | 0.315  ← **matches T3.9 measured 0.315** |
| 0.645 (minilm_chunk) | 0.333 |
| 0.665 (bge_chunk) | **0.337** |

So T3.11 tests whether raising hit-rate 0.55 → 0.665 raises the aggregate 0.315 → ~0.337 (the dose-response).
The predicted effect is **modest and bounded** — capped by the 0.400 "pass given the right article" ceiling
(a 3B grounded on one correct article still fails ~60% of the completeness bar). That ceiling, not retrieval,
is the *second* bottleneck the Loop+RAG capstone (T3.14) targets.

---

# Dose-response: the law demonstrated (T3.11)

**Task:** T3.11 (`docs/plan/T3.11-dose-response-e2e.md`) · **Owner:** ops + qa · **Depends on:** T3.10 (go) ·
**Status:** FINAL — all 600/600 replicates judged (3 seeds × 200, completed 2026-07-25); numbers locked.

The T3.10 winner `bge_chunk` (hit-rate 0.665) was run end-to-end on WixQA (3B, seeds {13,42,123}), with
**everything held identical to the T3.9 MiniLM run except the retriever** (same student qwen2.5:3b, same Groq
ref-comparing judge, same PASS≥3, same top-3, same article-level grounding). Tools:
`scripts/wixqa_run3seed_retriever.py` (grounds on a chosen retriever's top-k), `scripts/wixqa_dose_analyze.py`
(reuses `src/tlw/analysis`). Retrieval is seed-independent so the ranking is computed once and reused.

## The dose-response (only the retriever changes)

| retriever | hit-rate@3 | aggregate pass@≥3 (Wilson 95%) | mixture prediction |
|---|---|---|---|
| no-RAG | 0.000 | 0.163 [0.136, 0.195] | — |
| `minilm_whole` (ADR-030) | 0.550 | 0.315 [0.279, 0.353] | 0.315 (exact) |
| **`bge_chunk`** (T3.10) | **0.665** | **0.340 [0.303, 0.379]** | 0.337 (**within 0.003**) |

**Pass-rate rises monotonically with hit-rate** (0.163 → 0.315 → 0.340) — the dose-response the law
predicts, and the measured `bge_chunk` point lands within 0.003 of the pre-registered prediction.

## The mechanism — gold-split stability (this is the actual proof)

| retriever | P(pass \| gold retrieved) | P(pass \| gold missed) |
|---|---|---|
| `minilm_whole` | **0.400** (n=330) | 0.211 (n=270) |
| `bge_chunk` | **0.411** (n=399) | 0.199 (n=201) |

The stronger retriever does **not** change the payoff *when* gold is retrieved (**0.400 vs 0.411** — flat
within noise) — it changes *how often* gold is retrieved (0.55 → 0.665), moving more questions into that
bucket. Same student, prompt, judge; the only difference is retrieval quality. **This demonstrates the causal
mechanism: retrieval is the bottleneck, and the aggregate is a mixture gated by hit-rate × ~0.40.** The
mixture model `pass = hit·0.400 + (1−hit)·0.211` predicts both RAG points (0.315 exact; 0.340 measured vs
0.337 predicted).

## Honest reading (§0.1)

- **The aggregate lift is not statistically significant:** `bge_chunk` − `minilm_whole` = **+0.025, 95% CI
  [−0.030, +0.078], McNemar p = 0.27** (paired, n=600). This is *expected and disclosed*: the predicted effect
  (+0.022) is bounded by the 0.400 ceiling and smaller than the CI. The proof is the **dose-response +
  gold-split stability + prediction match**, not a large significant aggregate jump. A single retriever step
  cannot produce a big aggregate move when P(pass | retrieved) caps at 0.400 — and that is itself the finding.
- **Headroom closed:** the retriever closed **25.6%** of the retrieval gap (0.55 → 0.665 of the 0.55 → 1.0
  possible); the aggregate tracked it from 0.315 to 0.340, toward the ~0.40 anchor. Reaching the anchor would
  need hit-rate → 1.0, and even then pass caps at ~0.40.
- **The second bottleneck** is confirmed: perfect retrieval still leaves ~60% of gold-retrieved questions
  failing the completeness bar — a 3B grounded on one correct article is not as *complete* as the expert
  answer. This is the untouched pass@≥4 floor the **Loop+RAG capstone (T3.14, ADR-032)** targets.

## Cost / latency (product note)

The `bge_chunk` upgrade is a stronger local encoder (`bge-base-en-v1.5`, 768d) + 180-word chunking: a
one-time offline index build (~3 min on the RTX 4060 over ~30k chunks) and negligible per-query retrieval;
**$0 cloud, no runtime penalty.** For an SME product it is a cheap, clear win on retrieval quality — bounded
in end-to-end effect only by the small model's ability to *use* the retrieved article.

## Verdict

**The unified RAG law is demonstrated, not asserted:** pass-rate is a monotonic, predictable function of
retrieval hit-rate, with the gold-retrieved payoff pinned at 0.400 across retrievers. Retrieval quality is
the bottleneck of aggregate RAG performance; improving it moves the aggregate along the predicted line toward
the 0.400 ceiling. Beyond that ceiling, the small model's completeness — not retrieval — is the next lever.

*Refined by T3.14 Stage 1 (below): the 0.400 payoff is invariant across **retrievers**, but not across
**grounding** — it rises to 0.534 once more of the retrieved article actually reaches the prompt.*

---

# Grounding delivery: the second bottleneck (T3.14 Stage 1)

**Status:** COMPLETE 2026-08-06 — 600/600 replicates judged (200 questions × 3 seeds × 2 arms).
**One change only:** which text from the *same* retrieved articles reaches the prompt. Retrieval was
reused verbatim from T3.11 (identical article ids), and student/judge/bars/top-k/seeds are unchanged.

## Why this was tested (a pre-run diagnostic caught a confound)

Before running self-refine, an offline audit of the T3.11 logs found we were **truncating the answer out
of the prompt ourselves**: grounding showed only the first 900 chars of each article, but gold articles
have median 3,555 chars — **92.5% were truncated**, and the student saw a median **25%** of the gold
article. Measured on the expert answer's content words: the **full** article covered **72%**, but the
**shown** text covered only **36%**. So "gold retrieved" did **not** mean "answer in context", and any
self-refine result would have been uninterpretable.

## Offline grounding ladder (2×2, zero LLM calls) — `scripts/wixqa_grounding_ladder.py`

| variant | answer-coverage in context | Δ | prompt |
|---|---|---|---|
| `head900` (= T3.11) | 0.412 | — | 2,640 chars |
| `chunk900` | 0.482 | +0.071 | 2,818 chars (+7%) |
| `head2400` | 0.612 | +0.201 | 5,830 chars |
| **`chunk2400`** | **0.655** | **+0.244** | 6,175 chars |
| *ceiling (full gold article)* | *0.726* | | |

Budget is the dominant lever; **chunk-centring adds +0.071 at ~7% extra prompt** by using the
retriever's own localisation (`bge_chunk` matches a chunk, but T3.11 grounded on the article *head*).
Verified before running: the largest prompt (~6.2k chars = 1,323 tokens) is **not truncated** by
Ollama's default context (needle-at-start test), so `num_ctx` was left unchanged.

## End-to-end result (`chunk2400` vs `head900`, 3 seeds, paired)

| metric | `head900` | `chunk2400` | delta |
|---|---|---|---|
| **pass@≥3 (aggregate, n=600)** | 0.340 | **0.470** | **+0.130 [+0.072, +0.188]**, McNemar **p=3.5e-08** (fixed 139 / broke 61) |
| pass@≥3, gold-**retrieved** (n=399) | 0.411 | **0.534** | **+0.123 [+0.050, +0.198]**, p=6.5e-05 |
| pass@≥3, gold-**missed** (n=201) | 0.199 | **0.343** | **+0.144** |
| **reference-coverage** (continuous, judge-free) | 0.361 | 0.403 | **+0.042 [+0.032, +0.053]** |
| pass@≥4 | 0.007 | 0.007 | +0.000 — **flat** |
| mean judge score | 1.98 | 2.18 | +0.20 |
| catastrophe rate (≤1) | 0.298 | 0.232 | −0.066 |
| answer length | 152 w | 144 w | −8 w |
| **extraction ratio** (answer-cov ÷ context-cov) | **88%** | **61%** | −27pt |

## What this establishes

1. **Delivery is a first-class bottleneck — and a bigger lever than the retriever was.** A pure
   prompt-construction fix (no model change, no retriever change, no extra inference) moved the
   aggregate **+13pt**, versus **+2.5pt** for the entire retriever ladder (0.315 → 0.340). The
   project-wide ladder now reads: no-RAG **0.163** → MiniLM RAG **0.315** → +best retriever **0.340** →
   **+grounding repair 0.470**.
2. **It is not "writing more."** Answers got *shorter* (152 → 144 words) while covering more of the
   reference — the gain is better fact *selection*, matching diagnostic F1.
3. **The 0.400 "payoff when gold is retrieved" was not a model ceiling.** It was invariant across
   retrievers (T3.11) but rises to **0.534** once the answer actually reaches the prompt.
4. **Even gold-*missed* questions improved (+14pt).** With only 900 chars we also saw too little of the
   *non-gold* retrieved articles; many of those questions are answerable from them once enough text is
   shown. "Gold article" is a dataset annotation, not the only usable source.
5. **The model is now the binding constraint, quantified:** extraction ratio falls **88% → 61%** — we
   raised in-context answer coverage by +0.244 and only +0.042 reached the answer. **~39% of the
   available answer content is left unused** — precisely the target for Stage 2 (self-refine).
6. **pass@≥4 is confirmed structurally unreachable** (0.007 in both arms): the full gold article covers
   only ~72% of the reference, so "all key facts present" is unattainable. The continuous
   reference-coverage metric is what carries statistical power here.

**Data-integrity note (§0.1):** an Ollama/native crash mid-run produced 5 consecutive empty answers in
the `chunk2400` seed-42 file (idx 124–128). Left in place, the judge would have scored them 0 and biased
this arm *downward* by ~2.5pt. They were regenerated with the identical prompt/seed/grounding before
judging and are stamped `repaired: true` in the run records. No other empties in 600.

**Reproduce:**
```bash
HF_HUB_OFFLINE=1 python scripts/wixqa_grounding_ladder.py            # offline coverage ladder
HF_HUB_OFFLINE=1 python scripts/wixqa_run3seed_retriever.py --retriever bge_chunk --grounding chunk2400 --seeds 13 42 123
HF_HUB_OFFLINE=1 python scripts/wixqa_judge.py --glob 'runs/rag-wixqa/4-rag-wider-context/seed*.jsonl'
python scripts/wixqa_grounding_compare.py --control 'runs/rag-wixqa/3-rag-better-retriever/seed*.jsonl' \
    --treat 'runs/rag-wixqa/4-rag-wider-context/seed*.jsonl' --label-control head900 --label-treat chunk2400
```

---

# Loop+RAG: self-refine on top of RAG (T3.14 Stage 2)

**Status:** PILOT COMPLETE 2026-08-06 — 133/133 judged (gold-retrieved subset, seed 42). Stopped at the
pilot **per the pre-registered gate** (§6 of `docs/plan/P3E-CAPSTONE-PLAN.md`): the effect on the judged
bar was null, so the expensive 3-seed run was not run. Single-seed, labelled subset — see limits.

The configuration the project is named after, finally evaluated: **self-refine + RAG together**
(ADR-032). Every prior RAG run was single-pass; the loop had only ever run without RAG (Track A).

**Method:** 1 initial answer + **2 grounded refinement rounds** on top of the Stage-1 `chunk2400`
grounding. The same retrieved context is supplied to **both** the critique and the refine step of
**every** round — the framework's arm-B `refine` prompt drops passages after round 1
(`src/tlw/loop/strategies.py:154`), which would re-open the knowledge gap RAG just closed. This makes it
Reflexion-style grounded refinement (Shinn 2303.11366), not the intrinsic self-correction Huang
(2310.01798) showed to be unreliable. Per finding F1 the critique asks for *concrete facts present in the
context but missing from the draft* and the refine step *rewrites within the same length*. **§0.2:** the
reference-comparing judge never gates iteration — rounds are fixed and judged once, offline; a **blind**
self-assessment is logged each round so a stop-policy can be evaluated offline. Round 1 is reused from
the Stage-1 run (identical prompt+seed), so the comparison is exactly paired. Teacher stays dead (ADR-024).

## Result — self-refine adds content, but not judged correctness

| metric | single-pass | + self-refine | delta |
|---|---|---|---|
| **reference-coverage** (continuous) | 0.414 | **0.445** | **+0.031 [+0.018, +0.047] — CI excludes 0** |
| **extraction ratio** | 63% | **68%** | +5pt |
| **pass@≥3** | 0.571 | 0.556 | **−0.015 [−0.068, +0.038]**, p=0.774 (fixed 5 / broke 7) |
| pass@≥4 | 0.015 | 0.008 | −0.008 |
| mean judge score | 2.35 | 2.35 | **0.00** |
| catastrophe rate (≤1) | 0.165 | 0.173 | +0.008 |
| answer length | 141 w | 164 w | **+23 w (+16%)** — it padded despite the instruction |

**The refinement demonstrably works at the mechanical level** — it pulls significantly more of the
reference's content into the answer (+3.1pt coverage; extraction 63%→68%) — **but none of that reaches
the judged bar.** 62% of answers were edited; the edits were a wash.

## Why: the same tug-of-war as ADR-027, now for iteration

Splitting by the single-pass score (what the answer was *before* refinement):

| single-pass score | n | mean score change | improved | worsened |
|---|---|---|---|---|
| 0 (wrong) | 9 | **+0.33** | 3 | 0 |
| 1 (mostly wrong) | 13 | **+0.38** | 3 | 0 |
| 2 (missing a key fact) | 35 | +0.00 | 3 | 3 |
| **3 (correct, minor gap)** | **74** | **−0.11** | **0** | **7** |
| 4 (complete) | 2 | −0.50 | 0 | 1 |

**Self-refine helps bad answers and damages good ones** — and since 57% of the gold-retrieved cases were
already at score 3, the aggregate nets to zero. This is the *same structural pattern* ADR-027 found for
RAG on MedQuAD ("helps hard, hurts easy") — a recurring law of this project: **every "add more"
intervention pays off only where the answer was deficient, and taxes the cases that were already fine.**

## Selective refinement: real headroom, but the small model cannot self-gate

| policy | pass@≥3 | vs single-pass |
|---|---|---|
| single-pass (no refinement) | 0.571 | — |
| always-refine (what we ran) | 0.556 | −0.015 |
| **ORACLE selective** (refine only if the answer scored ≤2) | **0.609** | **+0.038** ← upper bound |
| **blind self-assessment gate** (implementable, no gold) | 0.571 | **+0.000** |

The oracle shows selective refinement is worth **+3.8pt** — but the *implementable* gate captures
**none** of it: the 3B declared its round-1 answer "complete" **59%** of the time, including on answers
that were wrong. This replicates the selective-RAG result (ADR-027: oracle +9.9pt, cheap gates fail) on
a second intervention. **The missing component in both cases is a reliable gate, not the intervention.**

## Verdict (pre-registered decision rule)

Stage-2 lift < +2pt with a CI spanning 0 → **self-refine does not compound with RAG here → ship
single-pass RAG**, and spend the extra ~3× inference on a better retriever/grounding or a larger base
model instead. The honest system for this product is: **small local model + good retrieval + generous,
well-localised grounding — single pass.**

## Limits (§0.1)

Single seed, gold-retrieved subset (n=133), so the null is directional rather than CI-tight across seeds;
the pre-registered gate stopped the 3-seed run precisely because the pilot showed no effect worth the
budget. The continuous-coverage gain, by contrast, *is* significant even at this n. A stronger critique
model (rather than the 3B critiquing itself) is untested and is the natural next experiment.
