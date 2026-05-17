import asyncio
import httpx

async def test_with_deepseek():
    print("=" * 70)
    print("测试 DeepSeek API Key 是否被正确使用")
    print("=" * 70)

    user_input = "帮我写一份详细的项目计划书，包含目标、时间线、预算和人员分工"
    print(f"\n发送请求: {user_input}")
    print("（这是一个复杂任务，应该会调用云端模型）\n")

    async with httpx.AsyncClient(timeout=180) as client:
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/workflow/execute",
                json={"user_input": user_input}
            )

            if response.status_code == 200:
                data = response.json()
                print(f"状态码: 200 OK")
                print(f"执行方式: {'本地执行' if data.get('executed_locally') else '云端执行（使用 DeepSeek）'}")
                print(f"复杂度评分: {data.get('complexity_score', 0.0):.2f}")
                print(f"总耗时: {data.get('total_duration_seconds', 0.0):.2f}秒")

                print("\n" + "=" * 70)
                print("最终结果:")
                print("=" * 70)
                result = data.get('final_result', '')
                if len(result) > 1500:
                    print(result[:1500] + "\n...")
                else:
                    print(result)

                if not data.get('executed_locally'):
                    print("\n" + "=" * 70)
                    print("✅ 成功使用云端模型（DeepSeek）")
                    print("=" * 70)
                else:
                    print("\n" + "=" * 70)
                    print("⚠️ 使用了本地模型")
                    print("=" * 70)
            else:
                print(f"请求失败: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_with_deepseek())
