import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiohttp

async def main():
    print("=== 测试工作流 API ===")
    
    # 模拟前端调用工作流API
    url = "http://localhost:8080/api/v1/workflow/execute"
    
    user_input = "帮我写一个关于校园AI助手的年度规划包含：1.时间线、2.人员安排、3.经费预算、4.风险分析、5.推广方案"
    
    payload = {
        "user_input": user_input,
        "context": {}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                print(f"HTTP状态码: {response.status}")
                
                if response.status == 200:
                    result = await response.json()
                    print("成功!")
                    print(f"最终结果长度: {len(result.get('final_result', ''))}")
                    print(f"步骤数: {len(result.get('steps', []))}")
                    
                    for step in result.get('steps', []):
                        print(f"\n步骤: {step['agent_name']}")
                        print(f"  状态: {'成功' if step['success'] else '失败'}")
                        print(f"  耗时: {step['duration_seconds']:.2f}s")
                        if 'error' in step.get('metadata', {}):
                            print(f"  错误: {step['metadata']['error']}")
                else:
                    error_text = await response.text()
                    print(f"失败!")
                    print(f"错误信息: {error_text}")
                    
    except Exception as e:
        print(f"请求失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
