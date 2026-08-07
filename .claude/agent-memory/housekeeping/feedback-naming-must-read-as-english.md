---
name: feedback-naming-must-read-as-english
description: Names in this repo must read like English to an outsider; the user rejects encoded/abbreviated "AI generic" names even when they are precise
metadata:
  type: feedback
---

**Rule: a name must read like English to someone who has never seen this repo.** If understanding
it requires knowing what `bge_chunk`, `chunk2400`, `armA` or `goldonly` mean, the name has failed.
Do not encode the whole experimental condition in a path — the path gets a short human label, and
the exact condition goes in a `manifest.json` beside it.

**Why:** on 2026-08-07 the user rejected a proposed convention that was internally consistent and
unambiguous but, in their words, still hard for a *real person* to read and "AI generic". The
failing example was
`runs/wixqa-rag/rag-bge_chunk-chunk2400-selfrefine-goldonly-pilot/seed42.jsonl` — where the token
`chunk` carried two unrelated meanings (retriever chunking vs grounding-window size) and the
separator scheme (hyphen between dimensions, underscore inside values) was a rule the reader had
to be taught. Their standard: this is a portfolio repo an employer will read.

**How to apply:** prefer `wider-context` over `chunk2400`, `better-retriever` over `bge_chunk`,
`baseline` / `self-refine` / `teacher-feedback` over `armA`/`armB`/`armC`. One separator per kind
of thing, and only kinds the reader already knows — hyphens for folders and artifacts, underscores
for `.py` files because that is PEP 8, not a house rule. Use ordinal prefixes (`1-`, `2-`) only
where step N+1 genuinely contains step N; never on a factorial design, because that invents a
progression and implies the last one is best. Precision is not sacrificed — it moves into the
manifest. Verify no two conditions collide onto one name before proposing the mapping.

Applies to folders, run artifacts, script filenames and report filenames alike. See
[[structure-audit-2026-08]] and [[repo-recurring-offenders]].
