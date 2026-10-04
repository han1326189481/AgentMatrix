"""Learning Engine V3 — Graph-based 自动学习闭环

V3 与 V2.1 SkillLearner 的核心区别:
- V2.1: 基于反馈收集，手动审核
- V3:  基于 Graph Diff，自动发现 + PatchValidator 守门

流程:
Writer Output
  → ConceptExtractor（规则提取，零 LLM）
  → SkillGraph.diff()（集合差，零 LLM）
  → PatchGenerator（生成 Patch）
  → PatchValidator（冲突/重复/置信度检查）
  → SkillGraph.merge()（安全合并）
  → [复杂概念] → DeepSeek 兜底分析
"""

import json
import os
import re
import shutil
import logging
import threading
import time
from datetime import date
from typing import Any, Dict, List, Optional, Set

from core.skill_engine.models import KnowledgePatch, WorkflowPatch

logger = logging.getLogger(__name__)

# ★ 数据安全护栏（2026-09-24 事故后新增）
# 事故：tests/test_phase7.py 用 `LearningEngine(SkillGraph())`（空图）构造引擎，
# 调 apply_patches() 后把内存里的 2 个节点全量 save 到生产 skill_graph.yaml，
# 一次性抹掉 636 个节点的知识库。
# 护栏：持久化前对比磁盘现有节点数，内存图若「缩水」到磁盘的 MIN_NODE_RETENTION 以下，
# 直接拒绝写入并报 error —— 宁可不落盘，也不能静默清空知识库。
MIN_NODE_RETENTION = 0.5


# ════════════════════════════════════════════════════════════════
# _deepseek_analyze 的成本护栏（2026-10-04 实装）
# ════════════════════════════════════════════════════════════════
# 为什么要有护栏：这是全链路唯一「按概念逐条上云」的路径。一次长回答可能提取出
# 几十个概念，其中找不到父节点的会逐个触发云端判定——不封顶就是不可控账单。
# 三重约束（总开关 / 日额度 / 最小间隔）+ 单次 learn() 的概念数上限，
# 任何一层拦下都退回「独立节点」策略，不会中断学习流程。


def _run_coro_sync(coro, timeout: float = 25.0):
    """在同步方法里安全地跑协程。

    `learn()` 是同步接口（测试与 API 都按同步调），而云端客户端是 async；
    若当前线程已有运行中的事件循环，`asyncio.run()` 会直接抛
    "cannot be called from a running event loop"。丢到独立线程里跑可同时兼容两种场景。
    """
    import asyncio
    import concurrent.futures

    def _runner():
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_runner).result(timeout=timeout)


class _AnalyzeBudget:
    """三重成本护栏：总开关 / 日额度 / 最小间隔（进程内，线程安全）"""

    def __init__(self):
        self._lock = threading.Lock()
        self._used_today = 0
        self._day = date.today()
        self._last_call_ts = 0.0

    def acquire(self) -> "tuple[bool, str]":
        """申请一次云调用额度。返回 (是否放行, 拒绝原因)。

        额度在**发起调用前**扣减：即使调用随后失败，这次尝试也算已消耗——
        否则失败重试会把日额度绕开。
        """
        try:
            from app.config import settings
            enabled = bool(getattr(settings, "learning_deepseek_enabled", True))
            max_per_day = int(getattr(settings, "learning_deepseek_max_per_day", 20))
            min_interval = int(getattr(settings, "learning_deepseek_min_interval_seconds", 30))
        except Exception:
            enabled, max_per_day, min_interval = True, 20, 30

        if not enabled:
            return False, "learning_deepseek_enabled=False"

        with self._lock:
            today = date.today()
            if today != self._day:
                self._day = today
                self._used_today = 0

            if max_per_day >= 0 and self._used_today >= max_per_day:
                return False, f"已达日额度上限 {max_per_day}"

            now = time.monotonic()
            if self._last_call_ts:
                wait = min_interval - (now - self._last_call_ts)
                if wait > 0:
                    return False, f"距上次云调用不足 {min_interval}s（还需 {wait:.1f}s）"

            self._used_today += 1
            self._last_call_ts = now
            return True, ""

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "used_today": self._used_today,
                "day": self._day.isoformat(),
                "last_call_ts": self._last_call_ts,
            }

    def reset(self) -> None:
        """重置额度（仅供测试 / 运维）"""
        with self._lock:
            self._used_today = 0
            self._last_call_ts = 0.0


_analyze_budget = _AnalyzeBudget()


def deepseek_analyze_budget() -> _AnalyzeBudget:
    """暴露护栏实例（读取额度 / 测试重置）"""
    return _analyze_budget


def _parse_analyze_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """从云端返回里抠出 JSON 对象（容忍 markdown 围栏与前后杂字）"""
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[A-Za-z0-9_]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


_ANALYZE_PROMPT = """你是知识图谱入库前的「新概念判定器」。
给定一个在本地知识图谱中**找不到任何可关联父节点**的概念，判断它是否值得作为独立知识点收录。

判定规则：
- 只收录具有明确技术 / 学术 / 业务含义的实体概念（如「向量数据库」「注意力机制」）。
- 泛泛短语、口语片段、模板套话、从标题里切出来的半截词，一律判定为不值得。
- 定义必须准确客观、40~120 字；**不确定就判不值得**，宁可漏收也不要把噪声写进知识库。

严格输出 JSON，不要任何解释文字、不要 markdown 围栏：
{{"worth_learning": true, "definition": "一句话定义", "domain": "所属领域", "related": ["相关概念"], "confidence": 0.0}}

【待判定概念】{concept}

【出处上下文（节选）】
{context}"""


class LearningEngine:
    """本地优先的学习引擎

    核心原则:
    1. 90% 操作零 LLM（Graph Diff + 名称匹配）
    2. 仅复杂概念走 DeepSeek 兜底
    3. 所有 Patch 必须通过 PatchValidator
    4. 只学习高质量回答（review_score >= 0.70）
    """

    def __init__(self, skill_graph, reasoning_graph=None,
                 validator=None, yaml_path: Optional[str] = None,
                 persist: bool = True, deepseek_enabled: Optional[bool] = None):
        """
        Args:
            skill_graph: 待操作的 SkillGraph 实例
            reasoning_graph: 推理图谱（可选）
            validator: PatchValidator（缺省自动创建）
            yaml_path: SkillGraph 持久化路径。**缺省为仓库生产路径**。
                测试 / 嵌入使用务必显式传入临时路径 —— 否则会把临时小图
                写到生产知识库上（2026-09-24 事故根因）。
            persist: 是否允许落盘。测试场景可置 False 彻底禁写。
            deepseek_enabled: 是否允许 `_deepseek_analyze` 上云。缺省读
                `settings.learning_deepseek_enabled`（默认 True），显式传 False 可
                在测试里彻底掐断云调用（**测试务必显式传 False**，避免真烧额度）。
        """
        self.skill_graph = skill_graph
        self.reasoning_graph = reasoning_graph
        if validator:
            self.validator = validator
        else:
            from core.engines.patch_validator import PatchValidator
            self.validator = PatchValidator(skill_graph)
        if deepseek_enabled is None:
            try:
                from app.config import settings
                deepseek_enabled = bool(getattr(settings, "learning_deepseek_enabled", True))
            except Exception:
                deepseek_enabled = True
        self.deepseek_enabled = deepseek_enabled
        self._learning_log: List[dict] = []
        self._workflow_log: List[dict] = []
        self.persist = persist
        # Layer 4 持久化路径（可注入）
        self._skill_graph_yaml = yaml_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "graphs", "skill_graph.yaml"
        )

    def learn(self, user_task: str, writer_output: str,
              skill_path: List[str], review_score: float,
              cloud_enhanced: bool = False) -> dict:
        """从一次回答中学习

        Args:
            cloud_enhanced: 是否由云端增强触发。True 时跳过 review_score 门槛
                （云端已润色，质量有保证）；False 时仍需 review_score >= 0.70。

        Returns:
            {
                "knowledge_patches": [...],
                "reasoning_patches": [...],
                "workflow_patches": [...],
                "deepseek_used": False,
                "validated": 3,
                "rejected": 1
            }
        """
        result = {
            "knowledge_patches": [],
            "reasoning_patches": [],
            "workflow_patches": [],
            "deepseek_used": False,
            "validated": 0,
            "rejected": 0
        }

        # 质量门槛：只学习高质量回答
        # 例外：云端增强（cloud_enhanced=True）时跳过门槛，因云端润色已保证质量
        # （用户决策 2026-07-28：触发云端 enhance 的答案才值得学习）
        if not cloud_enhanced and review_score < 0.70:
            logger.info(
                f"LearningEngine: 跳过学习 (review_score={review_score:.2f} < 0.70, "
                f"cloud_enhanced=False)"
            )
            return result
        if cloud_enhanced:
            logger.info(
                f"LearningEngine: 云端增强触发学习，跳过 review_score 门槛 "
                f"(review_score={review_score:.2f})"
            )

        # 1. 知识提取 + Graph Diff
        concepts = self._extract_concepts(writer_output)
        new_concepts = self.skill_graph.diff(concepts)
        domain = skill_path[-1] if skill_path else "root"

        # 单次 learn() 的上云概念数上限（护栏第 4 层，见文件顶部说明）
        max_analyze = 3
        try:
            from app.config import settings
            max_analyze = int(getattr(settings, "learning_deepseek_max_concepts_per_run", 3))
        except Exception:
            pass
        analyze_attempts = 0

        for concept in new_concepts:
            parent = self.skill_graph.find_similar_node(concept)
            if parent:
                patch = self._make_knowledge_patch(concept, parent, skill_path)
            else:
                # Layer 2→3 接通：找不到 parent 时，尝试 DeepSeek 兜底
                # （受总开关 / 日额度 / 最小间隔 / 单次上限四重约束）
                patch = None
                if analyze_attempts < max_analyze:
                    analyze_attempts += 1
                    patch = self._deepseek_analyze(concept, writer_output, domain=domain)
                if patch:
                    result["deepseek_used"] = True
                else:
                    # 云端未放行或判定不值得时，创建独立 concept 节点（不关联已有节点）
                    # 让 PatchValidator 决定是否通过，避免概念被直接跳过
                    patch = self._make_standalone_patch(concept, skill_path)

            if patch:
                validation = self.validator.validate_knowledge(patch)
                if validation.passed:
                    result["knowledge_patches"].append(patch)
                    result["validated"] += 1
                    logger.info(f"LearningEngine: 知识Patch通过: {concept}")
                else:
                    result["rejected"] += 1
                    logger.info(f"LearningEngine: 知识Patch被拒: {concept} "
                              f"({validation.errors})")

        # 2. 推理模式提取
        if self.reasoning_graph:
            pattern = self.reasoning_graph.extract_from_text(writer_output)
            if pattern:
                validation = self.validator.validate_reasoning(pattern)
                if validation.passed:
                    result["reasoning_patches"].append(pattern)
                    result["validated"] += 1
                    logger.info(
                        f"LearningEngine: 推理模式通过: {pattern.pattern_name}"
                    )
                else:
                    result["rejected"] += 1
                    logger.info(f"LearningEngine: 推理模式被拒: "
                              f"{validation.errors}")

        # 3. 工作流提取
        workflow = self._extract_workflow(writer_output)
        if workflow:
            validation = self.validator.validate_workflow(workflow)
            if validation.passed:
                result["workflow_patches"].append(workflow)
                result["validated"] += 1
                logger.info(
                    f"LearningEngine: 工作流Patch通过: {len(workflow.steps)}步"
                )
            else:
                result["rejected"] += 1
                logger.info(f"LearningEngine: 工作流Patch被拒: "
                          f"{validation.errors}")

        self._learning_log.append({
            "user_task": user_task[:100],
            "review_score": review_score,
            "new_concepts": len(new_concepts),
            "validated": result["validated"],
            "rejected": result["rejected"],
            "deepseek_used": result["deepseek_used"],
            "deepseek_attempts": analyze_attempts,
        })

        return result

    # 中文停用词 — 提取概念时过滤这些常见词组
    _CN_STOPWORDS = frozenset({
        # 代词/连词/介词
        "我们", "你们", "他们", "她们", "它们", "这个", "那个", "这些", "那些",
        "什么", "怎么", "为什么", "如何", "如果", "但是", "因为", "所以", "而且",
        "或者", "并且", "虽然", "尽管", "已经", "正在", "可以", "应该", "需要",
        "可能", "也许", "一定", "必须", "的话", "的话", "是的", "不是", "还有",
        # 常见动词/形容词
        "进行", "通过", "根据", "按照", "结合", "包括", "除外", "另外", "此外",
        "主要", "重要", "基本", "基础", "具体", "特定", "某些", "其他", "其它",
        "部分", "全部", "全部", "整体", "整体", "本身", "自动", "手动", "实时",
        "确保", "保证", "实现", "完成", "处理", "解决", "提供", "支持", "包含",
        # 时间/数量
        "现在", "目前", "之后", "之前", "以后", "以前", "今天", "明天", "昨天",
        "一次", "一种", "一个", "一些", "一点", "一下", "上面", "下面", "里面",
        "前面", "后面", "外面", "中间",
        # 常见名词（不适合作为概念）
        "情况", "方式", "方法", "方面", "内容", "信息", "数据", "系统", "功能",
        "问题", "结果", "目标", "过程", "步骤", "阶段", "级别", "类型", "模式",
        "场景", "环境", "工具", "资源", "能力", "价值", "意义", "作用", "效果",
        "建议", "意见", "想法", "看法", "观点", "态度", "状态", "趋势", "变化",
    })

    def _extract_concepts(self, text: str) -> Set[str]:
        """从文本中提取概念（规则，零 LLM）

        提取策略:
        1. Markdown 标题（## 概念名）
        2. 驼峰命名（Transformer, FastAPI）
        3. 下划线命名（skill_graph）
        4. 中文书名号（《概念》）
        5. 英文大写缩略词（LLM, RAG, CNN）
        6. Markdown 加粗文本（**概念**）— 中文关键概念
        7. 中文定义句式（"XX是/是指/指的是"）
        8. 中英混合术语（如"Transformer模型"）
        9. 中文专业术语（2-6字词组 + 停用词过滤）
        """
        concepts = set()

        # 1. Markdown 标题
        headers = re.findall(r'^#{1,3}\s+(.+?)$', text, re.MULTILINE)
        for h in headers:
            h = h.strip()
            if 3 < len(h) < 50:
                concepts.add(h)

        # 2. 驼峰命名（含混合大小写如 FastAPI）
        camel_matches = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text)
        camel_matches += re.findall(r'\b([A-Z][a-z]+(?:[A-Z]{2,}[a-z]*))\b', text)
        concepts.update(camel_matches)

        # 3. 下划线命名
        snake_matches = re.findall(r'\b([a-z]+(?:_[a-z]+)+)\b', text)
        concepts.update(snake_matches)

        # 4. 中文书名号
        book_matches = re.findall(r'《(.+?)》', text)
        for bm in book_matches:
            if 3 < len(bm) < 50:
                concepts.add(bm)

        # 5. 英文大写缩略词（3-5个字母）
        acronym_matches = re.findall(r'\b([A-Z]{3,5})\b', text)
        for am in acronym_matches:
            # 过滤常见英文单词
            if am not in ("THE", "AND", "FOR", "THIS", "THAT", "WITH", "FROM",
                          "ARE", "WAS", "NOT", "BUT", "ALL", "CAN", "HAS",
                          "ITS", "WILL", "ALSO", "THAN", "THEN", "WHEN",
                          "MORE", "SOME", "VERY", "JUST", "LIKE", "INTO",
                          "OVER", "ONLY", "NEW", "EACH", "MOST", "SUCH",
                          "MAKE", "USE", "SEE", "NOW", "OUR", "TOO", "WAY",
                          "HOW", "WHO", "WHY", "WHAT", "WHICH", "WHERE"):
                concepts.add(am)

        # 6. Markdown 加粗文本（**概念** 或 __概念__）— 作者明确标注的关键概念
        bold_matches = re.findall(r'\*\*(.+?)\*\*', text)
        bold_matches += re.findall(r'__(.+?)__', text)
        for bm in bold_matches:
            bm = bm.strip()
            # 过滤太短/太长的、纯标点、纯数字
            if 2 <= len(bm) <= 40 and re.search(r'[\u4e00-\u9fffa-zA-Z]', bm):
                # 去掉尾部冒号等标点
                bm = re.sub(r'[:：\s]+$', '', bm)
                if bm and bm not in self._CN_STOPWORDS:
                    concepts.add(bm)

        # 7. 中文定义句式（"XX是/是指/指的是XX"）— 提取主语作为概念
        definition_matches = re.findall(
            r'([\u4e00-\u9fff]{2,8})(?:是|是指|指的是|是一种|是一个|是一类)',
            text
        )
        for dm in definition_matches:
            dm = dm.strip()
            if dm not in self._CN_STOPWORDS and 2 <= len(dm) <= 8:
                concepts.add(dm)

        # 8. 中英混合术语（如"Transformer模型"、"BERT算法"）
        # 中文部分限制1-2字（名词后缀如"模型/算法/机制/网络/系统"），更长中文由规则9处理
        mixed_matches = re.findall(
            r'([A-Z][a-zA-Z]{2,}[\u4e00-\u9fff]{1,2})', text
        )
        mixed_matches += re.findall(
            r'([\u4e00-\u9fff]{2,4}[A-Z][a-zA-Z]{2,})', text
        )
        for mm in mixed_matches:
            mm = mm.strip()
            # 如果包含"的"，只保留"的"前面的部分
            if "的" in mm:
                mm = mm.split("的")[0]
            # 必须同时包含英文和中文
            if 3 <= len(mm) <= 30 and re.search(r'[\u4e00-\u9fff]', mm) and re.search(r'[a-zA-Z]', mm):
                concepts.add(mm)

        # 9. 中文专业术语（2-6字词组 + 停用词过滤 + 频率/上下文过滤）
        # 策略：只提取出现 >= 2 次的中文词组，或出现在列表项/冒号后的词组
        # 避免提取大量无意义碎片
        from collections import Counter
        cn_all = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
        cn_freq = Counter(cn_all)

        # 9a. 出现频率 >= 2 次的中文词组
        for cnd, freq in cn_freq.items():
            if freq < 2:
                continue
            if cnd in self._CN_STOPWORDS:
                continue
            if re.match(r'^第.{1,2}$', cnd):
                continue
            if "的" in cnd and len(cnd) <= 4:
                continue
            concepts.add(cnd)

        # 9b. 出现在列表项/冒号后的中文词组（"概念：..." 或 "- 概念：..."）
        list_item_matches = re.findall(
            r'(?:^|\n)\s*[-*]?\s*[\u4e00-\u9fff]{2,8}[:：]', text
        )
        for lm in list_item_matches:
            # 提取冒号前的中文词组
            term = re.search(r'([\u4e00-\u9fff]{2,8})[:：]', lm)
            if term:
                t = term.group(1).strip()
                if t not in self._CN_STOPWORDS and 2 <= len(t) <= 8:
                    concepts.add(t)

        return concepts

    def _make_knowledge_patch(self, concept: str, parent,
                              skill_path: List[str]) -> KnowledgePatch:
        """创建知识 Patch（有关联父节点）"""
        return KnowledgePatch(
            concept_name=concept,
            definition=f"自动提取自回答内容（关联: {parent.name}）",
            domain=skill_path[-1] if skill_path else "root",
            related_concepts=[parent.name],
            confidence=0.75,
            source="auto_extract"
        )

    def _make_standalone_patch(self, concept: str,
                               skill_path: List[str]) -> KnowledgePatch:
        """创建独立知识 Patch（无关联父节点，DeepSeek 兜底禁用时使用）

        与 _make_knowledge_patch 的区别：
        - 不关联到已有节点（related_concepts 为空）
        - confidence 略低（0.65 vs 0.75），因为无父节点佐证
        - 仍需通过 PatchValidator 的全部检查
        """
        return KnowledgePatch(
            concept_name=concept,
            definition=f"自动提取自回答内容（独立概念，域: {skill_path[-1] if skill_path else 'root'}）",
            domain=skill_path[-1] if skill_path else "root",
            related_concepts=[],
            confidence=0.65,
            source="auto_extract"
        )

    def _extract_workflow(self, text: str) -> Optional[WorkflowPatch]:
        """提取工作流模式（从有序列表）"""
        steps = re.findall(r'^\d+\.\s*\*?\*?(.+?)\*?\*?\s*$', text, re.MULTILINE)
        if len(steps) >= 3:
            return WorkflowPatch(
                task_type="detected",
                steps=steps[:7],
                optimization="自动提取"
            )
        return None

    async def _deepseek_analyze_async(
        self, concept: str, context: str, domain: str = "root"
    ) -> Optional[KnowledgePatch]:
        """云端判定「本地找不到父节点的新概念」是否值得收录，并生成带定义的知识补丁

        只有明确的 `worth_learning=true` 且定义长度达标才产出补丁；
        其余情况返回 None，由调用方退回 `_make_standalone_patch`。
        """
        from core.llm.client import get_llm_client

        prompt = _ANALYZE_PROMPT.format(
            concept=concept, context=(context or "")[:1500]
        )
        raw = await get_llm_client().generate_cloud(prompt=prompt)
        data = _parse_analyze_json(raw)
        if not data:
            logger.info("LearningEngine: DeepSeek 返回无法解析，判定不值得: %s", concept)
            return None

        if not bool(data.get("worth_learning")):
            logger.info("LearningEngine: DeepSeek 判定不值得学习: %s", concept)
            return None

        definition = str(data.get("definition", "")).strip()
        if len(definition) < 8:
            logger.info("LearningEngine: DeepSeek 定义过短视为无效: %s", concept)
            return None

        related = [
            str(x).strip()[:40]
            for x in (data.get("related") or [])
            if str(x).strip()
        ][:5]
        try:
            confidence = float(data.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = min(max(confidence, 0.0), 1.0)

        return KnowledgePatch(
            concept_name=concept,
            definition=definition[:300],
            domain=str(data.get("domain") or domain)[:60],
            related_concepts=related,
            confidence=confidence,
            source="deepseek_analyze",
        )

    def _deepseek_analyze(
        self, concept: str, context: str, domain: str = "root"
    ) -> Optional[KnowledgePatch]:
        """DeepSeek 兜底（同步门面，仅在本地图谱找不到可关联父节点时调用）

        四重成本护栏（总开关 / 日额度 / 最小间隔 / 单次上限）在调用方与本方法内按序生效，
        任何一层拦下都返回 None → 退回独立节点策略，学习流程不中断。
        """
        if not self.deepseek_enabled:
            logger.debug("LearningEngine: DeepSeek 兜底被关闭: %s", concept)
            return None

        allowed, reason = _analyze_budget.acquire()
        if not allowed:
            logger.info("LearningEngine: DeepSeek 兜底跳过（%s）: %s", reason, concept)
            return None

        try:
            patch = _run_coro_sync(
                self._deepseek_analyze_async(concept, context, domain)
            )
        except Exception as e:
            logger.warning("LearningEngine: DeepSeek 兜底调用失败（退回独立节点）: %s", e)
            return None

        if patch:
            logger.info("LearningEngine: DeepSeek 兜底收录: %s", concept)
        return patch

    def apply_patches(self, patches: dict) -> int:
        """应用已校验的 Patch 到 Skill Graph

        Returns:
            成功应用的 Patch 数量
        """
        count = 0

        # 知识 Patches
        for kp in patches.get("knowledge_patches", []):
            node_id = kp.concept_name.lower().replace(" ", "_").replace("-", "_")
            if node_id not in self.skill_graph.nodes:
                from core.graphs.skill_graph import GraphNode, GraphEdge
                self.skill_graph.add_node(GraphNode(
                    id=node_id,
                    name=kp.concept_name,
                    node_type="concept",
                    domain=kp.domain,
                    description=kp.definition,
                ))
                for related in kp.related_concepts:
                    related_id = related.lower().replace(" ", "_").replace("-", "_")
                    if related_id in self.skill_graph.nodes:
                        self.skill_graph.add_edge(GraphEdge(
                            from_node=node_id,
                            to_node=related_id,
                            edge_type="related_to"
                        ))
                count += 1
                logger.info(f"LearningEngine: 已应用知识Patch: {kp.concept_name}")

        # 推理 Patches
        for rp in patches.get("reasoning_patches", []):
            if self.reasoning_graph:
                if rp.pattern_id not in self.reasoning_graph.patterns:
                    self.reasoning_graph.register(rp)
                    count += 1
                    logger.info(f"LearningEngine: 已应用推理Patch: {rp.pattern_name}")

        # 工作流 Patches — 记录到学习日志，供后续优化参考
        for wp in patches.get("workflow_patches", []):
            self._workflow_log.append({
                "task_type": wp.task_type,
                "steps": wp.steps,
                "optimization": wp.optimization,
            })
            count += 1
            logger.info(f"LearningEngine: 已记录工作流Patch: {wp.task_type} ({len(wp.steps)}步)")

        # Layer 4 持久化：写回 yaml，重启不丢失（缩水护栏 + 原子写 + 备份）
        if count > 0:
            self._persist_safe()
            if self.reasoning_graph:
                try:
                    self.reasoning_graph.save_learned_patterns()
                except Exception as e:
                    logger.warning(f"LearningEngine: ReasoningGraph 持久化失败: {e}")

        return count

    def _persist_safe(self) -> bool:
        """安全持久化 SkillGraph：缩水护栏 + 原子写 + 自动备份。

        Returns:
            True 已写入；False 跳过（禁用 / 护栏拦截 / 异常）
        """
        if not self.persist:
            logger.debug("LearningEngine: persist=False，跳过落盘")
            return False

        path = self._skill_graph_yaml
        mem_nodes = len(self.skill_graph.nodes)

        # —— 护栏：拒绝用缩水图覆盖生产知识库 ——
        disk_nodes = 0
        if os.path.exists(path):
            try:
                from core.graphs.skill_graph import SkillGraph
                disk_nodes = len(SkillGraph.load(path).nodes)
            except Exception as e:
                logger.warning(f"LearningEngine: 读取磁盘现有图谱失败（跳过护栏比对）: {e}")

        if disk_nodes > 0 and mem_nodes < disk_nodes * MIN_NODE_RETENTION:
            logger.error(
                "LearningEngine: 拒绝持久化 —— 内存图 %d 节点 << 磁盘 %d 节点，"
                "疑似用空/临时图覆盖生产知识库，已阻止写入（这是保护，不是故障）。"
                "测试场景请构造 LearningEngine 时显式传入 yaml_path。",
                mem_nodes, disk_nodes,
            )
            return False

        # —— 原子写 + 备份前一份 ——
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(path):
                shutil.copy2(path, path + ".bak")
            tmp = path + ".tmp"
            self.skill_graph.save(tmp)
            os.replace(tmp, path)
            logger.info(
                f"LearningEngine: SkillGraph 已持久化到 {path} "
                f"({mem_nodes} 节点，备份 → {path}.bak)"
            )
            return True
        except Exception as e:
            logger.warning(f"LearningEngine: SkillGraph 持久化失败: {e}")
            return False

    def get_stats(self) -> dict:
        """获取学习统计"""
        total = len(self._learning_log)
        if total == 0:
            return {"total_sessions": 0, "total_validated": 0, "total_rejected": 0,
                    "deepseek_usage": 0, "avg_review_score": 0.0}

        validated = sum(s["validated"] for s in self._learning_log)
        rejected = sum(s["rejected"] for s in self._learning_log)
        deepseek_used = sum(1 for s in self._learning_log if s["deepseek_used"])
        avg_score = sum(s["review_score"] for s in self._learning_log) / total

        return {
            "total_sessions": total,
            "total_validated": validated,
            "total_rejected": rejected,
            "deepseek_usage": deepseek_used,
            "avg_review_score": round(avg_score, 2),
            "validator_stats": self.validator.get_stats(),
        }