"""Agent 职责边界契约（V1）

── 为什么需要它 ──
AgentMatrix 的 5 个 Agent 是**单例**（`agent_registry.py:25-29` 每个 Agent 只
new 一次），彼此通过 `core/workflow/service.py` 串成链。这套结构能跑，但有一条
隐患：**边界全靠约定，没有任何东西在检查约定**。

典型后果（本项目真实存在，见下）：
- `WriterAgent.execute` 把 `_current_system_prompt` 等写在自己的实例上，
  再由 `_generate_*` 读取（`writer/agent.py:801-980` 写、`:1165-1443` 读）。
  单例 + 无锁 ⇒ 两个请求并发时，后到的请求会覆盖前一个的 system prompt。
- `JudgeAgent` 被明确约束为「纯规则、不调 LLM」，但这条约束没有代码兜底，
  任何人加一行 `_call_llm` 都不会有任何东西报错。

契约把这些「口头约定」变成**可声明、可校验、可审计**的三件事：

1. **声明**（本模块的 `AgentContract`）：每个 Agent 的 6 项边界写在一处。
   字段与 `docs/Agent职责边界契约.md` 一一对应：
       输入类型 / 输出类型 / 是否允许调 LLM / 是否允许外部 IO /
       失败语义 / 是否有 per-request 状态（并发安全）
2. **运行时校验**：`guard_llm_call()` 挂在 `BaseAgent._call_llm` 上，
   任何越界的模型调用都会被记账（严格模式下直接抛 `ContractViolation`）。
   `AgentRegistry.execute_agent` 依据 `requires_serialization()` 对
   per-request 有状态的 Agent 加锁，把「已知会串味」变成「结构上串不了味」。
3. **静态审计**：`scripts/audit_agent_contracts.py` 用 AST 扫描真实代码，
   比对声明与实际。声明漂移会在审计和测试里直接失败。

── 设计取舍 ──
- `request_state` **不是手写的**，而是从 `declared_writes` 推导：只要有一个属性
  被标为 `PER_REQUEST`，该 Agent 就是 `SHARED_MUTABLE`。这样「第六字段」不会
  和实际写入行为脱节。
- 契约只做**边界检查**，不做流程编排。它回答「这个 Agent 能不能干这件事」，
  不回答「这件事该不该干」——后者是 `WorkflowService` 的职责。
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Tuple

logger = logging.getLogger(__name__)

# 严格模式：越界即抛异常（测试与 CI 打开；生产默认只记账 + 告警）
STRICT_ENV_VAR = "AGENT_CONTRACT_STRICT"


# ──────────────────────────── 枚举 ────────────────────────────


class ContractViolation(RuntimeError):
    """Agent 越过自身声明的职责边界。"""

    def __init__(self, agent_id: str, field: str, detail: str):
        self.agent_id = agent_id
        self.field = field
        self.detail = detail
        super().__init__(f"[contract:{agent_id}] {field} —— {detail}")


class LLMPolicy(str, Enum):
    """是否允许调用大模型"""

    NEVER = "never"        # 契约禁止（如 Judge / Knowledge）
    OPTIONAL = "optional"  # 允许，但存在不调模型的规则路径
    REQUIRED = "required"  # 主路径必须调用


class LLMScope(str, Enum):
    """允许调用的模型范围"""

    NONE = "none"    # 不调模型
    LOCAL = "local"  # 仅本地 Ollama（8GB 显存内）
    CLOUD = "cloud"  # 仅云端 API
    BOTH = "both"    # 本地或云端均可


class FailureSemantics(str, Enum):
    """失败语义"""

    FATAL = "fatal"        # 失败即整链失败，向上抛
    DEGRADED = "degraded"  # 必须返回降级结果，不得抛（链的可控性来源）


class IOResource(str, Enum):
    """外部 IO 资源"""

    OLLAMA_GPU = "ollama_gpu"      # 本地 Ollama（占显存）
    CLOUD_API = "cloud_api"        # 云端 HTTP
    WEB = "web"                    # 联网检索
    LOCAL_INDEX = "local_index"    # 本地代码/知识索引
    DATABASE = "database"          # SQLite / MySQL
    FILESYSTEM = "filesystem"      # 读写文件（含技能树 YAML、导出目录）


class WriteKind(str, Enum):
    """实例属性写入的性质"""

    CACHE = "cache"              # 幂等懒加载缓存，允许共享
    PER_REQUEST = "per_request"  # 承载单次请求数据 ⇒ 单例下并发不安全


class RequestState(str, Enum):
    """第六字段：是否有 per-request 实例状态"""

    REENTRANT = "reentrant"              # 无请求态，可并发
    SHARED_MUTABLE = "shared_mutable"    # 有请求态写在单例上，必须串行


# ──────────────────────────── 受控词表 ────────────────────────────

INPUT_KINDS = frozenset({"text", "context", "image", "document", "code", "structured_json"})
OUTPUT_KINDS = frozenset(
    {"text", "structured_json", "routing_decision", "files", "knowledge_package"}
)

# 与 agent_registry.initialize_all_agents 注册的 Agent 集合保持一致
REQUIRED_AGENT_IDS = ("knowledge", "writer", "review", "judge", "result")


# ──────────────────────────── 契约定义 ────────────────────────────


@dataclass(frozen=True)
class AgentContract:
    """单个 Agent 的职责边界声明"""

    agent_id: str
    role: str
    input_types: Tuple[str, ...]
    output_types: Tuple[str, ...]
    llm_policy: LLMPolicy
    llm_scope: LLMScope
    io_resources: FrozenSet[IOResource]
    failure_semantics: FailureSemantics
    # (属性名, 写入性质) —— 允许在 execute 路径上写的实例属性白名单
    declared_writes: Tuple[Tuple[str, WriteKind], ...] = ()
    notes: str = ""

    # ── 派生属性 ──

    @property
    def per_request_attrs(self) -> FrozenSet[str]:
        return frozenset(name for name, kind in self.declared_writes if kind is WriteKind.PER_REQUEST)

    @property
    def cache_attrs(self) -> FrozenSet[str]:
        return frozenset(name for name, kind in self.declared_writes if kind is WriteKind.CACHE)

    @property
    def request_state(self) -> RequestState:
        """第六字段由 declared_writes 推导，避免与真实写入行为脱节"""
        return RequestState.SHARED_MUTABLE if self.per_request_attrs else RequestState.REENTRANT

    @property
    def requires_serialization(self) -> bool:
        return self.request_state is RequestState.SHARED_MUTABLE

    @property
    def allowed_llm(self) -> bool:
        return self.llm_policy is not LLMPolicy.NEVER

    @property
    def allows_cloud(self) -> bool:
        return self.llm_scope in (LLMScope.CLOUD, LLMScope.BOTH)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "input_types": list(self.input_types),
            "output_types": list(self.output_types),
            "llm_policy": self.llm_policy.value,
            "llm_scope": self.llm_scope.value,
            "io_resources": sorted(r.value for r in self.io_resources),
            "failure_semantics": self.failure_semantics.value,
            "request_state": self.request_state.value,
            "per_request_attrs": sorted(self.per_request_attrs),
            "requires_serialization": self.requires_serialization,
            "notes": self.notes,
        }


def _w(*items: Tuple[str, WriteKind]) -> Tuple[Tuple[str, WriteKind], ...]:
    return tuple(items)


CONTRACTS: Dict[str, AgentContract] = {
    # ── Knowledge：链路第一环，IO 最重、却不碰模型 ──
    "knowledge": AgentContract(
        agent_id="knowledge",
        role="知识获取与结构化：把用户请求解析成 Writer 可直接消费的知识包",
        input_types=("text", "context", "image", "document", "code"),
        output_types=("knowledge_package", "structured_json"),
        llm_policy=LLMPolicy.NEVER,
        llm_scope=LLMScope.NONE,
        io_resources=frozenset(
            {
                IOResource.WEB,
                IOResource.LOCAL_INDEX,
                IOResource.OLLAMA_GPU,
                IOResource.DATABASE,
                IOResource.FILESYSTEM,
            }
        ),
        failure_semantics=FailureSemantics.DEGRADED,
        declared_writes=_w(
            ("_skill_manager", WriteKind.CACHE),
            ("_intent_analyzer", WriteKind.CACHE),
            ("_task_classifier", WriteKind.CACHE),
            ("_web_search_plugin", WriteKind.CACHE),
            ("_code_munch_plugin", WriteKind.CACHE),
            ("_timely_knowledge_service", WriteKind.CACHE),
            ("_knowledge_service", WriteKind.CACHE),
            ("_fallback_knowledge", WriteKind.CACHE),
            ("_fallback_keywords", WriteKind.CACHE),
        ),
        notes=(
            "全链路唯一 0 次 LLM 调用的重 IO Agent（84.8KB / execute 393 行）。"
            "OLLAMA_GPU 仅经 VisionPlugin 做图片转述，不参与文本生成。"
            "所有插件缺失都回退到规则路径并在 metadata 标注 source，故为 DEGRADED。"
        ),
    ),
    # ── Writer：链路唯一的 GPU 大户 ──
    "writer": AgentContract(
        agent_id="writer",
        role="内容生成：按技能栈装配 system prompt 并产出正文",
        input_types=("text", "context", "structured_json"),
        output_types=("text",),
        llm_policy=LLMPolicy.REQUIRED,
        llm_scope=LLMScope.LOCAL,
        io_resources=frozenset({IOResource.OLLAMA_GPU, IOResource.FILESYSTEM}),
        failure_semantics=FailureSemantics.DEGRADED,
        declared_writes=_w(
            ("_handler_chain", WriteKind.CACHE),
            ("_skill_manager", WriteKind.CACHE),
            ("_prompt_builder", WriteKind.CACHE),
            ("_template_engine", WriteKind.CACHE),
            ("_current_skill_path", WriteKind.PER_REQUEST),
            ("_current_skill_stack", WriteKind.PER_REQUEST),
            ("_current_system_prompt", WriteKind.PER_REQUEST),
        ),
        notes=(
            "7 处 _call_llm，max_tokens 最高 4096，是链上唯一持续占用显存的 Agent。"
            "全部调用点均为 use_cloud=False ⇒ 契约限定 LOCAL，越权上云会被 guard 拦下。"
            "!! 已知风险：3 个 _current_* 属性承载单次请求数据却写在单例上，"
            "并发请求会互相覆盖 system prompt；当前由注册表按契约串行化兜住，"
            "根治方案是把请求态改为局部变量/参数传递（见文档『待办』）。"
        ),
    ),
    # ── Review：默认走规则，LLM 仅在被显式要求时触发 ──
    "review": AgentContract(
        agent_id="review",
        role="质量评审：产出六维评分与改进建议",
        input_types=("text", "structured_json", "context"),
        output_types=("structured_json",),
        llm_policy=LLMPolicy.OPTIONAL,
        llm_scope=LLMScope.LOCAL,
        io_resources=frozenset({IOResource.OLLAMA_GPU, IOResource.FILESYSTEM}),
        failure_semantics=FailureSemantics.DEGRADED,
        declared_writes=_w(
            ("_skill_manager", WriteKind.CACHE),
            ("_review_engine", WriteKind.CACHE),
            ("_rules", WriteKind.CACHE),
            ("_v2_configs", WriteKind.CACHE),
        ),
        notes=(
            "唯一 LLM 调用点 _review_with_llm，由 input_data.use_llm 门控，"
            "默认走 review_rules.yaml 规则路径 ⇒ OPTIONAL 而非 REQUIRED。"
        ),
    ),
    # ── Judge：纯规则，全链路没有模型调用 ──
    "judge": AgentContract(
        agent_id="judge",
        role="路由决策：按难度阈值 + 评审分决定本地输出还是上云补救",
        input_types=("structured_json",),
        output_types=("routing_decision", "structured_json"),
        llm_policy=LLMPolicy.NEVER,
        llm_scope=LLMScope.NONE,
        io_resources=frozenset({IOResource.FILESYSTEM}),
        failure_semantics=FailureSemantics.DEGRADED,
        declared_writes=(),
        notes=(
            "纯规则双阈值路由，0 次模型调用（唯一外部读取是判断云 key 是否存在）。"
            "无实例状态写入 ⇒ REENTRANT，可安全并发。"
        ),
    ),
    # ── Result：链路末端，唯一会上云的 Agent ──
    "result": AgentContract(
        agent_id="result",
        role="结果交付：按 Judge 决策做云端补救，并导出 docx/pptx/md",
        input_types=("text", "structured_json"),
        output_types=("text", "files"),
        llm_policy=LLMPolicy.OPTIONAL,
        llm_scope=LLMScope.BOTH,
        io_resources=frozenset(
            {IOResource.OLLAMA_GPU, IOResource.CLOUD_API, IOResource.FILESYSTEM}
        ),
        failure_semantics=FailureSemantics.DEGRADED,
        declared_writes=(),
        notes=(
            "链上唯一允许 use_cloud=True 的 Agent（full_rewrite / polish 两条路径）。"
            "全部方法为 staticmethod，无实例状态 ⇒ REENTRANT。"
        ),
    ),
}


# ──────────────────────────── 导入期自检 ────────────────────────────


def validate_contracts(contracts: Optional[Dict[str, AgentContract]] = None) -> None:
    """校验契约自身合法（词表、唯一性、派生一致性）。导入期调用。"""
    contracts = CONTRACTS if contracts is None else contracts
    for agent_id, c in contracts.items():
        if c.agent_id != agent_id:
            raise ValueError(f"契约键 {agent_id} 与 agent_id {c.agent_id} 不一致")
        unknown_in = set(c.input_types) - INPUT_KINDS
        unknown_out = set(c.output_types) - OUTPUT_KINDS
        if unknown_in:
            raise ValueError(f"[{agent_id}] 未知输入类型: {sorted(unknown_in)}")
        if unknown_out:
            raise ValueError(f"[{agent_id}] 未知输出类型: {sorted(unknown_out)}")
        if not c.input_types or not c.output_types:
            raise ValueError(f"[{agent_id}] 输入/输出类型不得为空")
        if c.llm_policy is LLMPolicy.NEVER and c.llm_scope is not LLMScope.NONE:
            raise ValueError(f"[{agent_id}] LLM 策略为 NEVER 时 scope 必须为 none")
        if c.llm_policy is not LLMPolicy.NEVER and c.llm_scope is LLMScope.NONE:
            raise ValueError(f"[{agent_id}] 允许调 LLM 时 scope 不得为 none")
        names = [name for name, _ in c.declared_writes]
        if len(names) != len(set(names)):
            raise ValueError(f"[{agent_id}] declared_writes 存在重名")
    missing = set(REQUIRED_AGENT_IDS) - set(contracts)
    if missing:
        raise ValueError(f"以下 Agent 缺少契约声明: {sorted(missing)}")
    extra = set(contracts) - set(REQUIRED_AGENT_IDS)
    if extra:
        raise ValueError(f"以下契约没有对应 Agent: {sorted(extra)}")


# ──────────────────────────── 运行时守卫 ────────────────────────────

_ledger: Dict[str, int] = {}
_ledger_detail: list = []
_ledger_lock = threading.Lock()


def strict_mode() -> bool:
    return os.environ.get(STRICT_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def _record(agent_id: str, field_name: str, detail: str) -> None:
    with _ledger_lock:
        _ledger[agent_id] = _ledger.get(agent_id, 0) + 1
        _ledger_detail.append({"agent_id": agent_id, "field": field_name, "detail": detail})
    logger.warning("[Contract] %s 越界 %s: %s", agent_id, field_name, detail)


def guard_llm_call(agent_id: str, use_cloud: bool, model: str = "") -> None:
    """在真实发起模型调用前校验 LLM 边界。

    越界行为：策略为 NEVER 的 Agent 调模型，或 scope 限定 LOCAL 的 Agent 走云端。
    严格模式抛 `ContractViolation`；否则记账 + WARNING，不阻断业务。
    """
    contract = CONTRACTS.get(agent_id)
    if contract is None:
        _record(agent_id, "llm_policy", "未声明契约的 Agent 发起了模型调用")
        if strict_mode():
            raise ContractViolation(agent_id, "llm_policy", "缺少契约声明")
        return

    if contract.llm_policy is LLMPolicy.NEVER:
        detail = f"契约声明 llm_policy=never，却发起了模型调用（model={model or 'default'}）"
        _record(agent_id, "llm_policy", detail)
        if strict_mode():
            raise ContractViolation(agent_id, "llm_policy", detail)
        return

    if use_cloud and not contract.allows_cloud:
        detail = (
            f"契约声明 llm_scope={contract.llm_scope.value}，"
            f"却尝试云端调用（model={model or 'default'}）"
        )
        _record(agent_id, "llm_scope", detail)
        if strict_mode():
            raise ContractViolation(agent_id, "llm_scope", detail)


def guard_io(agent_id: str, resource: IOResource, detail: str = "") -> bool:
    """校验外部 IO 边界。返回是否放行。

    仅做判定与记账，不抛异常——IO 缺失在本项目里普遍走降级路径，
    因此调用方应按返回值决定是否跳过该 IO，而不是让异常打断整链。
    """
    contract = CONTRACTS.get(agent_id)
    if contract is None or resource in contract.io_resources:
        return True
    _record(agent_id, "io_resources", f"未声明使用 {resource.value}；{detail}".strip("；"))
    return False


def contract_violations() -> Dict[str, Any]:
    """导出越界账本（供 /metrics 或测试断言使用）"""
    with _ledger_lock:
        return {"total": sum(_ledger.values()), "by_agent": dict(_ledger), "detail": list(_ledger_detail)}


def reset_contract_ledger() -> None:
    with _ledger_lock:
        _ledger.clear()
        _ledger_detail.clear()


# ──────────────────────────── 查询接口 ────────────────────────────


def get_contract(agent_id: str) -> Optional[AgentContract]:
    return CONTRACTS.get(agent_id)


def requires_serialization(agent_id: str) -> bool:
    contract = CONTRACTS.get(agent_id)
    return bool(contract and contract.requires_serialization)


def describe_all() -> Dict[str, Any]:
    """全部契约的只读快照，供 API / 前端展示"""
    return {agent_id: c.to_dict() for agent_id, c in CONTRACTS.items()}


validate_contracts()
