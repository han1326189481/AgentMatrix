import asyncio
from core.llm.client import get_llm_client

async def test_llm():
    print("=== 测试 LLM 调用 ===")
    
    llm_client = get_llm_client()
    
    # 测试本地模型
    print("\n--- 测试本地模型 (phi4-mini:3.8b) ---")
    try:
        response = await llm_client.generate_local("帮我写一段关于人工智能的介绍", model="phi4-mini:3.8b")
        print(f"响应长度: {len(response)}")
        print(f"响应内容: {response[:500]}")
        if len(response) < 50:
            print(f"警告: 响应过短！完整响应: {response}")
    except Exception as e:
        print(f"本地模型调用失败: {e}")
    
    # 测试另一个本地模型
    print("\n--- 测试本地模型 (qwen2.5:1.5b) ---")
    try:
        response = await llm_client.generate_local("帮我写一段关于人工智能的介绍", model="qwen2.5:1.5b")
        print(f"响应长度: {len(response)}")
        print(f"响应内容: {response[:500]}")
        if len(response) < 50:
            print(f"警告: 响应过短！完整响应: {response}")
    except Exception as e:
        print(f"qwen2.5模型调用失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm())
