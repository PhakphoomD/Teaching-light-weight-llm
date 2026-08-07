# Reports — the committed evidence behind every published number

`runs/` holds the raw artifacts of each experiment and is gitignored (they are large and rebuildable).
**This directory holds the small, human-readable outputs that a reader needs in order to check a claim
without rerunning anything** — scores, analysis printouts, offline measurement tables. These *are*
tracked in git.

That split is deliberate: track what a reader must check, ignore what a command can rebuild.

## One directory per study, named by the question it answers

| Study | The question it answers | Headline | Written up in |
|---|---|---|---|
| `teaching-loop-medquad/` | Does an iterative teacher–student loop make a small model better? | Self-refinement **+0.091**; independent teacher **+0.003 (nothing)** | [TRACK_A_RESULTS](../docs/TRACK_A_RESULTS.md) |
| `rag-medquad/` | Does RAG help when the model *already knows* the domain? | **−0.005 — no effect**; it significantly *hurts* the larger model (−0.069) | [RAG_RESULTS](../docs/RAG_RESULTS.md) |
| `rag-medquad-fair-tests/` | Is that null just a bad retriever or too small a corpus? | No — a better reranker and a 24× corpus both fail. The null is structural. | [RAG_RESULTS](../docs/RAG_RESULTS.md) |
| `rag-medquad-reliability/` | Does RAG help *reliability* on hard questions, not the average? | Baseline pass@5 **exceeds** RAG's — RAG trades reliability for recovery | [RAG_RELIABILITY_ANALYSIS](../docs/RAG_RELIABILITY_ANALYSIS.md) |
| `student-prompt-medquad/` | Does the student's prompt style matter? | 0.840 vs 0.864, p=0.58 — **no** | ADR-029 |
| `rag-wixqa/` | Does RAG help when the model genuinely *lacks* the knowledge? | **+0.152**; then **+0.130 more** from fixing how the retrieved text is delivered | [WIXQA_RESULTS](../docs/WIXQA_RESULTS.md) |
| `lora-medquad/` | Does fine-tuning on reference answers help? | **−0.292 — it hurts** | [PRODUCT_RESULTS](../docs/PRODUCT_RESULTS.md) |
| `judge-calibration/` | Is the judge trustworthy enough to measure any of this? | Both candidate judges failed the probe; the response was to raise the bar and hold one judge fixed | ADR-022, T2.3 |

## Naming

A name must read like English to someone who has never seen this repo. The directory carries a short
human label; the exact experimental condition lives in the `manifest.json` beside the run, never
encoded into the path. Words, not codes — `wider-context`, not `chunk2400`.

Numbers appear in a name **only where step N+1 genuinely contains step N** — `rag-wixqa/` is a ladder
(no RAG → RAG → better retriever → wider context), so it is numbered. `rag-medquad/` is a 2×2, so it
is not: numbering it would imply the last arm is the best one, when in fact it is the worst.

## Reproducing any number

Each study directory carries the exact command that regenerates its report. The offline analyses need
no API key and no GPU:

```bash
python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A
python -m src.tlw.analysis --runs-dir runs/rag-medquad --rag
python scripts/wixqa/analyze_three_seeds.py
python scripts/wixqa/analyze_dose_response.py
```

> **Status:** this directory is populated during phase 4 of the ADR-034 restructure
> (`docs/plan/MIGRATION_CHECKLIST.md` §P4). Until that phase lands, the reports named above still
> live beside their raw runs; the table already reflects where each one is going.
