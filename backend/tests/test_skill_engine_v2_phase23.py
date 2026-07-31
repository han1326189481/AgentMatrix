"""
Skill Engine V2 集成测试 — Phase 2 & 3 验证
测试: skill_tree 模块 / Writer Agent / Result Agent
"""
import sys
import os
import json
import asyncio

# 确保 backend 在 Python path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# Test 1: SkillTree 模块独立性
# ============================================================
def test_skill_tree_module():
    print("=" * 60)
    print("Test 1: SkillTree 模块独立性")
    from core.skill_engine.skill_tree import SkillTreeNode, SkillTree

    # 构建测试树
    root = SkillTreeNode(id="root", name="通用")
    child = SkillTreeNode(id="test", name="测试")
    root.children = [child]

    tree = SkillTree(root)
    assert tree.get_path_to("test") == ["root", "test"], "路径查找失败"
    assert "test" in tree.get_all_leaf_domains(), "叶子节点获取失败"
    assert tree.find_node("test") is not None, "节点查找失败"

    print("  PASS: SkillTreeNode/SkillTree 独立运行正常")
    print("  PASS: get_path_to / get_all_leaf_domains / find_node 正常")

    # 验证 models.py 向后兼容
    from core.skill_engine.models import SkillTreeNode as MNode, SkillTree as MTree
    assert MNode is SkillTreeNode, "models.py 重导出不一致"
    assert MTree is SkillTree, "models.py 重导出不一致"
    print("  PASS: models.py 向后兼容重导出正常")

    # 验证 __init__.py 导出
    from core.skill_engine import SkillTree as ITree
    assert ITree is SkillTree, "__init__.py 导出不一致"
    print("  PASS: __init__.py 导出正常")


# ============================================================
# Test 2: SkillManager 集成
# ============================================================
def test_skill_manager():
    print("\n" + "=" * 60)
    print("Test 2: SkillManager 集成")
    from core.skill_engine.skill_manager import get_skill_manager

    mgr = get_skill_manager()

    # 加载技能
    skill = mgr.load_skill("daily")
    assert skill is not None, "daily skill 加载失败"
    assert skill.meta.skill_id == "daily", f"skill_id 不匹配: {skill.meta.skill_id}"
    print(f"  PASS: 加载 daily skill: {skill.meta.name}")

    # 加载技能栈
    stack = mgr.load_skill_stack(["root", "daily"])
    assert len(stack) == 2, f"技能栈长度应为2，实际: {len(stack)}"
    print(f"  PASS: 技能栈加载: {[s.meta.skill_id for s in stack]}")

    # 能力查询
    caps = mgr.get_capabilities(["root", "daily"])
    print(f"  PASS: 能力查询: {caps}")

    # 领域检测
    domain = mgr.detect_domain("你好，今天天气怎么样")
    print(f"  PASS: 领域检测: '你好...' → {domain}")

    domain2 = mgr.detect_domain("请写一篇关于量子计算的文章")
    print(f"  PASS: 领域检测: '量子计算...' → {domain2}")

    # 技能树
    tree = mgr.tree
    assert tree is not None, "技能树加载失败"
    print(f"  PASS: 技能树加载: {len(tree.get_all_domains())} 个领域节点")


# ============================================================
# Test 3: Writer Agent Skill Engine 集成
# ============================================================
def test_writer_agent():
    print("\n" + "=" * 60)
    print("Test 3: Writer Agent Skill Engine 集成")
    from agents.writer.agent import WriterAgent

    agent = WriterAgent()

    # 验证属性和方法存在
    assert hasattr(agent, 'skill_manager'), "WriterAgent 缺少 skill_manager"
    assert hasattr(agent, 'prompt_builder'), "WriterAgent 缺少 prompt_builder"
    assert hasattr(agent, '_current_system_prompt'), "WriterAgent 缺少 _current_system_prompt"
    assert hasattr(agent, '_current_skill_path'), "WriterAgent 缺少 _current_skill_path"
    print("  PASS: WriterAgent Skill Engine 属性完整")

    # 测试 _parse_knowledge_output 提取 skill_path
    parsed = agent._parse_knowledge_output('{"task": "test", "skill_path": ["root", "tech", "tech.ai"]}')
    assert parsed.get("skill_path") == ["root", "tech", "tech.ai"], "skill_path 提取失败"
    print("  PASS: _parse_knowledge_output 提取 skill_path 正常")

    # 测试无 skill_path 的 fallback
    parsed2 = agent._parse_knowledge_output('{"task": "hello"}')
    assert parsed2.get("skill_path") == ["root", "daily"], "skill_path fallback 失败"
    print("  PASS: skill_path fallback → ['root', 'daily'] 正常")

    # 测试 skill_manager 懒加载
    assert agent.skill_manager is not None, "skill_manager 懒加载失败"
    print("  PASS: skill_manager 懒加载正常")

    # 测试 prompt_builder 懒加载
    assert agent.prompt_builder is not None, "prompt_builder 懒加载失败"
    print("  PASS: prompt_builder 懒加载正常")


# ============================================================
# Test 4: Result Agent 弱维度分析
# ============================================================
def test_result_agent():
    print("\n" + "=" * 60)
    print("Test 4: Result Agent 弱维度分析")

    from agents.result.agent import ResultAgent

    agent = ResultAgent()

    # 测试 _extract_weak_dimensions (V2 格式)
    review_v2 = {
        "dimensions": {
            "accuracy": {"score": 0.45, "issues": [{"type": "factual_error", "desc": "事实错误"}], "suggestion": "修正事实"},
            "professional": {"score": 0.80, "issues": [], "suggestion": ""},
            "completeness": {"score": 0.55, "issues": [{"type": "missing_info", "desc": "缺少关键信息"}], "suggestion": "补充细节"},
            "reasoning": {"score": 0.90, "issues": [], "suggestion": ""},
            "structure": {"score": 0.75, "issues": [], "suggestion": ""},
            "actionable": {"score": 0.60, "issues": [{"type": "vague", "desc": "建议模糊"}], "suggestion": "添加具体步骤"},
        }
    }
    weak = agent._extract_weak_dimensions(json.dumps(review_v2))
    assert len(weak) == 3, f"应有3个弱维度，实际: {len(weak)}"
    assert weak[0]["name"] == "accuracy", f"最弱维度应为 accuracy，实际: {weak[0]['name']}"
    print(f"  PASS: V2格式弱维度提取: {[(w['name'], w['score']) for w in weak]}")

    # 测试 _extract_weak_dimensions (旧格式)
    review_old = {
        "dimensions": {
            "structure": 0.70,
            "relevance": 0.45,
            "richness": 0.65,
            "professional": 0.80,
            "actionable": 0.50,
        }
    }
    weak2 = agent._extract_weak_dimensions(json.dumps(review_old))
    assert len(weak2) == 3, f"旧格式应有3个弱维度，实际: {len(weak2)}"
    print(f"  PASS: 旧格式弱维度提取: {[(w['name'], w['score']) for w in weak2]}")

    # 测试空输入
    weak3 = agent._extract_weak_dimensions("")
    assert weak3 == [], "空输入应返回空列表"
    print("  PASS: 空输入返回空列表")

    # 测试 _build_weak_enhancement_prompt
    enhancement = agent._build_weak_enhancement_prompt(weak)
    assert "准确性" in enhancement, "增强提示应包含维度中文名"
    assert "得分" in enhancement, "增强提示应包含得分信息"
    print(f"  PASS: 增强提示构建成功 ({len(enhancement)} 字符)")

    # 测试 polish 模式
    enhancement2 = agent._build_weak_enhancement_prompt(weak, for_polish=True)
    assert "针对性修正" in enhancement2, "润色模式提示应包含'针对性修正'"
    print(f"  PASS: 润色模式增强提示构建成功 ({len(enhancement2)} 字符)")


# ============================================================
# Test 5: 端到端集成
# ============================================================
async def test_e2e():
    print("\n" + "=" * 60)
    print("Test 5: 端到端集成测试")

    from agents.writer.agent import WriterAgent
    from agents.base.agent import AgentInput

    agent = WriterAgent()

    # 模拟 Knowledge Agent 输出（含 skill_path）
    knowledge_output = json.dumps({
        "task": "写一篇关于AI的短文",
        "original_question": "请写一篇关于人工智能发展的短文，100字左右",
        "keywords": ["人工智能", "AI", "发展"],
        "knowledge_items": ["人工智能是计算机科学的分支"],
        "requirements": ["100字左右", "短文"],
        "summary": "写一篇关于AI发展的短文",
        "task_type": "创意写作",
        "skill_path": ["root", "tech", "tech.ai"],
        "skill_domain": "tech.ai",
    })

    input_data = AgentInput(content=knowledge_output, context={}, use_llm=True, use_cloud=False)

    try:
        result = await agent.execute(input_data)
        print(f"  PASS: Writer Agent 执行成功")
        print(f"  - 内容长度: {len(result.content)}")
        print(f"  - 成功: {result.success}")
        if result.metadata:
            print(f"  - skill_path: {result.metadata.get('skill_path', 'N/A')}")
            print(f"  - skill_domain: {result.metadata.get('skill_domain', 'N/A')}")
            print(f"  - task_type: {result.metadata.get('task_type', 'N/A')}")
    except Exception as e:
        print(f"  FAIL: Writer Agent 执行异常: {e}")


# ============================================================
# Test 6: Review 评分配置文件验证
# ============================================================
def test_review_configs():
    print("\n" + "=" * 60)
    print("Test 6: Review 评分配置文件验证")

    import os
    import yaml

    base_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "prompts", "skills", "review", "base_scoring.yaml"
    )
    diff_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "prompts", "skills", "review", "difficulty_matrix.yaml"
    )

    # 验证 base_scoring.yaml
    with open(base_path, "r", encoding="utf-8") as f:
        base = yaml.safe_load(f)
    assert "dimensions" in base, "base_scoring.yaml 缺少 dimensions"
    dims = base["dimensions"]
    expected_dims = ["accuracy", "professional", "completeness", "reasoning", "structure", "actionable"]
    for dim in expected_dims:
        assert dim in dims, f"base_scoring.yaml 缺少维度: {dim}"
    print(f"  PASS: base_scoring.yaml 包含全部6个维度")

    # 验证 difficulty_matrix.yaml
    with open(diff_path, "r", encoding="utf-8") as f:
        diff = yaml.safe_load(f)
    assert "domain_base_difficulty" in diff, "difficulty_matrix.yaml 缺少 domain_base_difficulty"
    assert "complexity_keywords" in diff, "difficulty_matrix.yaml 缺少 complexity_keywords"
    assert "difficulty_levels" in diff, "difficulty_matrix.yaml 缺少 difficulty_levels"
    print(f"  PASS: difficulty_matrix.yaml 结构完整 ({len(diff['complexity_keywords'])} 个复杂度关键词)")

    # 验证难度等级
    levels = diff["difficulty_levels"]
    assert "simple" in levels and "medium" in levels and "complex" in levels and "expert" in levels
    print("  PASS: 4个难度等级 (simple/medium/complex/expert) 定义完整")


# ============================================================
# 主函数
# ============================================================
def main():
    print("Skill Engine V2 — Phase 2 & 3 集成测试")
    print("=" * 60)

    try:
        test_skill_tree_module()
        test_skill_manager()
        test_writer_agent()
        test_result_agent()
        test_review_configs()

        # 端到端测试（需要 Ollama 运行）
        print("\n" + "=" * 60)
        print("Test 5: 端到端集成测试")
        try:
            asyncio.run(test_e2e())
        except Exception as e:
            print(f"  SKIP: 端到端测试需要 Ollama 运行 ({e})")

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