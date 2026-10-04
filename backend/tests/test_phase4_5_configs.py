"""Phase 4+5 Integration Tests — V2 Scoring Configs + Skill Book 完整性

验证目标：
P4: Review Agent 正确加载并使用 V2 评分配置
P5: 技能书文件完整性（tree.yaml 中所有节点都有对应 skill.yaml）
"""

import sys
import os
import yaml
import logging
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.WARNING)

SKILLS_DIR = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'skills')

# ============================================================
# Test 1: V2 评分配置加载验证
# ============================================================

def test_v2_scoring_configs():
    """测试 Review Agent 的 V2 评分配置加载"""
    print("\n" + "=" * 60)
    print("P4 Test 1: V2 评分配置加载验证")
    print("=" * 60)

    from agents.review.agent import ReviewAgent

    agent = ReviewAgent()
    passed = 0
    failed = 0

    # 1. 加载 V2 配置
    v2 = agent._load_v2_configs()
    checks = [
        ("base config loaded", v2.get("base") is not None),
        ("difficulty config loaded", v2.get("difficulty") is not None),
        ("tech config loaded", v2.get("tech") is not None),
    ]
    for name, ok in checks:
        if ok:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}")

    # 2. base_scoring 包含6维度
    base = v2.get("base", {})
    dims = base.get("dimensions", {})
    expected_dims = ["accuracy", "professional", "completeness", "reasoning", "structure", "actionable"]
    for dim in expected_dims:
        if dim in dims:
            passed += 1
            print(f"  ✓ base_scoring: {dim} (weight={dims[dim].get('weight', 'N/A')})")
        else:
            failed += 1
            print(f"  ✗ base_scoring: {dim} MISSING")

    # 3. difficulty_matrix 包含领域难度
    diff = v2.get("difficulty", {})
    domains = diff.get("domain_base_difficulty", {})
    if domains:
        passed += 1
        print(f"  ✓ difficulty_matrix: {len(domains)} domains defined")
    else:
        failed += 1
        print(f"  ✗ difficulty_matrix: NO domains")

    # 4. tech_scoring 包含子域调整
    tech = v2.get("tech", {})
    subdomains = tech.get("subdomain_adjustments", {})
    if subdomains:
        passed += 1
        print(f"  ✓ tech_scoring: {len(subdomains)} subdomain adjustments")
    else:
        failed += 1
        print(f"  ✗ tech_scoring: NO subdomain adjustments")

    # 5. _review_content_v2 使用 V2 pass_threshold
    try:
        result = agent._review_content_v2(
            "测试任务", "测试摘要", "测试输出内容",
            ["root", "daily"], {"accuracy": 0.25, "professional": 0.20}
        )
        if "dimensions" in result and len(result["dimensions"]) == 6:
            passed += 1
            print(f"  ✓ _review_content_v2: 6 dimensions in output")
        else:
            failed += 1
            print(f"  ✗ _review_content_v2: wrong dimension count")
    except Exception as e:
        failed += 1
        print(f"  ✗ _review_content_v2: ERROR {e}")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Test 2: Review Agent V2 路径完整性
# ============================================================

def test_review_v2_pipeline():
    """测试 Review Agent 的 V2 完整评审管线"""
    print("\n" + "=" * 60)
    print("P4 Test 2: Review Agent V2 完整评审管线")
    print("=" * 60)

    from agents.review.agent import ReviewAgent

    agent = ReviewAgent()
    passed = 0
    failed = 0

    test_cases = [
        {
            "id": "V2-P01",
            "desc": "技术领域 + 代码",
            "user_task": "用Python实现一个二分查找算法",
            "summary": "实现二分查找",
            "output": "```python\ndef binary_search(arr, target):\n    left, right = 0, len(arr) - 1\n    while left <= right:\n        mid = (left + right) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1\n```",
            "skill_path": ["root", "tech"],
            "checks": ["code_block_bonus", "6_dims"]
        },
        {
            "id": "V2-P02",
            "desc": "商业方案 + 长内容",
            "user_task": "设计一个校园活动方案",
            "summary": "校园活动策划",
            "output": "## 活动方案\n\n### 活动背景\n本次校园活动旨在提升学生参与度...\n\n### 活动流程\n1. 前期准备\n2. 执行阶段\n3. 收尾总结\n\n### 预算安排\n- 场地: 500元\n- 物料: 300元\n- 人员: 200元\n\n### 风险评估\n- 天气风险\n- 参与度风险",
            "skill_path": ["root", "business", "business.planning"],
            "checks": ["structure_bonus", "6_dims"]
        },
        {
            "id": "V2-P03",
            "desc": "简单对话",
            "user_task": "你好",
            "summary": "问候",
            "output": "你好！有什么可以帮助你的吗？",
            "skill_path": ["root", "daily"],
            "checks": ["simple_report", "high_score"]
        },
    ]

    for tc in test_cases:
        domain_weights = agent._get_domain_weights(tc["skill_path"])
        result = agent._review_content_v2(
            tc["user_task"], tc["summary"], tc["output"],
            tc["skill_path"], domain_weights
        )

        checks_ok = []
        # Check: 6 dimensions
        dims = result.get("dimensions", {})
        if len(dims) == 6:
            checks_ok.append("6_dims:OK")
        else:
            checks_ok.append(f"6_dims:FAIL({len(dims)})")

        # Check: has overall score
        if "overall" in result and "weighted_score" in result["overall"]:
            checks_ok.append(f"score:{result['overall']['weighted_score']:.2f}")
        else:
            checks_ok.append("score:FAIL")

        # Check: has difficulty
        if "difficulty" in result and "threshold" in result["difficulty"]:
            checks_ok.append(f"diff:{result['difficulty']['threshold']:.2f}")
        else:
            checks_ok.append("diff:FAIL")

        # Check: has risk
        if "risk" in result and "level" in result["risk"]:
            checks_ok.append(f"risk:{result['risk']['level']}")
        else:
            checks_ok.append("risk:FAIL")

        # Check: has confidence
        if "confidence" in result:
            checks_ok.append(f"conf:{result['confidence']:.2f}")

        # Check: has pass
        if "pass" in result:
            checks_ok.append(f"pass:{result['pass']}")

        all_ok = "FAIL" not in str(checks_ok)
        if all_ok:
            passed += 1
            status = "✓"
        else:
            failed += 1
            status = "✗"

        print(f"  {status} {tc['id']}: {tc['desc'][:35]:35s} | {', '.join(checks_ok)}")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Test 3: 技能书文件完整性
# ============================================================

def _collect_tree_nodes(tree_data: dict, prefix: str = "") -> List[str]:
    """递归收集技能树中所有节点的 skill_id"""
    nodes = []
    root = tree_data.get("tree", {}).get("root", {})
    if not root:
        return nodes

    def _walk(node, parent_id=""):
        node_id = node.get("id", "")
        if node_id:
            nodes.append(node_id)
        for child in node.get("children", []):
            _walk(child, node_id)

    _walk(root)
    return nodes


def _node_to_path(node_id: str) -> str:
    """将 skill_id 转换为文件路径"""
    parts = node_id.split(".")
    return os.path.join(SKILLS_DIR, *parts, "skill.yaml")


def test_skill_book_completeness():
    """测试技能树中所有节点都有对应的 skill.yaml 文件"""
    print("\n" + "=" * 60)
    print("P5 Test 3: 技能书文件完整性")
    print("=" * 60)

    # 加载 tree.yaml
    tree_path = os.path.join(SKILLS_DIR, "tree.yaml")
    with open(tree_path, "r", encoding="utf-8") as f:
        tree_data = yaml.safe_load(f)

    nodes = _collect_tree_nodes(tree_data)
    print(f"  Skill tree: {len(nodes)} nodes")

    passed = 0
    failed = 0
    missing = []

    for node_id in sorted(nodes):
        file_path = _node_to_path(node_id)
        if os.path.exists(file_path):
            # 验证 YAML 可解析
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    skill_data = yaml.safe_load(f)
                if skill_data and "meta" in skill_data:
                    passed += 1
                    print(f"  ✓ {node_id:30s} → {os.path.basename(os.path.dirname(file_path))}/skill.yaml")
                else:
                    failed += 1
                    missing.append(node_id)
                    print(f"  ✗ {node_id:30s} → EMPTY or INVALID")
            except Exception as e:
                failed += 1
                missing.append(node_id)
                print(f"  ✗ {node_id:30s} → PARSE ERROR: {e}")
        else:
            # root 节点由 base.yaml 承载，不需要 root/skill.yaml
            if node_id == "root":
                base_path = os.path.join(SKILLS_DIR, "base.yaml")
                if os.path.exists(base_path):
                    passed += 1
                    print(f"  ✓ {node_id:30s} → base.yaml (root entry)")
                    continue
            failed += 1
            missing.append(node_id)
            print(f"  ✗ {node_id:30s} → MISSING FILE")

    if missing:
        print(f"\n  ⚠ 缺失文件: {missing}")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Test 4: 技能书内容质量
# ============================================================

def test_skill_book_content_quality():
    """测试技能书内容的必要字段完整性"""
    print("\n" + "=" * 60)
    print("P5 Test 4: 技能书内容质量")
    print("=" * 60)

    tree_path = os.path.join(SKILLS_DIR, "tree.yaml")
    with open(tree_path, "r", encoding="utf-8") as f:
        tree_data = yaml.safe_load(f)

    nodes = _collect_tree_nodes(tree_data)
    passed = 0
    failed = 0

    # 每个 skill.yaml 必须包含的字段
    required_fields = {
        "meta": ["skill_id", "name", "version", "parent", "model"],
        "role": ["title", "description", "tone", "language"],
        "knowledge": ["keywords", "constraints", "confidence"],
        "scoring": ["dimensions", "pass_threshold"],
    }

    for node_id in sorted(nodes):
        file_path = _node_to_path(node_id)
        if not os.path.exists(file_path):
            continue  # 已在 Test 3 中报告

        with open(file_path, "r", encoding="utf-8") as f:
            skill_data = yaml.safe_load(f)

        issues = []
        for section, fields in required_fields.items():
            section_data = skill_data.get(section, {})
            if not section_data:
                issues.append(f"missing {section}")
                continue
            for field in fields:
                if field not in section_data:
                    issues.append(f"missing {section}.{field}")

        # 检查 scoring.dimensions 有6个维度
        dims = (skill_data.get("scoring", {}) or {}).get("dimensions", {})
        if len(dims) < 6:
            issues.append(f"dimensions count={len(dims)} (expected 6)")

        if not issues:
            passed += 1
            # 只打印 leaf nodes 的简要信息
            if "." in node_id:
                print(f"  ✓ {node_id:30s} | dims={len(dims)} examples={len(skill_data.get('knowledge',{}).get('examples',[]))}")
        else:
            failed += 1
            print(f"  ✗ {node_id:30s} | {', '.join(issues[:3])}")

    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("Phase 4+5 Review Configs + Skill Book 集成测试")
    print("=" * 60)

    total_passed = 0
    total_failed = 0

    # P4: V2 配置加载
    p1, f1 = test_v2_scoring_configs()
    total_passed += p1
    total_failed += f1

    # P4: V2 评审管线
    p2, f2 = test_review_v2_pipeline()
    total_passed += p2
    total_failed += f2

    # P5: 技能书完整性
    p3, f3 = test_skill_book_completeness()
    total_passed += p3
    total_failed += f3

    # P5: 技能书内容质量
    p4, f4 = test_skill_book_content_quality()
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