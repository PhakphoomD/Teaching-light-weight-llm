**Table 9**

*WixQA Retriever Comparison*

| retriever | hit@1 | hit@3 | hit@5 | hit@10 | MRR | vs baseline @3 | build time |
|---|---|---|---|---|---|---|---|
| BGE embeddings over 180-word chunks | 0.420 | **0.665** | 0.750 | 0.845 | 0.570 | +0.115 | 163s |
| MiniLM embeddings over 180-word chunks | 0.390 | **0.645** | 0.740 | 0.840 | 0.540 | +0.095 | 40s |
| BGE chunks, then a cross-encoder rerank | 0.365 | **0.640** | 0.785 | 0.880 | 0.537 | +0.090 | 184s |
| BGE embeddings over whole articles | 0.395 | **0.620** | 0.705 | 0.825 | 0.532 | +0.070 | 65s |
| BM25 and BGE fused by reciprocal rank | 0.395 | **0.605** | 0.705 | 0.790 | 0.529 | +0.055 | 14s |
| MiniLM over whole articles (the starting point) | 0.320 | **0.550** | 0.680 | 0.800 | 0.474 | +0.000 | 23s |
| BM25 keyword search alone | 0.280 | **0.465** | 0.525 | 0.620 | 0.396 | -0.085 | 15s |

### Which change did the work

| change | gain in hit@3 |
|---|---|
| splitting articles into chunks | +0.095 |
| a stronger encoder | +0.070 |
| both together | +0.115 |

The intuitive lever — a stronger embedding model — is the smaller of the two. Splitting long articles before embedding matters more, because the encoder only ever read their first few hundred tokens.

*Note.* Seven retrievers, ranked offline before any of them was run end to end. Hit rate is the share of the 200 questions whose answer-bearing article appears in the top k, over 6221 help-centre articles. No model calls, so the whole ladder costs minutes rather than GPU-days -- which is the point: it decided which single variant was worth an end-to-end run. Chunking matters more than the encoder (+0.095 versus +0.070), because whole-article embedding truncates long articles at roughly 256 tokens. The honest negatives are in here too: keyword search alone is well below the dense baseline, fusing the two drags the strong retriever down, and a cross-encoder rerank helps at k=5 and k=10 while costing precision at k=3, which is the k actually used. Source: reports/rag-wixqa/retriever-hitrate.json.
