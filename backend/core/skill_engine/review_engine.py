"""
Review Engine — 独立评审引擎（Skill Engine V2.1）

从 Review Agent 中提取核心评审逻辑，实现：
- 6维度评分（accuracy/professional/completeness/reasoning/structure/actionable）
- 领域感知难度计算
- 风险评估 + 置信度计算
- 结构化 ReviewReport 输出
- 评审缓存（同输入避免重复计算）

配置来源：prompts/skills/review/{base_scoring,difficulty_matrix,tech_scoring}.yaml

用法：
    engine = ReviewEngine()
    report = engine.review(user_task, summary, writer_output, skill_path, domain_weights)

Report 结构：
    {
        "dimensions": {dim: {"score": 0.75, "weight": 0.25, "issues": [], "suggestion": ""}},
        "overall": {"weighted_score": 0.72, "pass": True},
        "risk": {"level": "low", "factors": [], "mitigation": "本地处理"},
        "confidence": 0.85,
        "difficulty": {"threshold": 0.45, "level": "medium", "reason": "..."},
        "review_score": 0.72,  # 向后兼容
        "difficulty_threshold": 0.45,  # 向后兼容
        "issues": [...],
        "suggestions": [...],
        "pass": True
    }
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from functools import lru_cache

logger = logging.getLogger(__name__)

# ============================================================
# Helper Functions
# ============================================================


def safe_float(value, default=0.0):
    """安全转换为 float，处理 None 和非数值"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def clamp_score(score: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """将评分锁定在 [min, max] 范围内"""
    return max(min_val, min(max_val, safe_float(score, 0.5)))


def normalize_score(score, default: float = 0.5) -> float:
    """将分数标准化到 0.0-1.0 范围

    处理 LLM 可能输出的 0-10 或 0-100 分制。
    """
    s = safe_float(score, default)
    if s > 1.0:
        if s <= 10.0:
            s = s / 10.0
        elif s <= 100.0:
            s = s / 100.0
        else:
            s = 0.5
    return clamp_score(s)


# ============================================================
# 评审缓存
# ============================================================

@dataclass
class ReviewCacheEntry:
    """评审缓存条目"""
    report: Dict[str, Any]
    fingerprint: str


class ReviewCache:
    """评审结果缓存（LRU，按输入指纹）"""

    def __init__(self, max_size: int = 50):
        self._max_size = max_size
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._keys: List[str] = []

    @staticmethod
    def fingerprint(user_task: str, writer_output: str, skill_path: List[str]) -> str:
        """生成输入指纹（前100字符 + 输出长度 + skill_path）"""
        import hashlib
        key = f"{user_task[:100]}|{len(writer_output)}|{'/'.join(skill_path)}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get(self, user_task: str, writer_output: str, skill_path: List[str]) -> Optional[Dict[str, Any]]:
        fp = self.fingerprint(user_task, writer_output, skill_path)
        if fp in self._cache:
            logger.debug(f"ReviewCache hit: {fp}")
            return self._cache[fp]
        return None

    def put(self, user_task: str, writer_output: str, skill_path: List[str], report: Dict[str, Any]):
        fp = self.fingerprint(user_task, writer_output, skill_path)
        self._cache[fp] = report
        self._keys.append(fp)
        # LRU 淘汰
        while len(self._keys) > self._max_size:
            old = self._keys.pop(0)
            self._cache.pop(old, None)

    def clear(self):
        self._cache.clear()
        self._keys.clear()


# ============================================================
# Review Engine
# ============================================================

class ReviewEngine:
    """独立评审引擎

    负责加载评分配置、执行多维度评审、输出结构化 ReviewReport。
    不依赖任何 Agent，可被 Review Agent 或测试直接调用。
    """

    # 6维度默认权重
    DEFAULT_DIMENSION_WEIGHTS = {
        "accuracy": 0.25,
        "professional": 0.20,
        "completeness": 0.20,
        "reasoning": 0.15,
        "structure": 0.10,
        "actionable": 0.10,
    }

    # 6维度默认基础分
    DEFAULT_BASE_SCORES = {
        "accuracy": 0.75,
        "professional": 0.70,
        "completeness": 0.65,
        "reasoning": 0.80,
        "structure": 0.75,
        "actionable": 0.70,
    }

    def __init__(self, config_dir: str = None, enable_cache: bool = True):
        if config_dir is None:
            from shared.platform import get_prompts_dir
            config_dir = os.path.join(get_prompts_dir(), "skills", "review")
        self._config_dir = config_dir
        self._configs: Optional[Dict[str, Any]] = None
        self._cache = ReviewCache() if enable_cache else None

    # ============================================================
    # 配置加载
    # ============================================================

    def _load_configs(self) -> Dict[str, Any]:
        """加载 V2 评分配置（首次调用后缓存）"""
        if self._configs is not None:
            return self._configs

        try:
            import yaml

            base_config = self._load_yaml("base_scoring.yaml")
            diff_config = self._load_yaml("difficulty_matrix.yaml")
            tech_config = self._load_yaml("tech_scoring.yaml")

            self._configs = {
                "base": base_config,
                "difficulty": diff_config,
                "tech": tech_config,
            }
            logger.info(f"ReviewEngine: V2 configs loaded from {self._config_dir}")
        except Exception as e:
            logger.warning(f"ReviewEngine: failed to load V2 configs: {e}, using defaults")
            self._configs = self._default_configs()

        return self._configs

    def _load_yaml(self, filename: str) -> dict:
        """加载单个 YAML 配置文件"""
        path = os.path.join(self._config_dir, filename)
        if os.path.exists(path):
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _default_configs(self) -> Dict[str, Any]:
        """内置默认配置（YAML 文件不可用时）"""
        return {
            "base": {
                "dimensions": {
                    "accuracy": {"weight": 0.25},
                    "professional": {"weight": 0.20},
                    "completeness": {"weight": 0.20},
                    "reasoning": {"weight": 0.15},
                    "structure": {"weight": 0.10},
                    "actionable": {"weight": 0.10},
                },
                "scoring": {"pass_threshold": 0.65, "weak_threshold": 0.70},
                "length_scoring": [
                    {"threshold": 50, "operator": "<", "adjustments": {"completeness": -0.25, "reasoning": -0.15}},
                    {"threshold": 150, "operator": "<", "adjustments": {"completeness": -0.10}},
                    {"threshold": 500, "operator": ">", "adjustments": {"completeness": 0.10, "structure": 0.05}},
                    {"threshold": 1000, "operator": ">", "adjustments": {"completeness": 0.15, "professional": 0.05}},
                ],
                "markdown_checks": [
                    {"pattern": "#{1,3}\\s", "bonus": {"structure": 0.15, "professional": 0.05}},
                    {"pattern": "\\*\\*|__", "bonus": {"structure": 0.05}},
                    {"pattern": "- |\\* |\\d+\\.", "bonus": {"structure": 0.10}},
                ],
            },
            "difficulty": {
                "complexity_keywords": [
                    {"keyword": kw, "weight": 0.03} for kw in
                    ["方案", "策划", "设计", "架构", "系统", "分析", "报告", "论文", "PPT", "预算", "风险评估", "技术选型", "多智能体", "端云协同"]
                ],
                "content_length_boost": [
                    {"threshold": 2000, "operator": ">", "boost": 0.10},
                    {"threshold": 1000, "operator": ">", "boost": 0.05},
                ],
                "multi_question_boost": 0.08,
                "multi_paragraph_boost": 0.08,
                "weak_dimension_boost": [
                    {"weak_count": 1, "boost": 0.0}, {"weak_count": 2, "boost": 0.03},
                    {"weak_count": 3, "boost": 0.06}, {"weak_count": 4, "boost": 0.10},
                    {"weak_count": 5, "boost": 0.15}, {"weak_count": 6, "boost": 0.20},
                ],
            },
            "tech": {},
        }

    def get_config(self, section: str) -> dict:
        """获取指定配置段"""
        configs = self._load_configs()
        return (configs.get(section) or {})

    # ============================================================
    # 主评审入口
    # ============================================================

    def review(self, user_task: str, summary: str, writer_output: str,
               skill_path: List[str] = None, domain_weights: Dict[str, float] = None,
               use_cache: bool = True) -> Dict[str, Any]:
        """执行完整评审，返回结构化 ReviewReport

        Args:
            user_task: 用户原始任务
            summary: 摘要信息
            writer_output: Writer Agent 输出
            skill_path: 技能路径（如 ["root", "tech", "ai"]）
            domain_weights: 领域维度权重（如 {"accuracy": 0.30, "professional": 0.25}）
            use_cache: 是否使用缓存

        Returns:
            ReviewReport dict
        """
        if skill_path is None:
            skill_path = ["root", "daily"]
        if domain_weights is None:
            domain_weights = dict(self.DEFAULT_DIMENSION_WEIGHTS)

        # 缓存检查
        if self._cache and use_cache:
            cached = self._cache.get(user_task, writer_output, skill_path)
            if cached:
                return cached

        configs = self._load_configs()

        # 1. 维度评分
        dims = self._score_dimensions(writer_output, user_task, domain_weights)

        # 2. 加权总分
        weighted_score = self._calc_weighted_score(dims)

        # 3. 难度计算
        difficulty = self._calculate_difficulty(user_task, writer_output, weighted_score, dims, skill_path)

        # 4. 风险评估
        risk = self._assess_risk(dims, weighted_score)

        # 5. 置信度
        confidence = self._calculate_confidence(dims)

        # 6. pass_threshold
        base = configs.get("base", {}) or {}
        scoring = base.get("scoring", {}) or {}
        pass_threshold = safe_float(scoring.get("pass_threshold"), 0.65)

        report = {
            "dimensions": dims,
            "overall": {
                "weighted_score": round(weighted_score, 2),
                "pass": weighted_score >= pass_threshold,
            },
            "risk": risk,
            "confidence": round(confidence, 2),
            "difficulty": difficulty,
            "review_score": round(weighted_score, 2),
            "difficulty_threshold": difficulty["threshold"],
            "issues": self._collect_issues(dims),
            "suggestions": self._collect_suggestions(dims),
            "pass": weighted_score >= pass_threshold,
        }

        # 缓存结果
        if self._cache and use_cache:
            self._cache.put(user_task, writer_output, skill_path, report)

        return report

    # ============================================================
    # 维度评分
    # ============================================================

    def _score_dimensions(self, writer_output: str, user_task: str = "",
                           weights: Dict[str, float] = None) -> Dict[str, Dict]:
        """对6个维度独立评分"""
        configs = self._load_configs()
        base = configs.get("base", {}) or {}
        tech = configs.get("tech", {}) or {}
        if weights is None:
            weights = dict(self.DEFAULT_DIMENSION_WEIGHTS)

        dims = {}
        output_len = len(writer_output) if writer_output else 0
        output_lower = writer_output.lower() if writer_output else ""

        # 基础分
        default_scores = base.get("default_scores", {}) or {}
        for dim_key in self.DEFAULT_BASE_SCORES:
            dims[dim_key] = {
                "score": safe_float(default_scores.get(dim_key), self.DEFAULT_BASE_SCORES[dim_key]),
                "weight": safe_float(weights.get(dim_key), self.DEFAULT_DIMENSION_WEIGHTS[dim_key]),
                "issues": [],
                "suggestion": "",
            }

        # 内容长度调整
        for rule in (base.get("length_scoring") or []):
            threshold = safe_float(rule.get("threshold"), 0)
            operator = rule.get("operator", ">")
            if (operator == "<" and output_len < threshold) or \
               (operator == ">" and output_len > threshold):
                for dim, adj in (rule.get("adjustments") or {}).items():
                    if dim in dims:
                        dims[dim]["score"] += safe_float(adj, 0)

        # Markdown 格式检查
        for check in (base.get("markdown_checks") or []):
            pattern = check.get("pattern", "")
            if pattern and re.search(pattern, writer_output, re.MULTILINE):
                for dim, bonus in (check.get("bonus") or {}).items():
                    if dim in dims:
                        dims[dim]["score"] += safe_float(bonus, 0)

        # 技术领域专项检查
        for check_cfg in (tech.get("tech_checks") or {}).values():
            if not isinstance(check_cfg, dict):
                continue
            pattern = check_cfg.get("pattern", "")
            if pattern and re.search(pattern, writer_output, re.MULTILINE):
                for dim, bonus in (check_cfg.get("bonus") or {}).items():
                    if dim in dims:
                        dims[dim]["score"] += safe_float(bonus, 0)

        # 逻辑性检测
        if any(kw in output_lower for kw in ["因为", "因此", "所以", "首先", "其次", "然后", "最后"]):
            dims["reasoning"]["score"] = safe_float(dims["reasoning"]["score"] + 0.05, dims["reasoning"]["score"])

        # 短内容结构性调整
        if output_len < 50:
            dims["structure"]["score"] = clamp_score(safe_float(dims["structure"]["score"] + 0.10, dims["structure"]["score"]))

        # 锁定分数
        for dim in dims:
            dims[dim]["score"] = clamp_score(safe_float(dims[dim]["score"], 0.5))

        return dims

    def _calc_weighted_score(self, dims: Dict[str, Dict]) -> float:
        """计算加权总分"""
        total = 0.0
        total_weight = 0.0
        for dim_key, dim_data in dims.items():
            weight = safe_float(dim_data.get("weight"), 0.0)
            score = safe_float(dim_data.get("score"), 0.5)
            total += score * weight
            total_weight += weight
        return total / max(total_weight, 0.01)

    # ============================================================
    # 难度计算
    # ============================================================

    def _calculate_difficulty(self, user_task: str, writer_output: str,
                               weighted_score: float, dims: Dict[str, Dict],
                               skill_path: List[str]) -> Dict[str, Any]:
        """计算任务难度

        V2.4 (2026-07-30): base_difficulty 与 weighted_score 解耦
          - 旧逻辑: base_difficulty = 1.0 - weighted_score
          - 新逻辑: base_difficulty = 领域基础难度（domain_base_difficulty）
          原因: 难度应反映任务本身复杂度，review_score 反映回答质量，
                两者作为独立信号供 Judge 双门槛矩阵使用，避免矩阵退化。
        """
        configs = self._load_configs()
        diff_cfg = configs.get("difficulty", {}) or {}

        # V2.4: base_difficulty 改为领域基础难度（任务维度），不再用 1.0 - weighted_score
        domain = skill_path[-1] if skill_path else "daily"
        domain_diffs = diff_cfg.get("domain_base_difficulty", {}) or {}
        base_difficulty = safe_float(self._lookup_domain_difficulty(domain, domain_diffs), 0.20)
        complexity_boost = 0.0
        reason_parts = [f"{domain}领域({base_difficulty:.2f})"]
        user_lower = user_task.lower() if user_task else ""

        # 复杂度关键词
        for item in (diff_cfg.get("complexity_keywords") or []):
            if not isinstance(item, dict):
                continue
            if (item.get("keyword") or "") in user_lower:
                complexity_boost += safe_float(item.get("weight"), 0.03)

        # 内容长度加成
        output_len = len(writer_output) if writer_output else 0
        for rule in (diff_cfg.get("content_length_boost") or []):
            if not isinstance(rule, dict):
                continue
            if rule.get("operator") == ">" and output_len > safe_float(rule.get("threshold"), 0):
                complexity_boost += safe_float(rule.get("boost"), 0)

        # 多问题/多段落
        if user_task and (user_task.count("?") + user_task.count("？") >= 2):
            complexity_boost += safe_float(diff_cfg.get("multi_question_boost"), 0.08)
            reason_parts.append("多问题")
        if user_task and "\n" in user_task and len(user_task.split("\n")) >= 3:
            complexity_boost += safe_float(diff_cfg.get("multi_paragraph_boost"), 0.08)

        # 弱维度加成
        # V2.4 (2026-07-30): 弱阈值跟随 base_scoring.yaml 的 weak_threshold（0.60），
        #   不再硬编码 0.70。
        #   注意: 解耦后弱维度加成是难度对「回答质量」的唯一反馈通道，保留但已削弱。
        base_cfg = configs.get("base", {}) or {}
        base_scoring = base_cfg.get("scoring", {}) or {}
        weak_threshold = safe_float(base_scoring.get("weak_threshold"), 0.60)
        weak_count = sum(1 for d in (dims or {}).values()
                        if isinstance(d, dict) and safe_float(d.get("score"), 1.0) < weak_threshold)
        for rule in (diff_cfg.get("weak_dimension_boost") or []):
            if not isinstance(rule, dict):
                continue
            if rule.get("weak_count") == weak_count:
                complexity_boost += safe_float(rule.get("boost"), 0)
                if weak_count >= 2:
                    reason_parts.append(f"{weak_count}个弱维度")

        difficulty = max(0.0, min(1.0, base_difficulty + complexity_boost))

        if difficulty < 0.35:
            level = "simple"
        elif difficulty < 0.65:
            level = "medium"
        elif difficulty < 0.80:
            level = "complex"
        else:
            level = "expert"

        return {
            "threshold": round(difficulty, 2),
            "level": level,
            "reason": " | ".join(reason_parts) if reason_parts else f"{domain}领域({base_difficulty:.2f})"
        }

    @staticmethod
    def _lookup_domain_difficulty(domain: str, domain_diffs: dict) -> float:
        """在领域难度字典中查找指定领域的难度加成"""
        if domain in domain_diffs:
            val = domain_diffs[domain]
            if isinstance(val, dict):
                return float(val.get("base", 0.0))
            return float(val)

        parts = domain.split(".")
        current = domain_diffs
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return 0.0

        if isinstance(current, dict):
            return float(current.get("base", 0.0))
        return float(current) if current else 0.0

    # ============================================================
    # 风险 & 置信度
    # ============================================================

    @staticmethod
    def _assess_risk(dims: Dict[str, Dict], weighted_score: float) -> Dict[str, Any]:
        """评估风险等级"""
        if weighted_score < 0.4:
            level = "critical"
        elif weighted_score < 0.55:
            level = "high"
        elif weighted_score < 0.70:
            level = "medium"
        else:
            level = "low"

        factors = []
        if dims.get("accuracy", {}).get("score", 0) < 0.6:
            factors.append("准确性不足")
        if dims.get("completeness", {}).get("score", 0) < 0.5:
            factors.append("完整性严重不足")

        return {
            "level": level,
            "factors": factors,
            "mitigation": "云端增强" if level in ("critical", "high") else "本地处理"
        }

    @staticmethod
    def _calculate_confidence(dims: Dict[str, Dict]) -> float:
        """计算评审置信度（分数离散度越低，置信度越高）"""
        scores = [d["score"] for d in dims.values()]
        if not scores:
            return 0.7
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        return round(max(0.5, min(1.0, 1.0 - variance)), 2)

    # ============================================================
    # Issues & Suggestions
    # ============================================================

    @staticmethod
    def _collect_issues(dims: Dict[str, Dict]) -> List[str]:
        issues = []
        for name, dim in dims.items():
            if dim["score"] < 0.6:
                issues.append(f"{name}评分偏低({dim['score']:.2f})")
        return issues

    @staticmethod
    def _collect_suggestions(dims: Dict[str, Dict]) -> List[str]:
        suggestions = []
        if dims.get("completeness", {}).get("score", 0) < 0.6:
            suggestions.append("补充缺失的关键内容章节")
        if dims.get("professional", {}).get("score", 0) < 0.6:
            suggestions.append("提升专业术语准确性")
        if dims.get("reasoning", {}).get("score", 0) < 0.6:
            suggestions.append("优化逻辑推理链条")
        if dims.get("structure", {}).get("score", 0) < 0.6:
            suggestions.append("改善内容结构和层次")
        if dims.get("actionable", {}).get("score", 0) < 0.6:
            suggestions.append("增加可执行的具体步骤")
        return suggestions

    # ============================================================
    # 领域权重
    # ============================================================

    def get_domain_weights(self, skill_path: List[str]) -> Dict[str, float]:
        """从 SkillManager 获取领域权重，回退到默认值"""
        try:
            from core.skill_engine.skill_manager import get_skill_manager
            mgr = get_skill_manager()
            return mgr.get_domain_weights(skill_path)
        except (ImportError, Exception):
            return dict(self.DEFAULT_DIMENSION_WEIGHTS)

    # ============================================================
    # 缓存管理
    # ============================================================

    def clear_cache(self):
        if self._cache:
            self._cache.clear()

    def clear_config_cache(self):
        self._configs = None


# ============================================================
# 全局单例
# ============================================================

_review_engine: Optional[ReviewEngine] = None


def get_review_engine() -> ReviewEngine:
    """获取全局 ReviewEngine 单例"""
    global _review_engine
    if _review_engine is None:
        _review_engine = ReviewEngine()
    return _review_engine