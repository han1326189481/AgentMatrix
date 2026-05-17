import asyncio
import json
from agents.judge.agent import JudgeAgent
from agents.base.agent import AgentInput

async def test_judge_mechanism():
    judge_agent = JudgeAgent()
    
    test_cases = [
        {
            "name": "简单问题-什么是人工智能",
            "user_task": "什么是人工智能？",
            "writer_output": "人工智能是计算机科学的一个分支..."
        },
        {
            "name": "中等复杂度-活动策划",
            "user_task": "帮我策划一个校园运动会活动方案，需要包含流程、预算、时间安排",
            "writer_output": "# 校园运动会活动方案\n\n## 一、活动概述\n..."
        },
        {
            "name": "高复杂度-项目设计",
            "user_task": "帮我设计一个AI智能客服系统的技术方案，包含架构设计、技术选型、实施步骤、风险评估和预算规划，要求专业详细",
            "writer_output": "# AI智能客服系统技术方案\n\n## 1. 需求分析\n..."
        },
        {
            "name": "复杂方案-应急预案",
            "user_task": "请制定一份企业应急预案，包含风险评估、应急响应流程、人员分工、资源调配、演练计划等内容",
            "writer_output": "# 企业应急预案\n\n## 一、风险评估\n..."
        }
    ]
    
    print("=" * 80)
    print("Judge Agent 评审机制测试")
    print("=" * 80)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n【测试用例 {i}】{test_case['name']}")
        print("-" * 60)
        print(f"用户任务: {test_case['user_task'][:50]}..." if len(test_case['user_task']) > 50 else f"用户任务: {test_case['user_task']}")
        
        input_data = AgentInput(
            content=json.dumps({
                "user_task": test_case['user_task'],
                "summary_result": {"task": test_case['user_task']},
                "review_result": {"review_score": 0.7},
                "writer_output": test_case['writer_output']
            }),
            use_llm=False,
            use_cloud=False
        )
        
        output = await judge_agent.execute(input_data)
        
        if output.success:
            result = json.loads(output.content)
            print(f"复杂度评分: {result['complexity_score']:.2f}")
            print(f"Review评分: {result['review_score']:.2f}")
            print(f"决策结果: {result['decision']}")
            print(f"Cloud模式: {result['cloud_mode']}")
            print(f"执行方式: {'本地执行' if result['decision'] == 'local_output' else '云端增强'}")
            print("决策理由:")
            for reason in result.get("reason", []):
                print(f"  - {reason}")
            
            executed_locally = result["decision"] == "local_output"
            print(f"\n结论: {'✅ 使用本地模型' if executed_locally else '☁️ 调用云端服务'}")
        else:
            print(f"❌ 执行失败: {output.message}")
        
        print("-" * 60)
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_judge_mechanism())