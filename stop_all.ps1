<#
.SYNOPSIS
    AgentMatrix 一键停止脚本（PowerShell）
    停止前端 / 后端 / Ollama 三个服务

.DESCRIPTION
    用法：.\stop_all.ps1
#>

$ErrorActionPreference = "SilentlyContinue"

$Ports = @(3000, 8000, 11434)
$Names = @{
    3000  = "前端 (Next.js)"
    8000  = "后端 (FastAPI)"
    11434 = "Ollama"
}

Write-Host "`n=== AgentMatrix 一键停止 ===" -ForegroundColor Cyan

foreach ($port in $Ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $pid = $conn[0].OwningProcess
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        $procName = $proc.ProcessName
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        if (Test-Path "variable:$proc") {
            Write-Host "  [✓] 停止 $($Names[$port]) :$port (PID $pid, $procName)" -ForegroundColor Green
        } else {
            Write-Host "  [✓] 停止 $($Names[$port]) :$port (PID $pid)" -ForegroundColor Green
        }
    } else {
        Write-Host "  [-] $($Names[$port]) :$port 未运行" -ForegroundColor Gray
    }
}

Write-Host "`n所有服务已停止。`n" -ForegroundColor Cyan
