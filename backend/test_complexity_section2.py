import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from core.workflow.service import WorkflowService
from agents.base.agent_registry import AgentRegistry
from models.workflow import WorkflowInput

async def test_complexity_section():
    agent_registry = AgentRegistry()
    await agent_registry.initialize_all_agents()
    
    workflow_service = WorkflowService(agent_registry)
    
    test_input = "帮我制定一份校园科技节活动策划方案，包括活动主题、流程安排、预算分配、时间线规划、人员分工、宣传方案、应急预案等内容，要求专业详细可执行。"
    
    print("测试案例: 复杂规划任务")
    print("输入: {}...".format(test_input[:50]))
    
    try:
        workflow_input = WorkflowInput(user_input=test_input)
        result = await workflow_service.execute(workflow_input)
        
        print("\n检查最终输出是否包含复杂度评估部分:")
        print("-" * 50)
        
        has_complexity = "复杂度评估与建议" in result.final_result
        
        if has_complexity:
            print("RESULT: 包含复杂度评估部分")
            idx = result.final_result.index("复杂度评估与建议")
            section = result.final_result[idx:idx+1500]
            print("\n复杂度评估内容:")
            print(section)
        else:
            print("RESULT: 未找到复杂度评估部分")
            print("\n输出长度:", len(result.final_result))
            print("\n输出末尾1000字符:")
            print(result.final_result[-1000:])
        
        print("\nJudge结果:")
        for step in result.steps:
            if step.agent_id == 'judge':
                print("Judge输出:", step.output)
                break
            
    except Exception as e:
        print("ERROR:", e)
        import traceback
        traceback.print_exc()
    
    await agent_registry.shutdown_all_agents()

if __name__ == "__main__":
    asyncio.run(test_complexity_section())