<#
.SYNOPSIS
    AgentMatrix 一键启动脚本（唯一入口，v5 — Python 3.13 版）

.DESCRIPTION
    用法：
      .\start_all.ps1              # 启动全部三个服务
      .\start_all.ps1 -CheckOnly   # 仅检查服务状态，不启动

    v5 变更（2026-09-22）：
      - 后端固定使用 backend\.venv313\Scripts\python.exe（Python 3.13）
      - 后端命令改为 socket_app（app.main:app 缺 Socket.IO 挂载，此前是 bug）
      - 后端绑定 127.0.0.1（P0 安全加固：默认仅本机访问；需要局域网演示时
        在 backend\.env 中将 SERVER_HOST 改为 0.0.0.0）
      - 前端固定 http://localhost:3000

    前置要求：
      - 已运行 .\setup.ps1（创建 .venv313 并安装依赖）
      - Ollama 已安装并拉取 qwen2.5vl:7b
      - Node.js v22+，且 frontend\node_modules 已 npm install

    停止服务：.\stop_all.ps1
#>
param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "SilentlyContinue"

# ========== 工具函数 ==========
function Test-Port {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Get-PortProcess {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $proc = Get-Process -Id $conn[0].OwningProcess -ErrorAction SilentlyContinue
        return $proc.ProcessName
    }
    return $null
}

function Write-Status {
    param([string]$Name, [int]$Port, [string]$Url)
    $running = Test-Port -Port $Port
    if ($running) {
        $procName = Get-PortProcess -Port $Port
        Write-Host "  [OK] $Name :$Port  ($procName)  -> $Url" -ForegroundColor Green
    } else {
        Write-Host "  [--] $Name :$Port  (未运行)        -> $Url" -ForegroundColor Red
    }
}

# ========== 路径与解释器 ==========
$ROOT = $PSScriptRoot
$VenvPython = Join-Path $ROOT "backend\.venv313\Scripts\python.exe"

# ========== 服务定义 ==========
$Services = @(
    @{
        Name = "Ollama (本地模型)"
        Port = 11434
        Url  = "http://localhost:11434"
        Cmd  = "ollama serve"
        Cwd  = $null
    },
    @{
        Name = "后端 (FastAPI @ .venv313)"
        Port = 8000
        Url  = "http://127.0.0.1:8000/docs"
        Cmd  = "`"$VenvPython`" -m uvicorn app.main:socket_app --host 127.0.0.1 --port 8000 --log-level info"
        Cwd  = "$ROOT\backend"
    },
    @{
        Name = "前端 (Next.js)"
        Port = 3000
        Url  = "http://localhost:3000"
        Cmd  = "npm run dev"
        Cwd  = "$ROOT\frontend"
    }
)

# ========== 检查模式 ==========
if ($CheckOnly) {
    Write-Host "`n=== AgentMatrix 服务状态 ===" -ForegroundColor Cyan
    foreach ($svc in $Services) {
        Write-Status -Name $svc.Name -Port $svc.Port -Url $svc.Url
    }
    Write-Host ""
    exit 0
}

# ========== 前置校验 ==========
if (-not (Test-Path $VenvPython)) {
    Write-Host "[错误] 未找到 $VenvPython" -ForegroundColor Red
    Write-Host "       请先运行 .\setup.ps1 初始化环境" -ForegroundColor Yellow
    exit 1
}
Write-Host "后端解释器: $VenvPython" -ForegroundColor Gray
& $VenvPython -V

# ========== 启动前自动快照（运行时数据防线） ==========
# 知识图谱 / SQLite / 用户数据都在运行时被改写，git 管不到它们。
# 每次开工留一份快照，出事时用 scripts\restore.ps1 回档。
$BackupScript = Join-Path $ROOT "scripts\backup.ps1"
if (Test-Path $BackupScript) {
    Write-Host "`n[备份] 启动前快照运行时数据 ..." -ForegroundColor Cyan
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $BackupScript -Label startup -Quiet
        switch ($LASTEXITCODE) {
            0 { Write-Host "  [OK] 快照完成" -ForegroundColor Green }
            2 { Write-Host "  [!!] 快照被「缩水拦截」拒绝 —— 图谱疑似损坏，请立即检查！" -ForegroundColor Red }
            default { Write-Host "  [!!] 快照失败 (exit=$LASTEXITCODE)，详见 D:\AgentMatrix_backups\logs" -ForegroundColor Yellow }
        }
    } catch {
        Write-Host "  [!!] 快照异常: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "[备份] 未找到 scripts\backup.ps1，跳过快照" -ForegroundColor Yellow
}

# ========== 启动模式 ==========
Write-Host "`n=== AgentMatrix 一键启动 ===" -ForegroundColor Cyan
Write-Host "启动时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n" -ForegroundColor Gray

foreach ($svc in $Services) {
    $running = Test-Port -Port $svc.Port
    if ($running) {
        $procName = Get-PortProcess -Port $svc.Port
        Write-Host "[跳过] $($svc.Name) 已在运行 ($procName)" -ForegroundColor Yellow
        continue
    }

    Write-Host "[启动] $($svc.Name) ..." -ForegroundColor Cyan

    $argList = @("-NoExit", "-Command", $svc.Cmd)
    if ($svc.Cwd) {
        $argList = @("-NoExit", "-Command", "Set-Location '$($svc.Cwd)'; $($svc.Cmd)")
    }

    Start-Process -FilePath "powershell" -ArgumentList $argList -WindowStyle Normal

    # 等待端口就绪（Ollama 30s / 后端 45s / 前端 90s）
    $maxWait = 30
    if ($svc.Port -eq 8000) { $maxWait = 45 }
    if ($svc.Port -eq 3000) { $maxWait = 90 }
    $waited = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 1
        $waited++
        if (Test-Port -Port $svc.Port) { break }
    }

    if (Test-Port -Port $svc.Port) {
        Write-Host "  [OK] $($svc.Name) 启动成功 (等待 ${waited}s)" -ForegroundColor Green
    } else {
        Write-Host "  [!!] $($svc.Name) 启动超时 (${maxWait}s)，请检查新窗口的日志" -ForegroundColor Red
    }
}

# ========== 最终状态检查 ==========
Write-Host "`n=== 启动结果 ===" -ForegroundColor Cyan
foreach ($svc in $Services) {
    Write-Status -Name $svc.Name -Port $svc.Port -Url $svc.Url
}

Write-Host "`n访问地址:" -ForegroundColor Cyan
Write-Host "  前端主界面:    http://localhost:3000" -ForegroundColor White
Write-Host "  后端 API 文档: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Ollama API:    http://localhost:11434" -ForegroundColor White
Write-Host ""
Write-Host "提示: 三个服务各在一个独立的 PowerShell 窗口运行，关闭窗口即可停止对应服务。"
Write-Host "      一键停止: .\stop_all.ps1   仅查状态: .\start_all.ps1 -CheckOnly" -ForegroundColor Gray
Write-Host ""
