import asyncio
import json
from agents.base.agent_registry import AgentRegistry

async def test_writer_agent():
    print("=== 测试 Writer Agent ===")
    
    # 初始化 Agent Registry
    ar = AgentRegistry()
    ar.initialize_all_agents_sync()
    
    # 创建测试输入（模拟 Summary Agent 的输出格式）
    test_input = json.dumps({
        "task": "帮我写一个关于校园AI助手的年度规划",
        "original_question": "帮我写一个关于校园AI助手的年度规划包含：1.时间线、2.目标分析、3.实施步骤",
        "keywords": ["AI", "校园", "规划", "年度"],
        "knowledge_points": [
            {"type": "领域知识", "content": "校园AI助手可以帮助学生学习、教师教学管理等"},
            {"type": "通用知识", "content": "年度规划需要包含目标设定、时间安排、资源分配"}
        ],
        "requirements": ["需要包含时间线", "需要包含目标分析", "需要包含实施步骤"],
        "outline": [
            "一、任务概述",
            "二、核心需求", 
            "三、解决方案",
            "四、实施计划"
        ],
        "summary": "用户需要校园AI助手的年度规划方案"
    })
    
    print(f"输入长度: {len(test_input)}")
    print(f"输入内容预览: {test_input[:200]}...")
    
    # 获取 Writer Agent
    writer_agent = ar.get_agent("writer")
    if not writer_agent:
        print("ERROR: Writer Agent 未找到")
        return
    
    from agents.base.agent import AgentInput
    
    # 执行 Writer Agent
    agent_input = AgentInput(content=test_input, context={}, use_llm=True, use_cloud=False)
    result = await writer_agent.execute(agent_input)
    
    print(f"\n输出状态: {'成功' if result.success else '失败'}")
    print(f"输出长度: {len(result.content)}")
    print(f"输出内容预览: {result.content[:500]}")
    
    if len(result.content) < 100:
        print("\n警告: 输出内容过短，可能存在问题！")
        print(f"完整输出: {result.content}")
    
    print(f"\n元数据: {result.metadata}")

async def test_review_agent():
    print("\n=== 测试 Review Agent ===")
    
    ar = AgentRegistry()
    ar.initialize_all_agents_sync()
    
    # 创建测试输入
    review_input = json.dumps({
        "user_task": "帮我写一个关于校园AI助手的年度规划",
        "summary": "用户需要校园AI助手的年度规划方案",
        "writer_output": "# 校园AI助手年度规划\n\n## 一、任务概述\n校园AI助手是一个旨在提升校园智能化水平的项目...\n\n## 二、核心需求\n1. 时间线规划\n2. 目标分析\n3. 实施步骤\n\n## 三、解决方案\n...\n\n## 四、实施计划\n..."
    })
    
    print(f"输入长度: {len(review_input)}")
    
    review_agent = ar.get_agent("review")
    if not review_agent:
        print("ERROR: Review Agent 未找到")
        return
    
    from agents.base.agent import AgentInput
    
    agent_input = AgentInput(content=review_input, context={}, use_llm=True, use_cloud=False)
    result = await review_agent.execute(agent_input)
    
    print(f"\n输出状态: {'成功' if result.success else '失败'}")
    print(f"输出长度: {len(result.content)}")
    print(f"输出内容: {result.content}")
    
    if result.success and result.content:
        try:
            data = json.loads(result.content)
            print(f"\n解析结果:")
            print(f"  review_score: {data.get('review_score')}")
            print(f"  dimensions: {data.get('dimensions')}")
            print(f"  issues: {data.get('issues')}")
            print(f"  suggestions: {data.get('suggestions')}")
            print(f"  pass: {data.get('pass')}")
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_writer_agent())
    asyncio.run(test_review_agent())
