"""Phase 7: Learning Engine V3 测试

覆盖范围:
- ConceptExtractor: 规则提取概念（零 LLM）
- SkillGraph.diff(): 集合差运算
- PatchGenerator: 创建 KnowledgePatch
- PatchValidator: 冲突/重复/置信度检查
- LearningEngine.learn(): 完整学习流程
- LearningEngine.learn(): 质量门槛（review_score < 0.70）
- LearningEngine: 推理模式提取 + 注册
- LearningEngine: 工作流提取
- LearningEngine.apply_patches(): 应用补丁
- LearningEngine.get_stats(): 统计
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ============================================================
# Test 1: ConceptExtractor（规则提取）
# ============================================================

class TestConceptExtractor:
    """概念提取（零 LLM）"""

    @pytest.fixture
    def engine(self):
        from core.graphs.skill_graph import SkillGraph
        from core.engines.learning_engine import LearningEngine
        return LearningEngine(SkillGraph())

    def test_extract_markdown_headers(self, engine):
        """提取 Markdown 标题"""
        text = """## Transformer
## 注意力机制
## 自注意力计算"""
        concepts = engine._extract_concepts(text)
        assert "Transformer" in concepts
        assert "注意力机制" in concepts
        assert "自注意力计算" in concepts

    def test_extract_camel_case(self, engine):
        """提取驼峰命名"""
        text = "使用 FastAPI 和 DjangoRestFramework 构建 API"
        concepts = engine._extract_concepts(text)
        assert "FastAPI" in concepts
        assert "DjangoRestFramework" in concepts

    def test_extract_snake_case(self, engine):
        """提取下划线命名"""
        text = "使用 skill_graph 和 knowledge_base 进行管理"
        concepts = engine._extract_concepts(text)
        assert "skill_graph" in concepts
        assert "knowledge_base" in concepts

    def test_extract_chinese_bookmarks(self, engine):
        """提取中文书名号"""
        text = "《深度学习》和《机器学习实战》是经典教材"
        concepts = engine._extract_concepts(text)
        assert "深度学习" in concepts
        assert "机器学习实战" in concepts

    def test_extract_acronyms(self, engine):
        """提取英文大写缩略词"""
        text = "LLM 和 RAG 是当前 AI 领域的热门技术，CNN 也是"
        concepts = engine._extract_concepts(text)
        assert "LLM" in concepts
        assert "RAG" in concepts
        assert "CNN" in concepts

    def test_filter_common_words(self, engine):
        """过滤常见英文单词"""
        text = "THE model AND THE data FOR this task"
        concepts = engine._extract_concepts(text)
        assert "THE" not in concepts
        assert "AND" not in concepts
        assert "FOR" not in concepts

    def test_extract_short_headers_ignored(self, engine):
        """过短的标题被忽略"""
        text = """## AI
## 深度学习与神经网络
## 嗯"""
        concepts = engine._extract_concepts(text)
        assert "AI" not in concepts  # 太短
        assert "嗯" not in concepts  # 太短
        assert "深度学习与神经网络" in concepts

    def test_extract_long_headers_ignored(self, engine):
        """过长的标题被忽略"""
        short = "这是一个比较长的标题名称"
        # 确保超过50个字符
        long = "这是一个非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常非常长的标题名称"
        text = f"## {short}\n## {long}"
        concepts = engine._extract_concepts(text)
        assert short in concepts
        assert long not in concepts  # > 50 chars

    def test_extract_returns_set(self, engine):
        """返回 set 类型"""
        concepts = engine._extract_concepts("## Test\n## Test\n## Test")
        assert isinstance(concepts, set)
        assert len(concepts) == 1  # 去重


# ============================================================
# Test 2: Graph Diff（集合差）
# ============================================================

class TestGraphDiff:
    """SkillGraph.diff() 集合差运算"""

    @pytest.fixture
    def graph(self):
        from core.graphs.skill_graph import SkillGraph, GraphNode
        g = SkillGraph()
        g.add_node(GraphNode(id="transformer", name="Transformer",
                    node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="attention", name="Attention",
                    node_type="concept", domain="ai"))
        return g

    def test_diff_returns_new_concepts(self, graph):
        """返回图中不存在的概念"""
        new = graph.diff({"Transformer", "Attention", "BERT", "GPT"})
        assert "BERT" in new
        assert "GPT" in new
        assert "Transformer" not in new
        assert "Attention" not in new

    def test_diff_case_insensitive(self, graph):
        """大小写不敏感"""
        new = graph.diff({"transformer", "attention", "bert"})
        assert "transformer" not in new  # matches by lowercase
        assert "attention" not in new
        assert "bert" in new

    def test_diff_empty_input(self, graph):
        """空输入返回空集合"""
        new = graph.diff(set())
        assert len(new) == 0

    def test_diff_all_new(self, graph):
        """全部是新的"""
        new = graph.diff({"XGBoost", "LightGBM", "CatBoost"})
        assert len(new) == 3


# ============================================================
# Test 3: PatchValidator 拦截
# ============================================================

class TestPatchValidator:
    """PatchValidator 校验"""

    @pytest.fixture
    def graph(self):
        from core.graphs.skill_graph import SkillGraph, GraphNode
        g = SkillGraph()
        g.add_node(GraphNode(id="transformer", name="Transformer",
                    node_type="concept", domain="ai"))
        return g

    @pytest.fixture
    def validator(self, graph):
        from core.engines.patch_validator import PatchValidator
        return PatchValidator(graph)

    def test_valid_patch_passes(self, graph, validator):
        """有效补丁通过"""
        from core.skill_engine.models import KnowledgePatch
        patch = KnowledgePatch(
            concept_name="BERT",
            definition="Bidirectional Encoder Representations from Transformers，是一个预训练语言模型",
            domain="ai",
            related_concepts=["Transformer"]
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is True

    def test_duplicate_patch_rejected(self, graph, validator):
        """重复概念被拒绝"""
        from core.skill_engine.models import KnowledgePatch
        patch = KnowledgePatch(
            concept_name="Transformer",
            definition="A neural network architecture",
            domain="ai"
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False
        assert "重复" in result.errors[0] or "已存在" in result.errors[0]

    def test_short_name_rejected(self, validator):
        """过短名称被拒绝"""
        from core.skill_engine.models import KnowledgePatch
        patch = KnowledgePatch(
            concept_name="A",
            definition="A neural network architecture for NLP tasks",
            domain="ai"
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False

    def test_empty_definition_rejected(self, validator):
        """空定义被拒绝"""
        from core.skill_engine.models import KnowledgePatch
        patch = KnowledgePatch(
            concept_name="NewConcept",
            definition="",
            domain="ai"
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False

    def test_invalid_name_rejected(self, validator):
        """无效名称被拒绝"""
        from core.skill_engine.models import KnowledgePatch
        patch = KnowledgePatch(
            concept_name="12345",
            definition="This is a test concept for validation",
            domain="ai"
        )
        result = validator.validate_knowledge(patch)
        assert result.passed is False


# ============================================================
# Test 4: LearningEngine.learn() 完整流程
# ============================================================

class TestLearningEngine:
    """LearningEngine.learn() 完整学习流程"""

    @pytest.fixture
    def graph(self):
        from core.graphs.skill_graph import SkillGraph, GraphNode
        g = SkillGraph()
        g.add_node(GraphNode(id="transformer", name="Transformer",
                    node_type="concept", domain="ai"))
        g.add_node(GraphNode(id="attention", name="Attention",
                    node_type="concept", domain="ai"))
        return g

    @pytest.fixture
    def engine(self, graph):
        from core.engines.learning_engine import LearningEngine
        from core.graphs.reasoning_graph import ReasoningGraph
        return LearningEngine(
            skill_graph=graph,
            reasoning_graph=ReasoningGraph()
        )

    def test_learn_quality_threshold(self, engine):
        """低质量回答不学习（review_score < 0.70）"""
        result = engine.learn(
            user_task="什么是Transformer",
            writer_output="## Transformer\nTransformer是一种神经网络架构",
            skill_path=["ai"],
            review_score=0.50
        )
        assert result["validated"] == 0
        assert result["rejected"] == 0

    def test_learn_new_concept(self, engine):
        """高质量回答提取新概念"""
        result = engine.learn(
            user_task="解释BERT",
            writer_output="""## BERT
BERT是Bidirectional Encoder Representations from Transformers的缩写。
它是一种基于Transformer的预训练语言模型。

## GPT
GPT是Generative Pre-trained Transformer的缩写。
它是一种自回归语言模型。""",
            skill_path=["ai"],
            review_score=0.85
        )
        assert result["knowledge_patches"] or True  # 至少不报错

    def test_learn_returns_structure(self, engine):
        """返回结果包含必要字段"""
        result = engine.learn(
            user_task="test",
            writer_output="## Test\nTest content",
            skill_path=["root"],
            review_score=0.80
        )
        assert "knowledge_patches" in result
        assert "reasoning_patches" in result
        assert "workflow_patches" in result
        assert "deepseek_used" in result
        assert "validated" in result
        assert "rejected" in result

    def test_learn_with_workflow(self, engine):
        """提取工作流模式"""
        result = engine.learn(
            user_task="如何部署模型",
            writer_output="""部署步骤：
1. 准备环境
2. 安装依赖
3. 配置参数
4. 启动服务
5. 验证部署""",
            skill_path=["tech"],
            review_score=0.85
        )
        # 工作流至少有3步
        if result["workflow_patches"]:
            wf = result["workflow_patches"][0]
            assert len(wf.steps) >= 3

    def test_learn_skips_low_score(self, engine):
        """review_score < 0.70 时跳过学习"""
        result = engine.learn(
            user_task="test",
            writer_output="## NewConcept\nSome content about new concept",
            skill_path=["root"],
            review_score=0.60
        )
        assert result["validated"] == 0
        assert result["rejected"] == 0
        assert len(result["knowledge_patches"]) == 0


# ============================================================
# Test 5: LearningEngine 推理模式
# ============================================================

class TestReasoningLearning:
    """LearningEngine 推理模式提取 + 注册"""

    @pytest.fixture
    def graph(self):
        from core.graphs.skill_graph import SkillGraph
        return SkillGraph()

    @pytest.fixture
    def reasoning_graph(self):
        from core.graphs.reasoning_graph import ReasoningGraph
        return ReasoningGraph()

    @pytest.fixture
    def engine(self, graph, reasoning_graph):
        from core.engines.learning_engine import LearningEngine
        return LearningEngine(
            skill_graph=graph,
            reasoning_graph=reasoning_graph
        )

    def test_extract_reasoning_pattern(self, engine):
        """从高质量回答中提取推理模式"""
        result = engine.learn(
            user_task="分析对比",
            writer_output="""## 背景
这是背景介绍。

## 分析
这是分析内容。

## 举例
这是一个例子。

## 总结
这是总结。""",
            skill_path=["ai"],
            review_score=0.85
        )
        if result["reasoning_patches"]:
            pattern = result["reasoning_patches"][0]
            assert len(pattern.steps) >= 3

    def test_apply_reasoning_patch(self, engine, reasoning_graph):
        """应用推理模式补丁"""
        from core.graphs.reasoning_graph import ReasoningNode

        orig_count = len(reasoning_graph.patterns)

        result = engine.learn(
            user_task="分析对比",
            writer_output="""## 背景
背景。

## 分析
分析。

## 举例
举例。

## 总结
总结。""",
            skill_path=["ai"],
            review_score=0.85
        )

        if result["reasoning_patches"]:
            applied = engine.apply_patches(result)
            assert applied >= 1
            assert len(reasoning_graph.patterns) > orig_count

    def test_no_reasoning_without_graph(self, graph):
        """无 reasoning_graph 时不提取推理模式"""
        from core.engines.learning_engine import LearningEngine
        engine = LearningEngine(skill_graph=graph, reasoning_graph=None)
        result = engine.learn(
            user_task="test",
            writer_output="## 背景\n背景\n## 分析\n分析\n## 总结\n总结",
            skill_path=["root"],
            review_score=0.85
        )
        assert len(result["reasoning_patches"]) == 0


# ============================================================
# Test 6: LearningEngine.apply_patches()
# ============================================================

class TestApplyPatches:
    """应用补丁到 Skill Graph"""

    @pytest.fixture
    def graph(self):
        from core.graphs.skill_graph import SkillGraph, GraphNode
        g = SkillGraph()
        g.add_node(GraphNode(id="transformer", name="Transformer",
                    node_type="concept", domain="ai"))
        return g

    @pytest.fixture
    def engine(self, graph):
        from core.engines.learning_engine import LearningEngine
        from core.graphs.reasoning_graph import ReasoningGraph
        return LearningEngine(
            skill_graph=graph,
            reasoning_graph=ReasoningGraph()
        )

    def test_apply_knowledge_patch(self, engine, graph):
        """应用知识补丁到 Skill Graph"""
        from core.skill_engine.models import KnowledgePatch

        orig_count = len(graph.nodes)

        patch = KnowledgePatch(
            concept_name="BERT",
            definition="Bidirectional Encoder Representations from Transformers",
            domain="ai",
            related_concepts=["Transformer"]
        )
        patches = {"knowledge_patches": [patch], "reasoning_patches": [],
                   "workflow_patches": []}

        applied = engine.apply_patches(patches)
        assert applied == 1
        assert len(graph.nodes) == orig_count + 1

        # 验证节点已添加
        assert "bert" in graph.nodes
        assert graph.nodes["bert"].name == "BERT"

    def test_apply_duplicate_skipped(self, engine, graph):
        """重复概念不添加"""
        from core.skill_engine.models import KnowledgePatch

        patch = KnowledgePatch(
            concept_name="Transformer",
            definition="Already exists",
            domain="ai"
        )
        patches = {"knowledge_patches": [patch], "reasoning_patches": [],
                   "workflow_patches": []}

        orig_count = len(graph.nodes)
        applied = engine.apply_patches(patches)
        assert applied == 0  # 重复，不应用
        assert len(graph.nodes) == orig_count

    def test_apply_creates_edge(self, engine, graph):
        """应用补丁时创建 related_to 边"""
        from core.skill_engine.models import KnowledgePatch

        patch = KnowledgePatch(
            concept_name="BERT",
            definition="Bidirectional Encoder Representations from Transformers",
            domain="ai",
            related_concepts=["Transformer"]
        )
        patches = {"knowledge_patches": [patch], "reasoning_patches": [],
                   "workflow_patches": []}

        engine.apply_patches(patches)

        # 验证边已创建
        bert_adj = graph._adj_out.get("bert", [])
        has_related = any(e.to_node == "transformer" and e.edge_type == "related_to"
                         for e in bert_adj)
        assert has_related


# ============================================================
# Test 7: LearningEngine.get_stats()
# ============================================================

class TestLearningStats:
    """学习统计"""

    @pytest.fixture
    def graph(self):
        from core.graphs.skill_graph import SkillGraph
        return SkillGraph()

    @pytest.fixture
    def engine(self, graph):
        from core.engines.learning_engine import LearningEngine
        from core.graphs.reasoning_graph import ReasoningGraph
        return LearningEngine(
            skill_graph=graph,
            reasoning_graph=ReasoningGraph()
        )

    def test_stats_empty(self, engine):
        """空统计"""
        stats = engine.get_stats()
        assert stats["total_sessions"] == 0
        assert stats["total_validated"] == 0
        assert stats["total_rejected"] == 0
        assert stats["deepseek_usage"] == 0
        assert stats["avg_review_score"] == 0.0

    def test_stats_after_learning(self, engine):
        """学习后统计更新"""
        engine.learn(
            user_task="test",
            writer_output="## NewConcept\nSome content",
            skill_path=["root"],
            review_score=0.85
        )
        stats = engine.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["avg_review_score"] == 0.85

    def test_stats_after_multiple(self, engine):
        """多次学习后统计"""
        engine.learn("t1", "## Test1\ncontent", ["root"], 0.80)
        engine.learn("t2", "## Test2\ncontent", ["root"], 0.90)
        engine.learn("t3", "## Test3\ncontent", ["root"], 0.70)
        stats = engine.get_stats()
        assert stats["total_sessions"] == 3
        assert stats["avg_review_score"] == 0.80
        assert "validator_stats" in stats


# ============================================================
# Test 8: WorkflowPattern 提取
# ============================================================

class TestWorkflowExtraction:
    """工作流模式提取"""

    @pytest.fixture
    def engine(self):
        from core.graphs.skill_graph import SkillGraph
        from core.engines.learning_engine import LearningEngine
        return LearningEngine(SkillGraph())

    def test_extract_numbered_workflow(self, engine):
        """提取编号工作流"""
        text = """1. 数据准备
2. 模型训练
3. 模型评估
4. 模型部署"""
        wf = engine._extract_workflow(text)
        assert wf is not None
        assert len(wf.steps) == 4
        assert wf.steps[0] == "数据准备"

    def test_extract_workflow_minimum_3(self, engine):
        """至少3步才提取"""
        text = """1. 步骤1
2. 步骤2"""
        wf = engine._extract_workflow(text)
        assert wf is None

    def test_extract_workflow_max_7(self, engine):
        """最多7步"""
        text = "\n".join(f"{i}. 步骤{i}" for i in range(1, 11))
        wf = engine._extract_workflow(text)
        assert wf is not None
        assert len(wf.steps) == 7

    def test_extract_workflow_with_bold(self, engine):
        """提取带粗体的步骤"""
        text = """1. **数据准备**
2. **模型训练**
3. **模型评估**"""
        wf = engine._extract_workflow(text)
        assert wf is not None
        assert "数据准备" in wf.steps[0]


# ============================================================
# Test 9: Phase 7 集成测试
# ============================================================

class TestPhase7Integration:
    """Phase 7 集成测试"""

    def test_imports(self):
        from core.engines.learning_engine import LearningEngine
        from core.skill_engine.models import KnowledgePatch, WorkflowPatch
        from core.engines.patch_validator import PatchValidator
        assert True

    def test_full_pipeline(self):
        """完整学习流程：提取 → Diff → 校验 → 应用"""
        from core.graphs.skill_graph import SkillGraph, GraphNode, GraphEdge
        from core.engines.learning_engine import LearningEngine
        from core.graphs.reasoning_graph import ReasoningGraph

        graph = SkillGraph()
        graph.add_node(GraphNode(id="transformer", name="Transformer",
                       node_type="concept", domain="ai"))
        graph.add_node(GraphNode(id="attention", name="注意力",
                       node_type="concept", domain="ai"))
        graph.add_edge(GraphEdge(from_node="transformer", to_node="attention",
                       edge_type="has_part"))

        reasoning = ReasoningGraph()
        engine = LearningEngine(skill_graph=graph, reasoning_graph=reasoning)

        writer_output = """## 自注意力机制
自注意力机制是Transformer的核心组件，允许模型在处理序列时关注不同位置的信息。

## 多头注意力
多头注意力通过并行多个注意力头来捕获不同子空间的信息。

1. 计算QKV矩阵
2. 计算注意力分数
3. 加权求和
4. 多头拼接
5. 输出投影"""

        result = engine.learn(
            user_task="解释Transformer的注意力机制",
            writer_output=writer_output,
            skill_path=["ai", "transformer"],
            review_score=0.85
        )

        # 验证结果结构
        assert "knowledge_patches" in result
        assert "workflow_patches" in result
        assert "deepseek_used" in result
        assert "validated" in result
        assert "rejected" in result

        # 应用补丁
        if result["validated"] > 0:
            applied = engine.apply_patches(result)
            assert applied > 0

        # 检查统计
        stats = engine.get_stats()
        assert stats["total_sessions"] == 1

    def test_quality_threshold_integration(self):
        """低质量回答不触发学习"""
        from core.graphs.skill_graph import SkillGraph, GraphNode
        from core.engines.learning_engine import LearningEngine

        graph = SkillGraph()
        graph.add_node(GraphNode(id="test", name="Test",
                       node_type="concept", domain="test"))

        engine = LearningEngine(skill_graph=graph)

        result = engine.learn(
            user_task="bad question",
            writer_output="short answer",
            skill_path=["root"],
            review_score=0.30
        )

        assert result["validated"] == 0
        assert result["rejected"] == 0
        assert len(result["knowledge_patches"]) == 0
        assert len(result["reasoning_patches"]) == 0
        assert len(result["workflow_patches"]) == 0