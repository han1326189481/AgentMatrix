#!/usr/bin/env python3
"""
测试 AgentMatrix 环境是否配置正确
"""
import sys
import os

print("=" * 60)
print("🔍 AgentMatrix 环境检查")
print("=" * 60)

# 检查 Python 版本
print(f"\n1. Python 版本: {sys.version}")

# 检查必要的包
required_packages = [
    'uvicorn',
    'fastapi',
    'pydantic',
    'httpx',
    'aiofiles'
]

print("\n2. 检查依赖包:")
all_ok = True
for package in required_packages:
    try:
        __import__(package)
        print(f"   ✅ {package}")
    except ImportError:
        print(f"   ❌ {package} - 未安装")
        all_ok = False

# 检查 .env 文件
print("\n3. 检查配置文件:")
if os.path.exists('.env'):
    print("   ✅ .env 文件存在")
    with open('.env', 'r', encoding='utf-8') as f:
        content = f.read()
    print("      配置项:")
    for line in content.split('\n'):
        if line.strip() and not line.startswith('#'):
            key = line.split('=')[0]
            if 'KEY' in key or 'key' in key:
                print(f"         {key}=***")
            else:
                print(f"         {line}")
else:
    print("   ❌ .env 文件不存在")
    all_ok = False

# 检查 Ollama 配置
print("\n4. Ollama 配置:")
from app.config import settings
print(f"   默认端口: {settings.ollama_host}")

print("\n" + "=" * 60)
if all_ok:
    print("✅ 环境检查通过！可以启动服务")
    print("\n🚀 启动命令:")
    print("   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
else:
    print("❌ 环境检查失败，请检查上述错误")
print("=" * 60)
