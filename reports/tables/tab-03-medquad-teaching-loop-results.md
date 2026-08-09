**Table 3**

*MedQuAD Teaching Loop Results*

| arm | pass rate | Wilson 95% | n | similarity to reference | mean rounds | teacher calls | student tokens |
|---|---|---|---|---|---|---|---|
| One attempt, no feedback | 0.821 | [0.779, 0.857] | 375 | 0.715 | 1.00 | 0 | 99,308 |
| The model critiques and rewrites its own answer | 0.912 | [0.879, 0.937] | 375 | 0.698 | 1.28 | 0 | 239,429 |
| A larger model critiques it, without seeing the answer key | 0.915 | [0.882, 0.939] | 375 | 0.691 | 1.31 | 116 | 189,735 |
| The teacher is shown the answer key ⚠️ **leakage ceiling, not a result** | 0.940 | [0.903, 0.963] | 250 | 0.704 | 1.24 | 59 | 111,458 |

| comparison | difference | 95% CI | McNemar p | fixed / broke | paired cells |
|---|---|---|---|---|---|
| Self-refinement, over one attempt | +0.091 | [+0.051, +0.133] | 2.04e-06 | 43 / 9 | 375 |
| A teacher, over self-refinement | +0.003 | [-0.021, +0.029] | 1 | 16 / 15 | 375 |
| Showing the teacher the answer key ⚠️ **not a result — this is how far leakage inflates** | +0.025 | [-0.008, +0.061] | 0.21 | 15 / 8 | 250 |

*Note.* Every value measured in the loop ablation. 125 held-out MedQuAD questions x 3 seeds {13, 42, 123}. Student qwen2.5:3b (local), judge Groq llama-3.1-8b-instant, blind (it never sees the reference), pass = score >= 4. Intervals are Wilson for a level and a 10,000-resample paired cluster bootstrap over questions for a difference. Similarity to reference is a diagnostic and was never merged into the pass decision -- it stays flat while correctness rises nine points, which is why the two were kept apart. Recomputed from runs/teaching-loop-medquad.
