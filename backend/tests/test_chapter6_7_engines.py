"""Chapter 6+7 Integration Tests — Review Engine + Template Engine

验证目标：
Ch6: ReviewEngine 独立评审 + 缓存 + Review Agent 委托
Ch7: TemplateEngine 模板加载 + 选择 + 渲染 + TemplateHandler 委托
"""

import sys
import os
import json
import asyncio
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.WARNING)
logging.getLogger("core").setLevel(logging.WARNING)

# ============================================================
# Ch6 Test: Review Engine
# ============================================================

def test_review_engine_standalone():
    """测试 ReviewEngine 独立评审（不依赖 Review Agent）"""
    print("\n" + "=" * 60)
    print("Ch6 Test 1: ReviewEngine 独立评审")
    print("=" * 60)

    from core.skill_engine.review_engine import ReviewEngine, ReviewCache, safe_float, clamp_score, normalize_score

    engine = ReviewEngine()
    passed = 0
    failed = 0

    test_cases = [
        {
            "id": "RE01", "desc": "短内容评审",
            "user_task": "你好", "summary": "问候",
            "output": "你好！有什么可以帮助你的吗？",
            "skill_path": ["root", "daily"],
            "checks": ["risk_low", "diff_simple"]
        },
        {
            "id": "RE02", "desc": "长内容 + 技术领域",
            "user_task": "写一个Python冒泡排序",
            "summary": "实现冒泡排序",
            "output": "## Python冒泡排序\n\n```python\ndef bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr\n```\n\n冒泡排序的时间复杂度为O(n²)，适用于小规模数据。",
            "skill_path": ["root", "tech", "ai"],
            "checks": ["code_bonus", "6_dims"]
        },
        {
            "id": "RE03", "desc": "商业方案 + 长内容",
            "user_task": "设计一个校园活动方案",
            "summary": "校园活动策划",
            "output": "## 校园活动方案\n\n### 活动背景\n本次活动旨在提升学生综合素质...\n\n### 活动目标\n1. 提升学生参与度 30%\n2. 建立社团合作机制\n\n### 活动流程\n1. 前期策划（2周）\n2. 宣传推广（1周）\n3. 活动执行（1天）\n\n### 预算\n- 场地：500元\n- 物料：300元\n- 人力：200元\n\n### 风险预案\n- 天气风险：备选室内场地\n- 参与度风险：设置激励机制",
            "skill_path": ["root", "business", "business.planning"],
            "checks": ["structure_bonus", "high_confidence"]
        },
    ]

    for tc in test_cases:
        report = engine.review(
            tc["user_task"], tc["summary"], tc["output"], tc["skill_path"]
        )

        checks_ok = []
        # Check: 6 dimensions
        dims = report.get("dimensions", {})
        if len(dims) == 6:
            checks_ok.append("6_dims")
        else:
            checks_ok.append(f"dims:{len(dims)}")

        # Check: has overall
        if "overall" in report:
            checks_ok.append(f"score:{report['overall']['weighted_score']:.2f}")

        # Check: has difficulty
        if "difficulty" in report:
            checks_ok.append(f"diff:{report['difficulty']['threshold']:.2f}")

        # Check: has risk
        if "risk" in report:
            checks_ok.append(f"risk:{report['risk']['level']}")

        # Check: has confidence
        if "confidence" in report:
            checks_ok.append(f"conf:{report['confidence']:.2f}")

        # Check: has issues/suggestions
        if "issues" in report and "suggestions" in report:
            checks_ok.append("issues+suggestions")

        all_ok = all(not c.startswith("dims:") for c in checks_ok)  # 无维度数量错误
        if all_ok:
            passed += 1
            status = "✓"
        else:
            failed += 1
            status = "✗"

        print(f"  {status} {tc['id']}: {tc['desc'][:35]:35s} | {', '.join(checks_ok)}")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


def test_review_cache():
    """测试 ReviewEngine 缓存"""
    print("\n" + "=" * 60)
    print("Ch6 Test 2: ReviewEngine 缓存")
    print("=" * 60)

    from core.skill_engine.review_engine import ReviewEngine, ReviewCache

    engine = ReviewEngine(enable_cache=True)
    passed = 0
    failed = 0

    user_task = "测试缓存任务"
    output = "这是测试输出内容，用于验证缓存机制是否正常工作"
    skill_path = ["root", "daily"]

    # 第一次评审
    r1 = engine.review(user_task, "摘要", output, skill_path, use_cache=True)
    # 第二次应命中缓存
    r2 = engine.review(user_task, "摘要", output, skill_path, use_cache=True)
    # 第三次（不同输入）不应命中缓存
    r3 = engine.review("不同任务", "摘要", output, skill_path, use_cache=True)

    # 验证缓存命中（同一对象引用）
    if r1 is r2:
        passed += 1
        print("  ✓ 缓存命中: 相同输入返回相同对象")
    else:
        failed += 1
        print("  ✗ 缓存未命中")

    if r1 is not r3:
        passed += 1
        print("  ✓ 缓存隔离: 不同输入返回不同对象")
    else:
        failed += 1
        print("  ✗ 缓存隔离失败")

    engine.clear_cache()
    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Ch7 Test: Template Engine
# ============================================================

def test_template_engine_loading():
    """测试 TemplateEngine 模板加载"""
    print("\n" + "=" * 60)
    print("Ch7 Test 3: TemplateEngine 模板加载")
    print("=" * 60)

    from core.skill_engine.template_engine import TemplateEngine, Template

    engine = TemplateEngine()
    templates = engine.get_all_templates()
    passed = 0
    failed = 0

    # 基本检查
    if len(templates) >= 5:
        passed += 1
        print(f"  ✓ {len(templates)} templates loaded")
    else:
        failed += 1
        print(f"  ✗ Only {len(templates)} templates (expected >= 5)")

    # 每个模板都有必要的字段
    for t in templates:
        if (t.meta.template_id and t.meta.name and t.sections
                and t.applicable.keywords and t.constraints):
            passed += 1
        else:
            failed += 1
            print(f"  ✗ {t.meta.template_id}: incomplete fields")

    # 验证模板 ID 唯一
    ids = [t.meta.template_id for t in templates]
    if len(ids) == len(set(ids)):
        passed += 1
        print(f"  ✓ All template IDs unique")
    else:
        failed += 1
        print(f"  ✗ Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}")

    # 验证模板包含 required sections
    for t in templates:
        required = t.required_sections
        if required:
            passed += 1
        else:
            failed += 1
            print(f"  ✗ {t.meta.template_id}: no required sections")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


def test_template_selection():
    """测试模板选择逻辑"""
    print("\n" + "=" * 60)
    print("Ch7 Test 4: TemplateEngine 模板选择")
    print("=" * 60)

    from core.skill_engine.template_engine import TemplateEngine

    engine = TemplateEngine()
    passed = 0
    failed = 0

    test_cases = [
        {
            "id": "TS01", "query": "设计一个校园活动方案",
            "task_type": "planning", "domain": "business",
            "expected": "business_plan"
        },
        {
            "id": "TS02", "query": "写一份项目总结报告",
            "task_type": "analysis", "domain": "business",
            "expected": "business_report"
        },
        {
            "id": "TS03", "query": "写一个商业提案",
            "task_type": "planning", "domain": "business",
            "expected": "business_proposal"
        },
        {
            "id": "TS04", "query": "整理会议纪要",
            "task_type": "planning", "domain": "business",
            "expected": "meeting_minutes"
        },
        {
            "id": "TS05", "query": "写一份需求文档",
            "task_type": "planning", "domain": "tech",
            "expected": "requirements_doc"
        },
        {
            "id": "TS06", "query": "随便写点东西",
            "task_type": "chat", "domain": "daily",
            "expected": None  # 无匹配
        },
    ]

    for tc in test_cases:
        template = engine.select_template(
            task_type=tc["task_type"],
            domain=tc["domain"],
            user_query=tc["query"]
        )
        actual = template.meta.template_id if template else None

        if actual == tc["expected"]:
            passed += 1
            print(f"  ✓ {tc['id']}: '{tc['query'][:25]}' → {actual}")
        else:
            failed += 1
            print(f"  ✗ {tc['id']}: '{tc['query'][:25]}' → {actual} (expected {tc['expected']})")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


def test_template_prompt_building():
    """测试模板 Prompt 构建"""
    print("\n" + "=" * 60)
    print("Ch7 Test 5: TemplateEngine Prompt 构建")
    print("=" * 60)

    from core.skill_engine.template_engine import TemplateEngine

    engine = TemplateEngine()
    passed = 0
    failed = 0

    template = engine.select_template(user_query="设计一个活动方案")
    if not template:
        print("  ✗ No template found")
        return 0, 1

    prompt = engine.build_template_prompt(
        template=template,
        user_task="设计一个校园活动方案",
        summary="校园活动策划背景信息"
    )

    checks = [
        ("包含用户需求", "设计一个校园活动方案" in prompt),
        ("包含背景信息", "校园活动策划背景信息" in prompt),
        ("包含模板名称", template.meta.name in prompt),
        ("包含必填章节", all(s.title in prompt for s in template.required_sections)),
        ("包含约束条件", any(c[:6] in prompt for c in template.constraints)),
        ("包含格式要求", "markdown" in prompt.lower()),
    ]

    for name, ok in checks:
        if ok:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Ch6+7 Integration: Agent 委托
# ============================================================

async def test_agent_delegation():
    """测试 Review/Writer Agent 委托给引擎"""
    print("\n" + "=" * 60)
    print("Ch6+7 Test 6: Agent 委托引擎")
    print("=" * 60)

    passed = 0
    failed = 0

    # Test Review Agent has review_engine
    from agents.review.agent import ReviewAgent
    ra = ReviewAgent()
    try:
        re = ra.review_engine
        if re:
            passed += 1
            print("  ✓ ReviewAgent.review_engine 可用")
        else:
            failed += 1
            print("  ✗ ReviewAgent.review_engine 为 None")
    except Exception as e:
        failed += 1
        print(f"  ✗ ReviewAgent.review_engine: {e}")

    # Test Writer Agent has template_engine
    from agents.writer.agent import WriterAgent
    wa = WriterAgent()
    try:
        te = wa.template_engine
        if te:
            passed += 1
            print("  ✓ WriterAgent.template_engine 可用")
        else:
            failed += 1
            print("  ✗ WriterAgent.template_engine 为 None")
    except Exception as e:
        failed += 1
        print(f"  ✗ WriterAgent.template_engine: {e}")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Chapter 6+7 Review Engine + Template Engine 集成测试")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    # Ch6: Review Engine
    p1, f1 = test_review_engine_standalone()
    total_passed += p1
    total_failed += f1

    p2, f2 = test_review_cache()
    total_passed += p2
    total_failed += f2

    # Ch7: Template Engine
    p3, f3 = test_template_engine_loading()
    total_passed += p3
    total_failed += f3

    p4, f4 = test_template_selection()
    total_passed += p4
    total_failed += f4

    p5, f5 = test_template_prompt_building()
    total_passed += p5
    total_failed += f5

    # Ch6+7: Agent delegation
    p6, f6 = await test_agent_delegation()
    total_passed += p6
    total_failed += f6

    # Summary
    total = total_passed + total_failed
    print("\n" + "=" * 60)
    print(f"Chapter 6+7 测试总结")
    print("=" * 60)
    print(f"  总测试项: {total}")
    print(f"  通过: {total_passed} ({total_passed*100//total if total else 0}%)")
    print(f"  失败: {total_failed}")
    print("=" * 60)

    return total_failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)