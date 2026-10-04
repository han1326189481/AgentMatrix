<#
.SYNOPSIS
    注册 / 卸载 AgentMatrix 每日备份的 Windows 计划任务

.DESCRIPTION
    把 scripts\backup.ps1 注册成 Windows 计划任务，**脱离 WorkBuddy 独立运行**，
    这样即使不开 WorkBuddy，运行时数据（知识图谱 / SQLite / 用户数据）每天仍有快照。

    ⚠ 需要以**管理员身份**运行 PowerShell（Register-ScheduledTask 的系统限制）。

    用法:
      .\scripts\install_backup_task.ps1                # 注册：每天 21:30
      .\scripts\install_backup_task.ps1 -Time 09:00    # 自定义时间
      .\scripts\install_backup_task.ps1 -Uninstall     # 卸载

    说明:
      - 任务名: AgentMatrix-DailyBackup
      - 以当前用户身份、仅在该用户登录时运行（不存密码，最安全）
      - 可选：注册后关机错过的时间点，开机时补跑（StartWhenAvailable）
      - 运行日志: D:\AgentMatrix_backups\logs\backup-YYYY-MM.log

    退出码: 0 成功 / 1 失败
#>
[CmdletBinding()]
param(
    [string]$Time = "21:30",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "AgentMatrix-DailyBackup"

# ---------- 管理员权限校验 ----------
$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[错误] 需要管理员权限。" -ForegroundColor Red
    Write-Host "       请右键「Windows PowerShell」→ 以管理员身份运行，再执行本脚本。" -ForegroundColor Yellow
    exit 1
}

# ---------- 卸载 ----------
if ($Uninstall) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "[OK] 已卸载计划任务: $TaskName" -ForegroundColor Green
    } else {
        Write-Host "计划任务不存在: $TaskName" -ForegroundColor Yellow
    }
    exit 0
}

# ---------- 定位备份脚本 ----------
$RepoRoot     = Split-Path -Parent $PSScriptRoot
$BackupScript = Join-Path $RepoRoot "scripts\backup.ps1"
if (-not (Test-Path $BackupScript)) {
    Write-Host "[错误] 找不到 $BackupScript" -ForegroundColor Red
    exit 1
}

try {
    $atTime = [datetime]::ParseExact($Time, "HH:mm", $null)
} catch {
    Write-Host "[错误] 时间格式应为 HH:mm，例如 21:30（收到: $Time）" -ForegroundColor Red
    exit 1
}

# ---------- 注册 ----------
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$BackupScript`" -Label scheduled -Quiet"

$trigger = New-ScheduledTaskTrigger -Daily -At $atTime

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

$runAs = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $runAs `
    -Description "AgentMatrix 运行时数据每日备份（知识图谱 / SQLite / 用户数据）" `
    -Force | Out-Null

Write-Host "[OK] 已注册计划任务: $TaskName   每天 $Time" -ForegroundColor Green
Write-Host "     查看状态: Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo" -ForegroundColor Gray
Write-Host "     立即试跑: Start-ScheduledTask -TaskName $TaskName" -ForegroundColor Gray
Write-Host "     卸载:     .\scripts\install_backup_task.ps1 -Uninstall" -ForegroundColor Gray
exit 0
