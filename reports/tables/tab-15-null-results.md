**Table 15**

*Null Results*

| what was tested | what came back | what it means |
|---|---|---|
| An independent teacher on top of self-refinement | +0.003 [-0.021, +0.029], p=1.00 | the loop's benefit is the rewriting, not the teacher |
| Similarity to the reference, across all four arms | flat at ~0.70 while correctness rose 9pt | why correctness and similarity were never merged into one score |
| Retrieval on the 3B, MedQuAD | -0.005 [-0.067, +0.056], p=0.91 | no net effect |
| Retrieval on the 7B, MedQuAD | -0.069 [-0.120, -0.019], p=0.0004 | significantly harmful -- the stronger the model, the worse retrieval's distraction cost |
| 3B with retrieval against a plain 7B | -0.088 [-0.136, -0.043] | retrieval does not substitute for model size |
| Reranking to matching question type | 0.760 against 0.800 plain and 0.864 unaided | the 'better retriever' hypothesis, falsified |
| A 24x larger library | 0.816 against 0.864 unaided, p=0.26 | the 'bigger corpus' hypothesis, falsified |
| A more detailed student prompt | 0.840 against 0.864, p=0.58 | the prompt was not the lever |
| A hardened 'ignore irrelevant passages' prompt | 0.80 -> 0.56 | backfired; reverted |
| Groundedness as a diagnostic | ~0.81 but 61% of calls returned nothing usable | the metric was too weak at this judge quality to rely on |
| Retrieval's effect on pass@5 | 0.89 -> 0.74 broad, 0.69 -> 0.38 on gaps | grounding trades sample diversity for consistency |
| Cheap uncertainty gates | correlation ~0; an LLM gate fired 99% or 0% by prompt tone | a confidently wrong small model cannot flag its own gaps |
| BM25 alone | hit@3 0.465 against 0.550 | lexical search underperforms the dense baseline |
| Hybrid BM25 + dense fusion | hit@3 0.605 against 0.665 | fusion dragged the strong retriever down |
| Cross-encoder reranking at k=3 | 0.640 against 0.665 | helps at k=5 and 10, costs precision at 3 |
| The aggregate retriever upgrade | +0.025 [-0.030, +0.078], p=0.27 | not significant -- the proof of the mechanism is the pattern, not this number |
| Retrieval where the answer was not retrieved | +0.004 | no lift, as the law predicts |
| The 'complete' bar on WixQA | 0.007 -> 0.007, p=1 | structurally unreachable: the full source article holds only ~72% of the expert answer |
| Self-refinement on top of retrieval | -0.015 [-0.068, +0.038], p=0.77 | does not compound |
| Mean judge score after refinement | 2.35 -> 2.35 | no movement at all |
| Refinement's effect on catastrophes and length | 0.165 -> 0.173; 141 -> 164 words | slightly worse, and it padded despite being told not to |
| The model's own refinement gate | +0.000 against an oracle's +0.038 | captures none of the available headroom |
| Extraction ratio under the best intervention | 88% -> 61% | reported as a worsening; it is the remaining bottleneck |
| Fine-tuning on reference answers | -0.292 [-0.360, -0.224] | large and significant harm |
| The single-seed grounding pilot | +0.090 [-0.008, +0.188], p=0.096 | not significant at pilot size; only the 3-seed run reached significance |
| Judge calibration | both candidate judges failed the probe | the response was to raise the pass bar and hold one judge fixed, not to tune until it passed |

*Note.* Everything that did not work, stated as a result Twenty-six measurements that came back null, negative or not significant. They are listed together because they are the substance of the project rather than a footnote to it: three of them are hypotheses this project raised and then falsified with its own data, and two are cases where a well-supported published method did not transfer. A result set with no negatives in it has usually been filtered. Sources per row in the objective tables.
