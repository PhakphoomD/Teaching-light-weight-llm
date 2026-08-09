**Table 22**

*WixQA Reference Exposure*

| did the wider window reveal new reference text? | questions | narrow window | wider window | difference | 95% CI | McNemar p |
|---|---|---|---|---|---|---|
| no new reference text revealed | 117 | 0.328 | 0.405 | **+0.077** | [+0.006, +0.148] | 0.0086 |
| new reference text revealed | 83 | 0.357 | 0.562 | **+0.205** | [+0.112, +0.297] | 3.7e-07 |

*Note.* Whether the wider grounding window helped because it showed more of the graded answer. The knowledge-base articles this testbed indexes are the articles the expert answers were written from, so they quote them: by this project's own 12-token criterion 56.5% of questions had a verbatim run of the reference inside the text the model was shown (median 16 tokens, longest 123). That is deliberate and defended in the report, but it means the winning intervention -- a wider window -- could be helping simply by exposing more of the text the judge compares against. The test is to split the questions by whether the wider window revealed any *new* reference text. **It survives where it revealed none** (+0.077, interval excluding zero), and is 2.7 times larger where it did -- so the effect is real and its published size is inflated by exposure. Retrieval is byte-identical across the two rungs (600/600 cells), so the window is the only thing that changed. Sources: scripts/wixqa/measure_reference_exposure.py, reports/rag-wixqa/reference-exposure-strata.json.
