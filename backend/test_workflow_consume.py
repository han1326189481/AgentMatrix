import asyncio
import httpx

async def test_workflow_with_clear_cache():
    print("=" * 80)
    print("测试工作流 API - 确保产生真实消耗")
    print("=" * 80)

    # 首先清除缓存
    print("\n🔄 第一步：清除缓存")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("http://localhost:8000/api/v1/workflow/cache/clear")
        print(f"   缓存清除: {response.status_code}")

    # 然后执行复杂任务
    print("\n🔄 第二步：执行复杂任务（复杂度 >= 0.65）")
    task = "帮我设计一个详细的校园运动会活动方案，包含完整的流程安排、预算规划、人员分工和时间线"
    
    print(f"   任务: {task[:50]}...")
    
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            "http://localhost:8000/api/v1/workflow/execute",
            json={"user_input": task}
        )

        if response.status_code == 200:
            data = response.json()
            
            print("\n✅ 请求成功！")
            print(f"\n📊 执行结果:")
            print(f"   复杂度评分: {data.get('complexity_score', 0.0):.2f}")
            print(f"   执行方式: {'云端执行' if not data.get('executed_locally', True) else '本地执行'}")
            print(f"   耗时: {data.get('total_duration_seconds', 0.0):.2f}秒")
            
            # 检查步骤中的模型使用
            print(f"\n📝 各步骤详情:")
            for step in data.get('steps', []):
                model = step.get('metadata', {}).get('model_used', 'N/A')
                agent_name = step.get('agent_name', 'N/A')
                print(f"   - {agent_name}: 模型={model}")
            
            print(f"\n💰 请刷新您的 DeepSeek 平台页面查看最新消耗！")
            print(f"   此请求应该会产生约 2000+ tokens 的消耗")
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            print(f"   错误: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_workflow_with_clear_cache())
