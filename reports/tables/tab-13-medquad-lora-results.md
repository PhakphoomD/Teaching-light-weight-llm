**Table 13**

*MedQuAD LoRA Results*

| metric | value |
|---|---|
| pass rate, original model | 0.868 |
| pass rate, fine-tuned | 0.576 |
| difference | -0.292 |
| 95% CI | [-0.360, -0.224] |
| held-out questions | 125 |
| seeds | 1, 2 |
| training loss | 1.98 -> 0.99 (2 epochs) |
| token accuracy | 0.59 -> 0.75 |
| answer length change | roughly 30-45% shorter — on four sampled questions the base model's 178, 158, 152 and 174 words became 95, 26, 122 and 141 *(quoted from docs/EXPERIMENT_RESULTS.md §7.7; the per-question answers were not committed, so this row is cited rather than recomputed)* |

*Note.* Every value measured for the fine-tune. QLoRA, 4-bit NF4, rank 16 on attention and MLP projections, 2 epochs over 506 training pairs, 23 minutes on an RTX 4060 laptop GPU. Evaluated on the same 125 held-out questions with the adapter on and off, so the difference isolates the adapter and nothing else. The base rate here (0.868) differs slightly from the 0.821 measured elsewhere because this evaluation ran on the HuggingFace stack rather than Ollama -- which is exactly why the comparison was run within one stack. Source: reports/lora-medquad/fine-tuned-vs-original.json.
