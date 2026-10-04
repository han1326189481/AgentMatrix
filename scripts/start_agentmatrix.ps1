# AgentMatrix One-Click Launcher
$ErrorActionPreference = "Continue"
$OllamaPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
$AppPath = "D:\AgentMatrix\frontend\src-tauri\target\release\app.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AgentMatrix - Multi-Agent Platform" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Checking Ollama service..." -ForegroundColor Yellow
$ollamaRunning = Get-Process ollama -ErrorAction SilentlyContinue
if ($ollamaRunning) {
    Write-Host "  [OK] Ollama is running (PID: $($ollamaRunning.Id))" -ForegroundColor Green
}
else {
    Write-Host "  --> Starting Ollama..." -ForegroundColor Yellow
    if (Test-Path $OllamaPath) {
        Start-Process $OllamaPath -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 4
        Write-Host "  [OK] Ollama started" -ForegroundColor Green
    }
    else {
        Write-Host "  [ERROR] Ollama not found: $OllamaPath" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "[2/3] Launching AgentMatrix desktop app..." -ForegroundColor Yellow
if (Test-Path $AppPath) {
    Start-Process $AppPath
    Write-Host "  [OK] App launched" -ForegroundColor Green
}
else {
    Write-Host "  [ERROR] App not found: $AppPath" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "[3/3] Waiting for backend..." -ForegroundColor Yellow
$maxWait = 30
for ($i = 1; $i -le $maxWait; $i++) {
    Start-Sleep -Seconds 1
    $result = & curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8000/health 2>$null
    if ($result -eq "200") {
        Write-Host "  [OK] Backend ready (${i}s)" -ForegroundColor Green
        break
    }
    if ($i -eq $maxWait) {
        Write-Host "  [WARN] Backend timeout (${maxWait}s)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AgentMatrix launch complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to close..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")