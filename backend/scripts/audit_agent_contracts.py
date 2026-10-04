"""Agent 职责边界契约 —— 静态审计

用 AST 扫描 5 个 Agent 的真实源码，比对 `agents/base/contract.py` 里的声明。
声明与代码一旦漂移，本脚本以非 0 退出码结束，`tests/test_agents/test_agent_contracts.py`
也会调用同一套逻辑做断言。

用法：
    cd backend
    python scripts/audit_agent_contracts.py            # 打印报告
    python scripts/audit_agent_contracts.py --json      # 输出 JSON（供 CI 消费）

检查项：
    C1 LLM 边界    —— 声明 llm_policy=never 的 Agent 不得出现模型调用点
    C2 写入白名单  —— execute 可达路径上写的实例属性，必须全部在 declared_writes 中
    C3 缓存/请求态 —— 声明为 per_request 的属性必须真的在 execute 路径上被写
    C4 IO 边界     —— 代码里出现的 IO 依赖必须已在 io_resources 中声明
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agents.base.contract import (  # noqa: E402
    CONTRACTS,
    IOResource,
    LLMPolicy,
    WriteKind,
)

AGENT_MODULES = {
    "knowledge": "agents/knowledge/agent.py",
    "writer": "agents/writer/agent.py",
    "review": "agents/review/agent.py",
    "judge": "agents/judge/agent.py",
    "result": "agents/result/agent.py",
}

LLM_CALL_ATTRS = {"_call_llm", "_call_llm_chat", "_call_local_model"}

# import / 调用 → IO 资源映射
_IO_IMPORT_MAP = {
    "httpx": IOResource.CLOUD_API,
    "requests": IOResource.CLOUD_API,
    "aiohttp": IOResource.CLOUD_API,
    "sqlite3": IOResource.DATABASE,
    "pymysql": IOResource.DATABASE,
    "sqlalchemy": IOResource.DATABASE,
    "ollama": IOResource.OLLAMA_GPU,
}


@dataclass
class MethodInfo:
    name: str
    writes: Set[str] = field(default_factory=set)
    llm_calls: List[int] = field(default_factory=list)
    self_calls: Set[str] = field(default_factory=set)
    self_reads: Set[str] = field(default_factory=set)


# 构造期/生命周期方法：写入属于实例初始化，不受边界白名单约束
_EXEMPT_METHODS = {"__init__", "initialize", "shutdown"}


@dataclass
class AgentScan:
    agent_id: str
    path: str
    class_name: str = ""
    methods: Dict[str, MethodInfo] = field(default_factory=dict)
    reachable: Set[str] = field(default_factory=set)
    imports: Set[str] = field(default_factory=set)

    # ── 派生 ──
    @property
    def llm_call_lines(self) -> List[Tuple[str, int]]:
        return [
            (m.name, ln)
            for m in self.methods.values()
            for ln in m.llm_calls
        ]

    @property
    def reachable_writes(self) -> Set[str]:
        out: Set[str] = set()
        for name in self.reachable:
            out |= self.methods[name].writes
        return out

    @property
    def class_writes(self) -> Set[str]:
        """类内（除构造/生命周期方法外）出现过的全部实例属性写入。

        C2 用这个集合而非 reachable_writes：因为 Writer 的 `_generate_*` 是被
        TaskHandler 对象以 `self.agent._generate_xxx()` 转调的，纯 `self.` 调用图
        跟不到那里，只查可达集会产生**假通过**。要求「写在 self 上的属性一律登记」
        既更严也更简单。
        """
        out: Set[str] = set()
        for name, m in self.methods.items():
            if name in _EXEMPT_METHODS:
                continue
            out |= m.writes
        return out

    @property
    def io_found(self) -> Set[IOResource]:
        found: Set[IOResource] = set()
        for mod in self.imports:
            root = mod.split(".")[0]
            if root in _IO_IMPORT_MAP:
                found.add(_IO_IMPORT_MAP[root])
        return found


class _ClassScanner(ast.NodeVisitor):
    """收集单个类的方法级信息（不深入嵌套类）"""

    def __init__(self) -> None:
        self.methods: Dict[str, MethodInfo] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._scan_method(item)

    def _scan_method(self, fn: ast.AST) -> None:
        info = MethodInfo(name=fn.name)
        for sub in _iter_own_nodes(fn):
            if isinstance(sub, ast.Assign):
                for t in sub.targets:
                    if _is_self_attr(t):
                        info.writes.add(t.attr)
            elif isinstance(sub, ast.AnnAssign):
                if sub.value is not None and _is_self_attr(sub.target):
                    info.writes.add(sub.target.attr)
            elif isinstance(sub, ast.AugAssign):
                if _is_self_attr(sub.target):
                    info.writes.add(sub.target.attr)
            elif isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id == "self":
                        if func.attr in LLM_CALL_ATTRS:
                            info.llm_calls.append(getattr(sub, "lineno", 0))
                        else:
                            info.self_calls.add(func.attr)
            elif isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
                if sub.value.id == "self":
                    info.self_reads.add(sub.attr)
        self.methods[fn.name] = info


def _iter_own_nodes(root: ast.AST):
    """遍历 root 的后代节点，但**剪掉嵌套 ClassDef 的整棵子树**。

    必须剪而不是跳过：`ast.walk` 会无条件产出所有后代，只 `continue` 掉 ClassDef
    自己、却仍会走到它内部的语句。KnowledgeAgent 里就有一个内联的
    `FallbackKnowledgeService`，它的 `self._items` 属于那个工具类，
    不剪会把别人的状态误判成本 Agent 的状态。
    """
    stack = list(ast.iter_child_nodes(root))
    while stack:
        cur = stack.pop()
        if isinstance(cur, ast.ClassDef):
            continue
        yield cur
        stack.extend(ast.iter_child_nodes(cur))


def _is_self_attr(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def scan_agent(agent_id: str) -> AgentScan:
    rel = AGENT_MODULES[agent_id]
    path = BACKEND_DIR / rel
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    scan = AgentScan(agent_id=agent_id, path=rel)

    expected = agent_id.capitalize() + "Agent"
    target: Optional[ast.ClassDef] = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            base_names = {getattr(b, "id", getattr(b, "attr", "")) for b in node.bases}
            if node.name == expected or "BaseAgent" in base_names:
                target = node
                break
    if target is None:
        return scan

    scan.class_name = target.name
    scanner = _ClassScanner()
    scanner.visit(target)
    scan.methods = scanner.methods

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            scan.imports |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            scan.imports.add(node.module)

    scan.reachable = _reachable_from(scan.methods, "execute")
    return scan


def _reachable_from(methods: Dict[str, MethodInfo], entry: str) -> Set[str]:
    """沿 `self.<method>()` 调用 + `self.<property>` 属性访问求入口可达集。

    属性访问必须一起跟：本项目的懒加载都写成 `@property`，而 property 的触发
    点是不带括号的 `self.xxx`，只跟调用会漏掉整条懒加载链。
    """
    if entry not in methods:
        return set()
    seen: Set[str] = set()
    frontier = [entry]
    while frontier:
        cur = frontier.pop()
        if cur in seen or cur not in methods:
            continue
        seen.add(cur)
        for callee in methods[cur].self_calls | methods[cur].self_reads:
            if callee in methods and callee not in seen:
                frontier.append(callee)
    return seen


@dataclass
class Finding:
    level: str  # "error" | "warning" | "info"
    code: str
    agent_id: str
    message: str


def audit() -> Tuple[List[Finding], Dict[str, AgentScan]]:
    findings: List[Finding] = []
    scans: Dict[str, AgentScan] = {}

    for agent_id, contract in CONTRACTS.items():
        scan = scan_agent(agent_id)
        scans[agent_id] = scan
        if not scan.class_name:
            findings.append(
                Finding("error", "C0", agent_id, f"未能在 {scan.path} 定位 Agent 类")
            )
            continue

        # C1 LLM 边界
        if contract.llm_policy is LLMPolicy.NEVER and scan.llm_call_lines:
            sites = ", ".join(f"{m}:{ln}" for m, ln in scan.llm_call_lines)
            findings.append(
                Finding(
                    "error",
                    "C1",
                    agent_id,
                    f"契约声明 llm_policy=never，但代码存在模型调用点: {sites}",
                )
            )

        # C2 写入白名单（全类口径，避免调用图假通过）
        declared = contract.per_request_attrs | contract.cache_attrs
        undeclared = scan.class_writes - declared
        if undeclared:
            findings.append(
                Finding(
                    "error",
                    "C2",
                    agent_id,
                    f"类内写入未声明的实例属性: {sorted(undeclared)}；"
                    f"请补进 declared_writes（并按 CACHE / PER_REQUEST 定性）",
                )
            )

        # C3 声明了 per_request 却没人写 ⇒ 声明过期
        stale = contract.per_request_attrs - scan.class_writes
        if stale:
            findings.append(
                Finding(
                    "warning",
                    "C3",
                    agent_id,
                    f"声明为 per_request 但类内未见写入: {sorted(stale)}",
                )
            )

        # C3b per_request 属性的写入点应落在 execute 路径上（否则并发语义存疑）
        outside = contract.per_request_attrs - scan.reachable_writes
        if outside:
            findings.append(
                Finding(
                    "warning",
                    "C3b",
                    agent_id,
                    f"per_request 属性不在 execute 可达路径上写入: {sorted(outside)}；"
                    f"请确认它确实是请求态而非缓存",
                )
            )

        # C4 IO 边界
        missing_io = scan.io_found - set(contract.io_resources)
        if missing_io:
            findings.append(
                Finding(
                    "warning",
                    "C4",
                    agent_id,
                    f"代码使用了未声明 IO: {sorted(r.value for r in missing_io)}",
                )
            )

        if scan.reachable_writes and contract.requires_serialization:
            findings.append(
                Finding(
                    "info",
                    "C5",
                    agent_id,
                    f"有 per-request 状态 {sorted(contract.per_request_attrs)} ⇒ "
                    f"注册表按契约串行化该 Agent",
                )
            )

    return findings, scans


def print_report(findings: List[Finding], scans: Dict[str, AgentScan]) -> None:
    print("=" * 78)
    print("Agent 职责边界契约 —— 静态审计")
    print("=" * 78)
    for agent_id, scan in scans.items():
        c = CONTRACTS[agent_id]
        print(f"\n[{agent_id}]  class={scan.class_name or 'N/A'}  file={scan.path}")
        print(
            f"  in={list(c.input_types)}  out={list(c.output_types)}\n"
            f"  llm={c.llm_policy.value}/{c.llm_scope.value}  "
            f"failure={c.failure_semantics.value}  "
            f"request_state={c.request_state.value}"
        )
        print(
            f"  io={sorted(r.value for r in c.io_resources)}\n"
            f"  execute 可达方法 {len(scan.reachable)} 个；类内写入 "
            f"{sorted(scan.class_writes) or '[]'}；模型调用点 {len(scan.llm_call_lines)} 个"
        )

    errors = [f for f in findings if f.level == "error"]
    warnings = [f for f in findings if f.level == "warning"]
    infos = [f for f in findings if f.level == "info"]

    print("\n" + "-" * 78)
    for label, group in (("ERROR", errors), ("WARN", warnings), ("INFO", infos)):
        if not group:
            continue
        print(f"\n{label}:")
        for f in group:
            print(f"  [{f.code}] {f.agent_id}: {f.message}")

    print("\n" + "=" * 78)
    print(f"结论: {len(errors)} error / {len(warnings)} warning / {len(infos)} info")
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent 职责边界契约静态审计")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args()

    findings, scans = audit()
    if args.json:
        print(
            json.dumps(
                {
                    "findings": [
                        {"level": f.level, "code": f.code, "agent": f.agent_id, "message": f.message}
                        for f in findings
                    ],
                    "agents": {
                        aid: {
                            "class": s.class_name,
                            "reachable_writes": sorted(s.reachable_writes),
                            "llm_call_lines": s.llm_call_lines,
                            "request_state": CONTRACTS[aid].request_state.value,
                        }
                        for aid, s in scans.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_report(findings, scans)

    return 1 if any(f.level == "error" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
