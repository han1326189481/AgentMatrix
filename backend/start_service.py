#!/usr/bin/env python3
"""
启动 AgentMatrix 后端服务的脚本
"""
import subprocess
import sys
import time
import socket

def check_port(host, port):
    """检查端口是否被占用"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((host, port))
        s.close()
        return True
    except:
        return False

def main():
    print("=" * 60)
    print("🚀 启动 AgentMatrix 后端服务")
    print("=" * 60)
    
    # 检查 8000 端口
    if check_port('127.0.0.1', 8000):
        print("⚠️  警告: 端口 8000 已被占用")
        print("   请先停止占用该端口的程序")
        return
    
    # 检查必要的包
    try:
        import uvicorn
        import fastapi
        print("✅ 依赖检查通过")
    except ImportError as e:
        print(f"❌ 依赖缺失: {e}")
        print("   请安装依赖: pip install -r requirements.txt")
        return
    
    # 启动服务
    print("\n📦 正在启动服务...")
    print("📊 服务地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("⏹️  按 Ctrl+C 停止服务")
    print("=" * 60 + "\n")
    
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000",
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")

if __name__ == "__main__":
    main()
