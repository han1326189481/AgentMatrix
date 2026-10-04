"""
Skill Engine V2 集成测试 — Phase 6/7/8: 自学习 + 意图缓存 + 集成测试
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_intent_cache():
    print("=" * 60)
    print("Test 1: IntentCache 意图缓存")

    from core.skill_engine.intent_cache import IntentCache, get_intent_cache

    cache = IntentCache(max_size=10, ttl=300)

    # 测试指纹
    fp1 = cache._fingerprint("你好，今天天气怎么样？")
    fp2 = cache._fingerprint("你好 今天天气怎么样")
    fp3 = cache._fingerprint("你好，今天天气怎么样？")
    assert fp1 == fp2 == fp3, "归一化指纹不一致"
    print("  PASS: 指纹归一化一致（去标点+去空格+小写）")

    # 测试 L1 存储和查询
    cache.store_skill_path("你好", ["root", "daily"])
    result = cache.lookup_skill_path("你好？")
    assert result == ["root", "daily"], f"L1缓存未命中，期望['root', 'daily']，实际: {result}"
    print("  PASS: L1 技能路径缓存命中")

    result2 = cache.lookup_skill_path("完全不同的查询")
    assert result2 is None, "不应命中"
    print("  PASS: L1 未命中返回 None")

    # 测试 L2 存储和查询
    cache.store_result("简单问题", {
        "final_result": "这是测试结果",
        "executed_locally": True,
        "steps": [],
    })
    result3 = cache.lookup_result("简单问题")
    assert result3 is not None, "L2缓存未命中"
    assert result3["final_result"] == "这是测试结果"
    print("  PASS: L2 结果缓存命中")

    # 测试 L2 不缓存云端结果
    cache.store_result("云端问题", {
        "final_result": "云端结果",
        "executed_locally": False,
    })
    result4 = cache.lookup_result("云端问题")
    assert result4 is None, "云端结果不应缓存"
    print("  PASS: L2 云端结果不缓存")

    # 测试 L2 不缓存长结果
    long_result = "A" * 6000
    cache.store_result("长结果问题", {
        "final_result": long_result,
        "executed_locally": True,
    })
    result5 = cache.lookup_result("长结果问题")
    assert result5 is None, "长结果不应缓存"
    print("  PASS: L2 长结果（>5000字符）不缓存")

    # 测试缓存统计
    stats = cache.get_stats()
    assert stats["l1_skill_path"]["size"] == 1, f"L1应有1条，实际: {stats['l1_skill_path']['size']}"
    assert stats["l2_result"]["size"] == 1, f"L2应有1条（简单问题），实际: {stats['l2_result']['size']}"
    print(f"  PASS: 缓存统计 L1={stats['l1_skill_path']['size']} L2={stats['l2_result']['size']}")

    # 测试缓存清除
    cache.clear("l1")
    assert cache.get_stats()["l1_skill_path"]["size"] == 0
    print("  PASS: L1 缓存清除")

    cache.clear()
    assert cache.get_stats()["l2_result"]["size"] == 0
    print("  PASS: 全部缓存清除")

    # 测试全局单例
    cache2 = get_intent_cache()
    assert cache2 is not None
    print("  PASS: get_intent_cache() 全局单例正常")


def test_skill_learner():
    print("\n" + "=" * 60)
    print("Test 2: SkillLearner 技能自学习")

    from core.skill_engine.skill_learner import SkillLearner, get_skill_learner

    learner = SkillLearner(min_confidence=0.70, min_samples=2)

    # 模拟高置信度反馈
    review1 = {
        "overall": {"confidence": 0.90, "weighted_score": 0.65},
        "difficulty": {"threshold": 0.45, "level": "medium"},
        "dimensions": {
            "accuracy": {"score": 0.55, "issues": [{"description": "事实性错误"}], "suggestion": "修正事实错误"},
            "professional": {"score": 0.80, "issues": [], "suggestion": ""},
            "completeness": {"score": 0.60, "issues": [{"description": "缺少关键细节"}], "suggestion": "补充关键信息"},
            "reasoning": {"score": 0.85, "issues": [], "suggestion": ""},
            "structure": {"score": 0.75, "issues": [], "suggestion": ""},
            "actionable": {"score": 0.70, "issues": [], "suggestion": ""},
        }
    }

    accepted = learner.collect_feedback(
        ["root", "tech", "tech.ai", "tech.ai.agent"],
        review1
    )
    assert accepted, "高置信度反馈应被接受"
    print(f"  PASS: 高置信度反馈收集 (confidence=0.90)")

    # 模拟低置信度反馈
    review2 = {
        "overall": {"confidence": 0.40},
        "dimensions": {
            "accuracy": {"score": 0.30, "issues": [{"description": "严重错误"}], "suggestion": ""},
        }
    }
    accepted2 = learner.collect_feedback(
        ["root", "tech", "tech.ai"],
        review2
    )
    assert not accepted2, "低置信度反馈应被丢弃"
    print(f"  PASS: 低置信度反馈丢弃 (confidence=0.40)")

    # 再收集一条达到 min_samples=2
    review3 = {
        "overall": {"confidence": 0.92},
        "dimensions": {
            "accuracy": {"score": 0.50, "issues": [{"description": "数据不准确"}], "suggestion": "核实数据来源"},
            "completeness": {"score": 0.45, "issues": [{"description": "缺少背景信息"}], "suggestion": "补充背景"},
        }
    }
    accepted3 = learner.collect_feedback(
        ["root", "tech", "tech.ai", "tech.ai.agent"],
        review3
    )
    assert accepted3, "应触发学习"
    assert learner.should_learn("tech.ai.agent"), "应触发学习"
    print(f"  PASS: min_samples=2 触发学习 (buffer={learner.get_buffer_size('tech.ai.agent')})")

    # 测试 Patch 生成
    patch = learner.generate_patch("tech.ai.agent")
    assert patch is not None, "应生成Patch"
    assert len(patch.added_constraints) > 0, "Patch应包含约束"
    print(f"  PASS: Patch 生成 - constraints={len(patch.added_constraints)} forbidden={len(patch.added_forbidden)}")

    # 测试 Patch 保存为待审核
    success = learner.apply_patch("tech.ai.agent", patch, auto_approve=False)
    assert success, "保存待审核Patch应成功"
    print("  PASS: Patch 保存为待审核")

    # 测试统计
    stats = learner.get_stats()
    print(f"  PASS: 学习器统计 - buffered={stats['buffered_domains']} domains_ready={stats['domains_ready']}")

    # 测试全局单例
    learner2 = get_skill_learner()
    assert learner2 is not None
    print("  PASS: get_skill_learner() 全局单例正常")


def test_skill_stack_merging():
    print("\n" + "=" * 60)
    print("Test 3: Skill 叠加测试")

    from core.skill_engine.skill_manager import get_skill_manager
    mgr = get_skill_manager()
    mgr._cache = {}

    # 测试多层叠加
    path = ["root", "tech", "tech.ai", "tech.ai.agent", "tech.ai.agent.multi"]
    merged = mgr.load_skill_stack_merged(path)

    # 检查角色合并
    assert merged.role is not None, "角色应合并"
    print(f"  PASS: 角色合并: {merged.role.title}")

    # 检查能力合并（交集）
    capabilities = merged.capabilities
    assert len(capabilities) > 0, "应有能力"
    print(f"  PASS: 能力合并: {capabilities}")

    # 检查关键词合并
    total_kw = sum(
        sum(len(v) if isinstance(v, list) and v and isinstance(v[0], str) else 0
            for v in kw_map.values())
        if isinstance(kw_map, dict) else 0
        for kw_map in merged.knowledge.keywords.values()
    )
    print(f"  PASS: 关键词合并: {total_kw} 个关键词")

    # 检查约束合并
    constraints = merged.knowledge.constraints
    assert len(constraints) > 0, "应有约束"
    print(f"  PASS: 约束合并: {len(constraints)} 条约束")

    # 检查禁止事项合并
    forbidden = merged.forbidden
    assert len(forbidden) > 0, "应有禁止事项"
    print(f"  PASS: 禁止事项合并: {len(forbidden)} 条")


def test_capability_check():
    print("\n" + "=" * 60)
    print("Test 4: 能力检查测试")

    from core.skill_engine.skill_manager import get_skill_manager
    mgr = get_skill_manager()
    mgr._cache = {}

    # 测试 daily 领域能力
    caps = mgr.get_capabilities(["root", "daily"])
    assert isinstance(caps, (list, set)), "能力应为列表或集合"
    assert len(caps) > 0, "daily领域应有能力"
    print(f"  PASS: daily 能力: {list(caps) if isinstance(caps, set) else caps}")

    # 测试 tech 领域能力
    caps2 = mgr.get_capabilities(["root", "tech", "tech.ai", "tech.ai.agent", "tech.ai.agent.multi"])
    assert isinstance(caps2, (list, set)), "能力应为列表或集合"
    print(f"  PASS: multi-agent 能力: {list(caps2) if isinstance(caps2, set) else caps2}")

    # 测试 skill tree 路径
    tree = mgr.tree
    path = tree.get_path_to("tech.ai.agent.multi")
    assert len(path) > 1, "路径应存在"
    print(f"  PASS: skill tree 路径: {path}")


def test_cache_hit_scenario():
    print("\n" + "=" * 60)
    print("Test 5: 缓存命中场景测试")

    from core.skill_engine.intent_cache import IntentCache
    cache = IntentCache(max_size=10, ttl=300)

    # 模拟：第一次查询存储 L1
    cache.store_skill_path("AI Agent 开发", ["root", "tech", "tech.ai", "tech.ai.agent"])
    # 第二次相同查询命中 L1
    hit = cache.lookup_skill_path("AI Agent 开发...")
    assert hit == ["root", "tech", "tech.ai", "tech.ai.agent"], "L1应命中"
    print("  PASS: 相同查询 L1 命中")

    # 相似查询（归一化后相同）命中 L1
    hit2 = cache.lookup_skill_path("AI Agent 开发")
    assert hit2 == ["root", "tech", "tech.ai", "tech.ai.agent"], "相似查询 L1 应命中"
    print("  PASS: 归一化相似查询 L1 命中")

    # 不同查询不命中
    miss = cache.lookup_skill_path("天气预报")
    assert miss is None, "不同查询不应命中"
    print("  PASS: 不同查询 L1 未命中")

    # L2 缓存命中场景
    cache.store_result("简单问候", {
        "final_result": "你好！",
        "executed_locally": True,
        "steps": [],
    })
    hit3 = cache.lookup_result("简单问候")
    assert hit3 is not None and hit3["final_result"] == "你好！"
    print("  PASS: L2 缓存命中")

    # 命中计数
    stats = cache.get_stats()
    l1_hits = stats["l1_skill_path"]["hits"]
    l2_hits = stats["l2_result"]["hits"]
    print(f"  PASS: 缓存命中统计 L1={l1_hits} L2={l2_hits}")


def main():
    print("Skill Engine V2 — Phase 6/7/8 集成测试")
    print("=" * 60)

    try:
        test_intent_cache()
        test_skill_learner()
        test_skill_stack_merging()
        test_capability_check()
        test_cache_hit_scenario()

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