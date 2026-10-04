"""P1 接线验证（2026-10-04）

覆盖四项「模块在、接线断」的能力，每项都断言到**可观察的行为**而非实现细节：

① TASK_TEMPLATES → Knowledge `outline` → Writer「## 参考大纲」
   （此前 outline 恒为 []，Writer 永远拼到「- 无」）
② 上下文压缩三件套（recorder / counter / compressor）→ ContextTracker
   → /api/v1/context 端点 + WS `context_usage` 推送
③ `guard_io` 越界账本（IO 维度，此前零调用）
④ `LearningEngine._deepseek_analyze` 实装 + 四重成本护栏
"""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.base.agent import AgentInput, AgentOutput
from models.workflow import WorkflowInput


# ============================================================
# ① TASK_TEMPLATES 接线
# ============================================================

class TestTaskTemplatesWiring:

    def test_template_keys_cover_all_determinable_types(self):
        """_determine_task_type 能返回的每个类型都必须在 TASK_TEMPLATES 里有模板"""
        from agents.knowledge.agent import TASK_TEMPLATES
        agent_probe = {"活动策划", "方案设计", "分析报告", "文档撰写", "通用任务"}
        assert agent_probe <= set(TASK_TEMPLATES)
        for sections in TASK_TEMPLATES.values():
            assert isinstance(sections, list) and sections

    @pytest.mark.asyncio
    async def test_outline_populated_by_task_type(self):
        """活动策划类输入 → outline 取到「活动策划」模板，不再是空列表"""
        from agents.knowledge.agent import KnowledgeAgent, TASK_TEMPLATES

        agent = KnowledgeAgent()
        out = await agent.execute(AgentInput(content="帮我策划一场校园运动会活动方案"))
        data = json.loads(out.content)

        assert data["task_type"] == "活动策划"
        assert data["outline"] == TASK_TEMPLATES["活动策划"]
        assert data["outline"], "outline 不得为空（能力丢失的根因）"

    @pytest.mark.asyncio
    async def test_outline_falls_back_to_generic(self):
        """无关键词命中的输入 → 落到「通用任务」模板，而不是空列表"""
        from agents.knowledge.agent import KnowledgeAgent, TASK_TEMPLATES

        agent = KnowledgeAgent()
        out = await agent.execute(AgentInput(content="嗯嗯随便聊聊吧"))
        data = json.loads(out.content)

        assert data["task_type"] == "通用任务"
        assert data["outline"] == TASK_TEMPLATES["通用任务"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("with_knowledge", [True, False])
    async def test_writer_template_prompt_carries_outline(self, monkeypatch, with_knowledge):
        """两个 prompt 分支（有/无参考知识）都必须把大纲拼进提示词"""
        from agents.writer.agent import WriterAgent

        agent = WriterAgent()
        captured = {}

        async def _fake_call_llm(prompt, **kwargs):
            captured["prompt"] = prompt
            return "生成结果"

        monkeypatch.setattr(agent, "_call_llm", _fake_call_llm)

        parsed = {
            "original_question": "写一份方案",
            "keywords": ["方案"],
            "knowledge_items": (
                [{"keyword": "方案", "content": "参考内容"}] if with_knowledge else []
            ),
            "requirements": [],
            "outline": ["一、需求分析", "二、方案设计"],
            "task_type": "方案设计",
        }
        await agent._generate_with_template(
            parsed, [{"title": "需求分析", "content": "…"}], "方案设计"
        )

        prompt = captured["prompt"]
        assert "一、需求分析" in prompt
        assert "二、方案设计" in prompt
        assert "- 无" not in prompt.split("## 参考大纲")[1].split("##")[0]


# ============================================================
# ② 上下文压缩三件套接线
# ============================================================

def _feed_rounds(sandbox_id: str, rounds: int, body: str = "上下文内容" * 120):
    """往 RoundRecorder 里灌 rounds 轮记录"""
    from core.context_round_recorder import get_round_recorder
    recorder = get_round_recorder()
    for i in range(rounds):
        recorder.record_round(
            sandbox_id,
            f"第{i + 1}轮用户需求{body}",
            {
                "final_result": body,
                "steps": [{"agent_id": "writer", "success": True, "output": body}],
            },
        )
    return recorder


class TestContextWiring:

    @pytest.fixture(autouse=True)
    def _clean_sandboxes(self):
        from core.context_tracker import get_context_tracker
        tracker = get_context_tracker()
        for sid in ("t_ctx_a", "t_ctx_b", "t_ctx_c"):
            tracker.clear(sid)
        yield
        for sid in ("t_ctx_a", "t_ctx_b", "t_ctx_c"):
            tracker.clear(sid)

    def test_tracker_records_round_and_returns_usage_payload(self):
        from core.context_tracker import get_context_tracker

        _feed_rounds("t_ctx_a", 2)
        payload = get_context_tracker().track("t_ctx_a", "第三轮问题", {"final_result": "x", "steps": []})

        assert payload["sandbox_id"] == "t_ctx_a"
        assert payload["round"] == 3
        assert payload["limit"] == 4096
        assert 0.0 <= payload["usage_ratio"] <= 1.0
        assert payload["total_tokens"] == (
            payload["system_tokens"] + payload["history_tokens"] + payload["user_input_tokens"]
        )
        assert payload["compressed"] is False

    def test_tracker_compresses_when_over_threshold(self):
        """阈值压到 1% 后，超过保留轮数即触发压缩并产出摘要"""
        from app.config import settings
        from core.context_tracker import get_context_tracker

        settings.context_compress_threshold = 0.01
        _feed_rounds("t_ctx_b", 5)

        payload = get_context_tracker().track("t_ctx_b", "新一轮问题", {"final_result": "y", "steps": []})

        assert payload["compressed"] is True
        assert payload["compression_count"] == 1
        assert "压缩" in payload["message"]

        pending = get_context_tracker().pending_history("t_ctx_b")
        assert pending and pending[0]["user"] == "【此前对话摘要】"
        assert "# 对话摘要" in pending[0]["assistant"]

    def test_no_compression_below_threshold(self):
        from app.config import settings
        from core.context_tracker import get_context_tracker

        settings.context_compress_threshold = 0.99
        _feed_rounds("t_ctx_c", 5)

        payload = get_context_tracker().track("t_ctx_c", "新一轮问题", {"final_result": "z", "steps": []})
        assert payload["compressed"] is False
        assert get_context_tracker().pending_history("t_ctx_c") is None

    @pytest.mark.asyncio
    async def test_ws_manager_exposes_context_usage_broadcast(self):
        from api.websocket.manager import WebSocketManager

        captured = []

        class _Sink(WebSocketManager):
            async def send_message(self, message, connection_id=None):
                captured.append(message)

        payload = {"total_tokens": 100, "limit": 4096, "usage_ratio": 0.02}
        await _Sink().broadcast_context_usage(payload)

        assert captured == [{"type": "context_usage", "data": payload}]

    @pytest.mark.asyncio
    async def test_context_router_endpoints(self):
        from api.v1.context.router import (
            clear_context, compress_context, get_context_config, get_context_usage,
            CompressRequest,
        )

        _feed_rounds("t_ctx_a", 2)

        usage = await get_context_usage(sandbox_id="t_ctx_a")
        assert usage["sandbox_id"] == "t_ctx_a"
        assert len(usage["records"]) == 2
        assert usage["records"][0]["round"] == 1

        cfg = await get_context_config()
        assert cfg["context_max_tokens"] == 4096
        assert cfg["keep_recent_rounds"] == 3

        res = await compress_context(CompressRequest(sandbox_id="t_ctx_a"))
        assert res["sandbox_id"] == "t_ctx_a"
        assert res["compression_count"] == 1
        assert "# 对话摘要" in res["summary"]
        assert res["saved_tokens"] >= 0

        cleared = await clear_context("t_ctx_a")
        assert cleared["status"] == "success"
        assert (await get_context_usage(sandbox_id="t_ctx_a"))["round"] == 0

    @pytest.mark.asyncio
    async def test_workflow_execute_triggers_context_tracking(self, monkeypatch):
        """工作流跑完必须触发上下文追踪 + WS 推送（接线点存在的证据）"""
        import core.context_tracker as ct_mod
        import core.workflow.service as svc_mod
        from core.workflow.service import WorkflowService

        tracked, broadcast = [], []

        class _FakeTracker:
            def track(self, sandbox_id, user_input, workflow_output):
                tracked.append((sandbox_id, user_input))
                return {"total_tokens": 1, "limit": 4096, "usage_ratio": 0.0}

        monkeypatch.setattr(ct_mod, "get_context_tracker", lambda: _FakeTracker())

        async def _fake_broadcast(payload):
            broadcast.append(payload)

        monkeypatch.setattr(svc_mod, "_broadcast_context_usage", _fake_broadcast)

        from agents.base.agent_registry import AgentRegistry
        registry = MagicMock(spec=AgentRegistry)
        registry.execute_agent = AsyncMock()

        async def _normal(agent_id, agent_input):
            return AgentOutput(
                content=json.dumps({"result": f"output from {agent_id}"}),
                success=True,
                metadata={"knowledge_count": 1} if agent_id == "knowledge" else {},
            )

        registry.execute_agent.side_effect = _normal

        service = WorkflowService(registry)
        await service.execute(WorkflowInput(user_input="测试上下文追踪", sandbox_id="t_ctx_a"))

        assert tracked == [("t_ctx_a", "测试上下文追踪")]
        assert len(broadcast) == 1


# ============================================================
# ③ guard_io 接线
# ============================================================

class TestGuardIoWiring:

    def test_guard_io_records_violation_and_returns_false(self):
        from agents.base.contract import (
            IOResource, contract_violations, guard_io, reset_contract_ledger,
        )

        reset_contract_ledger()
        try:
            # judge 契约只声明 filesystem
            assert guard_io("judge", IOResource.CLOUD_API, "单测") is False
            ledger = contract_violations()
            assert ledger["total"] == 1
            assert ledger["by_agent"]["judge"] == 1
            assert ledger["detail"][0]["field"] == "io_resources"

            # 已声明的资源放行且不记账
            assert guard_io("judge", IOResource.FILESYSTEM, "单测") is True
            assert contract_violations()["total"] == 1
        finally:
            reset_contract_ledger()

    def test_guarded_call_sites_are_declared_in_contracts(self):
        """新接入的 guard_io 资源必须都在契约里，否则上线即狂报越界"""
        from agents.base.contract import CONTRACTS, IOResource

        knowledge = CONTRACTS["knowledge"].io_resources
        for res in (IOResource.WEB, IOResource.LOCAL_INDEX, IOResource.DATABASE,
                    IOResource.OLLAMA_GPU, IOResource.FILESYSTEM):
            assert res in knowledge, f"knowledge 未声明 {res.value}"

        result = CONTRACTS["result"].io_resources
        for res in (IOResource.CLOUD_API, IOResource.FILESYSTEM):
            assert res in result, f"result 未声明 {res.value}"

    def test_base_agent_facade_delegates_to_guard_io(self):
        from agents.base.contract import IOResource
        from agents.knowledge.agent import KnowledgeAgent
        from agents.judge.agent import JudgeAgent

        assert KnowledgeAgent()._guard_io(IOResource.WEB, "单测") is True
        assert JudgeAgent()._guard_io(IOResource.WEB, "单测") is False

    @pytest.mark.asyncio
    async def test_knowledge_agent_run_stays_within_contract(self):
        """常规运行不应产生任何 knowledge 维度的 IO 越界记录"""
        from agents.base.contract import contract_violations, reset_contract_ledger
        from agents.knowledge.agent import KnowledgeAgent

        reset_contract_ledger()
        try:
            await KnowledgeAgent().execute(AgentInput(content="生成校园AI助手方案"))
            assert contract_violations()["by_agent"].get("knowledge", 0) == 0
        finally:
            reset_contract_ledger()


# ============================================================
# ④ _deepseek_analyze 实装 + 成本护栏
# ============================================================

class _FakeCloudClient:
    def __init__(self, reply: str = ""):
        self.reply = reply
        self.calls = 0

    async def generate_cloud(self, prompt: str, system_prompt=None, model=None) -> str:
        self.calls += 1
        return self.reply


class TestDeepseekAnalyzeBudget:

    @pytest.fixture(autouse=True)
    def _reset_budget(self):
        from core.engines.learning_engine import deepseek_analyze_budget
        deepseek_analyze_budget().reset()
        yield
        deepseek_analyze_budget().reset()

    def test_disabled_switch_blocks_call(self, monkeypatch):
        from app.config import settings
        from core.engines.learning_engine import deepseek_analyze_budget

        monkeypatch.setattr(settings, "learning_deepseek_enabled", False)
        allowed, reason = deepseek_analyze_budget().acquire()
        assert allowed is False
        assert "enabled" in reason

    def test_daily_quota_is_enforced(self, monkeypatch):
        from app.config import settings
        from core.engines.learning_engine import deepseek_analyze_budget

        monkeypatch.setattr(settings, "learning_deepseek_enabled", True)
        monkeypatch.setattr(settings, "learning_deepseek_max_per_day", 2)
        monkeypatch.setattr(settings, "learning_deepseek_min_interval_seconds", 0)

        budget = deepseek_analyze_budget()
        assert budget.acquire()[0] is True
        assert budget.acquire()[0] is True
        allowed, reason = budget.acquire()
        assert allowed is False
        assert "日额度" in reason
        assert budget.stats()["used_today"] == 2

    def test_min_interval_is_enforced(self, monkeypatch):
        from app.config import settings
        from core.engines.learning_engine import deepseek_analyze_budget

        monkeypatch.setattr(settings, "learning_deepseek_enabled", True)
        monkeypatch.setattr(settings, "learning_deepseek_max_per_day", 10)
        monkeypatch.setattr(settings, "learning_deepseek_min_interval_seconds", 600)

        budget = deepseek_analyze_budget()
        assert budget.acquire()[0] is True
        allowed, reason = budget.acquire()
        assert allowed is False
        assert "不足" in reason


class TestDeepseekAnalyzeImplementation:

    @pytest.fixture(autouse=True)
    def _enable_and_reset(self, monkeypatch):
        from app.config import settings
        from core.engines.learning_engine import deepseek_analyze_budget

        monkeypatch.setattr(settings, "learning_deepseek_enabled", True)
        monkeypatch.setattr(settings, "learning_deepseek_min_interval_seconds", 0)
        monkeypatch.setattr(settings, "learning_deepseek_max_per_day", 20)
        deepseek_analyze_budget().reset()
        yield
        deepseek_analyze_budget().reset()

    def _engine(self, deepseek_enabled=True):
        from core.engines.learning_engine import LearningEngine
        from core.graphs.skill_graph import SkillGraph
        return LearningEngine(
            skill_graph=SkillGraph(), persist=False, deepseek_enabled=deepseek_enabled
        )

    def test_returns_patch_when_worth_learning(self, monkeypatch):
        import core.llm.client as client_mod
        from core.engines.learning_engine import LearningEngine

        fake = _FakeCloudClient(json.dumps({
            "worth_learning": True,
            "definition": "向量数据库是专为高维向量相似度检索设计的数据库系统。",
            "domain": "tech.ai",
            "related": ["向量检索", "ANN"],
            "confidence": 0.86,
        }, ensure_ascii=False))
        monkeypatch.setattr(client_mod, "get_llm_client", lambda: fake)

        engine = self._engine()
        patch = engine._deepseek_analyze("向量数据库", "上下文片段", domain="tech.ai")

        assert patch is not None
        assert patch.concept_name == "向量数据库"
        assert patch.domain == "tech.ai"
        assert patch.related_concepts == ["向量检索", "ANN"]
        assert patch.source == "deepseek_analyze"
        assert fake.calls == 1

    @pytest.mark.parametrize("reply", [
        json.dumps({"worth_learning": False, "definition": "随便"}, ensure_ascii=False),
        json.dumps({"worth_learning": True, "definition": "太短"}, ensure_ascii=False),
        "```json\n{\"worth_learning\": true, \"definition\": \"模型输出被 markdown 围栏包住时的定义内容\"}\n```",
        "完全不是 JSON",
        "",
    ])
    def test_invalid_or_unworthy_replies_yield_none(self, monkeypatch, reply):
        import core.llm.client as client_mod

        monkeypatch.setattr(client_mod, "get_llm_client", lambda: _FakeCloudClient(reply))
        result = self._engine()._deepseek_analyze("某个概念", "上下文")

        expected = "围栏" in reply
        assert (result is not None) is expected

    def test_returns_none_when_disabled(self, monkeypatch):
        import core.llm.client as client_mod

        fake = _FakeCloudClient(json.dumps({"worth_learning": True, "definition": "某个足够长的定义内容"}))
        monkeypatch.setattr(client_mod, "get_llm_client", lambda: fake)

        assert self._engine(deepseek_enabled=False)._deepseek_analyze("概念", "上下文") is None
        assert fake.calls == 0, "开关关闭时不得发起云调用"

    def test_learn_marks_deepseek_used_and_respects_per_run_cap(self, monkeypatch):
        import core.llm.client as client_mod
        from core.graphs.skill_graph import GraphNode, SkillGraph

        fake = _FakeCloudClient(json.dumps({
            "worth_learning": True,
            "definition": "这是一个由云端判定值得收录的概念定义。",
            "domain": "tech",
            "confidence": 0.8,
        }, ensure_ascii=False))
        monkeypatch.setattr(client_mod, "get_llm_client", lambda: fake)

        graph = SkillGraph()
        graph.add_node(GraphNode(id="transformer", name="Transformer", node_type="concept", domain="ai"))

        from core.engines.learning_engine import LearningEngine
        engine = LearningEngine(skill_graph=graph, persist=False, deepseek_enabled=True)

        result = engine.learn(
            user_task="讲讲这些技术",
            writer_output="\n".join(f"## Concept{i}\n定义内容 {i}" for i in range(6)),
            skill_path=["ai"],
            review_score=0.9,
        )

        assert result["deepseek_used"] is True
        # 单次 learn() 最多上云 3 个概念（第 4 层护栏）
        assert fake.calls == 3
        assert engine._learning_log[-1]["deepseek_attempts"] == 3
