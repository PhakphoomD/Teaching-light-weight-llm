**Table 18**

*Compute and Cost*

### Where the work actually happens

| what runs where |  |
|---|---|
| the model that answers | qwen2.5:3b, locally, on an RTX 4060 laptop GPU (8GB) |
| the retrieval index | local; 6,221 articles rebuild in about 3 minutes |
| the fine-tune | QLoRA 4-bit, 23 minutes on the same laptop GPU |
| the judge | a hosted API, free tier — the only thing not local, and it is the *measuring* instrument, not the product |
| cloud spend | **nothing** |

### The rebuilt experiments

| what was run | seeds | wall clock | student calls | student tokens | teacher calls | judge calls |
|---|---|---|---|---|---|---|
| Loop ablation, one arm (125 questions x 3 seeds) | 3 | 2.0 h | 375 | 99,308 | 0 | 375 |
| ...the arm that also calls a cloud teacher | 3 | 2.9 h | 491 | 189,735 | 116 | 491 |
| Retrieval on MedQuAD, one arm | 3 | 0.7 h | 375 | 325,501 | 0 | 375 |

### And what the retired project spent, for comparison

| the retired project's phases | runs | questions | pass rate range | tokens |
|---|---|---|---|---|
| phase0 — warm-up: does the loop run end to end | 1 | 100 | 0.66 – 0.66 | 248,589 |
| phase1 — memory on vs off | 2 | 20 | 0.85 – 0.90 | 167,629 |
| phase2 — three teacher-feedback styles | 3 | 20 | 0.40 – 0.90 | 375,164 |
| phase3 — hyper-parameter grid | 12 | 20 | 0.25 – 1.00 | 1,331,298 |
| phase4 — does it transfer across medical domains | 4 | 10 | 0.80 – 1.00 | 113,847 |
| phase5 — baseline vs the full optimised system | 2 | 100 | 0.33 – 0.84 | 496,169 |
| phase6 — memory seeded with the reference answers | 3 | 20 | 0.75 – 1.00 | 224,283 |

At the rates the original project quoted for itself — $0.59/$0.79 per million tokens for the 70B teacher, $0.05/$0.08 for the 8B, 1 USD = 1.53 AUD — those 2,956,979 tokens cost between **A$1.46 and A$1.98**. It is a range, not a figure, because the runs recorded student and teacher totals but never split input from output, and the two are priced differently — so the bound runs from all-input to all-output. The retired write-up reported **A$0.50**, from a token count that was itself understated about threefold. Rates recovered from the deleted notebook (`docs/archive/v1-notebook-narrative.md`); token counts from the logs.

The earlier version pushed roughly four times the tokens through a cloud teacher to produce the result that was later retracted. The rebuild's largest single win — the grounding window — cost nothing at inference time at all.

*Note.* What the whole project cost to run. Wall-clock and call counts summed over each condition's seeds, from the run summaries. **Cloud spend was zero.** The student model runs locally on an RTX 4060 laptop GPU; the retrieval index is local and rebuilds in about three minutes; the fine-tune took 23 minutes on the same GPU. Only the judge and the teacher used a hosted API, both within a free tier — and that tier's shared daily limit is itself a finding worth passing on, since it forced the judging of one 600-answer study to resume across two days and is the reason judge budget is tracked in the run logs at all. The practical claim this supports: a small business can reproduce this on one ordinary machine. Recomputed from runs/**/summary.jsonl and logs/experiments/phase0..6/summary.jsonl.
