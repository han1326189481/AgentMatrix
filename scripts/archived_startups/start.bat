@echo off
chcp 65001 >nul
title AgentMatrix - 一键启动

echo ============================================
echo  AgentMatrix - 多智能体动态协同系统
echo ============================================
echo.

REM 检查是否安装了Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 检查是否安装了Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js 20+
    pause
    exit /b 1echo 
)

echo [检查通过] Python 和 Node.js 环境已就绪
echo.

REM 切换到项目根目录
cd /d "%~dp0"

REM 检查并安装后端依赖
echo [步骤 1/4] 检查后端依赖...
cd backend
if not exist "venv" (
    echo 正在安装后端依赖...
    pip install pydantic pydantic-settings fastapi uvicorn httpx python-dotenv >nul 2>&1
) else (
    echo 后端依赖已存在
)
cd ..

REM 检查并安装前端依赖
echo [步骤 2/4] 检查前端依赖...
cd frontend
if not exist "node_modules" (
    echo 正在安装前端依赖...
    call npm install >nul 2>&1
) else (
    echo 前端依赖已存在
)
cd ..

echo.
echo [步骤 3/4] 启动后端服务...
cd backend
start "AgentMatrix Backend" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

timeout /t 2 /nobreak >nul

echo [步骤 4/4] 启动前端服务...
cd frontend
start "AgentMatrix Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ============================================
echo  系统启动完成！
echo ============================================
echo.
echo  访问地址：
echo   - 前端界面：http://localhost:3000
echo   - 后端API：http://localhost:8000
echo   - API文档：http://localhost:8000/docs
echo.
echo  按任意键关闭此窗口（服务会继续运行）...
pause >nul
