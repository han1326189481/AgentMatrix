"""Cognitive Controller — 系统调度大脑

职责: 根据任务类型 + 复杂度 + 用户画像，决定启用哪些引擎。
目标: 简单对话 < 50ms，复杂分析 < 200ms。
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PipelineDecision:
    """调度决策"""
    task_type: str
    engines: List[str]           # 要启用的引擎列表
    use_cloud: bool = False      # 是否走云端
    use_learning: bool = False   # 是否触发学习
    use_recommendation: bool = False  # 是否触发推荐
    use_reasoning: bool = False  # 是否注入推理模式
    complexity: float = 0.0
    reason: str = ""             # 决策理由


class CognitiveController:
    """认知调度器

    设计原则:
    - 简单对话只启用 Task + Skill，不启动 Planner/Learning/Cloud
    - 复杂分析启用全部引擎，但 Review/Cloud 仍按需
    - 引擎启用策略可配置，不硬编码
    """

    # 引擎启用策略（可配置）— 严格遵循 V3_DEVELOPMENT_GUIDE.md 第 4.1 节
    #
    # 2026-10-04 回滚说明：
    #   此前本表被一处**未进文档**的 "V3.1" 改动偏离规范——chat 常驻 decomposer，
    #   qa/coding/writing 常驻 decomposer+planner。该改动与三处独立证据冲突：
    #     1. docs/V3_DEVELOPMENT_GUIDE.md:660 / :790（4.4 验收标准「chat 仅 2 引擎」）
    #     2. tests/test_cognitive_controller.py（3 个用例）
    #     3. tests/test_v3_integration.py（2 个用例）
    #   且它使对外承诺的「简单对话 < 50ms」失效（chat 引擎 2→3，预期延迟 <50ms→<100ms）。
    #   现恢复为规范定义：decomposer/planner 只由 complexity>0.5 触发；
    #   planning/analysis 因本身即需拆解，始终包含两者。
    ENGINE_POLICIES = {
        # task_type: [always_enabled, optional]
        "chat":      (["task", "skill"], []),
        "qa":        (["task", "skill", "decomposer"], ["learning", "recommendation"]),
        "coding":    (["task", "skill"], ["decomposer"]),
        "writing":   (["task", "skill"], ["decomposer", "learning"]),
        "planning":  (["task", "skill", "decomposer", "planner"],
                      ["learning", "recommendation", "reasoning", "cloud"]),
        "analysis":  (["task", "skill", "decomposer", "planner"],
                      ["learning", "reasoning", "cloud"]),
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        # 实例级策略拷贝，避免类级别共享污染
        self.engine_policies = dict(self.ENGINE_POLICIES)
        if "engine_policies" in self.config:
            self.engine_policies.update(self.config["engine_policies"])

    def decide(self, task_profile, brain=None) -> PipelineDecision:
        """核心决策方法

        Args:
            task_profile: TaskEngine 的输出（TaskProfile）
            brain: PersonalBrain 实例（可选）

        Returns:
            PipelineDecision: 包含引擎列表和决策理由
        """
        task_type = task_profile.task_type.value
        complexity = getattr(task_profile, 'complexity', 0.0)
        confidence = getattr(task_profile, 'confidence', 0.5)

        always, optional = self.engine_policies.get(
            task_type, (["task", "skill"], []))

        engines = list(always)
        reasons = [f"task_type={task_type}"]

        # 复杂度驱动
        if complexity > 0.5:
            if "decomposer" not in engines:
                engines.append("decomposer")
            if "planner" not in engines:
                engines.append("planner")
            reasons.append(f"complexity={complexity:.2f} > 0.5")

        if complexity > 0.7:
            enabled = []
            if "cloud" in optional:
                engines.append("cloud")
                enabled.append("cloud")
            if "reasoning" in optional:
                engines.append("reasoning")
                enabled.append("reasoning")
            if enabled:
                reasons.append(f"complexity={complexity:.2f} > 0.7, enabling {','.join(enabled)}")
            else:
                reasons.append(f"complexity={complexity:.2f} > 0.7, but no optional engines available for {task_type}")

        # 用户画像驱动
        if brain:
            learning_stage = getattr(brain, 'learning_stage', '') or getattr(getattr(brain, 'profile', None), 'learning_stage', '')
            if learning_stage == "intermediate" and "recommendation" in optional:
                if "recommendation" not in engines:
                    engines.append("recommendation")
                reasons.append("user learning_stage=intermediate")

            if learning_stage == "advanced" and "reasoning" in optional:
                if "reasoning" not in engines:
                    engines.append("reasoning")
                reasons.append("user learning_stage=advanced")

        # 低置信度 → 简化流程
        if confidence < 0.3:
            engines = [e for e in engines if e not in ("decomposer", "planner", "cloud")]
            reasons.append(f"low confidence={confidence:.2f}, simplified pipeline")

        # 学习触发条件
        use_learning = ("learning" in engines or
                        (complexity > 0.4 and "learning" in optional))

        return PipelineDecision(
            task_type=task_type,
            engines=engines,
            use_cloud="cloud" in engines,
            use_learning=use_learning,
            use_recommendation="recommendation" in engines,
            use_reasoning="reasoning" in engines,
            complexity=complexity,
            reason="; ".join(reasons)
        )

    def get_expected_latency(self, decision: PipelineDecision) -> str:
        """预估延迟"""
        engine_count = len(decision.engines)
        if engine_count <= 2:
            return "< 50ms"
        elif engine_count <= 4:
            return "< 100ms"
        elif engine_count <= 6:
            return "< 200ms"
        else:
            return "< 500ms"