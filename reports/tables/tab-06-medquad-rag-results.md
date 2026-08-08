**Table 6**

*MedQuAD RAG Results*

| condition | pass rate | Wilson 95% | n | repetition |
|---|---|---|---|---|
| 3B alone | 0.821 | [0.779, 0.857] | 375 | 3 seeds |
| 3B + retrieval | 0.816 | [0.774, 0.852] | 375 | 3 seeds |
| 7B alone | 0.904 | [0.870, 0.930] | 375 | 3 seeds |
| 7B + retrieval | 0.835 | [0.794, 0.869] | 375 | 3 seeds |
| 3B + retrieval, matched question type | 0.760 | [0.678, 0.826] | 125 | seed 42 only |
| 3B + retrieval, 24x larger library | 0.816 | [0.739, 0.874] | 125 | seed 42 only |
| 3B alone, more detailed prompt | 0.840 | [0.766, 0.894] | 125 | seed 42 only |

### Differences

| comparison | difference | 95% CI | McNemar p | fixed / broke |
|---|---|---|---|---|
| Retrieval, on the 3B | -0.005 | [-0.067, +0.056] | 0.91 | 37 / 39 |
| Retrieval, on the 7B | -0.069 | [-0.120, -0.019] | 0.00041 | 13 / 39 |
| 3B + retrieval, against a plain 7B | -0.088 | [-0.136, -0.043] | 3.4e-06 | 9 / 42 |

### Where the change landed

| outcome | question-runs |
|---|---|
| both answered correctly | 269 |
| both failed | 30 |
| retrieval repaired it | 37 |
| ...of those, on questions the baseline never got right | 15 |
| retrieval broke it | 39 |
| ...of those, on questions the baseline always got right | 35 |

### The hard-tail probe

| set | without retrieval | with retrieval | difference | 95% CI | cells |
|---|---|---|---|---|---|
| Retrieval on the hard tail (5 seeds) | 0.606 | 0.640 | +0.034 | [-0.086, +0.166] | 175 |

### Diagnostics that were measured but never merged into the pass decision

| diagnostic | value | how it was treated |
|---|---|---|
| retrieved passages dropped for sharing wording with the held-out answer | 30 across 3 seeds | the run-time anti-leak filter, counted rather than assumed to be zero |
| groundedness of the answer in its retrieved passages | 0.809 — but unparsed for 61% of answers (228 of 375) | kept as a diagnostic and never allowed near the pass decision; at this judge quality the null rate makes the mean indicative at best |

*Note.* Every value measured on the domain the model already knew MedQuAD, 125 held-out questions, pass = judge score >= 4. The headline arms ran 3 seeds; the three rescue attempts ran one seed each and are labelled as such rather than presented alongside the others as equals. The mechanism table is the reason the aggregate is a null rather than a non-event. The reliability rows use a set selected on prior failure, so only the difference is interpretable, not either level. Recomputed from runs/rag-medquad, runs/rag-medquad-fair-tests, runs/student-prompt-medquad, runs/rag-medquad-reliability.
