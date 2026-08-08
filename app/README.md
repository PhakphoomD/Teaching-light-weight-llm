# WixQA RAG engine — the before/after comparison generator (T3.15)

A small, local, honest RAG core: a 3B model (`qwen2.5:3b` via Ollama) grounds on the Wix
help-centre KB and answers each question **three ways**, so the difference *is* the finding.
It runs fully local; no ground-truth answer ever reaches the model at inference (§0.2).

> **No UI.** A Streamlit chat was prototyped and removed — it read as generic, and the portfolio's
> value is the honest *results*, not a chat box. What this module produces is the **comparison data**
> the results tables (T3.16) and narrative (T3.17) present.

## What it produces
`build_showcase.py` runs a curated set of WixQA questions through the engine and writes
`reports/rag-wixqa/demo-showcase.jsonl` — per question, the answer from each lane plus (if a judge
is reachable) its 0–4 score:

- **① no-RAG vs ② RAG** → the knowledge lift (**+0.152**, ADR-030): the base 3B often answers a
  proprietary-product question confidently *wrong*; grounding fixes it.
- **② narrow (900) vs ③ wide (2400, chunk-centred)** → the **delivery** lever (**+0.130**, ADR-033):
  showing more of the retrieved article was worth ~5× a better retriever, at zero inference cost.
- optional **④ + self-refine** → the honest null (ADR-032).

The curated set deliberately includes **gold-retrieved** (RAG helps) *and* **gold-missed** (RAG
limited) questions — the honest tug-of-war, not a cherry-pick.

## Run
```bash
# Ollama must be running with qwen2.5:3b; the WixQA index must exist
#   (indexes/wixqa-help-centre/ — rebuild via scripts/wixqa/build_index.py on a fresh clone)
& "C:\Users\ham25\.conda\envs\tlw\python.exe" app/build_showcase.py --per-set 3
```

## Honest scope
RAG helps here because WixQA is a **real knowledge gap** and the KB genuinely contains the answers.
On a domain the model already knows (general medical QA) RAG did **not** help — the two-testbed point.
The engine uses the committed **MiniLM** index (hit-rate 0.55, the ADR-030 retriever) for speed; the
published winner is `bge_chunk` (0.665), but the delivery lever shown here is retriever-independent.

## Files
- `engine.py` — retrieval + grounding (narrow/wide) + answer + compare; reuses `src/tlw/wixqa`.
- `build_showcase.py` — writes `reports/rag-wixqa/demo-showcase.jsonl` (the curated before/after set).
