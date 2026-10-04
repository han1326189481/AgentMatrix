"""
Skill Engine V2 — 技能树模块

独立的技能树遍历、路径检测、领域匹配逻辑。
从 models.py 中提取，避免数据模型文件过于臃肿。
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# SkillTreeNode — 技能树节点
# ============================================================

@dataclass
class SkillTreeNode:
    """技能树节点"""
    id: str
    name: str
    children: List["SkillTreeNode"] = field(default_factory=list)
    model: str = ""  # 空字符串表示使用 ModelRegistry 默认模型
    parent_id: Optional[str] = None

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def find(self, node_id: str) -> Optional["SkillTreeNode"]:
        """递归查找节点"""
        if self.id == node_id:
            return self
        for child in self.children:
            result = child.find(node_id)
            if result:
                return result
        return None

    def get_path_to(self, node_id: str) -> List[str]:
        """获取从当前节点到目标节点的技能路径"""
        if self.id == node_id:
            return [self.id]

        for child in self.children:
            sub_path = child.get_path_to(node_id)
            if sub_path:
                return [self.id] + sub_path

        return []

    def get_all_leaf_ids(self) -> List[str]:
        """获取所有叶子节点ID"""
        if self.is_leaf():
            return [self.id]
        result = []
        for child in self.children:
            result.extend(child.get_all_leaf_ids())
        return result

    def get_all_domain_ids(self) -> List[str]:
        """获取所有领域节点ID（含中间节点）"""
        result = [self.id]
        for child in self.children:
            result.extend(child.get_all_domain_ids())
        return result

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "children": [c.to_dict() for c in self.children],
        }

    def get_effective_model(self, agent_id: str = "default") -> str:
        """获取有效模型名：空字符串时回退到 ModelRegistry"""
        if self.model:
            return self.model
        from core.model_registry import get_model
        return get_model(agent_id)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillTreeNode":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            children=[cls.from_dict(c) for c in data.get("children", [])],
            model=data.get("model", ""),
            parent_id=data.get("parent_id"),
        )


# ============================================================
# SkillTree — 技能树
# ============================================================

class SkillTree:
    """技能树 — 加载、遍历、路径检测"""

    def __init__(self, root: SkillTreeNode):
        self.root = root

    def get_path_to(self, domain_id: str) -> List[str]:
        """获取从根到指定领域的完整路径"""
        if domain_id == "root" or domain_id == self.root.id:
            return [self.root.id]
        return self.root.get_path_to(domain_id)

    def get_all_domains(self) -> List[str]:
        """获取所有领域ID"""
        return self.root.get_all_domain_ids()

    def get_all_leaf_domains(self) -> List[str]:
        """获取所有叶子领域ID"""
        return self.root.get_all_leaf_ids()

    def find_node(self, node_id: str) -> Optional[SkillTreeNode]:
        return self.root.find(node_id)

    def to_dict(self) -> dict:
        return {"tree": {"root": self.root.to_dict()}}

    @classmethod
    def from_dict(cls, data: dict) -> "SkillTree":
        tree_data = data.get("tree", {})
        root_data = tree_data.get("root", {})
        return cls(root=SkillTreeNode.from_dict(root_data))

    @classmethod
    def from_yaml(cls, filepath: str) -> "SkillTree":
        import yaml
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {"tree": {"root": {"id": "root", "name": "通用技能"}}}
        return cls.from_dict(data)

    # ===== 领域检测（关键词匹配） =====

    def detect_domain(self, user_input: str, skill_loader=None) -> List[str]:
        """沿技能树检测最匹配的领域路径

        对所有叶子节点进行关键词匹配，返回匹配度最高的领域路径。

        Args:
            user_input: 用户输入文本
            skill_loader: 可调用对象，接受 skill_id 返回 SkillBook（用于关键词匹配）

        Returns:
            技能路径列表（从根到叶），如 ["root", "tech", "tech.ai", "tech.ai.agent"]
        """
        if skill_loader is None:
            return ["root", "daily"]

        input_lower = user_input.lower()
        candidates = []

        for leaf_id in self.get_all_leaf_domains():
            if leaf_id == "root":
                continue

            try:
                skill = skill_loader(leaf_id)
            except Exception:
                continue

            matched_count = self._count_keyword_matches(input_lower, skill)
            if matched_count > 0:
                candidates.append({
                    "domain": leaf_id,
                    "matches": matched_count,
                    "confidence": skill.knowledge.confidence,
                })

        if candidates:
            candidates.sort(key=lambda x: (x["matches"], x["confidence"]), reverse=True)
            best = candidates[0]
            path = self.get_path_to(best["domain"])
            if path:
                return path

        return ["root", "daily"]

    def _count_keyword_matches(self, text: str, skill) -> int:
        """统计文本中匹配到的关键词数量

        支持三种关键词格式：
        1. dict: {kw: [aliases]} → 匹配 kw 或任意 alias
        2. list[str]: ["kw1", "kw2"] → 匹配任意字符串
        3. list[list]: [["kw1", "kw2"], ["kw3"]] → 递归匹配内层列表
        """
        count = 0
        for category, kw_map in skill.knowledge.keywords.items():
            if isinstance(kw_map, dict):
                for kw, aliases in kw_map.items():
                    all_terms = [kw]
                    if isinstance(aliases, list):
                        all_terms.extend(aliases)
                    if any(term.lower() in text for term in all_terms):
                        count += 1
            elif isinstance(kw_map, list):
                for item in kw_map:
                    if isinstance(item, str) and item.lower() in text:
                        count += 1
                    elif isinstance(item, list):
                        # 嵌套列表：匹配其中任意一个
                        if any(term.lower() in text for term in item if isinstance(term, str)):
                            count += 1
        return count

    def get_matched_keywords(self, text: str, skill) -> List[str]:
        """获取匹配到的关键词列表"""
        matched = []
        for category, kw_map in skill.knowledge.keywords.items():
            if isinstance(kw_map, dict):
                for kw, aliases in kw_map.items():
                    all_terms = [kw]
                    if isinstance(aliases, list):
                        all_terms.extend(aliases)
                    if any(term.lower() in text for term in all_terms):
                        matched.append(kw)
            elif isinstance(kw_map, list):
                for item in kw_map:
                    if isinstance(item, str) and item.lower() in text:
                        matched.append(item)
                    elif isinstance(item, list):
                        for term in item:
                            if isinstance(term, str) and term.lower() in text:
                                matched.append(term)
        return matched[:10]