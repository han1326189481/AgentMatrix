import asyncio
import httpx

async def test_workflow_api():
    print("测试工作流API...")
    print("=" * 60)
    
    tasks = [
        "帮我写一份简单的活动策划",
        "什么是人工智能？",
        "帮我设计一个校园运动会方案"
    ]
    
    for task in tasks:
        print(f"\n任务: {task}")
        print("-" * 40)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/workflow/execute",
                    json={"user_input": task}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"执行方式: {'本地执行' if data.get('executed_locally') else '云端执行'}")
                    print(f"复杂度评分: {data.get('complexity_score', 0.0):.2f}")
                    print(f"总耗时: {data.get('total_duration_seconds', 0.0):.2f}秒")
                    print(f"步骤数: {len(data.get('steps', []))}")
                    
                    print("\n各步骤详情:")
                    for step in data.get('steps', []):
                        model = step.get('metadata', {}).get('model_used', 'N/A')
                        status = "✅" if step.get('success') else "❌"
                        print(f"  {status} {step.get('agent_name')}: 模型={model}, 耗时={step.get('duration_seconds', 0.0):.2f}s")
                    
                    final_result = data.get('final_result', '')
                    print(f"\n最终结果预览 ({len(final_result)} 字符):")
                    print(final_result[:500] + "..." if len(final_result) > 500 else final_result)
                else:
                    print(f"❌ 请求失败: {response.status_code}")
                    print(f"错误信息: {response.text}")
                    
        except Exception as e:
            print(f"❌ 请求异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_workflow_api())