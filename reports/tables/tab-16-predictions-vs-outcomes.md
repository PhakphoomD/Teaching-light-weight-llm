**Table 16**

*Predictions vs Outcomes*

| what was predicted | prediction | outcome | verdict |
|---|---|---|---|
| The mixture model's forecast for the stronger retriever | 0.337 | 0.340 | correct, within 0.003 -- made before the run |
| The grounding-window repair | about 0.36 | 0.470 | **wrong** -- badly under-predicted |
| Self-refinement on top of retrieval | +3 points | -1.5 points | **wrong** -- the sign flipped |
| 'A broken retriever explains the null' | reranking should recover it | 0.760, worse than plain | falsified |
| 'Too small a corpus explains the null' | 24x more passages should recover it | 0.816, still below unaided | falsified |
| '0.400 is the model's ceiling once the answer is retrieved' | should not move | rose to 0.534 once delivery was fixed | superseded -- it was a delivery ceiling |
| The pre-registered stop rule for the loop study | if the pilot is flat, do not run three seeds | pilot was flat; the run was not done | fired as designed |

*Note.* What was predicted before running, and what actually happened Predictions were recorded before the corresponding runs so that being wrong would be visible rather than reinterpretable afterwards. Two were wrong, and both for the same reason: an observational correlation was trusted that a controlled comparison later contradicted -- which is the argument for running the controlled comparison. One prediction, built as an explicit mixture of two measured conditional rates, landed within 0.003 of the outcome, and that accuracy is stronger evidence for the mechanism than the size of any single effect. Sources: docs/EXPERIMENT_RESULTS.md §7.4-7.6, docs/EXPERIMENT_RESULTS.md §10.
