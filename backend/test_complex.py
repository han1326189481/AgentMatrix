import asyncio
import httpx

async def test_complex():
    user_input = "帮我设计一个校园运动会活动方案，需要包含流程、预算、时间线、人员分工"
    print(f"发送请求: {user_input}")
    
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            "http://localhost:8000/api/v1/workflow/execute",
            json={"user_input": user_input}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n状态码: 200 OK")
            print(f"执行方式: {'本地执行' if data.get('executed_locally') else '云端执行'}")
            print(f"复杂度评分: {data.get('complexity_score', 0.0):.2f}")
            print(f"总耗时: {data.get('total_duration_seconds', 0.0):.2f}秒")
            
            print("\n=== 最终结果 ===\n")
            result = data.get('final_result', '')
            if len(result) > 2000:
                print(result[:2000] + "\n...")
            else:
                print(result)
        else:
            print(f"请求失败: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_complex())