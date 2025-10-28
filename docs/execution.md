# Execution Guide

This guide explains how to run experiments with the Teaching Lightweight LLM system.

## Prerequisites

### Required Setup
1. **Python Environment**: Python 3.8+
2. **Dependencies**: Install from requirements.txt
   ```bash
   pip install -r requirements.txt
   ```
3. **API Keys**: Set environment variables
   ```bash
   set GROQ_API_KEY=your_groq_api_key
   set GOOGLE_API_KEY=your_google_api_key
   ```

### Verify Installation
```bash
python run_experiment.py --help
```

## Running Experiments

### Interactive Mode (Recommended for Beginners)
```bash
python run_experiment.py
```

You will be prompted to select:
1. Student model
2. Teacher model
3. Teaching strategies
4. Dataset
5. Maximum iterations

### Command-Line Mode

#### Basic Experiment
```bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_20
```

#### Multiple Strategies
```bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline multikey_tfidf reflection --dataset alpaca_100
```

#### Custom Parameters
```bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100 --max-iters 5
```

## Available Options

### Student Models
- `tinyllama_1.1b` - Smallest, fastest model
- `llama2_7b` - Medium-sized model
- `llama3_8b` - Larger, more capable model

Model files should be in: `src/models/<model_name>/`

### Teacher Models
- `gemini-1.5-flash` - Fast Google Gemini model (recommended)
- `gemini-1.5-pro` - More capable Gemini model
- `mixtral-8x7b-32768` - Groq-hosted Mixtral
- `llama3-70b-8192` - Groq-hosted Llama 3

### Teaching Strategies
- `baseline` - No memory, direct prompting
- `reflection` - Self-reflection after each attempt
- `multikey` - Multi-key memory retrieval
- `tfidf` - TF-IDF based retrieval
- `multikey_tfidf` - Combined approach
- `canonical_similarity` - Canonical concept matching
- `memory_none` - Memory system without storage

Combine multiple strategies:
```bash
--strategies baseline multikey_tfidf canonical_similarity
```

### Datasets
- `alpaca_20` - 20 questions (quick test)
- `alpaca_100` - 100 questions (standard)
- `alpaca_questions` - Full dataset

Custom datasets should be in: `data/` folder in JSONL format

### Other Parameters
- `--max-iters N` - Maximum teaching iterations (default: 3)
- `--output-dir DIR` - Custom output directory (default: results/)
- `--verbose` - Show detailed progress
- `--quiet` - Minimal output

## Understanding Output

### During Execution
The system displays:
- Current task progress
- Success/failure for each task
- Iteration counts
- Real-time metrics

Example output:
```
Task 1/100: Success in 2 iterations
Task 2/100: Success in 1 iteration
Task 3/100: Failed after 3 iterations
...
```

### After Completion
Summary statistics are shown:
```
Experiment Complete
==================
Total Tasks: 100
Successful: 85
Failed: 15
Success Rate: 85.00%
Average Iterations: 2.3
Total Time: 1234.56s
```

Results are saved to:
```
results/<model>/<strategy>/run_YYYYMMDD_HHMMSS/
```

## Experiment Workflow

### 1. Quick Test
Start with a small dataset to verify setup:
```bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_20
```

### 2. Strategy Comparison
Test multiple strategies on the same data:
```bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline multikey_tfidf reflection canonical_similarity --dataset alpaca_100
```

### 3. Full Evaluation
Run with full dataset:
```bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_questions --max-iters 5
```

### 4. Model Comparison
Compare different student models:
```bash
# Run for each model
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100
python run_experiment.py --student llama2_7b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100
python run_experiment.py --student llama3_8b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100
```

## Advanced Usage

### Batch Experiments
Create a batch script:

**Windows (batch.bat):**
```batch
@echo off
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_100
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies reflection --dataset alpaca_100
```

**Linux/Mac (batch.sh):**
```bash
#!/bin/bash
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies baseline --dataset alpaca_100
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies multikey_tfidf --dataset alpaca_100
python run_experiment.py --student tinyllama_1.1b --teacher gemini-1.5-flash --strategies reflection --dataset alpaca_100
```

### Custom Datasets
Create your own dataset in JSONL format:

```jsonl
{"instruction": "Your question here", "output": "Expected answer"}
{"instruction": "Another question", "output": "Another answer"}
```

Save to `data/my_dataset.jsonl` and use:
```bash
python run_experiment.py --dataset my_dataset
```

### Resume Interrupted Experiments
If an experiment is interrupted:
1. Check the last completed task in output
2. The system automatically saves progress
3. Re-run with the same parameters to continue

## Performance Tips

### Speed Optimization
1. Use `tinyllama_1.1b` for faster experiments
2. Use `gemini-1.5-flash` for faster teacher responses
3. Start with smaller datasets (alpaca_20)
4. Reduce `--max-iters` for quicker tests

### Cost Optimization
1. Use smaller datasets for development
2. Choose efficient strategies (fewer API calls)
3. Monitor token usage in `results/tokens/`
4. Use local models when possible

### Quality Optimization
1. Increase `--max-iters` for better results
2. Use more capable teacher models
3. Combine multiple strategies
4. Use larger student models

## Monitoring Progress

### Real-time Monitoring
- Watch console output for task completion
- Check success/failure counts
- Monitor iteration usage

### Log Files
Logs are saved to:
```
results/<model>/<strategy>/run_YYYYMMDD_HHMMSS/experiment.log
```

### Token Tracking
Token usage is tracked in:
```
results/tokens/<timestamp>.json
```

## Troubleshooting

### API Key Errors
```
Error: GROQ_API_KEY not found
```
**Solution**: Set environment variable
```bash
set GROQ_API_KEY=your_key_here
```

### Model Not Found
```
Error: Model 'tinyllama_1.1b' not found
```
**Solution**: Check model files in `src/models/`

### Out of Memory
```
Error: CUDA out of memory
```
**Solution**: 
- Use smaller batch sizes
- Use smaller models
- Close other applications

### Rate Limiting
```
Error: Rate limit exceeded
```
**Solution**:
- Wait before retrying
- Use different API key
- Reduce concurrent requests

### Dataset Not Found
```
Error: Dataset 'alpaca_100' not found
```
**Solution**: Check file exists in `data/alpaca_100.jsonl`

## Best Practices

1. **Start Small**: Test with alpaca_20 before full runs
2. **Version Control**: Track your configuration changes
3. **Document**: Keep notes on parameter choices
4. **Backup**: Save important results regularly
5. **Monitor**: Watch for errors and interruptions
6. **Validate**: Check results make sense
7. **Compare**: Run multiple configurations for comparison

## See Also
- [Configuration Guide](configuration.md)
- [Analysis Summary Guide](analysis_summary.md)
- [Visualization Guide](visualization.md)
- [Export Guide](export.md)
