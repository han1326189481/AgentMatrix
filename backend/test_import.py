#!/usr/bin/env python3
"""
测试能否正常导入
"""
import sys
import os

print("=" * 60)
print("🔍 导入测试")
print("=" * 60)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print(f"\n工作目录: {os.getcwd()}")
print(f"Python路径: {sys.path[0]}")
print()

try:
    print("1. 测试导入 app.config...")
    from app.config import settings
    print(f"   ✅ 成功 - 应用名称: {settings.app_name}")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n2. 测试导入 app.main...")
    from app.main import app
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n3. 测试导入 agents...")
    from agents.knowledge.agent import KnowledgeAgent
    print("   ✅ 成功")
except Exception as e:
    print(f"   ❌ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 所有导入测试通过！")
print("=" * 60)
print("\n🚀 现在可以启动服务了！")
print("   运行: python app/main.py")
