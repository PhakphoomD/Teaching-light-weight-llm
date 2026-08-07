# RAG Blueprint + Grounded-QA Eval Design (T3.1)

**Phase:** P3-A (docs only) · **Owner:** program-architect + qa-engineer · **Status:** Proposed
**Depends on:** ADR-024 (Track-A done), ADR-025 (P3 planned, RAG-first)
**Output of this task:** this spec + `schema.md` slot-D `rag` details + ADR-026. **No code.**
**Pre-registered headline:** **RAG effect = pass_rate(3B+RAG) − pass_rate(3B), reported with a 95%
paired cluster-bootstrap CI** over the held-out 125. A modest honest number is success; a
suspicious ~100% or a number that only moves `reference_match` (not blind correctness) is failure
(the ADR-001 trap).

This is the measurement-and-architecture blueprint for the RAG sub-track. It is *paper only* — it
changes no code (P3-A). It tells T3.2 (corpus/index), T3.3 (`rag` backend), T3.4 (grounded eval),
and T3.5 (ablation) exactly what to build. Every integrity rule cites §0 or a prior audit; every
architectural claim cites the code it reuses (file:line).

---

## 0. The one question

> Does grounding a small local student in **retrieved domain passages** make its answers **more
> correct** — measured by the same blind correctness judge as Track A, on the same held-out 125,
> with the retrieval corpus containing **no held-out answer**?

Track A settled that the loop adds no *knowledge* (C − B = +0.003, p = 1.00; `docs/TRACK_A_RESULTS.md:44`).
ADR-025 chose RAG as the knowledge source, on Ovadia et al. 2024 (EMNLP, "Fine-Tuning or Retrieval?",
aclanthology 2024.emnlp-main.15 — RAG > fine-tuning for injecting factual knowledge). This spec makes
the RAG number as defensible as the Track-A number: same judge, same held-out set, same statistics
(`src/tlw/analysis/stats.py`), same honesty discipline (§0.1/§0.2). RAG adds two *new* honesty traps
this design must close up front:

- **T-a Retrieval leakage.** A retrieved passage that *is* (or paraphrases) the held-out gold answer
  turns "grounded correctness" into an answer-key lookup — ADR-001 all over again. Closed by §5.
- **T-b Faithfulness ≠ correctness collapse.** "Grounded" can silently become "similar to the retrieved
  text," and a groundedness score can become a back-door reference-match gate. Closed by §4: faithfulness
  is a **diagnostic column only**, never the pass/fail decision; the pass/fail stays blind correctness.

---

## 1. Retrieval architecture (paper)

### 1.1 Corpus and chunking unit

- **Source corpus = the Diabetes TRAIN split only** — `data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl`,
  **506 records** (verified: `wc -l` → 506; held-out = 125, `..._heldout.jsonl`). READY for RAG at
  **93.4 / n=631** (`..._clean_readiness_rag.md:2`; the 631 = train+heldout, but only the 506 train
  records may enter the index — §5). Answerability 99.6 and self-contained (rubric D7) mean each cleaned
  answer is a usable standalone passage.
- **Chunking unit = one passage per cleaned record**, built from its **`answer`** field (the cleaned
  NIH section), with the record's `question`, `id`, and `domain` carried as passage metadata. Rationale:
  MedQuAD answers are auto-extracted NIH sections that are already topically coherent and self-contained
  (rubric D7 answerability 99.6); a record *is* the natural retrieval unit, matching how the memory
  backend already keys by a single question→note record (`src/tlw/memory/faiss_backend.py:269-289`).
- **Retrieval key = the record `question`, not the answer.** We embed and search over the *question*
  text (query = the held-out question → nearest TRAIN questions), then return their *answers* as the
  grounding passages. Why question-keyed: the incoming query is a question, so question↔question
  similarity is the honest match signal; answer↔question mixing degrades retrieval. This mirrors the
  memory backend, which also embeds the question and returns the associated note
  (`faiss_backend.py:152, 247, 304`).
- **Sub-chunking (optional, length-gated).** Sample median answer ≈ 175 words (`train.jsonl` record 0:
  `word_len: 175`); most fit one passage. For answers over **~250 words**, split on sentence boundaries
  into ≤~150-word windows sharing the parent's question/id metadata, so a long passage does not dominate
  the top-k context window. **Default for v1 = no sub-chunking** (one passage per record); T3.2 turns on
  length-gated sub-chunking only if it measurably helps retrieval on a TRAIN-internal probe. Keep it
  simple first (YAGNI, ADR-015).

### 1.2 Embedding model — reuse MiniLM

**Reuse `all-MiniLM-L6-v2` ("minilm")** — the same encoder the memory backend already loads
(`src/tlw/memory/faiss_backend.py:27-28, 100-106`) and the same one the dataset uniqueness/dedup metric
uses (rubric D3). Justification over a change: it is already a project dependency (no new install), free,
local, fast, and normalizing-friendly for cosine IP search. A stronger retriever (e.g. `bge-small`,
`gte-small`) is a **later optimization**, not a T3.2 requirement — swapping it is a one-line slot-D
`embedding` change (§2), so we do not gate the first RAG number on encoder tuning.

### 1.3 Retriever, top-k, similarity floor

- **Index = FAISS `IndexFlatIP` over L2-normalized MiniLM vectors** — exact cosine search, the exact
  construction already proven in the memory backend (`faiss_backend.py:119, 122-127, 304-305`). At n=506
  a flat index is instant; no approximate index (IVF/HNSW) is needed at this scale.
- **top-k default = 3** (slot-D `top_k`, matches the memory default `faiss_backend.py:54`). Small
  enough to keep the grounding context short (3 × ~175 words ≈ 525 words ≪ context window), large
  enough to cover a question answered across two near-neighbours.
- **Similarity floor default = 0.35** (slot-D `similarity_threshold`). NOTE this is **deliberately
  lower than the memory backend's 0.75** (`faiss_backend.py:54`): memory retrieval wants a near-exact
  question match before offering a note; RAG wants *related* domain context even when no train question
  is a close twin. The 0.75 floor would return `[]` for most held-out questions (they are held out —
  their close twins are largely absent by design) and starve the grounding. **0.35 is a starting value
  T3.2 calibrates** on a TRAIN-internal retrieval probe (hold out 50 train questions, measure
  recall@3 of a topically-relevant passage); the value is config-visible, not hardcoded.
- **Empty is normal and honest.** If nothing clears the floor, return `[]` and the student answers
  *un-grounded* for that question (identical to its no-RAG arm on that item). RAG is an aid, not a
  crutch — same posture as the memory retrieval contract (schema.md Memory v2 §3.6).

### 1.4 How passages enter the answer prompt (grounding, not answering)

Retrieved passages are injected as a **labelled reference-context block** the student is told to *use
as support*, never as the answer to emit. Draft grounding preamble (T3.3 finalizes wording; the
student preset stays the ADR-020 `minimal`/`orca` family, extended with a context slot):

```
You are answering a medical question for a patient. Use the REFERENCE PASSAGES below as
supporting evidence when they are relevant. They are background material, NOT the answer —
write your own answer to THE QUESTION, and do not copy a passage verbatim. If the passages
do not cover the question, answer from your own knowledge and say what you are unsure of.

REFERENCE PASSAGES:
[1] {passage_1}
[2] {passage_2}
[3] {passage_3}

THE QUESTION: {question}
```

Rules binding the grounding step:
- **Grounding reaches the FIRST answer attempt** (unlike memory notes, which schema.md Memory v2 §3
  restricts to *refinement* rounds only). This is the defining behavioural difference of the `rag`
  backend and is called out in §2. Knowledge must be available before the first draft, not only after
  a critique.
- **Never "the answer is …".** The passage block is evidence; the preamble forbids verbatim copying.
  The blind judge scores the student's *own* answer (§4), so copying a passage that is off-target is
  penalised, not rewarded.
- **The retrieved-passage text is TRAIN data, never the held-out gold answer** (§5) — so a passage in
  the student prompt is *not* a §0.2 violation the way the held-out reference would be. The existing
  loop leak guard `assert_gt_free(prompt, ground_truth)` (`src/tlw/loop/core.py:36`) still runs on every
  student-bound prompt with the *held-out* answer as `ground_truth`: if a retrieved passage ever
  contains a ≥12-token shingle of the held-out gold answer, the guard aborts the run (the seal firing =
  the §5 dedup failed; that is the intended tripwire, exactly as it fired in Track-A arm D,
  `docs/TRACK_A_RESULTS.md:109-113`).

---

## 2. Slot-D `rag` contract (schema.md addition)

`type: rag` is the third `MemoryBackend` implementation (schema.md slot-D table; registries.py:16
reserves the name **unregistered** so a `rag` run fails loud until T3.3 builds it). It satisfies the
**same seam** (`store`/`retrieve`/`update_outcome`/`stats`, `src/tlw/registries.py:75-100`) so the
runner is unchanged — but it is a *corpus-backed, read-only* backend, which differs from `faiss`
(run-local, accumulating teaching notes) on three points:

| Aspect | `faiss` (memory, T2.5) | `rag` (T3.3) |
|---|---|---|
| **What it stores** | teaching *notes* distilled from teacher feedback, written during the run | domain *passages* (train answers), built ONCE offline (T3.2), read-only at run time |
| **`store()`** | writes tripwire-checked notes (schema.md Memory v2 §2) | **no-op** (returns `None`) — the corpus is immutable during a run; nothing is learned into it |
| **`retrieve()` returns** | `{id, teaching_note, success_rate, …}` | `{id, passage, question, similarity, source_id}` — passage text + provenance |
| **Injection point** | refinement rounds only (schema.md Memory v2 §3) | **first answer attempt** (§1.4) + carried through refinement |
| **Corpus source** | empty per-run store, isolated by `run_id` | prebuilt index from `data/clean/…_train.jsonl` via `corpus_path` (§5) |
| **Arm gate (V8)** | A/B require `none`; C/D may use `faiss` | RAG arms are their OWN arms (§4), orthogonal to A–D; V8 does not forbid `rag` on a single-pass answer arm |

**Slot-D keys `rag` uses** (all already in the slot-D table, schema.md:69, plus two new optional keys):

- `type: rag` (required)
- `embedding: minilm` (reuse; §1.2)
- `top_k: 3` (§1.3)
- `similarity_threshold: 0.35` (§1.3 — note the RAG-specific lower default vs memory's 0.75)
- **`corpus_path`** *(new optional key, `rag` only)* — path to the prebuilt index directory produced by
  T3.2 (e.g. `data/rag/diabetes_train/`). Absent for `none`/`faiss`. Subject to a **held-out denylist**
  analogous to Config Contract V6 (§5): a `corpus_path` whose build manifest reports any held-out id
  fails validation.
- **`max_passage_words: 150`** *(new optional key, sub-chunk cap, §1.1)* — only consulted when
  sub-chunking is enabled.

`update_outcome()` and `stats()` are implemented trivially (no-op / `{index_size, corpus_size}`),
satisfying the ABC without pretending the corpus learns. Because the seam is unchanged, the T2.6 runner
composes a `rag` run exactly as it composes a `faiss` run — the only difference the runner sees is that
`retrieve()` returns passages and the loop injects them at round 1 (a loop concern, T3.3, not a runner
concern).

---

## 3. Ablation arms

Four arms on the **same held-out 125**, same seeds, paired question-by-question (ADR-025):

| Arm | Student | Retrieval | Role |
|---|---|---|---|
| **3B** | `qwen2.5:3b` (local) | none (`memory.type: none`) | the floor — identical to Track-A arm A on the 3B |
| **3B+RAG** | `qwen2.5:3b` (local) | `rag`, top-k 3 | **the headline treatment** |
| **7B** | `qwen2.5:7b-instruct` (local) | none | ceiling reference — does a bigger model close the gap without retrieval? |
| **7B+RAG** | `qwen2.5:7b-instruct` (local) | `rag`, top-k 3 | does RAG still help when the model is already stronger? |

- **Single-pass answering (no teacher loop) for the RAG headline.** Track A proved the teacher adds
  nothing (ADR-024) and self-refine adds +9pt independently of retrieval; to isolate the *retrieval*
  effect cleanly, the RAG arms answer in **one pass** (`params.arm: A`, `max_rounds: 1`). Self-refine ×
  RAG is a *separate* future ablation (like C′/D′ for memory), not this headline — keeps 3B+RAG − 3B a
  clean "retrieval vs no-retrieval" contrast with nothing else varying. *(If T3.5 wants the product
  configuration = RAG + self-refine, run it as a labelled secondary arm, never merged into the headline.)*
- **Same student model within a pair.** 3B+RAG differs from 3B *only* by the retrieval slot; 7B+RAG
  from 7B likewise. So each `+RAG − base` difference isolates retrieval.
- **Judge family ≠ student family (§0.2, V2).** Both students are Qwen → judge = Llama
  (`llama-3.1-8b-instant` or local `llama3.1:8b`), identical to Track A (`docs/TRACK_A_RESULTS.md:29`).

---

## 4. Grounded-QA eval protocol (mirrors EVAL_SPEC)

### 4.1 Primary metric — blind correctness (reused verbatim from Track A)

- **Same judge, same rubric, same threshold as Track A**, so RAG numbers are directly comparable:
  the `BlindJudge` (`src/tlw/evaluation/judge.py:128`), 0–4 correctness, **PASS iff score ≥ 4**
  (normalized `pass_threshold` 0.75; the score≥4 bar and its rationale are locked in
  `docs/TRACK_A_RESULTS.md:86-96`). Blind by construction — `score(question, answer, mode)` has no
  parameter through which any reference (held-out gold **or** retrieved passage) can reach the judge
  prompt (`judge.py:9-11, 161`). The judge scores the student's answer *on its own merits*, never
  against the passages, so "looks like the retrieved text" earns nothing (closes trap T-b).
- **Null-rate < 2%** (same gate as EVAL_SPEC §3.2), nulls excluded from the denominator.

### 4.2 Diagnostic metric #1 — faithfulness / groundedness (NEW, decided here, diagnostic only)

**Decision (T3.1 owns this choice): a RAGAS-style LLM-judged groundedness ratio** (Es et al. 2023,
arXiv 2309.15217 — "RAGAS: Automated Evaluation of RAG"). It answers *"is the answer supported by the
passages it was given?"* — a RAG-quality signal that is **ground-truth-free** (it compares the answer to
the *retrieved passages*, never to the held-out gold answer), therefore §0.2-safe, and judged by our
existing independent judge model.

- **Definition:** `faithfulness = supported_claims / total_claims`, where the judge (i) segments the
  student answer into atomic factual claims and (ii) marks each claim as *supported / not-supported* by
  the retrieved passage set. A single-call variant (ask the judge for the two counts in one JSON reply)
  keeps the budget to one extra judge call per answer; T3.4 may use the two-call RAGAS decomposition if
  the single call proves unreliable on a TRAIN probe.
- **§0.2 safety:** the faithfulness judge sees `(answer, retrieved_passages)` — both are non-gold
  (passages are TRAIN, §5). It **never** sees the held-out reference. It is a *new* judge mode, NOT the
  deliberately-unbuilt `gt_comparing` mode (registries.py:16) — build it as its own `FaithfulnessJudge`
  under a new registry name, not by unlocking `gt_comparing`.
- **NEVER the pass gate.** Faithfulness is reported as a **separate column** beside blind correctness,
  exactly as `reference_match` is in Track A (EVAL_SPEC §2). A highly-faithful-but-wrong answer (student
  faithfully echoes an off-target passage) must FAIL on correctness — that divergence is the whole point
  of keeping them separate (closes trap T-b). **No weighted fusion.** Slot-F `metrics.weights` stays
  `{ blind_score: 1.0 }` (V1), faithfulness logged outside the weighted score.
- **Reading the two together (the honesty check, §0.1):**
  | correctness | faithfulness | interpretation |
  |---|---|---|
  | ↑ | ↑ | RAG works — answers are more correct *and* grounded in retrieved evidence |
  | ↑ | ↓ | correct but not from the passages — the model already knew it; RAG isn't the cause |
  | ↓ | ↑ | grounded in the *wrong* passage — retrieval hurt (faithful to bad context) |
  | flat | flat | RAG is inert on this domain (small-model floor already high, ADR-024 §5) |

### 4.3 Diagnostic metric #2 — reference_match (reused, diagnostic only)

Keep `reference_match` (`src/tlw/evaluation/diagnostics.py:88` — MiniLM cosine + ROUGE-L vs the held-out
reference) as a diagnostic column, unchanged from Track A (EVAL_SPEC §2). Its Track-A finding — flat
while correctness rose (`docs/TRACK_A_RESULTS.md:72-77`) — is the reason it can never be a gate. For RAG
it earns its keep as a **leakage smell test**: if an arm's `reference_match` spikes toward 1.0, suspect
§5 retrieval leakage (a retrieved passage ≈ the gold answer) and audit before trusting the correctness
number.

### 4.4 Metrics summary (never merged)

| Metric | Sees held-out gold? | Sees passages? | Decides pass/fail? | Role |
|---|---|---|---|---|
| **`correctness`** (BlindJudge 0–4, ≥4) | **No** | No | **YES — headline** | comparable to Track A |
| **`faithfulness`** (RAGAS groundedness ratio) | **No** | Yes | No — diagnostic | is the answer grounded in retrieval? |
| **`reference_match`** (MiniLM+ROUGE-L) | Yes (score-path only) | No | No — diagnostic | old confound + leakage smell test |

---

## 5. Anti-leak rules for retrieval (hard rules T3.2/T3.3/T3.4 enforce)

> **Updated 2026-07-16 (hub finding + decision).** The first end-to-end RAG run surfaced that
> whole-answer cosine (RAG-L2a below) is **blind to templated verbatim-block leaks**: MedQuAD's
> "What to do for X?" answers reuse the same NIH advice template across different GI diseases
> (e.g. *Crohn's* vs *Ulcerative Colitis*), so two answers can share ~100% of their text verbatim
> yet score only ~0.76 whole-doc cosine — under the 0.90 cut. 16% of held-out questions retrieved
> such a passage. The seals below were strengthened accordingly: a **build-time verbatim-block
> scrub (RAG-L2b)** removes template twins from the corpus, and the **run-time guard (RAG-L3)
> filters the offending passage per-query rather than aborting the whole run.**

1. **RAG-L1 — the retrieval corpus is the TRAIN split ONLY.** The held-out 125 must NEVER be in the
   index. A retrieved chunk that is the gold answer is leakage (trap T-a) and would reproduce ADR-001.
   T3.2 builds the index from `…_train.jsonl` (506) exclusively and writes a **build manifest** listing
   every indexed `id`; the manifest must contain **zero** held-out ids.
2. **RAG-L2a — cosine near-duplicate scrub.** Drop any train record whose `question` OR `answer` is
   ≥ 0.90 cosine (MiniLM) to any held-out record (the rubric-D3 threshold). Catches semantic twins.
   *(Diabetes build: 58 dropped.)*
3. **RAG-L2b — verbatim-block scrub (NEW).** Drop any train record whose `answer` shares **≥ 8
   contiguous 12-token shingles** with any held-out `answer` (config `--block-shingle-min`, default 8) —
   the templated answer-by-proxy leak that cosine misses. This is the seal that removes the
   Crohn's/Colitis-style template twins. The manifest logs the dropped ids.
4. **RAG-L3 — run-time per-passage filter (defence in depth).** At grounding time,
   `grounding_block(...)` drops (and counts) any retrieved passage that still shares a ≥12-token
   shingle with the held-out gold answer, then grounds on the survivors — instead of aborting the run.
   This handles the *residual innocent* case: same-topic passages routinely share a single definitional
   sentence with the gold answer (e.g. the standard NIH definition of Acromegaly) without being the
   answer; dropping that passage is conservative (biases against RAG) and keeps the student gold-free.
   The count is reported per-run (`grounding_filtered_total`, §0.1 observability). The whole-prompt
   `assert_gt_free` (`src/tlw/loop/core.py`) stays as the final backstop: if gold text ever reaches a
   student prompt through any path, it still aborts rather than leak.
5. **Config validation.** A `corpus_path` whose manifest reports any held-out id → hard error (a slot-D
   analogue of Config Contract V6, schema.md:110).
6. **The judge never sees passages or gold** (§4.1) — blind correctness is computed exactly as Track A.
7. **Faithfulness judge sees passages but never gold** (§4.2) — it is a new mode, not `gt_comparing`.

---

## 6. Pre-registered claim (frozen before the run — §0.1)

> **RAG effect = pass_rate(3B+RAG) − pass_rate(3B)**, reported with a **95% paired cluster-bootstrap
> CI** over the 125 held-out questions (cluster = question, seeds pooled, ≥10,000 resamples), **exact
> McNemar p-value alongside**, **Wilson** per-arm descriptive — the identical machinery Track A used
> (`src/tlw/analysis/stats.py:41` wilson_interval, `:88` paired_cluster_bootstrap, `:168` exact_mcnemar).
> Secondary reported comparisons: **7B+RAG − 7B** (does RAG help a stronger model?) and **3B+RAG − 7B**
> (can retrieval lift a 3B to a 7B's level — the product question). `faithfulness` and `reference_match`
> are reported but are **NOT** the claim.

Pre-registering the metric, threshold (≥4), arms, seeds, and CI method *before* looking at held-out
results is what stops post-hoc metric-shopping — the same discipline that made the Track-A number
credible. `src/tlw/analysis` already accepts a `--comparison` argument (`docs/TRACK_A_RESULTS.md:156`);
T3.5 filters to the RAG run_ids and runs `--comparison 3BRAG-3B`.

---

## 7. Budget (arithmetic)

RAG is **essentially free** — everything runs local:

- **Students** — `qwen2.5:3b` and `qwen2.5:7b-instruct` on Ollama (local, $0). Single-pass answering
  (§3): `1 gen × 125 × 3 seeds × 4 arms = 1,500` local generations. At ~5 s/gen (ADR-014 Qwen-7B ≈ 4.8
  s/q; 3B faster) ≈ **~2 h** of local GPU time.
- **Embedding / index** — MiniLM local, one-time build over 506 records (seconds) + 125×3 query
  embeddings at run time (local, negligible).
- **Correctness judge** — reuse Track A's path: local `llama3.1:8b` (free) or Groq `llama-3.1-8b-instant`
  (well within 500K TPD). `125 × 3 × 4 = 1,500` judge calls, ~650 tok each ≈ 975K tok — one day on the
  8B-instant cap, or free/local.
- **Faithfulness judge** — one extra local call per answer (`1,500` calls, ~900 tok each with the passage
  block). Local → $0; wall-clock only.

**Total honest end-to-end ≈ a few hours of local compute, $0 cloud required** (Groq optional for the
correctness judge to free the GPU, as in Track A). No teacher, no 70B, no cap pressure. This is why RAG
is measured before LoRA (ADR-025): it is cheap to run and it is where the *knowledge* gap lives.

---

## 8. Slot-D / config fit (an example T3.3/T3.5 file)

```yaml
# experiments/trackB_p3_3bRAG_diabetes.yml   (diffs from config/base.yml)
student: { provider: local, model: qwen2.5:3b, temperature: 0.3 }        # A — under test (product floor)
memory:                                                                  # D — the RAG retriever
  type: rag
  embedding: minilm
  top_k: 3
  similarity_threshold: 0.35                                             #     RAG floor (lower than memory's 0.75, §1.3)
  corpus_path: data/rag/diabetes_train                                   #     prebuilt index (T3.2); held-out-free (§5)
params:  { arm: A, max_rounds: 1, seed: 42 }                             # E — single-pass; retrieval is the only variable
eval:                                                                    # F — SAME judge as Track A
  judge: { provider: local, model: llama3.1:8b }                        #     Llama judge ≠ Qwen student (V2, §0.2)
  mode: blind
  pass_threshold: 0.75                                                   #     score >= 4 ("correct AND complete")
  metrics: { weights: { blind_score: 1.0 } }                             #     faithfulness/reference_match logged outside
```

Validation this satisfies: **V1** weights sum 1.0; **V2** judge (Llama) ≠ student (Qwen); **V4** seed
present; **V5** threshold under `eval`; **V7** `mode ∈ {blind}`, `arm ∈ {A}`. The `3B` (no-RAG) arm is
the same file with `memory: { type: none }`; the 7B pair swaps `student.model: qwen2.5:7b-instruct`.
**V8 note:** arm A with `memory.type: rag` is legal — V8 forbids A/B + *accumulating* memory (`faiss`),
but `rag` is a read-only corpus, not a note-accumulating store, so it does not create the "baseline
that learns" problem V8 exists to stop. T3.3 must confirm the loader treats `rag` as exempt from V8's
A/B → `none` rule (a one-line validator change, flagged to T2.1's owner).

---

## 9. Definition-of-Done check (T3.1)

- [x] Retrieval architecture: chunking unit, embedding (reuse MiniLM), retriever (FAISS IP), top-k,
  similarity floor, grounding-into-prompt — §1
- [x] Slot-D `rag` contract: how it differs from `faiss`, which keys, same seam so runner unchanged — §2
  (+ schema.md addition)
- [x] Grounded-QA eval: blind correctness primary (PASS ≥ 4, same judge as Track A) + faithfulness
  diagnostic DECIDED (RAGAS groundedness ratio) + reference_match, never merged — §4
- [x] Pre-registered headline: 3B+RAG − 3B with 95% paired cluster-bootstrap CI (reuse
  `src/tlw/analysis`) — §6
- [x] Anti-leak rules: corpus = TRAIN only, train↔heldout dedup scrub, build manifest, run-time guard — §5
- [x] Budget (local, ~free) — §7 · Slot-D config fit — §8
- [x] ADR logged (ADR-026)

## 10. Open risks / NEEDS-HUB-DECISION

- **[decided-by-default, revisit if T3.2 probe fails] similarity_threshold 0.35 and top_k 3** are
  starting values calibrated on a TRAIN-internal retrieval probe (§1.3). Not user-level; T3.2 tunes.
- **[decided-by-default] no sub-chunking in v1** (§1.1). Turn on only if the probe shows long passages
  hurt.
- **[NEEDS-HUB-DECISION — small]** §3 runs the RAG headline **single-pass** (no self-refine) to isolate
  retrieval. The *product* likely wants RAG **+** self-refine (the +9pt Track-A gain). Confirm at the
  T3.5 gate whether to add a labelled `3B+RAG+self-refine` secondary arm (recommended: yes, as a
  secondary, never merged into the 3B+RAG − 3B headline).
- **[flag to T2.1 owner]** V8's "A/B ⇒ memory.type must be none" rule needs a one-line exemption for
  `type: rag` (read-only corpus, not an accumulating store) — §8. Small validator change in T3.3.
- **Faithfulness judge reliability** — the single-call RAGAS variant (§4.2) is a budget shortcut; if a
  TRAIN probe shows it disagrees with the two-call decomposition, T3.4 falls back to two calls. It is a
  *diagnostic*, so its noise never touches the headline — but report it with its own caveat.
- **Small-model floor** — Track A found the 3B already passes ~73–82% on these largely-definitional
  Diabetes questions (`docs/TRACK_A_RESULTS.md:59, 86-90`). If the floor is that high, RAG's *headroom*
  is small; a modest 3B+RAG − 3B is still the honest answer, and 3B+RAG − 7B (can retrieval lift a small
  model to a big one's level) may be the more product-relevant read. Report all three (§6).
```
