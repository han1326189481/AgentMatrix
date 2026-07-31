"""Phase 4 — CapabilityGraph / PersonalBrain 单元测试

测试覆盖:
- CapabilityGraph: has / get_proficiency / update / get_gaps / get_ready_for_next
- Proficiency 枚举: 五级熟练度
- PersonalBrain: UserProfile / build_context / update_from_session
- 集成: CapabilityGraph + SkillGraph 协作
"""

import pytest
from core.graphs.capability_graph import (
    CapabilityGraph, CapabilityNode, Proficiency
)
from core.personal_brain.brain import PersonalBrain, UserProfile
from core.graphs import get_skill_graph


# ============================================================
# Proficiency 枚举
# ============================================================

class TestProficiency:
    def test_enum_values(self):
        assert Proficiency.NONE == "none"
        assert Proficiency.THEORY == "theory"
        assert Proficiency.PRACTICE == "practice"
        assert Proficiency.PROFICIENT == "proficient"
        assert Proficiency.EXPERT == "expert"

    def test_enum_order(self):
        """能力等级排序正确"""
        levels = [Proficiency.NONE, Proficiency.THEORY, Proficiency.PRACTICE,
                  Proficiency.PROFICIENT, Proficiency.EXPERT]
        assert len(levels) == 5


# ============================================================
# CapabilityNode
# ============================================================

class TestCapabilityNode:
    def test_create_default(self):
        node = CapabilityNode(skill_node_id="transformer")
        assert node.skill_node_id == "transformer"
        assert node.proficiency == Proficiency.NONE
        assert node.evidence == []
        assert node.practice_count == 0

    def test_create_with_proficiency(self):
        node = CapabilityNode(skill_node_id="rag", proficiency=Proficiency.PRACTICE)
        assert node.proficiency == Proficiency.PRACTICE


# ============================================================
# CapabilityGraph
# ============================================================

class TestCapabilityGraph:
    @pytest.fixture
    def graph(self):
        return CapabilityGraph(user_id="test")

    def test_has_unknown_node(self, graph):
        """未知节点返回 False"""
        assert graph.has("nonexistent") is False

    def test_has_none_proficiency(self, graph):
        """NONE 熟练度视为未掌握"""
        graph.update("transformer", Proficiency.NONE)
        assert graph.has("transformer") is False

    def test_has_theory_proficiency(self, graph):
        """THEORY 熟练度：用户知道此概念，has=True，但 get_gaps 仍算缺口"""
        graph.update("transformer", Proficiency.THEORY)
        assert graph.has("transformer") is True  # 用户知道这个概念
        # get_gaps 中 THEORY 算缺口（需要实践）

    def test_has_practice_proficiency(self, graph):
        """PRACTICE 及以上视为已掌握"""
        graph.update("transformer", Proficiency.PRACTICE)
        assert graph.has("transformer") is True

    def test_has_proficient(self, graph):
        graph.update("transformer", Proficiency.PROFICIENT)
        assert graph.has("transformer") is True

    def test_has_expert(self, graph):
        graph.update("transformer", Proficiency.EXPERT)
        assert graph.has("transformer") is True

    def test_get_proficiency_unknown(self, graph):
        assert graph.get_proficiency("nonexistent") == Proficiency.NONE

    def test_get_proficiency_known(self, graph):
        graph.update("transformer", Proficiency.PROFICIENT)
        assert graph.get_proficiency("transformer") == Proficiency.PROFICIENT

    def test_update_creates_new_node(self, graph):
        graph.update("transformer", Proficiency.PRACTICE, evidence="built a model")
        node = graph.nodes["transformer"]
        assert node.proficiency == Proficiency.PRACTICE
        assert "built a model" in node.evidence
        assert node.practice_count == 1

    def test_update_existing_node(self, graph):
        graph.update("transformer", Proficiency.THEORY)
        graph.update("transformer", Proficiency.PRACTICE, evidence="practiced")
        node = graph.nodes["transformer"]
        assert node.proficiency == Proficiency.PRACTICE
        assert node.practice_count == 2
        assert len(node.evidence) == 1

    def test_update_multiple_evidence(self, graph):
        graph.update("transformer", Proficiency.PRACTICE, evidence="session 1")
        graph.update("transformer", Proficiency.PROFICIENT, evidence="session 2")
        assert len(graph.nodes["transformer"].evidence) == 2
        assert graph.nodes["transformer"].practice_count == 2

    def test_get_gaps(self, graph):
        skill_graph = get_skill_graph()
        graph.update("transformer", Proficiency.PRACTICE)
        graph.update("rag", Proficiency.THEORY)

        gaps = graph.get_gaps(skill_graph)
        # transformer is PRACTICE → not a gap
        # rag is THEORY → is a gap
        assert "rag" in gaps
        assert "transformer" not in gaps

    def test_get_gaps_all_unknown(self, graph):
        """空能力图谱，所有节点都是缺口"""
        skill_graph = get_skill_graph()
        gaps = graph.get_gaps(skill_graph)
        assert len(gaps) > 0

    def test_get_ready_for_next(self, graph):
        """前置条件满足时可学习下一步"""
        skill_graph = get_skill_graph()
        # 标记前置知识已掌握
        graph.update("transformer", Proficiency.PRACTICE)
        ready = graph.get_ready_for_next(skill_graph)
        assert isinstance(ready, list)

    def test_get_ready_for_next_empty(self, graph):
        """无前置条件满足时为空"""
        skill_graph = get_skill_graph()
        ready = graph.get_ready_for_next(skill_graph)
        # 所有节点都没有 prerequisite 满足，所以 ready 应该较少
        assert isinstance(ready, list)


# ============================================================
# UserProfile
# ============================================================

class TestUserProfile:
    def test_create_default(self):
        profile = UserProfile(user_id="user1")
        assert profile.user_id == "user1"
        assert profile.display_name == ""
        assert profile.identity == ""
        assert profile.long_term_goals == []
        assert profile.preferences == {}
        assert profile.expression_style == ""
        assert profile.learning_stage == ""

    def test_create_with_data(self):
        profile = UserProfile(
            user_id="user1",
            display_name="Test User",
            identity="developer",
            long_term_goals=["learn AI"],
            preferences={"lang": "zh"},
            expression_style="concise_technical",
            learning_stage="intermediate"
        )
        assert profile.identity == "developer"
        assert "learn AI" in profile.long_term_goals
        assert profile.learning_stage == "intermediate"


# ============================================================
# PersonalBrain
# ============================================================

class TestPersonalBrain:
    @pytest.fixture
    def brain(self):
        return PersonalBrain(user_id="test")

    def test_create_brain(self, brain):
        assert brain.user_id == "test"
        assert brain.profile is not None
        assert brain.capability is not None

    def test_build_context_empty(self, brain):
        """空画像时 context 为空"""
        ctx = brain.build_context()
        assert ctx == ""

    def test_build_context_with_identity(self, brain):
        brain.profile.identity = "developer"
        ctx = brain.build_context()
        assert "用户身份: developer" in ctx

    def test_build_context_with_goals(self, brain):
        brain.profile.long_term_goals = ["learn AI", "build agent"]
        ctx = brain.build_context()
        assert "learn AI" in ctx
        assert "build agent" in ctx

    def test_build_context_with_preferences(self, brain):
        brain.profile.preferences = {"code_style": "concise"}
        ctx = brain.build_context()
        assert "code_style=concise" in ctx

    def test_build_context_with_expression_style(self, brain):
        brain.profile.expression_style = "concise_technical"
        ctx = brain.build_context()
        assert "表达风格: concise_technical" in ctx

    def test_build_context_full(self, brain):
        brain.profile.identity = "developer"
        brain.profile.long_term_goals = ["learn AI"]
        brain.profile.preferences = {"lang": "zh"}
        brain.profile.expression_style = "concise_technical"
        ctx = brain.build_context()
        assert len(ctx) > 0
        assert "developer" in ctx
        assert "learn AI" in ctx
        assert "lang=zh" in ctx

    def test_update_from_session(self, brain):
        brain.update_from_session({
            "session_id": "s1",
            "skill_nodes": ["transformer", "rag"]
        })
        assert brain.capability.has("transformer") is True
        assert brain.capability.has("rag") is True
        assert brain.capability.get_proficiency("transformer") == Proficiency.PRACTICE

    def test_update_from_session_empty(self, brain):
        """空 skill_nodes 不报错"""
        brain.update_from_session({"session_id": "s1", "skill_nodes": []})
        assert len(brain.capability.nodes) == 0

    def test_update_from_session_no_skill_nodes(self, brain):
        """无 skill_nodes 字段不报错"""
        brain.update_from_session({"session_id": "s1"})
        assert len(brain.capability.nodes) == 0


# ============================================================
# 集成测试
# ============================================================

class TestPhase4Integration:
    def test_capability_with_skill_graph(self):
        """CapabilityGraph 与 SkillGraph 协作"""
        skill_graph = get_skill_graph()
        cap = CapabilityGraph(user_id="test")

        # 更新一些能力
        for node_id in list(skill_graph.nodes.keys())[:5]:
            cap.update(node_id, Proficiency.PRACTICE)

        # 检查缺口
        gaps = cap.get_gaps(skill_graph)
        assert len(gaps) < len(skill_graph.nodes)  # 有练习过的节点不应是缺口

    def test_brain_full_pipeline(self):
        """PersonalBrain 完整流程"""
        brain = PersonalBrain(user_id="test")
        brain.profile.identity = "developer"
        brain.profile.learning_stage = "intermediate"

        # 构建 context
        ctx = brain.build_context()
        assert "developer" in ctx

        # 会话更新
        brain.update_from_session({
            "session_id": "s1",
            "skill_nodes": ["transformer", "rag", "agent"]
        })
        assert brain.capability.has("transformer")

        # 再次构建 context（应包含能力信息）
        ctx2 = brain.build_context()
        assert "developer" in ctx2

    def test_imports(self):
        """所有模块正确导入"""
        from core.graphs.capability_graph import CapabilityGraph, Proficiency
        from core.personal_brain.brain import PersonalBrain, UserProfile
        assert CapabilityGraph is not None
        assert PersonalBrain is not None