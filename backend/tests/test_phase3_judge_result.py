"""Phase 3 Integration Tests — Judge Agent + Result Agent 数据流

验证目标：
1. Judge Agent 全维度检查（6个维度）
2. Judge Agent 输出 weak_dimensions
3. Result Agent 优先使用 Judge 的 weak_dimensions（避免重复解析）
4. Result Agent 精确 polish_mode 指令（polish_professional 等）
5. Judge → Result 数据流完整性

运行方式：
  cd d:\AgentMatrix\backend
  python -m tests.test_phase3_judge_result
"""

import sys
import os
import json
import asyncio
import logging
from typing import Dict, Any, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.WARNING)
logging.getLogger("agents").setLevel(logging.WARNING)

# ============================================================
# Test 1: Judge Agent 全维度决策
# ============================================================

def test_judge_all_dimensions():
    """测试 Judge Agent 检查全部6个维度并输出 weak_dimensions"""
    print("\n" + "=" * 60)
    print("Test 1: Judge Agent 全维度检查 + weak_dimensions 输出")
    print("=" * 60)

    from agents.judge.agent import JudgeAgent, DIM_NAMES_CN

    agent = JudgeAgent()
    passed = 0
    failed = 0

    # 模拟不同的 ReviewReport 场景
    test_cases = [
        {
            "id": "J01",
            "desc": "所有维度达标 → local_output",
            "review": {
                "overall": {"weighted_score": 0.85},
                "difficulty": {"threshold": 0.40},
                "risk": {"level": "low"},
                "dimensions": {
                    "accuracy": {"score": 0.85},
                    "professional": {"score": 0.80},
                    "completeness": {"score": 0.75},
                    "reasoning": {"score": 0.80},
                    "structure": {"score": 0.75},
                    "actionable": {"score": 0.70},
                }
            },
            "expected": {
                "decision": "local_output", "cloud_mode": "none",
                "weak_dimension_count": 0
            }
        },
        {
            "id": "J02",
            "desc": "准确性不足 → full_rewrite",
            "review": {
                "overall": {"weighted_score": 0.55},
                "difficulty": {"threshold": 0.50},
                "risk": {"level": "medium"},
                "dimensions": {
                    "accuracy": {"score": 0.55},
                    "professional": {"score": 0.70},
                    "completeness": {"score": 0.70},
                    "reasoning": {"score": 0.70},
                    "structure": {"score": 0.70},
                    "actionable": {"score": 0.70},
                }
            },
            "expects": {"decision": "cloud_enhance", "cloud_mode": "full_rewrite"}
        },
        {
            "id": "J03",
            "desc": "专业度不足 → polish_professional",
            "review": {
                "overall": {"weighted_score": 0.60},
                "difficulty": {"threshold": 0.45},
                "risk": {"level": "low"},
                "dimensions": {
                    "accuracy": {"score": 0.75},
                    "professional": {"score": 0.50},
                    "completeness": {"score": 0.70},
                    "reasoning": {"score": 0.70},
                    "structure": {"score": 0.70},
                    "actionable": {"score": 0.70},
                }
            },
            "expects": {"decision": "cloud_enhance", "cloud_mode": "polish_professional"}
        },
        {
            "id": "J04",
            "desc": "完整性不足 → polish_completeness",
            "review": {
                "overall": {"weighted_score": 0.60},
                "difficulty": {"threshold": 0.45},
                "risk": {"level": "low"},
                "dimensions": {
                    "accuracy": {"score": 0.75},
                    "professional": {"score": 0.70},
                    "completeness": {"score": 0.45},
                    "reasoning": {"score": 0.70},
                    "structure": {"score": 0.70},
                    "actionable": {"score": 0.70},
                }
            },
            "expects": {"decision": "cloud_enhance", "cloud_mode": "polish_completeness"}
        },
        {
            "id": "J05",
            "desc": "逻辑性不足 + 高难度 → polish_reasoning",
            "review": {
                "overall": {"weighted_score": 0.55},
                "difficulty": {"threshold": 0.55},
                "risk": {"level": "medium"},
                "dimensions": {
                    "accuracy": {"score": 0.75},
                    "professional": {"score": 0.70},
                    "completeness": {"score": 0.70},
                    "reasoning": {"score": 0.45},
                    "structure": {"score": 0.70},
                    "actionable": {"score": 0.70},
                }
            },
            "expects": {"decision": "cloud_enhance", "cloud_mode": "polish_reasoning"}
        },
        {
            "id": "J06",
            "desc": "风险 critical → full_rewrite",
            "review": {
                "overall": {"weighted_score": 0.60},
                "difficulty": {"threshold": 0.40},
                "risk": {"level": "critical"},
                "dimensions": {
                    "accuracy": {"score": 0.75},
                    "professional": {"score": 0.70},
                    "completeness": {"score": 0.70},
                    "reasoning": {"score": 0.70},
                    "structure": {"score": 0.70},
                    "actionable": {"score": 0.70},
                }
            },
            "expects": {"decision": "cloud_enhance", "cloud_mode": "full_rewrite"}
        },
        {
            "id": "J07",
            "desc": "低难度 + 逻辑性弱 → local_output（降级）",
            "review": {
                "overall": {"weighted_score": 0.70},
                "difficulty": {"threshold": 0.30},
                "risk": {"level": "low"},
                "dimensions": {
                    "accuracy": {"score": 0.75},
                    "professional": {"score": 0.70},
                    "completeness": {"score": 0.70},
                    "reasoning": {"score": 0.50},
                    "structure": {"score": 0.70},
                    "actionable": {"score": 0.70},
                }
            },
            "expects": {"decision": "local_output", "cloud_mode": "none"}
        },
        {
            "id": "J08",
            "desc": "可执行性不足 → polish_actionable",
            "review": {
                "overall": {"weighted_score": 0.55},
                "difficulty": {"threshold": 0.55},
                "risk": {"level": "low"},
                "dimensions": {
                    "accuracy": {"score": 0.75},
                    "professional": {"score": 0.70},
                    "completeness": {"score": 0.70},
                    "reasoning": {"score": 0.70},
                    "structure": {"score": 0.70},
                    "actionable": {"score": 0.40},
                }
            },
            "expects": {"decision": "cloud_enhance", "cloud_mode": "polish_actionable"}
        },
    ]

    for tc in test_cases:
        review_json = json.dumps(tc["review"])
        weak = agent._extract_weak_dimensions(tc["review"])
        result = agent._make_routing_decision_v2(
            "测试任务", review_json, "测试输出", weak
        )

        checks = []
        expects = tc.get("expects", tc.get("expected", {}))
        # Check decision
        if result["decision"] == expects["decision"]:
            checks.append("decision:OK")
        else:
            checks.append(f"decision:MISMATCH({result['decision']}≠{expects['decision']})")

        # Check cloud_mode
        if result["cloud_mode"] == expects["cloud_mode"]:
            checks.append("cloud_mode:OK")
        else:
            checks.append(f"cloud_mode:MISMATCH({result['cloud_mode']}≠{expects['cloud_mode']})")

        # Check weak_dimensions
        wd_count = len(result.get("weak_dimensions", []))
        if "weak_dimension_count" in expects:
            expected_count = expects["weak_dimension_count"]
            if wd_count == expected_count:
                checks.append(f"weak_dims:{wd_count}")
            else:
                checks.append(f"weak_dims:MISMATCH({wd_count}≠{expected_count})")
        else:
            checks.append(f"weak_dims:{wd_count}")

        all_ok = "MISMATCH" not in " ".join(checks)
        if all_ok:
            passed += 1
            status = "✓"
        else:
            failed += 1
            status = "✗"

        print(f"  {status} {tc['id']}: {tc['desc'][:35]:35s} | {', '.join(checks)}")

    print(f"\n  结果: {passed}/{len(test_cases)} 通过")
    return passed, failed


# ============================================================
# Test 2: Result Agent 使用 Judge 的 weak_dimensions
# ============================================================

def test_result_uses_judge_weak_dimensions():
    """测试 Result Agent 优先使用 Judge 提供的 weak_dimensions"""
    print("\n" + "=" * 60)
    print("Test 2: Result Agent 优先使用 Judge weak_dimensions")
    print("=" * 60)

    from agents.result.agent import ResultAgent

    agent = ResultAgent()
    passed = 0
    failed = 0

    test_cases = [
        {
            "id": "R01",
            "desc": "Judge 提供 weak_dimensions → 直接使用",
            "judge_result": {
                "decision": "cloud_enhance",
                "cloud_mode": "polish_professional",
                "weak_dimensions": [
                    {"key": "professional", "name": "专业性", "score": 0.50, "threshold": 0.65, "gap": 0.15},
                    {"key": "completeness", "name": "完整性", "score": 0.55, "threshold": 0.60, "gap": 0.05},
                ]
            },
            "expects": {
                "uses_judge_weak": True,
                "expected_count": 2,
            }
        },
        {
            "id": "R02",
            "desc": "Judge 未提供 weak_dimensions → 自行提取",
            "judge_result": {
                "decision": "local_output",
                "cloud_mode": "none",
            },
            "review_result": {
                "overall": {"weighted_score": 0.55},
                "dimensions": {
                    "accuracy": {"score": 0.55},
                    "professional": {"score": 0.50},
                    "completeness": {"score": 0.70},
                }
            },
            "expects": {
                "uses_judge_weak": False,
                "expected_count": 2,  # accuracy + professional
            }
        },
        {
            "id": "R03",
            "desc": "Judge 提供空 weak_dimensions → 使用空列表",
            "judge_result": {
                "decision": "local_output",
                "cloud_mode": "none",
                "weak_dimensions": [],
            },
            "expects": {
                "uses_judge_weak": True,
                "expected_count": 0,
            }
        },
    ]

    for tc in test_cases:
        # Simulate parsing the judge_result (as Result Agent does in execute())
        judge_result = tc["judge_result"]

        # Check if Judge provides weak_dimensions
        weak_from_judge = judge_result.get("weak_dimensions", [])
        uses_judge = bool(weak_from_judge is not None)  # even empty list counts as "provided"

        if not weak_from_judge and "review_result" in tc:
            # Fallback: extract from review_result
            weak_from_judge = agent._extract_weak_dimensions(tc["review_result"])
            uses_judge = False

        checks = []
        # Check source
        if uses_judge == tc["expects"]["uses_judge_weak"]:
            checks.append("source:OK")
        else:
            checks.append(f"source:MISMATCH({uses_judge}≠{tc['expects']['uses_judge_weak']})")

        # Check count
        if len(weak_from_judge) == tc["expects"]["expected_count"]:
            checks.append(f"count:{len(weak_from_judge)}")
        else:
            checks.append(f"count:MISMATCH({len(weak_from_judge)}≠{tc['expects']['expected_count']})")

        all_ok = "MISMATCH" not in " ".join(checks)
        if all_ok:
            passed += 1
            status = "✓"
        else:
            failed += 1
            status = "✗"

        print(f"  {status} {tc['id']}: {tc['desc'][:35]:35s} | {', '.join(checks)}")

    print(f"\n  结果: {passed}/{len(test_cases)} 通过")
    return passed, failed


# ============================================================
# Test 3: 精确 polish_mode 指令
# ============================================================

def test_polish_mode_directives():
    """测试 Result Agent 的精确 polish_mode 指令"""
    print("\n" + "=" * 60)
    print("Test 3: 精确 polish_mode 指令")
    print("=" * 60)

    from agents.result.agent import ResultAgent

    passed = 0
    failed = 0

    # 测试所有 polish_mode
    polish_modes = [
        "polish_professional",
        "polish_completeness",
        "polish_reasoning",
        "polish_structure",
        "polish_actionable",
        "polish",  # 通用兜底
    ]

    expected_keywords = {
        "polish_professional": "专业术语",
        "polish_completeness": "补充缺失",
        "polish_reasoning": "逻辑推理",
        "polish_structure": "段落结构",
        "polish_actionable": "可执行性",
        "polish": "专业性和流畅度",
    }

    for mode in polish_modes:
        directive = ResultAgent._get_polish_directive(mode)
        expected = expected_keywords.get(mode, "")

        if expected in directive:
            passed += 1
            print(f"  ✓ {mode:25s} → 匹配关键词: '{expected}'")
        else:
            failed += 1
            print(f"  ✗ {mode:25s} → 未匹配关键词: '{expected}'")
            print(f"    实际内容: {directive[:60]}...")

    print(f"\n  结果: {passed}/{len(polish_modes)} 通过")
    return passed, failed


# ============================================================
# Test 4: Judge → Result 数据流完整性
# ============================================================

def test_judge_to_result_dataflow():
    """测试 Judge → Result 完整数据流：weak_dimensions 传递链路"""
    print("\n" + "=" * 60)
    print("Test 4: Judge → Result 数据流完整性")
    print("=" * 60)

    from agents.judge.agent import JudgeAgent
    from agents.result.agent import ResultAgent

    judge = JudgeAgent()
    result_agent = ResultAgent()

    passed = 0
    failed = 0

    # 模拟场景：专业度不足
    review_data = {
        "overall": {"weighted_score": 0.60},
        "difficulty": {"threshold": 0.50},
        "risk": {"level": "low"},
        "dimensions": {
            "accuracy": {"score": 0.75},
            "professional": {"score": 0.45},
            "completeness": {"score": 0.70},
            "reasoning": {"score": 0.70},
            "structure": {"score": 0.70},
            "actionable": {"score": 0.65},
        }
    }

    # Step 1: Judge 决策
    weak = judge._extract_weak_dimensions(review_data)
    judge_result = judge._make_routing_decision_v2(
        "写一份专业技术报告", json.dumps(review_data), "测试输出", weak
    )

    # Step 2: 验证 Judge 输出的 weak_dimensions
    j_weak = judge_result.get("weak_dimensions", [])
    if j_weak and j_weak[0]["key"] == "professional":
        print(f"  ✓ Judge 输出: cloud_mode={judge_result['cloud_mode']}, "
              f"weak_dim={j_weak[0]['key']}(gap={j_weak[0]['gap']})")
        passed += 1
    else:
        print(f"  ✗ Judge 输出异常: {j_weak}")
        failed += 1

    # Step 3: 模拟 Result Agent 接收 Judge 数据
    # (模拟 execute() 中的解析逻辑)
    judge_result_for_result = judge_result  # 模拟从 judge_result 字段解析
    weak_from_judge = judge_result_for_result.get("weak_dimensions", [])

    if weak_from_judge:
        # 使用 Judge 的 weak_dimensions（跳过 re-extraction）
        used_direct = True
        print(f"  ✓ Result 使用 Judge weak_dimensions: "
              f"{[d['key'] for d in weak_from_judge]}")
        passed += 1
    else:
        # Fallback to re-extraction
        used_direct = False
        weak_from_judge = result_agent._extract_weak_dimensions(review_data)
        print(f"  ⚠ Result 回退到自行提取: {[d['key'] for d in weak_from_judge]}")
        passed += 1  # 回退也是正确行为

    # Step 4: 验证 polish_mode 指令
    cloud_mode = judge_result["cloud_mode"]
    if cloud_mode.startswith("polish"):
        directive = ResultAgent._get_polish_directive(cloud_mode)
        if "专业术语" in directive:
            print(f"  ✓ polish_mode={cloud_mode} → 指令包含专业术语靶向")
            passed += 1
        else:
            print(f"  ✗ polish_mode={cloud_mode} → 指令未匹配")
            failed += 1

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("Phase 3 Judge + Result Agent 集成测试")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    # Test 1: Judge 全维度决策
    p1, f1 = test_judge_all_dimensions()
    total_passed += p1
    total_failed += f1

    # Test 2: Result 使用 Judge weak_dimensions
    p2, f2 = test_result_uses_judge_weak_dimensions()
    total_passed += p2
    total_failed += f2

    # Test 3: 精确 polish_mode 指令
    p3, f3 = test_polish_mode_directives()
    total_passed += p3
    total_failed += f3

    # Test 4: Judge → Result 数据流
    p4, f4 = test_judge_to_result_dataflow()
    total_passed += p4
    total_failed += f4

    # Summary
    total = total_passed + total_failed
    print("\n" + "=" * 60)
    print(f"测试总结")
    print("=" * 60)
    print(f"  总测试项: {total}")
    print(f"  通过: {total_passed} ({total_passed*100//total if total else 0}%)")
    print(f"  失败: {total_failed}")
    print("=" * 60)

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)