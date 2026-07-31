<#
.SYNOPSIS
    AgentMatrix 一键启动脚本（PowerShell）
    启动 Ollama（本地模型）+ 后端（FastAPI）+ 前端（Next.js）

.DESCRIPTION
    用法：
      .\start_all.ps1              # 启动全部三个服务
      .\start_all.ps1 -CheckOnly   # 仅检查服务状态，不启动

    服务启动后会持续在后台运行，关闭本脚本窗口不会停止服务。
    要停止服务：关闭对应的终端窗口，或用 stop_all.ps1

.NOTES
    前置要求：
      - Ollama 已安装并拉取 qwen2.5:7b 模型
      - Node.js v22+ 已安装
      - Python 3.10+ 已安装
      - 已执行过 pip install -r backend/requirements.txt
      - 已执行过 cd frontend; npm install
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
        Write-Host "  [✓] $Name :$Port  ($procName)  -> $Url" -ForegroundColor Green
    } else {
        Write-Host "  [✗] $Name :$Port  (未运行)        -> $Url" -ForegroundColor Red
    }
}

# ========== 服务定义 ==========
$ROOT = $PSScriptRoot
$Services = @(
    @{
        Name = "Ollama (本地模型)"
        Port = 11434
        Url  = "http://localhost:11434"
        Cmd  = "ollama serve"
        Cwd  = $null
    },
    @{
        Name = "后端 (FastAPI)"
        Port = 8000
        Url  = "http://localhost:8000/docs"
        Cmd  = "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
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

    # 在新的 PowerShell 窗口中启动（保持后台运行）
    $argList = @("-NoExit", "-Command", $svc.Cmd)
    if ($svc.Cwd) {
        $argList = @("-NoExit", "-Command", "Set-Location '$($svc.Cwd)'; $($svc.Cmd)")
    }

    Start-Process -FilePath "powershell" -ArgumentList $argList -WindowStyle Normal

    # 等待端口就绪（最多 30 秒）
    $maxWait = 30
    $waited = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 1
        $waited++
        if (Test-Port -Port $svc.Port) {
            break
        }
    }

    if (Test-Port -Port $svc.Port) {
        Write-Host "  [✓] $($svc.Name) 启动成功 (等待 ${waited}s)" -ForegroundColor Green
    } else {
        Write-Host "  [✗] $($svc.Name) 启动超时 (${maxWait}s)，请检查新窗口的日志" -ForegroundColor Red
    }
}

# ========== 最终状态检查 ==========
Write-Host "`n=== 启动结果 ===" -ForegroundColor Cyan
foreach ($svc in $Services) {
    Write-Status -Name $svc.Name -Port $svc.Port -Url $svc.Url
}

Write-Host "`n访问地址:" -ForegroundColor Cyan
Write-Host "  前端主界面:   http://localhost:3000" -ForegroundColor White
Write-Host "  后端 API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Ollama API:   http://localhost:11434" -ForegroundColor White
Write-Host ""
Write-Host "提示: 三个服务各在一个独立的 PowerShell 窗口运行，关闭窗口即可停止对应服务。" -ForegroundColor Gray
Write-Host "      仅检查状态: .\start_all.ps1 -CheckOnly" -ForegroundColor Gray
Write-Host ""
