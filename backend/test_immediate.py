import asyncio
import httpx

async def test_immediate():
    user_input = "帮我给刘晓丹写一份情书"
    print(f"发送请求: {user_input}")
    
    async with httpx.AsyncClient(timeout=120) as client:
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
            
            print("\n=== 最终结果 ===")
            print(data.get('final_result', ''))
        else:
            print(f"请求失败: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_immediate())
