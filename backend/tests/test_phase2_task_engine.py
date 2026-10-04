"""Phase 2 Integration Tests — Task Engine (TaskClassifier + Knowledge/Writer 集成)

验证目标：
1. TaskClassifier 分类准确率（6种 TaskType）
2. Knowledge Agent 输出 task_type_v2 + task_data
3. Writer Agent 按 TaskType 调整行为（min_length、template）
4. Phase 1 遗留问题修复：TW03（模板）+ RG01（短回答）

运行方式：
  cd d:\AgentMatrix\backend
  python -m tests.test_phase2_task_engine
"""

import sys
import os
import json
import asyncio
import time
import logging
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 抑制日志噪音
logging.basicConfig(level=logging.WARNING)
logging.getLogger("agents").setLevel(logging.WARNING)
logging.getLogger("core").setLevel(logging.WARNING)

# ============================================================
# Test Data
# ============================================================

# 18 个测试用例覆盖 6 种 TaskType，每种 3 个
TEST_CASES = [
    # === CODING (编码类) ===
    {"id": "TC01", "input": "写一个快速排序的Python实现", "expected_type": "coding", "expected_handler": "CodeHandler"},
    {"id": "TC02", "input": "用Java实现二分查找算法", "expected_type": "coding", "expected_handler": "CodeHandler"},
    {"id": "TC03", "input": "React组件如何实现状态管理", "expected_type": "coding", "expected_handler": "CodeHandler"},

    # === PLANNING (规划类) ===
    {"id": "TC04", "input": "设计一个校园马拉松活动方案", "expected_type": "planning", "expected_handler": "TemplateHandler", "expected_template": True},
    {"id": "TC05", "input": "写一份项目总结报告", "expected_type": "planning", "expected_handler": "TemplateHandler", "expected_template": True},
    {"id": "TC06", "input": "制定学习计划", "expected_type": "planning", "expected_handler": "TemplateHandler", "expected_template": True},

    # === ANALYSIS (分析类) ===
    {"id": "TC07", "input": "SWOT分析一下这个项目", "expected_type": "analysis", "expected_handler": "FactQuestionHandler"},
    {"id": "TC08", "input": "评估AI技术对教育的影响", "expected_type": "analysis", "expected_handler": "FactQuestionHandler"},
    {"id": "TC09", "input": "比较一下Python和Java的优缺点", "expected_type": "analysis", "expected_handler": "FactQuestionHandler"},

    # === WRITING (创意写作类) ===
    {"id": "TC10", "input": "写一首关于春天的诗", "expected_type": "writing", "expected_handler": "CreativeWritingHandler"},
    {"id": "TC11", "input": "写一封情书", "expected_type": "writing", "expected_handler": "CreativeWritingHandler"},
    {"id": "TC12", "input": "写一篇关于AI的短文", "expected_type": "writing", "expected_handler": "CreativeWritingHandler"},

    # === QA (问答类) ===
    {"id": "TC13", "input": "什么是机器学习", "expected_type": "qa", "expected_handler": "FactQuestionHandler"},
    {"id": "TC14", "input": "Docker和虚拟机有什么区别", "expected_type": "qa", "expected_handler": "FactQuestionHandler"},
    {"id": "TC15", "input": "用一句话介绍Git", "expected_type": "qa", "expected_handler": "FactQuestionHandler"},

    # === CHAT (闲聊类) ===
    {"id": "TC16", "input": "你好", "expected_type": "chat", "expected_handler": "SimpleConversationHandler"},
    {"id": "TC17", "input": "今天天气真好", "expected_type": "chat", "expected_handler": "SimpleConversationHandler"},
    {"id": "TC18", "input": "推荐一部好看的电影", "expected_type": "chat", "expected_handler": "SimpleConversationHandler"},
]


# ============================================================
# Test: TaskClassifier 独立测试
# ============================================================

def test_task_classifier():
    """测试 TaskClassifier 分类准确率"""
    print("\n" + "=" * 60)
    print("Test 1: TaskClassifier 分类准确率")
    print("=" * 60)

    from core.skill_engine.task_engine import get_task_classifier

    classifier = get_task_classifier()
    passed = 0
    failed = 0
    results = []

    for tc in TEST_CASES:
        profile = classifier.classify(tc["input"])
        actual_type = profile.task_type.value
        expected_type = tc["expected_type"]
        match = actual_type == expected_type

        if match:
            passed += 1
            status = "✓"
        else:
            failed += 1
            status = "✗"

        results.append({
            "id": tc["id"],
            "input": tc["input"][:40],
            "expected": expected_type,
            "actual": actual_type,
            "confidence": profile.confidence,
            "matched": profile.matched_patterns[:3],
            "handler": profile.handler,
            "template": profile.template,
            "status": "PASS" if match else "FAIL"
        })
        print(f"  {status} {tc['id']}: {tc['input'][:40]:40s} → {actual_type:10s} "
              f"(conf={profile.confidence:.2f}, handler={profile.handler})")

    print(f"\n  结果: {passed}/{len(TEST_CASES)} 通过 ({passed*100//len(TEST_CASES)}%)")
    return results, passed, failed


# ============================================================
# Test: Knowledge Agent 集成
# ============================================================

async def test_knowledge_agent_integration():
    """测试 Knowledge Agent 是否输出 task_type_v2 和 task_data"""
    print("\n" + "=" * 60)
    print("Test 2: Knowledge Agent 集成 (task_type_v2 + task_data)")
    print("=" * 60)

    from agents.knowledge.agent import KnowledgeAgent
    from agents.base.agent import AgentInput

    agent = KnowledgeAgent()
    passed = 0
    failed = 0

    # 选取 6 个代表性用例（每种 TaskType 一个）
    sample_cases = [tc for tc in TEST_CASES if tc["id"] in
                    ["TC01", "TC04", "TC07", "TC10", "TC13", "TC16"]]

    for tc in sample_cases:
        try:
            output = await agent.execute(AgentInput(content=tc["input"]))
            parsed = json.loads(output.content)

            task_type_v2 = parsed.get("task_type_v2", "N/A")
            task_data = parsed.get("task_data", {})
            expected_type = tc["expected_type"]

            checks = []
            # Check 1: task_type_v2 存在
            if task_type_v2 and task_type_v2 != "N/A":
                checks.append("task_type_v2:OK")
            else:
                checks.append("task_type_v2:MISSING")

            # Check 2: task_type_v2 匹配预期
            if task_type_v2 == expected_type:
                checks.append("type_match:OK")
            else:
                checks.append(f"type_match:MISMATCH({task_type_v2}≠{expected_type})")

            # Check 3: task_data 存在
            if task_data:
                checks.append("task_data:OK")
            else:
                checks.append("task_data:EMPTY")

            # Check 4: task_data 包含关键字段
            if task_data.get("handler"):
                checks.append(f"handler:{task_data['handler']}")
            if "template" in task_data:
                checks.append(f"template:{task_data['template']}")
            if "min_length" in task_data:
                checks.append(f"min_length:{task_data['min_length']}")

            all_ok = "MISSING" not in str(checks) and "MISMATCH" not in str(checks)
            if all_ok:
                passed += 1
                status = "✓"
            else:
                failed += 1
                status = "✗"

            print(f"  {status} {tc['id']}: {tc['input'][:35]:35s} | {', '.join(checks)}")
        except Exception as e:
            failed += 1
            print(f"  ✗ {tc['id']}: {tc['input'][:35]:35s} | ERROR: {e}")

    print(f"\n  结果: {passed}/{len(sample_cases)} 通过")
    return passed, failed


# ============================================================
# Test: Writer Agent 按 TaskType 调整行为
# ============================================================

async def test_writer_task_type_behavior():
    """测试 Writer Agent 是否按 TaskType 调整行为"""
    print("\n" + "=" * 60)
    print("Test 3: Writer Agent 按 TaskType 调整行为")
    print("=" * 60)

    from agents.writer.agent import WriterAgent
    from agents.base.agent import AgentInput

    agent = WriterAgent()
    passed = 0
    failed = 0
    results = []

    # 模拟 Knowledge Agent 输出（包含 task_type_v2 + task_data）
    test_inputs = [
        {
            "id": "W01", "query": "写一个快速排序Python",
            "task_type_v2": "coding", "task_data": {
                "handler": "CodeHandler", "template": False, "min_length": 80
            },
            "checks": ["min_length>=80"]
        },
        {
            "id": "W02", "query": "设计一个校园马拉松活动方案",
            "task_type_v2": "planning", "task_data": {
                "handler": "TemplateHandler", "template": True, "min_length": 200
            },
            "checks": ["template", "min_length>=200"]
        },
        {
            "id": "W03", "query": "你好",
            "task_type_v2": "chat", "task_data": {
                "handler": "SimpleConversationHandler", "template": False, "min_length": 40
            },
            "checks": ["short_answer"]
        },
        {
            "id": "W04", "query": "写一首关于春天的诗",
            "task_type_v2": "writing", "task_data": {
                "handler": "CreativeWritingHandler", "template": False, "min_length": 60
            },
            "checks": ["creative"]
        },
        {
            "id": "W05", "query": "什么是机器学习",
            "task_type_v2": "qa", "task_data": {
                "handler": "FactQuestionHandler", "template": False, "min_length": 80
            },
            "checks": ["factual"]
        },
    ]

    for ti in test_inputs:
        try:
            # 构造模拟 Knowledge Agent 输出
            mock_knowledge = json.dumps({
                "task": ti["query"],
                "user_task": ti["query"],
                "original_question": ti["query"],
                "keywords": [],
                "knowledge_items": [],
                "knowledge_count": 0,
                "requirements": [],
                "outline": [],
                "task_type": "通用任务",
                "summary": f"用户需求：{ti['query']}",
                "skill_path": ["root", "daily"],
                "skill_domain": "daily",
                "skill_confidence": 0.5,
                "task_type_v2": ti["task_type_v2"],
                "task_data": ti["task_data"],
            })

            output = await agent.execute(AgentInput(content=mock_knowledge))
            parsed = agent._parse_knowledge_output(mock_knowledge)

            checks_ok = []
            # Check: task_type_v2 正确传递
            if parsed.get("task_type_v2") == ti["task_type_v2"]:
                checks_ok.append("task_type_v2:OK")
            else:
                checks_ok.append(f"task_type_v2:FAIL({parsed.get('task_type_v2')})")

            # Check: task_data 正确传递
            task_data = parsed.get("task_data", {})
            if task_data.get("template") == ti["task_data"].get("template"):
                checks_ok.append("template:OK")
            else:
                checks_ok.append("template:FAIL")

            if task_data.get("min_length") == ti["task_data"].get("min_length"):
                checks_ok.append("min_length:OK")
            else:
                checks_ok.append("min_length:FAIL")

            # Check: 内容长度
            if output.success and output.content:
                content_len = len(output.content)
                checks_ok.append(f"length:{content_len}")
            else:
                checks_ok.append(f"content:FAIL({output.message})")

            all_ok = "FAIL" not in str(checks_ok)
            if all_ok:
                passed += 1
                status = "✓"
            else:
                failed += 1
                status = "✗"

            print(f"  {status} {ti['id']}: {ti['query'][:35]:35s} | {', '.join(checks_ok)}")
            results.append({"id": ti["id"], "status": "PASS" if all_ok else "FAIL", "checks": checks_ok})

        except Exception as e:
            failed += 1
            print(f"  ✗ {ti['id']}: {ti['query'][:35]:35s} | ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n  结果: {passed}/{len(test_inputs)} 通过")
    return results, passed, failed


# ============================================================
# Test: Phase 1 遗留问题修复验证
# ============================================================

async def test_phase1_regression_fixes():
    """验证 Phase 1 遗留问题：TW03（模板） + RG01（短回答）"""
    print("\n" + "=" * 60)
    print("Test 4: Phase 1 遗留问题修复验证")
    print("=" * 60)

    from core.skill_engine.task_engine import get_task_classifier
    classifier = get_task_classifier()

    passed = 0
    failed = 0

    # TW03: "计划" 关键词应触发模板
    print("\n  --- TW03: 模板检测修复 ---")
    tw03_cases = [
        ("制定学习计划", True, "planning"),
        ("写一份工作计划", True, "planning"),
        ("项目计划", True, "planning"),
    ]
    for query, expect_template, expect_type in tw03_cases:
        profile = classifier.classify(query)
        ok = (profile.task_type.value == expect_type and profile.template == expect_template)
        if ok:
            passed += 1
            print(f"  ✓ '{query}' → type={profile.task_type.value}, template={profile.template}")
        else:
            failed += 1
            print(f"  ✗ '{query}' → type={profile.task_type.value}, template={profile.template} "
                  f"(expected type={expect_type}, template={expect_template})")

    # RG01: 简洁回答应有 min_length >= 40
    print("\n  --- RG01: 短回答改善 ---")
    rg01_cases = [
        ("用一句话介绍Git", "qa", 80),
        ("简要说明什么是Docker", "qa", 80),
        ("你好", "chat", 40),
    ]
    for query, expect_type, expect_min_length in rg01_cases:
        profile = classifier.classify(query)
        # QA 类型应有合理的 min_length（>= 40）
        ok = (profile.task_type.value == expect_type and profile.min_length >= 40)
        if ok:
            passed += 1
            print(f"  ✓ '{query}' → type={profile.task_type.value}, min_length={profile.min_length}")
        else:
            failed += 1
            print(f"  ✗ '{query}' → type={profile.task_type.value}, min_length={profile.min_length} "
                  f"(expected type={expect_type}, min_length>={expect_min_length})")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Phase 2 Task Engine 集成测试")
    print("=" * 60)
    start_time = time.time()

    total_passed = 0
    total_failed = 0

    # Test 1: TaskClassifier 独立测试
    results1, p1, f1 = test_task_classifier()
    total_passed += p1
    total_failed += f1

    # Test 2: Knowledge Agent 集成
    p2, f2 = await test_knowledge_agent_integration()
    total_passed += p2
    total_failed += f2

    # Test 3: Writer Agent 按 TaskType 调整行为
    results3, p3, f3 = await test_writer_task_type_behavior()
    total_passed += p3
    total_failed += f3

    # Test 4: Phase 1 遗留问题修复
    p4, f4 = await test_phase1_regression_fixes()
    total_passed += p4
    total_failed += f4

    # Summary
    elapsed = time.time() - start_time
    total = total_passed + total_failed
    print("\n" + "=" * 60)
    print(f"测试总结")
    print("=" * 60)
    print(f"  总测试项: {total}")
    print(f"  通过: {total_passed} ({total_passed*100//total if total else 0}%)")
    print(f"  失败: {total_failed}")
    print(f"  耗时: {elapsed:.1f}s")
    print("=" * 60)

    return total_failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)