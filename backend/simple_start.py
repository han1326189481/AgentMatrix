#!/usr/bin/env python3
"""
最简单的启动脚本
"""
import sys
import os

print("=" * 60)
print("🚀 AgentMatrix 启动器")
print("=" * 60)

# 检查当前目录
print(f"\n📁 工作目录: {os.getcwd()}")

# 检查必要的文件
required_files = ['app/main.py', '.env', 'frontend/index.html']
for file in required_files:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} - 不存在")
        sys.exit(1)

# 尝试导入
print("\n📦 检查依赖...")
try:
    import fastapi
    import uvicorn
    print("   ✅ FastAPI 和 Uvicorn 可用")
except ImportError as e:
    print(f"   ❌ 缺少依赖: {e}")
    print("\n💡 请先安装依赖:")
    print("   pip install fastapi uvicorn pydantic python-dotenv httpx")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 准备就绪！正在启动服务...")
print("=" * 60)
print("\n🌐 服务地址: http://localhost:8000")
print("📚 API文档: http://localhost:8000/docs")
print("⏹️  按 Ctrl+C 停止服务\n")

try:
    os.system(f'"{sys.executable}" -m uvicorn app.main:app --host 0.0.0.0 --port 8000')
except KeyboardInterrupt:
    print("\n\n👋 服务已停止")
except Exception as e:
    print(f"\n❌ 启动失败: {e}")
    print("\n💡 尝试直接运行:")
    print('   python app/main.py')
