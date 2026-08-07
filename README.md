# Teaching Loop for Lightweight LLMs

A research project on **what actually makes a small local LLM better at a specialised domain** —
and what only *looks* like it does. Starting from an iterative teacher–student loop, the project was
rebuilt to remove ground-truth leakage from its own evaluation, then used to measure each proposed
improvement honestly: the teaching loop, RAG, and LoRA fine-tuning.

**Headline findings (all measured on held-out data with 95% CIs — see [Key Results](#key-results)):**

- An independent **teacher in the loop adds nothing** (+0.003, p = 1.00). Plain **self-refinement**
  is the part that worked (+0.091).
- **RAG helps only when the model genuinely lacks the knowledge** — no effect on a saturated
  medical-QA testbed, **+0.152** on a real product knowledge base.
- **How retrieved text is delivered into the prompt mattered more than which retriever produced it**
  (+0.130 from a prompt-construction fix, versus +0.025 from a better retriever).
- **Naive LoRA fine-tuning on reference answers hurt** (−0.292).

> ⚠️ **On the older "25% → 83% → 100%" claim.** Earlier versions of this repo reported those numbers.
> The project's own audit showed they were an artefact of ground-truth leakage and a
> similarity-based metric, not real learning. They are retired: see
> [docs/archive/PROJECT_OVERVIEW_AND_RESULTS.md](docs/archive/PROJECT_OVERVIEW_AND_RESULTS.md)
> for the record and the correction. Reporting this honestly is the point of the rebuild.

---

## Table of Contents

- [Overview](#overview)
- [Key Results](#key-results)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Experimental Phases](#experimental-phases)
- [Cost Analysis](#cost-analysis)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

### The Problem

Small local language models (3–8B) are cheap and private, but weaker on specialised domains. The
usual proposals — teach them with a bigger model, give them RAG, fine-tune them — are widely
assumed to work. **This project measured whether they actually do, for a small business that wants
one local model deep in one domain.**

### The original hypothesis, and what happened to it

The project began as an *iterative teaching loop*: a large teacher model critiques the small
student's answer, successful teaching episodes are stored in FAISS memory, and the student improves
over rounds. Early results looked excellent (25% → 83% → 100%).

**They did not survive audit.** The teacher was shown the reference answer every round, memory was
storing reference answers and retrieving them later, and the score measured *similarity to a
reference* rather than correctness. The system was, in effect, being graded on how well it copied an
answer key it had been given.

So the project was rebuilt around one rule: **make leakage structurally impossible, then re-measure
everything.** The judge never sees the reference; a run aborts if ground truth reaches a student
prompt; every headline number is a held-out, multi-seed effect with a confidence interval.

### What the rebuild found

| proposed lever | verdict |
|---|---|
| Teacher-in-the-loop | ❌ adds nothing (+0.003, p = 1.00) — **dropped** |
| Self-refinement | ✅ real on its own (+0.091) … but ❌ adds nothing once RAG is in place |
| Memory of past episodes | ❌ was the main leakage path; redesigned to store *coaching notes, never answers* |
| RAG | ⚠️ **conditional** — nothing when the model already knows the domain, +0.152 when it does not |
| Grounding (how retrieved text enters the prompt) | ✅ **the biggest lever found** (+0.130), and free |
| LoRA fine-tuning on reference answers | ❌ actively harmful (−0.292) |

### Principles the project runs on

- **Honesty over optics** — every reported number must match its source log; negative results are
  reported as plainly as positive ones (most of the findings above are negative).
- **No ground-truth leakage in evaluation** — enforced in code, not by convention.
- **Reproducible** — seeded, single-command, with the resolved config recorded next to every run.
- **Evidence-backed** — claims cite a file, a line, or a command that was actually run.
- **Cheap checks before expensive ones** — offline metrics and pilots gate every costly run.

---

## Key Results

Every number below is computed from a committed run log, on held-out questions, with a
pre-registered statistic (paired cluster bootstrap 95% CI + exact McNemar). Full reports are linked
in the last column.

### 1. Does the teaching loop work? (MedQuAD, 125 held-out × 3 seeds, student `qwen2.5:3b`)

| Arm | Pass rate | Effect | Verdict | Report |
|---|---|---|---|---|
| A — single pass (baseline) | 0.821 | — | | [TRACK_A_RESULTS](docs/TRACK_A_RESULTS.md) |
| B — self-refinement | 0.912 | **B−A = +0.091** [+0.051, +0.133], p < 0.0001 | ✅ **real** | |
| C — independent teacher | 0.915 | **C−B = +0.003** [−0.021, +0.029], p = 1.00 | ❌ **adds nothing** | |
| D — teacher sees the answer | 0.940 | *labelled leakage ceiling, not a result* | ⚠️ | |

**Conclusion:** the value was in the model critiquing its own answer, not in the teacher. The
teacher-in-the-loop was dropped from the product.

### 2. Does RAG help? (two testbeds, deliberately)

| Testbed | Why it was chosen | 3B baseline | +RAG | Effect | Report |
|---|---|---|---|---|---|
| **MedQuAD** (medical QA) | the model already knows this | 0.821 | 0.816 | **−0.005** [−0.067, +0.056] → **no effect** | [RAG_RESULTS](docs/RAG_RESULTS.md) |
| **WixQA** (real product knowledge base) | the model has *no* knowledge of it | 0.163 | 0.315 | **+0.152** [+0.090, +0.213], p = 5e-11 | [WIXQA_RESULTS](docs/WIXQA_RESULTS.md) |

**Conclusion — the law this project set out to prove:** *RAG helps if and only if the retrieved text
actually contains the answer.* Demonstrated as a **dose-response**: raising retrieval hit-rate
0.55 → 0.665 raised the pass rate along a predicted line, while the payoff *given* a correct
retrieval stayed pinned (0.400 → 0.411) — the retriever changes **how often** the answer is found,
not the value of finding it.

### 3. What actually moved the needle on WixQA

| System | Pass rate | What changed |
|---|---|---|
| no RAG | 0.163 | — |
| + RAG (MiniLM, whole article) | 0.315 | retrieval added |
| + best retriever (BGE + chunking) | 0.340 | **+0.025** — better retrieval |
| **+ grounding repair** | **0.470** | **+0.130** [+0.072, +0.188], p = 3.5e-08 — *only the prompt construction changed* |
| + self-refinement on top | 0.470 | **+0.000** — no additional benefit |

**Conclusion:** the biggest single win was **delivery** — we were truncating retrieved articles at
900 characters, so the student saw only ~25% of the article and ~36% of the answer's content. Fixing
*how much and which part* of the retrieved text reaches the prompt was worth **5× more** than
upgrading the retriever, and costs nothing at inference time.

### 4. Does LoRA fine-tuning help? (QLoRA 4-bit on the 3B, held-out 125)

**No: −0.292** [−0.360, −0.224]. The fine-tune successfully transferred the reference *style* — and
that style was terser than the evaluation's completeness bar, so answers got ~30–45% shorter and
failed. → [PRODUCT_RESULTS](docs/PRODUCT_RESULTS.md)

### 5. The recurring pattern across all three interventions

RAG passages, wider context, and self-refinement each **helped answers that were deficient and taxed
answers that were already adequate.** Where a selective policy was simulated it was clearly positive
(oracle +0.099 for RAG, +0.038 for refinement) — but the small model could not decide *for itself*
when to apply it (it called its own answer "complete" 59% of the time, including when wrong).
**The missing component is a reliable gate, not a better intervention.**

---

## System Architecture

One run is one YAML file resolved through six registries. Behaviour changes by editing
configuration, never by editing the core — that is the whole point of the design (ADR-016/017).

```
experiments/<study>/<condition>.yml           run.py --config <that file>
        |                                            |
        +--> config/base.yml (defaults) -------------+
                     |
                     v
        +------------------------------------------------------------------+
        |  src/tlw/runner.py  — the composition root                        |
        |  resolves six slots, each through a registry:                     |
        |                                                                   |
        |   A student   -> ProviderRegistry   (local Ollama / Groq)         |
        |   B teacher   -> ProviderRegistry   (may see the reference)       |
        |   C preset    -> PresetRegistry     (prompt templates)            |
        |   D memory    -> MemoryRegistry     (none | faiss | rag)          |
        |   E params    -> StrategyRegistry   (arm A/B/C/D, rounds, seed)   |
        |   F eval      -> Judge              (blind or reference-comparing)|
        +----------------------------+--------------------------------------+
                                     |
                                     v
        +------------------------------------------------------------------+
        |  src/tlw/loop/  — the arm runs its rounds                          |
        |   round 1: (optional RAG grounding) -> student answers -> judge    |
        |   round N: critique/feedback -> student rewrites -> judge          |
        |   assert_gt_free() aborts if the reference ever reaches a prompt   |
        +----------------------------+--------------------------------------+
                                     |
                                     v
              runs/<study>/<condition>__seed<N>__<ts>/
                  summary.jsonl · rounds.jsonl · config_used.json
                                     |
                                     v
              src/tlw/analysis/  ->  paired bootstrap CI + McNemar  ->  reports/
```

### The four arms

| Arm | What feeds the next round | Measures |
|---|---|---|
| **A** baseline | nothing — single pass | the floor |
| **B** self-refine | the student's own critique | whether iterating helps at all |
| **C** blind teacher | an independent model, **without** the reference | whether a *teacher* adds anything over B |
| **D** sighted teacher | a teacher **with** the reference | a labelled leakage ceiling — never reported as a result |

`C − B` is the pre-registered headline: it isolates the teacher from the act of iterating.

### Key components

| Component | Where | Responsibility |
|---|---|---|
| Composition root | `src/tlw/runner.py` | config → six slots → run → write artifacts |
| Config loader | `src/tlw/config/` | layered merge + fail-loud validation (V1–V8) |
| Registries | `src/tlw/registries.py` | one resolver per swappable seam |
| Arm strategies | `src/tlw/loop/strategies.py` | A/B/C/D; no ground-truth path exists in any of them |
| Leakage guard | `src/tlw/loop/core.py` | `assert_gt_free` — aborts the run if the reference leaks |
| Memory | `src/tlw/memory/` | `none` / `faiss` (notes, GT-tripwired) / `rag` (corpus) |
| Evaluation | `src/tlw/evaluation/` | judge + diagnostics kept structurally separate |
| Analysis | `src/tlw/analysis/` | bootstrap CI, McNemar, Wilson — the pre-registered stats |
| Providers | `src/providers/` + `src/tlw/providers.py` | Groq, Gemini, and Ollama registered as `local` |

## Installation

### Prerequisites

| Requirement       | Version    | Notes                                    |
|-------------------|------------|------------------------------------------|
| Python            | 3.9+       | Tested on 3.11                           |
| CUDA (optional)   | 12.4       | For local GPU inference                  |
| RAM               | 8GB+       | 16GB recommended for local models        |
| Groq API Key      | -          | Free tier available                      |

### Step 1: Clone Repository

```bash
git clone https://github.com/Kosakiri/Teaching-light-weight-llm.git
cd Teaching-light-weight-llm
```

### Step 2: Create Conda Environment

```bash
# Create environment with PyTorch and CUDA support
conda env create -f environment.yml

# Activate environment
conda activate tlw
```

**environment.yml contents:**

```yaml
name: tlw
channels:
  - pytorch
  - nvidia
  - conda-forge
dependencies:
  - python=3.11
  - pytorch
  - torchvision
  - torchaudio
  - pytorch-cuda=12.4
  - pip
```

### Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Core dependencies include:**

| Package               | Version    | Purpose                           |
|-----------------------|------------|-----------------------------------|
| transformers          | >=4.43.0   | HuggingFace model loading         |
| accelerate            | >=0.33.0   | Device orchestration              |
| sentence-transformers | >=3.0.1    | Semantic embeddings               |
| faiss-cpu             | >=1.8.0    | Vector similarity search          |
| groq                  | >=0.11.0   | Groq API client                   |
| google-genai          | >=1.46.0   | Gemini API client                 |
| openai                | >=1.40.0   | OpenAI API client                 |
| rouge-score           | >=0.1.2    | ROUGE evaluation metric           |
| pydantic              | >=2.7.0    | Configuration validation          |
| rich                  | >=13.7.1   | Pretty console output             |

### Step 4: Configure API Keys

```bash
# Create .env file
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
echo "GOOGLE_API_KEY=your_gemini_api_key_here" >> .env  # Optional
```

**Get API Keys:**

| Provider | URL                                | Free Tier               |
|----------|------------------------------------|-----------------------|
| Groq     | https://console.groq.com/keys      | 30 RPM, 6K TPM          |
| Gemini   | https://aistudio.google.com/apikey | Available               |

### Step 5: Verify Installation

```bash
python -c "import torch; import transformers; import groq; print('Installation OK')"
```

---

## Configuration

**One run = one config file = six slots**, each resolved through a registry. `config/base.yml` holds
every default — it is the only place a default lives, so a comment can never disagree with a value.
An experiment file contains *only the diffs*, which is what makes its intent readable at a glance.

```yaml
# experiments/rag-medquad/small-model-with-rag.yml — only what differs from base.yml
student: { provider: local, model: qwen2.5:3b }         # A — the model under test
memory:  { type: rag, corpus_path: indexes/medquad-diabetes-train, top_k: 3 }   # D — retrieval
params:  { arm: A, max_rounds: 1 }                      # E — seed comes from the environment
eval:
  judge: { provider: groq, model: llama-3.1-8b-instant } # F — Llama judge ≠ Qwen student (§0.2)
  pass_threshold: 1.0
```

`params.seed` is deliberately **not** in a multi-seed config: the seed is the run's identity, supplied
per invocation via `EXPERIMENT_PARAMS_SEED`, so one file drives all pre-registered seeds.

### The validation that runs at load (fail-loud, never silent)

| Rule | What it prevents |
|---|---|
| **V1** weights sum to 1.0 | silently mis-scaled metrics |
| **V2** judge family ≠ student family | a model grading itself (§0.2) |
| **V3** unknown keys rejected | a typo'd key vanishing instead of failing |
| **V4** seed mandatory | an unreproducible run (§0.3) |
| **V5** thresholds only under `eval` | config drift |
| **V6** memory-store denylist | re-loading a ground-truth-seeded store |
| **V7** enums and ranges | an invalid arm or provider reaching the runner |
| **V8** arm A/B requires non-accumulating memory | a "baseline" that quietly learns across questions |

Full contract: [`.claude/rules/schema.md`](.claude/rules/schema.md).

## Usage

### Run one experiment

```bash
# the seed is the run's identity, so one config drives all pre-registered seeds
EXPERIMENT_PARAMS_SEED=42 python run.py --config experiments/teaching-loop/1-baseline.yml
```

Add `--limit 4 --data data/clean/<...>_train.jsonl` for a mechanics-only smoke run — never point a
smoke run at the held-out split.

### Reproduce a published number

Every headline recomputes from the committed logs, offline, with no API key:

```bash
# the loop ablation: teacher +0.003 (nothing), self-refine +0.091 (real)
python -m src.tlw.analysis --runs-dir runs/teaching-loop-medquad --comparison C-B --comparison B-A

# RAG where the model already knows the domain: no effect
python -m src.tlw.analysis --runs-dir runs/rag-medquad --rag

# RAG where it does not: +0.152, and the dose-response proof
python scripts/wixqa_analyze.py
python scripts/wixqa_dose_analyze.py
```

### Rebuild the artifacts a clone does not have

```bash
python scripts/dataset/fetch_wixqa.py        # third-party data (gitignored)
python -m tools.rag.cli                      # search indexes -> indexes/
python -m tools.dataset.cli --all            # clean + split MedQuAD
```

### Tests

```bash
python -m pytest tests/ -q
```

## Project Structure

```
config/         authored configuration — base.yml holds every default
experiments/    one YAML per run condition, grouped by study
data/           INPUTS ONLY (raw is immutable; external/ is third-party; legacy/ is pre-renovation)
indexes/        built search indexes — gitignored, rebuildable
src/            library code — core/ providers/ tlw/(config memory prompts evaluation loop analysis)
scripts/        thin drivers; each imports from src/ or tools/
tools/          reusable CLI utilities — dataset cleaner/assessor, RAG index builder
tests/          mirrors src/ and tools/
runs/           experiment artifacts, grouped by the question each study answers
reports/        the small, committed, human-readable evidence behind every number
docs/           narrative — start at docs/README.md
logs/           pre-renovation experiment evidence — immutable
models/         LoRA adapters and base weights — gitignored
```

The full annotated tree, the rule for where a new file goes, and the tracking policy live in
[`.claude/rules/structure.md`](.claude/rules/structure.md).

**Two conventions worth knowing before you add anything:**

1. **Source and artifacts never share a directory.** Anything a command regenerates goes under
   `runs/`, `indexes/`, `models/` (gitignored) or `reports/` (tracked, small).
2. **Names read as English.** The path carries a short human label — `runs/rag-wixqa/4-rag-wider-context/` —
   and the exact condition lives in a `manifest.json` beside the run, never encoded in the filename.

## Experimental Phases

### Phase 1 — the original exploration (2025, superseded)

Phases 0–6 explored feedback styles, memory and hyper-parameters, and reported "25% → 83% → 100%".
An audit then found the evaluation itself was compromised: the teacher saw the reference answer every
round, memory stored reference answers, and the metric scored *similarity to a noisy reference*
rather than correctness. **Those numbers are retired** — kept, with the full correction, in
[docs/archive/PROJECT_OVERVIEW_AND_RESULTS.md](docs/archive/PROJECT_OVERVIEW_AND_RESULTS.md).

### Phase 2 — honest rebuild (Track A)

The evaluation was rebuilt so leakage is structurally impossible (the judge never sees the reference;
a run aborts if ground truth reaches a student prompt), then the loop was re-measured on held-out
data across 3 seeds. Result: **self-refinement is real (+0.091), the teacher adds nothing (+0.003)**.
→ [TRACK_A_RESULTS.md](docs/TRACK_A_RESULTS.md)

### Phase 3 — the product levers (Track B)

RAG and LoRA measured under the same protocol, on two deliberately different testbeds, ending in a
dose-response proof of *when* RAG works and a study of how retrieved text should be delivered.
→ [RAG_RESULTS.md](docs/RAG_RESULTS.md) · [WIXQA_RESULTS.md](docs/WIXQA_RESULTS.md) ·
[PRODUCT_RESULTS.md](docs/PRODUCT_RESULTS.md) · **unified write-up: [RAG_LAW.md](docs/RAG_LAW.md)**

---

## Cost Analysis

### Groq API Pricing

| Model                             | Input (per 1M) | Output (per 1M) |
|-----------------------------------|----------------|-----------------|
| Llama 3.3 70B Versatile (Teacher) | $0.59          | $0.79           |
| Llama 3.1 8B Instant (Student)    | $0.05          | $0.08           |

### Experiment Costs

| Phase          | Questions | Total Tokens | Cost (AUD) |
|----------------|-----------|--------------|------------|
| Full Experiment| 290       | 920K         | $0.50      |

### What the current system costs to run

The measured configuration runs the **student and the retriever entirely locally** (Ollama +
FAISS on an RTX 4060), so the only cloud cost is the evaluation judge:

| Component | Where it runs | Cost |
|---|---|---|
| Student (`qwen2.5:3b`) | local (Ollama) | free |
| Retrieval (BGE embeddings + FAISS) | local, index built once offline | free |
| Grounding repair (wider, chunk-centred window) | prompt construction only | free — **no extra inference** |
| Evaluation judge (`llama-3.1-8b-instant`) | Groq free tier | free, but capped at 500K tokens/day org-wide — the binding constraint on how fast experiments finish |

Self-refinement was measured as roughly **3× the inference cost** for **no measurable gain**, so it
is not part of the recommended configuration.

---

## Troubleshooting

**Groq returns `429 Too Many Requests`.** The free tier's daily token cap is org-wide and is the
binding constraint on how fast an evaluation finishes. The judging scripts are built for it: they
self-pace, persist every score immediately, stop cleanly on the daily cap and resume idempotently.
Re-run the same command after the reset — nothing is lost and nothing is double-charged.

```bash
HF_HUB_OFFLINE=1 python scripts/wixqa_judge.py --glob 'runs/rag-wixqa/*/seed*.jsonl'
```

Never substitute a different judge mid-experiment to get around the cap — a mixed judge confounds
every comparison in that arm.

**The embedding model hangs for ~60 s.** `sentence-transformers` tries to reach huggingface.co first.
Set `HF_HUB_OFFLINE=1` for any command that embeds.

**A run aborts with a leakage error.** That is the guard working: `assert_gt_free` found the reference
answer inside a student-bound prompt. Do not disable it — find the path that leaked.

**`ModuleNotFoundError: No module named 'src'`.** Run from the repo root, or via `python -m`. Tests
resolve this through `pytest.ini` (`pythonpath = .`).

**The GPU is busy.** The 8 GB card cannot host the student and a local judge at once. Use a cloud
judge, or wait — the run scripts are resumable.

## License

### Project License

MIT License

### Model License

This project uses **Meta Llama 3.1** models under the [Llama 3.1 Community License Agreement](models/Llama-3.1-8B-Instruct/LICENSE).

Key terms:
- Non-exclusive, worldwide, royalty-free license
- Must display "Built with Llama" on related websites/documentation
- Must include "Llama" in any derivative AI model names
- Must retain attribution notice in all copies

**Attribution Notice:**
```
Llama 3.1 is licensed under the Llama 3.1 Community License,
Copyright (c) Meta Platforms, Inc. All Rights Reserved.
```

---

## Citation

```bibtex
@software{teaching_loop_2025,
  title   = {Teaching Loop for Lightweight LLMs},
  author  = {Phakphoom Deesuwan},
  year    = {2025},
  url     = {https://github.com/Kosakiri/Teaching-light-weight-llm},
  note    = {Built with Llama}
}
```

---

**Last Updated**: November 30, 2025  
**Version**: 3.0  
**Status**: Production Ready  
**Built with Llama**
