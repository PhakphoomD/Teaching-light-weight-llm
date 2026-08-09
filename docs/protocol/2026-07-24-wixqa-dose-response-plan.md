# P3-E — Prove the unified RAG law: retrieval quality is the bottleneck (WixQA)

**Status: active planning (2026-07-24 hub).** User goal chosen: *prove the RAG law decisively via
the retriever.* This sub-track turns ADR-030's claim ("RAG helps iff the retrieved passage holds
the answer; the bottleneck is retrieval, not the RAG concept") from an asserted finding into a
**demonstrated dose-response**.

## The claim to prove (ADR-030, memory [[wixqa-rag-positive-result]])
On WixQA: baseline 0.175 → 3B+RAG 0.305 (+13pt). Split by whether the gold KB article was
retrieved: **gold-retrieved 0.409 (+27pt) vs gold-missed 0.178 (−4pt); retrieval hit-rate = 55%.**
The unified law says the 0.55 hit-rate is the ceiling capping the aggregate. **If the law is true,
raising hit-rate must raise the aggregate pass-rate toward ~0.409.**

## The proof design (why dose-response, not just "a better retriever")
Weak proof = "we improved the retriever and the number went up" (could be luck/confound).
**Strong proof = pass-rate moves as a predictable function of hit-rate, across ≥3 retriever
settings, converging on the 0.409 gold-retrieved anchor.** That demonstrates the *causal
mechanism*, not a one-off gain. Even a partial climb (e.g. hit-rate 55%→75% ⇒ pass 0.305→~0.35 in
line with the curve) proves the law — we do NOT need hit-rate=100%.

## Honesty guards (carry from ADR-030)
- WixQA grounding on the KB article is LEGITIMATE (the KB is the intended source; NOT leakage) —
  but the index must contain **only the 6,221 KB articles, never the 200 expert QA answers**.
  Re-verify this seal after every re-index (a chunker/encoder swap must not pull in the QA gold).
- Same student (`qwen2.5:3b`), same judge (Groq `llama-3.1-8b`, ref-comparing / `gt_comparing` —
  legal closed-domain, only the JUDGE sees gold, §0.2), same PASS≥3 headline across ALL variants —
  or the dose-response comparison is meaningless (hold everything but the retriever fixed).

## Tasks
```
T3.9  instrument retriever + 3-seed baseline (CI on +13pt, hit-rate logging harness)
   └► T3.10 offline retriever ladder (chunking / encoder / hybrid) — hit-rate@k ONLY, cheap
        └► GATE: did any variant raise offline hit-rate? ──► T3.11 e2e dose-response run + PROOF
                                                              └► T3.14 Loop+RAG capstone (self-refine+RAG)
                                                                   └► T3.12 write-up: the FULL SYSTEM + law
T3.13 (independent, MUST-before-commit) fix stale docs/PROJECT_OVERVIEW_AND_RESULTS.md (§0.1)
```
- **T3.9** — measure hit-rate per question + re-run current RAG at 3 seeds (gives the +13pt a CI).
- **T3.10** — build 2–3 retriever variants; rank by OFFLINE hit-rate@k (no LLM calls — cheap de-risk).
- **T3.11** — run the winner(s) end-to-end (3B, 3 seeds); plot pass-rate vs hit-rate vs the 0.409 anchor.
- **T3.14** — **self-refine + RAG together (the actual Loop+RAG system, never yet run)** on the best
  retriever; targets the untouched **pass@≥4 completeness floor** on gold-retrieved. Closes the
  system-integration gap (ADR-032) so the write-up is about the SYSTEM, not two separate legs.
- **T3.12** — consolidate MedQuAD-null + WixQA-positive + dose-response + the Loop+RAG system result
  into the proven law + ADR.
- **T3.13** — retire the old inflated 25→83→100 narrative (live §0.1 violation).

## Owners (ADR-025 assignment continues)
retriever/corpus → **data-engineer** · e2e runs → **ops-engineer** · analysis/stats/write-up →
**qa-engineer** + main thread. No new agents.

## Scope discipline
This is the LAST research sub-track before write-up. If T3.10 finds NO retriever beats MiniLM's
hit-rate, that is itself a finding (retriever ceiling on this KB) → report it honestly, don't keep
grinding (the oracle 0.409 remains the motivating headroom). Product surface (P3-C, FE) stays
deferred until after this.
