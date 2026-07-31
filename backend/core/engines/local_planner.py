"""Local Planner — 基于 Skill Graph 的任务规划器（零 LLM）

策略:
1. 沿 has_part 边遍历，生成步骤序列
2. 无 Graph 匹配时使用通用模板兜底
3. 检测 Skill Gap（计划中是否有 Graph 未覆盖的步骤）
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class LocalPlanner:
    """将复杂任务分解为执行步骤"""

    def __init__(self, graph):
        self.graph = graph

    def plan(self, decomposer_result: dict) -> List[str]:
        """生成任务规划

        Args:
            decomposer_result: Decomposer.decompose() 的输出

        Returns:
            ["需求分析", "模块设计", "通信方案", "Memory设计", "部署方案"]
        """
        steps = []

        # 1. 从 Decomposer 结果中获取 sub_topics
        sub_topics = decomposer_result.get("sub_topics", [])
        if sub_topics:
            steps = [s["node"].name for s in sub_topics]
        else:
            # 2. 回退：搜索主题节点
            topic = decomposer_result.get("topic", "")
            matched = self.graph.search_by_name(topic, top_k=1)
            if matched:
                children = self.graph.get_children(matched[0].id, "has_part")
                steps = [c.name for c in children]

        # 3. 通用模板兜底
        if not steps:
            steps = self._fallback_plan(decomposer_result.get("topic", ""))

        return steps

    def _fallback_plan(self, topic: str) -> List[str]:
        """通用任务拆分兜底（当 SkillGraph 未匹配到子主题时）

        使用用户友好的通用步骤标题，不依赖 topic 拼接，
        避免"具体解释概述与背景"这类不直观的标题。
        """
        return [
            "理解问题与检索知识",
            "分析核心要点",
            "生成详细解答",
            "检查与优化内容",
            "输出最终结果",
        ]

    def detect_skill_gap(self, plan_steps: List[str]) -> List[str]:
        """检测 Skill Gap：哪些步骤在 Graph 中没有对应节点"""
        return [step for step in plan_steps
                if not self.graph.search_by_name(step, top_k=1)]