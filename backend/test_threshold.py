import asyncio
import httpx

async def test_threshold():
    print("=" * 70)
    print("测试复杂度阈值决策逻辑")
    print("阈值: 0.65")
    print("=" * 70)

    test_cases = [
        ("帮我写一份情书", "简单任务，应该本地执行"),
        ("帮我设计一个校园运动会活动方案，包含流程、预算、时间线、人员分工", "复杂任务，应该云端执行"),
        ("写一份详细的项目计划书，包含目标、时间线、预算和人员分工", "复杂任务，应该云端执行"),
        ("什么是人工智能？", "简单任务，应该本地执行"),
    ]

    for task, expected in test_cases:
        print(f"\n{'='*70}")
        print(f"任务: {task}")
        print(f"预期: {expected}")
        print("-" * 70)

        async with httpx.AsyncClient(timeout=180) as client:
            try:
                response = await client.post(
                    "http://localhost:8000/api/v1/workflow/execute",
                    json={"user_input": task}
                )

                if response.status_code == 200:
                    data = response.json()
                    complexity = data.get('complexity_score', 0.0)
                    is_local = data.get('executed_locally', True)

                    print(f"复杂度评分: {complexity:.2f}")
                    print(f"执行方式: {'本地执行' if is_local else '云端执行（DeepSeek）'}")

                    if complexity >= 0.65:
                        if not is_local:
                            print("✅ 正确：复杂度 >= 0.65，使用云端模型")
                        else:
                            print("❌ 错误：复杂度 >= 0.65，但使用了本地模型")
                    else:
                        if is_local:
                            print("✅ 正确：复杂度 < 0.65，使用本地模型")
                        else:
                            print("⚠️ 注意：复杂度 < 0.65，但使用了云端模型")
                else:
                    print(f"请求失败: {response.status_code}")
            except Exception as e:
                print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_threshold())
