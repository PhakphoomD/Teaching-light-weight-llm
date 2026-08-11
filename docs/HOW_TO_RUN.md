# How to run this project

Everything here has been executed on a clean checkout. Commands are grouped by what you are
trying to do, and each one says what it needs, roughly how long it takes, and what it produces.

| I want to… | Go to |
|---|---|
| Set the environment up | [1. Setup](#1-setup) |
| Check the published numbers without running a model | [2. Verify the results](#2-verify-the-results-no-model-no-api-key) |
| Run the tests, or one test | [3. The tests](#3-the-tests) |
| Run an experiment myself | [4. Run an experiment](#4-run-an-experiment) |
| Rebuild the dataset or a search index | [5. Rebuild what a clone does not carry](#5-rebuild-what-a-clone-does-not-carry) |
| Ask the demo engine a question | [6. The answering engine](#6-the-answering-engine) |
| Understand why a command failed | [7. When something goes wrong](#7-when-something-goes-wrong) |

---

## 1. Setup

**You need:** Python 3.11, [conda](https://docs.conda.io/en/latest/miniconda.html), and — only for
sections 4 and 6 — [Ollama](https://ollama.com). A Groq API key is needed only to re-run judging;
nothing in sections 2 and 3 calls a model or the network.

```bash
git clone https://github.com/PhakphoomD/Teaching-light-weight-llm.git
cd Teaching-light-weight-llm
conda env create -f environment.yml
conda activate tlw
pip install -r requirements.txt
```

**Both install commands are required.** `environment.yml` carries only what conda must resolve —
the Python version and the CUDA build of PyTorch. Everything else, including the test runner, is in
`requirements.txt`.

### Finding your interpreter path

Once the environment exists, every command below can be written as plain `python`, provided `tlw`
is active. If you would rather name the interpreter explicitly — which is what this repository's
own rules require of its automation, because a bare `python` on Windows resolves to the Microsoft
Store stub — print the path once and reuse it:

```bash
conda run -n tlw python -c "import sys; print(sys.executable)"
```

That prints something like `C:\Users\<you>\.conda\envs\tlw\python.exe` on Windows, or
`/home/<you>/miniconda3/envs/tlw/bin/python` on Linux. Substitute **your** output wherever the
project's internal documentation writes `PY`. Nothing in the repository hardcodes a path; the
guard hook resolves it at run time and prints yours in its error messages.

### Confirming the setup works

```bash
python -m pytest tests/ -q
```

All tests should pass on a fresh clone, with no API key and no model downloaded except a small
sentence encoder that two tests fetch on first use. If they do not, section 7 lists the causes.

---

## 2. Verify the results (no model, no API key)

This is the section for a reader who wants to check the claims rather than take them. Every number
in `README.md` and `docs/EXPERIMENT_RESULTS.md` is recomputed from logs committed to this
repository. None of these commands calls a language model.

| What it checks | Command | Time |
|---|---|---|
| **Does an iterative teaching loop help?** Prints the teacher effect and the self-refinement effect with intervals | `python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A` | ~20 s |
| **Does retrieval help a model that already knows the domain?** The four-arm table | `python -m src.tlw.analysis --runs-dir runs/rag-medquad --rag` | ~20 s |
| **Does retrieval help when the model genuinely lacks the knowledge?** Three seeds, plus the causal split by whether the answer was retrieved | `python scripts/wixqa/analyze_three_seeds.py` | ~15 s |
| **Is retrieval quality the bottleneck?** The dose-response across three retrievers | `python scripts/wixqa/analyze_dose_response.py` | ~15 s |
| **Is the largest effect explained by the grounding window, or by exposing the graded answer?** | `python scripts/wixqa/measure_reference_exposure.py` | ~3 min, needs `data/external/` |
| **Regenerate every figure and table from the logs** | `python scripts/make_figures.py` | ~90 s |

The first command should print `C-B: +0.003 [-0.021, +0.029]` and `B-A: +0.091 [+0.051, +0.133]`.
Those are the two numbers the report leads with; if they do not match, something is wrong and the
project would like to know.

`scripts/make_figures.py` rewrites the 17 figures and 22 tables in `reports/`. Its output is
deterministic — two consecutive runs produce byte-identical files — so `git status` staying clean
afterwards is itself a check.

---

## 3. The tests

**Run everything:**

```bash
python -m pytest tests/ -q
```

**Run one file:**

```bash
python -m pytest tests/tlw/analysis/test_stats.py -q
```

**Run one test**, by name — useful when a single assertion fails:

```bash
python -m pytest tests/tlw/analysis/test_stats.py::test_mcnemar_matches_scipy_binomtest_cross_check -q
```

**Run everything matching a word.** `-k` takes a substring or a boolean expression, so this runs
every leakage-related test wherever it lives:

```bash
python -m pytest tests/ -k "leak or tripwire" -q
```

**See why a test failed**, rather than that it failed:

```bash
python -m pytest tests/ --tb=short          # a short traceback per failure
python -m pytest tests/ -x                  # stop at the first failure
python -m pytest tests/ -q --lf             # re-run only what failed last time
```

**List what exists without running it:**

```bash
python -m pytest tests/ --collect-only -q
```

### What each group covers

<!-- test-inventory:begin -->

#### Statistics and analysis

| tests | what it checks | run only this |
|---|---|---|
| 5 | The analysis command documented in this file actually runs and prints its banner | `pytest tests/tlw/analysis/test_cli.py -q` |
| 16 | Run discovery and parsing, including the guard that stops a pilot being pooled into a headline | `pytest tests/tlw/analysis/test_loaders.py -q` |
| 4 | The retrieval ablation report, which groups runs by whether retrieval was attached | `pytest tests/tlw/analysis/test_rag_report.py -q` |
| 16 | Report assembly: the per-arm table, the headline comparison, the honesty banner | `pytest tests/tlw/analysis/test_report.py -q` |
| 24 | The statistics themselves: bootstrap intervals, Wilson intervals, exact McNemar, checked against `scipy` where an independent implementation exists | `pytest tests/tlw/analysis/test_stats.py -q` |

#### Configuration

| tests | what it checks | run only this |
|---|---|---|
| 42 | Every experiment file shipped in `experiments/` still loads and validates | `pytest tests/tlw/config/test_experiment_configs.py -q` |
| 11 | Config layering: defaults, then the experiment file, then environment overrides | `pytest tests/tlw/config/test_loader.py -q` |
| 37 | The eight validation rules a config must pass, including judge-family independence | `pytest tests/tlw/config/test_validation.py -q` |

#### Evaluation and judging

| tests | what it checks | run only this |
|---|---|---|
| 8 | Reference-match diagnostics, computed separately from correctness and never merged | `pytest tests/tlw/evaluation/test_diagnostics.py -q` |
| 9 | The groundedness diagnostic, which sees retrieved passages but never the reference | `pytest tests/tlw/evaluation/test_faithfulness.py -q` |
| 14 | The blind judge: score parsing, edge cases, and the contract it must satisfy | `pytest tests/tlw/evaluation/test_judge.py -q` |
| 5 | Leakage seals on the evaluation path, including the judge-family rule | `pytest tests/tlw/evaluation/test_leakage.py -q` |

#### Leakage control

| tests | what it checks | run only this |
|---|---|---|
| 14 | The loop's leakage seals: no prompt bound for the student may carry the reference | `pytest tests/tlw/loop/test_leakage_seals.py -q` |
| 10 | The four arm strategies: who is asked what, and in which order | `pytest tests/tlw/loop/test_strategies.py -q` |
| 11 | The store-time tripwire's three rules, each on its own and in combination | `pytest tests/tlw/memory/test_tripwire.py -q` |

#### The loop and its memory

| tests | what it checks | run only this |
|---|---|---|
| 14 | The note store: persistence, ranking, per-run isolation, and the red-team fixture of answer-seeded records it must reject every time | `pytest tests/tlw/memory/test_faiss_backend.py -q` |
| 8 | The retrieval backend and the run-time filter that drops a leaky passage | `pytest tests/tlw/memory/test_rag_backend.py -q` |
| 15 | Prompt presets resolve correctly, and the two quarantined leaking templates refuse to load | `pytest tests/tlw/prompts/test_presets.py -q` |

#### The retrieval study

| tests | what it checks | run only this |
|---|---|---|
| 13 | The grounding window: how much of an article reaches the prompt, and from where | `pytest tests/tlw/wixqa/test_grounding.py -q` |
| 22 | The controlled variables of the retrieval study, and the pure retrieval helpers | `pytest tests/tlw/wixqa/test_prompts_and_retrieval.py -q` |
| 6 | The index builder, whose held-out exclusion seals are the point of the test | `pytest tests/tools/rag/test_builder.py -q` |

#### Composition and registries

| tests | what it checks | run only this |
|---|---|---|
| 30 | The composition root: a config becomes six wired blocks, with no model called | `pytest tests/tlw/runner/test_runner.py -q` |
| 13 | Slot registries resolve real implementations and fail loudly on an unknown name | `pytest tests/tlw/test_registries.py -q` |

#### Published numbers and drivers

| tests | what it checks | run only this |
|---|---|---|
| 71 | Every experiment driver under `scripts/` imports cleanly and has no unbound name | `pytest tests/test_scripts_load.py -q` |
| 61 | Every published figure and table still equals what the documents claim -- point estimates, confidence intervals and counts alike | `pytest tests/tlw/figures/test_published_numbers.py -q` |

**479 tests in 25 files.** Regenerate this table with `python scripts/make_test_inventory.py`.

<!-- test-inventory:end -->

### The two tests that matter most

Two of these are not ordinary unit tests, and are worth knowing about.

**`tests/tlw/figures/test_published_numbers.py`** recomputes each published value from the
committed logs and fails if it no longer equals what `README.md` and `docs/EXPERIMENT_RESULTS.md`
say. It is the reason a number in this repository cannot drift away from its evidence silently. It
covers point estimates, confidence intervals, and the counts the documents quote.

**`tests/test_scripts_load.py`** imports all 66 experiment drivers and separately checks each for a
name that is read but never bound. Nothing else imports `scripts/`, so without it a driver can be
broken by a refactor elsewhere and stay broken while the published numbers still reconcile.

---

## 4. Run an experiment

**Additionally needs:** Ollama running locally with the student model pulled, and a Groq API key in
`.env` for the judge.

```bash
ollama pull qwen2.5:3b
cp .env.example .env      # then put your GROQ_API_KEY in it
```

One run is one config file. The seed is the run's identity and comes from the environment, so a
single config drives all of its pre-registered seeds:

```bash
# PowerShell
$env:EXPERIMENT_PARAMS_SEED="42"
python run.py --config experiments/teaching-loop/1-baseline.yml
```

```bash
# bash
EXPERIMENT_PARAMS_SEED=42 python run.py --config experiments/teaching-loop/1-baseline.yml
```

**Try it small first.** This answers four questions from the training split and writes a complete
run directory, so you can see the shape of the output without waiting hours:

```bash
python run.py --config experiments/teaching-loop/1-baseline.yml \
  --data data/clean/Diabetes_and_Digestive_and_Kidney_Diseases_train.jsonl \
  --limit 4
```

Never point `--data` at the training split for a *measured* run — the held-out set is the default
for a reason.

**What the conditions are.** Each file under `experiments/` is one condition, named for what it
does:

| Directory | Conditions |
|---|---|
| `experiments/teaching-loop/` | `1-baseline` · `2-self-refine` · `3-teacher-feedback` · `4-teacher-sees-answer` |
| `experiments/rag-medquad/` | `{small,large}-model-{no,with}-rag` |
| `experiments/rag-medquad-fair-tests/` | `matching-question-type-only` · `much-bigger-library` |
| `experiments/student-prompt/` | `detailed-prompt-style` |
| `experiments/lora/` | `generate-training-data` |
| `experiments/pilots/` | the small runs used to set parameters before the real ones |

A run writes `runs/<study>/<condition>__seed<n>__<timestamp>/` containing the resolved config, the
per-round log, and a one-line summary. `reports/HOW_TO_REGENERATE.md` gives the exact commands
behind each published study, including the retrieval ones, which use their own drivers under
`scripts/wixqa/`.

---

## 5. Rebuild what a clone does not carry

Search indexes, third-party data and model weights are gitignored because they are large and
rebuildable. Everything needed to *check* the results is committed; these commands are for
*re-running* them.

```bash
python scripts/dataset/fetch_wixqa.py     # third-party corpus -> data/external/
python -m tools.rag.cli                   # search indexes -> indexes/
python -m tools.dataset.cli --all         # 12,428 raw pairs -> 10,024 clean, with a readiness report
```

Set `HF_HUB_OFFLINE=1` for anything that embeds text. Without it the sentence-transformers loader
stalls for about a minute per process whenever it cannot reach huggingface.co:

```bash
HF_HUB_OFFLINE=1 python -m tools.rag.cli
```

---

## 6. The answering engine

`app/` is the engine the results point at: retrieve over a local index, choose which part of the
retrieved text to show, answer with a 3B model. It is a library and a batch script — there is no
HTTP endpoint and no container.

```bash
python app/build_showcase.py --per-set 3
```

That answers a sample of questions three ways — without retrieval, with a narrow grounding window,
and with the wider window the study selected — and writes
`reports/rag-wixqa/demo-showcase.jsonl`. Both the questions where retrieval helps and the ones
where it hurts are kept, which is the point of showing it.

---

## 7. When something goes wrong

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: matplotlib` (or pytest, faiss, …) | `pip install -r requirements.txt` was skipped. `conda env create` alone does not install them. |
| `python` is not recognised, or opens the Microsoft Store | The environment is not active. Run `conda activate tlw`, or name the interpreter by the full path from section 1. |
| Tests hang for a minute, then pass | The sentence encoder is being fetched. Set `HF_HUB_OFFLINE=1` once the cache exists. |
| `MissingEvidence: runs/... is missing` | An analysis wants a run directory a clone does not carry. Everything the *published* numbers need is committed; a missing directory means you asked for something that has to be re-run. |
| A run stops with a leakage error | The guard found the reference answer inside a prompt. That is the guard working — read `docs/LEAKAGE_AUDIT.md` before changing anything. |
| Groq returns 429 | The free tier's daily cap is shared across an organisation. Wait, or use a local judge with `--judge-fallback local:llama3.1:8b`. |
| A command was blocked by `.claude/hooks/guard.py` | Only applies when working through Claude Code. The message names the rule and prints your interpreter path; follow it rather than working around it. |

---

*Every command on this page was run on a clean checkout while writing it. If one does not work for
you, that is a defect worth reporting — the claim this project makes about itself is that a
stranger can reproduce it.*
