import asyncio
import json
from agents.base.agent_registry import AgentRegistry
from agents.base.agent import AgentInput
from core.workflow.service import WorkflowService

async def test_llm_calls():
    print("=" * 80)
    print("测试 LLM 调用集成")
    print("=" * 80)
    
    agent_registry = AgentRegistry()
    await agent_registry.initialize_all_agents()
    
    print("\n【1】检查所有 Agent 配置")
    print("-" * 60)
    for agent_id in ["knowledge", "summary", "writer", "review", "judge", "result"]:
        agent = agent_registry.get_agent(agent_id)
        if agent:
            print(f"Agent: {agent.agent_id} ({agent.name})")
            print(f"  - 本地模型: {agent.local_model}")
            print(f"  - 云端模型: {agent.cloud_model}")
            print()
    
    print("\n【2】测试单个 Agent LLM 调用")
    print("-" * 60)
    
    # 测试 Summary Agent
    summary_agent = agent_registry.get_agent("summary")
    if summary_agent:
        print("测试 Summary Agent (使用本地LLM)...")
        input_data = AgentInput(content="帮我写一份活动策划", use_llm=True, use_cloud=False)
        output = await summary_agent.execute(input_data)
        print(f"  成功: {output.success}")
        print(f"  模型: {output.model_used}")
        print(f"  输出长度: {len(output.content)} 字符")
        print(f"  输出预览: {output.content[:100]}...")
        print()
    
    # 测试 Writer Agent
    writer_agent = agent_registry.get_agent("writer")
    if writer_agent:
        print("测试 Writer Agent (使用本地LLM)...")
        summary_result = json.dumps({
            "task": "帮我写一份简单的活动策划",
            "keywords": ["活动", "策划"],
            "summary": "用户需要一份活动策划方案"
        })
        input_data = AgentInput(content=summary_result, use_llm=True, use_cloud=False)
        output = await writer_agent.execute(input_data)
        print(f"  成功: {output.success}")
        print(f"  模型: {output.model_used}")
        print(f"  输出长度: {len(output.content)} 字符")
        print(f"  输出预览: {output.content[:100]}...")
        print()
    
    # 测试 Review Agent
    review_agent = agent_registry.get_agent("review")
    if review_agent:
        print("测试 Review Agent (使用本地LLM)...")
        review_input = json.dumps({
            "user_task": "帮我写一份活动策划",
            "summary": "用户需要一份活动策划方案",
            "writer_output": "# 活动策划方案\n\n## 活动概述\n这是一份活动策划方案。"
        })
        input_data = AgentInput(content=review_input, use_llm=True, use_cloud=False)
        output = await review_agent.execute(input_data)
        print(f"  成功: {output.success}")
        print(f"  模型: {output.model_used}")
        result = json.loads(output.content) if output.success else {}
        print(f"  Review评分: {result.get('review_score', 'N/A')}")
        print()
    
    print("\n【3】测试完整工作流")
    print("-" * 60)
    
    workflow_service = WorkflowService(agent_registry)
    
    test_task = "帮我写一份简单的校园活动策划"
    
    from models.workflow import WorkflowInput
    workflow_input = WorkflowInput(user_input=test_task)
    
    print(f"执行任务: {test_task}")
    print("请稍候...")
    
    try:
        result = await workflow_service.execute(workflow_input)
        print(f"\n工作流执行完成!")
        print(f"  执行方式: {'本地执行' if result.executed_locally else '云端执行'}")
        print(f"  复杂度评分: {result.complexity_score:.2f}")
        print(f"  总耗时: {result.total_duration_seconds:.2f}秒")
        print(f"  步骤数: {len(result.steps)}")
        
        print("\n  各步骤详情:")
        for step in result.steps:
            status = "✅" if step.success else "❌"
            model = step.metadata.get("model_used", "N/A")
            print(f"    {status} {step.agent_name}: 模型={model}, 耗时={step.duration_seconds:.2f}s")
        
        print(f"\n  最终结果长度: {len(result.final_result)} 字符")
        
    except Exception as e:
        print(f"❌ 工作流执行失败: {str(e)}")
    
    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_llm_calls())