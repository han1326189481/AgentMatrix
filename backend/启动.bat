@echo off
chcp 65001 >nul
echo ============================================================
echo   AgentMatrix 启动器
echo ============================================================
echo.
echo [1/3] 检查环境...
python --version
if errorlevel 1 (
    echo ❌ Python 未安装或不在PATH中
    pause
    exit /b 1
)
echo ✅ Python 检查通过
echo.

echo [2/3] 启动服务...
echo.
echo ============================================================
echo   服务地址: http://localhost:8000
echo   API文档: http://localhost:8000/docs
echo   按 Ctrl+C 停止服务
echo ============================================================
echo.

python app/main.py

if errorlevel 1 (
    echo.
    echo ❌ 启动失败！
    echo.
    echo 尝试其他方式:
    echo   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    echo.
)
pause
