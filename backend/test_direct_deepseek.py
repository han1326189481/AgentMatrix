import aiohttp
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_deepseek_directly():
    print("=" * 70)
    print("直接测试 DeepSeek API")
    print("=" * 70)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"
    url = "https://api.deepseek.com/v1/chat/completions"

    messages = [
        {"role": "user", "content": "你好，请简单介绍一下你自己"}
    ]

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print(f"\n发送请求到: {url}")
    print(f"模型: deepseek-chat")
    print(f"API Key: {api_key[:15]}...{api_key[-5:]}")
    print(f"消息: {messages[0]['content']}")
    print("-" * 70)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                print(f"\n响应状态码: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print("✅ API调用成功！")
                    print(f"\n响应数据:")
                    print(f"  模型: {data.get('model', 'N/A')}")
                    print(f"  Token使用: {data.get('usage', {})}")

                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        print(f"\n回复内容:")
                        print(content)
                else:
                    error_text = await response.text()
                    print(f"❌ API调用失败")
                    print(f"错误信息: {error_text}")

    except Exception as e:
        print(f"❌ 发生异常: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_deepseek_directly())
