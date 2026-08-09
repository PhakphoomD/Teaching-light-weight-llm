**Table 7**

*MedQuAD RAG Reliability*

| what is being asked | without retrieval | with retrieval | difference | why it matters |
|---|---|---|---|---|
| per-attempt accuracy | 0.606 | 0.640 | +0.034 | is any single answer more likely to be right |
| right at least once in 5 attempts | 0.886 | 0.743 | -0.143 | can it get there at all |
| right on **every** one of 5 attempts | 0.343 | 0.400 | +0.057 | **the one a product cares about** |

### The subset where a knowledge gap actually exists

| what is being asked | without retrieval | with retrieval | difference |
|---|---|---|---|
| per-attempt accuracy | 0.231 | 0.354 | +0.123 |
| right at least once in 5 | 0.692 | 0.385 | -0.308 |
| **right on all 5 attempts** | **0 of 13** | **4 of 13** | **+0.308** |

These 13 are the questions the model never once answered correctly on its own, across all three seeds of the original run — a real knowledge gap rather than an unlucky sample. It is the only place in the project where retrieval made answers *dependable*: not one of them was answered correctly on all five attempts without retrieval, and 4 were with it. That is the product-shaped version of the finding, and it is invisible in the aggregate.

*Note.* Three different questions about the same runs, with three different answers. The same 35 questions answered 5 times each, with and without retrieval. Accuracy per attempt and dependability are not the same measurement, and retrieval moves them in opposite directions: grounding makes the model more consistent, which raises the chance that any given answer is right and lowers the chance that at least one of several attempts stumbles onto the answer. If a system is allowed several tries, sampling diversity is worth something and grounding spends it. Method caveat, stated because it bounds the reading: this set was chosen because the baseline had failed on it, so only the difference between the two columns is interpretable — neither level is, and a set selected on prior failure will regress toward the mean on its own. A second, larger sweep (125 questions x 8 seeds) also sits under the same study directory, but it was judged with a different model and returns levels far below every other result here — so it is named rather than pooled in. Blending two instruments into one number is the kind of thing this project exists to retire. Recomputed from runs/rag-medquad-reliability/hard-questions-only.
