# AgentMatrix Backend Launcher

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AgentMatrix Backend" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot\backend

Write-Host "[1/3] Checking Python..." -ForegroundColor Yellow
python --version

Write-Host "[2/3] Ensuring .env exists..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created .env" -ForegroundColor Green
} else {
    Write-Host "  .env already exists" -ForegroundColor Green
}

Write-Host "[3/3] Starting Uvicorn..." -ForegroundColor Yellow
Write-Host ""

python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
