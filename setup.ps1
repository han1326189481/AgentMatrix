<#
.SYNOPSIS
    AgentMatrix 环境初始化脚本（一次性执行）

.DESCRIPTION
    创建 backend/.venv313（Python 3.13）并安装全部依赖。
    幂等：已存在且依赖齐全时直接跳过。

    前置要求：
      - 已安装 Python 3.13（系统命令 py -3.13 或 python 3.13+）
      - Node.js v22+（前端依赖，npm install 手动执行）
#>
$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$VenvPython = Join-Path $Root "backend\.venv313\Scripts\python.exe"

Write-Host "=== AgentMatrix 环境初始化 ===" -ForegroundColor Cyan

# ── 1. 定位 Python 3.13 ──
if (Test-Path $VenvPython) {
    Write-Host "[跳过] .venv313 已存在: $VenvPython" -ForegroundColor Green
    & $VenvPython -V
    exit 0
}

$basePython = $null
try { $v = & py -3.13 -V 2>&1; if ($LASTEXITCODE -eq 0 -and "$v" -match "3\.13") { $basePython = "py -3.13" } } catch {}
if (-not $basePython) {
    try { $v = & python -V 2>&1; if ("$v" -match "3\.1[0-9]") { $basePython = "python" } } catch {}
}
if (-not $basePython) {
    # 回退：WorkBuddy 托管运行时
    $fallback = "C:\Users\13261\.workbuddy\binaries\python\versions\3.13.12\python.exe"
    if (Test-Path $fallback) { $basePython = $fallback }
}
if (-not $basePython) {
    Write-Host "[错误] 未找到 Python 3.10+（优先 3.13）。请安装后重试。" -ForegroundColor Red
    exit 1
}
Write-Host "[1/3] 使用基础解释器: $basePython" -ForegroundColor Yellow

# ── 2. 创建 venv ──
Write-Host "[2/3] 创建 backend\.venv313 ..." -ForegroundColor Yellow
& $basePython -m venv (Join-Path $Root "backend\.venv313")
if (-not (Test-Path $VenvPython)) {
    Write-Host "[错误] venv 创建失败" -ForegroundColor Red
    exit 1
}

# ── 3. 安装依赖 ──
Write-Host "[3/3] 安装依赖（阿里云镜像，约 5-15 分钟）..." -ForegroundColor Yellow
& $VenvPython -m pip install -r (Join-Path $Root "backend\requirements.txt") `
    -i https://mirrors.aliyun.com/pypi/simple/ --no-cache-dir --timeout 90 --retries 8
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 依赖安装失败，请检查网络后重跑本脚本" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== 初始化完成 ===" -ForegroundColor Green
& $VenvPython -V
Write-Host "启动服务: .\start_all.ps1"
