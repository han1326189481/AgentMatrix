@echo off
chcp 65001 >nul
title AgentMatrix - 工作流测试

echo ============================================
echo  测试 AgentMatrix 工作流
echo ============================================
echo.

cd /d "%~dp0backend"
python test_workflow.py

echo.
echo.
echo 测试完成！
pause
