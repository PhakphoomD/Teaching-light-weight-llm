# Run Baseline Model - TinyLlama 1.1B
# No memory, no retrieval

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Baseline Model - TinyLlama 1.1B" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:DATASET_PATH = "data/datasets/alpaca_20.jsonl"
$env:OUTPUT_DIR = "logs/experiments/tinyllama_1_1b/baseline"
$env:MAX_ITERS = "3"
$env:STUDENT_PROVIDER = "local"

# Run experiment
python -m src.experiments.baseline_model

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Baseline experiment completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
