import asyncio
import aiohttp
import json

async def test_deepseek_v4_flash():
    print("=" * 80)
    print("测试 deepseek-v4-flash 模型")
    print("=" * 80)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"
    url = "https://api.deepseek.com/v1/chat/completions"

    messages = [
        {"role": "user", "content": "用100字介绍你自己"}
    ]

    payload = {
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 200
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print(f"\n发送请求到: {url}")
    print(f"使用模型: deepseek-v4-flash")
    print(f"API Key: {api_key[:15]}...")
    print("-" * 80)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                print(f"\n响应状态码: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print("\n✅ API调用成功！")

                    print("\n响应数据:")
                    print(f"  模型: {data.get('model', 'N/A')}")

                    usage = data.get('usage', {})
                    print(f"\n💰 Token消耗:")
                    print(f"  prompt: {usage.get('prompt_tokens', 0)}")
                    print(f"  completion: {usage.get('completion_tokens', 0)}")
                    print(f"  total: {usage.get('total_tokens', 0)}")

                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        print(f"\n回复内容:")
                        print(content)
                else:
                    error_text = await response.text()
                    print(f"\n❌ 错误: {response.status}")
                    print(error_text)
    except Exception as e:
        print(f"\n❌ 异常: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_deepseek_v4_flash())
