**Table 4**

*V1 Claims vs Logs*

| what was claimed | what the log holds | the difference | source |
|---|---|---|---|
| pass rate 25% -> 83% | 0.33 -> 0.84 | inflated at both ends; the real logged gain is +51pt, not +58 | `logs/experiments/phase5/summary.jsonl` |
| ground-truth memory reaches 100% accuracy | pass_rate 1.0 at memory_hit_rate 1.0 | the number is real; it measures the store returning its own answer key on every question | `logs/experiments/phase6/summary.jsonl` |
| the whole project consumed 920,814 tokens, about $0.50 AUD | 2,956,979 tokens across all 7 phases | understated 3.2x — the per-phase figures quoted one run each where a phase had two, three, or twelve | `logs/experiments` |
| the warm-up phase ran on 20 questions, 2.7 rounds each | 100 questions, 2.12 rounds (pass rate 0.66 matches) | the headline rate is right; the setup around it is not, and the same document contradicts itself on the count elsewhere | `logs/experiments/phase0/summary.jsonl` |
| teacher styles scored ORCA 90%, principle 85%, chain-of-thought 80% | ORCA 90%, principle 50%, chain-of-thought 40% | ORCA's number is right, the two it beat are overstated by 35-40 points — and a properly powered re-test later found ORCA indistinguishable from a minimal prompt (p=0.58), so the conclusion this table was used to justify does not hold either | `logs/experiments/phase2/summary.jsonl` |
| memory beats no-memory by +5.0 points | with-memory 0.85 vs no-memory 0.9 | sign reversed -- the logged runs show memory doing worse | `logs/experiments/phase1/summary.jsonl` |
| student temperature 0.0 / 0.3 / 0.5 compared; 0.0 is critical | only 0.0 and 0.2 were run (12 configs, not the 27 a three-level grid implies) | two of the three compared settings have no run behind them | `logs/experiments/phase3/summary.jsonl` |
| hard domains Heart/Lung 70% and Genetic 60% | cancer 0.9, diabetes 0.8, disease_control 1.0, growth_hormone 0.9 | neither domain appears in the logs; every domain that ran scored >= 0.80 | `logs/experiments/phase4/summary.jsonl` |

### The strongest row is the one that reconciles perfectly

The retired system's pass rate was a composite score compared against a threshold the
experimenter set. Its own hyper-parameter grid shows what that setting was worth, on
identical runs:

| threshold set | pass rate that results | runs averaged |
|---|---|---|
| 0.75 | 0.975 | 4 |
| 0.80  ← **the one chosen** | **0.775** | 4 |
| 0.85 | 0.337 | 4 |

Nothing here was miscopied — this table matches its logs exactly. That is what makes
it decisive: the reported 25% → 83% is a function of a dial the experimenter turned, not a
property of the system. The rebuild turned the same dial the other way, raising the bar
until the baseline stopped passing everything (figure 6).


### Why the two cannot share an axis

|  | the retired version | the rebuild |
|---|---|---|
| what the score measured | 70% resemblance to the reference, 30% correctness | correctness only, judged blind |
| pass bar | a composite >= 0.75-0.85 | judge score >= 4 (>= 3 on the support testbed) |
| student | Llama-3.1-8B via a cloud API | qwen2.5:3b running locally |
| judge | same model family as the student | a different family, enforced at config load |
| evaluation set | 20-100 ad-hoc questions, no held-out split | 125 held-out questions, corpus and split kept disjoint |
| repetition | one run, one seed, no intervals | 3 seeds, bootstrap CI, exact McNemar |
| reference answer at inference | reached the student through four paths | structurally unreachable; a guard aborts the run if it appears |

*Note.* The retired result, line by line against its own logs. The pre-renovation write-up reported a rise from 25% to 83%, and 100% with 'ground-truth memory'. Reconciling it against the immutable run logs found two separate problems. The headline numbers are inflated relative to the logs. And several supporting claims have no run behind them at all -- a comparison whose sign is reversed, a grid of settings two thirds of which were never executed, two domains that do not appear anywhere in the logs. The second table is why the old and new numbers can never share an axis: seven independent things differ, so no arithmetic converts one into the other. Recomputed live from logs/experiments/phase1..6/summary.jsonl; claims quoted from docs/archive/PROJECT_OVERVIEW_AND_RESULTS.md, which carries a superseded banner.
