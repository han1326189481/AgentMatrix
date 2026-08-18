"""CostTracker — 成本追踪模块

职责:
- 记录每次 workflow 的云端 API 和本地模型 token 消耗
- 计算实际成本和本地模型节省金额
- 提供累计统计摘要

使用方式:
    from core.cost_tracker import get_cost_tracker

    tracker = get_cost_tracker()
    tracker.record_workflow(local_tokens={"input": 1200, "output": 800}, cloud_tokens={...})
    summary = tracker.get_summary()
"""

import logging
from typing import Dict, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)

# 定价模型（元/百万token）
DEEPSEEK_INPUT_PRICE = 1.0    # DeepSeek 输入: ¥1/百万token
DEEPSEEK_OUTPUT_PRICE = 4.0   # DeepSeek 输出: ¥4/百万token


class CostTracker:
    """成本追踪器 — 单例模式

    Attributes:
        total_cloud_cost: 累计云端 API 花费（元）
        total_local_savings: 累计本地模型节省（元，即等效云端成本）
        total_cloud_input_tokens: 累计云端输入 token
        total_cloud_output_tokens: 累计云端输出 token
        total_local_input_tokens: 累计本地输入 token
        total_local_output_tokens: 累计本地输出 token
        workflow_count: 总 workflow 执行次数
        local_workflow_count: 本地执行次数
        cloud_workflow_count: 云端增强次数
        recent_costs: 最近 N 次 workflow 的单次成本（用于滚动平均）
    """

    _instance: Optional["CostTracker"] = None

    def __new__(cls) -> "CostTracker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._reset()
        return cls._instance

    def _reset(self):
        """重置所有计数器"""
        self.total_cloud_cost = 0.0
        self.total_local_savings = 0.0
        self.total_cloud_input_tokens = 0
        self.total_cloud_output_tokens = 0
        self.total_local_input_tokens = 0
        self.total_local_output_tokens = 0
        self.workflow_count = 0
        self.local_workflow_count = 0
        self.cloud_workflow_count = 0
        self.recent_costs = deque(maxlen=10)  # 最近 10 次单次成本

        # 此次 workflow 的临时计数
        self._current_cloud_cost = 0.0
        self._current_local_savings = 0.0

    def record_workflow(
        self,
        executed_locally: bool,
        local_tokens: Optional[Dict[str, int]] = None,
        cloud_tokens: Optional[Dict[str, int]] = None,
    ):
        """记录一次 workflow 的 token 消耗

        Args:
            executed_locally: 是否本地执行（False 表示走了云端增强）
            local_tokens: 本地模型 token 消耗 {"input": int, "output": int, "calls": int}
            cloud_tokens: 云端 API token 消耗 {"input": int, "output": int, "calls": int}
        """
        self.workflow_count += 1

        local_tokens = local_tokens or {}
        cloud_tokens = cloud_tokens or {}

        local_input = local_tokens.get("input", 0)
        local_output = local_tokens.get("output", 0)
        cloud_input = cloud_tokens.get("input", 0)
        cloud_output = cloud_tokens.get("output", 0)

        # 累计本地 token
        self.total_local_input_tokens += local_input
        self.total_local_output_tokens += local_output

        # 累计云端 token
        self.total_cloud_input_tokens += cloud_input
        self.total_cloud_output_tokens += cloud_output

        # 计算云端成本
        cloud_cost = self._calc_cost(cloud_input, cloud_output)
        self.total_cloud_cost += cloud_cost
        self._current_cloud_cost = cloud_cost

        # 计算本地节省（等效云端成本）
        local_savings = self._calc_cost(local_input, local_output)
        self.total_local_savings += local_savings
        self._current_local_savings = local_savings

        # 记录单次总成本（云端实际花费 + 本地等效成本）
        total_this_run = cloud_cost + local_savings
        self.recent_costs.append(total_this_run)

        # 执行模式计数
        if executed_locally:
            self.local_workflow_count += 1
        else:
            self.cloud_workflow_count += 1

        logger.info(
            f"[CostTracker] Workflow #{self.workflow_count}: "
            f"local={local_input}+{local_output} tokens (saved ¥{local_savings:.6f}), "
            f"cloud={cloud_input}+{cloud_output} tokens (cost ¥{cloud_cost:.6f}), "
            f"mode={'local' if executed_locally else 'cloud_enhance'}"
        )

    def get_summary(self) -> Dict[str, Any]:
        """获取累计成本摘要

        Returns:
            {
                "estimated_cost": float,           # 实际云端花费（元）
                "estimated_savings": float,         # 本地模型节省（元）
                "total_equivalent_cost": float,     # 如果全部走云端的总成本（元）
                "total_cloud_input_tokens": int,
                "total_cloud_output_tokens": int,
                "total_local_input_tokens": int,
                "total_local_output_tokens": int,
                "workflow_count": int,
                "local_workflow_count": int,
                "cloud_workflow_count": int,
                "avg_cost_per_workflow": float,     # 平均每次 workflow 成本（含等效）
                "savings_rate": float,              # 节省比例（0-1）
            }
        """
        total_equivalent = self.total_cloud_cost + self.total_local_savings
        avg_cost = total_equivalent / self.workflow_count if self.workflow_count > 0 else 0.0
        savings_rate = (
            self.total_local_savings / total_equivalent
            if total_equivalent > 0
            else 0.0
        )

        return {
            "estimated_cost": round(self.total_cloud_cost, 6),
            "estimated_savings": round(self.total_local_savings, 6),
            "total_equivalent_cost": round(total_equivalent, 6),
            "total_cloud_input_tokens": self.total_cloud_input_tokens,
            "total_cloud_output_tokens": self.total_cloud_output_tokens,
            "total_local_input_tokens": self.total_local_input_tokens,
            "total_local_output_tokens": self.total_local_output_tokens,
            "workflow_count": self.workflow_count,
            "local_workflow_count": self.local_workflow_count,
            "cloud_workflow_count": self.cloud_workflow_count,
            "avg_cost_per_workflow": round(avg_cost, 6),
            "savings_rate": round(savings_rate, 4),
        }

    def get_current_workflow_summary(self) -> Dict[str, Any]:
        """获取当前（最近一次）workflow 的成本摘要"""
        return {
            "cloud_cost": round(self._current_cloud_cost, 6),
            "local_savings": round(self._current_local_savings, 6),
        }

    @staticmethod
    def _calc_cost(input_tokens: int, output_tokens: int) -> float:
        """计算 token 消耗对应的成本（元）"""
        cost = (input_tokens / 1_000_000) * DEEPSEEK_INPUT_PRICE + \
               (output_tokens / 1_000_000) * DEEPSEEK_OUTPUT_PRICE
        return round(cost, 6)


def get_cost_tracker() -> CostTracker:
    """获取全局 CostTracker 单例"""
    return CostTracker()


def reset_cost_tracker():
    """重置 CostTracker（用于测试或会话重置）"""
    CostTracker()._reset()