"""
Skill Engine V2 集成测试 — Phase 4 & 5 验证
测试: Review Agent YAML配置 / 全部技能文件加载 / 领域检测
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_review_agent_v2_configs():
    print("=" * 60)
    print("Test 1: Review Agent V2 配置加载")
    from agents.review.agent import ReviewAgent

    r = ReviewAgent()
    cfg = r._load_v2_configs()

    # 基础配置
    base = cfg["base"]
    assert "dimensions" in base, "base缺少dimensions"
    dims = base["dimensions"]
    assert len(dims) == 6, f"应有6个维度，实际: {len(dims)}"
    assert "accuracy" in dims, "缺少accuracy维度"
    print(f"  PASS: base_scoring.yaml 加载成功，6维评分: {list(dims.keys())}")

    # 难度矩阵
    diff = cfg["difficulty"]
    assert "domain_base_difficulty" in diff, "difficulty缺少domain_base_difficulty"
    assert "complexity_keywords" in diff, "difficulty缺少complexity_keywords"
    print(f"  PASS: difficulty_matrix.yaml 加载成功，{len(diff['complexity_keywords'])}个关键词")

    # 技术评分配置
    tech = cfg["tech"]
    assert "tech_checks" in tech, "tech缺少tech_checks"
    print(f"  PASS: tech_scoring.yaml 加载成功，{len(tech['tech_checks'])}个专项检查")

    # 领域难度查找
    diffs = diff["domain_base_difficulty"]
    test_cases = [
        ("daily", 0.15),
        ("creative", 0.30),
        ("business.planning", 0.45),
        ("business.report", 0.50),
        ("tech.ai.agent", 0.60),
        ("tech.ai.rag.retrieval", 0.62),
        ("tech.crypto.quantum", 0.75),
        ("tech.network", 0.50),
        ("tech.compiler", 0.60),
        ("tech.os", 0.55),
    ]
    for domain, expected in test_cases:
        actual = r._lookup_domain_difficulty(domain, diffs)
        assert actual == expected, f"{domain}: 期望{expected}，实际{actual}"
    print(f"  PASS: {len(test_cases)}个领域难度查找全部正确")


def test_all_skills_load():
    print("\n" + "=" * 60)
    print("Test 2: 全部技能文件加载")

    from core.skill_engine.skill_manager import get_skill_manager
    mgr = get_skill_manager()

    # 强制刷新以加载新技能
    mgr._cache = {}

    all_leaf_ids = [
        "daily", "creative",
        "business.planning", "business.report", "business.proposal",
        "tech.ai.agent.memory", "tech.ai.agent.multi", "tech.ai.agent.tool", "tech.ai.agent.mcp",
        "tech.ai.rag.chunking", "tech.ai.rag.embedding", "tech.ai.rag.retrieval",
        "tech.ai.prompt", "tech.ai.llm",
        "tech.crypto.quantum", "tech.crypto.post_quantum", "tech.crypto.classical",
        "tech.network", "tech.compiler", "tech.os",
    ]

    loaded = 0
    failed = []
    for skill_id in all_leaf_ids:
        try:
            skill = mgr.load_skill(skill_id)
            assert skill is not None
            assert skill.meta.skill_id == skill_id, f"ID不匹配: {skill.meta.skill_id} != {skill_id}"
            loaded += 1
        except Exception as e:
            failed.append((skill_id, str(e)))

    print(f"  PASS: {loaded}/{len(all_leaf_ids)} 个技能文件加载成功")
    if failed:
        print(f"  FAIL: {len(failed)} 个加载失败:")
        for sid, err in failed:
            print(f"    - {sid}: {err}")
    else:
        print(f"  PASS: 全部技能文件加载成功！")


def test_domain_detection_v2():
    print("\n" + "=" * 60)
    print("Test 3: 领域检测（V2 全量技能）")

    from core.skill_engine.skill_manager import get_skill_manager
    mgr = get_skill_manager()
    mgr._cache = {}

    test_cases = [
        ("你好", ["root", "daily"]),
        ("写一首诗", ["root", "creative"]),
        ("帮我策划一个活动方案", ["root", "business", "business.planning"]),
        ("写一份市场分析报告", ["root", "business", "business.report"]),
        ("设计一个RAG系统的文档分块策略", ["root", "tech", "tech.ai", "tech.ai.rag", "tech.ai.rag.chunking"]),
        ("如何选择Embedding模型", ["root", "tech", "tech.ai", "tech.ai.rag", "tech.ai.rag.embedding"]),
        ("多Agent系统的编排方案", ["root", "tech", "tech.ai", "tech.ai.agent", "tech.ai.agent.multi"]),
        ("MCP协议的工具注册流程", ["root", "tech", "tech.ai", "tech.ai.agent", "tech.ai.agent.mcp"]),
        ("量子计算对密码学的影响", ["root", "tech", "tech.crypto", "tech.crypto.quantum"]),
        ("AES加密算法的原理", ["root", "tech", "tech.crypto", "tech.crypto.classical"]),
        ("设计一个编译器", ["root", "tech", "tech.compiler"]),
        ("Linux内核的进程调度", ["root", "tech", "tech.os"]),
    ]

    passed = 0
    for query, expected_path in test_cases:
        path = mgr.detect_domain(query)
        if path == expected_path:
            passed += 1
            print(f"  PASS: '{query[:20]}...' → {path}")
        else:
            print(f"  WARN: '{query[:20]}...' → {path} (期望: {expected_path})")

    print(f"\n  PASS: {passed}/{len(test_cases)} 领域检测正确")


def test_skill_stack_merging():
    print("\n" + "=" * 60)
    print("Test 4: 技能栈合并")

    from core.skill_engine.skill_manager import get_skill_manager
    mgr = get_skill_manager()
    mgr._cache = {}

    # 测试多层技能栈合并
    path = ["root", "tech", "tech.ai", "tech.ai.agent", "tech.ai.agent.multi"]
    stack = mgr.load_skill_stack(path)
    assert len(stack) == len(path), f"技能栈长度应为{len(path)}，实际: {len(stack)}"
    print(f"  PASS: 技能栈深度 {len(stack)}: {[s.meta.skill_id for s in stack]}")

    # 合并
    merged = mgr.load_skill_stack_merged(path)
    assert merged is not None, "合并失败"
    print(f"  PASS: 合并技能栈 - 角色: {merged.role.title}")
    print(f"  PASS: 合并能力: {merged.capabilities}")
    print(f"  PASS: 合并关键词数: {sum(len(v) for v in merged.knowledge.keywords.values())}")

    # 能力交集
    caps = mgr.get_capabilities(path)
    print(f"  PASS: 能力交集: {caps}")


def main():
    print("Skill Engine V2 — Phase 4 & 5 集成测试")
    print("=" * 60)

    try:
        test_review_agent_v2_configs()
        test_all_skills_load()
        test_domain_detection_v2()
        test_skill_stack_merging()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nTEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()