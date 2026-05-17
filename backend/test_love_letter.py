import asyncio
import httpx
import json

async def test_love_letter():
    print("测试写情书功能...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "http://localhost:8000/api/v1/workflow/execute",
            json={"user_input": "帮我给刘晓丹写一份情书"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"执行方式: {'本地执行' if data.get('executed_locally') else '云端执行'}")
            print(f"复杂度评分: {data.get('complexity_score', 0.0):.2f}")
            print(f"总耗时: {data.get('total_duration_seconds', 0.0):.2f}秒")
            
            print("\n各步骤详情:")
            for step in data.get('steps', []):
                model = step.get('metadata', {}).get('model_used', 'N/A')
                status = "✅" if step.get('success') else "❌"
                print(f"  {status} {step.get('agent_name')}: 模型={model}, 耗时={step.get('duration_seconds', 0.0):.2f}s")
            
            print("\nWriter Agent 输出:")
            writer_step = next((s for s in data.get('steps', []) if s.get('agent_id') == 'writer'), None)
            if writer_step:
                print(f"  输出长度: {len(writer_step.get('output', ''))}")
                print(f"  输出内容:")
                print(writer_step.get('output', '')[:800])
            
            print("\n最终结果:")
            final_result = data.get('final_result', '')
            print(final_result[:1200])
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_love_letter())