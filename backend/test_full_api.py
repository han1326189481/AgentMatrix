import asyncio
import aiohttp
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_with_full_log():
    print("=" * 80)
    print("完整测试 DeepSeek API 调用")
    print("=" * 80)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"
    model_name = "deepseek-v4-flash"
    url = "https://api.deepseek.com/v1/chat/completions"

    messages = [
        {"role": "user", "content": "用50字介绍你自己"}
    ]

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print(f"\n📡 请求信息:")
    print(f"   URL: {url}")
    print(f"   模型: {model_name}")
    print(f"   API Key: {api_key[:10]}...")
    print(f"   消息: {messages[0]['content']}")
    print("-" * 80)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            print("\n⏳ 正在发送请求...")
            
            async with session.post(url, json=payload, headers=headers) as response:
                print(f"\n📤 响应状态码: {response.status}")
                
                if response.status == 200:
                    print("\n✅ API调用成功！")
                    
                    data = await response.json()
                    print("\n📋 响应详情:")
                    print(f"   模型: {data.get('model', 'N/A')}")
                    print(f"   ID: {data.get('id', 'N/A')}")
                    print(f"   对象类型: {data.get('object', 'N/A')}")
                    
                    usage = data.get('usage', {})
                    prompt_tokens = usage.get('prompt_tokens', 0)
                    completion_tokens = usage.get('completion_tokens', 0)
                    total_tokens = usage.get('total_tokens', 0)
                    
                    print(f"\n💰 Token消耗:")
                    print(f"   输入Token: {prompt_tokens}")
                    print(f"   输出Token: {completion_tokens}")
                    print(f"   总计Token: {total_tokens}")
                    
                    print(f"\n💵 费用估算:")
                    print(f"   约 ${(total_tokens / 1000000) * 0.27:.6f} (假设 $0.27/1M tokens)")
                    
                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        print(f"\n📝 回复内容:")
                        print(content)
                        
                    print(f"\n✅ 确认: 已成功调用 {model_name} 模型！")
                    print(f"✅ Token已消耗: {total_tokens} tokens")
                    
                else:
                    error_text = await response.text()
                    print(f"\n❌ API调用失败")
                    print(f"   状态码: {response.status}")
                    print(f"   错误: {error_text}")

    except Exception as e:
        print(f"\n❌ 发生异常: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_with_full_log())
