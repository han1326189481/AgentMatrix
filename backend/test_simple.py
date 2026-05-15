import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入所有agent
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

    print("=== Agent注册完成 ===")
    print(f"已注册的Agent: {list(registry.agents.keys())}")

    # 测试单个agent（不使用LLM，只测试规则引擎）
    print("\n=== 测试单个Agent（规则引擎模式） ===")

    # 测试Knowledge Agent
    print("\n1. 测试 Knowledge Agent...")
    knowledge_result = await registry.execute_agent("knowledge", AgentInput(content="帮我写一份简单的校园活动策划", use_llm=False))
    print(f"   成功: {knowledge_result.success}")
    print(f"   内容长度: {len(knowledge_result.content)}")
    print(f"   预览: {knowledge_result.content[:100]}...")

    # 测试Summary Agent
    print("\n2. 测试 Summary Agent...")
    summary_result = await registry.execute_agent("summary", AgentInput(content=knowledge_result.content, use_llm=False))
    print(f"   成功: {summary_result.success}")
    print(f"   内容长度: {len(summary_result.content)}")

    # 测试Writer Agent
    print("\n3. 测试 Writer Agent...")
    writer_input = f"{knowledge_result.content}\n\n任务摘要: {summary_result.content}"
    writer_result = await registry.execute_agent("writer", AgentInput(content=writer_input, use_llm=False))
    print(f"   成功: {writer_result.success}")
    print(f"   内容长度: {len(writer_result.content)}")

    # 测试Review Agent（使用正确的JSON格式）
    print("\n4. 测试 Review Agent...")
    import json
    review_input = json.dumps({
        "user_task": "帮我写一份简单的校园活动策划",
        "summary": summary_result.content,
        "writer_output": writer_result.content
    })
    review_result = await registry.execute_agent("review", AgentInput(content=review_input, use_llm=False))
    print(f"   成功: {review_result.success}")
    print(f"   内容长度: {len(review_result.content)}")
    print(f"   内容: {review_result.content}")

    # 测试Judge Agent（使用正确的JSON格式）
    print("\n5. 测试 Judge Agent...")
    judge_input = json.dumps({
        "user_task": "帮我写一份简单的校园活动策划",
        "summary_result": summary_result.content,
        "review_result": review_result.content,
        "writer_output": writer_result.content
    })
    judge_result = await registry.execute_agent("judge", AgentInput(content=judge_input, use_llm=False))
    print(f"   成功: {judge_result.success}")
    print(f"   内容长度: {len(judge_result.content)}")
    print(f"   内容: {judge_result.content}")

    # 测试Result Agent（使用正确的JSON格式）
    print("\n6. 测试 Result Agent...")
    try:
        judge_data = json.loads(judge_result.content)
        result_input = json.dumps({
            "user_task": "帮我写一份简单的校园活动策划",
            "summary_result": summary_result.content,
            "review_result": review_result.content,
            "judge_result": judge_result.content,
            "writer_output": writer_result.content,
            "executed_locally": True,
            "complexity_score": judge_data.get("complexity_score", 0.0),
            "judge_decision": judge_data.get("decision", "local_output"),
            "cloud_mode": judge_data.get("cloud_mode", "none")
        })
        result_result = await registry.execute_agent("result", AgentInput(content=result_input, use_llm=False))
        print(f"   成功: {result_result.success}")
        print(f"   内容长度: {len(result_result.content)}")
        print(f"   预览: {result_result.content[:200]}...")
    except Exception as e:
        print(f"   失败: {e}")

    print("\n=== 所有单个Agent测试完成 ===")

if __name__ == "__main__":
    asyncio.run(main())
