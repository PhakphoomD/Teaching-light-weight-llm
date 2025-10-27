# Run TF-IDF Experiment for Llama2 7B
# Memory with TF-IDF retrieval

Write-Host "================================" -ForegroundColor Cyan
Write-Host "TF-IDF Experiment - Llama2 7B" -ForegroundColor Cyan
Write-Host "Memory + TF-IDF Retrieval" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$env:DATASET_PATH = "data/datasets/alpaca_20.jsonl"
$env:OUTPUT_DIR = "logs/experiments/llama2_7b/memory_tfidf"
$env:MAX_ITERS = "3"
$env:STUDENT_PROVIDER = "local"
$env:RETRIEVAL_K = "5"
$env:TFIDF_THRESHOLD = "0.15"

# Run experiment
# Note: You'll need to create llama2 experiment runners
# python -m src.experiments.llama2.tfidf_model

Write-Host ""
Write-Host "TF-IDF experiment for Llama2 7B" -ForegroundColor Yellow
Write-Host "NOTE: Llama2 experiment runners not yet implemented" -ForegroundColor Red
Write-Host "Create them similar to src/experiments/tfidf_model.py" -ForegroundColor Yellow
