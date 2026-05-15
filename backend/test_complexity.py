import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from core.workflow.service import WorkflowService
from agents.base.agent_registry import AgentRegistry
from models.workflow import WorkflowInput

async def test_complexity_assessment():
    agent_registry = AgentRegistry()
    await agent_registry.initialize_all_agents()
    
    workflow_service = WorkflowService(agent_registry)
    
    test_cases = [
        {
            "name": "简单问答",
            "input": "什么是人工智能？",
            "expected_complexity": "低"
        },
        {
            "name": "中等任务",
            "input": "帮我写一封邮件",
            "expected_complexity": "中"
        },
        {
            "name": "复杂规划任务",
            "input": "帮我制定一份校园科技节活动策划方案，包括活动主题、流程安排、预算分配、时间线规划、人员分工、宣传方案、应急预案等内容，要求专业详细可执行。",
            "expected_complexity": "高"
        }
    ]
    
    for test_case in test_cases:
        print("\n" + "="*60)
        print("测试案例: {}".format(test_case['name']))
        print("输入: {}...".format(test_case['input'][:50]))
        print("预期复杂度: {}".format(test_case['expected_complexity']))
        print("="*60)
        
        try:
            workflow_input = WorkflowInput(user_input=test_case['input'])
            result = await workflow_service.execute(workflow_input)
            
            print("\n执行结果:")
            print("- 复杂度评分: {:.2f}".format(result.complexity_score))
            print("- 是否本地执行: {}".format("是" if result.executed_locally else "否"))
            
            for step in result.steps:
                if step.agent_id == 'judge':
                    try:
                        judge_data = json.loads(step.output)
                        print("- Judge决策: {}".format(judge_data.get('decision', '未知')))
                        print("- Cloud模式: {}".format(judge_data.get('cloud_mode', '未知')))
                        print("- Review评分: {:.2f}".format(judge_data.get('review_score', 0.0)))
                        reasons = judge_data.get('reason', [])
                        print("- 原因: {}".format(", ".join(reasons)))
                    except Exception as e:
                        print("- Judge输出解析失败: {}".format(e))
                        print("- Judge原始输出: {}".format(step.output[:200]))
            
            if result.complexity_score >= 0.7:
                actual_complexity = "高"
            elif result.complexity_score >= 0.4:
                actual_complexity = "中"
            else:
                actual_complexity = "低"
            
            match = "匹配" if actual_complexity == test_case['expected_complexity'] else "不匹配"
            print("\n评估: {}".format(match))
            
        except Exception as e:
            print("错误: {}".format(e))
    
    await agent_registry.shutdown_all_agents()

if __name__ == "__main__":
    asyncio.run(test_complexity_assessment())