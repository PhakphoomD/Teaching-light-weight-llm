**Table 12**

*WixQA Loop Plus RAG Results*

| metric | single pass | with refinement | difference | 95% CI | p |
|---|---|---|---|---|---|
| pass rate (score >= 3) | 0.571 | 0.556 | -0.015 | [-0.068, +0.038] | 0.77 |
| pass rate (score >= 4) | 0.015 | 0.008 | -0.008 | [-0.023, +0.000] | 1 |
| mean judge score | 2.353 | 2.346 | -0.008 | -- | -- |
| share scoring <= 1 | 0.165 | 0.173 | +0.008 | -- | -- |
| answer length (words) | 141 | 164 | +23 | -- | -- |
| reference coverage | 0.414 | 0.445 | +0.031 | [+0.018, +0.047] | -- |
| extraction ratio | 0.63 | 0.68 | +0.05 | -- | -- |
| the model judged itself already complete | -- | 79/133 (59%) | -- | -- | -- |

### Split by how good the answer already was

| score before refining | cells | mean change | improved | worsened |
|---|---|---|---|---|
| 0 | 9 | +0.33 | 3 | 0 |
| 1 | 13 | +0.38 | 3 | 0 |
| 2 | 35 | +0.00 | 3 | 3 |
| 3 | 74 | -0.11 | 0 | 7 |
| 4 | 2 | -0.50 | 0 | 1 |

### What a perfect gate would be worth

| policy | pass rate | Wilson 95% | vs single pass |
|---|---|---|---|
| single pass, never refine | 0.571 | [0.486, 0.652] | +0.000 |
| always refine | 0.556 | [0.472, 0.638] | -0.015 |
| refine only weak answers (oracle) | 0.609 | [0.524, 0.688] | +0.038 |
| refine when the model says it is not done | 0.571 | [0.486, 0.652] | +0.000 |

*Note.* Every value measured when the loop and retrieval ran together. Two grounded self-refinement rounds on top of the best retrieval configuration, 133 gold-retrieved questions, seed 42 only -- a pre-registered stop rule ended the study here because the pilot came back flat, so every number below is directional and is labelled as such wherever it appears. The mechanism demonstrably works (reference coverage rises, and the interval on that rise excludes zero) while the judged bar does not move, which is the whole finding: making an answer contain more of the right material is not the same as making it correct. Recomputed from runs/rag-wixqa/pilots; the two coverage rows come from the committed analysis printout.
