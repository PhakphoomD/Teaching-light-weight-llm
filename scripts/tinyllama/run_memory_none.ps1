# Run Memory-None Experiment
# Stores reflections but doesn't retrieve them

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Memory-None Experiment" -ForegroundColor Cyan
Write-Host "TinyLlama 1.1B - Memory without Retrieval" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$env:DATASET_PATH = "data/datasets/alpaca_20.jsonl"
$env:OUTPUT_DIR = "logs/experiments/tinyllama_1_1b/memory_none"
$env:MAX_ITERS = "3"
$env:STUDENT_PROVIDER = "local"

# Run experiment
python -m src.experiments.memory_none_model

Write-Host ""
Write-Host "Memory-None experiment completed!" -ForegroundColor Green
