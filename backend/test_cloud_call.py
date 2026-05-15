"""
测试云服务调用是否正常工作
"""
import asyncio
import sys
sys.path.insert(0, '.')

from core.llm.client import get_llm_client
from app.config import settings

async def test_cloud_call():
    print("=" * 60)
    print("🧪 测试云服务调用")
    print("=" * 60)
    
    # 获取LLM客户端
    client = get_llm_client()
    
    # 设置API Key（从配置读取）
    api_key = settings.deepseek_api_key
    if not api_key:
        print("❌ API Key 未设置，请先在 .env 文件中配置")
        return
    
    client.deepseek_api_key = api_key
    print(f"✅ API Key 已设置: {api_key[:10]}...")
    
    # 测试云服务调用
    print("\n🌐 正在调用 DeepSeek 云服务...")
    try:
        result = await client.generate_cloud("Hello, this is a test.")
        if "Error" in result:
            print(f"❌ 云服务调用失败: {result}")
        else:
            print(f"✅ 云服务调用成功！")
            print(f"📝 返回结果: {result[:100]}...")
            print("\n🎉 这证明云服务正在被正确调用！")
            print("💡 您的 API Key 应该会产生消费了")
    except Exception as e:
        print(f"❌ 调用异常: {str(e)}")
    
    # 测试本地调用
    print("\n" + "=" * 60)
    print("🖥️ 测试本地模型调用")
    print("=" * 60)
    try:
        result = await client.generate_local("Hello, this is a test.", model="qwen2.5:1.5b")
        if "Error" in result:
            print(f"⚠️  本地模型调用失败: {result}")
            print("   这可能是因为 Ollama 服务未启动")
        else:
            print(f"✅ 本地模型调用成功！")
            print(f"📝 返回结果: {result[:100]}...")
    except Exception as e:
        print(f"❌ 调用异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_cloud_call())
