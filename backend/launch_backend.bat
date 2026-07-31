@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo Starting AgentMatrix Backend...
echo ========================================================
echo.
python -m pip install pydantic pydantic-settings fastapi uvicorn httpx python-dotenv python-socketio sqlalchemy
echo.
echo ========================================================
echo Launching server...
echo ========================================================
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
