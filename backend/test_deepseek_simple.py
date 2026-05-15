#!/usr/bin/env python3
import asyncio
import aiohttp

async def main():
    print("="*50)
    print("DeepSeek API 连接测试工具")
    print("="*50)
    
    api_key = input("请输入你的 DeepSeek API Key: ").strip()
    
    if not api_key:
        print("❌ API Key 不能为空！")
        return
    
    print("\n正在测试 DeepSeek API...")
    
    # 测试多个可能的URL
    urls = [
        "https://api.deepseek.com/v1/chat/completions",
        "https://api.deepseek.com/chat/completions",
        "https://api.deepseek.com/openai/v1/chat/completions"
    ]
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "max_tokens": 50
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    for url in urls:
        print(f"\n📡 测试 URL: {url}")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    status = response.status
                    text = await response.text()
                    
                    print(f"   状态码: {status}")
                    
                    if status == 200:
                        print("   ✅ 成功！")
                        try:
                            import json
                            data = json.loads(text)
                            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                            print(f"   响应: {content[:50]}...")
                        except:
                            print(f"   响应: {text[:100]}...")
                        return
                    elif status == 401:
                        print("   ❌ 认证失败 - API Key 无效")
                    elif status == 404:
                        print("   ❌ 路径不存在")
                    elif status == 400:
                        print(f"   ❌ 请求错误: {text[:100]}")
                    else:
                        print(f"   ❌ 未知错误: {text[:100]}")
                        
        except Exception as e:
            print(f"   ❌ 连接失败: {e}")
    
    print("\n❌ 所有URL测试失败，请检查API Key和网络连接")

if __name__ == "__main__":
    asyncio.run(main())
