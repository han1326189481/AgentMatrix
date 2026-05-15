import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agents.knowledge.agent
import agents.summary.agent
import agents.writer.agent
import agents.review.agent

from agents.base.agent_registry import AgentRegistry
from agents.base.agent import AgentInput

async def main():
    # 创建registry并注册agent
    registry = AgentRegistry()
    registry.register_agent(agents.knowledge.agent.KnowledgeAgent())
    registry.register_agent(agents.summary.agent.SummaryAgent())
    registry.register_agent(agents.writer.agent.WriterAgent())
    registry.register_agent(agents.review.agent.ReviewAgent())

    print("=== 测试 Review Agent 调试 ===")
    
    # 测试数据 - 模拟用户输入
    user_task = "帮我写一个关于校园AI助手的年度规划包含：1.时间线、2.人员安排、3.经费预算、4.风险分析、5.推广方案"
    
    print(f"\n1. 用户任务: {user_task}")
    print(f"   长度: {len(user_task)} 字符")
    
    # 测试 Knowledge Agent
    print("\n2. 测试 Knowledge Agent...")
    knowledge_result = await registry.execute_agent("knowledge", AgentInput(content=user_task, use_llm=False))
    print(f"   成功: {knowledge_result.success}")
    print(f"   长度: {len(knowledge_result.content)} 字符")
    
    # 测试 Summary Agent
    print("\n3. 测试 Summary Agent...")
    summary_result = await registry.execute_agent("summary", AgentInput(content=knowledge_result.content, use_llm=False))
    print(f"   成功: {summary_result.success}")
    print(f"   长度: {len(summary_result.content)} 字符")
    
    # 测试 Writer Agent
    print("\n4. 测试 Writer Agent...")
    writer_input = f"{knowledge_result.content}\n\n任务摘要: {summary_result.content}"
    writer_result = await registry.execute_agent("writer", AgentInput(content=writer_input, use_llm=False))
    print(f"   成功: {writer_result.success}")
    print(f"   长度: {len(writer_result.content)} 字符")
    print(f"   预览: {writer_result.content[:200]}...")
    
    # 测试 Review Agent（使用正确的JSON格式）
    print("\n5. 测试 Review Agent...")
    import json
    review_input = json.dumps({
        "user_task": user_task,
        "summary": summary_result.content,
        "writer_output": writer_result.content
    })
    print(f"   输入格式: JSON")
    print(f"   输入长度: {len(review_input)} 字符")
    
    try:
        review_result = await registry.execute_agent("review", AgentInput(content=review_input, use_llm=True, use_cloud=False))
        print(f"   成功: {review_result.success}")
        print(f"   长度: {len(review_result.content)} 字符")
        print(f"   内容: {review_result.content}")
    except Exception as e:
        print(f"   失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
