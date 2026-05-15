#!/usr/bin/env python3
import asyncio
import aiohttp
import sys

async def test_deepseek(api_key):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "你好"}
        ],
        "temperature": 0.7,
        "max_tokens": 50
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                status = response.status
                text = await response.text()

                if status == 200:
                    print("✅ API Key 有效！")
                    return True
                else:
                    print(f"❌ API 调用失败，状态码: {status}")
                    print(f"响应: {text}")
                    return False

    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_api.py <api_key>")
        sys.exit(1)

    api_key = sys.argv[1]
    result = asyncio.run(test_deepseek(api_key))
    sys.exit(0 if result else 1)
