"""
Skill Engine V2 — 技能自学习器

核心功能：
- Review 反馈收集：从 Review Agent 的 ReviewReport 中收集高置信度反馈
- 置信度过滤：仅 confidence >= 0.85 的反馈纳入学习
- 最少样本数：同一领域累积 >= 3 条反馈后触发学习
- Patch 生成：分析弱维度和常见问题，生成 SkillPatch
- 半自动应用：**默认全部落待审队列**（人工审批后才写入技能书）；
  auto_approve=True 时才直接应用

学习闭环（2026-09-24 打通）：
  Review Report → confidence > 0.85? → 收集反馈（落盘，重启不丢）
    → min_samples >= 3? → 生成 SkillPatch → 落统一待审队列 pending
    → 人工在审批 API / 前端确认 → 版本号 +1

★ 与知识筛网的分工：
  - **知识类**（KnowledgePatch）走 `core.engines.filter_net` 三层筛网（联网核验权威出处）
  - **技能类**（SkillPatch）改的是提示词/约束，没有"权威出处"可言，
    因此不套三层筛网，改为「自动生成 + 全进 pending + 人工审批」，
    另加一条本地质量约束（空补丁 / 垃圾文本不入队）。
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def _default_buffer_path() -> str:
    """反馈缓冲区落盘路径（遵循 shared.platform 规范）"""
    try:
        from shared.platform import get_storage_dir
        base = os.path.join(get_storage_dir(), "pending_learning")
    except Exception:
        base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "storage", "pending_learning",
        )
    return os.path.join(base, "_feedback_buffer.json")


class SkillLearner:
    """技能自学习器 — 从 Review 反馈中学习并改进 Skill Book

    ★ 反馈缓冲区**落盘持久化**（2026-09-24 修复）：
      原实现 `_feedback_buffer` 是纯内存字典，后端一重启就清空，
      而触发条件是「同一领域累积 >= 3 条」，导致生产环境几乎永远攒不够
      —— 自学习闭环在触发端就是断的。现在每次写入即落盘，启动时加载。
    """

    def __init__(
        self,
        min_confidence: float = 0.85,
        min_samples: int = 3,
        buffer_path: Optional[str] = None,
        persist: bool = True,
    ):
        self.min_confidence = min_confidence
        self.min_samples = min_samples
        self._feedback_buffer: Dict[str, List[Dict[str, Any]]] = {}
        self.persist = persist
        self._buffer_path = buffer_path or _default_buffer_path()
        if self.persist:
            self._load_buffer()

    # ============================================================
    # 缓冲区持久化
    # ============================================================

    def _load_buffer(self) -> None:
        try:
            if not os.path.exists(self._buffer_path):
                return
            with open(self._buffer_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._feedback_buffer = {
                    str(k): list(v) for k, v in data.items() if isinstance(v, list)
                }
                logger.info(
                    "SkillLearner: 已加载反馈缓冲区 %d 个领域 / %d 条",
                    len(self._feedback_buffer),
                    sum(len(v) for v in self._feedback_buffer.values()),
                )
        except Exception as e:
            logger.warning(f"SkillLearner: 反馈缓冲区加载失败（从空开始）: {e}")
            self._feedback_buffer = {}

    def _save_buffer(self) -> None:
        if not self.persist:
            return
        try:
            os.makedirs(os.path.dirname(self._buffer_path), exist_ok=True)
            tmp = self._buffer_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._feedback_buffer, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._buffer_path)
        except Exception as e:
            logger.warning(f"SkillLearner: 反馈缓冲区落盘失败: {e}")

    # ============================================================
    # 反馈收集
    # ============================================================

    def collect_feedback(self, skill_path: List[str], review_result: Dict[str, Any]) -> bool:
        """收集 Review 反馈

        Args:
            skill_path: 技能路径，如 ["root", "tech", "tech.ai", "tech.ai.agent"]
            review_result: Review Agent 的评审结果（dict 格式）

        Returns:
            True 如果反馈被接受（置信度达标），False 如果被丢弃
        """
        if not skill_path or len(skill_path) < 2:
            return False

        domain = skill_path[-1]

        # 提取置信度
        confidence = self._extract_confidence(review_result)
        if confidence < self.min_confidence:
            logger.debug(f"SkillLearner: 丢弃低置信度反馈 domain={domain} confidence={confidence:.2f}")
            return False

        # 提取弱维度信息
        weak_dims = self._extract_weak_dimensions(review_result)

        if not weak_dims:
            logger.debug(f"SkillLearner: 无弱维度，跳过 domain={domain}")
            return False

        # 存储反馈
        if domain not in self._feedback_buffer:
            self._feedback_buffer[domain] = []

        feedback_entry = {
            "skill_path": skill_path,
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "confidence": confidence,
            "weak_dimensions": weak_dims,
            "weighted_score": review_result.get("overall", {}).get("weighted_score", 0.0),
            "difficulty_threshold": review_result.get("difficulty", {}).get("threshold", 0.0),
        }

        self._feedback_buffer[domain].append(feedback_entry)
        self._save_buffer()
        logger.info(
            f"SkillLearner: 收集反馈 domain={domain} "
            f"buffer_size={len(self._feedback_buffer[domain])} "
            f"weak_dims={[d['name'] for d in weak_dims]}"
        )

        # ★ 触发点不在这里（2026-09-24 归位）：
        #   collect_feedback 保持「纯收集」语义，无任何副作用；
        #   should_learn() 因此是一个稳定可查的谓词（先问再触发）；
        #   真正的「自动生成补丁 + 入待审队列」由工作流触发点执行：
        #     core/workflow/service.py::_collect_and_trigger_skill_learning
        #       → collect_feedback() → should_learn() → trigger_learning()
        #   若在此处自作主张触发，会把 service.py 的 should_learn 判断变成
        #   永远为假的死代码，且让调用方无法观察到「攒够了」这一状态。
        return True

    def trigger_learning(self, domain: str) -> Optional[str]:
        """触发一次技能学习：生成补丁 → 落统一待审队列

        Returns:
            入队成功返回待审条目 id；无有效补丁 / 入队失败返回 None
        """
        try:
            patch = self.generate_patch(domain)
        except Exception as e:
            logger.error(f"SkillLearner: 生成补丁失败 domain={domain}: {e}")
            return None

        if patch is None:
            logger.info(f"SkillLearner: domain={domain} 无可用补丁（缓冲区不足）")
            return None

        problems = self._patch_problems(patch)
        if problems:
            logger.warning(
                f"SkillLearner: domain={domain} 生成的补丁质量不达标，丢弃: {problems}"
            )
            return None

        try:
            from core.engines.learning_intake import (
                PendingStore, KIND_SKILL, get_learning_intake,
            )
            store = get_learning_intake().store
            item_id = store.add(
                kind=KIND_SKILL,
                payload={
                    "domain": patch.domain,
                    "added_keywords": patch.added_keywords,
                    "added_constraints": patch.added_constraints,
                    "added_examples": patch.added_examples,
                    "added_forbidden": patch.added_forbidden,
                    "added_ontology": patch.added_ontology,
                },
                domain=domain,
                evidence=[],
                layers=[{
                    "layer": 0, "name": "技能补丁本地质量约束",
                    "passed": True, "reasons": [], "detail": {"checks": "empty/garbage"},
                }],
                trigger={
                    "source": "skill_learner",
                    "buffered_samples": self.min_samples,
                    "min_confidence": self.min_confidence,
                },
            )
            logger.info(f"SkillLearner: 补丁已入待审队列 id={item_id}")
            return item_id
        except Exception as e:
            logger.error(f"SkillLearner: 补丁入队失败: {e}")
            return None

    @staticmethod
    def _patch_problems(patch) -> List[str]:
        """技能补丁的本地质量约束（空补丁 / 垃圾文本不入队）"""
        problems: List[str] = []
        total = (
            len(patch.added_constraints)
            + len(patch.added_forbidden)
            + sum(len(v) for v in (patch.added_keywords or {}).values())
            + len(patch.added_examples)
            + len(patch.added_ontology or {})
        )
        if total == 0:
            problems.append("空补丁（无任何约束/禁止项/关键词）")

        try:
            from core.engines.filter_net import _format_problems
            for c in list(patch.added_constraints) + list(patch.added_forbidden):
                if len(c) > 10:
                    bad = _format_problems(c)
                    if bad:
                        problems.append(f"文本不达标 {c[:24]!r}: {bad}")
                        break
        except Exception:
            pass
        return problems

    # ============================================================
    # 学习触发
    # ============================================================

    def should_learn(self, domain: str) -> bool:
        """判断是否应该触发学习"""
        if domain not in self._feedback_buffer:
            return False
        return len(self._feedback_buffer[domain]) >= self.min_samples

    def get_buffer_size(self, domain: str) -> int:
        """获取某领域的反馈缓冲区大小"""
        return len(self._feedback_buffer.get(domain, []))

    # ============================================================
    # Patch 生成
    # ============================================================

    def generate_patch(self, domain: str) -> Optional[Any]:
        """生成技能补丁

        分析缓冲区中的反馈，生成 SkillPatch：
        1. 统计最常见的弱维度 → 添加约束
        2. 统计常见问题类型 → 添加禁止事项
        3. 统计缺失内容 → 建议补充关键词

        Args:
            domain: 领域ID，如 "tech.ai.agent"

        Returns:
            SkillPatch 对象，如果缓冲区不足则返回 None
        """
        from core.skill_engine.models import SkillPatch

        feedbacks = self._feedback_buffer.get(domain, [])
        if not feedbacks:
            return None

        patch = SkillPatch(domain=domain)

        # 分析弱维度
        weak_dim_stats = self._analyze_weak_dimensions(feedbacks)
        if weak_dim_stats:
            # 最常见的弱维度 → 添加约束
            constraints = self._generate_dimension_constraints(weak_dim_stats)
            patch.added_constraints.extend(constraints)

        # 分析常见问题
        common_issues = self._extract_common_issues(feedbacks)
        if common_issues:
            # 常见的错误模式 → 添加禁止事项
            forbidden = self._extract_forbidden_patterns(common_issues)
            patch.added_forbidden.extend(forbidden)

        # 提取建议的关键词（弱维度相关）
        suggested_keywords = self._suggest_keywords(weak_dim_stats, domain)
        if suggested_keywords:
            patch.added_keywords = suggested_keywords

        logger.info(
            f"SkillLearner: 生成 Patch domain={domain} "
            f"constraints={len(patch.added_constraints)} "
            f"forbidden={len(patch.added_forbidden)} "
            f"keywords={sum(len(v) for v in patch.added_keywords.values())}"
        )

        # 清除缓冲区（避免重复生成相同 Patch）
        self._feedback_buffer[domain] = []
        self._save_buffer()

        return patch

    def apply_patch(self, skill_id: str, patch: Any, auto_approve: bool = False) -> bool:
        """应用技能补丁

        Args:
            skill_id: 技能ID（如 "tech.ai.agent"）
            patch: SkillPatch 对象
            auto_approve: True=直接应用，False=保存为待审核

        Returns:
            True 如果成功
        """
        if not auto_approve:
            # 保存为待审核补丁
            try:
                patch.save_pending(skill_id)
                logger.info(f"SkillLearner: Patch 已保存为待审核 skill_id={skill_id}")
                return True
            except Exception as e:
                logger.error(f"SkillLearner: 保存待审核 Patch 失败: {e}")
                return False

        # 自动应用
        try:
            from core.skill_engine.skill_manager import get_skill_manager
            mgr = get_skill_manager()
            skill = mgr.load_skill(skill_id)

            # 应用补丁
            self._merge_patch_to_skill(skill, patch)

            # 版本号 +1
            skill.meta.version = self._bump_version(skill.meta.version)

            # 保存
            mgr.save_skill(skill_id, skill)
            mgr.invalidate_cache(skill_id)

            logger.info(f"SkillLearner: Patch 已自动应用 skill_id={skill_id} version={skill.meta.version}")
            return True
        except Exception as e:
            logger.error(f"SkillLearner: 自动应用 Patch 失败: {e}")
            return False

    # ============================================================
    # 分析辅助方法
    # ============================================================

    def _extract_confidence(self, review_result: Dict[str, Any]) -> float:
        """从 Review 结果中提取置信度"""
        if isinstance(review_result, dict):
            # 直接字段
            if "confidence" in review_result:
                return float(review_result["confidence"])
            # 嵌套在 overall 中
            overall = review_result.get("overall", {})
            if isinstance(overall, dict) and "confidence" in overall:
                return float(overall["confidence"])
        return 0.0

    def _extract_weak_dimensions(self, review_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 Review 结果中提取弱维度（score < 0.70）"""
        weak = []
        dims = review_result.get("dimensions", {})

        if isinstance(dims, dict):
            for name, dim_data in dims.items():
                if isinstance(dim_data, dict):
                    score = dim_data.get("score", 0.0)
                    issues = dim_data.get("issues", [])
                    suggestion = dim_data.get("suggestion", "")
                elif isinstance(dim_data, (int, float)):
                    score = float(dim_data)
                    issues = []
                    suggestion = ""
                else:
                    continue

                if score < 0.70:
                    weak.append({
                        "name": name,
                        "score": round(score, 2),
                        "issues": issues,
                        "suggestion": suggestion,
                    })

        weak.sort(key=lambda x: x["score"])
        return weak

    def _analyze_weak_dimensions(self, feedbacks: List[Dict]) -> Dict[str, Dict]:
        """统计弱维度出现频率"""
        stats = {}
        for fb in feedbacks:
            for dim in fb.get("weak_dimensions", []):
                name = dim["name"]
                if name not in stats:
                    stats[name] = {"count": 0, "total_score": 0.0, "issues": [], "suggestions": []}
                stats[name]["count"] += 1
                stats[name]["total_score"] += dim["score"]
                for issue in dim.get("issues", []):
                    if isinstance(issue, dict):
                        stats[name]["issues"].append(issue.get("description", str(issue)))
                    elif isinstance(issue, str):
                        stats[name]["issues"].append(issue)
                if dim.get("suggestion"):
                    stats[name]["suggestions"].append(dim["suggestion"])

        # 排序：出现次数最多的在前
        return dict(sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True))

    def _generate_dimension_constraints(self, weak_stats: Dict[str, Dict]) -> List[str]:
        """根据弱维度统计生成约束"""
        constraints = []
        dim_name_map = {
            "accuracy": "准确性",
            "professional": "专业性",
            "completeness": "完整性",
            "reasoning": "逻辑性",
            "structure": "结构性",
            "actionable": "可执行性",
        }

        for dim_name, stats in list(weak_stats.items())[:3]:
            if stats["count"] >= self.min_samples:
                cn_name = dim_name_map.get(dim_name, dim_name)
                avg_score = stats["total_score"] / stats["count"]
                # 2026-09-24 修正：原实现只写「历史平均评分: 0.53」这种无行动价值的文本
                # （而且容易被误读成答案总分）。改为「维度 + 该维度均值 + 首要已知问题」，
                # 让约束本身可执行。
                unique_issues = [i for i in dict.fromkeys(stats["issues"]) if i]
                text = f"强化{cn_name}（该维度历史均值 {avg_score:.2f}）"
                if unique_issues:
                    text += f"：{unique_issues[0][:60]}"
                constraints.append(text)

                # 附加具体建议（去重、过滤过短项）
                unique_suggestions = [s for s in dict.fromkeys(stats["suggestions"]) if s and len(s) > 4]
                for sug in unique_suggestions[:2]:
                    if sug not in constraints:
                        constraints.append(sug)

        return constraints

    def _extract_common_issues(self, feedbacks: List[Dict]) -> List[str]:
        """提取常见问题描述"""
        issues = []
        for fb in feedbacks:
            for dim in fb.get("weak_dimensions", []):
                for issue in dim.get("issues", []):
                    if isinstance(issue, dict):
                        desc = issue.get("description", "")
                    elif isinstance(issue, str):
                        desc = issue
                    else:
                        continue
                    if desc and len(desc) > 3:
                        issues.append(desc)

        # 去重并统计频率
        from collections import Counter
        counter = Counter(issues)
        return [desc for desc, count in counter.most_common(5)]

    def _extract_forbidden_patterns(self, common_issues: List[str]) -> List[str]:
        """从常见问题中提取禁止事项"""
        forbidden = []
        for issue in common_issues[:3]:
            if len(issue) > 10:
                forbidden.append(f"避免: {issue[:80]}")
        return forbidden

    def _suggest_keywords(self, weak_stats: Dict[str, Dict], domain: str) -> Dict[str, Dict[str, List[str]]]:
        """根据弱维度建议补充关键词"""
        suggested = {}

        # 专业性弱 → 建议补充专业术语
        if "professional" in weak_stats:
            suggested["professional"] = {
                "专业术语": weak_stats["professional"].get("suggestions", [])[:5]
            }

        # 完整性弱 → 建议补充相关概念
        if "completeness" in weak_stats:
            suggested["completeness"] = {
                "补充内容": weak_stats["completeness"].get("suggestions", [])[:5]
            }

        return suggested

    def _merge_patch_to_skill(self, skill, patch):
        """将 Patch 合并到 Skill Book"""
        # 合并关键词
        if patch.added_keywords:
            for category, kw_map in patch.added_keywords.items():
                if category not in skill.knowledge.keywords:
                    skill.knowledge.keywords[category] = {}
                if isinstance(skill.knowledge.keywords[category], dict):
                    skill.knowledge.keywords[category].update(kw_map)

        # 合并约束
        if patch.added_constraints:
            existing = set(skill.knowledge.constraints)
            for c in patch.added_constraints:
                if c not in existing:
                    skill.knowledge.constraints.append(c)

        # 合并禁止事项
        if patch.added_forbidden:
            existing = set(skill.forbidden)
            for f in patch.added_forbidden:
                if f not in existing:
                    skill.forbidden.append(f)

        # 合并示例
        if patch.added_examples:
            skill.knowledge.examples.extend(patch.added_examples)
            skill.knowledge.examples = skill.knowledge.examples[-5:]  # 最多保留5个

    @staticmethod
    def _bump_version(version: str) -> str:
        """版本号 +1（末位）"""
        parts = version.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
        except (ValueError, IndexError):
            parts.append("1")
        return ".".join(parts)

    # ============================================================
    # 缓存管理
    # ============================================================

    def clear_buffer(self, domain: str = None):
        """清除反馈缓冲区"""
        if domain:
            self._feedback_buffer.pop(domain, None)
        else:
            self._feedback_buffer.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取学习器状态"""
        return {
            "buffered_domains": len(self._feedback_buffer),
            "total_feedbacks": sum(len(v) for v in self._feedback_buffer.values()),
            "domains_ready": [
                d for d, fbs in self._feedback_buffer.items()
                if len(fbs) >= self.min_samples
            ],
            "min_confidence": self.min_confidence,
            "min_samples": self.min_samples,
        }


# ============================================================
# 全局单例
# ============================================================

_skill_learner: Optional[SkillLearner] = None


def get_skill_learner() -> SkillLearner:
    global _skill_learner
    if _skill_learner is None:
        _skill_learner = SkillLearner(min_confidence=0.85, min_samples=3)
    return _skill_learner