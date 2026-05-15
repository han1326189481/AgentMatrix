import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.base.agent_registry import AgentRegistry
from agents.base.agent import AgentInput

async def test_agent_model_switch():
    agent_registry = AgentRegistry()
    await agent_registry.initialize_all_agents()
    
    print("测试 Review Agent...")
    review_agent = agent_registry.get_agent("review")
    
    test_input = AgentInput(
        content=json.dumps({
            "user_task": "帮我写一份校园活动策划",
            "summary": "用户需要正式校园活动方案",
            "writer_output": "举办活动促进同学交流。"
        }),
        use_llm=True,
        use_cloud=True
    )
    
    result = await review_agent.execute(test_input)
    print("Review Agent (云端):")
    print("  成功: {}".format(result.success))
    print("  模型: {}".format(result.model_used))
    print("  内容预览: {}...".format(result.content[:100]))
    
    test_input_local = AgentInput(
        content=json.dumps({
            "user_task": "帮我写一份校园活动策划",
            "summary": "用户需要正式校园活动方案",
            "writer_output": "举办活动促进同学交流。"
        }),
        use_llm=True,
        use_cloud=False
    )
    
    result_local = await review_agent.execute(test_input_local)
    print("\nReview Agent (本地):")
    print("  成功: {}".format(result_local.success))
    print("  模型: {}".format(result_local.model_used))
    print("  内容预览: {}...".format(result_local.content[:100]))
    
    print("\n\n测试 Judge Agent...")
    judge_agent = agent_registry.get_agent("judge")
    
    judge_input_cloud = AgentInput(
        content=json.dumps({
            "user_task": "帮我制定一份校园科技节活动策划方案，包括活动主题、流程安排、预算分配、时间线规划、人员分工、宣传方案、应急预案等内容，要求专业详细可执行。",
            "summary_result": "用户需要详细的校园科技节策划方案",
            "review_result": '{"review_score": 0.7}',
            "writer_output": "这是一个详细的活动策划方案..."
        }),
        use_llm=True,
        use_cloud=True
    )
    
    judge_result = await judge_agent.execute(judge_input_cloud)
    print("Judge Agent (云端):")
    print("  成功: {}".format(judge_result.success))
    print("  模型: {}".format(judge_result.model_used))
    print("  内容: {}".format(judge_result.content))
    
    judge_input_local = AgentInput(
        content=json.dumps({
            "user_task": "帮我制定一份校园科技节活动策划方案，包括活动主题、流程安排、预算分配、时间线规划、人员分工、宣传方案、应急预案等内容，要求专业详细可执行。",
            "summary_result": "用户需要详细的校园科技节策划方案",
            "review_result": '{"review_score": 0.7}',
            "writer_output": "这是一个详细的活动策划方案..."
        }),
        use_llm=False,
        use_cloud=False
    )
    
    judge_result_local = await judge_agent.execute(judge_input_local)
    print("\nJudge Agent (规则引擎):")
    print("  成功: {}".format(judge_result_local.success))
    print("  模型: {}".format(judge_result_local.model_used))
    print("  内容: {}".format(judge_result_local.content))
    
    await agent_registry.shutdown_all_agents()

if __name__ == "__main__":
    asyncio.run(test_agent_model_switch())