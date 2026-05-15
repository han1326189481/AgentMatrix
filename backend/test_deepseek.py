import asyncio
import aiohttp

async def test_deepseek():
    api_key = input("请输入你的 DeepSeek API Key: ").strip()

    if not api_key:
        print("API Key 不能为空！")
        return

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "你好，请简单介绍一下你自己"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }

    print(f"\n测试 DeepSeek API...")
    print(f"URL: {url}")
    print(f"Model: deepseek-chat")
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    print("\n正在请求...\n")

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                status = response.status
                text = await response.text()

                print(f"状态码: {status}")
                print(f"响应: {text[:500]}")

                if status == 200:
                    print("\n✅ API 调用成功！")
                    data = await response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    print(f"\n回复内容:\n{content}")
                elif status == 401:
                    print("\n❌ 认证失败！请检查 API Key 是否正确")
                elif status == 400:
                    print("\n❌ 请求格式错误！")
                else:
                    print(f"\n❌ 请求失败，状态码: {status}")

    except Exception as e:
        print(f"\n❌ 连接失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_deepseek())
