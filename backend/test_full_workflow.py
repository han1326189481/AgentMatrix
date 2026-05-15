import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from core.workflow.service import WorkflowService
from agents.base.agent_registry import AgentRegistry
from models.workflow import WorkflowInput

async def test_full_workflow():
    agent_registry = AgentRegistry()
    await agent_registry.initialize_all_agents()
    
    workflow_service = WorkflowService(agent_registry)
    
    test_cases = [
        {
            "name": "简单问答",
            "input": "什么是人工智能？"
        },
        {
            "name": "复杂规划任务",
            "input": "帮我制定一份校园科技节活动策划方案，包括活动主题、流程安排、预算分配、时间线规划、人员分工、宣传方案、应急预案等内容，要求专业详细可执行。"
        }
    ]
    
    for test_case in test_cases:
        print("\n" + "="*70)
        print("测试案例: {}".format(test_case['name']))
        print("输入: {}...".format(test_case['input'][:50]))
        print("="*70)
        
        try:
            workflow_input = WorkflowInput(user_input=test_case['input'])
            result = await workflow_service.execute(workflow_input)
            
            print("\n" + "-"*70)
            print("最终输出结果:")
            print("-"*70)
            
            # 只显示最后一部分，包含复杂度评估和建议
            final_output = result.final_result
            
            # 找到 "复杂度评估与建议" 部分
            if "复杂度评估与建议" in final_output:
                idx = final_output.index("复杂度评估与建议")
                summary_section = final_output[idx:]
                print(summary_section)
            else:
                print(final_output[-2000:])
            
            print("\n" + "="*70)
            
        except Exception as e:
            print("错误: {}".format(e))
            import traceback
            traceback.print_exc()
    
    await agent_registry.shutdown_all_agents()

if __name__ == "__main__":
    asyncio.run(test_full_workflow())