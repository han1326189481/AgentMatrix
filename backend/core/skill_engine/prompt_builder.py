"""
Skill Engine V2 — Prompt 构建器

从 SkillBook 结构化数据构建最终的 System Prompt。
Skill 是数据，Prompt 是产物。
"""

import logging
from typing import List
from .models import SkillBook

logger = logging.getLogger(__name__)


class PromptBuilder:
    """从 SkillBook 数据构建最终的 System Prompt"""

    # ===== Agent System Prompt =====

    @staticmethod
    def build_system_prompt(agent_id: str, skill_stack: List[SkillBook]) -> str:
        """将技能栈拼接为 LLM 可读的 System Prompt

        Args:
            agent_id: Agent ID（knowledge/writer/review/judge/result）
            skill_stack: 技能栈（从根到叶）

        Returns:
            完整的 System Prompt 字符串
        """
        merged = SkillBook.merge(skill_stack)

        sections = []

        # 1. 角色定义
        if merged.role.title:
            sections.append(f"# 角色\n你是 {merged.role.title}。")
        if merged.role.description:
            sections.append(merged.role.description)

        # 2. 能力声明
        if merged.capabilities:
            caps_str = ", ".join(merged.capabilities)
            sections.append(f"\n# 能力\n你支持以下能力: {caps_str}")

        # 3. 领域知识（本体）
        if merged.knowledge.ontology:
            sections.append("\n# 领域知识")
            onto = merged.knowledge.ontology
            if isinstance(onto, dict):
                for term, info in onto.items():
                    if isinstance(info, dict):
                        definition = info.get("definition", str(info))
                        related = info.get("related", [])
                        sections.append(f"- **{term}**: {definition}")
                        if related:
                            sections.append(f"  相关概念: {', '.join(related)}")
                    else:
                        sections.append(f"- **{term}**: {info}")

        # 4. 写作约束
        if merged.knowledge.constraints:
            sections.append("\n# 约束")
            for c in merged.knowledge.constraints:
                sections.append(f"- {c}")

        # 5. 示例（最多2个）
        if merged.knowledge.examples:
            sections.append("\n# 示例")
            for i, ex in enumerate(merged.knowledge.examples[:2], 1):
                if isinstance(ex, dict):
                    query = ex.get("query", "")
                    structure = ex.get("response_structure", "")
                    sections.append(f"\n## 示例 {i}: {query}")
                    sections.append(structure)

        # 6. 禁止事项
        if merged.forbidden:
            sections.append("\n# 禁止事项")
            for f in merged.forbidden:
                sections.append(f"- {f}")

        # 7. 输出格式
        if merged.output.format:
            sections.append("\n# 输出格式")
            sections.append(f"格式: {merged.output.format}")
            if merged.output.sections:
                sections.append(f"章节结构: {' → '.join(merged.output.sections)}")
            if merged.output.max_length:
                sections.append(f"最大长度: {merged.output.max_length} 字符")

        return "\n".join(sections)
