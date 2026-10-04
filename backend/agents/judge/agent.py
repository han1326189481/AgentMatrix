"""Judge Agent - 基于多维 ReviewReport 的路由决策（Skill Engine V2.1）

V2.1 变更：
- 全维度检查：6个维度（accuracy/professional/completeness/reasoning/structure/actionable）
- 输出 weak_dimensions 供 Result Agent 直接使用，避免重复解析
- 精确 cloud_mode：polish_professional / polish_completeness / polish_reasoning 等

开发指南约束：Judge Agent 标记为 stable，V3 不再新增功能。
Cloud 增强决策由 Cognitive Controller + Skill Gap 检测链路负责，不由 Judge Agent 负责。
"""
import json
import re
import logging
from typing import Dict, Any, List, Tuple
from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from agents.base.utils import safe_json_parse, clamp_score, safe_float

logger = logging.getLogger(__name__)

# 6维度名称映射
DIM_NAMES_CN = {
    "accuracy": "准确性",
    "professional": "专业性",
    "completeness": "完整性",
    "reasoning": "逻辑性",
    "structure": "结构性",
    "actionable": "可执行性",
}


class JudgeAgent(BaseAgent):
    def __init__(self, settings=None):
        super().__init__("judge", "Judge Agent", settings=settings)
        # local_model 由 BaseAgent 从 ModelRegistry 读取，无需在此硬编码（Judge 使用规则引擎）

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"路由决策: {input_data.content[:50]}...")

        try:
            input_data_dict = safe_json_parse(input_data.content)
            user_task = input_data_dict.get("user_task", "")
            review_result = input_data_dict.get("review_result", {})
            writer_output = input_data_dict.get("writer_output", "")

            # V2.4: 读取自学习知识信号（由 WorkflowService 从 Knowledge Agent 透传）
            skill_graph_used = bool(input_data_dict.get("skill_graph_used", False))
            skill_graph_contents = input_data_dict.get("skill_graph_contents", []) or []

            # V2.4: 检测 Writer 回答是否基于自学习知识库
            #   方法: 对每条 skill_graph_content 提取关键片段（节点名 + 描述前 50 字），
            #         检查是否在 writer_output 中出现（不区分大小写）。
            #   信任加成: 若检测到引用，Judge 质量补救兜底阈值从 0.50 降到 0.40，
            #          因为自学习知识已通过 knowledge_auditor 审计为权威百科来源，可信度更高。
            used_skill_graph = False
            if skill_graph_used and skill_graph_contents and writer_output:
                used_skill_graph = self._detect_skill_graph_usage(writer_output, skill_graph_contents)

            # V2.1: 提取弱维度 + 全维度决策
            weak_dimensions = self._extract_weak_dimensions(review_result)
            judge_result = self._make_routing_decision_v2(
                user_task, review_result, writer_output, weak_dimensions,
                used_skill_graph=used_skill_graph
            )

            await self._set_status("idle")
            await self._set_current_task(None)

            executed_locally = judge_result["decision"] == "local_output"

            logger.info(
                f"Judge Agent V2.4 - Decision: {judge_result['decision']}, "
                f"difficulty: {judge_result['difficulty_threshold']:.2f}, "
                f"score: {judge_result['review_score']:.2f}, "
                f"cloud_mode: {judge_result['cloud_mode']}, "
                f"risk: {judge_result.get('risk_level', 'low')}, "
                f"weak_dims: {[d['name'] for d in weak_dimensions]}, "
                f"used_skill_graph: {used_skill_graph}"
            )

            return AgentOutput(
                content=json.dumps(judge_result, ensure_ascii=False),
                success=True,
                message=judge_result["decision"],
                metadata={
                    "difficulty_threshold": judge_result["difficulty_threshold"],
                    "review_score": judge_result["review_score"],
                    "decision": judge_result["decision"],
                    "cloud_mode": judge_result["cloud_mode"],
                    "executed_locally": executed_locally,
                    "model_used": "rule-engine",
                    "reason": judge_result.get("reason", []),
                    "risk_level": judge_result.get("risk_level", "low"),
                    "weak_dimensions": weak_dimensions,
                    # V2.4: 自学习知识信任加成信号
                    "used_skill_graph": used_skill_graph,
                },
                model_used="rule-engine"
            )

        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(content="", success=False, message=str(e))

    @staticmethod
    def _count_complexity_signals(user_task: str) -> int:
        """统计用户输入中强复杂度信号词的数量

        用于校正 LLM 评审路径偏低的 difficulty_threshold。
        信号词来源：agents/base/utils.py 的 _COMPLEXITY_SIGNALS
        """
        from agents.base.utils import _COMPLEXITY_SIGNALS
        if not user_task:
            return 0
        count = 0
        for signal in _COMPLEXITY_SIGNALS:
            if signal in user_task:
                count += 1
        return count

    @staticmethod
    def _detect_skill_graph_usage(writer_output: str, skill_graph_contents: List[str]) -> bool:
        """V2.4: 检测 Writer 回答是否基于自学习知识库

        策略（轻量级，零 LLM）:
        1. 对每条 skill_graph_content，提取关键片段：
           - 节点名（"[自学习知识] X:" 中的 X）
           - 描述前 40 字符（去除前缀后的前缀片段）
        2. 检查关键片段是否在 writer_output 中出现（不区分大小写）
        3. 命中任一关键片段（长度 >= 4）即判定为"基于自学习知识"

        Args:
            writer_output: Writer Agent 的输出文本
            skill_graph_contents: Knowledge Agent 注入的自学习知识 content 列表

        Returns:
            True 若检测到 Writer 引用了自学习知识
        """
        if not writer_output or not skill_graph_contents:
            return False

        writer_lower = writer_output.lower()
        import re

        for content in skill_graph_contents:
            if not content or not isinstance(content, str):
                continue
            # 提取节点名: "[自学习知识] {name}: {desc}" → name
            name_match = re.match(r'\[自学习知识\]\s*(.+?):\s*', content)
            if name_match:
                node_name = name_match.group(1).strip()
                # 节点名长度 >= 4 才作为检测锚点（避免短名误匹配）
                if len(node_name) >= 4 and node_name.lower() in writer_lower:
                    return True
                # 英文节点名（如 Kubernetes、ClusterIP）长度 >= 3 也检测
                if len(node_name) >= 3 and re.match(r'^[A-Za-z]', node_name) and node_name.lower() in writer_lower:
                    return True

            # 提取描述前 40 字符作为关键片段（去除前缀）
            desc = re.sub(r'^\[自学习知识\]\s*.+?:\s*', '', content).strip()
            if len(desc) >= 10:
                # 取描述前 40 字符的连续中文/英文片段作为指纹
                fingerprint = desc[:40]
                # 只用长度 >= 8 的指纹检测，避免短片段误匹配
                if len(fingerprint) >= 8 and fingerprint.lower() in writer_lower:
                    return True

        return False

    def _extract_weak_dimensions(self, review_result: Any) -> List[Dict[str, Any]]:
        """V2.1: 从 ReviewReport 提取弱维度信息

        检查全部6个维度，低于阈值者标记为弱维度。
        支持三种输入格式：
        1. 字符串（JSON）：先解析为 dict
        2. 嵌套格式：review_result["dimensions"]["accuracy"]["score"]
        3. 平铺格式：review_result["accuracy"] = 0.85

        阈值参考：accuracy<0.70 / professional<0.65 / completeness<0.60
                  reasoning<0.60 / structure<0.60 / actionable<0.55
        """
        weak = []
        thresholds = {
            "accuracy": 0.70,
            "professional": 0.65,
            "completeness": 0.60,
            "reasoning": 0.60,
            "structure": 0.60,
            "actionable": 0.55,
        }

        if isinstance(review_result, str):
            review_result = safe_json_parse(review_result)
        if not isinstance(review_result, dict):
            return weak

        dims = review_result.get("dimensions", {})
        if dims and isinstance(dims, dict):
            for dim_key, dim_name in DIM_NAMES_CN.items():
                dim_data = dims.get(dim_key, {})
                if isinstance(dim_data, dict):
                    score = safe_float(dim_data.get("score", 0.0))
                else:
                    score = safe_float(dim_data)
                threshold = thresholds.get(dim_key, 0.60)
                if score < threshold:
                    weak.append({
                        "key": dim_key,
                        "name": dim_name,
                        "score": score,
                        "threshold": threshold,
                        "gap": round(threshold - score, 2),
                    })
        else:
            for dim_key, dim_name in DIM_NAMES_CN.items():
                score = safe_float(review_result.get(dim_key, 0.0))
                threshold = thresholds.get(dim_key, 0.60)
                if score < threshold:
                    weak.append({
                        "key": dim_key,
                        "name": dim_name,
                        "score": score,
                        "threshold": threshold,
                        "gap": round(threshold - score, 2),
                    })

        weak.sort(key=lambda x: x["gap"], reverse=True)
        return weak

    def _make_routing_decision_v2(self, user_task: str, review_result: Any,
                                  writer_output: str, weak_dimensions: List[Dict[str, Any]] = None,
                                  used_skill_graph: bool = False) -> Dict[str, Any]:
        """Skill Engine V2.4: 基于难度阈值区间 + 双门槛精确路由 + 质量补救兜底

        决策矩阵（V2.3 — 拓宽本地范围，0.65 归入 full_rewrite 区间）：
        ┌──────────────────┬──────────────────┬─────────────────┬──────────────┐
        │ 难度区间          │ review_score     │ decision        │ cloud_mode   │
        ├──────────────────┼──────────────────┼─────────────────┼──────────────┤
        │ < 0.50           │ 任意             │ local_output    │ none         │
        │ [0.50, 0.65)     │ >= 0.70          │ local_output    │ none         │
        │ [0.50, 0.65)     │ < 0.70           │ cloud_enhance   │ polish_*     │
        │ [0.65, 0.80)     │ >= 0.80          │ local_output    │ none         │
        │ [0.65, 0.80)     │ < 0.80           │ cloud_enhance   │ full_rewrite │
        │ >= 0.80          │ 任意             │ cloud_enhance   │ full_rewrite │
        └──────────────────┴──────────────────┴─────────────────┴──────────────┘

        V2.4 (2026-07-30) 新增 — 质量补救兜底规则（优先级介于 critical 风险与难度区间之间）：
        - review_score < 0.50 且 has_api_key → cloud_enhance (full_rewrite)
          原因: V2.4 将难度与 review_score 解耦后，难度<0.50 区间无条件 local_output，
                导致低质量本地回答（review_score 极低）永远不会被云端补救。
                此兜底规则恢复「本地回答不合格时走云端增强」的设计初衷。
        - 自学习知识信任加成: 若 used_skill_graph=True，兜底阈值从 0.50 降到 0.40。
          原因: 自学习知识已通过 knowledge_auditor 审计为权威百科来源，
                基于它的回答即使评分稍低也值得信任，不必触发云端增强。

        规则：
        - 简单任务 < 0.50 → 本地处理（V2.3 拓宽，原为 < 0.35）
        - 中等难度区间 [0.50, 0.65) 触发 polish_* 局部润色（按 worst 弱维度选择精确模式）
        - 高难度区间 [0.65, 0.80) 触发 full_rewrite 完整重写（0.65 归入此区间）
        - 极高难度 >= 0.80 强制 full_rewrite
        - 风险等级 critical 始终触发 full_rewrite（覆盖难度区间规则）
        - 双门槛机制：中等难度需 review < 0.70 才润色，高难度需 review < 0.80 才重写
        - V2.4 质量补救兜底：review_score < 阈值（0.50 或 0.40）强制 cloud_enhance

        注意：云端增强决策由 Cognitive Controller 的 complexity > 0.7 调度 + Skill Gap 检测链路负责。
        """
        review_data = safe_json_parse(review_result)
        if weak_dimensions is None:
            weak_dimensions = self._extract_weak_dimensions(review_result)

        overall = review_data.get("overall", {})
        risk = review_data.get("risk", {})
        difficulty = review_data.get("difficulty", {})

        difficulty_threshold = safe_float(difficulty.get("threshold", review_data.get("difficulty_threshold", 0.5)))
        weighted_score = safe_float(overall.get("weighted_score", review_data.get("review_score", 0.7)))
        risk_level = risk.get("level", "low")

        # V2.3 难度校正：LLM 评审路径常把高难度问题压回 0.65 边界
        # 通过用户输入的强复杂度信号词数量提升难度档位，确保高难度问题进入正确区间
        # 规则：信号词 >= 2 → 提升至 0.70（进入 full_rewrite 区间 [0.65, 0.80)）
        #       信号词 == 1 不再单独触发升级（避免中等难度问题被误判为高难度）
        original_difficulty = difficulty_threshold
        signal_count = self._count_complexity_signals(user_task)
        if signal_count >= 2 and difficulty_threshold < 0.70:
            difficulty_threshold = 0.70

        settings = self._get_settings()
        has_api_key = bool(settings.deepseek_api_key and settings.deepseek_api_key.strip())

        reason = []

        # 记录难度校正（如有发生）
        if difficulty_threshold != original_difficulty:
            reason.append(
                f"难度校正: LLM 原值 {original_difficulty:.2f} → {difficulty_threshold:.2f} "
                f"(强复杂度信号词 {signal_count} 个)"
            )

        # 1. 风险等级 critical → 始终云端完整重写（最高优先级）
        if risk_level == "critical":
            if has_api_key:
                decision = "cloud_enhance"
                cloud_mode = "full_rewrite"
                reason.append(f"风险等级 {risk_level}，云端完整重写")
            else:
                decision = "local_output"
                cloud_mode = "none"
                reason.append(f"风险等级 {risk_level}，但 API Key 未配置，降级本地处理")

        # 1.5 V2.4 质量补救兜底：review_score 极低 → 强制云端完整重写
        #     优先级介于 critical 风险与难度区间之间。
        #     阈值: 默认 0.50；若回答基于自学习知识（已审计）→ 降到 0.40（信任加成）。
        #     原因: V2.4 难度解耦后，难度<0.50 区间无条件 local_output，
        #           但本地回答不合格时仍需云端补救，否则违背「云端增强为补救本地不足」的初衷。
        elif has_api_key and weighted_score < 0.50:
            # 自学习知识信任加成：基于已审计知识的回答，兜底阈值放宽到 0.40
            rescue_threshold = 0.40 if used_skill_graph else 0.50
            if weighted_score < rescue_threshold:
                decision = "cloud_enhance"
                cloud_mode = "full_rewrite"
                if used_skill_graph:
                    reason.append(
                        f"质量补救: 评分 {weighted_score:.2f} < {rescue_threshold:.2f}（自学习知识信任加成），"
                        f"虽基于已审计知识仍需云端完整重写"
                    )
                else:
                    reason.append(
                        f"质量补救: 评分 {weighted_score:.2f} < {rescue_threshold:.2f}，"
                        f"本地回答不合格，强制云端完整重写"
                    )
            else:
                # 评分在 [rescue_threshold, 0.50) 区间：基于自学习知识，信任放行
                decision = "local_output"
                cloud_mode = "none"
                reason.append(
                    f"质量补救评估: 评分 {weighted_score:.2f} ∈ [{rescue_threshold:.2f}, 0.50)，"
                    f"基于自学习知识（已审计），信任本地处理"
                )

        # 2. 简单任务：难度 < 0.50 → 本地处理（V2.3 拓宽，原为 < 0.35）
        elif difficulty_threshold < 0.50:
            decision = "local_output"
            cloud_mode = "none"
            reason.append(f"难度 {difficulty_threshold:.2f} < 0.50，简单任务，本地处理")

        # 3. 中等难度区间 [0.50, 0.65)：双门槛决定是否触发 polish_* 局部润色
        elif difficulty_threshold < 0.65:
            if weighted_score >= 0.70:
                decision = "local_output"
                cloud_mode = "none"
                reason.append(
                    f"难度 {difficulty_threshold:.2f} ∈ [0.50, 0.65)，"
                    f"评分 {weighted_score:.2f} >= 0.70，本地处理"
                )
            elif not has_api_key:
                decision = "local_output"
                cloud_mode = "none"
                reason.append(
                    f"难度 {difficulty_threshold:.2f} ∈ [0.50, 0.65)，"
                    f"需局部润色但 API Key 未配置"
                )
            else:
                decision = "cloud_enhance"
                # 根据最弱维度选择精确 polish 模式
                if weak_dimensions:
                    worst = weak_dimensions[0]
                    cloud_mode = f"polish_{worst['key']}"
                    reason.append(
                        f"难度 {difficulty_threshold:.2f} ∈ [0.50, 0.65)，"
                        f"{worst['name']} {worst['score']:.2f} < {worst['threshold']:.2f}，"
                        f"云端局部润色 (polish_{worst['key']})"
                    )
                else:
                    cloud_mode = "polish"
                    reason.append(
                        f"难度 {difficulty_threshold:.2f} ∈ [0.50, 0.65)，"
                        f"评分 {weighted_score:.2f} < 0.70，云端局部润色"
                    )

        # 4. 高难度区间 [0.65, 0.80)：双门槛决定是否触发 full_rewrite 完整重写
        #    （V2.3 变更：0.65 归入此区间，原为 (0.65, 0.80)）
        elif difficulty_threshold < 0.80:
            if weighted_score >= 0.80:
                decision = "local_output"
                cloud_mode = "none"
                reason.append(
                    f"难度 {difficulty_threshold:.2f} ∈ [0.65, 0.80)，"
                    f"评分 {weighted_score:.2f} >= 0.80，本地处理"
                )
            elif not has_api_key:
                decision = "local_output"
                cloud_mode = "none"
                reason.append(
                    f"难度 {difficulty_threshold:.2f} ∈ [0.65, 0.80)，"
                    f"需完整重写但 API Key 未配置"
                )
            else:
                decision = "cloud_enhance"
                cloud_mode = "full_rewrite"
                weak_info = ""
                if weak_dimensions:
                    worst = weak_dimensions[0]
                    weak_info = f"，主要弱维度: {worst['name']}({worst['score']:.2f})"
                reason.append(
                    f"难度 {difficulty_threshold:.2f} ∈ [0.65, 0.80)，"
                    f"评分 {weighted_score:.2f} < 0.80，云端完整重写{weak_info}"
                )

        # 5. 极高难度 >= 0.80：强制 full_rewrite
        else:
            if has_api_key:
                decision = "cloud_enhance"
                cloud_mode = "full_rewrite"
                reason.append(
                    f"极高难度 {difficulty_threshold:.2f} >= 0.80，强制云端完整重写"
                )
            else:
                decision = "local_output"
                cloud_mode = "none"
                reason.append(
                    f"极高难度 {difficulty_threshold:.2f} >= 0.80，"
                    f"但 API Key 未配置，降级本地处理"
                )

        return {
            "decision": decision,
            "cloud_mode": cloud_mode,
            "difficulty_threshold": round(difficulty_threshold, 2),
            "review_score": round(weighted_score, 2),
            "executed_locally": decision == "local_output",
            "reason": reason,
            "risk_level": risk_level,
            "weak_dimensions": weak_dimensions,
        }