$ErrorActionPreference = "Continue"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host " AgentMatrix - Full Startup" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/6] Checking environment..." -ForegroundColor Yellow
$projectPath = Get-Location

$env:OLLAMA_HOST = "http://localhost:11435"

Write-Host "[2/6] Checking Ollama..." -ForegroundColor Yellow
try {
    $ollamaCheck = ollama list 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Ollama is running!" -ForegroundColor Green
        Write-Host "  Installed models:"
        Write-Host $ollamaCheck -ForegroundColor DarkGray
    } else {
        Write-Host "  Starting Ollama service..." -ForegroundColor Yellow
        Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 3
        Write-Host "  Ollama started!" -ForegroundColor Green
    }
} catch {
    Write-Host "  Starting Ollama service..." -ForegroundColor Yellow
    Start-Process ollama -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "[3/6] Ensuring backend .env exists..." -ForegroundColor Yellow
Set-Location (Join-Path $projectPath "backend")
if (-not (Test-Path ".env")) {
    Write-Host "  Creating .env from .env.example..."
    Copy-Item ".env.example" ".env" -ErrorAction SilentlyContinue
    (Get-Content .env) -replace "http://localhost:11434", "http://localhost:11435" | Set-Content .env
}
Write-Host "  Backend config ready!" -ForegroundColor Green

Write-Host ""
Write-Host "[4/6] Starting backend service..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($projectPath)
    Set-Location (Join-Path $projectPath "backend")
    python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload 2>&1
} -ArgumentList $projectPath
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "[5/6] Starting frontend service..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($projectPath)
    Set-Location (Join-Path $projectPath "frontend")
    npm run dev 2>&1
} -ArgumentList $projectPath

Write-Host ""
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Services starting! Please wait 5-10 seconds" -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 8

Write-Host "[6/6] Checking service status..." -ForegroundColor Yellow

try {
    $backendOutput = Receive-Job $backendJob
    $frontendOutput = Receive-Job $frontendJob

    if ($backendOutput -match "Uvicorn running" -or $backendOutput -match "Application startup") {
        Write-Host "  Backend service started successfully!" -ForegroundColor Green
    }
    if ($frontendOutput -match "Ready in" -or $frontendOutput -match "Next.js") {
        Write-Host "  Frontend service started successfully!" -ForegroundColor Green
    }
} catch {
    Write-Host "  Checking services..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host "  System started!" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Access URLs:" -ForegroundColor White
Write-Host "    Frontend:    http://localhost:3000" -ForegroundColor Cyan
Write-Host "    Backend API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "    API Docs:    http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Local models loaded:" -ForegroundColor White
Write-Host "    qwen2.5:1.5b" -ForegroundColor Green
Write-Host "    phi4-mini:3.8b" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 10
        $bOut = Receive-Job $backendJob
        $fOut = Receive-Job $frontendJob
        if ($bOut) { Write-Host $bOut -ForegroundColor DarkGray }
        if ($fOut) { Write-Host $fOut -ForegroundColor DarkGray }
    }
} finally {
    Write-Host "Stopping all services..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
    Remove-Job $frontendJob -Force -ErrorAction SilentlyContinue
    Write-Host "All services stopped!" -ForegroundColor Green
}