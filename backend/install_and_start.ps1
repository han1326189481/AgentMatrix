# Install dependencies and start backend
$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AgentMatrix Backend Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
$backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendDir
Write-Host "Working in: $backendDir" -ForegroundColor Yellow
Write-Host ""

# Install dependencies
Write-Host "[1/2] Installing dependencies..." -ForegroundColor Yellow
python -m pip install fastapi uvicorn pydantic pydantic-settings python-dotenv python-socketio sqlalchemy aiohttpx

Write-Host ""
Write-Host "[2/2] Starting server..." -ForegroundColor Yellow
Write-Host "Server: http://localhost:8000" -ForegroundColor Green
Write-Host "Health: http://localhost:8000/health" -ForegroundColor Green
Write-Host "Docs:   http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start the server
python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000
