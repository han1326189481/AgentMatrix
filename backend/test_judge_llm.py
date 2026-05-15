import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agents.knowledge.agent
import agents.summary.agent
import agents.writer.agent
import agents.review.agent
import agents.judge.agent
import agents.result.agent

from agents.base.agent_registry import AgentRegistry
from agents.base.agent import AgentInput

async def main():
    # 创建registry并注册agent
    registry = AgentRegistry()
    registry.register_agent(agents.knowledge.agent.KnowledgeAgent())
    registry.register_agent(agents.summary.agent.SummaryAgent())
    registry.register_agent(agents.writer.agent.WriterAgent())
    registry.register_agent(agents.review.agent.ReviewAgent())
    registry.register_agent(agents.judge.agent.JudgeAgent())
    registry.register_agent(agents.result.agent.ResultAgent())

    print("=== 测试 Judge Agent LLM 模式 ===")
    
    # 测试数据
    user_task = "帮我写一份校园活动策划，包含时间线、人员安排、经费预算、风险分析和推广方案"
    summary_result = "用户需要一份完整的校园活动策划方案，包含五个核心模块"
    writer_output = "这是一份校园活动策划方案...（内容略）"
    
    # 先获取 Review 结果
    import json
    review_input = json.dumps({
        "user_task": user_task,
        "summary": summary_result,
        "writer_output": writer_output
    })
    review_result = await registry.execute_agent("review", AgentInput(content=review_input, use_llm=True, use_cloud=False))
    print(f"Review 结果: {review_result.content}")
    
    # 测试 Judge Agent 使用 LLM 模式
    print("\n=== Judge Agent 使用 LLM 模式 ===")
    judge_input = json.dumps({
        "user_task": user_task,
        "summary_result": summary_result,
        "review_result": review_result.content,
        "writer_output": writer_output
    })
    
    # 使用 LLM 模式
    judge_result = await registry.execute_agent("judge", AgentInput(content=judge_input, use_llm=True, use_cloud=False))
    print(f"成功: {judge_result.success}")
    print(f"模型: {judge_result.model_used}")
    print(f"内容: {judge_result.content}")
    print(f"元数据: {judge_result.metadata}")
    
    # 验证结果
    try:
        judge_data = json.loads(judge_result.content)
        print(f"\n解析结果:")
        print(f"  复杂度评分: {judge_data.get('complexity_score')}")
        print(f"  Review评分: {judge_data.get('review_score')}")
        print(f"  决策: {judge_data.get('decision')}")
        print(f"  Cloud模式: {judge_data.get('cloud_mode')}")
        print(f"  理由: {judge_data.get('reason')}")
    except Exception as e:
        print(f"解析失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
