import aiohttp
import asyncio

async def check_deepseek_usage():
    """检查 DeepSeek API 的使用情况"""
    print("=" * 80)
    print("DeepSeek API 使用情况检查")
    print("=" * 80)

    api_key = "sk-6ccaead05a2f462d97417a268139b561"

    # 方法1：尝试不同的余额查询接口
    print("\n📋 方法1: 查询余额信息")
    balance_endpoints = [
        "https://api.deepseek.com/v1/wallet/balance",
        "https://api.deepseek.com/v1/balance",
        "https://api.deepseek.com/balance",
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for endpoint in balance_endpoints:
        print(f"\n   尝试: {endpoint}")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(endpoint, headers=headers) as response:
                    print(f"   状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"   ✅ 成功: {data}")
                    else:
                        error = await response.text()
                        print(f"   ❌ 失败: {error[:100]}")
        except Exception as e:
            print(f"   ❌ 异常: {str(e)[:100]}")

    # 方法2：查询用量明细
    print("\n\n📋 方法2: 尝试查询用量记录")
    usage_endpoints = [
        "https://api.deepseek.com/v1/usage",
        "https://api.deepseek.com/usage",
    ]

    for endpoint in usage_endpoints:
        print(f"\n   尝试: {endpoint}")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(endpoint, headers=headers) as response:
                    print(f"   状态码: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"   ✅ 成功: {data}")
                    else:
                        error = await response.text()
                        print(f"   ❌ 失败: {error[:100]}")
        except Exception as e:
            print(f"   ❌ 异常: {str(e)[:100]}")

    print("\n" + "=" * 80)
    print("💡 建议:")
    print("   1. 请登录 DeepSeek 开放平台: https://platform.deepseek.com")
    print("   2. 进入 'API' -> '使用明细' 或 '消费记录' 页面")
    print("   3. 查看是否有 API 调用记录")
    print("   4. 如果没有记录，请检查:")
    print("      - API Key 是否正确")
    print("      - 是否使用了免费额度的模型")
    print("      - 账户余额是否充足")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(check_deepseek_usage())
