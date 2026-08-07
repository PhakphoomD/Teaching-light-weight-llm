# T3.9 — Instrument the retriever + harden the WixQA baseline to 3 seeds

- **Phase:** P3-E (code + run) · **Owner:** data-engineer + qa-engineer · **Depends on:** ADR-030
- **Output:** per-question retrieval log (hit-rate harness) + 3-seed WixQA RAG numbers with CI

## Objective
Two things the dose-response proof needs as its foundation: (1) a per-question record of *whether
the gold KB article was retrieved and at what rank* (the hit-rate measurement harness), and (2) the
current +13pt result re-run at 3 seeds so it carries a real CI, not a single-seed point.

## Why (hub context)
The whole P3-E proof is "pass-rate tracks hit-rate." That requires measuring hit-rate per question
per variant — build the harness once here. And WixQA is the project's ONLY positive result
(ADR-030) but single-seed; 3 seeds turns +13pt from directional into a claim (cheap: local student
+ Groq judge).

## Read first
- `scripts/wixqa_{baseline,build_index,rag}.py` · `data/wixqa/`, `data/rag/wixqa_kb/manifest.json`
- ADR-030 · memory [[wixqa-rag-positive-result]] · `runs_wixqa/{baseline_norag,rag_top3}.jsonl`

## Steps
1. Add a per-question retrieval record to the RAG run: `{q_id, gold_article_id, retrieved_ids[top_k],
   gold_rank (or -1 if missed), gold_retrieved: bool, top_sim}`. Persist alongside the run outputs.
   Confirm it reproduces the known **hit-rate = 55% (110/200)** at seed 42 (sanity anchor).
2. Re-run BOTH arms (baseline no-RAG, 3B+RAG top-3) at **seeds {13, 42, 123}**, same student/judge/
   PASS≥3 as ADR-030. Keep the ref-comparing judge (§0.2-legal here — only judge sees gold).
3. Compute: per-seed and pooled pass-rate for both arms; **+RAG delta with 95% CI** (reuse the
   `src/tlw/analysis` bootstrap/McNemar machinery, or an equivalent documented method); and the
   gold-retrieved vs gold-missed split pooled over seeds (confirm the +27 / −4 pattern holds).
4. Write a short results note (append to the WixQA section / a new `docs/WIXQA_RESULTS.md`): 3-seed
   headline + CI + the hit-rate baseline (this is variant #1 = MiniLM/whole-article in the ladder).

## Definition of Done
- Retrieval log emitted + hit-rate reproduces 55% at seed 42; 3-seed +RAG delta with CI reported;
  gold-split pattern confirmed across seeds; numbers trace to run files (§0.1/§0.4).

## Must NOT do
- Don't change the retriever yet (that's T3.10 — this task measures the CURRENT one at 3 seeds).
- Don't index the 200 expert QA answers (only KB articles). Don't switch judge/bar/student
  (comparability). Don't read individual QA to tune anything (§0.2).
