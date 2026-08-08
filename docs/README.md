# Documentation index — start here

This project asked a simple question: **what actually makes a small local LLM better at one domain,
and what only looks like it does?** Everything below is the answer, measured on held-out data with
confidence intervals, on a codebase rebuilt so that its own evaluation cannot leak the answer key.

## Read in this order

| # | Document | What it gives you | Time |
|---|---|---|---|
| 1 | **[EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md)** | **The whole result in one place.** The law, the evidence chain, product implications, limitations, and every number with its source. | ~10 min |
| 2 | [TRACK_A_RESULTS.md](TRACK_A_RESULTS.md) | Does the teaching loop work? Self-refinement **+0.091**; an independent teacher **+0.003 (nothing)**. | ~5 min |
| 3 | [WIXQA_RESULTS.md](WIXQA_RESULTS.md) | RAG where the model genuinely lacks the knowledge: **+0.152**, the dose-response proof, the grounding-delivery finding (**+0.130**), and Loop+RAG. | ~10 min |
| 4 | [RAG_RESULTS.md](RAG_RESULTS.md) | RAG where the model already knows the domain: **no effect** (−0.005), and why that null is structural. | ~5 min |
| 5 | [PRODUCT_RESULTS.md](PRODUCT_RESULTS.md) | LoRA fine-tuning on reference answers: **−0.292**, it hurts — and exactly why. | ~4 min |
| 6 | [RAG_RELIABILITY_ANALYSIS.md](RAG_RELIABILITY_ANALYSIS.md) | Does RAG help *reliability* on the hard tail, rather than the average? | ~4 min |

## If you only read one thing

[**EXPERIMENT_RESULTS.md**](EXPERIMENT_RESULTS.md). It states the finding — *RAG helps only when the retrieved text actually
contains the answer, and the biggest lever turned out to be how that text is delivered into the
prompt, not which retriever produced it* — and backs every claim with a number, a CI and a log.

## Where the evidence lives

- **`reports/`** — the committed, human-readable outputs behind the numbers (scores, analysis
  printouts). Start at [`reports/README.md`](../reports/README.md).
- **`runs/`** — raw run artifacts, grouped by the question each study answers. Gitignored except the
  small evidence files; every one is rebuildable from a config and a seed.

## Other directories here

| Path | What it is |
|---|---|
| `plan/` | Task specifications and design documents — one per task (`T*.md`), plus the specs behind each decision. How the work was planned before it was run. |
| `audit/` | The audits that started the rebuild: the code map, the ground-truth leakage census, the environment review. |
| `archive/` | Superseded documents, kept with a banner explaining what was wrong and which ADR corrected it. Retained deliberately — the correction is part of the honest record. |

## The rules everything here follows

Decisions live in `.claude/rules/decisions.md` (ADR log) and the constitution in
`.claude/rules/00-index.md`. The two that shape these documents most:

- **§0.1 Honesty over optics** — every reported number must match its source log. Negative results are
  reported as plainly as positive ones, and most of the findings here are negative.
- **§0.4 Evidence-backed** — a claim cites a file, a line, or a command that was actually run.
