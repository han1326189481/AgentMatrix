import asyncio
import json
from agents.judge.agent import JudgeAgent
from agents.base.agent import AgentInput

async def test_judge_comprehensive():
    judge_agent = JudgeAgent()
    
    test_cases = [
        {
            "name": "简单问答-什么是问题",
            "user_task": "什么是人工智能？",
            "writer_output": "人工智能是计算机科学的一个分支，致力于研究、开发用于模拟、延伸和扩展人的智能的理论、方法、技术及应用系统。",
            "review_score": 0.8
        },
        {
            "name": "简单问答-如何问题",
            "user_task": "如何学习编程？",
            "writer_output": "学习编程可以从选择一门编程语言开始，建议从Python入门，通过在线课程和实践项目来提升技能。",
            "review_score": 0.75
        },
        {
            "name": "中等复杂度-活动策划",
            "user_task": "帮我策划一个校园运动会活动方案，需要包含流程、预算、时间安排",
            "writer_output": "# 校园运动会活动方案\n\n## 一、活动概述\n本次运动会旨在增强学生体质，丰富校园文化生活...\n\n## 二、活动流程\n开幕式 -> 比赛项目 -> 闭幕式\n\n## 三、预算安排\n预计总预算5万元...",
            "review_score": 0.7
        },
        {
            "name": "中等复杂度-方案设计",
            "user_task": "设计一个企业团建活动方案，包含活动主题、流程安排、人员分工、预算规划",
            "writer_output": "# 企业团建活动方案\n\n## 活动主题\n团结协作，共创未来\n\n## 时间安排\n2024年12月15日\n\n## 人员分工\n活动策划组、后勤保障组、宣传组...",
            "review_score": 0.65
        },
        {
            "name": "高复杂度-AI系统设计",
            "user_task": "帮我设计一个AI智能客服系统的技术方案，包含架构设计、技术选型、实施步骤、风险评估和预算规划，要求专业详细",
            "writer_output": "# AI智能客服系统技术方案\n\n## 1. 需求分析\n分析用户需求和业务场景...\n\n## 2. 架构设计\n采用微服务架构，包含对话模块、知识库模块...\n\n## 3. 技术选型\n前端：React + TypeScript\n后端：Python + FastAPI\nAI模型：DeepSeek R1...",
            "review_score": 0.7
        },
        {
            "name": "高复杂度-应急预案",
            "user_task": "请制定一份企业应急预案，包含风险评估、应急响应流程、人员分工、资源调配、演练计划等内容，要求符合行业标准",
            "writer_output": "# 企业应急预案\n\n## 一、风险评估\n识别潜在风险：火灾、水灾、地震、网络安全...\n\n## 二、应急响应流程\n预警阶段 -> 响应阶段 -> 恢复阶段\n\n## 三、人员分工\n应急指挥中心、抢险救援组、后勤保障组...",
            "review_score": 0.75
        },
        {
            "name": "低质量-需要云端增强",
            "user_task": "帮我写一份详细的市场调研报告",
            "writer_output": "市场调研报告\n\n1. 市场现状\n2. 竞争分析\n3. 建议",
            "review_score": 0.4
        },
        {
            "name": "中等质量-本地重试",
            "user_task": "制定一个产品推广方案",
            "writer_output": "# 产品推广方案\n\n## 目标\n提高产品知名度\n\n## 渠道\n线上和线下",
            "review_score": 0.55
        },
        {
            "name": "长文本复杂任务",
            "user_task": "请为我撰写一份关于AI技术发展趋势的深度分析报告，要求涵盖2024-2025年的主要技术突破、行业应用案例、市场趋势预测、挑战与机遇分析，以及对未来5年发展的展望。报告需要数据支撑，引用至少5个权威机构的研究数据，包括Gartner、IDC、麦肯锡等，并提供具体的行业应用案例分析。",
            "writer_output": "# AI技术发展趋势深度分析报告\n\n## 一、引言\n人工智能技术近年来取得了飞速发展...\n\n## 二、2024-2025年主要技术突破\n1. 大语言模型能力提升\n2. 多模态AI融合\n3. Edge AI发展...",
            "review_score": 0.68
        },
        {
            "name": "简单问题但长描述",
            "user_task": "请问什么是云计算？请从定义、特点、服务类型、应用场景、优缺点等方面进行详细解释，最好能举一些实际的应用案例。",
            "writer_output": "云计算是一种基于互联网的计算方式...",
            "review_score": 0.72
        }
    ]
    
    print("=" * 80)
    print("Judge Agent 评审机制综合测试")
    print("=" * 80)
    print(f"测试用例总数: {len(test_cases)}")
    print("-" * 80)
    
    stats = {
        "local_output": 0,
        "local_retry": 0,
        "cloud_enhance": 0
    }
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n【测试用例 {i}】{test_case['name']}")
        print("-" * 60)
        print(f"用户任务: {test_case['user_task'][:60]}..." if len(test_case['user_task']) > 60 else f"用户任务: {test_case['user_task']}")
        
        input_data = AgentInput(
            content=json.dumps({
                "user_task": test_case['user_task'],
                "summary_result": {"task": test_case['user_task']},
                "review_result": {"review_score": test_case['review_score']},
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
            print(f"执行方式: {'本地执行' if result['decision'] == 'local_output' else '本地重试' if result['decision'] == 'local_retry' else '云端增强'}")
            print("决策理由:")
            for reason in result.get("reason", []):
                print(f"  - {reason}")
            
            stats[result['decision']] += 1
            
            if result['decision'] == 'local_output':
                print(f"\n结论: ✅ 使用本地模型")
            elif result['decision'] == 'local_retry':
                print(f"\n结论: ⚠️ 本地重试优化")
            else:
                print(f"\n结论: ☁️ 调用云端服务")
        else:
            print(f"❌ 执行失败: {output.message}")
        
        print("-" * 60)
    
    print("\n" + "=" * 80)
    print("测试统计")
    print("=" * 80)
    print(f"本地执行: {stats['local_output']} 个")
    print(f"本地重试: {stats['local_retry']} 个")
    print(f"云端增强: {stats['cloud_enhance']} 个")
    print(f"总测试: {sum(stats.values())} 个")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_judge_comprehensive())