# Run RuleKey Model - TinyLlama 1.1B
# Baseline + Rule-based Retrieval

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RuleKey Model - TinyLlama 1.1B" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:DATASET_PATH = "data/datasets/alpaca_20.jsonl"
$env:OUTPUT_DIR = "logs/experiments/tinyllama_1_1b/memory_rulekey"
$env:MAX_ITERS = "3"
$env:STUDENT_PROVIDER = "local"
$env:K_RULEKEY = "3"
$env:USE_SELF_REFLECTION = "true"

# Run experiment
python -m src.experiments.rulekey_model

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "RuleKey experiment completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
