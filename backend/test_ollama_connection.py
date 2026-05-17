import asyncio
import httpx

async def test_ollama():
    print("测试 Ollama 连接...")
    
    # 测试默认端口
    ports = ["11434", "11435"]
    
    for port in ports:
        url = f"http://localhost:{port}/api/tags"
        print(f"\n测试: {url}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ 连接成功!")
                    print(f"  模型列表: {[m['name'] for m in data.get('models', [])]}")
                else:
                    print(f"❌ 状态码: {response.status_code}")
        except Exception as e:
            print(f"❌ 连接失败: {str(e)}")
    
    # 测试生成
    print("\n测试生成能力...")
    url = "http://localhost:11435/api/generate"
    payload = {
        "model": "qwen2.5:1.5b",
        "prompt": "你好，简单介绍一下你自己。",
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 生成成功!")
                print(f"  响应: {data.get('response', '')[:100]}...")
            else:
                print(f"❌ 状态码: {response.status_code}")
                print(f"  错误: {await response.text()}")
    except Exception as e:
        print(f"❌ 生成失败: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_ollama())