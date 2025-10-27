# Run Baseline Experiment for Llama2 7B
# No memory, no retrieval

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Baseline Experiment - Llama2 7B" -ForegroundColor Cyan
Write-Host "No Memory, No Retrieval" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$env:DATASET_PATH = "data/datasets/alpaca_20.jsonl"
$env:OUTPUT_DIR = "logs/experiments/llama2_7b/baseline"
$env:MAX_ITERS = "3"
$env:STUDENT_PROVIDER = "local"  # Change to your provider

# Run experiment
# Note: You'll need to create llama2 experiment runners similar to tinyllama
# python -m src.experiments.llama2.baseline_model

Write-Host ""
Write-Host "Baseline experiment for Llama2 7B" -ForegroundColor Yellow
Write-Host "NOTE: Llama2 experiment runners not yet implemented" -ForegroundColor Red
Write-Host "Create them similar to src/experiments/baseline_model.py" -ForegroundColor Yellow
