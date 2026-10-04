"""测试全局护栏 —— 测试绝不写生产数据。

2026-09-24 事故复盘
-------------------
`tests/test_phase7.py` 用 `LearningEngine(SkillGraph())`（空图）构造引擎，
调用 `apply_patches()` 时把内存里仅剩的 2 个节点全量 `save()` 到
`core/graphs/skill_graph.yaml`，一次性抹掉 636 个节点的生产知识库
（后经 D:\\AgentMatrix_backup_20260922 整目录备份恢复）。

同一次跑测试还污染了 `core/graphs/reasoning_graph.yaml`
（写进 1 条从测试文本「背景/分析/举例/总结」提取的假模式）。

根因
----
三处**默认落盘路径都指向仓库内生产文件，且构造时不可注入**：
1. `LearningEngine._skill_graph_yaml`   → core/graphs/skill_graph.yaml
2. `KnowledgeAuditor._save_skill_graph` → core/graphs/skill_graph.yaml
3. `ReasoningGraph._YAML_PATH`          → core/graphs/reasoning_graph.yaml
4. `skill_learner._default_buffer_path` → storage/pending_learning/_feedback_buffer.json

防护分层
--------
生产侧（真护栏，即使非测试代码误用也拦得住）：
  - `learning_engine.MIN_NODE_RETENTION` 缩水护栏 + 原子写 + 自动备份
  - `knowledge_auditor._save_skill_graph` 同款护栏
测试侧（本文件，逐条封住写入通道）：
  - 禁止 LearningEngine / KnowledgeAuditor 落盘
  - ReasoningGraph 读写重定向到 tmp_path
  - SkillLearner 默认反馈缓冲区重定向到 tmp_path
  - PendingStore 待审队列根目录重定向到 tmp_path
  - PersonalBrain 画像目录重定向到 tmp_path
  - MemoryStore 记忆目录重定向到 tmp_path（2026-10-04 补漏）
  - （已移除）旧版 KnowledgeService 知识库文件重定向 —— 该实现已删除

若某个测试确实要验证落盘逻辑，请显式传入 `yaml_path=` / `buffer_path=`
指向 `tmp_path`，不要依赖默认路径。
"""

import pytest


@pytest.fixture(autouse=True)
def _forbid_learning_engine_production_writes(monkeypatch):
    """禁止测试把 SkillGraph 写回生产 YAML（全局兜底）。"""
    try:
        from core.engines.learning_engine import LearningEngine
    except Exception:  # 模块导入失败时不影响测试收集
        return

    def _no_persist(self):  # noqa: ANN001
        return False

    monkeypatch.setattr(LearningEngine, "_persist_safe", _no_persist)


@pytest.fixture(autouse=True)
def _forbid_knowledge_auditor_production_writes(monkeypatch):
    """禁止测试通过 KnowledgeAuditor 写回生产 YAML（同类风险，一并堵住）。"""
    try:
        from core.engines.knowledge_auditor import KnowledgeAuditor
    except Exception:
        return

    def _no_save(self):  # noqa: ANN001
        return None

    for name in ("_persist_skill_graph", "_save_skill_graph"):
        if hasattr(KnowledgeAuditor, name):
            monkeypatch.setattr(KnowledgeAuditor, name, _no_save)


@pytest.fixture(autouse=True)
def _isolate_reasoning_graph(monkeypatch, tmp_path):
    """推理图谱读写重定向到 tmp_path。

    隔离原因：`ReasoningGraph()` 会从生产 `reasoning_graph.yaml` 加载自学习模式，
    导致「本次新学到的模式」与「文件里已有的同 id 模式」重合时计数不增长，
    测试假设从预置模式起算就会被生产状态打破（test_phase7
    `assert len(reasoning_graph.patterns) > orig_count` → `assert 6 > 6`）。
    同时阻止测试把假模式写进生产文件。
    """
    try:
        from core.graphs.reasoning_graph import ReasoningGraph
    except Exception:
        return

    monkeypatch.setattr(
        ReasoningGraph, "_YAML_PATH", str(tmp_path / "reasoning_graph.yaml")
    )

    def _no_save(self):  # noqa: ANN001
        return None

    monkeypatch.setattr(ReasoningGraph, "save_learned_patterns", _no_save)


@pytest.fixture(autouse=True)
def _isolate_skill_learner_buffer(monkeypatch, tmp_path):
    """SkillLearner 默认反馈缓冲区重定向到 tmp_path。

    隔离原因：`SkillLearner()` 默认 persist=True 且 buffer_path 缺省指向
    `storage/pending_learning/_feedback_buffer.json`，测试会往生产缓冲区灌
    测试反馈，可能在生产侧凑够 min_samples 触发一次假学习。
    """
    try:
        import core.skill_engine.skill_learner as _sl
    except Exception:
        return

    monkeypatch.setattr(
        _sl, "_default_buffer_path", lambda: str(tmp_path / "_feedback_buffer.json")
    )


@pytest.fixture(autouse=True)
def _isolate_pending_queue(monkeypatch, tmp_path):
    """待审学习队列默认根目录重定向到 tmp_path。

    隔离原因：`PendingStore()` 缺省落在 `storage/pending_learning/`。
    跑一次 `test_skill_engine_v2_phase678.py` 就曾把 4 条
    `domain=tech.ai.agent` 的测试垃圾写进生产待审队列，
    污染人工审批列表。
    """
    try:
        import core.engines.learning_intake as _li
    except Exception:
        return

    d = tmp_path / "pending_learning"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_li, "_pending_root", lambda: str(d))


@pytest.fixture(autouse=True)
def _isolate_personal_brain_profiles(monkeypatch, tmp_path):
    """个人画像读写重定向到 tmp_path。

    隔离原因：`PersonalBrain("test")` 的画像缺省落在 `storage/profiles/test.json`。
    测试 `update_from_session` 会把它写成 `learning_stage=intermediate` 并持久化，
    导致 `test_build_context_empty`（断言空画像 → ctx == ""）在第二次及以后的
    运行中必然失败（已实测复现）。
    """
    try:
        import core.personal_brain.brain as _brain
    except Exception:
        return

    d = tmp_path / "profiles"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_brain, "get_profiles_dir", lambda: str(d))


@pytest.fixture(autouse=True)
def _isolate_memory_store(monkeypatch, tmp_path):
    """长期记忆读写重定向到 tmp_path。

    2026-10-04 补漏：护栏原来的五项只封了 LearningEngine / KnowledgeAuditor /
    ReasoningGraph / SkillLearner / PendingStore / 画像，**漏了 MemoryStore**。
    实测跑一次全量测试，`storage/memory/default.json` 的 access_count 被 +8
    （WorkflowService 每轮结束都会 get_memory_store() 并更新访问计数）。
    与 9/24 事故同款漏网，只是这次没造成数据丢失。
    """
    try:
        import core.memory_store.store as _ms
    except Exception:
        return

    d = tmp_path / "memory"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_ms, "get_memory_dir", lambda: str(d))


# 注：原 `_isolate_legacy_knowledge_service` 护栏已随旧实现一并移除
# （2026-10-04，批次 3）：`knowledge/service.py`（JSON 字典版 KnowledgeService）
# 已删除，`tests/test_api/test_knowledge_api.py` 改为打在役的 SQLite 实现，
# 并自行用临时数据库（tmp_path）隔离 —— 该写入通道已不存在，护栏不再需要。
