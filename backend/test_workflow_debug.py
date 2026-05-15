import asyncio
import json
from agents.knowledge.agent import KnowledgeAgent
from agents.summary.agent import SummaryAgent
from agents.writer.agent import WriterAgent
from agents.review.agent import ReviewAgent
from agents.base.agent import AgentInput

async def test_full_workflow():
    print("=== 测试完整工作流 ===")
    
    user_input = "帮我写一个关于校园AI助手的年度规划包含：1.时间线、2.目标分析、3.实施步骤"
    
    print(f"用户输入: {user_input}")
    print(f"输入长度: {len(user_input)}")
    
    # 执行 Knowledge Agent
    print("\n--- 1. 执行 Knowledge Agent ---")
    knowledge_agent = KnowledgeAgent()
    knowledge_input = AgentInput(content=user_input, context={}, use_llm=False, use_cloud=False)
    knowledge_result = await knowledge_agent.execute(knowledge_input)
    print(f"输出状态: {'成功' if knowledge_result.success else '失败'}")
    print(f"输出长度: {len(knowledge_result.content)}")
    print(f"输出预览: {knowledge_result.content[:300]}...")
    
    # 执行 Summary Agent
    print("\n--- 2. 执行 Summary Agent ---")
    summary_agent = SummaryAgent()
    summary_input = AgentInput(content=knowledge_result.content, context={}, use_llm=False, use_cloud=False)
    summary_result = await summary_agent.execute(summary_input)
    print(f"输出状态: {'成功' if summary_result.success else '失败'}")
    print(f"输出长度: {len(summary_result.content)}")
    print(f"输出预览: {summary_result.content[:500]}")
    
    # 解析 Summary 输出
    try:
        summary_data = json.loads(summary_result.content)
        print(f"\n解析的任务: {summary_data.get('task')}")
        print(f"关键词: {summary_data.get('keywords')}")
        print(f"需求: {summary_data.get('requirements')}")
        print(f"大纲: {summary_data.get('outline')}")
    except json.JSONDecodeError as e:
        print(f"Summary 输出 JSON 解析失败: {e}")
        print(f"原始输出: {summary_result.content}")
    
    # 执行 Writer Agent
    print("\n--- 3. 执行 Writer Agent ---")
    writer_agent = WriterAgent()
    writer_input = AgentInput(content=summary_result.content, context={}, use_llm=True, use_cloud=False)
    writer_result = await writer_agent.execute(writer_input)
    print(f"输出状态: {'成功' if writer_result.success else '失败'}")
    print(f"输出长度: {len(writer_result.content)}")
    print(f"输出预览: {writer_result.content[:500]}")
    
    if len(writer_result.content) < 100:
        print(f"\n警告: Writer Agent 输出过短！")
        print(f"完整输出: {writer_result.content}")
        print(f"错误信息: {writer_result.message}")
    
    # 执行 Review Agent
    print("\n--- 4. 执行 Review Agent ---")
    review_agent = ReviewAgent()
    
    review_input_data = {
        "user_task": user_input,
        "summary": summary_data.get("summary", "") if 'summary_data' in dir() else "",
        "writer_output": writer_result.content
    }
    print(f"Review 输入数据: {json.dumps(review_input_data)[:300]}...")
    
    review_input = AgentInput(content=json.dumps(review_input_data), context={}, use_llm=True, use_cloud=False)
    review_result = await review_agent.execute(review_input)
    print(f"输出状态: {'成功' if review_result.success else '失败'}")
    print(f"输出长度: {len(review_result.content)}")
    print(f"输出内容: {review_result.content}")

if __name__ == "__main__":
    asyncio.run(test_full_workflow())
