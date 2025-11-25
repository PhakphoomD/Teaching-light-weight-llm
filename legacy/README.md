# Teaching-light-weight-llm

## Set up guide
This repository separates **machine/runtime-specific** packages (installed with **Conda**) from **cross-platform Python libraries** (installed with **pip**).  
Follow the steps for your platform.

### Windows (NVIDIA)
Verify NVIDIA driver:
   ```powershell```
   nvidia-smi
If you don't see your GPU/driver, install the official NVIDIA Driver first.

Create Conda env (GPU runtime):

    conda env create -f environment.yml
    conda activate tlw```
Install Python packages with pip:

    pip install --upgrade pip
    pip install -r requirements.txt
Sanity check:

    import torch
    print("CUDA available:", torch.cuda.is_available())
    print("Device:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU")

### MacOS (Apple Silicon: M1/M2/M3)
macOS uses MPS/Metal, not CUDA.
`` same as window without nvidia ``

    conda env create -f environment.yml
    conda activate tlw

    pip install --upgrade pip
    pip install torch torchvision torchaudio
    pip install -r requirements.txt

    
    import torch
    print("MPS available:", getattr(torch.backends, "mps", None) and torch.backends.m)
    is_available()
    print("CUDA available:", torch.cuda.is_available())
    


### Google Colab (pip-only)
    pip install --upgrade pip
    pip install torch torchvision torchaudio
    pip install -r requirements.txt

## Files in this repo

environment.yml — Conda environment for machine/runtime-specific packages (GPU/CUDA on Windows).

requirements.txt — pip requirements for cross-platform libs and LLM SDKs.

Optional: if you want to keep provider SDKs separate, create requirements-llm.txt with:
    openai>=1.40.0
    groq>=0.11.0
    google-generativeai>=0.7.2

## Set-up Troubleshooting
1. nvidia-smi not found / no GPU shown (Windows)
Install the official NVIDIA Driver (Studio/Game Ready), reboot, then re-run nvidia-smi.

2. Torch says CUDA available: False on Windows
Ensure you created/activated the Conda env from environment.yml (which installs pytorch-cuda).
Then reinstall pip packages: pip install -r requirements.txt.

3. FAISS GPU on Windows
Use CPU build (faiss-cpu) on Windows. If you need FAISS GPU, use Linux/WSL2.

4. macOS cannot use CUDA
Correct — use MPS (Metal) via pip install torch torchvision torchaudio.

After a successful setup:

    pip freeze > requirements-lock.txt
    conda env export > environment-lock.yml
this can help us to reproducibility next time.

---

## Critic & Feedback System

### Overview

The **Critic system** evaluates student answers and provides structured feedback for the refinement loop. We've upgraded from XML-based parsing to a robust **JSON schema** with hybrid evaluation.

### Architecture

**⭐ Primary Path: HybridCritic** (Recommended for all new code)
- Combines **rule-based** (fast, deterministic) + **LLM-based** (deep understanding)
- Returns **CriticFeedback** (standardized JSON schema)
- Weighted aggregation: `overall = w_rule × rule_score + w_llm × llm_score`
- Sigmoid calibration: `stop_score = sigmoid(a × overall + b)`
- Disagreement detection: Logs when `|rule - llm| > threshold`

**⚠️ Legacy Path: TeacherCritic** (Deprecated, backward compatibility only)
- XML-based parsing (fragile)
- Returns **CriticResult** (old schema)
- No rule-based fallback
- Keep for existing code, migrate to HybridCritic

### Schema Comparison

| **Old (CriticResult)** | **New (CriticFeedback)** |
|------------------------|--------------------------|
| `evaluation` (str: "correct"/"incorrect") | `stop_score` (float: 0.0-1.0) |
| `reasoning` (str) | `issues` (List[str]) |
| `hint` (str) | `lesson` (str) + `fixes` (List[str]) |
| XML parsing | JSON parsing |
| Binary only | Gradual scoring |

### Usage

#### ✅ Recommended (HybridCritic)

```python
from src.critic import HybridCritic

# Automatic config loading from config.yaml
critic = HybridCritic()

# Evaluate answer
feedback = critic.evaluate(
    question="What is the capital of France?",
    answer="Paris is the capital",
    ground_truth="Paris"
)

# Access results
print(f"Stop score: {feedback.stop_score}")  # 0.0-1.0 (calibrated)
print(f"Overall: {feedback.scores['overall']}")
print(f"Rule: {feedback.scores['rule']}")
print(f"LLM: {feedback.scores['llm']}")
print(f"Issues: {feedback.issues}")
print(f"Lesson: {feedback.lesson}")
```

#### ⚠️ Legacy (TeacherCritic)

```python
from src.critic.model import TeacherCritic

critic = TeacherCritic()
result = critic.evaluate(
    question="What is 2+2?",
    student_answer="4"
)

print(result.evaluation)  # "correct" or "incorrect"
print(result.reasoning)
print(result.hint)
```

### Configuration

All critic parameters are in `config/config.yaml`:

```yaml
critic:
  type: hybrid                    # hybrid | rule | llm
  rule_weight: 0.5               # weight for rule-based score
  llm_weight: 0.5                # weight for LLM score
  stop_calibration:
    a: 1.0                       # sigmoid steepness
    b: 0.0                       # sigmoid bias
  disagreement_delta: 0.3        # log when |rule-llm| > this
  disagreements_file: disagreements.jsonl
  evaluation_thresholds:
    correct: 0.8               # stop_score ≥ 0.8 → "correct"
    partially_correct: 0.4     # stop_score ≥ 0.4 → "partially_correct"
```

### Migration Guide

**Step 1: Update imports**
```python
# Old
from src.critic.model import TeacherCritic

# New
from src.critic import HybridCritic
```

**Step 2: Update initialization**
```python
# Old
critic = TeacherCritic(provider="gemini", model_name="gemini-2.0-flash-lite")

# New (uses config.yaml automatically)
critic = HybridCritic()
```

**Step 3: Update evaluate() calls**
```python
# Old
result = critic.evaluate(question, student_answer, correct_answer="")

# New
feedback = critic.evaluate(question, answer, ground_truth=None)
```

**Step 4: Update result handling**
```python
# Old
if result.evaluation == "correct":
    stop = True

# New
if feedback.stop_score >= 0.8:  # or use config threshold
    stop = True
```

### Testing

Run critic tests (no API calls, all mocked):

```bash
# Schema validation tests (13 tests)
pytest src/tests/test_critic_schema.py -v

# Hybrid critic tests (15 tests)
pytest src/tests/test_critic_hybrid.py -v

# All critic tests
pytest src/tests/test_critic*.py -v
```

### Disagreement Logging

When rule and LLM scores disagree significantly, the system logs to `disagreements.jsonl`:

```json
{
  "timestamp": "2025-11-10T20:54:03",
  "question": "What is 2+2?",
  "answer": "5",
  "rule_score": 0.2,
  "llm_score": 0.8,
  "disagreement": 0.6,
  "threshold": 0.3
}
```

Use this to:
- Debug evaluation inconsistencies
- Tune rule checker weights
- Identify edge cases
- Improve calibration

### Key Benefits

✅ **Robust**: JSON parsing handles LLM output variations  
✅ **Fast**: Rule checkers provide instant feedback  
✅ **Smart**: LLM catches nuanced errors  
✅ **Calibrated**: Sigmoid maps scores to stopping criterion  
✅ **Observable**: Disagreement logging for debugging  
✅ **Configurable**: All weights/thresholds in config.yaml  
✅ **Tested**: 28 unit tests, 100% mocked (no API costs)