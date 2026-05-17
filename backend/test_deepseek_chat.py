import asyncio
import httpx

async def test_deepseek_chat():
    print("=" * 80)
    print("测试 deepseek-chat 模型（付费模型）")
    print("=" * 80)

    # 首先清除缓存
    print("\n🔄 清除缓存...")
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post("http://localhost:8000/api/v1/workflow/cache/clear")
        print("   ✅ 缓存已清除")

    # 执行复杂任务
    print("\n🔄 执行复杂任务（应该使用 deepseek-chat）...")
    task = "帮我写一份详细的项目计划书，包含目标、时间线、预算和人员分工"
    
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
            print(f"   执行方式: {'云端执行（DeepSeek）' if not data.get('executed_locally', True) else '本地执行'}")
            print(f"   耗时: {data.get('total_duration_seconds', 0.0):.2f}秒")
            
            # 检查步骤中的模型使用
            print(f"\n📝 各步骤详情:")
            for step in data.get('steps', []):
                model = step.get('metadata', {}).get('model_used', 'N/A')
                agent_name = step.get('agent_name', 'N/A')
                print(f"   - {agent_name}: 模型={model}")
            
            # 检查 Result Agent 的模型
            result_step = [s for s in data.get('steps', []) if s.get('agent_id') == 'result']
            if result_step:
                model = result_step[0].get('metadata', {}).get('model_used', 'N/A')
                print(f"\n🎯 Result Agent 使用模型: {model}")
                
                if 'deepseek-chat' in model:
                    print("   ✅ 现在使用的是 deepseek-chat（付费模型）！")
                    print("   💰 请刷新 DeepSeek 平台查看消费记录！")
                else:
                    print(f"   ⚠️ 当前模型: {model}")
        else:
            print(f"\n❌ 请求失败: {response.status_code}")

if __name__ == "__main__":
    asyncio.run(test_deepseek_chat())
