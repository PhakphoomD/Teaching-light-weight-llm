**Table 17**

*Judge Calibration Probes*

| judge | seed | n per class | passes good | passes wrong | passes truncated | passes plausible-wrong | agreement (kappa) | gate |
|---|---|---|---|---|---|---|---|---|
| groq/llama-3.1-8b-instant | 42 | 40 | 0.950 | 0.100 | 0.775 | **0.925** | 0.411 | **fail** |
| ollama/llama3.1:8b | 42 | 40 | 0.975 | 0.100 | 0.900 | **0.950** | 0.346 | **fail** |
| ollama/llama3.1:8b | 42 | 40 | 0.250 | 0.050 | 0.250 | **0.200** | 0.120 | **fail** |
| ollama/llama3.1:8b | 123 | 40 | 0.250 | 0.050 | 0.250 | **0.300** | 0.213 | **fail** |

*Note.* The instrument was tested before it was trusted, and it failed. Each candidate judge was shown 40 answers per class built from the training split: correct answers, plainly wrong ones, truncated ones, and a deliberately adversarial class of answers altered to be subtly wrong while still reading well. A usable judge passes the first class, fails the second and fourth, and agrees with a stronger reference judge. **Neither candidate passed.** The plausible-wrong column is why: a judge that waves through answers built to be wrong cannot certify correctness. What was done about it is the part worth reading — the pass bar was raised, one judge was held fixed across every arm so the comparison between arms stays valid even where the absolute level does not, and the limitation is stated wherever the numbers appear. The alternative, retuning the probe until it passed, was tried once on a stricter rubric and made the judge worse (it began rejecting good answers), which is recorded rather than discarded. Sources: runs/judge-calibration/**.
