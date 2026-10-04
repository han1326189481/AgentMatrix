<#
.SYNOPSIS
    AgentMatrix 知识资产定期备份（知识图谱 / 用户数据 / 配置）

.DESCRIPTION
    把「运行时数据层」快照到仓库之外的目录，与代码的 git 版本管理互补：
    git 管得住 .py/.ts，但管不住运行时被改写的知识图谱与用户数据。

    备份内容：
      backend/core/graphs/*.yaml                     知识图谱（最珍贵，636 节点）
      backend/storage/{memory,profiles,pending_learning,workspace}
      backend/config/app_config.json
      backend/.env                                   ⚠ 含密钥，注意保管备份目录
      %APPDATA%\AgentMatrix\config\*                 打包环境配置（存在才备份）

    内置「缩水拦截」：图谱节点数骤降（低于上次基线的 50%）时**拒绝备份**，
    防止把已经损坏的状态当成「好状态」存下来，覆盖掉健康的基线。
    这正是 2026-09-24 知识库被清空事故的直接防线。

    用法:
      .\scripts\backup.ps1                  # 自动备份（标签 auto）
      .\scripts\backup.ps1 -Label manual
      .\scripts\backup.ps1 -Keep 60         # 保留最近 60 份（默认 30）
      .\scripts\backup.ps1 -Force           # 跳过缩水拦截（确实要存异常状态时）
      .\scripts\backup.ps1 -List            # 只列出已有快照

    退出码: 0 成功 / 1 失败 / 2 被缩水拦截拒绝
#>
[CmdletBinding()]
param(
    [string]$Label = "auto",
    [int]$Keep = 30,
    [string]$Destination = "D:\AgentMatrix_backups",
    [switch]$Force,
    [switch]$SkipRotation,
    [switch]$List,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$RepoRoot  = Split-Path -Parent $PSScriptRoot
$Backend   = Join-Path $RepoRoot "backend"
$SnapDir   = Join-Path $Destination "snapshots"
$LogDir    = Join-Path $Destination "logs"
$StatePath = Join-Path $Destination "state.json"
$TmpStage  = Join-Path $Destination ".staging"
$VenvPy    = Join-Path $Backend ".venv313\Scripts\python.exe"

foreach ($d in @($Destination, $SnapDir, $LogDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}
$LogFile = Join-Path $LogDir ("backup-" + (Get-Date -Format "yyyy-MM") + ".log")

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
    if (-not $Quiet) {
        $color = "Gray"
        if ($Level -eq "WARN")  { $color = "Yellow" }
        if ($Level -eq "ERROR") { $color = "Red" }
        if ($Level -eq "OK")    { $color = "Green" }
        Write-Host $line -ForegroundColor $color
    }
}

# ================= -List：只列快照 =================
if ($List) {
    Write-Host "`n=== 已有快照 ($SnapDir) ===" -ForegroundColor Cyan
    $snaps = @(Get-ChildItem $SnapDir -Filter "snapshot_*.zip" -ErrorAction SilentlyContinue |
               Sort-Object LastWriteTime -Descending)
    if ($snaps.Count -eq 0) {
        Write-Host "  (无)" -ForegroundColor DarkGray
        return
    }
    foreach ($s in $snaps) {
        Write-Host ("  {0}   {1,9:N0} KB   {2}" -f `
            $s.Name, ($s.Length / 1KB), $s.LastWriteTime.ToString("yyyy-MM-dd HH:mm"))
    }
    Write-Host ("`n  合计 {0} 份，占用 {1:N1} MB`n" -f `
        $snaps.Count, (($snaps | Measure-Object -Property Length -Sum).Sum / 1MB)) -ForegroundColor Cyan
    return
}

# ================= 1. 健康检查 =================
$nodes = -1
$edges = -1
$healthOk = $false
if (Test-Path $VenvPy) {
    try {
        $raw = & $VenvPy (Join-Path $PSScriptRoot "graph_health.py") 2>&1 | Out-String
        $h = $raw | ConvertFrom-Json
        $healthOk = [bool]$h.ok
        $nodes = [int]$h.skill_nodes
        $edges = [int]$h.skill_edges
    } catch {
        Write-Log ("图谱健康检查失败: {0}" -f $_.Exception.Message) "WARN"
    }
} else {
    Write-Log ("未找到解释器 {0}，跳过健康检查" -f $VenvPy) "WARN"
}

# ================= 2. 缩水拦截 =================
$baseline = 0
if (Test-Path $StatePath) {
    try {
        $st = Get-Content $StatePath -Raw -Encoding utf8 | ConvertFrom-Json
        if ($st.last_skill_nodes) { $baseline = [int]$st.last_skill_nodes }
    } catch {
        Write-Log "state.json 解析失败，忽略基线" "WARN"
    }
}

if (-not $Force) {
    if ((Test-Path $VenvPy) -and (-not $healthOk)) {
        Write-Log "图谱无法读取（health.ok=false）——拒绝备份，避免固化损坏状态。如确认要备份请加 -Force" "ERROR"
        exit 2
    }
    if ($baseline -gt 0 -and $nodes -ge 0 -and $nodes -lt ($baseline * 0.5)) {
        Write-Log ("缩水拦截：图谱仅 {0} 节点，上次基线 {1} 节点（不足 50%）。" -f $nodes, $baseline) "ERROR"
        Write-Log "拒绝备份——当前状态很可能是损坏的。请先排查；确需备份请加 -Force" "ERROR"
        exit 2
    }
}

# ================= 3. 暂存复制 =================
if (Test-Path $TmpStage) { Remove-Item $TmpStage -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $TmpStage -Force | Out-Null

$manifest = New-Object System.Collections.ArrayList

function Copy-Tree {
    param([string]$Src, [string]$RelDest)
    if (-not (Test-Path $Src)) { return }
    $dst = Join-Path $TmpStage $RelDest
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    Copy-Item -Path (Join-Path $Src "*") -Destination $dst -Recurse -Force -ErrorAction SilentlyContinue
    $n = @(Get-ChildItem $dst -Recurse -File -ErrorAction SilentlyContinue).Count
    [void]$manifest.Add(@{ path = $RelDest; files = $n })
    Write-Log ("  收集 {0}  ({1} 文件)" -f $RelDest, $n)
}

# 3.1 知识图谱（逐文件，便于校验存在性）
$graphSrc = Join-Path $Backend "core\graphs"
$graphDst = Join-Path $TmpStage "backend\core\graphs"
New-Item -ItemType Directory -Path $graphDst -Force | Out-Null
$graphFiles = @(Get-ChildItem $graphSrc -Filter "*.yaml" -File -ErrorAction SilentlyContinue)
foreach ($f in $graphFiles) {
    Copy-Item $f.FullName $graphDst -Force
    [void]$manifest.Add(@{ path = ("backend/core/graphs/" + $f.Name); bytes = $f.Length })
}
Write-Log ("  收集 backend/core/graphs  ({0} 个 yaml)" -f $graphFiles.Count)

# 3.2 用户数据（sandboxes / backups 是临时或已有备份，跳过）
foreach ($sub in @("memory", "profiles", "pending_learning", "workspace")) {
    Copy-Tree -Src (Join-Path $Backend ("storage\" + $sub)) -RelDest ("backend\storage\" + $sub)
}

# 3.3 配置
$cfgDst = Join-Path $TmpStage "backend\config"
New-Item -ItemType Directory -Path $cfgDst -Force | Out-Null
$cfg = Join-Path $Backend "config\app_config.json"
if (Test-Path $cfg) { Copy-Item $cfg $cfgDst -Force; [void]$manifest.Add(@{ path = "backend/config/app_config.json" }) }
$envDst = Join-Path $TmpStage "backend"
New-Item -ItemType Directory -Path $envDst -Force | Out-Null
$envF = Join-Path $Backend ".env"
if (Test-Path $envF) { Copy-Item $envF $envDst -Force; [void]$manifest.Add(@{ path = "backend/.env"; note = "含密钥" }) }
# .token 是本地 API 访问令牌；不备份会导致「恢复了 .env 但前端仍连不上」
$tokenF = Join-Path $Backend ".token"
if (Test-Path $tokenF) { Copy-Item $tokenF $envDst -Force; [void]$manifest.Add(@{ path = "backend/.token"; note = "含密钥" }) }
Write-Log "  收集 backend/config + .env + .token"

# 3.4 打包环境配置
$appDataCfg = Join-Path $env:APPDATA "AgentMatrix\config"
if (Test-Path $appDataCfg) {
    Copy-Tree -Src $appDataCfg -RelDest "appdata\AgentMatrix\config"
} else {
    Write-Log "  (无 %APPDATA%\AgentMatrix\config，跳过)"
}

# 3.5 SQLite 主库（一致性备份）
#     ★ 不能直接 Copy-Item：运行时处于 WAL 模式，未 checkpoint 的数据只在
#       -wal 文件里，复制 .db 会得到残缺快照。改走 sqlite3 backup API。
$dbSrc = Join-Path $Backend "storage\agentmatrix.db"
if (Test-Path $dbSrc) {
    $dbDstDir = Join-Path $TmpStage "backend\storage"
    New-Item -ItemType Directory -Path $dbDstDir -Force | Out-Null
    $dbDst = Join-Path $dbDstDir "agentmatrix.db"
    $dbTool = Join-Path $PSScriptRoot "db_backup.py"
    if ((Test-Path $VenvPy) -and (Test-Path $dbTool)) {
        $dbOut = & $VenvPy $dbTool $dbSrc $dbDst 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            $dbBytes = (Get-Item $dbDst).Length
            Write-Log ("  SQLite agentmatrix.db ({0:N0} B)  {1}" -f $dbBytes, $dbOut.Trim())
            [void]$manifest.Add(@{ path = "backend/storage/agentmatrix.db"; bytes = $dbBytes; note = "sqlite-backup-api" })
        } else {
            Write-Log ("  [警告] SQLite 备份失败 (exit={0}): {1}" -f $LASTEXITCODE, $dbOut.Trim()) "WARN"
        }
    } else {
        Write-Log "  [警告] 缺解释器或 db_backup.py，跳过 SQLite 备份" "WARN"
    }
} else {
    Write-Log "  (无 agentmatrix.db，跳过)"
}

# ================= 4. manifest + 压缩 =================
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$meta = [ordered]@{
    created_at      = (Get-Date -Format "o")
    label           = $Label
    repo_root       = $RepoRoot
    skill_nodes     = $nodes
    skill_edges     = $edges
    baseline_nodes  = $baseline
    host            = $env:COMPUTERNAME
    items           = $manifest
}
$meta | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $TmpStage "manifest.json") -Encoding utf8

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipName = "snapshot_{0}_{1}.zip" -f $stamp, $Label
$zipPath = Join-Path $SnapDir $zipName
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

try {
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $TmpStage, $zipPath,
        [System.IO.Compression.CompressionLevel]::Optimal, $false)
} catch {
    Write-Log ("压缩失败: {0}" -f $_.Exception.Message) "ERROR"
    exit 1
}

Remove-Item $TmpStage -Recurse -Force -ErrorAction SilentlyContinue

$zipKB = (Get-Item $zipPath).Length / 1KB
Write-Log ("快照已生成: {0}  ({1:N0} KB)  图谱 {2} 节点/{3} 边" -f `
    $zipName, $zipKB, $nodes, $edges) "OK"

# ================= 5. 更新基线状态 =================
$state = [ordered]@{
    last_backup_at   = (Get-Date -Format "o")
    last_snapshot    = $zipName
    last_label       = $Label
    last_skill_nodes = $nodes
    last_skill_edges = $edges
    keep             = $Keep
}
$state | ConvertTo-Json | Set-Content $StatePath -Encoding utf8

# ================= 6. 轮转 =================
if (-not $SkipRotation) {
    $snaps = @(Get-ChildItem $SnapDir -Filter "snapshot_*.zip" -ErrorAction SilentlyContinue |
               Sort-Object LastWriteTime -Descending)
    if ($snaps.Count -gt $Keep) {
        $drop = $snaps | Select-Object -Skip $Keep
        foreach ($d in $drop) {
            Remove-Item $d.FullName -Force -ErrorAction SilentlyContinue
            Write-Log ("轮转删除旧快照: {0}" -f $d.Name)
        }
    }
    Write-Log ("当前快照 {0} 份（上限 {1}）" -f ([Math]::Min($snaps.Count, $Keep)), $Keep)
}

Write-Log "备份完成" "OK"
exit 0
