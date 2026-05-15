import asyncio
import aiohttp

async def test_deepseek_direct():
    # 这里直接测试 DeepSeek API
    api_key = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # 用户需要替换为真实的 API Key
    url = "https://api.deepseek.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    print(f"测试 URL: {url}")
    print(f"API Key 长度: {len(api_key)}")
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                status = response.status
                text = await response.text()
                
                print(f"\n状态码: {status}")
                print(f"响应内容: {text}")
                
                if status == 200:
                    print("\n✅ API 调用成功！")
                else:
                    print(f"\n❌ API 调用失败，状态码: {status}")
                    
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_deepseek_direct())
