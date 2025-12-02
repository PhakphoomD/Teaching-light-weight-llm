# Teaching Loop for Lightweight LLMs

An iterative teaching system that improves accuracy of small, budget-friendly language models (Llama 3.1 8B) through structured feedback and memory-based learning. Achieves **83% pass rate** on medical Q&A (up from 25% baseline) without fine-tuning.

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

Small language models (8B parameters) are cost-efficient but often produce inaccurate answers on domain-specific tasks. Traditional solutions require expensive fine-tuning or using larger models.

### Our Solution

An **iterative teaching loop** that:

1. Uses a larger teacher model (70B) to provide structured feedback
2. Stores successful teaching episodes in semantic memory (FAISS)
3. Retrieves relevant examples to guide future answers
4. Achieves high accuracy without modifying model weights

### Core Philosophy

- **Minimal Prompts**: Small models perform best with focused, concise instructions
- **Hybrid Evaluation**: Combines deterministic metrics with LLM-based judges
- **Smart Memory**: FAISS-based retrieval with success-rate ranking
- **Deterministic Student**: Temperature = 0.0 is critical for memory effectiveness
- **ORCA Feedback**: Critique-based feedback outperforms Chain-of-Thought

---

## Key Results

| Configuration            | Pass Rate | Improvement | Cost per 100Q |
|--------------------------|-----------|-------------|---------------|
| Baseline (no teaching)   | 25%       | -           | $0.10 AUD     |
| Optimized Teaching Loop  | 83%       | +58%        | $0.23 AUD     |
| Ground Truth Memory      | 100%      | +75%        | $0.04 AUD     |

### Research Questions Answered

| RQ  | Question                                          | Finding                                    |
|-----|---------------------------------------------------|--------------------------------------------|
| RQ1 | Does teaching loop improve accuracy?              | Yes, +58% pass rate (25% to 83%)           |
| RQ2 | What feedback style works best?                   | ORCA (critique-based) > CoT > Principle    |
| RQ3 | Does memory help?                                 | Yes, when Student Temperature = 0.0        |
| RQ4 | What is the cost-quality trade-off?               | 4x tokens for 3x accuracy improvement      |

---

## System Architecture

### High-Level Flow

```
+-----------------------------------------------------------------------------------+
|                        Teaching Loop System Architecture                          |
+-----------------------------------------------------------------------------------+

                              +-------------------+
                              |   Input Question  |
                              |   + Ground Truth  |
                              +---------+---------+
                                        |
                                        v
                              +-------------------+
                              |  Initialize Loop  |
                              |  round = 1        |
                              +---------+---------+
                                        |
                                        v
                         +-----------------------------+
                         |   Memory Search (Round 1)   |
                         |   FAISS semantic retrieval  |
                         +-------------+---------------+
                                       |
                    +------------------+------------------+
                    |                                     |
                    v                                     v
          +------------------+                  +------------------+
          | Memory Hit Found |                  |   No Memory Hit  |
          | (similarity > T) |                  |                  |
          +--------+---------+                  +--------+---------+
                   |                                     |
                   v                                     v
     +------------------------+             +------------------------+
     | Build Prompt with      |             | Build First-Attempt    |
     | Retrieved Feedback     |             | Minimal Prompt         |
     +------------------------+             +------------------------+
                   |                                     |
                   +------------------+------------------+
                                      |
                                      v
                         +------------------------+
                         |    Student Model       |
                         |    Generate Answer     |
                         |    (Llama 3.1 8B)      |
                         +-----------+------------+
                                     |
                                     v
                         +------------------------+
                         |   Hybrid Evaluation    |
                         | - Semantic Similarity  |
                         | - ROUGE-L Score        |
                         | - Blind Judge (LLM)    |
                         | - Comparison Judge     |
                         +-----------+------------+
                                     |
                                     v
                         +------------------------+
                         |  Compute Final Score   |
                         |  (Weighted Average)    |
                         +-----------+------------+
                                     |
                    +----------------+----------------+
                    |                                 |
                    v                                 v
          +------------------+              +------------------+
          | Score >= 0.80    |              | Score < 0.80     |
          | (Pass Threshold) |              | (Needs Improve)  |
          +--------+---------+              +--------+---------+
                   |                                 |
                   v                                 v
          +------------------+              +------------------+
          |     SUCCESS      |              | Check Stopping   |
          | - Update Memory  |              | - Max rounds?    |
          | - Return Result  |              | - Plateau?       |
          +------------------+              +--------+---------+
                                                     |
                                    +----------------+----------------+
                                    |                                 |
                                    v                                 v
                          +------------------+              +------------------+
                          |  Continue Loop   |              |   Stop (Fail)    |
                          +--------+---------+              +------------------+
                                   |
                                   v
                          +------------------+
                          |  Teacher Model   |
                          |  Generate ORCA   |
                          |  Feedback (70B)  |
                          +--------+---------+
                                   |
                                   v
                          +------------------+
                          | Build Refinement |
                          | Prompt + Feedback|
                          +--------+---------+
                                   |
                                   +-------> (Loop back to Student Model)
```

### Key Components

| Component              | File                                 | Responsibility                           |
|------------------------|--------------------------------------|------------------------------------------|
| Teaching Loop          | `simplified_teaching_loop.py`        | Main orchestrator, iteration control     |
| Experiment Runner      | `simplified_experiment_runner.py`    | Batch execution, result aggregation      |
| Student Client         | `src/simplified/student.py`          | Prompt building, student LLM calls       |
| Teacher Feedback       | `src/simplified/teacher_feedback.py` | ORCA/CoT feedback generation             |
| Metrics Evaluator      | `src/simplified/metrics.py`          | Hybrid scoring system                    |
| Memory System          | `src/simplified/memory.py`           | FAISS indexing and retrieval             |
| Early Stopping         | `src/simplified/early_stopping.py`   | Plateau/repetition detection             |
| LLM Providers          | `src/providers/*.py`                 | Groq, Gemini, OpenAI, Local              |

---

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

### Main Configuration File

`config/simplified_config.yml`

```yaml
# Student Model Configuration
student:
  model: "llama-3.1-8b-instant"
  provider: "groq"
  temperature: 0.0          # CRITICAL: Must be 0.0 for memory effectiveness
  max_tokens: 256
  timeout: 30

# Teacher Model Configuration
teacher:
  model: "llama-3.3-70b-versatile"
  provider: "groq"
  temperature: 0.3          # Allows creative feedback generation
  max_tokens: 256
  pass_threshold: 0.80      # Optimal balance of quality and convergence
  feedback_style: "orca"    # Best performing style

  # Hybrid Scoring Weights
  metrics:
    weights:
      blind_score: 0.25       # LLM judge without ground truth
      comparison_score: 0.35  # LLM judge with ground truth
      semantic_sim: 0.25      # Embedding similarity
      rouge_l: 0.10           # ROUGE-L score
      exact_match: 0.05       # Perfect match bonus

# Memory Configuration
memory:
  embedding_model: "all-MiniLM-L6-v2"
  top_k: 5
  similarity_threshold: 0.7
  min_success_rate: 0.5
  storage_path: "logs/memory/store.jsonl"
  index_path: "logs/memory/faiss.index"

# Loop Configuration
loop:
  max_rounds: 5
  early_stopping:
    enabled: true
    patience: 2
    min_improvement: 0.05
    start_from_round: 2
```

### Optimal Hyperparameters (Discovered via Experiments)

| Parameter             | Value | Rationale                                    |
|-----------------------|-------|----------------------------------------------|
| Student Temperature   | 0.0   | Enables memory effectiveness (95% hit rate)  |
| Pass Threshold        | 0.80  | Balances quality and convergence             |
| Teacher Temperature   | 0.3   | Creative but focused feedback                |
| Feedback Style        | ORCA  | +10% pass rate vs Chain-of-Thought           |
| Max Rounds            | 5     | Sufficient for most questions                |

---

## Usage

### Quick Start

```bash
# Run with 10 questions (quick test)
python simplified_experiment_runner.py --questions 10

# Run with 100 questions (full validation)
python simplified_experiment_runner.py --questions 100

# Run with custom config
python simplified_experiment_runner.py --config config/my_config.yml --questions 50
```

### Python API

```python
from simplified_teaching_loop import SimplifiedTeachingLoop

# Initialize the teaching loop
loop = SimplifiedTeachingLoop(config_path="config/simplified_config.yml")

# Run on a single question
result = loop.run(
    question="What is the treatment for Type 2 diabetes?",
    ground_truth="Lifestyle changes, metformin, and monitoring blood glucose.",
    max_rounds=5
)

# Check results
print(f"Success: {result['success']}")
print(f"Final Answer: {result['final_answer']}")
print(f"Rounds Used: {result['num_rounds']}")
print(f"Final Score: {result['final_score']:.3f}")

# Access round-by-round history
for round_data in result['history']:
    print(f"Round {round_data['round']}: Score {round_data['final_score']:.3f}")
```

### Batch Processing

```python
from simplified_experiment_runner import run_experiment

# Run batch experiment
results = run_experiment(
    config_path="config/simplified_config.yml",
    dataset_path="data/medical_100.jsonl",
    num_questions=50,
    mode="champion_mem_on"
)

# Aggregate metrics
print(f"Pass Rate: {results['pass_rate']:.1%}")
print(f"Average Rounds: {results['avg_rounds']:.2f}")
print(f"Memory Hit Rate: {results['memory_hit_rate']:.1%}")
```

### Command-Line Options

```bash
python simplified_experiment_runner.py [OPTIONS]

Options:
  --config PATH       Path to config file (default: config/simplified_config.yml)
  --questions N       Number of questions to test (default: 10)
  --mode MODE         Experiment mode: baseline, champion_mem_on, champion_mem_off
  --dataset PATH      Path to dataset file (JSONL format)
  --help              Show help message
```

### Example Output

```
================================================================================
Simplified Teaching Loop
================================================================================
Dataset: data/medical_100.jsonl (10 questions)
Student Model:  groq/llama-3.1-8b-instant
Teacher Model:  groq/llama-3.3-70b-versatile
Pass Threshold: 0.80
Max Rounds: 5
================================================================================

Processing: [====================] 10/10 (100%)

Question 1/10 | Result: [PASS] | Score: 0.92 | Rounds: 2 | Memory: HIT

  Question:     What is the treatment for Type 2 diabetes?
  Ground Truth: Lifestyle changes, metformin, and monitoring blood glucose.

  Round | Mode   | Answer                           | Score | Status
  ------|--------|----------------------------------|-------|--------
  1     | MEMORY | Lifestyle changes and metformin  | 0.78  | FAIL
  2     | REFINE | Lifestyle changes, metformin...  | 0.92  | PASS

================================================================================
FINAL SUMMARY
================================================================================
Success Rate:     90.0% (9/10)
Average Rounds:   2.30
Memory Hit Rate:  40.0%
Total Time:       45.2s

Average Metrics:
  Semantic Similarity:  0.891
  ROUGE-L:              0.823
  Blind Judge:          0.812
  Comparison Judge:     0.845
  Final Score:          0.834
================================================================================
```

---

## Project Structure

```
Teaching-light-weight-llm/
|
|-- README.md                           # This file
|-- requirements.txt                    # Python dependencies
|-- environment.yml                     # Conda environment
|-- .env.example                        # API key template
|
|-- simplified_teaching_loop.py         # Main orchestrator
|-- simplified_experiment_runner.py     # Batch experiment runner
|
|-- config/
|   |-- simplified_config.yml           # Main system configuration
|   |-- prompts_config.yml              # Centralized prompt templates
|   +-- experiments/                    # Phase-specific configs
|
|-- src/
|   |-- simplified/                     # Core teaching loop components
|   |   |-- student.py                  # Student model client
|   |   |-- teacher_feedback.py         # Teacher feedback generation
|   |   |-- metrics.py                  # Hybrid evaluation system
|   |   |-- memory.py                   # FAISS memory system
|   |   |-- early_stopping.py           # Convergence detection
|   |   |-- logger.py                   # Round-by-round logging
|   |   |-- logger_manager.py           # Log file management
|   |   |-- console_logger.py           # Console output formatting
|   |   |-- debug_logger.py             # Debug logging utilities
|   |   |-- terminal_ui.py              # Terminal UI display
|   |   +-- monitor.py                  # Performance tracking
|   |
|   |-- providers/                      # LLM API clients
|   |   |-- factory.py                  # Provider registry
|   |   |-- groq_client.py              # Groq API
|   |   |-- gemini_client.py            # Google Gemini API
|   |   +-- local_client.py             # Local HuggingFace inference
|   |
|   |-- core/                           # Core infrastructure
|   |   |-- client.py                   # LLMClient base class
|   |   |-- types.py                    # Type definitions
|   |   +-- tokens.py                   # Token estimation
|   |
|   +-- utils/
|       +-- prompt_loader.py            # Prompt template management
|
|-- data/
|   |-- medical_mixed_100.jsonl         # Main medical dataset
|   |-- alpaca_100.jsonl                # General instruction dataset
|   +-- medical_by_source/              # Domain-specific datasets
|
|-- models/                              # Local models (not tracked in git)
|   +-- Llama-3.1-8B-Instruct/          # Download separately if needed
|
|-- notebooks/
|   +-- experiment_redesigned.ipynb     # Analysis and visualization
|
|-- logs/
|   |-- experiments/                    # Phase results
|   +-- simplified/                     # Run logs (debug/ excluded from git)
|
+-- docs/
    +-- PROJECT_OVERVIEW_AND_RESULTS.md # Detailed experimental analysis
```

---

## Experimental Phases

| Phase | Purpose                    | Key Finding                                    |
|-------|----------------------------|------------------------------------------------|
| 0     | Warmup Memory Pool         | Created 13 teaching episodes for memory        |
| 1     | Memory vs No Memory        | +5% with memory (not yet optimized)            |
| 2     | Feedback Style             | ORCA > CoT > Principle                         |
| 3     | Hyperparameter Tuning      | ST=0.0 is critical for memory effectiveness    |
| 4     | Cross-Domain               | Domain-specific memory works best              |
| 5     | Full Validation (100Q)     | 25% to 83% improvement                         |
| 6     | Ground Truth Memory        | 100% with pre-stored answers ("Training via Memory") |

See [PROJECT_OVERVIEW_AND_RESULTS.md](docs/PROJECT_OVERVIEW_AND_RESULTS.md) for detailed analysis.

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

### Projection: 1,000 Questions

| Configuration  | Pass Rate | Passed/1000 | Est. Cost (AUD) |
|----------------|-----------|-------------|-----------------|
| Baseline       | 66%       | 660         | $1.48           |
| Optimized      | 83%       | 830         | $2.29           |
| GT Memory      | 100%      | 1000        | $0.38           |

---

## Troubleshooting

### API Rate Limits

**Problem:** `429 Too Many Requests`

**Solution:**
```bash
# Reduce batch size
python simplified_experiment_runner.py --questions 5

# Or switch to local model
# Edit config/simplified_config.yml:
# student:
#   provider: "local"
```

### Poor Performance

**Problem:** Low pass rate or too many rounds

**Check these settings:**
```yaml
student:
  temperature: 0.0  # Must be 0.0, NOT 0.3 or higher

teacher:
  pass_threshold: 0.80  # Not too high (0.85) or low (0.75)
```

### Memory Not Working

**Problem:** Memory hit rate is 0%

**Solution:**
```bash
# Reset memory index
rm logs/memory/faiss.index logs/memory/faiss.ids

# Verify student temperature is 0.0
grep "temperature" config/simplified_config.yml
```

### Out of Memory

**Problem:** CUDA out of memory

**Solution:**
```bash
# Use API-based models instead of local
# Edit config to use provider: "groq"
```

---

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
