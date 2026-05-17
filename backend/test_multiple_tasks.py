import asyncio
import httpx

async def test_tasks():
    tasks = [
        "帮我给刘晓丹写一份情书",
        "写一首关于春天的诗",
        "帮我设计一个校园运动会活动方案",
        "什么是人工智能？",
        "写一封感谢信给老师"
    ]
    
    for task in tasks:
        print(f"\n{'='*60}")
        print(f"任务: {task}")
        print('='*60)
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/workflow/execute",
                    json={"user_input": task}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"执行方式: {'本地执行' if data.get('executed_locally') else '云端执行'}")
                    print(f"复杂度评分: {data.get('complexity_score', 0.0):.2f}")
                    print(f"总耗时: {data.get('total_duration_seconds', 0.0):.2f}秒")
                    
                    final_result = data.get('final_result', '')
                    print(f"\n结果长度: {len(final_result)} 字符")
                    print("\n结果预览:")
                    print(final_result[:800])
                else:
                    print(f"❌ 请求失败: {response.status_code}")
        except Exception as e:
            print(f"❌ 异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_tasks())