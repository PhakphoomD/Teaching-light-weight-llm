**Table 1**

*All Interventions Provenance*

| intervention | effect | 95% CI | significance | testbed | seeds | pass bar | source |
|---|---|---|---|---|---|---|---|
| Teacher feedback, over self-refinement | **+0.003** | [-0.021, +0.029] | p=1 | MedQuAD, 125 held-out | 3 | score >= 4 | `runs/teaching-loop-medquad` |
| Self-refinement, over a single attempt | **+0.091** | [+0.051, +0.133] | p=2.0e-06 | MedQuAD, 125 held-out | 3 | score >= 4 | `runs/teaching-loop-medquad` |
| Retrieval, on a domain the 3B knows | **-0.005** | [-0.067, +0.056] | p=0.91 | MedQuAD, 125 held-out | 3 | score >= 4 | `runs/rag-medquad` |
| Retrieval, on the same domain with a 7B | **-0.069** | [-0.120, -0.019] | p=4.1e-04 | MedQuAD, 125 held-out | 3 | score >= 4 | `runs/rag-medquad` |
| Retrieval, on a domain the 3B does not know | **+0.152** | [+0.092, +0.213] | p=5.2e-11 | WixQA, 200 expert questions | 3 | score >= 3 | `runs/rag-wixqa` |
| A stronger retriever | **+0.025** | [-0.028, +0.080] | p=0.27 | WixQA, 200 expert questions | 3 | score >= 3 | `runs/rag-wixqa` |
| A wider, better-placed grounding window | **+0.130** | [+0.072, +0.188] | p=3.5e-08 | WixQA, 200 expert questions | 3 | score >= 3 | `runs/rag-wixqa` |
| Self-refinement added on top of retrieval | **-0.015** | [-0.068, +0.038] | p=0.77, single seed | WixQA, 133 questions whose article was retrieved | 1 — directional | score >= 3 | `runs/rag-wixqa/pilots` |
| Fine-tuning on reference answers | **-0.292** | [-0.360, -0.224] | -- | MedQuAD, 125 held-out | 2 | score >= 4 | `reports/lora-medquad` |

*Note.* Every lever in the overview figure, with what it was measured on The companion to figure 1. Two pass bars appear here and they are not interchangeable: MedQuAD is scored at 'correct AND complete' because the model already answers most of it, and WixQA at 'correct' because a 3B given one support article cannot match an expert answer's completeness — so the columns are read as separate studies that happen to share an axis of *change*, which is the one thing that is comparable. The single-seed row is labelled directional wherever it appears, including on the figure itself.
