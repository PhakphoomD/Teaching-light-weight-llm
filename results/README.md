# Experiment Results

This directory contains all experiment results organized by:
- Student model
- Strategy
- Run timestamp

## Directory Structure

```
results/
├── tinyllama_1.1b/
│   ├── baseline/
│   │   └── run_YYYYMMDD_HHMMSS/
│   │       ├── config.json
│   │       ├── summary.json
│   │       ├── results.jsonl
│   │       └── memory_store.jsonl (if applicable)
│   ├── memory_multikey_tfidf/
│   └── ...
├── llama2_7b/
├── llama3_8b/
└── ...
```

## Files in Each Run

- **config.json**: Experiment configuration (strategy, models, parameters)
- **summary.json**: Aggregate metrics (success rate, avg iterations, etc.)
- **results.jsonl**: Detailed per-task results (JSONL format)
- **memory_store.jsonl**: Memory feedback storage (for memory-enabled strategies)

## Analyzing Results

Use the analysis tools in `src/analysis/`:
```bash
# Compare strategies for a model
python -m src.analysis.compare_experiments --model tinyllama_1.1b

# Compare across models
python -m src.analysis.compare_models --strategy memory_multikey_tfidf

# Visualize results
python -m src.analysis.visualize --results-dir results/
```
