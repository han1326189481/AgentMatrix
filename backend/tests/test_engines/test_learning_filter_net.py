"""三层筛网 / 摄入管线 / 待审队列 单元测试

全部离线可跑（权威源与云端调用都换成桩），覆盖各层**拒绝路径**——
筛网最不能接受的错误是"静默放行"，所以拒绝路径比通过路径更值得断言。

对应模块:
- core/engines/authority_sources.py  （域名分级、词条匹配）
- core/engines/filter_net.py         （三层筛网）
- core/engines/learning_intake.py    （摄入管线 + 待审队列）
- core/skill_engine/skill_learner.py （技能补丁触发与入队）
"""

import asyncio
import json
import os

import pytest

from core.engines.authority_sources import (
    AuthorityRegistry,
    SourceHit,
    SourceTier,
    TermVerification,
    _term_matches,
    classify_domain,
)
from core.engines.filter_net import (
    FilterNet,
    FilterItem,
    VerifiedKnowledge,
    _format_problems,
    _is_meaningful_term,
    _parse_json_block,
)
from core.engines.learning_intake import (
    IntakeReport,
    LearningIntake,
    PendingStore,
    KIND_KNOWLEDGE,
    KIND_SKILL,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
)


# ============================================================
# 桩
# ============================================================

class _StubAuthority:
    """假的权威源校验器：按预设结果返回，不联网"""

    def __init__(self, verified_terms=None, recheck_ok=True, second_round_terms=None):
        self.verified_terms = set(verified_terms or [])
        self.recheck_ok = recheck_ok
        self.second_round_terms = set(second_round_terms or [])
        self.verify_calls = 0
        self.recheck_calls = 0

    async def verify_many(self, terms, *, max_concurrency: int = 1):
        self.verify_calls += 1
        out = []
        for t in terms:
            v = TermVerification(term=t)
            if t in self.verified_terms:
                v.verified = True
                v.best_tier = SourceTier.TIER1
                v.authoritative_definition = f"{t}：来自权威词条的完整定义，长度足够用于入库校验。"
                v.sources = [{"url": f"https://zh.wikipedia.org/wiki/{t}", "tier": 1,
                              "title": t, "term_matched": True, "origin": "wikipedia_api",
                              "snippet": "权威定义"}]
            else:
                v.reasons.append("未找到任何权威来源")
            out.append(v)
        return out

    async def recheck_many(self, verifications, *, max_concurrency: int = 1):
        self.recheck_calls += 1
        for v in verifications:
            if self.recheck_ok:
                v.verified = True
            else:
                v.verified = False
                v.reasons.append("二次检索未再命中权威出处")
        return verifications


class _StubLLM:
    """假的云端客户端：返回固定 JSON"""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def generate_cloud(self, prompt, system_prompt=None, model=None):
        self.calls += 1
        return json.dumps(self.payload, ensure_ascii=False)


class _Verdict:
    def __init__(self, passed, errors=None):
        self.passed = passed
        self.errors = errors or []


class _StubEngine:
    """假的 LearningEngine：记录 apply_patches 调用"""

    def __init__(self, validate=True):
        self.applied = []
        self.validate = validate

        class _V:
            def __init__(self, outer):
                self.outer = outer

            def validate_knowledge(self, patch):
                return _Verdict(self.outer.validate)

        self.validator = _V(self)

    def apply_patches(self, patches):
        self.applied.append(patches)
        return len(patches.get("knowledge_patches", []))


def _net(authority, llm_payload=None, **kw):
    return FilterNet(
        authority=authority,
        llm_client=_StubLLM(llm_payload or {"items": []}),
        **kw,
    )


# ============================================================
# 权威源分级（纯函数）
# ============================================================

class TestSourceTiering:
    def test_tier1_domains(self):
        assert classify_domain("https://baike.baidu.com/item/x") == SourceTier.TIER1
        assert classify_domain("https://zh.wikipedia.org/wiki/x") == SourceTier.TIER1
        assert classify_domain("https://arxiv.org/abs/1706.03762") == SourceTier.TIER1
        assert classify_domain("https://www.miit.gov.cn/x") == SourceTier.TIER1
        assert classify_domain("https://www.tsinghua.edu.cn/x") == SourceTier.TIER1

    def test_tier2_media(self):
        assert classify_domain("https://www.xinhuanet.com/tech") == SourceTier.TIER2
        assert classify_domain("https://www.reuters.com/tech") == SourceTier.TIER2

    def test_tier3_community(self):
        assert classify_domain("https://blog.csdn.net/a/b") == SourceTier.TIER3
        assert classify_domain("https://zhuanlan.zhihu.com/p/1") == SourceTier.TIER3
        assert classify_domain("https://github.com/x/y") == SourceTier.TIER3

    def test_unknown_domain(self):
        assert classify_domain("https://some-random-blog.xyz/p") == SourceTier.UNKNOWN
        assert classify_domain("") == SourceTier.UNKNOWN

    def test_org_cn_is_not_tier1(self):
        """回归：`.org.cn` 曾被整条划为一级，导致 deepin.org.cn 这类社区站冒充权威源"""
        assert classify_domain("https://www.deepin.org.cn/zh/deepin/") != SourceTier.TIER1


class TestTermMatching:
    def test_exact_title_match(self):
        assert _term_matches("注意力机制", "注意力机制", "")

    def test_semantic_drift_rejected(self):
        """回归：搜「注意力机制」会命中百度百科「注意（心理学术语）」，必须判不匹配"""
        assert not _term_matches("注意力机制", "注意（心理学术语）", "注意是心理活动对一定对象的指向和集中")

    def test_disambiguation_suffix_still_matches(self):
        assert _term_matches("Transformer模型", "Transformer（机器学习模型）", "")

    def test_substring_in_snippet(self):
        assert _term_matches("过拟合", "某页标题", "过拟合是指模型过度匹配训练集的现象")

    def test_unrelated_title_rejected(self):
        assert not _term_matches("深度学习", "深in 操作系统", "")


# ============================================================
# 第 1 层：质量门槛
# ============================================================

class TestLayer1Gate:
    def test_reject_low_score(self):
        r = _net(_StubAuthority()).layer1_gate(0.5, True, False)
        assert not r.passed
        assert any("质量分不足" in x for x in r.reasons)

    def test_reject_no_cloud_no_search(self):
        r = _net(_StubAuthority()).layer1_gate(0.95, False, False)
        assert not r.passed
        assert any("web search" in x for x in r.reasons)

    def test_pass_with_cloud(self):
        assert _net(_StubAuthority()).layer1_gate(0.86, True, False).passed

    def test_pass_with_web_search(self):
        assert _net(_StubAuthority()).layer1_gate(0.80, False, True).passed

    def test_boundary_score(self):
        """0.80 是闭区间下界（佳文口述「0.8 以上」）"""
        net = _net(_StubAuthority(), min_quality_score=0.80)
        assert net.layer1_gate(0.80, True, False).passed
        assert not net.layer1_gate(0.799, True, False).passed


# ============================================================
# 第 3 层：格式规则（纯函数）
# ============================================================

class TestFormatRules:
    def test_normal_text_ok(self):
        assert _format_problems("这是一个正常的定义内容，长度足够。") == []

    def test_too_short(self):
        assert any("过短" in p for p in _format_problems("短"))

    def test_placeholder_residue(self):
        probs = _format_problems("TODO: 待补充完整定义")
        assert any("占位符" in p for p in probs)

    def test_unbalanced_brackets(self):
        probs = _format_problems("Transformer 是一种架构（未闭合")
        assert any("不闭合" in p for p in probs)

    def test_truncated_tail(self):
        probs = _format_problems("这是一段被硬截断的定义内容…")
        assert any("截断" in p for p in probs)


class TestJsonParse:
    def test_plain_json(self):
        assert _parse_json_block('{"items":[]}') == {"items": []}

    def test_fenced_json(self):
        assert _parse_json_block('```json\n{"items":[]}\n```') == {"items": []}

    def test_json_with_prose(self):
        got = _parse_json_block('好的：{"items":[{"term":"x"}]} 完毕')
        assert got and got["items"][0]["term"] == "x"

    def test_garbage(self):
        assert _parse_json_block("完全不是 JSON") is None
        assert _parse_json_block("") is None


# ============================================================
# 三层筛网：拒绝路径
# ============================================================

class TestFilterNetRejectPaths:
    async def test_stop_at_layer1(self):
        net = _net(_StubAuthority(["深度学习"]))
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.3, cloud_enhanced=False, web_search_performed=False,
            rule_candidates=["深度学习"],
        )
        assert not rep.passed
        assert rep.stopped_at == "layer1"
        assert rep.layer2 is None and rep.layer3 is None   # 后续层完全没跑

    async def test_stop_at_layer2_no_authoritative_source(self):
        net = _net(_StubAuthority(verified_terms=[]))
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True,
            rule_candidates=["自注意力机制", "多头注意力"],
        )
        assert not rep.passed
        assert rep.stopped_at == "layer2"
        assert rep.layer3 is None
        assert len(rep.rejected) == 2

    async def test_disabled_net_never_passes(self):
        net = _net(_StubAuthority(["深度学习"]), enabled=False)
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.99, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        assert not rep.passed
        assert rep.stopped_at == "disabled"

    async def test_layer3_rejects_format_problem(self):
        authority = _StubAuthority(["坏词条"])
        # 让权威定义故意不合格（含占位符 + 过短）
        orig = authority.verify_many

        async def patched(terms, **kw):
            res = await orig(terms, **kw)
            for v in res:
                v.authoritative_definition = "TODO 待补充"
            return res

        authority.verify_many = patched
        net = _net(authority)
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["坏词条"],
        )
        assert not rep.passed
        assert rep.stopped_at == "layer3"
        assert any(r["stage"] == "layer3-format" for r in rep.rejected)

    async def test_layer3_rejects_failed_recheck(self):
        """二次检索没再命中权威源 → 不入库（写死逻辑，不依赖本地知识库）"""
        authority = _StubAuthority(["注意力机制"], recheck_ok=False)
        net = _net(authority)
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["注意力机制"],
        )
        assert not rep.passed
        assert rep.stopped_at == "layer3"
        assert any(r["stage"] == "layer3-recheck" for r in rep.rejected)
        assert authority.recheck_calls == 1   # 二次检索确实执行了


# ============================================================
# 三层筛网：通过路径与成本
# ============================================================

class TestFilterNetPassPaths:
    async def test_full_pass(self):
        authority = _StubAuthority(["深度学习", "过拟合"])
        net = _net(authority)
        rep = await net.run(
            user_task="解释一下深度学习",
            answer="深度学习是……",
            review_score=0.88, cloud_enhanced=True,
            rule_candidates=["深度学习", "过拟合", "不存在的假概念zzz"],
            domain="tech.ai",
        )
        assert rep.passed
        assert rep.stopped_at is None
        terms = {a.term for a in rep.accepted}
        assert terms == {"深度学习", "过拟合"}
        assert all(a.tier == 1 and a.sources for a in rep.accepted)
        assert all(a.domain == "tech.ai" for a in rep.accepted)
        # 假词条必须在第 2 层被拒
        assert any(r["term"] == "不存在的假概念zzz" for r in rep.rejected)

    async def test_cloud_decompose_adds_terms(self):
        authority = _StubAuthority(["内部协变量偏移"])
        llm_payload = {"items": [
            {"term": "内部协变量偏移", "claim": "稳定训练", "kind": "unknown_term", "reason": "术语"},
        ]}
        net = _net(authority, llm_payload)
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=[],
        )
        assert rep.passed
        assert [a.term for a in rep.accepted] == ["内部协变量偏移"]
        assert rep.accepted[0].kind == "unknown_term"

    async def test_cloud_decompose_failure_degrades_to_rule_candidates(self):
        """云端拆解失败时降级为规则候选，不得静默放行全部内容"""

        class _BoomLLM:
            async def generate_cloud(self, *a, **kw):
                raise RuntimeError("API 不可用")

        authority = _StubAuthority(["深度学习"])
        net = FilterNet(authority=authority, llm_client=_BoomLLM())
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习", "假词zzz"],
        )
        assert rep.passed
        assert [a.term for a in rep.accepted] == ["深度学习"]

    async def test_run_exception_is_fail_closed(self):
        """第 2 层抛异常 → 判定不通过，不得放行"""

        class _BoomAuthority:
            async def verify_many(self, terms, **kw):
                raise RuntimeError("网络炸了")

        net = _net(_BoomAuthority())
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        assert not rep.passed
        assert rep.stopped_at == "layer2"

    async def test_max_terms_caps_candidates(self):
        """候选词条数受 filter_max_terms 限制（控制联网+云端成本）"""
        authority = _StubAuthority([f"词{i}" for i in range(30)])
        net = _net(authority, max_terms=2)
        rep = await net.run(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True,
            rule_candidates=[f"词{i}" for i in range(30)],
        )
        # max_terms=2 → 合并后上限 max(max_terms*2, max_terms) = 4
        assert len(rep.rejected) + len(rep.accepted) <= 4


class TestMeaningfulTerm:
    def test_accepts_real_terms(self):
        assert _is_meaningful_term("深度学习")
        assert _is_meaningful_term("Transformer")
        assert _is_meaningful_term("RAG")

    def test_rejects_junk(self):
        assert not _is_meaningful_term("")
        assert not _is_meaningful_term("x")
        assert not _is_meaningful_term("12345")
        assert not _is_meaningful_term("!!!")
        assert not _is_meaningful_term("a" * 60)


# ============================================================
# 待审队列
# ============================================================

class TestPendingStore:
    def test_add_and_get(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        item_id = store.add(KIND_KNOWLEDGE, {"concept_name": "深度学习"}, domain="tech")
        rec = store.get(item_id)
        assert rec["status"] == STATUS_PENDING
        assert rec["kind"] == KIND_KNOWLEDGE
        assert rec["payload"]["concept_name"] == "深度学习"

    def test_traversal_id_blocked(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        assert store.get("../../evil") is None
        assert store.get("..\\..\\evil") is None

    def test_set_status_and_filter(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        a = store.add(KIND_KNOWLEDGE, {"concept_name": "A"})
        b = store.add(KIND_SKILL, {"domain": "d"})
        store.set_status(a, STATUS_APPROVED)
        store.set_status(b, STATUS_REJECTED)

        assert [r["id"] for r in store.list_items(status=STATUS_APPROVED)] == [a]
        assert [r["id"] for r in store.list_items(status=STATUS_REJECTED)] == [b]
        assert [r["id"] for r in store.list_items(kind=KIND_SKILL)] == [b]

        stats = store.stats()
        assert stats["approved"] == 1 and stats["rejected"] == 1

    def test_invalid_kind_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            PendingStore(root=str(tmp_path)).add("bogus", {})

    def test_audit_ledger(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        store.append_audit({"event": "filter_reject", "domain": "x"})
        store.append_audit({"event": "filter_pass", "domain": "x"})
        rows = store.read_audit()
        assert len(rows) == 2
        assert rows[-1]["event"] == "filter_pass"
        assert "ts" in rows[0]


# ============================================================
# 摄入管线
# ============================================================

class TestLearningIntake:
    async def test_filter_reject_writes_nothing(self, tmp_path):
        """筛网没过 → 不落盘、不进队列（只写审计）"""
        store = PendingStore(root=str(tmp_path))
        intake = LearningIntake(
            learning_engine=_StubEngine(),
            filter_net=_net(_StubAuthority(verified_terms=[])),
            store=store, auto_apply=False,
        )
        rep = await intake.process(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["假词zzz"],
        )
        assert not rep.passed
        assert rep.pending_ids == []
        assert store.list_items(limit=100) == []
        assert store.read_audit()[-1]["event"] == "filter_reject"

    async def test_filter_pass_goes_to_pending_not_applied(self, tmp_path):
        """通过筛网但 auto_apply=False（默认）→ 全进待审队列，不写图谱"""
        store = PendingStore(root=str(tmp_path))
        engine = _StubEngine()
        intake = LearningIntake(
            learning_engine=engine,
            filter_net=_net(_StubAuthority(["深度学习"])),
            store=store, auto_apply=False,
        )
        rep = await intake.process(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        assert rep.passed
        assert len(rep.pending_ids) == 1
        assert rep.applied_count == 0
        assert engine.applied == []          # 没有自动改自己
        rec = store.get(rep.pending_ids[0])
        assert rec["status"] == STATUS_PENDING
        assert rec["evidence"]                  # 权威出处被一起存下来了
        assert rec["filter"]["layers"]          # 逐层判定留痕

    async def test_auto_apply_when_enabled(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        engine = _StubEngine()
        intake = LearningIntake(
            learning_engine=engine,
            filter_net=_net(_StubAuthority(["深度学习"])),
            store=store, auto_apply=True,
        )
        rep = await intake.process(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        assert rep.applied_count == 1
        assert rep.pending_ids == []
        assert len(engine.applied) == 1

    async def test_validator_reject_blocks_pending(self, tmp_path):
        """过了筛网但被 PatchValidator 拦下 → 也不进队列"""
        store = PendingStore(root=str(tmp_path))
        intake = LearningIntake(
            learning_engine=_StubEngine(validate=False),
            filter_net=_net(_StubAuthority(["深度学习"])),
            store=store, auto_apply=False,
        )
        rep = await intake.process(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        assert rep.accepted_count == 1
        assert rep.pending_ids == []
        assert store.list_items(limit=100) == []

    async def test_approve_knowledge_writes_graph(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        engine = _StubEngine()
        intake = LearningIntake(
            learning_engine=engine,
            filter_net=_net(_StubAuthority(["深度学习"])),
            store=store, auto_apply=False,
        )
        rep = await intake.process(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        item_id = rep.pending_ids[0]

        res = intake.approve(item_id, note="人工确认")
        assert res["ok"]
        assert len(engine.applied) == 1
        assert store.get(item_id)["status"] == STATUS_APPROVED
        assert store.read_audit()[-1]["event"] == "approved"

    async def test_approve_twice_rejected(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        intake = LearningIntake(
            learning_engine=_StubEngine(),
            filter_net=_net(_StubAuthority(["深度学习"])),
            store=store, auto_apply=False,
        )
        rep = await intake.process(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        item_id = rep.pending_ids[0]
        assert intake.approve(item_id)["ok"]
        second = intake.approve(item_id)
        assert not second["ok"]
        assert "pending" in second["error"]

    async def test_reject_keeps_item_but_marks_status(self, tmp_path):
        store = PendingStore(root=str(tmp_path))
        engine = _StubEngine()
        intake = LearningIntake(
            learning_engine=engine,
            filter_net=_net(_StubAuthority(["深度学习"])),
            store=store, auto_apply=False,
        )
        rep = await intake.process(
            user_task="t", answer="a",
            review_score=0.9, cloud_enhanced=True, rule_candidates=["深度学习"],
        )
        item_id = rep.pending_ids[0]
        assert intake.reject(item_id, note="质量不够")["ok"]
        assert store.get(item_id)["status"] == STATUS_REJECTED
        assert engine.applied == []

    async def test_intake_exception_is_fail_closed(self, tmp_path):
        class _BoomNet:
            async def run(self, **kw):
                raise RuntimeError("筛网炸了")

        store = PendingStore(root=str(tmp_path))
        intake = LearningIntake(
            learning_engine=_StubEngine(), filter_net=_BoomNet(), store=store, auto_apply=False,
        )
        rep = await intake.process(
            user_task="t", answer="a", review_score=0.9, cloud_enhanced=True,
        )
        assert not rep.passed
        assert rep.pending_ids == []
        assert store.list_items(limit=100) == []


# ============================================================
# 技能自学习器（触发端 + 落盘持久化）
# ============================================================

def _review_result(confidence=0.9, dim_score=0.5, with_weak=True):
    dims = {}
    if with_weak:
        dims = {"professional": {"score": dim_score, "issues": ["术语使用不准确"],
                                 "suggestion": "补充领域术语表"}}
    else:
        dims = {"professional": {"score": 0.95, "issues": [], "suggestion": ""}}
    return {
        "confidence": confidence,
        "dimensions": dims,
        "overall": {"weighted_score": 0.7},
        "difficulty": {"threshold": 0.5},
    }


class TestSkillLearnerTrigger:
    def _learner(self, tmp_path, monkeypatch, min_samples=3):
        from core.skill_engine.skill_learner import SkillLearner
        buf = tmp_path / "buf.json"
        learner = SkillLearner(
            min_confidence=0.85, min_samples=min_samples, buffer_path=str(buf), persist=True
        )
        # 把统一待审队列指到临时目录
        store = PendingStore(root=str(tmp_path / "pending"))

        class _FakeIntake:
            @property
            def store(self):
                return store

        monkeypatch.setattr(
            "core.engines.learning_intake.get_learning_intake", lambda: _FakeIntake()
        )
        return learner, store

    def test_reject_low_confidence(self, tmp_path, monkeypatch):
        learner, _ = self._learner(tmp_path, monkeypatch)
        assert learner.collect_feedback(["root", "tech"], _review_result(confidence=0.5)) is False

    def test_reject_no_weak_dimension(self, tmp_path, monkeypatch):
        learner, _ = self._learner(tmp_path, monkeypatch)
        assert learner.collect_feedback(["root", "tech"], _review_result(with_weak=False)) is False

    def test_buffer_persists_across_instances(self, tmp_path, monkeypatch):
        """回归：缓冲区原为纯内存字典，重启即丢，导致「攒够 3 条」永远达不到"""
        from core.skill_engine.skill_learner import SkillLearner
        buf = str(tmp_path / "buf.json")
        a = SkillLearner(min_samples=99, buffer_path=buf, persist=True)
        a.collect_feedback(["root", "tech"], _review_result())
        b = SkillLearner(min_samples=99, buffer_path=buf, persist=True)
        assert b.get_buffer_size("tech") == 1

    def test_collect_feedback_is_pure_collection(self, tmp_path, monkeypatch):
        """collect_feedback 是纯收集：攒够样本也不自动入队，should_learn 稳定为真

        回归：曾一度把 trigger_learning 塞进 collect_feedback 内部，导致
        （a）should_learn 在收集后立刻翻假，调用方无法观察「攒够了」；
        （b）workflow service 的 should_learn 分支变成死代码。
        现约定：collect 纯收集，触发由工作流触发点显式执行。
        """
        learner, store = self._learner(tmp_path, monkeypatch, min_samples=2)
        learner.collect_feedback(["root", "tech"], _review_result())
        learner.collect_feedback(["root", "tech"], _review_result())
        assert store.list_items(limit=10) == [], "纯收集阶段不应产生待审条目"
        assert learner.should_learn("tech") is True, "谓词必须稳定可查"

    def test_trigger_enqueues_patch_at_min_samples(self, tmp_path, monkeypatch):
        """回归：原实现 should_learn 为真时只打一行日志，什么都不触发"""
        learner, store = self._learner(tmp_path, monkeypatch, min_samples=2)
        learner.collect_feedback(["root", "tech"], _review_result())
        learner.collect_feedback(["root", "tech"], _review_result())
        assert learner.should_learn("tech")
        assert learner.trigger_learning("tech"), "触发端应生成补丁并入队"
        items = store.list_items(limit=10)
        assert len(items) == 1
        assert items[0]["kind"] == KIND_SKILL
        assert items[0]["domain"] == "tech"
        assert items[0]["payload"]["added_constraints"]

    def test_empty_patch_not_enqueued(self, tmp_path, monkeypatch):
        """空补丁（无任何内容）不得入队"""
        learner, store = self._learner(tmp_path, monkeypatch, min_samples=1)
        monkeypatch.setattr(learner, "generate_patch", lambda domain: _EmptyPatch("tech"))
        assert learner.trigger_learning("tech") is None
        assert store.list_items(limit=10) == []

    def test_generated_constraint_is_actionable(self, tmp_path, monkeypatch):
        """回归：原生成的约束文本是「历史平均评分: 0.53」，无行动价值且易被误读为总分"""
        learner, store = self._learner(tmp_path, monkeypatch, min_samples=2)
        learner.collect_feedback(["root", "tech"], _review_result())
        learner.collect_feedback(["root", "tech"], _review_result())
        learner.trigger_learning("tech")
        constraints = store.list_items(limit=1)[0]["payload"]["added_constraints"]
        assert constraints
        joined = " ".join(constraints)
        assert "历史平均评分" not in joined


class _EmptyPatch:
    def __init__(self, domain):
        self.domain = domain
        self.added_keywords = {}
        self.added_constraints = []
        self.added_examples = []
        self.added_forbidden = []
        self.added_ontology = {}
