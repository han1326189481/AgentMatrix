"""Knowledge Recommendation — 基于 Graph Traversal 的精准推荐（零 LLM）

推荐来源（仅四类，不猜测）:
1. 当前任务: has_part 子节点（你正在学 Agent，建议了解 Memory）
2. Goal: 长期目标的 prerequisite 前置知识（你想学 Agent 开发，需要先学 RAG）
3. Capability: 能力图谱的缺口（你理论了解但没实践过的技能）
4. Skill Graph: next_step 学习路径（学完 K8S 推荐学 Service Mesh）
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class KnowledgeRecommendation:
    """知识介入引擎 — 仅基于真实数据推导，不猜测用户意图"""

    def __init__(self, skill_graph, brain=None):
        self.skill_graph = skill_graph
        self.brain = brain

    def recommend(self, current_task: str, active_nodes: List[str],
                  limit: int = 5) -> List[dict]:
        """基于当前上下文推荐知识

        Args:
            current_task: 用户当前问题
            active_nodes: Decomposer 匹配到的 Skill Graph 节点 ID 列表
            limit: 最大推荐数

        Returns:
            [{"type": "sub_topic", "node": "Memory", "node_id": "memory",
              "reason": "...", "priority": 0.8}, ...]
        """
        recommendations = []

        # 1. 当前任务的子主题（has_part）
        for node_id in active_nodes:
            children = self.skill_graph.get_children(node_id, "has_part")
            for child in children:
                if not self._user_has(child.id):
                    recommendations.append({
                        "type": "sub_topic",
                        "node": child.name,
                        "node_id": child.id,
                        "reason": f"当前主题 '{node_id}' 的组成部分",
                        "priority": 0.8
                    })

        # 2. 学习路径下一步（next_step）
        for node_id in active_nodes:
            next_steps = self.skill_graph.get_next_steps(node_id)
            for next_node, weight in next_steps:
                if not self._user_has(next_node.id):
                    recommendations.append({
                        "type": "next_step",
                        "node": next_node.name,
                        "node_id": next_node.id,
                        "reason": f"'{node_id}' 学习路径的下一步",
                        "priority": min(weight, 1.0)
                    })

        # 3. 目标相关的前置知识（priority=0.7，高于capability_gap的0.6）
        if self.brain and self.brain.profile.long_term_goals:
            for goal in self.brain.profile.long_term_goals:
                goal_nodes = self.skill_graph.search_by_name(goal, top_k=1)
                if goal_nodes:
                    prereqs = self.skill_graph.get_prerequisites(goal_nodes[0].id)
                    for prereq in prereqs:
                        if not self._user_has(prereq.id):
                            recommendations.append({
                                "type": "goal_prerequisite",
                                "node": prereq.name,
                                "node_id": prereq.id,
                                "reason": f"长期目标 '{goal}' 的前置知识",
                                "priority": 0.7
                            })

        # 4. 能力缺口（Capability Graph）
        if self.brain:
            gaps = self.brain.capability.get_gaps(self.skill_graph)
            for gap_id in gaps[:5]:
                node = self.skill_graph.get_node(gap_id)
                if node:
                    recommendations.append({
                        "type": "capability_gap",
                        "node": node.name,
                        "node_id": gap_id,
                        "reason": "能力图谱中的缺口",
                        "priority": 0.6
                    })

        # 5. 提示词模板（subdomain_of 反向遍历）
        # 当 active_nodes 包含域/子域节点（如 ppt、ppt.ppt_structure）时，
        # 通过 get_domain_tree 找出其下的所有提示词模板节点。
        # 这一步独立于前4类推荐，专门用于把已收录的 prompt_template 推给 Writer Agent。
        template_recs = self.recommend_templates(active_nodes, limit=limit)
        recommendations.extend(template_recs)

        # 去重 + 按优先级排序
        seen = set()
        unique = []
        for r in recommendations:
            if r["node_id"] not in seen:
                seen.add(r["node_id"])
                unique.append(r)

        return sorted(unique, key=lambda r: r["priority"], reverse=True)[:limit]

    def recommend_templates(self, active_nodes: List[str],
                            limit: int = 5) -> List[dict]:
        """基于 active_nodes 推荐提示词模板节点

        策略:
        1. 若 active_node 本身就是模板节点（node_kind=prompt_template），
           直接加入推荐列表（Decomposer 可能直接匹配到模板节点）
        2. 遍历 active_nodes，对每个节点调用 get_domain_tree(subdomain_of)
           获取其下的模板节点
        3. 若 active_node 是粗域（如 "ppt"），先遍历其 subdomain_of 子节点
           （ppt.ppt_structure 等），再对每个子域获取模板
        4. 仅返回 metadata.node_kind == "prompt_template" 的节点

        Returns:
            [{"type": "prompt_template", "node": "...", "node_id": "ppt_structure_001",
              "reason": "...", "priority": 0.85,
              "template_text": "...", "variables": [...], "intent_tags": [...],
              "quality_score": 0.95, "domain": "ppt.ppt_structure"}, ...]
        """
        recommendations = []
        seen_ids = set()

        def _add_template(tpl_node, reason, boost=0.0):
            """辅助：把模板节点加入推荐列表（去重）

            Args:
                tpl_node: 模板节点
                reason: 推荐理由
                boost: 优先级加成（如直接匹配 = 0.1，子域匹配 = 0.0）
            """
            if tpl_node.id in seen_ids:
                return
            if tpl_node.metadata.get("node_kind") != "prompt_template":
                return
            seen_ids.add(tpl_node.id)
            quality_score = float(tpl_node.metadata.get("quality_score", 0.85))
            recommendations.append({
                "type": "prompt_template",
                "node": tpl_node.name,
                "node_id": tpl_node.id,
                "reason": reason,
                # 直接匹配的模板 priority 加 boost，确保排在领域无关的高分模板之前
                "priority": min(quality_score + boost, 1.0),
                "template_text": tpl_node.metadata.get("template_text", ""),
                "variables": tpl_node.metadata.get("variables", []),
                "intent_tags": tpl_node.metadata.get("intent_tags", []),
                "quality_score": quality_score,
                "domain": tpl_node.metadata.get("domain", "") or tpl_node.domain,
                "difficulty": tpl_node.metadata.get("difficulty", ""),
            })

        for node_id in active_nodes:
            node = self.skill_graph.get_node(node_id)
            if not node:
                continue

            # 策略1: active_node 本身就是模板节点 → 直接加入推荐（最高优先级）
            if node.metadata.get("node_kind") == "prompt_template":
                _add_template(node, "与用户问题直接匹配的提示词模板", boost=0.1)
                continue

            # 策略2: active_node 是子域节点（如 speech.speech_opening）→ 中等优先级
            if node.id.startswith(("ppt.", "speech.")):
                parents_to_scan = [node_id]
                sub_domains = self.skill_graph.get_domain_tree(node_id)
                for sd in sub_domains:
                    if sd.metadata.get("node_kind") != "prompt_template":
                        parents_to_scan.append(sd.id)
                for parent_id in parents_to_scan:
                    templates = self.skill_graph.get_domain_tree(parent_id)
                    for tpl_node in templates:
                        _add_template(tpl_node, f"子域 '{parent_id}' 下的精选提示词模板", boost=0.05)
                continue

            # 策略3: active_node 是粗域节点（如 ppt / speech）→ 普通优先级
            parents_to_scan = [node_id]
            sub_domains = self.skill_graph.get_domain_tree(node_id)
            for sd in sub_domains:
                if sd.metadata.get("node_kind") != "prompt_template":
                    parents_to_scan.append(sd.id)

            # 遍历每个父节点，找出其下的模板节点
            for parent_id in parents_to_scan:
                templates = self.skill_graph.get_domain_tree(parent_id)
                for tpl_node in templates:
                    _add_template(tpl_node, f"领域 '{parent_id}' 下的精选提示词模板")

            if len(recommendations) >= limit:
                break

        return recommendations[:limit]

    def _user_has(self, node_id: str) -> bool:
        """检查用户是否已掌握某技能"""
        if self.brain:
            return self.brain.capability.has(node_id)
        return False

    def should_intervene(self, intent_graph=None) -> bool:
        """判断是否应该介入推荐

        介入条件:
        - 连续3次以上相关领域提问
        - Intent Graph 显示学习路径
        """
        if intent_graph:
            consecutive = intent_graph.get_consecutive_domain(window=3)
            if consecutive:
                logger.info(f"KnowledgeRecommendation: 连续3次 {consecutive} 领域提问，建议介入")
                return True
        return False

    def recommend_for_context(self, current_task: str, active_nodes: List[str],
                              intent_graph=None, limit: int = 5) -> dict:
        """完整的上下文推荐（含介入判断）

        Returns:
            {"should_intervene": bool, "recommendations": [...], "reason": str}
        """
        should = self.should_intervene(intent_graph)
        recs = self.recommend(current_task, active_nodes, limit) if should else []

        reason = ""
        if should:
            if intent_graph:
                consecutive = intent_graph.get_consecutive_domain(window=3)
                if consecutive:
                    reason = f"连续关注 {consecutive} 领域，推荐相关学习内容"
            if not reason:
                reason = "基于当前学习路径推荐"

        return {
            "should_intervene": should,
            "recommendations": recs,
            "reason": reason,
            "total": len(recs)
        }