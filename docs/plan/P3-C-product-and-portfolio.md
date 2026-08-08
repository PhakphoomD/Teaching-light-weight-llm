# P3-C — Product demo + portfolio presentation (planned 2026-08-07 hub)

The research is complete and verified (ADR-024…034, `docs/RAG_LAW.md`). P3-C turns it into two
things a portfolio needs: a **runnable demo** (the product half of the vision) and an **accessible
narrative** (so a reviewer grasps it in minutes), backed by **professional visualizations**.

## Three artifacts, three audiences — keep them separate (do NOT merge into one file)
| Artifact | For whom | Home (structure.md v3) | Task |
|---|---|---|---|
| Local RAG demo app | someone who wants to *try* it | `app/` (planned dir — create now) | **T3.15** |
| Result visualizations | support the narrative + RAG_LAW | `reports/figures/` (tracked) | **T3.16** |
| Narrative notebook | a hiring manager / reviewer reading the story | `notebooks/` (new, clean) | **T3.17** |

`docs/RAG_LAW.md` stays the **rigorous, result-first** artifact (technical reader). The narrative
notebook is the **journey-first, accessible** version — complementary, not a duplicate; it links to
RAG_LAW as "the rigorous companion".

## Narrative outline (T3.17) — the user's arc, senior-refined
0. **HOOK (1–2 sentences, before the chronology):** the payoff up front — "a 3B on a laptop; the
   biggest accuracy win was a prompt-construction fix worth 5× a better retriever; and we caught our
   own inflated numbers." A skimming reviewer must get the result in 10 seconds.
1. **Purpose & painpoint:** SMEs need domain AI but can't afford big models / cloud; small models
   hallucinate. Business value + real usage (a local, private, one-domain Q&A assistant).
2. **The data-cleaning work:** MedQuAD → cleaned pipeline (the reusable `tools/dataset/` blocks).
3. **V1 (the original system):** teacher–student loop + memory — what it was, why it seemed to work.
4. **What went wrong (the honest core — lean in, don't apologise):** ground-truth leakage +
   similarity-metric → the "25→83→100" was an artefact; how the audit caught it; the leak-proof rebuild.
5. **The current work & results:** the unified law (retrieval→delivery→extraction), two-testbed
   design, the delivery finding, Loop+RAG doesn't compound, LoRA hurts — with the live charts (T3.16).
6. **The demo:** the working product (embed a screenshot/GIF from T3.15) — "and here it runs."
7. **What this demonstrates (NEW closer — the hire signal):** honest evaluation, catching one's own
   leakage, scope discipline, mechanistic reasoning, reproducibility-from-clone.

## Sequencing
```
T3.15 demo app  ┐  (parallel)
T3.16 viz       ┘→ T3.17 narrative notebook (consumes both: embeds viz + a demo screenshot)
```
Retire the dead `notebooks/experiment.ipynb` (V1-era, flagged in T2.9) — replace, don't resurrect.

## Optional high-value add (flagged, not required)
The same narrative can be published as a **shareable web Artifact** (a "send this link" portfolio
page that works without a Python env). The notebook is the in-repo reproducible version; the
Artifact is the outward-facing one. Decide at the T3.17 gate.

## Owners (ADR-025 assignment continues; no new agents)
demo app → **ops-engineer** + **codebase-steward** · visualizations → **qa-engineer** + main thread ·
narrative → **main thread**. FE is finally in scope (was deferred through P0–P3-E).
