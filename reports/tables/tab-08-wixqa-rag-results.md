**Table 8**

*WixQA RAG Results*

| rung | pass >= 3 | Wilson 95% | pass >= 4 | mean score | score <= 1 | words | cells |
|---|---|---|---|---|---|---|---|
| No retrieval | 0.163 | [0.136, 0.195] | 0.000 | 1.76 | 0.342 | 68 | 600 |
| Retrieval (MiniLM over whole articles) | 0.315 | [0.279, 0.353] | 0.010 | 1.93 | 0.335 | 141 | 600 |
| Retrieval (BGE over 180-word chunks) | 0.340 | [0.303, 0.379] | 0.007 | 1.98 | 0.298 | 152 | 600 |
| ...plus a wider, chunk-centred grounding window | 0.470 | [0.430, 0.510] | 0.007 | 2.18 | 0.232 | 144 | 600 |

### Split by whether retrieval found the answer

| subset | without retrieval | with retrieval | difference | 95% CI | cells |
|---|---|---|---|---|---|
| the answer's article was retrieved | 0.127 | 0.400 | +0.273 | [+0.188, +0.355] | 330 |
| it was not | 0.207 | 0.211 | +0.004 | [-0.078, +0.085] | 270 |

### Judge-score distribution

| condition | score 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| No retrieval | 37 (6%) | 168 (28%) | 297 (50%) | 98 (16%) | 0 (0%) |
| Retrieval | 34 (6%) | 167 (28%) | 210 (35%) | 183 (30%) | 6 (1%) |
| Retrieval + wider window | 41 (7%) | 98 (16%) | 179 (30%) | 278 (46%) | 4 (1%) |

*Note.* Every value measured where the model had a real knowledge gap. WixQA: 200 expert-written question/answer pairs over 6,221 real help-centre articles, 3 seeds (600 judged cells per rung). Student qwen2.5:3b, judge Groq llama-3.1-8b-instant in reference-comparing mode -- only the judge ever sees the expert answer, never the student. Pass = score >= 3 ('correct'); the >= 4 column shows why that bar was chosen. The split table is the causal result: identical system, opposite outcome, decided only by whether retrieval delivered the answer. Recomputed from runs/rag-wixqa.
