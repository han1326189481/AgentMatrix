# Simple start script
$ErrorActionPreference = "Continue"

Write-Host "Starting AgentMatrix Backend..." -ForegroundColor Cyan
Write-Host "Working directory: $PWD" -ForegroundColor Yellow

try {
    # Check Python
    $pyVersion = python --version 2>&1
    Write-Host "Python: $pyVersion" -ForegroundColor Green
    
    # Change to backend directory
    $backendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $backendDir
    Write-Host "Changed to: $backendDir" -ForegroundColor Yellow
    
    # Start uvicorn
    Write-Host "Starting uvicorn..." -ForegroundColor Cyan
    Write-Host "Server will be at: http://localhost:8000" -ForegroundColor Green
    Write-Host "Health check: http://localhost:8000/health" -ForegroundColor Green
    Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Green
    Write-Host ""
    
    python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
