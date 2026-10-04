<#
.SYNOPSIS
    从快照恢复 AgentMatrix 数据（知识图谱 / 用户数据 / 配置）

.DESCRIPTION
    与 scripts\backup.ps1 配套。恢复前会**自动把当前状态另存**为
    `prerevert` 快照，所以即使恢复了错误的快照也能再退回来。

    用法:
      .\scripts\restore.ps1 -List                    # 列出可用快照
      .\scripts\restore.ps1                           # 恢复最新一份（需输入 YES 确认）
      .\scripts\restore.ps1 -Snapshot snapshot_20260924_210702_manual.zip
      .\scripts\restore.ps1 -Snapshot 20260924        # 模糊匹配
      .\scripts\restore.ps1 -Yes                      # 跳过确认（脚本化场景）

    退出码: 0 成功 / 1 找不到快照或失败
#>
[CmdletBinding()]
param(
    [string]$Snapshot = "latest",
    [string]$Source = "D:\AgentMatrix_backups",
    [switch]$List,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Backend  = Join-Path $RepoRoot "backend"
$SnapDir  = Join-Path $Source "snapshots"

function Get-Snaps {
    @(Get-ChildItem $SnapDir -Filter "snapshot_*.zip" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending)
}

# ================= -List =================
if ($List) {
    Write-Host "`n=== 可用快照 ($SnapDir) ===" -ForegroundColor Cyan
    $snaps = Get-Snaps
    if ($snaps.Count -eq 0) { Write-Host "  (无)" -ForegroundColor DarkGray; return }
    foreach ($s in $snaps) {
        Write-Host ("  {0}   {1,9:N0} KB   {2}" -f `
            $s.Name, ($s.Length / 1KB), $s.LastWriteTime.ToString("yyyy-MM-dd HH:mm"))
    }
    Write-Host ""
    return
}

# ================= 解析目标快照 =================
$target = $null
if ($Snapshot -eq "latest") {
    $target = Get-Snaps | Select-Object -First 1
} else {
    $direct = Join-Path $SnapDir $Snapshot
    if (Test-Path $direct) {
        $target = Get-Item $direct
    } else {
        $target = Get-Snaps | Where-Object { $_.Name -like "*$Snapshot*" } | Select-Object -First 1
    }
}

if (-not $target) {
    Write-Host "找不到快照: $Snapshot" -ForegroundColor Red
    Write-Host "用 .\scripts\restore.ps1 -List 查看可用快照" -ForegroundColor Yellow
    exit 1
}

# ================= 确认 =================
Write-Host "`n即将用以下快照恢复（会覆盖当前运行时数据）：" -ForegroundColor Yellow
Write-Host ("  快照: {0}" -f $target.Name) -ForegroundColor White
Write-Host ("  时间: {0}" -f $target.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")) -ForegroundColor White
Write-Host ("  大小: {0:N0} KB" -f ($target.Length / 1KB)) -ForegroundColor White

if (-not $Yes) {
    Write-Host "`n当前数据会先自动另存为 prerevert 快照。" -ForegroundColor Gray
    $ans = Read-Host "确认恢复请输入 YES"
    if ($ans -ne "YES") { Write-Host "已取消" -ForegroundColor Gray; exit 0 }
}

# ================= 1. 先另存当前状态 =================
Write-Host "`n[1/4] 另存当前状态..." -ForegroundColor Cyan
$bk = Join-Path $PSScriptRoot "backup.ps1"
if (Test-Path $bk) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $bk -Label prerevert -Force
} else {
    Write-Host "  [警告] 未找到 backup.ps1，跳过预存" -ForegroundColor Yellow
}

# ================= 2. 解压 =================
Write-Host "[2/4] 解压快照..." -ForegroundColor Cyan
$tmp = Join-Path $Source (".restore_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
Expand-Archive -Path $target.FullName -DestinationPath $tmp -Force

# ================= 3. 校验 manifest =================
$mf = Join-Path $tmp "manifest.json"
if (Test-Path $mf) {
    try {
        $m = Get-Content $mf -Raw -Encoding utf8 | ConvertFrom-Json
        Write-Host ("  快照信息: 创建于 {0}" -f $m.created_at) -ForegroundColor Gray
        Write-Host ("            图谱 {0} 节点 / {1} 边" -f $m.skill_nodes, $m.skill_edges) -ForegroundColor Gray
    } catch {
        Write-Host "  [警告] manifest 解析失败，继续恢复" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [警告] 快照内无 manifest.json" -ForegroundColor Yellow
}

# ================= 4. 覆盖写回 =================
Write-Host "[3/4] 写回数据..." -ForegroundColor Cyan

$srcBackend = Join-Path $tmp "backend"
if (Test-Path $srcBackend) {
    Copy-Item -Path (Join-Path $srcBackend "*") -Destination $Backend -Recurse -Force
    Write-Host "  已恢复 backend\ (graphs / storage / config / .env)" -ForegroundColor Gray
} else {
    Write-Host "  [警告] 快照内无 backend\ 目录" -ForegroundColor Yellow
}

$srcAppData = Join-Path $tmp "appdata\AgentMatrix\config"
if (Test-Path $srcAppData) {
    $dstAppData = Join-Path $env:APPDATA "AgentMatrix\config"
    New-Item -ItemType Directory -Path $dstAppData -Force | Out-Null
    Copy-Item -Path (Join-Path $srcAppData "*") -Destination $dstAppData -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  已恢复 %APPDATA%\AgentMatrix\config\" -ForegroundColor Gray
}

Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

# ================= 验证 =================
Write-Host "[4/4] 校验恢复结果..." -ForegroundColor Cyan
$py = Join-Path $Backend ".venv313\Scripts\python.exe"
if (Test-Path $py) {
    try {
        $raw = & $py (Join-Path $PSScriptRoot "graph_health.py") 2>&1 | Out-String
        Write-Host ("  图谱现状: " + $raw.Trim()) -ForegroundColor Green
    } catch {
        Write-Host ("  [警告] 校验失败: " + $_.Exception.Message) -ForegroundColor Yellow
    }
}

Write-Host "`n恢复完成。建议重启后端使其重新加载数据。" -ForegroundColor Green
exit 0
