"""AgentMatrix 后端 PyInstaller 打包入口点

此文件仅用于 PyInstaller 打包，不用于开发模式。
开发模式请使用: python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
"""
import uvicorn
from app.main import socket_app

if __name__ == "__main__":
    uvicorn.run(socket_app, host="127.0.0.1", port=8000, log_level="info")
