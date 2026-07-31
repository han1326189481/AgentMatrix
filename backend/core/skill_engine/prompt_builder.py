"""
Skill Engine V2 — Prompt 构建器

从 SkillBook 结构化数据构建最终的 System Prompt。
Skill 是数据，Prompt 是产物。
"""

import logging
from typing import List, Dict, Any
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
            sections.append(f"\n# 输出格式")
            sections.append(f"格式: {merged.output.format}")
            if merged.output.sections:
                sections.append(f"章节结构: {' → '.join(merged.output.sections)}")
            if merged.output.max_length:
                sections.append(f"最大长度: {merged.output.max_length} 字符")

        return "\n".join(sections)

    @staticmethod
    def build_agent_prompt(agent_id: str, skill_stack: List[SkillBook], user_input: str,
                           extra_context: Dict[str, Any] = None) -> str:
        """构建 Agent 执行 Prompt（System + User）

        Args:
            agent_id: Agent ID
            skill_stack: 技能栈
            user_input: 用户输入
            extra_context: 额外上下文

        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = PromptBuilder.build_system_prompt(agent_id, skill_stack)

        # 根据 Agent 类型构建不同的 user prompt
        if agent_id == "knowledge":
            user_prompt = f"请分析以下用户需求，提取关键词和任务类型：\n\n{user_input}"
        elif agent_id == "writer":
            user_prompt = f"请根据以下信息生成内容：\n\n{user_input}"
        elif agent_id == "review":
            user_prompt = f"请评审以下内容的质量：\n\n{user_input}"
        elif agent_id == "judge":
            user_prompt = f"请根据以下评审结果做出路由决策：\n\n{user_input}"
        elif agent_id == "result":
            user_prompt = f"请格式化以下最终结果：\n\n{user_input}"
        else:
            user_prompt = user_input

        return system_prompt, user_prompt

    # ===== Review Agent 专用 =====

    @staticmethod
    def build_review_prompt(skill_stack: List[SkillBook], content: str,
                            user_task: str = "") -> str:
        """构建 Review Agent 的评审 Prompt（含领域权重）

        Args:
            skill_stack: 技能栈
            content: 待评审内容
            user_task: 原始用户任务

        Returns:
            评审 Prompt 字符串
        """
        merged = SkillBook.merge(skill_stack)

        weights = merged.scoring.dimensions
        if not weights:
            weights = {
                "accuracy": 0.25,
                "professional": 0.20,
                "completeness": 0.20,
                "reasoning": 0.15,
                "structure": 0.10,
                "actionable": 0.10,
            }

        # 难度矩阵
        diff_matrix = merged.scoring.difficulty_matrix
        diff_matrix_str = ""
        if diff_matrix:
            import yaml
            diff_matrix_str = yaml.dump(diff_matrix, allow_unicode=True, default_flow_style=False)

        prompt = f"""你是 Review Agent，请按以下标准评审内容质量。

## 评审维度及权重
"""
        for dim, weight in weights.items():
            prompt += f"- **{dim}**: 权重 {weight}\n"

        if diff_matrix_str:
            prompt += f"""
## 难度参考矩阵
{diff_matrix_str}
"""

        prompt += f"""
## 用户任务
{user_task[:500] if user_task else "无"}

## 待评审内容
{content[:3000]}

## 输出格式（严格 JSON）
{{
  "dimensions": {{
    "accuracy": {{"score": 0.0, "issues": [], "suggestion": ""}},
    "professional": {{"score": 0.0, "issues": [], "suggestion": ""}},
    "completeness": {{"score": 0.0, "issues": [], "suggestion": ""}},
    "reasoning": {{"score": 0.0, "issues": []}},
    "structure": {{"score": 0.0, "issues": []}},
    "actionable": {{"score": 0.0, "issues": []}}
  }},
  "overall": {{"weighted_score": 0.0, "pass": false}},
  "risk": {{"level": "low", "factors": [], "mitigation": ""}},
  "confidence": 0.0,
  "difficulty": {{"threshold": 0.0, "level": "medium", "reason": ""}}
}}
"""
        return prompt

    # ===== Writer Agent 专用 =====

    @staticmethod
    def build_writer_prompt(skill_stack: List[SkillBook], task: str,
                            knowledge_items: List[str] = None,
                            keywords: List[str] = None,
                            requirements: List[str] = None) -> str:
        """构建 Writer Agent 的写作 Prompt

        Args:
            skill_stack: 技能栈
            task: 用户任务
            knowledge_items: 知识条目
            keywords: 关键词
            requirements: 需求点

        Returns:
            写作 Prompt 字符串
        """
        merged = SkillBook.merge(skill_stack)

        sections = [f"# 写作任务\n{task}"]

        if knowledge_items:
            sections.append("\n# 参考知识")
            for i, item in enumerate(knowledge_items[:5], 1):
                sections.append(f"{i}. {item}")

        if keywords:
            sections.append(f"\n# 关键词\n{', '.join(keywords[:10])}")

        if requirements:
            sections.append("\n# 需求点")
            for r in requirements[:5]:
                sections.append(f"- {r}")

        if merged.knowledge.constraints:
            sections.append("\n# 写作约束")
            for c in merged.knowledge.constraints[:5]:
                sections.append(f"- {c}")

        if merged.output.sections:
            sections.append(f"\n# 建议结构\n{' → '.join(merged.output.sections)}")

        if merged.forbidden:
            sections.append("\n# 避免事项")
            for f in merged.forbidden[:3]:
                sections.append(f"- {f}")

        sections.append("\n请直接输出最终内容，不要添加多余说明。")

        return "\n".join(sections)

    # ===== Knowledge Agent 专用 =====

    @staticmethod
    def build_knowledge_prompt(skill_stack: List[SkillBook], user_input: str) -> str:
        """构建 Knowledge Agent 的分析 Prompt"""
        merged = SkillBook.merge(skill_stack)

        prompt = f"""你是知识检索与需求分析专家。

## 领域上下文
- 当前领域: {merged.meta.name}
- 角色: {merged.role.title}

## 任务
分析以下用户输入，提取关键词、判断任务类型、生成结构化摘要。

## 用户输入
{user_input}

## 可用关键词库（优先匹配）
"""
        for category, kw_map in merged.knowledge.keywords.items():
            if isinstance(kw_map, dict):
                kws = list(kw_map.keys())[:10]
                prompt += f"- {category}: {', '.join(kws)}\n"

        prompt += """
## 输出格式（JSON）
{
  "task": "核心任务描述",
  "keywords": ["关键词1", "关键词2"],
  "knowledge_items": [],
  "task_type": "任务类型",
  "summary": "需求摘要"
}
"""
        return prompt