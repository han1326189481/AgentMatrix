@echo off
chcp 65001 >nul
title AgentMatrix - 停止服务

echo ============================================
echo  正在停止 AgentMatrix 服务...
echo ============================================

REM 停止后端进程
taskkill /F /IM python.exe /FI "WINDOWTITLE eq AgentMatrix Backend*" >nul 2>&1
if errorlevel 1 (
    echo [提示] 未找到后端进程或已停止
) else (
    echo [完成] 后端服务已停止
)

REM 停止前端进程
taskkill /F /IM node.exe /FI "WINDOWTITLE eq AgentMatrix Frontend*" >nul 2>&1
if errorlevel 1 (
    echo [提示] 未找到前端进程或已停止
) else (
    echo [完成] 前端服务已停止
)

taskkill /F /IM cmd.exe /FI "WINDOWTITLE eq AgentMatrix Backend*" >nul 2>&1
taskkill /F /IM cmd.exe /FI "WINDOWTITLE eq AgentMatrix Frontend*" >nul 2>&1

echo.
echo 所有服务已停止
echo.
pause
