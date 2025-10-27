# Compare Baseline vs Rule-Key Retrieval
# Runs both experiments on same dataset and compares results

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "COMPARISON: Baseline vs Rule-Key Retrieval" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Activate conda environment
Write-Host "Activating conda environment 'tlw'..." -ForegroundColor Gray
conda activate tlw
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to activate conda environment!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Configuration
$DATASET = "data/datasets/alpaca_100.jsonl"
$MAX_ITERS = "2"
$STUDENT = "local"
$K_RULE = "3"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Dataset: $DATASET"
Write-Host "  Max iterations: $MAX_ITERS"
Write-Host "  Student: $STUDENT"
Write-Host "  K_RULE: $K_RULE"
Write-Host ""

# Run Baseline
Write-Host "=" * 70 -ForegroundColor Green
Write-Host "EXPERIMENT 1: BASELINE (No Retrieval)" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Green
Write-Host ""

$env:DATASET_PATH = $DATASET
$env:MEMORY_PATH = "data/memory/baseline.json"
$env:MAX_ITERS = $MAX_ITERS
$env:STUDENT_PROVIDER = $STUDENT

python -m src.pipeline.baseline_eval

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nBaseline evaluation failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Waiting 3 seconds before next experiment..." -ForegroundColor Gray
Start-Sleep -Seconds 3
Write-Host ""

# Run Rule-Key
Write-Host "=" * 70 -ForegroundColor Green
Write-Host "EXPERIMENT 2: RULE-KEY RETRIEVAL" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Green
Write-Host ""

$env:DATASET_PATH = $DATASET
$env:MEMORY_PATH = "data/memory/rulekey.json"
$env:MAX_ITERS = $MAX_ITERS
$env:STUDENT_PROVIDER = $STUDENT
$env:K_RULE = $K_RULE

python -m src.pipeline.rulekey_eval

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nRule-key evaluation failed!" -ForegroundColor Red
    exit 1
}

# Compare Results
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "COMPARISON RESULTS" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

$baseline = Get-Content "logs/experiments/baseline/summary.json" | ConvertFrom-Json
$rulekey = Get-Content "logs/experiments/rulekey/summary.json" | ConvertFrom-Json

Write-Host "Metric                  Baseline        Rule-Key        Improvement" -ForegroundColor Yellow
Write-Host "-" * 70

$successImprovement = (($rulekey.success_rate - $baseline.success_rate) * 100)
Write-Host ("Success Rate:           {0:P1}          {1:P1}          {2:+0.0;-0.0}%" -f $baseline.success_rate, $rulekey.success_rate, $successImprovement)

$attemptsImprovement = (($baseline.avg_attempts - $rulekey.avg_attempts) / $baseline.avg_attempts * 100)
Write-Host ("Avg Attempts:           {0:F2}           {1:F2}           {2:+0.0;-0.0}%" -f $baseline.avg_attempts, $rulekey.avg_attempts, $attemptsImprovement)

Write-Host ("Avg Gen Time:           {0:F0} ms        {1:F0} ms" -f $baseline.avg_generation_ms, $rulekey.avg_generation_ms)

if ($rulekey.PSObject.Properties.Name -contains 'avg_retrieval_ms') {
    Write-Host ("Avg Retrieval Time:     N/A             {0:F0} ms" -f $rulekey.avg_retrieval_ms)
}

$totalTimeImprovement = (($baseline.avg_total_ms - $rulekey.avg_total_ms) / $baseline.avg_total_ms * 100)
Write-Host ("Avg Task Time:          {0:F0} ms        {1:F0} ms        {2:+0.0;-0.0}%" -f $baseline.avg_total_ms, $rulekey.avg_total_ms, $totalTimeImprovement)

Write-Host ""
Write-Host "Detailed results saved to:" -ForegroundColor Green
Write-Host "  - logs/experiments/baseline/"
Write-Host "  - logs/experiments/rulekey/"
Write-Host ""

if ($rulekey.success_rate -gt $baseline.success_rate) {
    Write-Host "✅ Rule-key retrieval shows improvement!" -ForegroundColor Green
} elseif ($rulekey.success_rate -eq $baseline.success_rate) {
    Write-Host "➡️  Both methods show similar performance" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Baseline performed better (unexpected)" -ForegroundColor Yellow
}

Write-Host ""
