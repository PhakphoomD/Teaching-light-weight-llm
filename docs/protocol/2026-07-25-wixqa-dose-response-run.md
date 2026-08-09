# T3.11 — End-to-end dose-response run: the proof

- **Phase:** P3-E (run + analysis) · **Owner:** ops-engineer + qa-engineer · **Depends on:** T3.10 gate (go)
- **Output:** end-to-end pass-rates for the improved retriever(s) + the hit-rate↔pass-rate proof

## Objective
Run the winning retriever(s) from T3.10 end-to-end on WixQA (3B, 3 seeds) and demonstrate the
**dose-response**: pass-rate rises with retrieval hit-rate, converging toward the gold-retrieved
anchor (~0.409). This is the capstone result that proves retrieval is the bottleneck.

## Why (hub context)
Everything before this measured hit-rate (cheap) or a single retriever's pass-rate. This task
connects them: ≥3 points of (hit-rate, pass-rate) — {MiniLM 0.55, improved-retriever(s)} — plotted
against the 0.409 ceiling. A monotonic climb along the predicted line IS the proof (ADR-030's law
demonstrated, not asserted).

## Read first
- T3.10 winner + its offline hit-rate · T3.9 baseline (MiniLM, 3-seed pass-rate + hit-rate)
- ADR-030 (the anchors: aggregate 0.305, gold-retrieved 0.409, gold-missed 0.178)

## Steps
1. Run baseline-no-RAG (already have from T3.9) + improved-retriever RAG at seeds {13,42,123},
   holding student/judge/PASS≥3/top-k FIXED (only the retriever changes vs T3.9's MiniLM run).
2. Per variant, report pooled pass-rate + CI AND its measured hit-rate; re-confirm the
   gold-retrieved (~0.409) / gold-missed (~0.178) split is stable (the anchor shouldn't move —
   the retriever changes *how often* gold is retrieved, not the payoff *when* it is).
3. **The proof artifact:** a table/plot of (hit-rate → aggregate pass-rate) across
   {MiniLM(T3.9), improved(T3.11)...} with the 0.409 anchor line. State whether pass-rate tracks
   hit-rate as the law predicts, with the delta's CI.
4. Cost/latency note (the retriever upgrade's practical cost for a product).

## Definition of Done
- Improved-retriever pass-rate (3 seeds, CI) + measured hit-rate; the hit-rate↔pass-rate
  relationship shown across ≥3 points with the anchor; explicit statement of whether the law is
  confirmed (and by how much of the 0.55→~1.0 headroom was closed). Numbers trace to run logs.

## Must NOT do
- Don't change anything but the retriever between T3.9 and T3.11 (confound control). Don't cherry-
  pick the best seed. If pass-rate does NOT track hit-rate, report that honestly — it would refute
  or qualify the law, which is a real finding, not a failure to hide (§0.1).
