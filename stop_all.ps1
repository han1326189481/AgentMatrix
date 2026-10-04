<#
.SYNOPSIS
    AgentMatrix 一键停止脚本（唯一入口）

.DESCRIPTION
    用法：.\stop_all.ps1
    按端口停止前端(3000) / 后端(8000) / Ollama(11434)。

    注意：仅停止 Ollama 服务进程，不影响 Ollama 常驻模型。
    若只想重启后端，可运行 .\stop_all.ps1 后再 .\start_all.ps1。
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
        $targetPid = $conn[0].OwningProcess
        $proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
        $procName = $proc.ProcessName
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        Write-Host "  [OK] 已停止 $($Names[$port]) :$port (PID $targetPid, $procName)" -ForegroundColor Green
    } else {
        Write-Host "  [--] $($Names[$port]) :$port 未运行" -ForegroundColor Gray
    }
}

Write-Host "`n所有服务已停止。`n" -ForegroundColor Cyan
