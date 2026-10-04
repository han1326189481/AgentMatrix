"""自学习摄入管线 —— 把「一次高质量回答」变成「可入库的知识 / 可审批的补丁」

链路（2026-09-24 与佳文确定的形态）:

    工作流产出（答案 + 质量分 + 是否云端增强 / 是否 web search）
        │
        ├─→ 三层筛网（core.engines.filter_net.FilterNet）
        │       没过 → 记拒绝账本，什么都不写
        │       过了 → 得到「有权威出处」的知识条目
        │
        ├─→ PatchValidator（既有守门人：重复/冲突/长度/来源）
        │
        └─→ 落盘
                ├─ learning_auto_apply=False（默认）→ 全部进待审队列，等人工审批
                └─ learning_auto_apply=True         → 直接合并进 Skill Graph

两条铁律:
1. **筛网是唯一入口。** 任何自动学习产出都必须过筛网，没过的一律不落盘、
   也不进待审队列（避免把垃圾灌进人工审核的队列里，浪费人）。
2. **默认不自动改自己。** 默认全部落 `pending`，由审批 API / 前端人工确认后
   才真正写入知识图谱或技能书。

落盘位置（遵循 shared.platform 规范）:
- 开发:  `backend/storage/pending_learning/`
- 打包:  `%APPDATA%/AgentMatrix/storage/pending_learning/`
- 审计账本: 同目录 `_audit.jsonl`（每次筛网运行一行，供答辩取证）
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PENDING_DIRNAME = "pending_learning"
AUDIT_FILENAME = "_audit.jsonl"

# 待审条目状态
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
VALID_STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED)

# 条目类型
KIND_KNOWLEDGE = "knowledge"
KIND_SKILL = "skill"
VALID_KINDS = (KIND_KNOWLEDGE, KIND_SKILL)

_ID_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _pending_root() -> str:
    """待审队列目录（懒加载，避免导入期就依赖 app 配置）"""
    try:
        from shared.platform import get_storage_dir
        return os.path.join(get_storage_dir(), PENDING_DIRNAME)
    except Exception:
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "storage", PENDING_DIRNAME,
        )


def _slug(text: str, limit: int = 40) -> str:
    """把任意文本消毒成安全 slug（防目录穿越）"""
    s = _ID_SAFE.sub("_", str(text or "")).strip("._")
    return (s or "item")[:limit]


@dataclass
class IntakeReport:
    """一次摄入的结果"""

    passed: bool = False
    accepted_count: int = 0
    applied_count: int = 0
    pending_ids: List[str] = field(default_factory=list)
    rejected_count: int = 0
    stopped_at: Optional[str] = None
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "accepted_count": self.accepted_count,
            "applied_count": self.applied_count,
            "pending_ids": self.pending_ids,
            "rejected_count": self.rejected_count,
            "stopped_at": self.stopped_at,
            "error": self.error,
        }


# ============================================================
# 统一待审队列
# ============================================================

class PendingStore:
    """待审学习队列（文件后端，一条一 JSON）

    并发安全：每次写入用独立文件名（时间戳 + 随机后缀），
    不存在两个线程写同一文件的竞争；读取用 glob 快照。
    """

    def __init__(self, root: Optional[str] = None):
        self._root = root or _pending_root()

    @property
    def root(self) -> str:
        return self._root

    def _ensure(self) -> None:
        os.makedirs(self._root, exist_ok=True)

    def _path(self, item_id: str) -> str:
        """由 id 推出文件路径，并强制校验仍在队列目录内（防路径穿越）"""
        safe = _slug(item_id, limit=120)
        filepath = os.path.join(self._root, f"{safe}.json")
        if os.path.dirname(os.path.realpath(filepath)) != os.path.realpath(self._root):
            raise ValueError(f"非法条目 id: {item_id!r}")
        return filepath

    # ---------- 写 ----------

    def add(
        self,
        kind: str,
        payload: Dict[str, Any],
        *,
        domain: str = "root",
        evidence: Optional[List[Dict[str, Any]]] = None,
        layers: Optional[List[Dict[str, Any]]] = None,
        trigger: Optional[Dict[str, Any]] = None,
        source: str = "auto_learn",
    ) -> str:
        """新增一条待审条目，返回条目 id

        Args:
            kind: KIND_KNOWLEDGE | KIND_SKILL
            payload: 补丁内容（KnowledgePatch / SkillPatch 的 dict）
            domain: 所属领域
            evidence: 权威出处（筛网产出）
            layers: 三层筛网的各层判定（审计留痕）
            trigger: 触发上下文（质量分 / 云端 / web search）
            source: 产出方
        """
        if kind not in VALID_KINDS:
            raise ValueError(f"未知条目类型: {kind!r}")

        self._ensure()
        now = datetime.now()
        item_id = f"{kind[:2]}_{now.strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}"

        record = {
            "id": item_id,
            "kind": kind,
            "status": STATUS_PENDING,
            "created_at": now.isoformat(timespec="seconds"),
            "domain": domain or "root",
            "source": source,
            "trigger": trigger or {},
            "filter": {"layers": layers or []},
            "evidence": evidence or [],
            "payload": payload or {},
            "review": {},
        }

        filepath = self._path(item_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        logger.info("[PendingStore] 新增待审条目 %s (kind=%s, domain=%s)", item_id, kind, domain)
        return item_id

    def set_status(self, item_id: str, status: str, note: str = "") -> Optional[Dict[str, Any]]:
        """更新条目状态（审批 / 拒绝）"""
        if status not in VALID_STATUSES:
            raise ValueError(f"未知状态: {status!r}")
        record = self.get(item_id)
        if record is None:
            return None
        record["status"] = status
        record["review"] = {
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
            "note": note or "",
        }
        with open(self._path(item_id), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        logger.info("[PendingStore] 条目 %s 状态 -> %s", item_id, status)
        return record

    # ---------- 读 ----------

    def get(self, item_id: str) -> Optional[Dict[str, Any]]:
        try:
            filepath = self._path(item_id)
        except ValueError:
            return None
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("[PendingStore] 读取条目失败 %s: %s", item_id, e)
            return None

    def list_items(
        self,
        status: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """列出条目（按创建时间倒序）"""
        if not os.path.isdir(self._root):
            return []

        items: List[Dict[str, Any]] = []
        for name in os.listdir(self._root):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._root, name), "r", encoding="utf-8") as f:
                    rec = json.load(f)
            except Exception:
                continue
            if status and rec.get("status") != status:
                continue
            if kind and rec.get("kind") != kind:
                continue
            items.append(rec)

        items.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return items[: max(1, limit)]

    def stats(self) -> Dict[str, int]:
        """队列统计"""
        out = {"pending": 0, "approved": 0, "rejected": 0, "total": 0,
               "knowledge_pending": 0, "skill_pending": 0}
        for rec in self.list_items(limit=100000):
            st = rec.get("status", STATUS_PENDING)
            out["total"] += 1
            if st in out:
                out[st] += 1
            if st == STATUS_PENDING:
                key = f"{rec.get('kind')}_pending"
                if key in out:
                    out[key] += 1
        return out

    # ---------- 审计账本 ----------

    def append_audit(self, record: Dict[str, Any]) -> None:
        """追加一行审计记录（每次筛网运行都写，供取证）"""
        try:
            self._ensure()
            line = json.dumps(
                {"ts": datetime.now().isoformat(timespec="seconds"), **(record or {})},
                ensure_ascii=False,
            )
            with open(os.path.join(self._root, AUDIT_FILENAME), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:  # pragma: no cover
            logger.warning("[PendingStore] 写审计账本失败: %s", e)

    def read_audit(self, limit: int = 100) -> List[Dict[str, Any]]:
        path = os.path.join(self._root, AUDIT_FILENAME)
        if not os.path.exists(path):
            return []
        out: List[Dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except Exception:
                            continue
        except Exception:
            return []
        return out[-max(1, limit):]


# ============================================================
# 摄入管线
# ============================================================

class LearningIntake:
    """把工作流产出送进「筛网 → 守门人 → 待审/入库」的管线

    使用方式（由 workflow service 以后台任务调用，不进用户响应路径）::

        intake = get_learning_intake()
        report = await intake.process(
            user_task=..., answer=..., skill_path=["root", "tech"],
            review_score=0.88, cloud_enhanced=True, web_search_performed=False,
        )
    """

    def __init__(
        self,
        learning_engine: Optional[Any] = None,
        filter_net: Optional[Any] = None,
        store: Optional[PendingStore] = None,
        *,
        auto_apply: Optional[bool] = None,
        max_rule_candidates: int = 12,
    ):
        self._engine = learning_engine
        self._net = filter_net
        self._store = store
        self._auto_apply = auto_apply
        self.max_rule_candidates = max_rule_candidates

    # ---------- 依赖懒加载 ----------

    @property
    def net(self):
        if self._net is None:
            from core.engines.filter_net import get_filter_net
            self._net = get_filter_net()
        return self._net

    @property
    def store(self) -> PendingStore:
        if self._store is None:
            self._store = PendingStore()
        return self._store

    @property
    def engine(self):
        if self._engine is None:
            from core.graphs import get_skill_graph
            from core.engines.learning_engine import LearningEngine
            self._engine = LearningEngine(skill_graph=get_skill_graph())
        return self._engine

    @property
    def auto_apply(self) -> bool:
        if self._auto_apply is None:
            try:
                from app.config import settings
                self._auto_apply = bool(getattr(settings, "learning_auto_apply", False))
            except Exception:
                self._auto_apply = False
        return self._auto_apply

    # ---------- 主流程 ----------

    async def process(
        self,
        *,
        user_task: str,
        answer: str,
        skill_path: Optional[List[str]] = None,
        review_score: float = 0.0,
        cloud_enhanced: bool = False,
        web_search_performed: bool = False,
        rule_candidates: Optional[List[str]] = None,
    ) -> IntakeReport:
        """一次自学习摄入

        任何异常都不向上抛（后台任务），但**失败方向永远是「不落盘」**。
        """
        skill_path = skill_path or ["root"]
        domain = skill_path[-1] if skill_path else "root"
        report = IntakeReport()

        # 规则候选：由既有概念提取器产出（零成本），交给筛网做联网核验
        if rule_candidates is None:
            try:
                concepts = self.engine._extract_concepts(answer or "")  # noqa: SLF001
                rule_candidates = sorted(concepts)[: self.max_rule_candidates]
            except Exception as e:
                logger.debug("[Intake] 概念提取失败（忽略）: %s", e)
                rule_candidates = []

        try:
            filter_report = await self.net.run(
                user_task=user_task,
                answer=answer,
                review_score=review_score,
                cloud_enhanced=cloud_enhanced,
                web_search_performed=web_search_performed,
                rule_candidates=rule_candidates,
                domain=domain,
            )
        except Exception as e:
            logger.warning("[Intake] 筛网执行异常，本次不落盘: %s", e)
            report.error = f"筛网异常: {e}"
            report.stopped_at = "exception"
            self.store.append_audit({
                "event": "intake_error", "domain": domain, "error": str(e),
                "user_task": (user_task or "")[:120],
            })
            return report

        report.passed = filter_report.passed
        report.stopped_at = filter_report.stopped_at
        report.accepted_count = len(filter_report.accepted)
        report.rejected_count = len(filter_report.rejected)

        trigger = {
            "review_score": round(float(review_score or 0.0), 3),
            "cloud_enhanced": bool(cloud_enhanced),
            "web_search_performed": bool(web_search_performed),
            "user_task": (user_task or "")[:200],
        }

        # 筛网没过：只记账，不写任何知识/补丁
        if not filter_report.passed:
            self.store.append_audit({
                "event": "filter_reject",
                "domain": domain,
                "stopped_at": filter_report.stopped_at,
                "trigger": trigger,
                "rejected": filter_report.rejected[:20],
            })
            logger.info(
                "[Intake] 筛网未通过 (stopped_at=%s)，本次不落盘", filter_report.stopped_at
            )
            return report

        # 过了筛网：逐条过 PatchValidator，再决定落 pending 还是直接入库
        layers = [
            lr.to_dict() for lr in
            (filter_report.layer1, filter_report.layer2, filter_report.layer3) if lr
        ]
        validator = self._get_validator()

        for item in filter_report.accepted:
            patch = item.to_knowledge_patch(domain)
            if validator is not None:
                verdict = validator.validate_knowledge(patch)
                if not verdict.passed:
                    self.store.append_audit({
                        "event": "validator_reject",
                        "domain": domain,
                        "term": item.term,
                        "errors": verdict.errors,
                    })
                    report.rejected_count += 1
                    continue

            if self.auto_apply:
                ok = self._apply_knowledge([patch])
                report.applied_count += 1 if ok else 0
                self.store.append_audit({
                    "event": "knowledge_applied",
                    "domain": domain,
                    "term": item.term,
                    "tier": item.tier,
                    "sources": [s.get("url", "") for s in item.sources[:3]],
                    "trigger": trigger,
                })
            else:
                item_id = self.store.add(
                    kind=KIND_KNOWLEDGE,
                    payload=patch.to_dict(),
                    domain=domain,
                    evidence=item.sources,
                    layers=layers,
                    trigger=trigger,
                )
                report.pending_ids.append(item_id)

        self.store.append_audit({
            "event": "filter_pass",
            "domain": domain,
            "trigger": trigger,
            "accepted": [a.term for a in filter_report.accepted],
            "pending": len(report.pending_ids),
            "applied": report.applied_count,
            "layers": [{"layer": l["layer"], "passed": l["passed"]} for l in layers],
        })
        logger.info(
            "[Intake] 筛网通过: accepted=%d pending=%d applied=%d",
            report.accepted_count, len(report.pending_ids), report.applied_count,
        )
        return report

    # ---------- 内部工具 ----------

    def _get_validator(self):
        try:
            return self.engine.validator
        except Exception:
            return None

    def _apply_knowledge(self, patches: List[Any]) -> bool:
        """把已通过筛网与守门人的知识合并进 Skill Graph 并持久化"""
        try:
            self.engine.apply_patches({"knowledge_patches": patches})
            return True
        except Exception as e:
            logger.warning("[Intake] 知识入库失败: %s", e)
            return False

    # ---------- 审批落地（供 API 调用） ----------

    def approve(self, item_id: str, note: str = "") -> Dict[str, Any]:
        """审批通过：把待审条目真正写进知识图谱 / 技能书"""
        record = self.store.get(item_id)
        if record is None:
            return {"ok": False, "error": f"条目不存在: {item_id}"}
        if record.get("status") != STATUS_PENDING:
            return {"ok": False, "error": f"条目状态不是 pending: {record.get('status')}"}

        kind = record.get("kind")
        payload = record.get("payload") or {}

        if kind == KIND_KNOWLEDGE:
            from core.skill_engine.models import KnowledgePatch
            patch = KnowledgePatch(
                concept_name=payload.get("concept_name", ""),
                definition=payload.get("definition", ""),
                domain=payload.get("domain", record.get("domain", "root")),
                related_concepts=payload.get("related_concepts", []) or [],
                confidence=float(payload.get("confidence", 0.8)),
                source=payload.get("source", "verified"),
            )
            ok = self._apply_knowledge([patch])
        elif kind == KIND_SKILL:
            ok = self._apply_skill_payload(record)
        else:
            return {"ok": False, "error": f"未知条目类型: {kind}"}

        if ok:
            self.store.set_status(item_id, STATUS_APPROVED, note)
            self.store.append_audit({
                "event": "approved", "id": item_id, "kind": kind,
                "domain": record.get("domain"),
            })
            return {"ok": True, "id": item_id, "kind": kind}
        return {"ok": False, "error": "写入失败，请查看后端日志"}

    def reject(self, item_id: str, note: str = "") -> Dict[str, Any]:
        """审批拒绝：条目标记为 rejected，不写入任何地方"""
        record = self.store.get(item_id)
        if record is None:
            return {"ok": False, "error": f"条目不存在: {item_id}"}
        self.store.set_status(item_id, STATUS_REJECTED, note)
        self.store.append_audit({
            "event": "rejected", "id": item_id,
            "kind": record.get("kind"), "note": note,
        })
        return {"ok": True, "id": item_id}

    def _apply_skill_payload(self, record: Dict[str, Any]) -> bool:
        """把技能补丁合并进对应 Skill Book 并版本号 +1"""
        from core.skill_engine.models import SkillPatch
        payload = record.get("payload") or {}
        domain = payload.get("domain") or record.get("domain") or "root"

        patch = SkillPatch(
            domain=domain,
            added_keywords=payload.get("added_keywords", {}) or {},
            added_constraints=payload.get("added_constraints", []) or [],
            added_examples=payload.get("added_examples", []) or [],
            added_forbidden=payload.get("added_forbidden", []) or [],
            added_ontology=payload.get("added_ontology", {}) or {},
        )
        try:
            from core.skill_engine.skill_learner import get_skill_learner
            return bool(get_skill_learner().apply_patch(domain, patch, auto_approve=True))
        except Exception as e:
            logger.warning("[Intake] 技能补丁应用失败: %s", e)
            return False


# ============================================================
# 单例
# ============================================================

_intake: Optional[LearningIntake] = None


def get_learning_intake() -> LearningIntake:
    global _intake
    if _intake is None:
        _intake = LearningIntake()
    return _intake
