import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app
from app.dependencies import get_agent_registry
from models.workflow import WorkflowInput

async def test_workflow():
    """测试工作流执行"""
    try:
        # 获取agent registry
        registry = get_agent_registry()
        # 初始化所有agent
        registry.initialize_all_agents_sync()
        
        # 创建测试输入
        test_input = WorkflowInput(
            user_input="帮我写一份简单的校园活动策划",
            context={}
        )
        
        # 测试单个agent
        print("=== 测试单个Agent ===")
        
        # 测试Knowledge Agent
        print("\n1. 测试 Knowledge Agent...")
        from agents.base.agent import AgentInput
        knowledge_result = await registry.execute_agent("knowledge", AgentInput(content="帮我写一份简单的校园活动策划"))
        print(f"   成功: {knowledge_result.success}")
        print(f"   内容长度: {len(knowledge_result.content)}")
        print(f"   预览: {knowledge_result.content[:100]}...")
        
        # 测试Summary Agent
        print("\n2. 测试 Summary Agent...")
        summary_result = await registry.execute_agent("summary", AgentInput(content=knowledge_result.content))
        print(f"   成功: {summary_result.success}")
        print(f"   内容长度: {len(summary_result.content)}")
        
        # 测试Writer Agent
        print("\n3. 测试 Writer Agent...")
        writer_input = f"{knowledge_result.content}\n\n任务摘要: {summary_result.content}"
        writer_result = await registry.execute_agent("writer", AgentInput(content=writer_input))
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
        review_result = await registry.execute_agent("review", AgentInput(content=review_input))
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
        judge_result = await registry.execute_agent("judge", AgentInput(content=judge_input))
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
            result_result = await registry.execute_agent("result", AgentInput(content=result_input))
            print(f"   成功: {result_result.success}")
            print(f"   内容长度: {len(result_result.content)}")
            print(f"   预览: {result_result.content[:200]}...")
        except Exception as e:
            print(f"   失败: {e}")
        
        print("\n=== 所有单个Agent测试完成 ===")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_workflow())
