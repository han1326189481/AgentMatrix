$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " AgentMatrix - Multi-Agent Collaboration System" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Python not found. Please install Python 3.10+" -ForegroundColor Red
        Read-Host "Press any key to exit..."
        exit 1
    }
} catch {
    Write-Host "[ERROR] Python not found. Please install Python 3.10+" -ForegroundColor Red
    Read-Host "Press any key to exit..."
    exit 1
}

try {
    $nodeVersion = node --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Node.js not found. Please install Node.js 20+" -ForegroundColor Red
        Read-Host "Press any key to exit..."
        exit 1
    }
} catch {
    Write-Host "[ERROR] Node.js not found. Please install Node.js 20+" -ForegroundColor Red
    Read-Host "Press any key to exit..."
    exit 1
}

Write-Host "[OK] Python and Node.js environment ready" -ForegroundColor Green
Write-Host ""

$projectPath = Get-Location

Write-Host "[Step 1/4] Checking backend dependencies..." -ForegroundColor Yellow
Set-Location (Join-Path $projectPath "backend")
if (-not (Test-Path "venv")) {
    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    pip install pydantic pydantic-settings fastapi uvicorn httpx python-dotenv | Out-Null
} else {
    Write-Host "Backend dependencies already installed" -ForegroundColor Green
}
Set-Location $projectPath

Write-Host "[Step 2/4] Checking frontend dependencies..." -ForegroundColor Yellow
Set-Location (Join-Path $projectPath "frontend")
if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install | Out-Null
} else {
    Write-Host "Frontend dependencies already installed" -ForegroundColor Green
}
Set-Location $projectPath

Write-Host ""
Write-Host "[Step 3/4] Starting backend server..." -ForegroundColor Yellow
Start-Process -FilePath "powershell" -ArgumentList "-Command", "cd '$(Join-Path $projectPath 'backend')'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -WindowStyle Normal -WorkingDirectory (Join-Path $projectPath "backend")

Start-Sleep -Seconds 2

Write-Host "[Step 4/4] Starting frontend server..." -ForegroundColor Yellow
Start-Process -FilePath "powershell" -ArgumentList "-Command", "cd '$(Join-Path $projectPath 'frontend')'; npm run dev" -WindowStyle Normal -WorkingDirectory (Join-Path $projectPath "frontend")

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " System started successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host " Access URLs:" -ForegroundColor White
Write-Host "   - Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "   - Backend API: http://localhost:8000" -ForegroundColor Green
Write-Host "   - API Docs: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Read-Host "Press any key to close this window (services will continue running)..."