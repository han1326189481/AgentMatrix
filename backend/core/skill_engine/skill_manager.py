"""
Skill Engine V2 — 技能书管理器

核心功能：
- 加载技能书（YAML → SkillBook 对象）
- 缓存已加载的技能书
- 技能栈合并（沿技能树叠加）
- 能力查询、关键词查询
- 领域检测
"""

import os
import logging
from typing import Dict, Any, List, Optional, Set
from .models import SkillBook
from .skill_tree import SkillTree

logger = logging.getLogger(__name__)


class SkillManager:
    """技能书管理器 — 核心组件"""

    def __init__(self, skills_dir: str = None):
        if skills_dir is None:
            # 从 shared.platform 获取 prompts 目录
            from shared.platform import get_prompts_dir
            prompts_dir = get_prompts_dir()
            self._skills_dir = os.path.join(prompts_dir, "skills")
        else:
            self._skills_dir = skills_dir

        self._cache: Dict[str, SkillBook] = {}
        self._tree: Optional[SkillTree] = None

    # ===== 加载 =====

    def load_skill(self, skill_id: str) -> SkillBook:
        """加载单个技能书（带缓存）"""
        if skill_id in self._cache:
            return self._cache[skill_id]

        filepath = self._resolve_path(skill_id)
        if not os.path.exists(filepath):
            logger.warning(f"Skill file not found: {filepath}, returning empty skill")
            skill = SkillBook.from_dict({"meta": {"skill_id": skill_id, "name": skill_id}})
        else:
            skill = SkillBook.from_yaml(filepath)

        self._cache[skill_id] = skill
        return skill

    def load_skill_stack(self, skill_path: List[str]) -> List[SkillBook]:
        """沿技能树路径加载技能栈（从根到叶）"""
        return [self.load_skill(sid) for sid in skill_path]

    def load_skill_stack_merged(self, skill_path: List[str]) -> SkillBook:
        """加载并合并技能栈（子节点覆盖父节点）"""
        stack = self.load_skill_stack(skill_path)
        return SkillBook.merge(stack)

    def load_all_skills(self) -> Dict[str, SkillBook]:
        """加载所有技能书"""
        result = {}
        if not os.path.isdir(self._skills_dir):
            return result

        for root, dirs, files in os.walk(self._skills_dir):
            for filename in files:
                if filename.endswith(".yaml") or filename.endswith(".yml"):
                    filepath = os.path.join(root, filename)
                    try:
                        skill = SkillBook.from_yaml(filepath)
                        if skill.meta.skill_id:
                            result[skill.meta.skill_id] = skill
                            self._cache[skill.meta.skill_id] = skill
                    except Exception as e:
                        logger.warning(f"Failed to load skill {filepath}: {e}")
        return result

    # ===== 查询 =====

    def get_capabilities(self, skill_path: List[str]) -> Set[str]:
        """获取技能栈支持的能力集合（交集）"""
        capabilities = None
        for skill in self.load_skill_stack(skill_path):
            if capabilities is None:
                capabilities = set(skill.capabilities)
            else:
                capabilities &= set(skill.capabilities)
        return capabilities or set()

    def check_capability(self, skill_path: List[str], required: str) -> bool:
        """检查技能栈是否支持某项能力"""
        return required in self.get_capabilities(skill_path)

    def get_keywords(self, skill_path: List[str]) -> Dict:
        """获取技能栈的关键词库（合并）"""
        merged = {}
        for skill in self.load_skill_stack(skill_path):
            for category, kw_map in skill.knowledge.keywords.items():
                if category not in merged:
                    merged[category] = {}
                if isinstance(kw_map, dict):
                    merged[category].update(kw_map)
        return merged

    def get_ontology(self, skill_path: List[str]) -> Dict:
        """获取技能栈的本体知识"""
        merged = {}
        for skill in self.load_skill_stack(skill_path):
            onto = skill.knowledge.ontology
            if isinstance(onto, dict):
                merged.update(onto)
        return merged

    def get_constraints(self, skill_path: List[str]) -> List[str]:
        """获取技能栈的约束条件"""
        merged = []
        seen = set()
        for skill in self.load_skill_stack(skill_path):
            for c in skill.knowledge.constraints:
                if c not in seen:
                    merged.append(c)
                    seen.add(c)
        return merged

    def get_examples(self, skill_path: List[str]) -> List[Dict]:
        """获取技能栈的示例"""
        merged = []
        for skill in self.load_skill_stack(skill_path):
            merged.extend(skill.knowledge.examples)
        return merged

    # ===== 技能树 =====

    @property
    def tree(self) -> SkillTree:
        """懒加载技能树"""
        if self._tree is None:
            tree_path = os.path.join(self._skills_dir, "tree.yaml")
            if os.path.exists(tree_path):
                self._tree = SkillTree.from_yaml(tree_path)
            else:
                logger.warning("Skill tree not found, creating default")
                from .skill_tree import SkillTreeNode
                root = SkillTreeNode(id="root", name="通用技能")
                self._tree = SkillTree(root)
        return self._tree

    def detect_domain(self, user_input: str) -> List[str]:
        """检测用户输入对应的技能树路径（委托给 SkillTree）"""
        return self.tree.detect_domain(user_input, skill_loader=self.load_skill)

    # ===== 缓存管理 =====

    def invalidate_cache(self, skill_id: str = None):
        """清除缓存"""
        if skill_id:
            self._cache.pop(skill_id, None)
        else:
            self._cache.clear()

    def save_skill(self, skill_id: str, skill: SkillBook):
        """保存技能书到 YAML 文件并刷新缓存

        Args:
            skill_id: 技能ID
            skill: SkillBook 对象
        """
        filepath = self._resolve_path(skill_id)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        skill.save(filepath)
        self.invalidate_cache(skill_id)
        logger.info(f"Skill saved: {skill_id} → {filepath}")

    def reload(self):
        """重新加载所有技能书"""
        self.invalidate_cache()
        self._tree = None
        self.load_all_skills()

    def get_cache_stats(self) -> dict:
        return {
            "cached_skills": len(self._cache),
            "skill_ids": list(self._cache.keys()),
        }

    # ===== 内部方法 =====

    def _resolve_path(self, skill_id: str) -> str:
        """将 skill_id 解析为文件路径

        映射规则:
        - "root" / "base" → skills/base.yaml
        - "daily" → skills/daily/skill.yaml
        - "tech.ai.agent" → skills/tech/ai/agent/skill.yaml
        """
        if skill_id in ("root", "base"):
            return os.path.join(self._skills_dir, "base.yaml")

        # 将点号分隔的 ID 转为路径: tech.ai.agent → tech/ai/agent/skill.yaml
        parts = skill_id.split(".")
        dir_path = os.path.join(self._skills_dir, *parts)
        skill_file = os.path.join(dir_path, "skill.yaml")

        if os.path.exists(skill_file):
            return skill_file

        # 也尝试不带子目录的: tech.ai → tech/ai.yaml
        parent_dir = os.path.join(self._skills_dir, *parts[:-1])
        flat_file = os.path.join(parent_dir, f"{parts[-1]}.yaml")
        if os.path.exists(flat_file):
            return flat_file

        return skill_file  # 返回默认路径，调用方会处理不存在


# 全局单例
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """获取全局 SkillManager 单例"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager