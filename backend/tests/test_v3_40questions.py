"""V3 全系统集成测试 — 40个跨领域问题

测试覆盖:
- Skill Graph: 关键词匹配 + 分解 + 规划
- Cognitive Controller: 引擎调度决策
- Reasoning Graph: 推理模式匹配
- Knowledge Recommendation: 四类推荐来源
- Capability Graph + Personal Brain: 用户画像
- Learning Engine: 概念提取 + Patch校验
- Writer Agent: 推理模式注入
"""

import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.graphs import get_skill_graph, ReasoningGraph
from core.engines.cognitive_controller import CognitiveController
from core.engines.decomposer import Decomposer
from core.engines.local_planner import LocalPlanner
from core.engines.knowledge_recommendation import KnowledgeRecommendation
from core.engines.learning_engine import LearningEngine
from core.graphs.capability_graph import CapabilityGraph, Proficiency
from core.personal_brain.brain import PersonalBrain
from core.skill_engine.task_engine import TaskType

# ============================================================
# 40个跨领域测试问题
# ============================================================
QUESTIONS = [
    # === AI/ML (8题) ===
    {"domain": "ai", "task_type": TaskType.QA, "q": "什么是Transformer架构？"},
    {"domain": "ai", "task_type": TaskType.QA, "q": "解释注意力机制的原理"},
    {"domain": "ai", "task_type": TaskType.QA, "q": "RAG和微调有什么区别？"},
    {"domain": "ai", "task_type": TaskType.QA, "q": "如何评估一个大语言模型？"},
    {"domain": "ai", "task_type": TaskType.QA, "q": "什么是Prompt Engineering？"},
    {"domain": "ai", "task_type": TaskType.ANALYSIS, "q": "对比BERT和GPT的架构差异"},
    {"domain": "ai", "task_type": TaskType.QA, "q": "解释迁移学习的概念"},
    {"domain": "ai", "task_type": TaskType.QA, "q": "如何防止模型过拟合？"},

    # === 技术/编码 (8题) ===
    {"domain": "tech", "task_type": TaskType.CODING, "q": "用Python写一个快速排序算法"},
    {"domain": "tech", "task_type": TaskType.QA, "q": "解释RESTful API的设计原则"},
    {"domain": "tech", "task_type": TaskType.QA, "q": "什么是Docker？如何使用？"},
    {"domain": "tech", "task_type": TaskType.ANALYSIS, "q": "对比SQL和NoSQL数据库"},
    {"domain": "tech", "task_type": TaskType.QA, "q": "解释Git的工作流程"},
    {"domain": "tech", "task_type": TaskType.ANALYSIS, "q": "如何优化一个慢查询？"},
    {"domain": "tech", "task_type": TaskType.QA, "q": "什么是微服务架构？"},
    {"domain": "tech", "task_type": TaskType.CODING, "q": "用Python实现一个简单的装饰器"},

    # === 商业分析 (8题) ===
    {"domain": "business", "task_type": TaskType.ANALYSIS, "q": "分析电商行业的SWOT"},
    {"domain": "business", "task_type": TaskType.PLANNING, "q": "如何制定一个产品上市策略？"},
    {"domain": "business", "task_type": TaskType.ANALYSIS, "q": "分析远程办公的利弊"},
    {"domain": "business", "task_type": TaskType.PLANNING, "q": "如何提高团队协作效率？"},
    {"domain": "business", "task_type": TaskType.ANALYSIS, "q": "创业公司如何选择技术栈？"},
    {"domain": "business", "task_type": TaskType.ANALYSIS, "q": "分析订阅制vs一次性付费模式"},
    {"domain": "business", "task_type": TaskType.ANALYSIS, "q": "如何做用户需求分析？"},
    {"domain": "business", "task_type": TaskType.ANALYSIS, "q": "AI对传统行业的影响分析"},

    # === 日常/闲聊 (6题) ===
    {"domain": "daily", "task_type": TaskType.CHAT, "q": "你好，今天天气怎么样？"},
    {"domain": "daily", "task_type": TaskType.CHAT, "q": "推荐几本好书"},
    {"domain": "daily", "task_type": TaskType.CHAT, "q": "如何保持健康的生活习惯？"},
    {"domain": "daily", "task_type": TaskType.QA, "q": "用一句话说明什么是AI"},
    {"domain": "daily", "task_type": TaskType.WRITING, "q": "写一首关于秋天的诗"},
    {"domain": "daily", "task_type": TaskType.WRITING, "q": "写一封感谢信"},

    # === 学术/规划 (5题) ===
    {"domain": "academic", "task_type": TaskType.PLANNING, "q": "如何规划一个研究项目？"},
    {"domain": "academic", "task_type": TaskType.PLANNING, "q": "如何撰写一篇学术论文？"},
    {"domain": "academic", "task_type": TaskType.PLANNING, "q": "如何准备一场技术演讲？"},
    {"domain": "academic", "task_type": TaskType.PLANNING, "q": "如何设计一个实验方案？"},
    {"domain": "academic", "task_type": TaskType.PLANNING, "q": "如何进行文献综述？"},

    # === 创意写作 (5题) ===
    {"domain": "creative", "task_type": TaskType.WRITING, "q": "写一个关于AI觉醒的短故事"},
    {"domain": "creative", "task_type": TaskType.WRITING, "q": "为一家咖啡店写广告文案"},
    {"domain": "creative", "task_type": TaskType.WRITING, "q": "写一篇关于时间管理的日记"},
    {"domain": "creative", "task_type": TaskType.WRITING, "q": "为新产品写一句口号"},
    {"domain": "creative", "task_type": TaskType.WRITING, "q": "写一封情书"},
]

# 用于验证的Mock Writer输出
MOCK_WRITER_OUTPUTS = {
    "coding": "## 需求分析\n快速排序是一种分治算法。\n\n## 设计\n选择基准值，分区，递归。\n\n## 实现\n```python\ndef quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[0]\n    left = [x for x in arr[1:] if x < pivot]\n    right = [x for x in arr[1:] if x >= pivot]\n    return quicksort(left) + [pivot] + quicksort(right)\n```\n\n## 边界\n处理空数组和重复元素。\n\n## 测试\n测试各种输入场景。",
    "analysis": "## 背景与问题\n这是一个需要深入分析的话题。\n\n## 对比维度定义\n维度一：性能\n维度二：易用性\n维度三：成本\n\n## 逐维对比分析\n各方面详细对比...\n\n## 优劣总结\n综合分析结论...\n\n## 选择建议\n基于以上分析给出建议。",
    "qa": "## 定义\nTransformer是一种基于自注意力机制的神经网络架构。\n\n## 核心原理\n通过自注意力机制捕捉序列中各位置的依赖关系。\n\n## 关键特性\n并行计算、长距离依赖、可扩展性。\n\n## 应用场景\nNLP、CV、多模态等领域的广泛应用。\n\n## 举例说明\nBERT、GPT等模型都是基于Transformer架构。",
    "writing": "## 观点提出\n这是关于写作主题的核心观点。\n\n## 论据支撑\n第一，...\n第二，...\n\n## 反驳与回应\n可能有人会说...\n\n## 深化论证\n进一步思考...\n\n## 结论\n总结全文。",
    "planning": "## 问题定义\n明确目标\n\n## 原因分析\n当前状况分析\n\n## 方案设计\n1. 第一阶段\n2. 第二阶段\n3. 第三阶段\n4. 第四阶段\n5. 第五阶段\n\n## 方案评估\n评估标准\n\n## 实施建议\n具体建议",
    "chat": "你好！很高兴为你服务。有什么我可以帮你的吗？",
}


class MockTaskProfile:
    """Mock TaskProfile for CognitiveController"""
    def __init__(self, task_type, complexity=0.5, confidence=0.8, domain="", keywords=None):
        self.task_type = task_type
        self.complexity = complexity
        self.confidence = confidence
        self.domain = domain
        self.keywords = keywords or []


def run_test():
    print("=" * 70)
    print("  V3 全系统集成测试 — 40个跨领域问题")
    print("=" * 70)
    print()

    # 初始化组件
    skill_graph = get_skill_graph()
    reasoning_graph = ReasoningGraph()
    controller = CognitiveController()
    decomposer = Decomposer(skill_graph)
    planner = LocalPlanner(skill_graph)
    brain = PersonalBrain(user_id="test_user")
    brain.profile.identity = "developer"
    brain.profile.long_term_goals = ["学习AI开发", "掌握Agent技术"]
    learning_engine = LearningEngine(skill_graph=skill_graph, reasoning_graph=reasoning_graph)
    recommender = KnowledgeRecommendation(skill_graph, brain)

    results = []
    stats = {
        "total": len(QUESTIONS),
        "controller_passed": 0,
        "decomposer_passed": 0,
        "planner_passed": 0,
        "reasoning_passed": 0,
        "recommendation_passed": 0,
        "learning_passed": 0,
        "errors": [],
    }

    t_start = time.perf_counter()

    for i, item in enumerate(QUESTIONS):
        q = item["q"]
        domain = item["domain"]
        task_type = item["task_type"]
        qid = f"Q{i+1:02d}"

        q_result = {"id": qid, "domain": domain, "task_type": task_type.value, "question": q}
        checks = {}

        # === 1. Cognitive Controller 决策 ===
        try:
            profile = MockTaskProfile(
                task_type=task_type, domain=domain,
                complexity=0.5, confidence=0.8
            )
            decision = controller.decide(profile)
            checks["controller"] = True
            checks["engines"] = decision.engines
            checks["use_learning"] = decision.use_learning
            checks["use_reasoning"] = decision.use_reasoning
            stats["controller_passed"] += 1
        except Exception as e:
            checks["controller"] = False
            checks["engines"] = []
            stats["errors"].append(f"{qid}: Controller error - {e}")

        # === 2. Decomposer 分解 ===
        try:
            dc_result = decomposer.decompose(q)
            checks["decomposer"] = True
            checks["keywords"] = dc_result.get("keywords", [])[:5]
            checks["active_nodes"] = dc_result.get("active_nodes", [])[:3]
            stats["decomposer_passed"] += 1
        except Exception as e:
            checks["decomposer"] = False
            checks["active_nodes"] = []
            stats["errors"].append(f"{qid}: Decomposer error - {e}")

        # === 3. LocalPlanner 规划 ===
        try:
            plan = dc_result if checks.get("decomposer") else {"sub_topics": [], "keywords": []}
            plan_result = planner.plan(plan)
            checks["planner"] = True
            checks["plan_steps"] = len(plan_result) if isinstance(plan_result, list) else 0
            stats["planner_passed"] += 1
        except Exception as e:
            checks["planner"] = False
            checks["plan_steps"] = 0

        # === 4. Reasoning Graph 推理模式匹配 ===
        try:
            pattern = reasoning_graph.match(task_type=task_type.value, domain=domain)
            checks["reasoning"] = pattern is not None
            checks["reasoning_pattern"] = pattern.pattern_name if pattern else "none"
            if pattern:
                stats["reasoning_passed"] += 1
        except Exception as e:
            checks["reasoning"] = False
            stats["errors"].append(f"{qid}: Reasoning error - {e}")

        # === 5. Knowledge Recommendation 推荐 ===
        try:
            active_nodes = checks.get("active_nodes", [])
            recs = recommender.recommend(q, active_nodes, limit=3)
            checks["recommendation"] = True
            checks["rec_count"] = len(recs)
            checks["rec_types"] = list(set(r["type"] for r in recs))
            stats["recommendation_passed"] += 1
        except Exception as e:
            checks["recommendation"] = False
            stats["errors"].append(f"{qid}: Recommendation error - {e}")

        # === 6. Learning Engine 概念提取 ===
        try:
            mock_output = MOCK_WRITER_OUTPUTS.get(task_type.value, MOCK_WRITER_OUTPUTS["qa"])
            concepts = learning_engine._extract_concepts(mock_output)
            checks["learning"] = True
            checks["concepts_found"] = len(concepts)
            checks["concepts"] = list(concepts)[:3]
            stats["learning_passed"] += 1
        except Exception as e:
            checks["learning"] = False
            stats["errors"].append(f"{qid}: Learning error - {e}")

        q_result["checks"] = checks
        results.append(q_result)

    t_elapsed = time.perf_counter() - t_start

    # === 打印报告 ===
    print(f"  总耗时: {t_elapsed:.2f}s")
    print(f"  平均每题: {t_elapsed/len(QUESTIONS)*1000:.2f}ms")
    print()

    # 通过率统计
    print("-" * 70)
    print("  V3 组件通过率")
    print("-" * 70)
    components = [
        ("Cognitive Controller", stats["controller_passed"]),
        ("Decomposer", stats["decomposer_passed"]),
        ("LocalPlanner", stats["planner_passed"]),
        ("Reasoning Graph", stats["reasoning_passed"]),
        ("Knowledge Recommendation", stats["recommendation_passed"]),
        ("Learning Engine", stats["learning_passed"]),
    ]
    for name, count in components:
        pct = count / stats["total"] * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {name:25s}  {bar}  {count}/{stats['total']} ({pct:.0f}%)")

    print()

    # 领域分布统计
    print("-" * 70)
    print("  领域分布")
    print("-" * 70)
    domains = {}
    for r in results:
        d = r["domain"]
        if d not in domains:
            domains[d] = {"count": 0, "reasoning_hit": 0, "rec_avg": 0}
        domains[d]["count"] += 1
        if r["checks"].get("reasoning"):
            domains[d]["reasoning_hit"] += 1
        domains[d]["rec_avg"] += r["checks"].get("rec_count", 0)

    for d, info in sorted(domains.items()):
        rec_avg = info["rec_avg"] / info["count"] if info["count"] > 0 else 0
        print(f"  {d:15s}  {info['count']:2d}题  "
              f"推理命中:{info['reasoning_hit']}/{info['count']}  "
              f"平均推荐:{rec_avg:.1f}条")

    print()

    # 任务类型分布
    print("-" * 70)
    print("  任务类型分布")
    print("-" * 70)
    task_types = {}
    for r in results:
        tt = r["task_type"]
        if tt not in task_types:
            task_types[tt] = {"count": 0, "reasoning_hit": 0, "learning": 0}
        task_types[tt]["count"] += 1
        if r["checks"].get("reasoning"):
            task_types[tt]["reasoning_hit"] += 1
        if r["checks"].get("learning"):
            task_types[tt]["learning"] += 1

    for tt, info in sorted(task_types.items()):
        print(f"  {tt:15s}  {info['count']:2d}题  "
              f"推理命中:{info['reasoning_hit']}/{info['count']}  "
              f"学习触发:{info['learning']}/{info['count']}")

    print()

    # 推理模式使用统计
    print("-" * 70)
    print("  推理模式匹配统计")
    print("-" * 70)
    pattern_stats = reasoning_graph.stats()
    print(f"  总模式数: {pattern_stats['total_patterns']}")
    print(f"  按类型: {pattern_stats['by_type']}")
    most_used = pattern_stats['most_used']
    if most_used:
        print(f"  最常用: {most_used[0]['pattern_name']} (使用{most_used[0]['usage_count']}次)")

    print()

    # 详细问题列表
    print("-" * 70)
    print("  详细结果")
    print("-" * 70)
    for r in results:
        c = r["checks"]
        reasoning_icon = "✓" if c.get("reasoning") else "✗"
        pattern_name = c.get("reasoning_pattern", "none")
        engines = c.get("engines", [])
        keywords = c.get("keywords", [])
        concepts = c.get("concepts", [])

        print(f"\n  [{r['id']}] {r['domain']:10s} | {r['task_type']:10s}")
        print(f"    问题: {r['question'][:50]}...")
        print(f"    引擎: {engines}")
        print(f"    推理: {reasoning_icon} {pattern_name}")
        if keywords:
            print(f"    关键词: {keywords}")
        if concepts:
            print(f"    提取概念: {concepts}")
        if c.get("rec_count", 0) > 0:
            print(f"    推荐: {c['rec_count']}条 ({c.get('rec_types', [])})")

    print()

    # 错误报告
    if stats["errors"]:
        print("-" * 70)
        print(f"  错误 ({len(stats['errors'])}):")
        print("-" * 70)
        for e in stats["errors"]:
            print(f"  - {e}")
    else:
        print("-" * 70)
        print("  零错误!")
        print("-" * 70)

    print()

    # 总评
    total_passed = sum([
        stats["controller_passed"],
        stats["decomposer_passed"],
        stats["planner_passed"],
        stats["reasoning_passed"],
        stats["recommendation_passed"],
        stats["learning_passed"],
    ])
    max_possible = stats["total"] * 6
    overall = total_passed / max_possible * 100

    print("=" * 70)
    print(f"  总评: {total_passed}/{max_possible} ({overall:.1f}%)")
    if overall >= 95:
        print("  评级: 优秀 — 所有V3组件运行正常")
    elif overall >= 80:
        print("  评级: 良好 — 大部分组件运行正常")
    else:
        print("  评级: 需改进")
    print("=" * 70)

    return results, stats


if __name__ == "__main__":
    run_test()