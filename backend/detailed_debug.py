import aiohttp
import asyncio
import json

async def detailed_api_test():
    print("=" * 80)
    print("DeepSeek API 详细调试测试")
    print("=" * 80)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"
    url = "https://api.deepseek.com/v1/chat/completions"

    # 测试消息
    messages = [
        {"role": "user", "content": "你好，请用一句话介绍自己"}
    ]

    # 完整 payload
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 50
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    print("\n📤 发送请求:")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps({k: v[:20] + '...' if k == 'Authorization' else v for k, v in headers.items()}, indent=2)}")
    print(f"Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    print("\n⏳ 等待响应...")
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                print(f"\n📥 收到响应:")
                print(f"状态码: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    print("\n✅ API调用成功！")
                    print("\n完整响应数据:")
                    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
                    
                    # 解析关键信息
                    print("\n📊 关键信息:")
                    print(f"  模型: {data.get('model', 'N/A')}")
                    print(f"  ID: {data.get('id', 'N/A')}")
                    
                    usage = data.get('usage', {})
                    print(f"\n💰 Token 消耗:")
                    print(f"  prompt_tokens: {usage.get('prompt_tokens', 0)}")
                    print(f"  completion_tokens: {usage.get('completion_tokens', 0)}")
                    print(f"  total_tokens: {usage.get('total_tokens', 0)}")
                    
                    choices = data.get('choices', [])
                    if choices:
                        content = choices[0].get('message', {}).get('content', '')
                        print(f"\n📝 回复内容:")
                        print(content)
                    
                    print("\n" + "=" * 80)
                    print("✅ 测试完成！")
                    print("=" * 80)
                    print("\n💡 如果以上显示有 token 消耗，但 DeepSeek 平台没有消费记录，可能原因：")
                    print("   1. API Key 不属于您的账户")
                    print("   2. 该 API Key 没有绑定到您的账户")
                    print("   3. DeepSeek 平台的消费记录有延迟")
                    print("   4. 您使用的是其他渠道的 API Key（如代理、第三方平台）")
                else:
                    error_text = await response.text()
                    print(f"\n❌ API调用失败:")
                    print(f"状态码: {response.status}")
                    print(f"错误信息: {error_text}")

    except Exception as e:
        print(f"\n❌ 发生异常:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(detailed_api_test())
