import asyncio
import aiohttp

async def verify_api_key():
    print("=" * 80)
    print("验证 DeepSeek API Key 是否正确使用")
    print("=" * 80)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"
    url = "https://api.deepseek.com/v1/chat/completions"

    print(f"\n🔑 API Key: {api_key}")
    print(f"🔗 API URL: {url}")
    print("\n" + "=" * 80)

    # 测试1：使用 deepseek-chat 模型
    print("\n📋 测试1: deepseek-chat 模型")
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 10
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 成功")
                    print(f"   模型: {data.get('model', 'N/A')}")
                    print(f"   Token消耗: {data.get('usage', {}).get('total_tokens', 0)}")
                else:
                    error = await response.text()
                    print(f"   ❌ 失败: {response.status} - {error}")
    except Exception as e:
        print(f"   ❌ 异常: {str(e)}")

    # 测试2：使用 deepseek-v4-flash 模型
    print("\n📋 测试2: deepseek-v4-flash 模型")
    payload = {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 10
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 成功")
                    print(f"   模型: {data.get('model', 'N/A')}")
                    print(f"   Token消耗: {data.get('usage', {}).get('total_tokens', 0)}")
                else:
                    error = await response.text()
                    print(f"   ❌ 失败: {response.status} - {error}")
    except Exception as e:
        print(f"   ❌ 异常: {str(e)}")

    # 测试3：查询账户余额
    print("\n📋 测试3: 查询账户余额")
    balance_url = "https://api.deepseek.com/v1/wallet/balance"
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(balance_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"   ✅ 查询成功")
                    print(f"   余额信息: {data}")
                else:
                    error = await response.text()
                    print(f"   ❌ 查询失败: {response.status} - {error}")
                    print(f"   可能原因: API Key无效或无权访问")
    except Exception as e:
        print(f"   ❌ 异常: {str(e)}")

    print("\n" + "=" * 80)
    print("💡 建议:")
    print("   1. 检查API Key是否正确")
    print("   2. 确认API Key是否属于您的账户")
    print("   3. 检查DeepSeek平台的消费记录")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(verify_api_key())
