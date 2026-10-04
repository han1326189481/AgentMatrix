"""自学习三层筛网 —— 自学习内容入库前的强制检验通道

佳文 2026-09-24 定的三层设计（逐字对应实现）:

    第 1 层｜质量门槛（纯规则，零成本）
        回答质量分 >= filter_min_quality_score（默认 0.80）
        **并且** 满足「触发过云端增强」或「进行过 web search」
        —— 两者是与关系。没过 L1 直接终止，不进入后续任何联网/云端动作。

    第 2 层｜名词拆解 + 权威源比对（调用云端 API）
        用云端 `deepseek-flash`（显示名 DeepSeek-V4.1-Flash）把回答里
        「本地模型不理解的名词 / 解释不好的
        地方 / 格式或模板痕迹」拆解成条目，然后**逐条**到权威源比对：
        拆出来的短语或名词解释必须能在权威站点找到出处才算过筛。
        （实测注意：搜索引擎存在语义漂移，因此命中域名权威还不够，
          必须通过 `authority_sources._term_matches` 的词条匹配校验。）

    第 3 层｜格式与二次校验（规则 + 强制再检索）
        1) 过滤格式不正确的、被截断的知识点（占位符残留、括号/引号不闭合、
           结尾截断、定义过短等）
        2) 每条新知识入库前**再执行一次独立 web search** 校验：
           必须有权威网站或权威媒体的出处才准入库。
           ★ 写死逻辑：不得依据模型自身知识库判断。

设计约束:
- 第 2/3 层要联网、要调云端，**绝不放在用户问答的实时路径上**，
  由 `learning_intake` 以后台任务方式执行（见 core/engines/learning_intake.py）。
- 失败方向永远是「拒绝」：网络不通、云端不可用、解析失败 → 不入库。
  静默放行是这套筛网唯一不能接受的错误。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.engines.authority_sources import (
    AuthorityRegistry,
    SourceTier,
    TermVerification,
    get_authority_registry,
)

logger = logging.getLogger(__name__)

# 送进云端拆解的答案最大长度（控制 token）
MAX_ANSWER_CHARS = 4000

# 词条合法性（进入联网校验前的廉价预筛）
_TERM_MIN_LEN = 2
_TERM_MAX_LEN = 40
_TERM_HAS_MEANING = re.compile(r"[\u4e00-\u9fffA-Za-z]")

# 第 3 层：截断/残缺特征
_TRUNCATED_TAILS = ("…", "...", "、", "，", ",", "：", ":", "(", "（", "【", "《", "-", "—", "/")
# 第 3 层：占位符/模板残留
_PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTODO\b", re.I), re.compile(r"\bFIXME\b", re.I),
    re.compile(r"\bXXX+\b", re.I), re.compile(r"X{4,}"),
    re.compile(r"\?\?"), re.compile(r"\{\{|\}\}"),
    re.compile(r"<[a-z_]{3,}>"), re.compile(r"\$\{[^}]*\}"),
    re.compile(r"待补充|待完善|待填写|待确认|此处省略|略\.\.\.|（略）|占位"),
    re.compile(r"\[(?:插入|填写|补充)[^\]]*\]"),
)
# 第 3 层：成对符号
_BRACKET_PAIRS = (("(", ")"), ("（", "）"), ("[", "]"), ("【", "】"),
                  ("{", "}"), ("《", "》"), ("“", "”"), ("‘", "’"))

# 云端拆解的可用类型
ITEM_KINDS = ("unknown_term", "definition", "format_issue")


# ============================================================
# 数据结构
# ============================================================

@dataclass
class FilterItem:
    """一个待核验条目（名词/短语/疑点）"""

    term: str
    claim: str = ""          # 回答中关于该词的说法
    kind: str = "unknown_term"
    reason: str = ""         # 为何需要核验
    origin: str = "rule"     # rule（规则提取）| cloud_decompose（云端拆解）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term, "claim": self.claim, "kind": self.kind,
            "reason": self.reason, "origin": self.origin,
        }


@dataclass
class VerifiedKnowledge:
    """通过第 2 层、有权威出处的候选知识（尚未过第 3 层）"""

    term: str
    definition: str          # 权威定义（来自权威源，不是模型自述）
    claim: str = ""          # 回答中的原始说法
    kind: str = "unknown_term"
    tier: int = 9
    sources: List[Dict[str, Any]] = field(default_factory=list)
    domain: str = "root"
    # 非序列化：携带第 2 层的校验对象，供第 3 层复用证据做二次检索
    verification: Optional[Any] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term, "definition": self.definition, "claim": self.claim,
            "kind": self.kind, "tier": self.tier,
            "tier_label": SourceTier(self.tier).label
            if self.tier in tuple(int(t) for t in SourceTier) else "未识别",
            "sources": self.sources, "domain": self.domain,
        }

    def to_knowledge_patch(self, domain: Optional[str] = None):
        """转成 LearningEngine 的 KnowledgePatch（source=verified，注明权威出处）"""
        from core.skill_engine.models import KnowledgePatch

        src_note = ""
        if self.sources:
            src_note = f" [出处: {self.sources[0].get('url', '')}]"
        return KnowledgePatch(
            concept_name=self.term,
            definition=f"{self.definition}{src_note}",
            domain=domain or self.domain or "root",
            related_concepts=[],
            confidence=0.9 if self.tier == 1 else 0.8,
            source="verified",
        )


@dataclass
class LayerReport:
    """单层判定结果（进审计账本）"""

    layer: int
    name: str
    passed: bool
    reasons: List[str] = field(default_factory=list)
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer, "name": self.name, "passed": self.passed,
            "reasons": self.reasons, "detail": self.detail,
        }


@dataclass
class FilterReport:
    """三层筛网总报告"""

    passed: bool = False
    stopped_at: Optional[str] = None      # layer1 / layer2 / layer3 / None(通过)
    layer1: Optional[LayerReport] = None
    layer2: Optional[LayerReport] = None
    layer3: Optional[LayerReport] = None
    accepted: List[VerifiedKnowledge] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "stopped_at": self.stopped_at,
            "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected),
            "layers": [
                r.to_dict() for r in (self.layer1, self.layer2, self.layer3) if r
            ],
            "accepted": [a.to_dict() for a in self.accepted],
            "rejected": self.rejected,
        }


# ============================================================
# 工具函数
# ============================================================

def _norm_term(term: str) -> str:
    return re.sub(r"\s+", "", (term or "").strip().lower())


def _is_meaningful_term(term: str) -> bool:
    """廉价预筛：值得花联网成本去核验的词条"""
    t = (term or "").strip()
    if not (_TERM_MIN_LEN <= len(t) <= _TERM_MAX_LEN):
        return False
    if not _TERM_HAS_MEANING.search(t):
        return False
    if t.isdigit():
        return False
    if not re.search(r"[\u4e00-\u9fff]|[A-Za-z]{2,}", t):
        return False
    return True


def _parse_json_block(text: str) -> Optional[dict]:
    """从可能带 ```json 围栏的模型输出里抠出 JSON 对象"""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(t[start:end + 1])
        except Exception:
            return None
    return None


def _matched_source_dicts(sources: Any, limit: int = 5) -> List[Dict[str, Any]]:
    """取出「词条匹配」的来源并序列化为 dict

    容错：`TermVerification.sources` 正常是 `SourceHit` 对象，但也可能是
    已序列化的 dict（测试桩、或跨进程反序列化）。原实现硬取 `.term_matched`
    属性，一旦拿到 dict 就抛 AttributeError —— 而这个异常会被上层归类成
    「第 2 层异常 ⟹ 不通过」，属于**因为类型假设而误杀正常知识**，
    因此这里两种形态都接受。
    """
    out: List[Dict[str, Any]] = []
    for s in (sources or []):
        if isinstance(s, dict):
            if s.get("term_matched", True):
                out.append(s)
        else:
            if getattr(s, "term_matched", False):
                out.append(s.to_dict())
    return out[:limit]


def _format_problems(text: str) -> List[str]:
    """第 3 层格式规则检查（纯规则，零成本）"""
    problems: List[str] = []
    t = (text or "").strip()
    if not t:
        return ["内容为空"]
    if len(t) < 10:
        problems.append(f"内容过短({len(t)}字)")

    lowered = t.lower()
    for pat in _PLACEHOLDER_PATTERNS:
        if pat.search(t):
            problems.append(f"占位符/模板残留: {pat.pattern}")
            break

    if t.endswith(_TRUNCATED_TAILS):
        problems.append("内容被截断（结尾为分隔符/省略号）")

    for op, cl in _BRACKET_PAIRS:
        if t.count(op) != t.count(cl):
            problems.append(f"成对符号不闭合: {op}{cl}")
            break

    # 纯标点/纯空白
    if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", t):
        problems.append("内容无有效字符")
    # 控制字符 / 乱码特征
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", t):
        problems.append("含控制字符")
    return problems


# ============================================================
# 三层筛网
# ============================================================

class FilterNet:
    """自学习三层筛网

    用法::

        net = FilterNet()
        report = await net.run(
            user_task=..., answer=...,
            review_score=0.86, cloud_enhanced=True, web_search_performed=False,
            rule_candidates=["Transformer", "自注意力机制"],
        )
        if report.passed:
            for item in report.accepted:      # 有权威出处的知识
                ...

    并发安全：无内部可变状态（报告按次返回），可并发调用。
    """

    def __init__(
        self,
        authority: Optional[AuthorityRegistry] = None,
        llm_client: Optional[Any] = None,
        *,
        enabled: bool = True,
        min_quality_score: float = 0.80,
        max_terms: int = 6,
        recheck: bool = True,
        decompose_with_cloud: bool = True,
    ):
        self._authority = authority
        self._llm = llm_client
        self.enabled = enabled
        self.min_quality_score = min_quality_score
        self.max_terms = max_terms
        self.recheck_enabled = recheck
        self.decompose_with_cloud = decompose_with_cloud

    # ---------- 依赖懒加载 ----------

    @property
    def authority(self) -> AuthorityRegistry:
        if self._authority is None:
            self._authority = get_authority_registry()
        return self._authority

    def _get_llm(self):
        if self._llm is None:
            from core.llm.client import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    # ==========================================================
    # 第 1 层｜质量门槛（纯规则）
    # ==========================================================

    def layer1_gate(
        self,
        review_score: float,
        cloud_enhanced: bool,
        web_search_performed: bool,
    ) -> LayerReport:
        """第 1 层：质量分达标 **且**（云端增强 或 web search）

        佳文原话：「回答质量要达到 0.85 或者是 0.8 以上，并且还要满足
        触发了云端增强或者是进行了 web search 才能进入筛网」
        """
        reasons: List[str] = []
        score = float(review_score or 0.0)

        if score < self.min_quality_score:
            reasons.append(
                f"质量分不足: {score:.2f} < {self.min_quality_score:.2f}"
            )
        if not (cloud_enhanced or web_search_performed):
            reasons.append("既未触发云端增强，也未进行 web search")

        return LayerReport(
            layer=1,
            name="质量门槛",
            passed=not reasons,
            reasons=reasons,
            detail={
                "review_score": round(score, 3),
                "min_quality_score": self.min_quality_score,
                "cloud_enhanced": bool(cloud_enhanced),
                "web_search_performed": bool(web_search_performed),
            },
        )

    # ==========================================================
    # 第 2 层｜云端拆解 + 权威源比对
    # ==========================================================

    async def layer2_decompose(
        self, user_task: str, answer: str
    ) -> List[FilterItem]:
        """用云端模型把回答拆成「需要核验的条目」

        只挑三类：本地可能不理解的专有名词、可外部核实的定义性论断、
        格式/模板可疑片段。
        """
        if not self.decompose_with_cloud:
            return []

        prompt = (
            "你是知识入库前的「名词拆解与疑点提取器」。给定一次问答，"
            "找出需要在入库前核验的条目。\n\n"
            "只挑这三类：\n"
            "1. unknown_term —— 专有名词/术语，本地小模型很可能不理解或解释含糊\n"
            "2. definition —— 回答中给出的、可被外部事实核验的定义性论断\n"
            "3. format_issue —— 格式或模板痕迹可疑的片段\n\n"
            "严格输出 JSON，不要任何解释文字、不要 markdown 围栏：\n"
            '{"items":[{"term":"名词或短语","claim":"回答中关于它的一句话说法",'
            '"kind":"unknown_term|definition|format_issue","reason":"为何需要核验"}]}\n\n'
            f"最多 {self.max_terms} 条；没有则输出 {{\"items\":[]}}\n\n"
            f"【用户任务】\n{(user_task or '')[:800]}\n\n"
            f"【回答内容】\n{(answer or '')[:MAX_ANSWER_CHARS]}"
        )

        try:
            raw = await self._get_llm().generate_cloud(prompt=prompt)
        except Exception as e:
            logger.warning("[FilterNet] 第 2 层云端拆解失败（降级为仅用规则候选）: %s", e)
            return []

        data = _parse_json_block(raw)
        if not isinstance(data, dict):
            logger.warning("[FilterNet] 第 2 层拆解结果无法解析为 JSON")
            return []

        items: List[FilterItem] = []
        for it in (data.get("items") or [])[: self.max_terms]:
            if not isinstance(it, dict):
                continue
            term = str(it.get("term", "")).strip()
            if not _is_meaningful_term(term):
                continue
            kind = str(it.get("kind", "unknown_term")).strip()
            if kind not in ITEM_KINDS:
                kind = "unknown_term"
            items.append(FilterItem(
                term=term,
                claim=str(it.get("claim", ""))[:300],
                kind=kind,
                reason=str(it.get("reason", ""))[:200],
                origin="cloud_decompose",
            ))
        logger.info("[FilterNet] 第 2 层云端拆解得到 %d 条待核验条目", len(items))
        return items

    def _merge_items(
        self, cloud_items: List[FilterItem], rule_candidates: List[str]
    ) -> List[FilterItem]:
        """合并云端拆解条目与规则候选，去重并按优先级截断"""
        merged: List[FilterItem] = []
        seen = set()

        kind_rank = {"unknown_term": 0, "definition": 1, "format_issue": 2}
        cloud_sorted = sorted(cloud_items, key=lambda i: kind_rank.get(i.kind, 9))

        for it in cloud_sorted:
            key = _norm_term(it.term)
            if key and key not in seen:
                seen.add(key)
                merged.append(it)

        for c in rule_candidates or []:
            term = (c or "").strip()
            key = _norm_term(term)
            if not key or key in seen or not _is_meaningful_term(term):
                continue
            seen.add(key)
            merged.append(FilterItem(term=term, kind="unknown_term", origin="rule"))

        # 云端拆解条目优先（它针对的是模型答不好的地方），上限 max_terms*2 控制成本
        return merged[: max(self.max_terms * 2, self.max_terms)]

    async def layer2_verify(
        self, items: List[FilterItem]
    ) -> Tuple[List[VerifiedKnowledge], List[Dict[str, Any]], LayerReport]:
        """第 2 层：逐条到权威源比对（不做二次校验，二次校验属第 3 层）"""
        if not items:
            return [], [], LayerReport(
                layer=2, name="名词拆解+权威比对", passed=False,
                reasons=["没有可核验的候选词条"], detail={"candidates": 0},
            )

        terms = [i.term for i in items]
        verdicts: List[TermVerification] = await self.authority.verify_many(terms)
        by_term = {_norm_term(v.term): v for v in verdicts}

        accepted: List[VerifiedKnowledge] = []
        rejected: List[Dict[str, Any]] = []

        for item in items:
            v = by_term.get(_norm_term(item.term))
            if v and v.verified and v.authoritative_definition:
                accepted.append(VerifiedKnowledge(
                    term=item.term,
                    definition=v.authoritative_definition,
                    claim=item.claim,
                    kind=item.kind,
                    tier=int(v.best_tier),
                    sources=_matched_source_dicts(v.sources),
                    verification=v,
                ))
            else:
                rejected.append({
                    "term": item.term,
                    "stage": "layer2",
                    "kind": item.kind,
                    "origin": item.origin,
                    "reasons": (v.reasons if v else ["未获得校验结果"]),
                })

        report = LayerReport(
            layer=2,
            name="名词拆解+权威比对",
            passed=bool(accepted),
            reasons=[] if accepted else ["所有候选词条均未通过权威源比对"],
            detail={
                "candidates": len(items),
                "verified": len(accepted),
                "rejected": len(rejected),
            },
        )
        return accepted, rejected, report

    # ==========================================================
    # 第 3 层｜格式校验 + 二次检索
    # ==========================================================

    async def layer3_finalize(
        self, candidates: List[VerifiedKnowledge], *, recheck: Optional[bool] = None
    ) -> Tuple[List[VerifiedKnowledge], List[Dict[str, Any]], LayerReport]:
        """第 3 层：格式/截断过滤 + 入库前二次 web search 硬校验"""
        do_recheck = self.recheck_enabled if recheck is None else recheck

        if not candidates:
            return [], [], LayerReport(
                layer=3, name="格式+二次校验", passed=False,
                reasons=["第 2 层无通过条目"], detail={"candidates": 0},
            )

        accepted: List[VerifiedKnowledge] = []
        rejected: List[Dict[str, Any]] = []

        # 3.1 格式规则（先做，省掉不必要的联网）
        survivors: List[VerifiedKnowledge] = []
        for c in candidates:
            problems = _format_problems(c.definition)
            problems += [f"词条名不合法({c.term!r})"] if not _is_meaningful_term(c.term) else []
            if problems:
                rejected.append({
                    "term": c.term, "stage": "layer3-format",
                    "kind": c.kind, "reasons": problems,
                })
            else:
                survivors.append(c)

        # 3.2 二次检索（写死：不得依据本地知识库判断）
        if survivors and do_recheck:
            carried = [c.verification for c in survivors if c.verification is not None]
            if len(carried) == len(survivors):
                # 复用第 2 层的证据对象，只补一轮独立检索（避免重复查维基触发限流）
                await self.authority.recheck_many(carried)
            else:
                # 兜底：没有携带第 2 层证据时，重新完整校验一次
                logger.info("[FilterNet] 第 3 层缺少第 2 层证据，回退为完整重校验")
                carried = await self.authority.verify_many([s.term for s in survivors])

            for c, v in zip(survivors, carried):
                if v is not None and v.verified:
                    # 二次校验通过：用最新证据刷新出处
                    fresh = _matched_source_dicts(v.sources)
                    c.sources = fresh or c.sources
                    if v.authoritative_definition:
                        c.definition = v.authoritative_definition
                    c.tier = int(v.best_tier)
                    accepted.append(c)
                else:
                    rejected.append({
                        "term": c.term, "stage": "layer3-recheck",
                        "kind": c.kind,
                        "reasons": (v.reasons if v else ["二次检索无结果"]),
                    })
        else:
            accepted.extend(survivors)

        report = LayerReport(
            layer=3,
            name="格式+二次校验",
            passed=bool(accepted),
            reasons=[] if accepted else ["全部候选在格式或二次校验中被拒"],
            detail={
                "candidates": len(candidates),
                "format_rejected": sum(1 for r in rejected if r["stage"] == "layer3-format"),
                "recheck": do_recheck,
                "recheck_rejected": sum(1 for r in rejected if r["stage"] == "layer3-recheck"),
                "accepted": len(accepted),
            },
        )
        return accepted, rejected, report

    # ==========================================================
    # 总入口
    # ==========================================================

    async def run(
        self,
        user_task: str,
        answer: str,
        *,
        review_score: float,
        cloud_enhanced: bool = False,
        web_search_performed: bool = False,
        rule_candidates: Optional[List[str]] = None,
        domain: str = "root",
    ) -> FilterReport:
        """跑完整三层。任一层不通过即终止，永不静默放行。"""
        report = FilterReport()

        if not self.enabled:
            report.stopped_at = "disabled"
            report.layer1 = LayerReport(
                layer=1, name="质量门槛", passed=False,
                reasons=["三层筛网已关闭 (filter_net_enabled=False)"],
            )
            return report

        # ---- 第 1 层 ----
        l1 = self.layer1_gate(review_score, cloud_enhanced, web_search_performed)
        report.layer1 = l1
        if not l1.passed:
            report.stopped_at = "layer1"
            logger.info("[FilterNet] 第 1 层未通过，终止: %s", l1.reasons)
            return report

        # ---- 第 2 层 ----
        try:
            cloud_items = await self.layer2_decompose(user_task, answer)
            items = self._merge_items(cloud_items, rule_candidates or [])
            accepted2, rejected2, l2 = await self.layer2_verify(items)
        except Exception as e:
            logger.warning("[FilterNet] 第 2 层异常，判定为不通过: %s", e)
            rejected2 = [{"term": "-", "stage": "layer2", "reasons": [f"第 2 层异常: {e}"]}]
            accepted2 = []
            l2 = LayerReport(
                layer=2, name="名词拆解+权威比对", passed=False,
                reasons=[f"第 2 层异常: {e}"],
            )
        report.layer2 = l2
        report.rejected.extend(rejected2)
        if not l2.passed:
            report.stopped_at = "layer2"
            logger.info("[FilterNet] 第 2 层未通过，终止: %s", l2.reasons)
            return report

        # ---- 第 3 层 ----
        try:
            accepted3, rejected3, l3 = await self.layer3_finalize(accepted2)
        except Exception as e:
            logger.warning("[FilterNet] 第 3 层异常，判定为不通过: %s", e)
            accepted3 = []
            rejected3 = [{"term": "-", "stage": "layer3", "reasons": [f"第 3 层异常: {e}"]}]
            l3 = LayerReport(
                layer=3, name="格式+二次校验", passed=False,
                reasons=[f"第 3 层异常: {e}"],
            )
        report.layer3 = l3
        report.rejected.extend(rejected3)

        for item in accepted3:
            item.domain = domain or "root"

        report.accepted = accepted3
        report.passed = bool(accepted3)
        report.stopped_at = None if report.passed else "layer3"
        logger.info(
            "[FilterNet] 三层完成: passed=%s accepted=%d rejected=%d",
            report.passed, len(report.accepted), len(report.rejected),
        )
        return report


# ============================================================
# 单例
# ============================================================

_filter_net: Optional[FilterNet] = None


def get_filter_net() -> FilterNet:
    global _filter_net
    if _filter_net is None:
        try:
            from app.config import settings
            _filter_net = FilterNet(
                enabled=bool(getattr(settings, "filter_net_enabled", True)),
                min_quality_score=float(getattr(settings, "filter_min_quality_score", 0.80)),
                max_terms=int(getattr(settings, "filter_max_terms", 6)),
                recheck=bool(getattr(settings, "filter_recheck_enabled", True)),
            )
        except Exception:
            _filter_net = FilterNet()
    return _filter_net
