import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.workflow.service import WorkflowService
from agents.base.agent_registry import AgentRegistry
from models.workflow import WorkflowInput

async def test_output():
    ar = AgentRegistry()
    await ar.initialize_all_agents()
    
    ws = WorkflowService(ar)
    
    test_input = "什么是人工智能？"
    workflow_input = WorkflowInput(user_input=test_input)
    result = await ws.execute(workflow_input)
    
    print("输出长度:", len(result.final_result))
    print("\n=== 检查是否包含复杂度评估 ===")
    print("包含 '复杂度评估':", "复杂度评估" in result.final_result)
    print("包含 '复杂度等级':", "复杂度等级" in result.final_result)
    print("包含 '评估':", "评估:" in result.final_result)
    print("包含 '建议':", "建议:" in result.final_result)
    
    with open("test_output.txt", "w", encoding="utf-8") as f:
        f.write(result.final_result)
    print("\n输出已保存到 test_output.txt")
    
    await ar.shutdown_all_agents()

if __name__ == "__main__":
    asyncio.run(test_output())