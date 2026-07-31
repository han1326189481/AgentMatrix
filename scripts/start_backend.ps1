$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Starting AgentMatrix Backend..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$env:PYTHONPATH = ".\backend"

$backendDir = Join-Path $PSScriptRoot "..\backend"
Push-Location $backendDir

Write-Host "[1/2] Checking environment..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python version: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found!" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "[2/2] Starting Uvicorn..." -ForegroundColor Yellow
Write-Host ""

try {
    python -c "
import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
import app.main
import uvicorn
from app.main import socket_app
print('✅ All imports succeeded, now starting server...')
uvicorn.run(socket_app, host='0.0.0.0', port=8000, reload=True)
"
} catch {
    Write-Host "❌ Failed to start server: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Server stopped"
