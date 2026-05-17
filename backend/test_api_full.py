import aiohttp
import asyncio

async def test_api_with_full_response():
    print("=" * 70)
    print("完整测试 DeepSeek API 调用和 Token 消耗")
    print("=" * 70)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"
    url = "https://api.deepseek.com/v1/chat/completions"

    messages = [
        {"role": "user", "content": "请用100字介绍自己"}
    ]

    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 200
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("\n发送请求...")
    print(f"模型: deepseek-chat")
    print(f"API Key: {api_key[:15]}...{api_key[-5:]}")
    print("-" * 70)

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                print(f"\n响应状态码: {response.status}")

                if response.status == 200:
                    data = await response.json()
                    print("\n✅ API调用成功！")

                    # 打印完整响应
                    print("\n完整响应数据:")
                    print(f"  模型: {data.get('model', 'N/A')}")
                    print(f"  ID: {data.get('id', 'N/A')}")
                    print(f"  Object: {data.get('object', 'N/A')}")
                    print(f"  Created: {data.get('created', 'N/A')}")

                    # 打印 Token 使用情况
                    usage = data.get('usage', {})
                    print("\n📊 Token 使用情况:")
                    print(f"  prompt_tokens: {usage.get('prompt_tokens', 0)}")
                    print(f"  completion_tokens: {usage.get('completion_tokens', 0)}")
                    print(f"  total_tokens: {usage.get('total_tokens', 0)}")

                    if usage:
                        print("\n💰 计费信息:")
                        print(f"  总消耗 Token: {usage.get('total_tokens', 0)}")
                        print(f"  预计费用: ${(usage.get('total_tokens', 0) / 1000000) * 0.27:.6f} (假设 $0.27/1M tokens)")

                    # 打印回复
                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        print(f"\n回复内容 ({len(content)} 字符):")
                        print(content)
                else:
                    error_text = await response.text()
                    print(f"\n❌ API调用失败")
                    print(f"错误信息: {error_text}")

    except Exception as e:
        print(f"\n❌ 发生异常: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_with_full_response())
