# AgentMatrix Backend Startup Script
$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AgentMatrix 后端启动脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
Write-Host "[1/3] 工作目录: $PWD" -ForegroundColor Green

# Check Python
Write-Host "[2/3] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $PyVersion = python --version 2>&1
    Write-Host "✅ Python 版本: $PyVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python 未找到！" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# Start the backend
Write-Host "[3/3] 启动服务..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  服务地址: http://localhost:8000" -ForegroundColor Green
Write-Host "  API文档: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  按 Ctrl+C 停止服务" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

try {
    python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
} catch {
    Write-Host ""
    Write-Host "❌ 启动失败！" -ForegroundColor Red
    Write-Host "错误信息: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "尝试使用直接方式启动..." -ForegroundColor Yellow
    try {
        python app/main.py
    } catch {
        Write-Host "❌ 仍然失败，请检查依赖安装" -ForegroundColor Red
        Read-Host "按 Enter 退出"
    }
}
