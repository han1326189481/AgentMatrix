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

    #: 软节流阈值：末尾连续同领域达到该次数即「加权介入」
    #: （原硬开关要求连续 3 次 + 不重启，实际几乎不可触发，见服务层注释）
    REINFORCE_WINDOW = 2
    #: 加权介入时给同领域提示词模板的优先级加成（与子域匹配的 0.05 同量级）
    REINFORCE_BOOST = 0.05

    def __init__(self, skill_graph, brain=None):
        self.skill_graph = skill_graph
        self.brain = brain

    def recommend(self, current_task: str, active_nodes: List[str],
                  limit: int = 5, focus_domain: str = "") -> List[dict]:
        """基于当前上下文推荐知识

        Args:
            current_task: 用户当前问题
            active_nodes: Decomposer 匹配到的 Skill Graph 节点 ID 列表
            limit: 最大推荐数
            focus_domain: 焦点领域（来自 IntentGraph 软节流信号）。
                          非空时同领域模板获得 priority 加成 → 连续关注的领域置顶

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
        template_recs = self.recommend_templates(
            active_nodes, limit=limit, focus_domain=focus_domain
        )
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
                            limit: int = 5,
                            focus_domain: str = "") -> List[dict]:
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

            # IntentGraph 软节流：连续关注的领域，其模板额外加权（置顶）
            focus_boost = 0.0
            tpl_domain = str(
                tpl_node.metadata.get("domain", "") or tpl_node.domain or ""
            )
            if focus_domain and tpl_domain:
                fd, td = focus_domain.lower(), tpl_domain.lower()
                if fd == td or fd.startswith(td + ".") or td.startswith(fd + "."):
                    focus_boost = self.REINFORCE_BOOST

            recommendations.append({
                "type": "prompt_template",
                "node": tpl_node.name,
                "node_id": tpl_node.id,
                "reason": reason,
                # 直接匹配的模板 priority 加 boost，确保排在领域无关的高分模板之前
                "priority": min(quality_score + boost + focus_boost, 1.0),
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

    def should_intervene(self, intent_graph=None, current_domain: str = "") -> bool:
        """IntentGraph 驱动的**软节流信号**（非硬开关）——图优先

        与旧语义的区别：这里返回 True 不再意味着「才推荐」，而是「加权介入」——
        推荐始终发生（保证首次提问即可见模板），本信号只用于：
          ① 给同领域提示词模板加权置顶
          ② 跳过用户使用模板后的冷却期

        判定条件：
        - IntentGraph 末尾连续同领域提问次数 >= REINFORCE_WINDOW（默认 2）
        - 若给定 current_domain，还要求末尾领域与其同根（跨领域切换 → 不加权）
        """
        if not intent_graph:
            return False
        try:
            run = intent_graph.get_consecutive_domain_run()
        except Exception as e:  # 防御：图实现变更不应打断主流程
            logger.warning(f"KnowledgeRecommendation: 读取 IntentGraph 连续领域失败: {e}")
            return False
        if run < self.REINFORCE_WINDOW:
            return False
        if current_domain:
            tail = intent_graph.records[-1].domain if intent_graph.records else ""
            if not intent_graph.domains_related(tail, current_domain):
                logger.info(
                    f"KnowledgeRecommendation: 领域切换 {tail} → {current_domain}，不加权介入"
                )
                return False
        logger.info(
            f"KnowledgeRecommendation: 连续 {run} 次同领域提问（阈值 {self.REINFORCE_WINDOW}），"
            f"加权介入"
        )
        return True

    def intervention_signal(self, intent_graph=None, current_domain: str = "") -> dict:
        """软节流信号（供服务层消费，不改变「是否推荐」）

        Returns:
            {"level": "reinforce"|"baseline", "consecutive": int,
             "domain": str, "boost": float, "reason": str}
            - reinforce: 连续关注同领域 → domain/boost 生效，冷却期可跳过
            - baseline : 首次或领域切换 → 走正常推荐与冷却
        """
        reinforce = self.should_intervene(intent_graph, current_domain)
        count = 0
        domain = ""
        if intent_graph and getattr(intent_graph, "records", None):
            domain = intent_graph.records[-1].domain or ""
            count = intent_graph.get_consecutive_domain_run()
        return {
            "level": "reinforce" if reinforce else "baseline",
            "consecutive": count,
            "domain": domain if reinforce else "",
            "boost": self.REINFORCE_BOOST if reinforce else 0.0,
            "reason": f"连续 {count} 次关注 {domain} 领域" if reinforce else "",
        }

    def recommend_for_context(self, current_task: str, active_nodes: List[str],
                              intent_graph=None, limit: int = 5) -> dict:
        """完整的上下文推荐（含介入判断）

        Returns:
            {"should_intervene": bool, "recommendations": [...], "reason": str,
             "intent_signal": {...}}
        """
        signal = self.intervention_signal(intent_graph)
        should = signal["level"] == "reinforce"
        recs = (
            self.recommend(current_task, active_nodes, limit,
                           focus_domain=signal["domain"])
            if should else []
        )

        reason = ""
        if should:
            if signal["reason"]:
                reason = f"{signal['reason']}，推荐相关学习内容"
            else:
                reason = "基于当前学习路径推荐"

        return {
            "should_intervene": should,
            "recommendations": recs,
            "reason": reason,
            "total": len(recs),
            "intent_signal": signal,
        }