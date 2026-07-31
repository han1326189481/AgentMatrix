"""
Skill Engine V2 — 意图分析器

核心功能：
- 意图识别：识别用户意图类型
- 领域检测：沿技能树检测最匹配的领域路径（委托给 SkillTree）
- 历史意图匹配：检查意图缓存
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """意图分析结果"""
    skill_path: List[str] = field(default_factory=lambda: ["root", "daily"])
    domain: str = "daily"
    confidence: float = 0.0
    is_cached: bool = False
    matched_keywords: List[str] = field(default_factory=list)
    raw_query: str = ""

    def to_dict(self) -> dict:
        return {
            "skill_path": self.skill_path,
            "domain": self.domain,
            "confidence": self.confidence,
            "is_cached": self.is_cached,
            "matched_keywords": self.matched_keywords,
            "raw_query": self.raw_query,
        }


class IntentAnalyzer:
    """意图分析器 — 识别用户意图并检测领域"""

    def __init__(self):
        self._skill_manager = None

    @property
    def skill_manager(self):
        if self._skill_manager is None:
            from core.skill_engine.skill_manager import get_skill_manager
            self._skill_manager = get_skill_manager()
        return self._skill_manager

    def analyze(self, user_input: str) -> Intent:
        """分析用户输入，返回意图分析结果

        检测策略（优先级从高到低）：
        1. 意图缓存命中（L1）
        2. 精确关键词匹配（委托给 SkillTree.detect_domain）
        3. Fallback → "daily"
        """
        intent = Intent(raw_query=user_input)

        # Step 1: 检查意图缓存
        cached = self._check_cache(user_input)
        if cached:
            intent.skill_path = cached
            intent.domain = cached[-1]
            intent.is_cached = True
            intent.confidence = 0.9
            return intent

        # Step 2: 委托给 SkillTree 进行关键词匹配
        tree = self.skill_manager.tree
        input_lower = user_input.lower()

        # 收集所有叶子节点及其匹配分数
        candidates = []
        for leaf_id in tree.get_all_leaf_domains():
            if leaf_id == "root":
                continue

            try:
                skill = self.skill_manager.load_skill(leaf_id)
            except Exception:
                continue

            matched_count = tree._count_keyword_matches(input_lower, skill)
            if matched_count > 0:
                candidates.append({
                    "domain": leaf_id,
                    "matches": matched_count,
                    "confidence": skill.knowledge.confidence,
                })

        # Step 3: 排序取最佳
        if candidates:
            candidates.sort(key=lambda x: (x["matches"], x["confidence"]), reverse=True)
            best = candidates[0]
            path = tree.get_path_to(best["domain"])
            if path:
                intent.skill_path = path
                intent.domain = best["domain"]
                intent.confidence = min(best["confidence"], 0.9)
                # 获取匹配的关键词
                try:
                    skill = self.skill_manager.load_skill(best["domain"])
                    intent.matched_keywords = tree.get_matched_keywords(input_lower, skill)
                except Exception:
                    pass
                return intent

        # Step 4: Fallback
        intent.skill_path = ["root", "daily"]
        intent.domain = "daily"
        intent.confidence = 0.3
        return intent

    def _check_cache(self, user_input: str) -> Optional[List[str]]:
        """检查意图缓存"""
        try:
            from core.skill_engine.intent_cache import get_intent_cache
            cache = get_intent_cache()
            return cache.lookup_skill_path(user_input)
        except ImportError:
            return None
        except Exception:
            return None


# 全局单例
_intent_analyzer: Optional[IntentAnalyzer] = None


def get_intent_analyzer() -> IntentAnalyzer:
    global _intent_analyzer
    if _intent_analyzer is None:
        _intent_analyzer = IntentAnalyzer()
    return _intent_analyzer