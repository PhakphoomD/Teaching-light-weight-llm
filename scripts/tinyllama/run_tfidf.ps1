# Run TF-IDF Model - TinyLlama 1.1B
# Baseline + TF-IDF Retrieval

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TF-IDF Model - TinyLlama 1.1B" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:DATASET_PATH = "data/datasets/alpaca_20.jsonl"
$env:OUTPUT_DIR = "logs/experiments/tinyllama_1_1b/memory_tfidf"
$env:MAX_ITERS = "3"
$env:STUDENT_PROVIDER = "local"
$env:K_TFIDF = "3"
$env:TFIDF_THRESHOLD = "0.1"
$env:USE_SELF_REFLECTION = "true"

# Run experiment
python -m src.experiments.tfidf_model

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "TF-IDF experiment completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
