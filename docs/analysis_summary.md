# Analysis Summary Guide

This guide explains how to analyze and summarize experiment results.

## Overview

The system provides several tools for analyzing experiment results:
1. Built-in analysis modules in `src/analysis/`
2. Analysis report generator (see [Visualization Guide](visualization.md))
3. Manual inspection of result files

## Result Directory Structure

```
results/
├── <model_name>/              # e.g., tinyllama_1.1b
│   ├── <strategy>/            # e.g., baseline, multikey_tfidf
│   │   └── run_YYYYMMDD_HHMMSS/
│   │       ├── config.json           # Experiment configuration
│   │       ├── summary.json          # Aggregate metrics
│   │       ├── results.jsonl         # Per-task results
│   │       └── memory_store.jsonl    # Memory data (if applicable)
└── tokens/                    # Token usage tracking
```

## Using Built-in Analysis Tools

### Compare Strategies for a Model
```bash
python -m src.analysis.compare_experiments --model tinyllama_1.1b
```

This will:
- List all strategies tested with the specified model
- Show comparative metrics
- Highlight best-performing strategies

### Compare Across Models
```bash
python -m src.analysis.compare_models --strategy multikey_tfidf
```

This will:
- Compare different models using the same strategy
- Show which model performs best
- Identify scaling patterns

### Visualize Results
```bash
python -m src.analysis.visualize --results-dir results/
```

This generates:
- Comparison charts
- Performance trends
- Statistical summaries

## Understanding Result Files

### config.json
Contains experiment configuration:
```json
{
  "student_model": "tinyllama_1.1b",
  "teacher_model": "gemini-1.5-flash",
  "strategies": ["multikey_tfidf"],
  "dataset": "alpaca_100",
  "max_iterations": 3,
  "timestamp": "20251028_200210"
}
```

### summary.json
Contains aggregate metrics:
```json
{
  "total_tasks": 100,
  "successful_tasks": 85,
  "failed_tasks": 15,
  "success_rate": 0.85,
  "avg_iterations": 2.3,
  "avg_score": 0.782,
  "total_time": 1234.56
}
```

### results.jsonl
One JSON object per line, each containing:
- `task_id`: Task identifier
- `question`: Input question
- `success`: Boolean success status
- `num_iterations`: Number of iterations used
- `final_score`: Quality score
- `responses`: All generated responses
- `feedback`: Teacher feedback for each iteration

### memory_store.jsonl
For memory-enabled strategies:
- `key`: Memory lookup key
- `question`: Original question
- `feedback`: Stored lesson
- `timestamp`: When stored
- `metadata`: Additional information

## Key Metrics Explained

### Success Rate
- **Definition**: Percentage of tasks completed successfully
- **Calculation**: `successful_tasks / total_tasks`
- **Target**: Higher is better (>80% is good)

### Average Iterations
- **Definition**: Average number of teaching iterations per task
- **Calculation**: Sum of all iterations / total tasks
- **Target**: Lower is better (indicates efficient learning)

### Average Score
- **Definition**: Mean quality score across all successful tasks
- **Calculation**: Sum of final scores / successful tasks
- **Range**: 0.0 to 1.0
- **Target**: Higher is better (>0.7 is good)

### Token Usage
- Tracked separately in `results/tokens/`
- Shows API call costs
- Helps optimize for efficiency

## Comparing Experiments

### Manual Comparison
1. Navigate to experiment folders
2. Compare `summary.json` files
3. Look for patterns in success rates and iterations

### Automated Comparison
Use the analysis report generator:
```bash
python create_analysis_report.py
```
Select multiple experiments to generate comparative analysis.

## Statistical Analysis

### Confidence Intervals
For robust conclusions, consider:
- Running multiple trials
- Calculating standard deviations
- Testing statistical significance

### Sample Size
- Minimum 20 tasks for preliminary results
- 100+ tasks for reliable metrics
- 500+ tasks for publication-quality data

## Common Analysis Tasks

### Find Best Strategy
```bash
# Generate report with all strategies for a model
python create_analysis_report.py
# Select all runs for the model
# Compare success rates in summary_table.csv
```

### Track Improvement Over Time
```bash
# Select runs ordered by timestamp
# Look for trends in metrics
# Identify successful modifications
```

### Identify Failure Patterns
```bash
# Open results.jsonl for failed runs
# Filter for success: false
# Analyze common characteristics of failures
```

### Analyze Memory Effectiveness
```bash
# Compare memory vs non-memory strategies
# Check memory_store.jsonl for stored lessons
# Verify lessons are being retrieved and used
```

## Exporting Results

### To Excel/CSV
All analysis reports include CSV exports:
- Open in Excel or Google Sheets
- Sort and filter data
- Create custom visualizations

### To Research Paper
1. Use generated graphs (PNG, 300 DPI)
2. Extract key metrics from summary tables
3. Quote from detailed reports for examples

### To Presentation
1. Copy graphs directly
2. Use summary statistics
3. Highlight success stories from detailed reports

## Advanced Analysis

### Custom Analysis Scripts
Create your own analysis tools:

```python
import json
from pathlib import Path

def analyze_experiment(run_dir):
    # Load data
    with open(run_dir / "summary.json") as f:
        summary = json.load(f)
    
    # Perform custom analysis
    # ...
    
    return results
```

### Database Export
Convert JSONL to database:

```python
import jsonlines
import sqlite3

# Read results
with jsonlines.open('results.jsonl') as reader:
    results = list(reader)

# Store in database
conn = sqlite3.connect('experiments.db')
# ... insert data
```

### Statistical Testing
Use scipy/pandas for statistical analysis:

```python
import pandas as pd
from scipy import stats

# Load multiple experiments
df1 = pd.read_csv('exp1/summary_table.csv')
df2 = pd.read_csv('exp2/summary_table.csv')

# Perform t-test
t_stat, p_value = stats.ttest_ind(df1['Avg Score'], df2['Avg Score'])
```

## Troubleshooting

### Missing Summary Files
- Ensure experiment completed successfully
- Check for errors in experiment log
- Re-run experiment if needed

### Inconsistent Metrics
- Verify same dataset used
- Check for different configurations
- Ensure fair comparison (same parameters)

### Empty Results
- Check for API failures
- Verify connectivity
- Review error logs

## Best Practices

1. **Consistent Naming**: Use clear strategy names
2. **Document Changes**: Note configuration changes
3. **Regular Backups**: Save important results
4. **Incremental Testing**: Test on small datasets first
5. **Version Control**: Track code changes with results

## See Also
- [Visualization Guide](visualization.md)
- [Running Experiments](execution.md)
- [Configuration Guide](configuration.md)
