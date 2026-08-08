**Table 2**

*MedQuAD Dataset Report*

| domain | raw | clean | noise rate | duplicate answers | templated questions | median answer words |
|---|---|---|---|---|---|---|
| Cancer | 370 | 336 | 0.162 → 0.000 | 26 → 0 | 60% | 129 → 125 |
| Diabetes, digestive, kidney | 656 | 631 | 0.014 → 0.000 | 3 → 0 | 71% | 118 → 124 |
| Disease control | 211 | 205 | 0.000 → 0.000 | 1 → 0 | 71% | 100 → 105 |
| Genetic and rare | 4,511 | 3,031 | 0.328 → 0.000 | 50 → 0 | 100% | 140 → 108 |
| Heart, lung, blood | 246 | 246 | 0.000 → 0.000 | 0 → 0 | 80% | 174 → 174 |
| General medical QA | 1,982 | 1,940 | 0.004 → 0.000 | 2 → 0 | 56% | 117 → 118 |
| Genetics Home Reference | 4,452 | 3,635 | 0.000 → 0.000 | 404 → 0 | 78% | 70 → 93 |
| **All domains** | **12,428** | **10,024** |  |  |  |  |

### Readiness of the split used for the experiments

| dimension | score | band |
|---|---|---|
| structural | 100.0 | green |
| cleanliness | 100.0 | green |
| uniqueness | 97.3 | green |
| complexity | 100.0 | green |
| diversity | 72.6 | green |
| answerability | 99.6 | green |
| quality | 76.7 | green |
| **overall** | **93.4** | **READY** |

*Note.* The dataset, before and after, and whether it was fit to measure on **When this happened matters: after the audit, not before the experiments.** The original runs (November 2025) used an unidentified medical question-answer dump with no held-out split; everything below — the source, the licence, the cleaning, the 506/125 split — was established in July 2026 as part of the repair (see tab-21). MedQuAD (Ben Abacha & Demner-Fushman 2019, CC BY 4.0): real question-answer pairs auto-extracted from twelve NIH sites, which is why the raw text carries boilerplate, referral phone numbers and duplicated template answers. The readiness score is a published-rubric assessment of the split the experiments actually used (631 records, 506 train / 125 held-out), scored against thresholds set before the assessment ran. Two honest notes: uniqueness is 97.3 rather than 100 because MedQuAD reuses one NIH advice template across related conditions — the same property that later required a verbatim-block scrub in the retrieval corpus; and 'growth hormone receptor' is a mislabelled source, it is Genetics Home Reference. Sources: data/clean/*_report.json, data/clean/*_readiness_rag.json.
