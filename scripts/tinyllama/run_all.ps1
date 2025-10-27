# Run All TinyLlama 1.1B Experiments
# Baseline, TF-IDF, RuleKey, and Memory-None

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Running ALL TinyLlama 1.1B Experiments" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""

# 1. Baseline
Write-Host "[1/4] Running Baseline..." -ForegroundColor Cyan
.\scripts\tinyllama\run_baseline.ps1

Write-Host ""
Start-Sleep -Seconds 2

# 2. TF-IDF
Write-Host "[2/4] Running TF-IDF..." -ForegroundColor Cyan
.\scripts\tinyllama\run_tfidf.ps1

Write-Host ""
Start-Sleep -Seconds 2

# 3. RuleKey
Write-Host "[3/4] Running RuleKey..." -ForegroundColor Cyan
.\scripts\tinyllama\run_rulekey.ps1

Write-Host ""
Start-Sleep -Seconds 2

# 4. Memory-None
Write-Host "[4/4] Running Memory-None..." -ForegroundColor Cyan
.\scripts\tinyllama\run_memory_none.ps1

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "All experiments completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Results saved to: logs/experiments/tinyllama_1_1b/" -ForegroundColor White
