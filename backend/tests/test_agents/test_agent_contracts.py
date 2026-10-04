"""Agent 职责边界契约测试

三层验证：
1. 声明层   —— 5 个 Agent 都有契约，词表合法，派生字段自洽
2. 静态层   —— 审计脚本扫真实源码，声明与实现不得漂移（零 error）
3. 运行时层 —— _call_llm 的边界守卫真的会拦，注册表真的会串行化
"""
import asyncio
import importlib

import pytest

from agents.base.agent import AgentInput, AgentOutput, BaseAgent
from agents.base.agent_registry import AgentRegistry
from agents.base.contract import (
    CONTRACTS,
    REQUIRED_AGENT_IDS,
    ContractViolation,
    FailureSemantics,
    LLMPolicy,
    LLMScope,
    RequestState,
    WriteKind,
    contract_violations,
    describe_all,
    get_contract,
    guard_llm_call,
    requires_serialization,
    reset_contract_ledger,
    strict_mode,
)


@pytest.fixture(autouse=True)
def _clean_ledger(monkeypatch):
    """每个用例独占一份越界账本，并默认关闭严格模式（用例内自行打开）"""
    monkeypatch.delenv("AGENT_CONTRACT_STRICT", raising=False)
    reset_contract_ledger()
    yield
    reset_contract_ledger()


# ──────────────────────────── 1. 声明层 ────────────────────────────


class TestContractDeclarations:
    def test_contract_coverage_matches_registry(self):
        """契约集合必须与注册表注册的 Agent 集合完全一致"""
        assert set(CONTRACTS) == set(REQUIRED_AGENT_IDS)

    def test_contract_maps_to_real_agent_class(self):
        """每个契约都要能对应到真实模块中的 Agent 类（防映射写错）"""
        modules = {
            "knowledge": ("agents.knowledge.agent", "KnowledgeAgent"),
            "writer": ("agents.writer.agent", "WriterAgent"),
            "review": ("agents.review.agent", "ReviewAgent"),
            "judge": ("agents.judge.agent", "JudgeAgent"),
            "result": ("agents.result.agent", "ResultAgent"),
        }
        assert set(modules) == set(CONTRACTS)
        for agent_id, (module_name, class_name) in modules.items():
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            assert issubclass(cls, BaseAgent), f"{class_name} 未继承 BaseAgent"
            assert cls is not None, agent_id

    def test_derived_request_state_is_consistent(self):
        """第六字段由 declared_writes 推导，二者不得互相矛盾"""
        for agent_id, c in CONTRACTS.items():
            if c.per_request_attrs:
                assert c.request_state is RequestState.SHARED_MUTABLE, agent_id
                assert c.requires_serialization is True, agent_id
            else:
                assert c.request_state is RequestState.REENTRANT, agent_id
                assert c.requires_serialization is False, agent_id

    def test_llm_policy_and_scope_agree(self):
        for agent_id, c in CONTRACTS.items():
            if c.llm_policy is LLMPolicy.NEVER:
                assert c.llm_scope is LLMScope.NONE, agent_id
                assert c.allowed_llm is False
            else:
                assert c.llm_scope is not LLMScope.NONE, agent_id
                assert c.allowed_llm is True

    def test_known_boundaries_are_pinned(self):
        """把已核实的边界钉死，任何人改动都会在这里被拦住"""
        # 两个纯规则 Agent 不得调模型
        assert get_contract("judge").llm_policy is LLMPolicy.NEVER
        assert get_contract("knowledge").llm_policy is LLMPolicy.NEVER
        # Writer 全部调用点 use_cloud=False ⇒ 契约限定本地
        assert get_contract("writer").llm_scope is LLMScope.LOCAL
        assert get_contract("writer").llm_policy is LLMPolicy.REQUIRED
        # 只有 Result 允许上云
        cloud_agents = {aid for aid, c in CONTRACTS.items() if c.allows_cloud}
        assert cloud_agents == {"result"}
        # 只有 Writer 有 per-request 状态
        assert {aid for aid, c in CONTRACTS.items() if c.requires_serialization} == {"writer"}

    def test_every_agent_declares_failure_semantics(self):
        for agent_id, c in CONTRACTS.items():
            assert isinstance(c.failure_semantics, FailureSemantics), agent_id

    def test_describe_all_is_serialisable(self):
        snapshot = describe_all()
        assert set(snapshot) == set(CONTRACTS)
        for payload in snapshot.values():
            assert isinstance(payload["io_resources"], list)
            assert isinstance(payload["request_state"], str)


# ──────────────────────────── 2. 静态层 ────────────────────────────


class TestStaticAudit:
    def test_audit_reports_no_errors(self):
        """审计脚本扫真实代码：声明与实现不得漂移"""
        audit_module = importlib.import_module("scripts.audit_agent_contracts")
        findings, scans = audit_module.audit()
        errors = [f for f in findings if f.level == "error"]
        assert not errors, "契约漂移:\n" + "\n".join(
            f"[{f.code}] {f.agent_id}: {f.message}" for f in errors
        )
        assert set(scans) == set(CONTRACTS)

    def test_audit_detects_all_five_agents(self):
        audit_module = importlib.import_module("scripts.audit_agent_contracts")
        _, scans = audit_module.audit()
        for agent_id, scan in scans.items():
            assert scan.class_name, f"{agent_id} 未定位到 Agent 类"

    def test_declared_writes_superset_of_class_writes(self):
        """C2 的断言版本：类内写入必须被完整登记"""
        audit_module = importlib.import_module("scripts.audit_agent_contracts")
        _, scans = audit_module.audit()
        for agent_id, scan in scans.items():
            declared = get_contract(agent_id).per_request_attrs | get_contract(agent_id).cache_attrs
            assert not (scan.class_writes - declared), (
                f"{agent_id} 有未登记写入: {sorted(scan.class_writes - declared)}"
            )

    def test_never_llm_agents_have_no_call_sites(self):
        audit_module = importlib.import_module("scripts.audit_agent_contracts")
        _, scans = audit_module.audit()
        for agent_id, scan in scans.items():
            if get_contract(agent_id).llm_policy is LLMPolicy.NEVER:
                assert not scan.llm_call_lines, (
                    f"{agent_id} 声明 never 却存在调用点 {scan.llm_call_lines}"
                )


# ──────────────────────────── 3. 运行时层 ────────────────────────────


class TestRuntimeGuard:
    def test_never_policy_blocks_in_strict_mode(self, monkeypatch):
        monkeypatch.setenv("AGENT_CONTRACT_STRICT", "1")
        assert strict_mode() is True
        with pytest.raises(ContractViolation) as exc:
            guard_llm_call("judge", use_cloud=False)
        assert "llm_policy" in str(exc.value)

    def test_never_policy_blocks_knowledge(self, monkeypatch):
        monkeypatch.setenv("AGENT_CONTRACT_STRICT", "1")
        with pytest.raises(ContractViolation):
            guard_llm_call("knowledge", use_cloud=False)

    def test_local_scope_blocks_cloud_escalation(self, monkeypatch):
        """Writer 声明 LOCAL，越权上云必须被拦"""
        monkeypatch.setenv("AGENT_CONTRACT_STRICT", "1")
        with pytest.raises(ContractViolation) as exc:
            guard_llm_call("writer", use_cloud=True, model="deepseek-flash")
        assert "llm_scope" in str(exc.value)

    def test_result_may_use_cloud(self, monkeypatch):
        monkeypatch.setenv("AGENT_CONTRACT_STRICT", "1")
        guard_llm_call("result", use_cloud=True)  # 不抛即通过

    def test_non_strict_records_without_raising(self):
        assert strict_mode() is False
        guard_llm_call("judge", use_cloud=False, model="qwen2.5vl:7b")
        ledger = contract_violations()
        assert ledger["by_agent"].get("judge") == 1
        assert ledger["total"] == 1

    def test_unknown_agent_is_flagged(self, monkeypatch):
        monkeypatch.setenv("AGENT_CONTRACT_STRICT", "1")
        with pytest.raises(ContractViolation):
            guard_llm_call("ghost-agent", use_cloud=False)

    async def test_base_agent_wiring_actually_blocks(self, monkeypatch):
        """确认守卫真的接在 BaseAgent._call_llm 上，而不只是模块里有个函数"""

        class FakeJudge(BaseAgent):
            def __init__(self):
                super().__init__("judge", "Fake Judge")

            async def execute(self, input_data: AgentInput) -> AgentOutput:  # pragma: no cover
                return AgentOutput(content="")

        monkeypatch.setenv("AGENT_CONTRACT_STRICT", "1")
        agent = FakeJudge()
        with pytest.raises(ContractViolation):
            await agent._call_llm("hello", use_cloud=False)

    async def test_base_agent_wiring_allows_declared_agent(self):
        """契约允许的调用不得被误拦（假 Positive 检查）"""

        class FakeWriter(BaseAgent):
            def __init__(self):
                super().__init__("writer", "Fake Writer")

            async def execute(self, input_data: AgentInput) -> AgentOutput:  # pragma: no cover
                return AgentOutput(content="")

        agent = FakeWriter()
        agent.llm_client = _StubLLMClient()
        result = await agent._call_llm("hello", use_cloud=False)
        assert result == "stub-response"


class _StubLLMClient:
    async def generate(self, prompt, use_cloud=False, system_prompt=None, model=None):
        return "stub-response"


class TestRegistrySerialization:
    async def test_shared_mutable_agent_is_serialized(self):
        """Writer 有 per-request 状态 ⇒ 并发 execute_agent 必须被串行化"""

        class ConcurrencyProbe(BaseAgent):
            def __init__(self):
                super().__init__("writer", "Probe")
                self.active = 0
                self.max_active = 0

            async def execute(self, input_data: AgentInput) -> AgentOutput:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.05)
                self.active -= 1
                return AgentOutput(content="ok")

        registry = AgentRegistry()
        probe = ConcurrencyProbe()
        registry.register_agent(probe)

        await asyncio.gather(
            *(registry.execute_agent("writer", AgentInput(content=str(i))) for i in range(5))
        )
        assert probe.max_active == 1, f"Writer 未串行化，峰值并发 {probe.max_active}"

    async def test_reentrant_agent_runs_concurrently(self):
        """无请求态的 Agent 不应被串行化拖慢"""

        class ConcurrencyProbe(BaseAgent):
            def __init__(self):
                super().__init__("judge", "Probe")
                self.active = 0
                self.max_active = 0

            async def execute(self, input_data: AgentInput) -> AgentOutput:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                await asyncio.sleep(0.05)
                self.active -= 1
                return AgentOutput(content="ok")

        registry = AgentRegistry()
        probe = ConcurrencyProbe()
        registry.register_agent(probe)

        await asyncio.gather(
            *(registry.execute_agent("judge", AgentInput(content=str(i))) for i in range(5))
        )
        assert probe.max_active > 1, "Judge 被误串行化"

    async def test_requires_serialization_helper(self):
        assert requires_serialization("writer") is True
        assert requires_serialization("judge") is False
        assert requires_serialization("ghost") is False

    async def test_locks_are_per_agent(self):
        registry = AgentRegistry()
        assert registry._get_lock("writer") is registry._get_lock("writer")
        assert registry._get_lock("result") is not registry._get_lock("writer")


def test_contract_snapshot_to_dict_roundtrip():
    for agent_id, c in CONTRACTS.items():
        payload = c.to_dict()
        assert payload["agent_id"] == agent_id
        assert payload["request_state"] in {s.value for s in RequestState}
        for name in c.declared_writes:
            assert isinstance(name[1], WriteKind)
