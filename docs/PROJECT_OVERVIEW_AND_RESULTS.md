# Project Overview and Experimental Results

## 1. Introduction and Problem Setting

This study investigates how to improve the performance of lightweight, cost-efficient language models ("student" models, e.g., Llama-3.1-8B) by surrounding them with an iterative teaching loop driven by a stronger "teacher" model and a small semantic memory.

The central practical question is:

> **If we cannot afford to fine-tune or run very large models all the time, how far can we push a small model using structured feedback, memory, and carefully designed evaluation?**

The work is organised around four research questions:

- **RQ1 – Teaching loop effectiveness**  
  Can multi-round teacher feedback substantially improve the answer quality of small models compared to a one-shot baseline?

- **RQ2 – Evaluation design**  
  How should hybrid evaluation metrics (deterministic + LLM-based) be configured to reliably select good answers?

- **RQ3 – Memory augmentation**  
  Does a simple FAISS-based memory of past successful teaching episodes provide additional measurable benefits?

- **RQ4 – Cost–quality trade-off**  
  What is the empirical trade-off between quality gains (e.g., EM, semantic similarity, judge scores) and token cost (student + teacher tokens, rounds per question)?

To address these questions, the experiments are structured into **Phases 0–5**. Each phase adds, modifies, or ablates specific components of the pipeline (teacher feedback, memory, judge modes, metric weights, maximum rounds). The overall design follows the mapping

> **Design choices → Experimental configurations → Observed metrics and costs**

so that readers can see (1) what changed, (2) why it was changed, and (3) how much it helped in terms of both quality and cost.

---

## 2. System Architecture and Main Components

At a high level, the system implements an **iterative teaching loop** around a small student LLM. For each question, the system:

1. Optionally retrieves similar past cases from a **semantic memory**.
2. Prompts the **student model** to answer (first attempt or refinement).
3. Evaluates the answer using a **hybrid metric** combining deterministic scores and LLM judges.
4. If the answer fails a configured threshold, the **teacher model** generates feedback.
5. The student revises its answer using this feedback, up to a maximum number of rounds or until early-stopping criteria are met.
6. Successful teaching episodes are written back into FAISS memory.

For the final experiments, the simplified implementation is organised around the following Python entry points:

- `simplified_experiment_runner.py` – batch runner for experiments over datasets.
- `simplified_teaching_loop.py` – orchestrator implementing the per-question teaching loop.
- `src/simplified/*.py` – supporting modules (student, teacher, metrics, memory, early-stopping, logging).
- `notebooks/*.ipynb` – Jupyter notebooks for experimental analysis and result visualisation.

These layers separate:

- running controlled experiments,
- implementing the loop logic,
- supporting metrics, memory, and logging, and
- analysing results and producing figures and tables.

### 2.1. Experiment Runner (`simplified_experiment_runner.py`)

**Role.** Top-level script that runs controlled experiments with a given configuration.

**Responsibilities.**

- Parse CLI arguments:
  - configuration path,
  - domain/dataset (Alpaca or Medical),
  - number of questions,
  - mode (`baseline`, `champion_mem_on`, `champion_mem_off`).
- Instantiate `SimplifiedTeachingLoop` using `config/simplified_config.yml`.
- Load questions from JSONL datasets in `data/` via `load_questions()`.
- For each question:
  - call `loop.run(...)` to execute the full teaching loop,
  - collect per-round history and send it to the terminal UI for formatted display.
- After all questions:
  - aggregate metrics via `loop.get_performance_report()`,
  - compute averages (EM, ROUGE-L, semantic similarity, judge scores, rounds, tokens),
  - print a final summary (success rate, memory hit rate, average rounds and tokens),
  - save detailed results (e.g., `test_results.json`, `summary.jsonl`) under `logs/`.

This script is the **experimental harness** that generates the logs summarised in Phases 0–5.

### 2.2. Core Teaching Loop (`simplified_teaching_loop.py`)

**Role.** Implements the **per-question iterative teaching process** and encapsulates the logic for:

- student answer generation,
- teacher feedback,
- hybrid evaluation,
- memory usage,
- early stopping, and
- structured logging.

**Key collaborators.**

- `StudentClient` – `src/simplified/student.py`  
- `TeacherFeedback` – `src/simplified/teacher_feedback.py`  
- `MetricsEvaluator` – `src/simplified/metrics.py`  
- `FAISSMemory` – `src/simplified/memory.py`  
- `EarlyStopping` – `src/simplified/early_stopping.py`  
- `RoundLogger`, `PerformanceMonitor` – `src/simplified/logger.py`, `src/simplified/monitor.py`  
- `DebugLogger`, `TerminalUI` – `src/simplified/debug_logger.py`, `src/simplified/terminal_ui.py`  

**Main workflow in `SimplifiedTeachingLoop.run(...)`.**

1. **Configuration and initialisation.**  
   Load configuration from `config/simplified_config.yml` and extract `max_rounds`, `pass_threshold`, metric weights, memory thresholds, early-stopping parameters, and repetition-detection thresholds.

2. **Round 1: optional memory retrieval.**  
   Call `self.memory.get_best_feedback(question)` to retrieve the most similar past episode, if memory is enabled and similarity exceeds a threshold.  
   - If a memory item is found, its feedback seeds the first prompt.  
   - Otherwise, the student starts from a minimal template.

3. **Prompt construction.**
   - **Round 1.**
     - With memory feedback: build a refinement-style prompt using retrieved feedback.
     - Without memory: build a minimal first-attempt prompt.
   - **Later rounds.**
     - If repetition is detected or a configured "hint round" is reached, build a last-chance prompt including a partial ground-truth hint.
     - Otherwise, build a standard refinement prompt using the latest teacher feedback.

4. **Student answer generation.**  
   Call `self.student.answer(prompt)` to generate an answer from the small model and track student token usage.

5. **Hybrid evaluation.**  
   Call `self.metrics.evaluate(...)` to compute:
   - deterministic metrics: **Exact Match (EM)**, **ROUGE-L**, **semantic similarity** (encoder-based),
   - LLM-based metrics: **blind judge score**, **comparison judge score**.  
   Combine them into a single `final_score` via configurable `metric_weights`.

6. **Decision, feedback, and early stopping.**
   - If `final_score ≥ pass_threshold`, mark the question as solved.
   - Otherwise:
     - apply early-stopping checks:
       - `max_rounds` reached?
       - score plateau over several rounds?
       - repetition loop detected?
     - if the loop continues, call `self.teacher.generate_feedback(...)` to obtain feedback for the next round.

7. **Memory update and logging.**
   - On success, write a compact teaching episode (question, ground truth, final feedback, summary scores) into FAISS memory.
   - Log round-by-round details and aggregate statistics via logging modules.

The loop returns a structured record containing: success flag, final answer and final score, number of rounds, and per-round history (metrics, prompts, feedback).

### 2.3. Analysis Layer: Jupyter Notebooks (`notebooks/*.ipynb`)

**Role.** Post-experiment analysis, visualisation, and interpretation.

Jupyter notebooks form a separate analysis layer:

- load summary metrics from `logs/organized_data/phase*_*/summary.jsonl`,
- load detailed trajectories from `logs/phase5_full_experiment/debug_per_round.jsonl`,
- compute derived statistics:
  - per-phase deltas (e.g., EM gain from Phase 0 → Phase 5),
  - cost–quality curves (tokens vs EM, tokens vs semantic similarity),
  - memory hit distributions by domain,
- produce tables and graphs:
  - EM vs phase,
  - semantic similarity vs phase,
  - tokens per question vs EM,
  - distribution of rounds per question.

Experiment logs are treated as data, and the notebooks act as **reproducible analysis scripts**.

---

## 3. Loop Structure and Algorithm

This section describes the teaching loop independently of any particular dataset or configuration and shows how its design supports the research questions:

- where memory enters the loop (RQ3),
- how teacher feedback is integrated (RQ1),
- how hybrid metrics gate progress (RQ2),
- how cost (tokens and rounds) emerges (RQ4).

### 3.1. Teaching Loop Architecture (Flow Chart)

For each question, the system executes a closed-loop mini-experiment:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                  Simplified Teaching Loop (per question)              │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                       ┌───────────────────────────┐
                       │   Load Question           │
                       │   + Ground Truth          │
                       └─────────────┬─────────────┘
                                     │
                                     ▼
                       ┌───────────────────────────┐
                       │   Initialise State        │
                       │   - round = 1             │
                       │   - reset early stopping  │
                       │   - clear history         │
                       └─────────────┬─────────────┘
                                     │
                                     ▼
                       ┌───────────────────────────┐
                       │ Memory Retrieval (r = 1)  │
                       │  FAISS search if enabled  │
                       └─────────────┬─────────────┘
                                     │
                          ┌──────────┴───────────┐
                          │                      │
                          ▼                      ▼
              ┌──────────────────────┐   ┌──────────────────────┐
              │ High-sim memory hit? │   │   No suitable hit    │
              └──────────┬───────────┘   └──────────┬───────────┘
                         │                         │
                         ▼                         ▼
          ┌───────────────────────────┐  ┌───────────────────────────┐
          │ Build prompt from         │  │ Build first-attempt       │
          │ retrieved feedback        │  │ minimal student template  │
          └─────────────┬─────────────┘  └─────────────┬─────────────┘
                        │                            │
                        └──────────────┬─────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────┐
                       │     Student model         │
                       │     generates answer      │
                       └─────────────┬─────────────┘
                                     │
                                     ▼
                       ┌───────────────────────────┐
                       │   Hybrid evaluation       │
                       │   EM, ROUGE-L, semantic   │
                       │   Blind + comparison     │
                       └─────────────┬─────────────┘
                                     │
                                     ▼
                       ┌───────────────────────────┐
                       │  Compute final_score      │
                       │  (weighted combination)   │
                       └─────────────┬─────────────┘
                                     │
                           ┌─────────┴─────────┐
                           │                   │
                           ▼                   ▼
                 Score ≥ threshold       Score < threshold
                           │                   │
                           │                   ▼
                           │       ┌────────────────────────┐
                           │       │   Early-stopping?      │
                           │       │ max_rounds / plateau / │
                           │       │ repetition detected    │
                           │       └──────────┬─────────────┘
                           │                  │
                           │           ┌──────┴───────┐
                           │           │              │
                           │           ▼              ▼
                           │        CONTINUE       STOP (fail)
                           │           │
                           │           ▼
                           │   ┌──────────────────┐
                           │   │ Teacher generates│
                           │   │ feedback         │
                           │   └──────────┬───────┘
                           │              │
                           │              ▼
                           │   ┌──────────────────┐
                           │   │   Update state   │
                           │   │   round += 1     │
                           │   └──────────┬───────┘
                           │              │
                           └──────────────┘
                                      ▲
                                      │
                        ┌─────────────┴─────────────┐
                        │  If success (pass):       │
                        │  - write episode to       │
                        │    FAISS memory           │
                        │  - log metrics & tokens   │
                        └───────────────────────────┘
```

From a research perspective:

* **State initialisation** makes each question an independent mini-experiment.
* **Single memory consult** explains the relatively low memory hit rates in Phase 5 (5% Alpaca, 12% Medical).
* **Hybrid evaluation + threshold** directly drives the EM and semantic improvements reported later.
* **Early stopping before teacher calls** explains why average rounds are well below `max_rounds = 10`, even though tokens per question increase substantially.

### 3.2. Algorithmic Pseudocode

The following pseudocode mirrors the implemented loop:

```text
FUNCTION teaching_loop(question, ground_truth, config):
    # 1. Memory retrieval (round 1 only)
    memory_feedback = memory.search(question)

    # 2. Initialise loop state
    round = 1
    previous_answer = None
    feedback = memory_feedback if memory_feedback else None
    scores_history = []

    WHILE round <= config.max_rounds:
        # 3. Build prompt
        IF round == 1 AND feedback is None:
            prompt = build_first_attempt_prompt(question)
        ELSE IF repetition_detected(previous_answer, scores_history) OR \
                round == config.hint_round:
            prompt = build_last_chance_prompt(question, ground_truth, feedback)
        ELSE:
            prompt = build_refinement_prompt(question, previous_answer, feedback)

        # 4. Student generates answer
        answer = student_model.generate(prompt)

        # 5. Evaluate answer
        metrics = evaluate_hybrid(answer, ground_truth, previous_answer)
        final_score = weighted_sum(metrics, config.metric_weights)
        scores_history.append(final_score)

        # 6. Check success
        IF final_score >= config.pass_threshold:
            memory.save(question, answer, feedback, metrics)
            RETURN SUCCESS(answer, round, metrics)

        # 7. Early stopping BEFORE new teacher call
        IF early_stopping.should_stop(scores_history, round):
            RETURN FAILURE(answer, round, metrics)

        # 8. Generate teacher feedback
        feedback = teacher_model.generate_feedback(
            question, answer, ground_truth,
            previous_feedback=feedback,
            round_num=round
        )

        # 9. Update state
        previous_answer = answer
        round += 1

    # Max rounds reached
    RETURN FAILURE(answer, config.max_rounds, metrics)
```

These trajectories (per-round scores and prompts) are stored in logs and form the basis of the quantitative analysis in Sections 6–8.

### 3.3. Key Design Decisions

1. **Iterative refinement instead of single-shot answers.**
   The loop encodes the hypothesis that structured feedback plus multiple attempts can substantially improve quality even without updating model weights.

2. **Hybrid metrics rather than a single objective.**
   EM is strict; semantic similarity is meaning-oriented but can reward vague answers; LLM judges approximate human grading. A weighted combination balances these signals and was tuned in Phases 2–3.

3. **FAISS memory as a lightweight augmentation.**
   Memory stores compact episodes (question, ground truth, feedback, scores) and retrieves high-quality precedents. Its simplicity keeps the main focus on the teaching loop.

4. **Early stopping and repetition detection.**
   These mechanisms prevent wasting rounds on plateaued or repetitive behaviour, which is crucial when tokens are expensive.

5. **Ground-truth hints as a last resort.**
   When the student is stuck, a late-round prompt includes a partial hint based on the ground truth, allowing the model to recover rather than failing silently.

---

## 4. Supporting Modules (Simplified Layer)

### 4.1. Student Module (`src/simplified/student.py`)

* Provides prompt builders for:

  * first-attempt prompts (short templates),
  * refinement prompts that include the question, previous answer, and teacher feedback.
* `StudentClient` wraps the chosen provider (Gemini, Groq, OpenAI, or local) and:

  * issues chat calls,
  * tracks student token usage,
  * cleans answers (remove markers like "Answer:", trim incomplete tails).

The module is deliberately thin: it only converts prompts into outputs and leaves control decisions to the loop.

### 4.2. Teacher Feedback Module (`src/simplified/teacher_feedback.py`)

* Generates teaching feedback in several styles:

  * **CoT feedback** (default),
  * **template-based feedback**,
  * **Socratic feedback** (question-driven).
* Configured via `config/simplified_config.yml` (model, provider, temperature, max tokens, verbosity).
* The core method `generate_feedback(...)`:

  * builds a prompt from the question, student answer, ground truth, previous feedback, and round,
  * calls the teacher LLM,
  * extracts a concise feedback string (≈ ≤ 200 characters),
  * optionally returns a debug object (full prompt + raw response).

Prompt variants are defined in `config/prompts_config.yml` and loaded via the `prompt_loader`.

### 4.3. Metrics, Memory, Early Stopping, Logging

* **MetricsEvaluator (`src/simplified/metrics.py`)**

  * computes EM, ROUGE-L, semantic similarity, blind judge score, and comparison judge score,
  * combines them into a single `final_score` using tuned weights (for the champion: blind ≈ 0.24, comparison ≈ 0.39, semantic ≈ 0.21, ROUGE-L ≈ 0.10, EM ≈ 0.05).

* **FAISSMemory (`src/simplified/memory.py`)**

  * stores compact teaching episodes,
  * indexes them with FAISS,
  * provides `get_best_feedback(question)` based on similarity and quality filters.

* **EarlyStopping (`src/simplified/early_stopping.py`)**

  * monitors score trajectories,
  * stops when `max_rounds` is reached, when the score plateaus over a patience window, or when repetition is detected.

* **Logging and monitoring modules**

  * log per-round answers, metrics, feedback,
  * compute aggregated statistics (EM, semantic similarity, judge scores, rounds, tokens),
  * write JSONL logs for detailed analysis,
  * render summaries in the terminal UI.

---

## 5. Configuration, Data, and Logs

### 5.1. Configuration Files (`config/`)

* `config/simplified_config.yml` – main system configuration (student/teacher models, loop parameters, metric configuration, memory settings, logging and dataset paths).
* `config/prompts_config.yml` – prompt templates for student and teacher.
* `legacy/config/experiments/` – earlier, richer configuration files kept for reference.

### 5.2. Data Files (`data/`)

* Alpaca-style instruction datasets:

  * `alpaca_20.jsonl`,
  * `alpaca_100.jsonl`,
  * `alpaca_questions.jsonl`.
* Medical Q&A datasets:

  * `medical_100.jsonl`,
  * `medical_all_clean.jsonl`,
  * source-specific splits in `medical_by_source/`,
  * CSVs in `Medical_Q&A/`.

These provide the two core domains: **Alpaca** (general instruction) and **Medical** (specialised Q&A).

### 5.3. Logs and Result Files (`logs/`)

* Aggregated logs:

  * `phase0_baseline/summary.jsonl`,
  * `phase1_teacher_student/summary.jsonl`,
  * `phase3_judge_modes/summary.jsonl`,
  * `phase4_final_validation/summary.jsonl`,
  * `phase5_full_experiment/summary.jsonl`.
* Per-round trajectories:

  * `phase5_full_experiment/debug_per_round.jsonl`.

All quantitative results reported below are derived from these files.

---

## 6. Phase-Wise Experimental Design and Results (0–5)

### 6.1. Phase 0 – Baseline (No Teaching Loop)

* Single-shot student, no teacher, no memory.
* Optional LLM judges evaluated **after** answer generation.

**Metrics (Alpaca dev).**

* EM: 0.05
* ROUGE-L: ≈ 0.3794
* Semantic similarity: ≈ 0.7313
* Blind judge: 0.0 (or ≈ 0.885 when enabled)
* Comparison judge: 0.0 (or ≈ 0.73)
* Avg. rounds: 1.0

This configuration serves as the reference point.

### 6.2. Phase 1 – Teacher + Student Templates + Memory

Phase 1 introduces:

* teacher feedback,
* multi-round prompting,
* early FAISS memory,
* simplified student prompts.

Key configurations (`template_feedback_minimal`, `cot_feedback_simple_minimal`) increase EM to 0.20 and semantic similarity to ≈ 0.80–0.83, at ≈ 1.75–1.8 rounds per question, with high memory usage (≈ 0.85 hit rate).

### 6.3. Phases 2–3 – Metric / Configuration Search and Judge Modes

A configuration search tunes:

* metric weights for EM, ROUGE-L, semantic similarity, blind judge, comparison judge,
* judge modes (hybrid, comparison-only, deterministic-only).

The champion `hybrid_full` configuration reaches:

* EM ≈ 0.30,
* semantic similarity ≈ 0.867–0.916,
* comparison judge ≈ 0.94

on Alpaca dev sets, with ≈ 1.6–2.35 rounds depending on the judge mode.

### 6.4. Phase 4 – Memory Ablation

Using the champion configuration (comparison-only judges, `max_rounds = 3`), Phase 4 ablates memory across Alpaca and Medical dev sets.

**Table 1 – Phase 4: Memory ablation (dev; max_rounds = 3).**

| Domain  | Mode    | EM   | ROUGE-L | Semantic Sim. | Blind Judge | Comparison Judge | Avg. Rounds |
| ------- | ------- | ---- | ------- | ------------- | ----------- | ---------------- | ----------- |
| Alpaca  | Mem ON  | 0.07 | 0.5344  | 0.7317        | 0.8770      | 0.9420           | 1.13        |
| Alpaca  | Mem OFF | 0.04 | 0.5094  | 0.7251        | 0.8765      | 0.9380           | 1.23        |
| Medical | Mem ON  | 0.01 | 0.3561  | 0.7048        | 0.8725      | 0.8970           | 1.25        |
| Medical | Mem OFF | 0.01 | 0.3687  | 0.7096        | 0.8725      | 0.9020           | 1.27        |

Memory provides only small aggregate benefits under these short-loop settings.

### 6.5. Phase 5 – Full Experiment (100Q × 2 Domains × 3 Modes)

Phase 5 evaluates the champion configuration on realistic test sets:

* **Domains:** Alpaca (100Q), Medical (100Q),
* **Modes:** Baseline, Champion MemON, Champion MemOFF,
* **Champion configuration:** CoT teacher, minimal student, hybrid metric weights from Phase 3, `max_rounds = 10`.

#### 6.5.1. Alpaca

* **Baseline.**

  * EM: 0.07; ROUGE-L ≈ 0.4410; semantic ≈ 0.7202
  * judges = 0.0; rounds = 1.0
  * tokens ≈ 138.57 per question

* **Champion MemON.**

  * EM: 0.66; ROUGE-L ≈ 0.9051; semantic ≈ 0.9637
  * blind ≈ 0.8555; comparison ≈ 0.972
  * rounds ≈ 6.34
  * memory hit rate = 0.05
  * tokens ≈ 5,522.55 per question

* **Champion MemOFF.**

  * EM: 0.62; ROUGE-L ≈ 0.9094; semantic ≈ 0.9595
  * blind ≈ 0.8545; comparison ≈ 0.960
  * rounds ≈ 6.53
  * memory hit rate = 0.00
  * tokens ≈ 5,719.65 per question

#### 6.5.2. Medical

* **Baseline.**

  * EM: 0.00; ROUGE-L ≈ 0.1455; semantic ≈ 0.7022
  * judges = 0.0; rounds = 1.0
  * tokens ≈ 171.52 per question

* **Champion MemON.**

  * EM: 0.37; ROUGE-L ≈ 0.7460; semantic ≈ 0.9343
  * blind ≈ 0.862; comparison ≈ 0.940
  * rounds ≈ 9.23
  * memory hit rate = 0.12
  * tokens ≈ 12,094.33 per question

* **Champion MemOFF.**

  * EM: 0.37; ROUGE-L ≈ 0.7481; semantic ≈ 0.9417
  * blind ≈ 0.866; comparison ≈ 0.939
  * rounds ≈ 9.20
  * memory hit rate = 0.00
  * tokens ≈ 12,164.43 per question

#### 6.5.3. Phase 5 Summary Tables

**Table 2 – Phase 5: Aggregate metrics per domain and mode.**

| Domain  | Mode            | EM   | ROUGE-L | Semantic Sim. | Blind Judge | Comparison Judge | Avg. Rounds | Tokens/Q (S+T) |
| ------- | --------------- | ---- | ------- | ------------- | ----------- | ---------------- | ----------- | -------------- |
| Alpaca  | Baseline        | 0.07 | 0.4410  | 0.7202        | 0.0000      | 0.000            | 1.00        | 138.57         |
| Alpaca  | Champion MemON  | 0.66 | 0.9051  | 0.9637        | 0.8555      | 0.972            | 6.34        | 5522.55        |
| Alpaca  | Champion MemOFF | 0.62 | 0.9094  | 0.9595        | 0.8545      | 0.960            | 6.53        | 5719.65        |
| Medical | Baseline        | 0.00 | 0.1455  | 0.7022        | 0.0000      | 0.000            | 1.00        | 171.52         |
| Medical | Champion MemON  | 0.37 | 0.7460  | 0.9343        | 0.8620      | 0.940            | 9.23        | 12094.33       |
| Medical | Champion MemOFF | 0.37 | 0.7481  | 0.9417        | 0.8660      | 0.939            | 9.20        | 12164.43       |

**Table 3 – Phase 5: Improvement over baseline (per domain).**

| Domain  | Mode            | EM (base → mode) | ΔEM   | Semantic (base → mode) | Tokens/Q (base → mode) | Token ratio |
| ------- | --------------- | ---------------- | ----- | ---------------------- | ---------------------- | ----------- |
| Alpaca  | Champion MemON  | 0.07 → 0.66      | +0.59 | 0.720 → 0.964          | 138.57 → 5522.55       | ≈ 40×       |
| Alpaca  | Champion MemOFF | 0.07 → 0.62      | +0.55 | 0.720 → 0.959          | 138.57 → 5719.65       | ≈ 41×       |
| Medical | Champion MemON  | 0.00 → 0.37      | +0.37 | 0.702 → 0.934          | 171.52 → 12094.33      | ≈ 70×       |
| Medical | Champion MemOFF | 0.00 → 0.37      | +0.37 | 0.702 → 0.942          | 171.52 → 12164.43      | ≈ 71×       |

#### 6.5.4. Placement of Phase 5 Figures

The following sub-section defines where the analysis charts should be placed in the written report.

##### Figure 1 – Quality metrics per experiment

![Figure 1 – Phase 5 quality metrics (EM, semantic similarity, comparison judge) for Alpaca and Medical across Baseline, Champion+MemON, Champion+MemOFF](fig/phase5_quality_metrics.png)

*Caption.*
Figure 1 compares EM, semantic similarity, and comparison-judge scores for all Phase 5 configurations. Champion modes clearly dominate the baseline across all metrics, while differences between MemON and MemOFF are small.

##### Figure 2 – EM vs baseline by domain

![Figure 2 – EM vs Baseline for Alpaca (left) and Medical (right); each panel shows Baseline vs Champion+MemOFF vs Champion+MemON](fig/phase5_em_vs_baseline.png)

*Caption.*
Figure 2 shows EM relative to the baseline for Alpaca and Medical. The Alpaca EM increases from 0.07 to 0.62–0.66, while Medical EM increases from 0.00 to 0.37, illustrating the magnitude of improvement supplied by the teaching loop.

##### Figure 3 – Memory hit rate

![Figure 3 – Phase 5 memory hit rates for champion configurations in each domain](fig/phase5_memory_hit_rate.png)

*Caption.*
Figure 3 displays memory hit rates for the champion configurations: 5% for Alpaca and 12% for Medical. These low but non-zero rates explain why memory has only a modest aggregate effect.

##### Figure 4 – Cost vs quality

![Figure 4 – Cost vs quality: EM (bars, left axis) vs tokens per question (line, right axis) for each domain and mode](fig/phase5_cost_vs_quality.png)

*Caption.*
Figure 4 combines EM (bars) with tokens per question (line) to visualise the cost–quality trade-off. Moving from baseline to champion configurations yields substantial EM gains at the cost of 40–70× additional tokens per question.

##### Figure 5 – Feedback loop dynamics

![Figure 5 – Average final_score per round for Alpaca and Medical champion configurations (MemON and MemOFF)](fig/phase5_feedback_dynamics.png)

*Caption.*
Figure 5 plots the evolution of the average final_score as a function of the round index (1–10). The curves show gradual improvements with a sharp jump in later rounds, reflecting the effect of repeated teacher feedback and the hint mechanism on harder questions.

---

## 7. Cross-Phase Analysis and Discussion

### 7.1. Teacher + Feedback Loop vs Baseline (RQ1)

Across phases, EM and semantic similarity improve monotonically from the one-shot baseline to the Phase-5 champion:

* EM: 0.05 → 0.20 → 0.30 → 0.66 (Alpaca),
* semantic similarity: ≈ 0.73 → ≈ 0.80–0.83 → ≈ 0.87 → ≈ 0.96.

The consistent pattern, together with the qualitative dynamics in Figure 5, supports the conclusion that the **teacher-driven, multi-round loop is the dominant source of improvement**.

### 7.2. Memory ON vs OFF (RQ3)

Comparing MemON vs MemOFF in Phases 4 and 5:

* Memory hit rates are low (5% Alpaca, 12% Medical),
* EM differences are small (e.g., 0.66 vs 0.62 on Alpaca; 0.37 vs 0.37 on Medical),
* Semantic similarity is slightly higher without memory in the Medical domain.

Thus, **memory acts as a secondary mechanism**, offering modest, context-dependent gains while the bulk of improvement comes from the teacher loop and hybrid metrics.

### 7.3. Cost–Quality Trade-off (RQ4)

Table 3 and Figure 4 jointly show that:

* Alpaca improvements are obtained at ≈ 40× token cost,
* Medical improvements require ≈ 70× token cost.

The system therefore defines a **cost–quality frontier** for teaching-loop-enhanced small models. Whether this frontier is acceptable depends on downstream application constraints.

### 7.4. Domain-Specific Behaviour

Medical Q&A is harder for the student:

* more rounds (≈ 9 vs 6),
* more tokens per question (≈ 12k vs 5.5k),
* higher memory activation (12% vs 5%).

Nevertheless, the loop generalises: both domains benefit from the same architecture and configuration, with different cost profiles.

---

## 8. Limitations and Future Work

### 8.1. Limitations

* High token cost (40–70× baseline).
* Simple memory schema, which does not capture rich error types or sub-skills.
* Heuristic thresholds and hyperparameters tuned on limited data.
* No explicit factuality/safety evaluation, especially for medical outputs.
* No parameter updates for the student; gains come purely from prompting and interaction.
* Limited domains (Alpaca-style and medical Q&A).

### 8.2. Future Work

Promising directions include:

1. richer, more selective memory mechanisms (including error taxonomies and difficulty labels);
2. cost-aware and adaptive teaching strategies (allocating rounds based on early signals);
3. reinforcement-learning-based teacher or critic policies optimised for downstream gains;
4. curriculum learning and cross-task sharing of memory;
5. broader evaluations (other domains, human judgements, robustness tests).

---

## 9. Conclusions

This work presents a phase-wise empirical study of a **teaching loop** for small language models. The results show that wrapping a lightweight student model with multi-round teacher feedback, hybrid evaluation, and a simple semantic memory can:

* raise EM from ≈ 0.05–0.07 to up to 0.66 (Alpaca) and 0.37 (Medical),
* increase semantic similarity to ≈ 0.93–0.96,
* achieve high LLM-judge scores (≈ 0.94–0.97),

at the cost of 40–70× more tokens per question.

The findings support the following conclusions:

* **RQ1.** Multi-round teacher feedback is highly effective for improving small-model answers.
* **RQ2.** Hybrid metrics combining deterministic scores and LLM judges work well in practice and strongly influence loop behaviour.
* **RQ3.** A simple FAISS memory offers small but measurable gains in some settings, but is not the main driver of performance.
* **RQ4.** The method is computationally expensive; however, it provides a transparent, measurable cost–quality trade-off.

Overall, the study offers a concrete blueprint for future research on cost-efficient feedback strategies, richer memory designs, adaptive stopping rules, and generalisation of teaching loops beyond Alpaca-style and medical question answering.
