#!/usr/bin/env python3
"""
直接运行 app.main
"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("🚀 AgentMatrix 直接启动")
print("=" * 60)

try:
    from app.main import app
    import uvicorn
    
    print("\n✅ 导入成功！")
    print("\n🌐 服务地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("⏹️  按 Ctrl+C 停止服务\n")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
except Exception as e:
    print(f"\n❌ 启动失败: {type(e).__name__}: {e}")
    import traceback
    print("\n详细错误:")
    traceback.print_exc()
    print("\n" + "=" * 60)
