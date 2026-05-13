$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Stopping AgentMatrix Services..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$backendProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*AgentMatrix*" }
if ($backendProcesses) {
    $backendProcesses | ForEach-Object { 
        $_.Kill()
        Write-Host "[OK] Backend server stopped" -ForegroundColor Green
    }
} else {
    Write-Host "[INFO] Backend process not found or already stopped" -ForegroundColor Yellow
}

$frontendProcesses = Get-Process node -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*AgentMatrix*" }
if ($frontendProcesses) {
    $frontendProcesses | ForEach-Object { 
        $_.Kill()
        Write-Host "[OK] Frontend server stopped" -ForegroundColor Green
    }
} else {
    Write-Host "[INFO] Frontend process not found or already stopped" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "All services stopped" -ForegroundColor Green
Write-Host ""
Read-Host "Press any key to exit..."