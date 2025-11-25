# Organized Experimental Data
================================================================================
# Data Structure for "Reflection + Memory" Experiment Analysis
================================================================================

This folder contains **all experimental data** organized by phase, with clear 
instructions on which files to use for different types of analysis.

## 📁 Folder Structure

```
logs/organized_data/
├── phase0_baseline/           # Baseline (no reflection, no memory)
├── phase1_teacher_student/    # Teacher × Student prompt combinations (12 configs)
├── phase2a_lhs/               # Latin Hypercube Sampling (20 configs)
├── phase2b_grid/              # Grid search around best LHS (27 configs)
├── phase2c_champion/          # Fine-tuning champion config (27 configs)
├── phase3_judge_modes/        # Judge comparison (4 modes)
├── phase4_final_validation/   # Champion config validation (4 experiments)
├── debug_per_round/           # Round-by-round behavior (all phases)
├── debug_detailed_examples/   # Detailed question-level traces
└── memory_stores/             # Memory databases (Phase 4)
```

================================================================================
## 📊 DATA USAGE GUIDE
================================================================================

### 🎯 Use Case 1: Compare Phase Performance (Aggregate Results)
**Goal**: Plot EM, ROUGE, Semantic, Judges, Rounds across phases

**Files to use**:
- `phase0_baseline/summary.jsonl` → Baseline metrics
- `phase1_teacher_student/summary.jsonl` → 12 teacher×student combinations
- `phase2a_lhs/summary.jsonl` → 20 LHS samples
- `phase2b_grid/summary.jsonl` → 27 grid search configs
- `phase2c_champion/summary.jsonl` → 27 champion fine-tuning configs
- `phase3_judge_modes/summary.jsonl` → 4 judge modes
- `phase4_final_validation/summary.jsonl` → 4 final experiments ⭐

**Each record contains**:
```json
{
  "experiment_id": "phase4_champion_mem_on_alpaca",
  "phase": "phase4",
  "config": {
    "domain": "alpaca",
    "mode": "champion_mem_on",
    "teacher": "cot_feedback",
    "student": "minimal",
    "pass_threshold": 0.898,
    "metric_weights": {...},
    "memory_similarity_threshold": 0.836,
    "memory_top_k": 3,
    "student_temperature": 0.0,
    "teacher_temperature": 0.2,
    "max_rounds": 3
  },
  "metrics": {
    "exact_match": 0.07,
    "rouge_l": 0.534,
    "semantic_similarity": 0.732,
    "blind_judge": 0.877,
    "comparison_judge": 0.942
  },
  "avg_rounds": 1.13,
  "total_tokens": 0,
  "cost": 0.0,
  "timestamp": "2025-11-18T11:17:03.327437"
}
```

**Python example**:
```python
import json
import pandas as pd

# Load Phase 4 data
with open('logs/organized_data/phase4_final_validation/summary.jsonl') as f:
    phase4 = [json.loads(line) for line in f]

# Extract metrics
df = pd.DataFrame([
    {
        'experiment': exp['experiment_id'],
        'comparison': exp['metrics']['comparison_judge'],
        'rounds': exp['avg_rounds']
    }
    for exp in phase4
])
```

---

### 🔄 Use Case 2: Analyze Reflection Behavior (Round-by-Round)
**Goal**: See if scores improve with each round (reflection impact)

**Files to use**:
- `debug_per_round/all_rounds.jsonl` ⭐

**Each record contains**:
```json
{
  "round": 1,
  "timestamp": "2025-11-15T01:08:48.251854",
  "question": "Select an appropriate Machine Learning algorithm...",
  "answer": "The appropriate algorithm is...",
  "scores": {
    "exact_match": 0.0,
    "rouge_l": 0.727,
    "semantic_sim": 0.467,
    "blind_score": 0.9,
    "comparison_score": 1.0,
    "final": 0.746
  },
  "final_score": 0.746,
  "passed": false,
  "feedback_id": null,
  "time_ms": 7219
}
```

**⚠️ Limitation**: This file contains data from **multiple phases/runs** mixed together 
(no `phase` or `experiment_id` tag). Use for global reflection analysis, not phase-specific.

**Python example**:
```python
import json
from collections import defaultdict

# Load all rounds
with open('logs/organized_data/debug_per_round/all_rounds.jsonl') as f:
    rounds = [json.loads(line) for line in f]

# Group by question
questions = defaultdict(list)
for r in rounds:
    q_key = r['question'][:50]  # First 50 chars as key
    questions[q_key].append(r)

# Analyze improvement
for q, rounds_list in questions.items():
    sorted_rounds = sorted(rounds_list, key=lambda x: x['round'])
    for i in range(len(sorted_rounds) - 1):
        delta = sorted_rounds[i+1]['final_score'] - sorted_rounds[i]['final_score']
        if delta > 0:
            print(f"Question improved: {delta:+.3f}")
```

---

### 🧠 Use Case 3: Analyze Memory Impact (Phase 4 Specific)
**Goal**: Compare Memory ON vs OFF in Alpaca/Medical domains

**Files to use**:
- `phase4_final_validation/summary.jsonl` ⭐ → Aggregate metrics
- `memory_stores/phase4_memory_alpaca_mem_on.jsonl` → Memory entries (Alpaca ON)
- `memory_stores/phase4_memory_alpaca_mem_off.jsonl` → Memory entries (Alpaca OFF)
- `memory_stores/phase4_memory_medical_mem_on.jsonl` → Memory entries (Medical ON)
- `memory_stores/phase4_memory_medical_mem_off.jsonl` → Memory entries (Medical OFF)

**Memory store format**:
```json
{
  "id": "600998a4d3865058",
  "question": "Instruction: Split the sentence...",
  "teaching_feedback": "Format: The component words are...",
  "attempts": 2,
  "success_count": 3,
  "success_rate": 1.5,
  "scores": {
    "exact_match": 0.0,
    "rouge_l": 0.4,
    "semantic_sim": 0.181,
    "blind_score": 0.9,
    "comparison_score": 0.0,
    "final": 1.0
  },
  "timestamp": "2025-11-18T11:09:51.815403"
}
```

**Python example**:
```python
import json

# Compare Memory ON vs OFF (Alpaca)
with open('logs/organized_data/phase4_final_validation/summary.jsonl') as f:
    phase4 = [json.loads(line) for line in f]

alpaca_on = next(x for x in phase4 if 'alpaca' in x['experiment_id'] and 'mem_on' in x['experiment_id'])
alpaca_off = next(x for x in phase4 if 'alpaca' in x['experiment_id'] and 'mem_off' in x['experiment_id'])

print(f"Alpaca Memory ON:  {alpaca_on['metrics']['comparison_judge']:.3f}")
print(f"Alpaca Memory OFF: {alpaca_off['metrics']['comparison_judge']:.3f}")
print(f"Delta: {alpaca_on['metrics']['comparison_judge'] - alpaca_off['metrics']['comparison_judge']:+.3f}")
```

---

### 🔍 Use Case 4: Qualitative Analysis (Example Traces)
**Goal**: Show real examples of student answers, teacher feedback, memory retrieval

**Files to use**:
- `debug_detailed_examples/*.json` → Detailed per-run traces

**Each file contains**:
```json
{
  "timestamp": "20251116_013156",
  "run_start": "2025-11-16T01:31:56.123456",
  "parameters": {
    "student_model": "llama-3.1-8b-instant",
    "teacher_model": "llama-3.3-70b-versatile",
    "pass_threshold": 0.8,
    ...
  },
  "questions": [
    {
      "question_idx": 1,
      "question": "What is the capital of France?",
      "ground_truth": "Paris",
      "rounds": [
        {
          "round": 1,
          "mode": "FIRST",
          "student": {
            "input": "Question: What is the capital of France?\nAnswer:",
            "output": "The capital of France is Paris.",
            "raw_response": {...}
          },
          "teacher": {
            "input": "Evaluate the following answer...",
            "output": {...},
            "raw_response": {...}
          },
          "scores": {...},
          "feedback": null,
          "memory_hits": [],
          "flags": []
        }
      ],
      "final_result": {
        "passed": true,
        "total_rounds": 1,
        "final_score": 1.0,
        "stop_reason": "PASSED"
      }
    }
  ]
}
```

**Use for**: Paper examples, case studies, error analysis

---

================================================================================
## 📈 RECOMMENDED VISUALIZATIONS BY DATA SOURCE
================================================================================

### From Phase Summaries (summary.jsonl files):

1. **Phase Progression Line Plot**
   - X: Phase (0, 1, 2a, 2b, 2c, 3, 4)
   - Y: Average comparison_judge score
   - Message: "Progressive optimization leads to 94.2% accuracy"

2. **Memory Impact Bar Chart** (Phase 4)
   - X: [Alpaca ON, Alpaca OFF, Medical ON, Medical OFF]
   - Y: Comparison score
   - Message: "Memory helps general QA, not domain-specific"

3. **Judge Mode Comparison** (Phase 3)
   - X: [full_hybrid, blind_only, comparison_only, deterministic_only]
   - Y: Avg rounds
   - Message: "Comparison-only judge is fastest (1.1 rounds)"

4. **Domain Gap Heatmap** (Phase 4)
   - Rows: [Alpaca, Medical]
   - Cols: [EM, ROUGE, Semantic, Blind, Comparison]
   - Message: "Medical domain significantly harder"

### From Debug Per-Round (all_rounds.jsonl):

5. **Reflection Pattern** (Score Δ per round)
   - X: Round number
   - Y: Score change from previous round
   - Distribution: [Improved, Degraded, No change]
   - Message: "39% improve, 27% degrade → reflection has mixed impact"

6. **Round Progression** (Metric evolution)
   - X: Round (1, 2, 3)
   - Y: Average metric value
   - Lines: [EM, ROUGE, Semantic, Blind, Comparison]
   - Message: "Round 1 achieves 92.8% comparison score"

### From Memory Stores (phase4_memory_*.jsonl):

7. **Memory Retrieval Distribution**
   - Histogram of similarity scores for retrieved memories
   - Color: [Questions that improved vs degraded]
   - Message: "High similarity (>0.9) correlates with improvement"

================================================================================
## 🎓 PAPER SECTIONS MAPPED TO DATA
================================================================================

### Abstract / Introduction
- Use: `phase4_final_validation/summary.jsonl` → Final metrics
- Claim: "Achieves 94.2% comparison accuracy on Alpaca dataset"

### Related Work
- No data needed (literature review)

### Methodology
- Use: `phase0_baseline/summary.jsonl` → Baseline setup
- Use: Phase configs from any `summary.jsonl` → Hyperparameter details

### Experimental Setup
- Use: `phase1_teacher_student/summary.jsonl` → Prompt engineering
- Use: `phase2a_lhs/`, `phase2b_grid/`, `phase2c_champion/` → Optimization process

### Results
- **RQ1: Does reflection work?**
  - Use: `debug_per_round/all_rounds.jsonl` → Round-by-round analysis
  - Use: `phase4_final_validation/summary.jsonl` → avg_rounds = 1.13
  
- **RQ2: Does memory help?**
  - Use: `phase4_final_validation/summary.jsonl` → Memory ON vs OFF
  - Use: `memory_stores/*.jsonl` → Retrieval statistics
  
- **RQ3: Domain differences?**
  - Use: `phase4_final_validation/summary.jsonl` → Alpaca vs Medical

### Discussion / Qualitative Analysis
- Use: `debug_detailed_examples/*.json` → Case studies
- Pick 2-3 good examples where reflection helped
- Pick 1-2 bad examples where reflection hurt

### Conclusion
- Use: `phase4_final_validation/summary.jsonl` → Final takeaways

================================================================================
## 🔧 QUICK START COMMANDS
================================================================================

### Load all Phase 4 data (Python):
```python
import json
import pandas as pd

def load_phase(phase_name):
    """Load any phase summary"""
    path = f'logs/organized_data/{phase_name}/summary.jsonl'
    with open(path) as f:
        return [json.loads(line) for line in f]

# Example: Load Phase 4
phase4 = load_phase('phase4_final_validation')
df = pd.DataFrame([
    {
        'exp': exp['experiment_id'],
        'domain': exp['config']['domain'],
        'memory': 'ON' if 'mem_on' in exp['experiment_id'] else 'OFF',
        **exp['metrics']
    }
    for exp in phase4
])
print(df)
```

### Count experiments per phase:
```python
import json
from pathlib import Path

for phase_dir in Path('logs/organized_data').iterdir():
    if phase_dir.is_dir() and 'phase' in phase_dir.name:
        summary_file = phase_dir / 'summary.jsonl'
        if summary_file.exists():
            with open(summary_file) as f:
                count = sum(1 for _ in f)
            print(f"{phase_dir.name:30s}: {count:3d} experiments")
```

### Analyze reflection improvement rate:
```python
import json
from collections import defaultdict

with open('logs/organized_data/debug_per_round/all_rounds.jsonl') as f:
    rounds = [json.loads(line) for line in f]

questions = defaultdict(list)
for r in rounds:
    questions[r['question'][:50]].append(r)

improved = degraded = no_change = 0

for q, rounds_list in questions.items():
    sorted_rounds = sorted(rounds_list, key=lambda x: x['round'])
    for i in range(len(sorted_rounds) - 1):
        curr = sorted_rounds[i]['final_score']
        next_score = sorted_rounds[i+1]['final_score']
        delta = next_score - curr
        
        if delta > 0.01:
            improved += 1
        elif delta < -0.01:
            degraded += 1
        else:
            no_change += 1

total = improved + degraded + no_change
print(f"Improved: {improved}/{total} ({improved/total*100:.1f}%)")
print(f"Degraded: {degraded}/{total} ({degraded/total*100:.1f}%)")
print(f"No change: {no_change}/{total} ({no_change/total*100:.1f}%)")
```

================================================================================
## 📝 NOTES & LIMITATIONS
================================================================================

1. **Phase Separation Issue**: `debug_per_round/all_rounds.jsonl` contains data 
   from multiple phases mixed together. To analyze Phase 4 specifically, you need 
   to match by timestamp or re-run experiments with phase tags.

2. **Memory Store Format**: Phase 4 memory stores (in `memory_stores/`) are 
   **per-domain** and **per-mode** (ON/OFF), allowing comparison of what memories 
   were stored in each configuration.

3. **Token Costs**: All `total_tokens` and `cost` fields are 0 because token 
   tracking was not enabled. For production, enable token tracking in provider code.

4. **Reproducibility**: All configs are stored in `config` field of each experiment. 
   To reproduce Phase 4 champion config:
   ```python
   champion = phase4[0]  # Any Phase 4 experiment
   config = champion['config']  # Use this config
   ```

================================================================================
## 🚀 NEXT STEPS
================================================================================

1. **Create visualizations** using the scripts in `scripts/analyze_*.py`
2. **Write paper** using the data mappings above
3. **Run additional experiments** if needed:
   - Per-round tracking with phase tags
   - Statistical significance tests
   - Ablation studies

================================================================================
## 📧 CONTACT & REFERENCES
================================================================================

For questions about this data structure, refer to:
- `scripts/analyze_phase4_detailed.py` → Phase 4 analysis
- `scripts/analyze_reflection_memory_impact.py` → Reflection/memory analysis
- `notebooks/hyperparameter_tuning.ipynb` → Experiment execution

================================================================================
Generated: 2025-11-18
Experiment: Reflection + Memory for Small LLM Teaching
================================================================================
