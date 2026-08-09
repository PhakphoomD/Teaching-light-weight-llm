**Table 16**

*Predictions vs Outcomes*

| what was predicted | prediction (range) | outcome | verdict |
|---|---|---|---|
| Stage 1: pass rate where the answer was retrieved | 0.45 (0.38-0.52) | 0.534 | **outside** the range, above it |
| Stage 1: aggregate pass rate | 0.36 (0.32-0.41) | 0.470 | **outside** the range, above it |
| Stage 1: aggregate rate at the *completeness* bar | 0.03 (0.01-0.06) | 0.007 | **outside** the range, **below** it |
| Stage 2: pass rate after self-refinement | 0.47 (0.42-0.53) | 0.556 | **outside** the range, above it |
| Stage 2: completeness bar after self-refinement | 0.06 (0.02-0.11) | 0.008 | **outside** the range, **below** it |
| Stage 2: gain in how much of the reference the answer covers | +0.04 (+0.00 to +0.09) | +0.031 | inside the stated range |
| The mixture model's forecast for the stronger retriever | 0.337 | 0.340 | correct, within 0.003 -- made before the run |
| 'A broken retriever explains the null' | reranking should recover it | 0.760, worse than plain | falsified |
| 'Too small a corpus explains the null' | 24x more passages should recover it | 0.816, still below unaided | falsified |
| '0.400 is the model's ceiling once the answer is retrieved' | should not move | rose to 0.534 once delivery was fixed | superseded -- it was a delivery ceiling |
| The pre-registered stop rule for the loop study | if the pilot is flat, do not run three seeds | pilot was flat; the run was not done | fired as designed |

*Note.* What was predicted before running, and what actually happened. Predictions were recorded before the corresponding runs so that being wrong would be visible rather than reinterpretable afterwards. Of the six numeric predictions the capstone protocol recorded with ranges, **5 landed outside their range** -- three above and two below, the low ones both on the completeness bar the intervention was built to move. An earlier version of this table showed two of them; the omission was found by an external review and the scoring is now computed from the runs rather than typed, which is why it can no longer drift in the author's favour. The misses share a cause: an observational correlation was trusted that a controlled comparison later contradicted -- which is the argument for running the controlled comparison. One prediction, built as an explicit mixture of two measured conditional rates, landed within 0.003 of the outcome, and that accuracy is stronger evidence for the mechanism than the size of any single effect. Sources: docs/protocol/2026-07-25-wixqa-grounding-and-loop-plan.md (the ranges), runs/rag-wixqa/ (the outcomes).
