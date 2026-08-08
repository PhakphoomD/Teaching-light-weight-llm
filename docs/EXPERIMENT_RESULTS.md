# Experiment record

**What makes a small local language model better at one specialised domain — and what only looks
like it does.**

This is the complete record: what was being attempted, what was decided and why, every measurement
taken, and everything that did not work. It is written to be checkable rather than persuasive. The
[README](../README.md) is the five-minute version; this is the one that shows the working.

---

## How to read this

**Every number here is recomputed from a committed log.** Figures and tables regenerate with
`python scripts/make_figures.py`, and `tests/tlw/figures/test_published_numbers.py` recomputes each
published headline from its artifact and fails if a document and a log ever disagree. Three
content-overlap values are read from committed analysis printouts rather than recomputed; they are
labelled where they appear. Nothing else is typed by hand.

**Differences carry intervals, and colour follows the interval.** Every effect is reported as a
change in held-out pass rate with a 95% paired cluster-bootstrap interval over questions (10,000
resamples, seeded at 0) and an exact McNemar test. Where an interval spans zero, the result is drawn
in grey and called inconclusive — not rounded up into a finding.

**Negative results are results.** [Twenty-six of them](../reports/tables/tab-15-null-results.md) (Table 15)
have their own table. Three are hypotheses this project raised and then falsified with its own data;
two are cases where a well-supported published method did not transfer to this scale.

**Two pass bars appear and they are not interchangeable.** On the medical testbed a pass means the
judge scored the answer 4 — "correct *and* complete". On the support-documentation testbed it means
3 — "correct". The reason is in §6.4, and the two testbeds are read as separate studies that share
an axis of *change*, which is the only thing comparable between them.

---

## Contents

| | |
|---|---|
| [1. What this was for](#1-what-this-was-for) | the problem, the thesis, what would have counted as success |
| [2. The order things actually happened](#2-the-order-things-actually-happened) | and why that order matters |
| [3. The original system, and what it claimed](#3-the-original-system-and-what-it-claimed) | November 2025 |
| [4. The audit](#4-the-audit) | July 2026 — how the results came apart |
| [5. Rebuilding something measurable](#5-rebuilding-something-measurable) | the dataset, the framework, the instrument |
| [6. The measurements](#6-the-measurements) | seven questions, seven answers |
| [7. Against the literature](#7-against-the-literature) | what confirmed, what did not |
| [8. What broke in the project itself](#8-what-broke-in-the-project-itself) | six guardrails that fired |
| [9. What this means for building something](#9-what-this-means-for-building-something) | the product reading |
| [10. Limitations](#10-limitations) | what these numbers cannot support |
| [11. Reproducing all of it](#11-reproducing-all-of-it) | commands |

---

## 1. What this was for

### The problem

A small business wants a question-answering assistant over its own domain — support documentation,
internal procedures, a specialist field. It cannot send that material to a hosted model, cannot
afford per-token costs at volume, and has no ML team. A 3-billion-parameter model runs on an
ordinary laptop for nothing and keeps every document local. It is also noticeably worse at
specialised questions than a model twenty times its size.

**So: what closes that gap, and by how much?** Three things are widely assumed to. Have a larger
model teach the smaller one. Give it retrieval over the domain's documents. Fine-tune it on domain
answers. Each has strong published support. None of them had been measured, together, on one small
model, with the reference answer kept out of the evaluation.

### The thesis this project set out to test

> Fine-tuning teaches a model *how to say things*; retrieval teaches it *what is true*; an iterative
> teacher-student loop is a way of generating training data and evaluating, not a thing you ship.

That framing comes from the superficial alignment hypothesis [[3](#references)] and was adopted
early ([ADR-003](../reports/tables/tab-20-decision-log.md), Table 20). Most of what follows is that thesis being
tested rather than assumed — including the parts of it that turned out to be wrong at this scale.

### What would have counted as success

Stated before the measurements, so that failing is visible rather than reinterpretable:

- an intervention "works" if its 95% interval on held-out data excludes zero;
- the loop's value is specifically **arm C minus arm B** — an independent teacher measured *against*
  the model simply re-reading its own answer, not against no attempt at all;
- retrieval's value is measured on two testbeds chosen to differ in one property: whether the model
  already knows the domain.

---

## 2. The order things actually happened

**Table 21.** [*Project Timeline*](../reports/tables/tab-21-project-timeline.md) — the dated timeline, generated by merging
timestamps inside the run logs with the dates on the decision log.

**Sources:** `logs/experiments/phase*/summary.jsonl` · `runs/**/summary.jsonl` ·
`.claude/rules/decisions.md`.

The intuitive order is wrong here, in a way that flatters the early work. Every natural account of a
project like this runs *collect data → clean it → run experiments*. The dates say otherwise:

| | |
|---|---|
| **2025-11-29** | all seven original experiment phases ran, in a single day |
| **2026-07-10** | the audit found the results invalid (ADR-001) |
| **2026-07-12** | the dataset was *identified* as MedQuAD, licence-checked, and the cleaning tool was designed (ADR-005, ADR-006) |

Seven and a half months separate the experiments from the data work, and two days separate the audit
from it. So the original runs used an unidentified medical question-answer dump, with **no held-out
split**, no licence recorded, and no measurement of how noisy the reference answers were.

That ordering is not a footnote. It changes what the cleaning stage *is*: not preparation, but part
of the repair. And everything the project knows about its data — the twelve NIH sources, the CC BY
licence, the mislabelled directory that turns out to be Genetics Home Reference rather than a growth
hormone receptor — was learned during that repair, not before the experiments that depended on it.

---

## 3. The original system, and what it claimed

**Table 4.** [*V1 Claims vs Logs*](../reports/tables/tab-04-v1-claims-vs-logs.md) — the retraction, line by line ·
**[→ the original design rationale, recovered verbatim](archive/v1-notebook-narrative.md)**

### What it was

A teaching loop. The small model answers; a larger model reads the answer and critiques it; the
small model rewrites. Successful teaching episodes are stored in a vector database and retrieved on
later questions. Seven phases built up from a warm-up run to a final validation, and the design of
each is preserved in the archive link above, in the original author's words.

### What it reported

A rise from **25% to 83%**, and **100%** with what was called "training via memory". Those numbers
appeared in the project's own README until they were removed.

### What the logs say

| claimed | logged |
|---|---|
| 25% → 83% | **0.33 → 0.84** |
| memory beats no-memory by +5.0 points | **no-memory 0.90, with-memory 0.85** — the sign is reversed |
| teacher styles scored 90 / 85 / 80 | **90 / 50 / 40** |
| student temperature compared at 0.0, 0.3, 0.5 | **only 0.0 and 0.2 were ever run** |
| hard domains: Heart/Lung 70%, Genetic 60% | **neither appears in the logs**; all four that ran scored ≥ 0.80 |
| 920,814 tokens ≈ A$0.50 | **2,956,979 tokens** — one run quoted per phase where a phase had up to twelve; at the project's own quoted rates, **A$1.46–1.98** |
| 100% via ground-truth memory | **true as a number** — and it measures the store returning its own answer key |

Two different failures are mixed in that table, and the second is worse than the first. Some numbers
are inflated relative to their logs. Others describe runs that do not exist.

### The strongest evidence is the table that reconciles perfectly

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-06-pass-threshold-sensitivity-dark.png">
  <img alt="Left: the original system's pass rate at three thresholds — 0.975, 0.775 and 0.337 — with 0.80 marked as chosen. Right: the rebuilt arms scored at both candidate bars, where the lower bar puts every arm at 0.99 or above." src="../reports/figures/fig-06-pass-threshold-sensitivity.png">
</picture>

The original system's "pass rate" was a composite score compared against a threshold the
experimenter set, and its own hyper-parameter grid records what that setting was worth on identical
runs: **0.975 at the loosest, 0.337 at the strictest**. 0.80 was selected, and the resulting 25% →
83% was reported as a measured improvement.

Nothing in that grid was miscopied — it is the one table in the retired write-up that matches its
logs exactly. That is precisely what makes it decisive. The headline was a function of a dial the
experimenter turned, not a property of the system.

### And what the score was actually measuring

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-05-v1-score-composition-dark.png">
  <img alt="The retired composite score split into four components: a comparison judge that sees the reference at 35%, embedding similarity to the reference at 25%, ROUGE-L against the reference at 10%, and a blind correctness judge at 30%." src="../reports/figures/fig-05-v1-score-composition.png">
</picture>

Three of the four components compare the answer against the reference text. **70% of the score
rewarded resemblance**, not correctness.

---

## 4. The audit

**Table 5.** [*Leakage Audit*](../reports/tables/tab-05-leakage-audit.md) — eighteen leakage paths and the six seals that closed them

Reading the code rather than the results found eighteen paths by which the reference answer could
reach the model being measured. Seven were serious. The line the audit drew is that a model may be
*taught* using the reference answer but never *shown* it while being measured — so a teacher reading
the answer is legal, and a memory store handing that answer back to the student is not.

The three that mattered most:

- **A prompt template that rendered `COPY THIS EXACTLY: {ground_truth}`.** Reachable when the model
  got stuck. Not subtle.
- **Round one of every question retrieved stored feedback into the student's prompt** — with no
  content check, and gated by no configuration flag. Structural.
- **A teacher template instructing the teacher to end its critique with `Example: {ground_truth}`**,
  and that critique went to the student. Confirmed in a production log.

Three of these were switched off by configuration at the time and would have looked clean in any
log. They were found by reading, not by observing a symptom.

### The one worth understanding rather than mocking

The final phase deliberately pre-seeded the memory store with question-and-answer pairs, and the
notebook explains the reasoning in a way worth quoting:

> Similar to an "Open-book Exam" — the Student has correct answers available in Memory. No GPU
> required, no weight updates. Knowledge can be added or removed dynamically at any time.
>
> **Hypothesis:** If Memory contains Ground Truth, the Student should pass from Round 1.

The idea is not absurd. Retrieval-augmented generation *is* a kind of open-book exam, and "no GPU,
knowledge stays editable" is a real advantage — it is close to the system this project eventually
shipped. The error is in what the book contains. An open-book exam where the book is the marked
answer script is not an exam.

And the hypothesis was confirmed exactly as written: the model passed from round one, 100% of the
time. **The confirmation is what should have raised the alarm.** A system that scores 100% has
usually found a way to read the answers.

---

## 5. Rebuilding something measurable

### 5.1 The dataset

**Table 2.** [*MedQuAD Dataset Report*](../reports/tables/tab-02-medquad-dataset-report.md) — where the data came from and what cleaning removed

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-03-medquad-cleaning-yield-dark.png">
  <img alt="Records surviving cleaning per source domain, from 12,428 raw pairs to 10,024." src="../reports/figures/fig-03-medquad-cleaning-yield.png">
</picture>

MedQuAD [[21](#references)], CC BY 4.0: 47,457 question-answer pairs auto-extracted
from twelve NIH websites — which is why the raw text carries boilerplate, referral phone numbers and
duplicated template answers. **12,428 pairs in, 10,024 out.** On the domain the experiments used,
residual noise went from 1.4% to zero, three duplicate answers to zero, thirty-two malformed
questions were repaired and twenty-two answers were dropped as too short to be answerable. The
near-duplicate threshold follows the deduplication literature [[23](#references)]; the readiness
rubric's complexity, quality and diversity axes follow DEITA [[24](#references)].

**Sources:** `data/clean/*_report.json` · `data/clean/*_readiness_rag.json`.

The split is **506 train / 125 held-out**, disjoint. The retrieval corpus is built from the train
side only and the held-out side is never indexed.

This stage is reported like a result because the previous version's score was 70% resemblance to
these answers, and a noisy reference makes such a score a measurement of the noise.

### 5.2 The system

**Table 20.** [*Decision Log*](../reports/tables/tab-20-decision-log.md) — every decision with its date

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-02-system-architecture-dark.png">
  <img alt="Top: one YAML file feeds six registries, resolving an arm strategy scored by a blind judge, with a guard that aborts the run if the reference answer reaches a prompt. Bottom: a question is retrieved against chunked articles, grounded on a window centred on the matched chunk, and answered by a local 3B model." src="../reports/figures/fig-02-system-architecture.png">
</picture>

One run is one YAML file. Six slots — which model answers, which model critiques, which prompt,
whether retrieval or memory is attached, the loop parameters and seed, and which judge scores it —
each resolved through a registry by name and validated by eight rules when the configuration loads.

Two of those rules exist because of the failure above: **the judge must come from a different model
family than the student**, and **a baseline arm may not accumulate memory**. A third guard inspects
every prompt before it reaches a model and aborts the run if the reference answer appears in it. It
fired once, on the arm designed to leak, and that run is reported as aborted rather than quietly
rerun.

The memory store was redesigned to hold a *coaching note* rather than an answer, with a store-time
tripwire — exact substring, a twelve-token shingle, and cosine similarity — that rejects any note
containing the reference. Red-teamed against the thirty-two leaked records from the old store, it
rejects all of them.

### 5.3 The instrument, which failed its own test

**Table 17.** [*Judge Calibration Probes*](../reports/tables/tab-17-judge-calibration-probes.md) — the judge calibration probes

Each candidate judge was shown forty answers per class: correct ones, plainly wrong ones, truncated
ones, and a deliberately adversarial class altered to be subtly wrong while still reading well. A
usable judge passes the first, fails the second and fourth, and agrees with a stronger reference
judge.

**Neither candidate passed.** One waved through 92.5% of the deliberately-wrong answers; the other,
95%. A stricter rubric was tried and made things worse — the judge began rejecting good answers, its
pass rate on correct answers falling from 0.975 to 0.25.

What was done about it is the part worth reading. The pass bar was raised, and **one judge was held
fixed across every arm** so that comparisons between arms remain valid even where absolute levels do
not. The limitation is stated wherever the numbers appear. Retuning the probe until it passed was
tried once, recorded, and rejected.

### 5.4 Choosing the pass bar

The right panel of the figure in §3 shows why. At "correct", all four arms of the loop ablation sit
between 0.99 and 1.00 and are indistinguishable — an ablation run at that bar would have returned a
null *by construction* rather than by evidence, because there was no room left to improve. Raising
the bar to "correct and complete" restores about eighteen points of headroom.

Note what this is: the same dial the original project turned downward, turned upward. The difference
is direction and disclosure — the bar was fixed before the comparison and the cost is stated.

### 5.5 Deleting the old system

The 843-line monolith that produced the retracted numbers was deleted, along with five dead modules
— about 1,400 lines with no importers — after a search confirmed the rebuilt core imports none of
it. Keeping it would have left a second, leaking implementation beside the audited one. This is also
why the original notebook no longer runs: its imports pointed here.

The project's own README was still advertising "Achieves 83% pass rate (up from 25%)" on its third
line until that was removed too.

---

## 6. The measurements

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-01-all-interventions-measured-dark.png">
  <img alt="Nine interventions as changes in pass rate with 95% intervals on a zero axis. Only self-refinement, retrieval where a knowledge gap exists, and a wider grounding window clear zero; fine-tuning is a large negative." src="../reports/figures/fig-01-all-interventions-measured.png">
</picture>

**Table 1.** [*All Interventions Provenance*](../reports/tables/tab-01-all-interventions-provenance.md) — what each point was measured on

Nine things were tried. Two worked, one of them for a reason nobody predicted.

### 6.1 Does a teacher-student loop teach a small model?

**Table 3.** [*MedQuAD Teaching Loop Results*](../reports/tables/tab-03-medquad-teaching-loop-results.md) — every value · 125 held-out questions ×
3 seeds, 375 question-runs per arm

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-04-medquad-teaching-loop-ablation-dark.png">
  <img alt="Four arms with Wilson intervals and the two pre-registered differences. Self-refinement gains 0.091; a teacher on top gains 0.003 with an interval spanning zero." src="../reports/figures/fig-04-medquad-teaching-loop-ablation.png">
</picture>

| arm | pass rate |
|---|---|
| one attempt, no feedback | 0.821 |
| the model critiques and rewrites its own answer | 0.912 |
| a larger model critiques it, without seeing the answer key | 0.915 |
| *the teacher is shown the answer key* | *0.940 — leakage ceiling, not a result* |

**Self-refinement: +0.091 [+0.051, +0.133], p < 0.0001.** Real.
**An independent teacher on top of it: +0.003 [−0.021, +0.029], p = 1.00.** Nothing.

**Source:** `runs/teaching-loop-medquad/` (12 runs, 4 conditions x 3 seeds).

The value was in the model re-reading its own answer, not in the teacher. A 70-billion-parameter
model was being paid to add three thousandths of a point. The teacher was dropped.

One diagnostic is worth keeping: similarity to the reference stayed flat at about 0.70 across all
four arms while correctness rose nine points. Merging those two into one score — which is what the
original system did — would have hidden the entire effect.

### 6.2 Does retrieval help a model that already knows the domain?

**Table 6.** [*MedQuAD RAG Results*](../reports/tables/tab-06-medquad-rag-results.md) — every value

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-07-medquad-rag-ablation-dark.png">
  <img alt="Pass rates for the 3B and 7B with and without retrieval, plus three single-seed rescue attempts, none beating the unaided baseline." src="../reports/figures/fig-07-medquad-rag-ablation.png">
</picture>

**No.** On MedQuAD the 3B already answers 82% of held-out questions unaided.

- retrieval on the 3B: **−0.005 [−0.067, +0.056]**, p = 0.91 — no effect
- retrieval on the 7B: **−0.069 [−0.120, −0.019]**, p = 0.0004 — significantly harmful
- the 3B with retrieval against a plain 7B: **−0.088 [−0.136, −0.043]** — retrieval does not
  substitute for model size

Three rescue attempts were run before accepting this: reranking so only passages of the matching
question type survive (0.760), a corpus twenty-four times larger (0.816), and a more detailed
student prompt (0.840). All below the 0.864 unaided baseline on the same seed. The null is
structural, not an artefact of a weak retriever or a small corpus.

**Sources:** `runs/rag-medquad/` · `runs/rag-medquad-fair-tests/` · `runs/student-prompt-medquad/`.

#### The null is two effects cancelling

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-08-medquad-rag-outcome-split-dark.png">
  <img alt="Retrieval's repairs and regressions bucketed by how reliably the baseline already answered: all 15 repairs where it never succeeded, all 35 regressions where it always did." src="../reports/figures/fig-08-medquad-rag-outcome-split.png">
</picture>

Retrieval repaired 37 answers and broke 39, and the two sets barely overlap. Every repair landed on
a question the model had never once answered correctly; every regression on one it had always got
right. A retrieved passage that is on-topic but answers a neighbouring question pulls the model off
an answer it already had.

"Retrieval did nothing" and "retrieval did two opposite things of equal size" are different facts,
and only the second tells you what to build.

#### Which raises the obvious question

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-09-selective-gating-bounds-dark.png">
  <img alt="Two panels showing that applying retrieval or refinement only where the model struggles beats both always-on and never." src="../reports/figures/fig-09-selective-gating-bounds.png">
</picture>

Applied only where the model struggles, retrieval is worth **+0.088** (gating per question) to
**+0.099** (gating per attempt, the absolute ceiling). Neither gate is implementable — both need the
outcome they are predicting — but the gap between them and always-on retrieval is the size of the
prize for solving the gating problem. Hold that thought; it recurs in §6.6 on a completely different
intervention.

#### And one thing retrieval genuinely fixed

**Table 7.** [*MedQuAD RAG Reliability*](../reports/tables/tab-07-medquad-rag-reliability.md) — reliability

On the thirteen questions the model never once answered correctly across three seeds — real
knowledge gaps rather than unlucky samples — retrieval raised per-attempt accuracy 0.231 → 0.354.
More usefully: **not one of them was answered correctly on all five attempts without retrieval, and
four were with it.**

That is the product-shaped version of the finding, and it is invisible in the aggregate. It comes
with a cost, though: retrieval *lowers* the chance that at least one of several attempts lands
(0.89 → 0.74), because grounding trades sampling diversity for consistency.

### 6.3 Does retrieval help when the model genuinely lacks the knowledge?

**Table 8.** [*WixQA RAG Results*](../reports/tables/tab-08-wixqa-rag-results.md) — every value · WixQA: 200
expert-written questions over 6,221 real help-centre articles, 3 seeds

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-11-two-testbed-comparison-dark.png">
  <img alt="Top: the 3B answers 0.821 of MedQuAD unaided and 0.163 of WixQA. Bottom: retrieval is worth −0.005 on the first and +0.152 on the second." src="../reports/figures/fig-11-two-testbed-comparison.png">
</picture>

**Yes: 0.163 → 0.315, a difference of +0.152 [+0.092, +0.213], p = 5×10⁻¹¹.** Same technique,
opposite result — and the second
testbed was chosen precisely because the model has no parametric knowledge of one company's
proprietary support documentation.

#### The lift is the retrieved data, demonstrably

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-10-wixqa-rag-gold-split-dark.png">
  <img alt="Pass rate with and without retrieval split by whether the answer-bearing article was retrieved: 0.127 to 0.400 where it was, 0.207 to 0.211 where it was not." src="../reports/figures/fig-10-wixqa-rag-gold-split.png">
</picture>

Hold the model, prompt, judge and pass bar fixed. Split the same run by one property — whether the
article containing the answer actually appeared in the retrieved top three:

| | without retrieval | with retrieval | difference |
|---|---|---|---|
| the answer's article **was** retrieved | 0.127 | 0.400 | **+0.273** |
| it **was not** | 0.207 | 0.211 | +0.004 |

Nothing differs between those two rows except whether the retrieved text contained the answer. The
aggregate +0.152 is those two regimes mixed at a 55% hit rate.

**Sources:** `runs/rag-wixqa/1-no-rag/`, `runs/rag-wixqa/2-rag-basic/` and the retrieval log beside
them. Dataset: WixQA [[22](#references)], MIT.

**The law, in one sentence: retrieval helps if and only if the retrieved text contains the
answer.** That sounds tautological and is not — it makes a testable prediction about what to spend
effort on, which §6.4 tests.

### 6.4 What actually gates retrieval

If the law holds, raising the hit rate should raise the pass rate along a predictable path, and the
payoff *given* a correct retrieval should stay put.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-12-wixqa-retrieval-dose-response-dark.png">
  <img alt="Pass rate against retrieval hit rate across three rungs, with the pre-registered prediction marked, and per-subset rates showing the payoff unchanged between retrievers." src="../reports/figures/fig-12-wixqa-retrieval-dose-response.png">
</picture>

**Table 9.** [*WixQA Retriever Comparison*](../reports/tables/tab-09-wixqa-retriever-comparison.md) — seven retrievers ranked offline

Seven retriever variants were compared offline — no model calls, so the whole ladder costs minutes
rather than GPU-days. The winner raised hit rate 0.550 → 0.665. Chunking articles before embedding
mattered more (+0.095) than a stronger encoder (+0.070), for a reason visible in the corpus itself:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-13-wixqa-article-length-distribution-dark.png">
  <img alt="Cumulative distribution of article lengths, showing that the encoder's roughly 256-token window covers only 47% of articles." src="../reports/figures/fig-13-wixqa-article-length-distribution.png">
</picture>

The encoder reads roughly the first 256 tokens, so for most of this corpus a whole-article vector
describes an introduction.

**The prediction held.** Before running the upgraded retriever end-to-end, its pass rate was
predicted at **0.337** from a mixture of the two conditional rates measured on the previous rung.
The run returned **0.340**. And P(pass | answer retrieved) stayed pinned at 0.400 → 0.411: the
retriever changes how *often* the answer is found, not what it is worth once found.

Honest caveat: the aggregate retriever gain is **+0.025 [−0.028, +0.080], p = 0.27** and is *not*
significant. The evidence for the mechanism is the invariance and the accuracy of the prediction,
not the size of the jump.

**Sources:** `reports/rag-wixqa/retriever-hitrate.json` (offline ladder) ·
`runs/rag-wixqa/3-rag-better-retriever/`. Encoder: BGE [[13](#references)]. The position effect
that motivates chunk-centring is Lost in the Middle [[9](#references)].

#### The largest single win was not the retriever

An audit before the next experiment asked a question nobody had: when the right article *is*
retrieved, does the answer actually reach the prompt? It did not. The system showed the first 900
characters of each article, and the median article is 3,555 characters — so **92.7% were cut, the
model saw about a quarter of the article, and 41% of the expert answer's content survived** against
a ceiling of 72%.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-15-wixqa-grounding-window-coverage-dark.png">
  <img alt="Four ways of choosing which part of a retrieved article to show, from 0.412 to 0.655 coverage against a 0.726 ceiling." src="../reports/figures/fig-15-wixqa-grounding-window-coverage.png">
</picture>

**Table 10.** [*WixQA Grounding Window Results*](../reports/tables/tab-10-wixqa-grounding-window-results.md) — what changed when only the window changed

Centring the same window on the chunk the retriever had already matched — using localisation the
system was computing and discarding — costs 7% more prompt and recovers seven points of coverage.
The widest centred window reaches 90% of what the full article could possibly contribute.

Holding retrieval byte-identical and changing only which text reached the prompt:

**pass rate 0.340 → 0.470, +0.130 [+0.072, +0.188], p = 3.5×10⁻⁸.**

Five times the retriever's effect, at zero inference cost. And the supposed "0.400 model ceiling"
rose to 0.534 — so it was never a model ceiling.

**Sources:** `reports/rag-wixqa/context-window-coverage.json` (offline 2x2) ·
`runs/rag-wixqa/4-rag-wider-context/` · `reports/rag-wixqa/wider-context-vs-narrow.txt`.

#### Fixing two stages exposed a third

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-14-rag-pipeline-stage-analysis-dark.png">
  <img alt="Retrieval improved 0.550 to 0.665, delivery 0.412 to 0.655, and extraction fell from 0.880 to 0.610." src="../reports/figures/fig-14-rag-pipeline-stage-analysis.png">
</picture>

Retrieval resolves into three stages that can be measured separately. With nearly twice as much
answer material in front of it, **the model used a smaller share of it: 88% → 61%.** Roughly two
fifths of what it is shown goes unused. That is the remaining bottleneck, and it is not a retrieval
problem.

### 6.5 Does the loop compound with retrieval?

**Table 12.** [*WixQA Loop Plus RAG Results*](../reports/tables/tab-12-wixqa-loop-plus-rag-results.md) — every value · 133 gold-retrieved
questions, one seed — directional

This is the system the project is named after: the loop and retrieval together. **It does not
compound.**

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-16-wixqa-self-refine-by-prior-score-dark.png">
  <img alt="Left: refinement's mean score change by prior score, positive for 0 and 1, negative for 3 and 4. Right: four policies where only the unimplementable oracle beats doing nothing." src="../reports/figures/fig-16-wixqa-self-refine-by-prior-score.png">
</picture>

Mechanically it works — reference coverage rises **+0.031 [+0.018, +0.047]**, an interval excluding
zero, and 62% of answers are edited. But the judged bar does not move: **−0.015 [−0.068, +0.038]**,
p = 0.77. Making an answer contain more of the right material is not the same as making it correct.

The reason is the tug-of-war again, now for iteration: refinement lifts answers that scored 0 or 1
(+0.33, +0.38) and taxes those that scored 3 (−0.11, with seven made worse and none improved). 57%
were already at 3.

**And the gate is the missing piece, for the second time.** Refining only the weak answers would be
worth +0.038. The implementable version — asking the model whether it is done — captures **none** of
it: the 3B called its own answer complete **79 times out of 133**, including when it was wrong.

That is the same conclusion §6.2 reached about selective retrieval, on a different intervention, a
different testbed, and months apart. A finding that replicates across experiments with no reason to
agree is the strongest thing in this report — and it is what the self-correction literature
predicts [[5](#references), [11](#references)].

**Source:** `runs/rag-wixqa/pilots/5-rag-plus-self-refine/`, paired against the seed-42
gold-retrieved slice of `runs/rag-wixqa/4-rag-wider-context/`.

### 6.6 Does fine-tuning help?

**Table 13.** [*MedQuAD LoRA Results*](../reports/tables/tab-13-medquad-lora-results.md) — every value

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../reports/figures/fig-17-medquad-lora-effect-dark.png">
  <img alt="Pass rate falling from 0.868 to 0.576 after fine-tuning." src="../reports/figures/fig-17-medquad-lora-effect.png">
</picture>

**No: −0.292 [−0.360, −0.224].** A QLoRA fine-tune on 506 (question, reference answer) pairs, 23
minutes on a laptop GPU, evaluated with the adapter switched on and off on the same stack.

Training was healthy — loss 1.98 → 0.99, token accuracy 0.59 → 0.75. **The fine-tune worked, and
that is why it hurt.** It learned the reference corpus's terse house style, answers became 30–45%
shorter, and shorter answers fail a bar that requires completeness. The objective it was trained on
and the objective it was scored on were not the same one — the alignment tax [[16](#references)] and
catastrophic forgetting during continual fine-tuning [[15](#references)], measured.

**Source:** `reports/lora-medquad/fine-tuned-vs-original.json`.

### 6.7 The system answering live

**Table 11.** [*Demo Worked Examples*](../reports/tables/tab-11-demo-worked-examples.md) — the same questions three ways

Four questions run through the local 3B with no retrieval, with retrieval and a narrow window, and
with retrieval and the wider centred window. The set deliberately includes a question whose
answer-bearing article was *not* retrieved, and it gets worse rather than better — the tug-of-war
showing up in four examples instead of 600 cells.

---

## 7. Against the literature

**Table 14.** [*Literature Comparison*](../reports/tables/tab-14-literature-comparison.md) — fifteen works and what happened when each was measured here

Most confirmed. Ovadia et al. [[2](#references)] — retrieval before fine-tuning for injecting
knowledge — is supported sharply: +0.152 against −0.292. The superficial alignment hypothesis
[[3](#references)] is supported painfully; the fine-tune transferred style exactly as predicted, and
that is what broke it. Adaptive retrieval [[6](#references)], distraction by irrelevant context
[[7](#references), [8](#references)], and position within the context window [[9](#references)] all
reproduce.

**One did not.** Self-Refine [[4](#references)] improves outputs through iterative self-critique,
and it held here on a saturated domain (+0.091) but did **not** transfer on top of retrieval at 3B
scale (−0.015). That is consistent with Huang et al. [[5](#references)], which predicts exactly this
failure when the model must supply its own correctness signal — and the 59% false "complete" rate is
that paper's mechanism, measured.

The statistics follow standard practice: Wilson score intervals for a proportion
[[25](#references)], the exact paired test for a difference [[26](#references)], and a cluster
bootstrap over questions [[27](#references)]. The figures follow message-first design with
self-contained captions [[28](#references)], and differences are drawn as position on a common scale
rather than as bars because position is the more accurately read encoding [[29](#references)].

---

## 8. What broke in the project itself

**Table 19.** [*Methodology and Integrity*](../reports/tables/tab-19-methodology-and-integrity.md) — the guardrails, including the ones that caught something

A guardrail nobody has ever tripped is untested. Eleven fired. Six are worth naming here because
they are defects in the project's *own* credibility rather than in a result:

- **The results could not be reproduced from a clone.** Thirteen scripts hardcoded an absolute path
  into one developer's home directory — including every script behind the retrieval findings.
  Discovered by a structure audit *after* all the results were in.
- **A wrong comparator reversed a study's conclusion.** The loop-plus-retrieval effect rendered as
  +0.045 — "the loop compounds" — because it was paired against a similarly-named earlier pilot.
  The correct value is −0.015. Caught by looking at the rendered figure and noticing it disagreed
  with the report.
- **A third of the evidence was reported as all of it.** A diagnostic returned the first run it
  found instead of aggregating seeds; because run directories sort lexically, that was seed 123
  alone.
- **The more damning of two calibration probes was silently dropped**, because the two candidates
  were probed by different script versions writing different key names.
- **A headline was quietly wrong for one command** — pointing the analysis at the whole runs
  directory pooled fourteen pilot runs into the loop ablation.
- **The project was still advertising its own retracted result** on the third line of its README.

Each is now closed structurally rather than by remembering: paths made relative and validated by
tests, pilots moved where the discovery function cannot reach them, named regression tests on the
comparator and the aggregation, and a function that refuses to return if it finds fewer than two
calibration candidates.

---

## 9. What this means for building something

1. **Measure the no-retrieval baseline before building an index.** It is the cheapest measurement
   in this report and it predicts whether retrieval can pay at all. 0.821 versus 0.163 is the whole
   difference between a null and +0.152.
2. **Spend the first effort on delivery, not the retriever.** Which text reaches the prompt was
   worth five times a better retriever here, at no inference cost. Ground on the passage the
   retriever matched, not the top of the document.
3. **Do not ship always-on self-refinement.** Roughly three times the inference cost for no
   measurable gain, and it damages answers that were already correct.
4. **Do not fine-tune on reference answers to add knowledge.** It transfers style, and the style may
   fight your evaluation.
5. **The unsolved problem is a gate.** Two independent experiments say the same thing: these
   interventions are worth having *selectively*, and a 3B cannot decide for itself when to apply
   them. That is where the next real gain is.
6. **Target "correct", not "expert-complete", for a small model.** On WixQA the strict bar was
   structurally unreachable — the full source article contains only about 72% of the expert answer.
7. **It runs on one laptop for nothing.** The model, the index and the fine-tune are all local; only
   the judge — the measuring instrument, not the product — used a hosted API.

---

## 10. Limitations

- **The judge failed its calibration probe** and no better independent option was available within
  the constraints. Comparisons between arms use one fixed judge and remain valid; absolute levels
  carry less weight than the differences.
- **One seed for the loop-plus-retrieval study.** A pre-registered stop rule ended it when the pilot
  came back flat, so those numbers are directional and labelled as such everywhere.
- **The three rescue attempts on the retrieval null are single-seed** and shown in a lighter colour
  for that reason.
- **The reliability set was selected on prior failure**, so only the difference between arms is
  interpretable and it will regress toward the mean on its own.
- **Two of the three testbed-level findings rest on one dataset each.** MedQuAD and WixQA differ in
  more than the knowledge gap; the gold-split within a single run is what makes the causal claim,
  not the comparison between them.
- **Two predictions were wrong**, both from trusting an observational correlation that a controlled
  comparison later contradicted — the grounding repair was predicted at ~0.36 and returned 0.470,
  and refinement was predicted at +3 points and returned −1.5.
  **Table 16.** [*Predictions vs Outcomes*](../reports/tables/tab-16-predictions-vs-outcomes.md) — tab-16
- **"Extraction" is a derived ratio**, not a directly observed quantity, and inherits the noise of
  both its parts.

---

## 11. Reproducing all of it

Nothing below needs a GPU, an API key, or a model run. Every number comes from committed logs.

```bash
python scripts/make_figures.py
```

Regenerates all 17 figures (light and dark) and all 21 tables from `runs/`, `reports/` and
`logs/experiments/`.

```bash
python -m pytest tests/ -q
```

401 tests, including `tests/tlw/figures/`, which recomputes each published headline from its
artifact and fails if a figure and a document disagree.

```bash
python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A
python -m src.tlw.analysis --runs-dir runs/rag-medquad --rag
python scripts/wixqa/analyze_three_seeds.py
python scripts/wixqa/analyze_dose_response.py
```

The original analyses, run directly.

### Where everything lives

| | |
|---|---|
| every figure with its caption | [`reports/figures/README.md`](../reports/figures/README.md) |
| every measured value, including the nulls | [`reports/tables/`](../reports/tables/) |
| per-study protocol and limitations | [`TRACK_A_RESULTS`](TRACK_A_RESULTS.md) · [`RAG_RESULTS`](RAG_RESULTS.md) · [`WIXQA_RESULTS`](WIXQA_RESULTS.md) · [`PRODUCT_RESULTS`](PRODUCT_RESULTS.md) · [`RAG_RELIABILITY_ANALYSIS`](RAG_RELIABILITY_ANALYSIS.md) |
| the decision log in full | [`.claude/rules/decisions.md`](../.claude/rules/decisions.md) |
| the retired write-up, with a banner naming each false claim | [`archive/PROJECT_OVERVIEW_AND_RESULTS.md`](archive/PROJECT_OVERVIEW_AND_RESULTS.md) |
| the original design rationale, recovered verbatim | [`archive/v1-notebook-narrative.md`](archive/v1-notebook-narrative.md) |

---

## References

Numbered as cited above. The same list, annotated with what each work claims and what happened when
it was measured here, is generated into
[reports/tables/tab-14](../reports/tables/tab-14-literature-comparison.md) (Table 14) from a single source in
`src/tlw/figures/data.py`, so the two cannot disagree — and a test asserts every work cited in this
report appears there.

1. Lewis, P., Perez, E., Piktus, A., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020. arXiv:2005.11401.
2. Ovadia, O., Brief, M., Mishaeli, M., Elisha, O. (2024). *Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs*. EMNLP 2024. arXiv:2312.05934.
3. Zhou, C., Liu, P., Xu, P., et al. (2023). *LIMA: Less Is More for Alignment*. NeurIPS 2023. arXiv:2305.11206.
4. Madaan, A., Tandon, N., Gupta, P., et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback*. NeurIPS 2023. arXiv:2303.17651.
5. Huang, J., Chen, X., Mishra, S., et al. (2024). *Large Language Models Cannot Self-Correct Reasoning Yet*. ICLR 2024. arXiv:2310.01798.
6. Mallen, A., Asai, A., Zhong, V., et al. (2023). *When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories*. ACL 2023. arXiv:2212.10511.
7. Cuconasu, F., Trappolini, G., Siciliano, F., et al. (2024). *The Power of Noise: Redefining Retrieval for RAG Systems*. SIGIR 2024. arXiv:2401.14887.
8. Shi, F., Chen, X., Misra, K., et al. (2023). *Large Language Models Can Be Easily Distracted by Irrelevant Context*. ICML 2023. arXiv:2302.00093.
9. Liu, N. F., Lin, K., Hewitt, J., et al. (2024). *Lost in the Middle: How Language Models Use Long Contexts*. TACL 2024. arXiv:2307.03172.
10. Kadavath, S., Conerly, T., Askell, A., et al. (2022). *Language Models (Mostly) Know What They Know*. preprint. arXiv:2207.05221.
11. Xiong, M., Hu, Z., Lu, X., et al. (2024). *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs*. ICLR 2024. arXiv:2306.13063.
12. Shinn, N., Cassano, F., Berman, E., et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning*. NeurIPS 2023. arXiv:2303.11366.
13. Xiao, S., Liu, Z., Zhang, P., Muennighoff, N. (2023). *C-Pack: Packed Resources For General Chinese Embeddings (BGE)*. preprint. arXiv:2309.07597.
14. Es, S., James, J., Espinosa-Anke, L., Schockaert, S. (2023). *RAGAS: Automated Evaluation of Retrieval Augmented Generation*. preprint. arXiv:2309.15217.
15. Luo, Y., Yang, Z., Meng, F., et al. (2023). *An Empirical Study of Catastrophic Forgetting in LLMs During Continual Fine-tuning*. preprint. arXiv:2308.08747.
16. Ouyang, L., Wu, J., Jiang, X., et al. (2022). *Training Language Models to Follow Instructions with Human Feedback*. NeurIPS 2022. arXiv:2203.02155.
17. Chen, M., Tworek, J., Jun, H., et al. (2021). *Evaluating Large Language Models Trained on Code (pass@k)*. preprint. arXiv:2107.03374.
18. Wang, X., Wei, J., Schuurmans, D., et al. (2023). *Self-Consistency Improves Chain of Thought Reasoning in Language Models*. ICLR 2023. arXiv:2203.11171.
19. Geifman, Y., El-Yaniv, R. (2017). *Selective Classification for Deep Neural Networks*. NeurIPS 2017. arXiv:1705.08500.
20. Kamath, A., Jia, R., Liang, P. (2020). *Selective Question Answering under Domain Shift*. ACL 2020. ACL Anthology 2020.acl-main.503.
21. Ben Abacha, A., Demner-Fushman, D. (2019). *A Question-Entailment Approach to Question Answering (MedQuAD)*. BMC Bioinformatics 20(1):511. doi:10.1186/s12859-019-3119-4.
22. Cohen, D., Shalom, A., et al. (2025). *WixQA: A Multi-Dataset Benchmark for Enterprise Retrieval-Augmented Generation*. preprint. arXiv:2505.08643.
23. Lee, K., Ippolito, D., Nystrom, A., et al. (2022). *Deduplicating Training Data Makes Language Models Better*. ACL 2022. arXiv:2107.06499.
24. Liu, W., Zeng, W., He, K., et al. (2024). *What Makes Good Data for Alignment? A Comprehensive Study of Automatic Data Selection in Instruction Tuning (DEITA)*. ICLR 2024. arXiv:2312.15685.
25. Wilson, E. B. (1927). *Probable Inference, the Law of Succession, and Statistical Inference*. JASA 22(158):209-212. doi:10.2307/2276774.
26. McNemar, Q. (1947). *Note on the Sampling Error of the Difference Between Correlated Proportions or Percentages*. Psychometrika 12(2):153-157. doi:10.1007/BF02295996.
27. Efron, B., Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall. ISBN 978-0412042317.
28. Rougier, N. P., Droettboom, M., Bourne, P. E. (2014). *Ten Simple Rules for Better Figures*. PLOS Computational Biology 10(9). doi:10.1371/journal.pcbi.1003833.
29. Cleveland, W. S., McGill, R. (1984). *Graphical Perception: Theory, Experimentation, and Application to the Development of Graphical Methods*. JASA 79(387):531-554. doi:10.2307/2288400.

---

## Citation

If you refer to this work:

```bibtex
@misc{teaching_lightweight_llms_2026,
  title  = {Teaching Lightweight LLMs: what actually improves a small local model on one domain},
  author = {Deesuwan, Phakphoom},
  year   = {2026},
  note   = {Experiment record: docs/EXPERIMENT_RESULTS.md. All results recomputed from committed
            logs; regenerate with 	exttt{python scripts/make_figures.py}.}
}
```

**Datasets.** MedQuAD [[21](#references)], CC BY 4.0 — Ben Abacha & Demner-Fushman 2019.
WixQA [[22](#references)], MIT — Cohen et al. 2025. Built with Llama.
