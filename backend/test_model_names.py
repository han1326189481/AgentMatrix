import aiohttp
import asyncio

async def test_model_comparison():
    print("=" * 70)
    print("测试不同的 DeepSeek 模型")
    print("=" * 70)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"
    url = "https://api.deepseek.com/v1/chat/completions"

    messages = [
        {"role": "user", "content": "请用一句话介绍自己"}
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    models_to_test = [
        ("deepseek-chat", "标准对话模型"),
        ("deepseek-coder", "代码模型"),
        ("deepseek-r1-distill", "R1蒸馏模型（配置的模型）")
    ]

    for model_name, description in models_to_test:
        print(f"\n{'='*70}")
        print(f"测试模型: {model_name} ({description})")
        print("-" * 70)

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 50
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        usage = data.get('usage', {})
                        print(f"✅ 成功!")
                        print(f"   Token使用: {usage}")
                        choices = data.get('choices', [])
                        if choices:
                            content = choices[0].get('message', {}).get('content', '')
                            print(f"   回复: {content[:100]}")
                    else:
                        error_text = await response.text()
                        print(f"❌ 失败 (状态码: {response.status})")
                        print(f"   错误: {error_text[:200]}")

        except Exception as e:
            print(f"❌ 异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_model_comparison())
