$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Testing AgentMatrix Workflow" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$projectPath = Get-Location
Set-Location (Join-Path $projectPath "backend")

python test_workflow.py

Write-Host ""
Write-Host ""
Write-Host "Test completed!" -ForegroundColor Green
Read-Host "Press any key to exit..."