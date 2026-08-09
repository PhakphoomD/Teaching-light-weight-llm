**Table 10**

*WixQA Grounding Window Results*

| metric | narrow window | wider centred window | difference | 95% CI | p | provenance |
|---|---|---|---|---|---|---|
| pass rate (score >= 3) | 0.340 | 0.470 | +0.130 | [+0.072, +0.188] | 3.5e-08 | recomputed |
| ...where the answer's article was retrieved | 0.411 | 0.534 | +0.123 | [+0.050, +0.201] | 6.5e-05 | recomputed |
| ...where it was not | 0.199 | 0.343 | +0.144 | [+0.055, +0.234] | 8.2e-05 | recomputed |
| pass rate (score >= 4) | 0.007 | 0.007 | +0.000 | [-0.005, +0.005] | 1 | recomputed |
| mean judge score | 1.98 | 2.18 | +0.20 | -- | -- | recomputed |
| share scoring <= 1 | 0.298 | 0.232 | -0.067 | -- | -- | recomputed |
| answer length (words) | 0 | 0 | +0 | -- | -- | recomputed |
| reference coverage (continuous) | 0.361 | 0.403 | +0.042 | [+0.032, +0.053] | -- | from the committed printout |
| extraction ratio | 0.88 | 0.61 | -0.27 | -- | -- | from the committed printout |

*Note.* What changed when only the grounding window changed Retrieval was reused byte-for-byte from the previous rung, so the single difference between these two columns is which 2,400 characters of the same retrieved articles were placed in the prompt. 600 judged cells (200 questions x 3 seeds). Most rows are recomputed from the judged records; reference coverage and the extraction ratio are content-overlap metrics computed by the analysis script and are read from its committed printout, marked accordingly. Note the last three rows together: answers got shorter, covered more of the reference, and used a smaller share of what they were shown. Sources: runs/rag-wixqa, reports/rag-wixqa/wider-context-vs-narrow.txt.
