"""Agent 公共工具函数
提供 JSON 解析、简单对话检测、分数钳位等跨 Agent 复用逻辑。
"""
import json
import re
import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# ============================================================
# JSON 解析
# ============================================================

def safe_json_parse(
    data: Union[str, Dict[str, Any]],
    default: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """安全解析 JSON，支持 str 和 dict 两种输入。

    Args:
        data: 待解析的 JSON 字符串或已为 dict 的对象
        default: 解析失败时返回的默认值（默认为空 dict）

    Returns:
        解析后的 dict，失败时返回 default
    """
    if default is None:
        default = {}

    if isinstance(data, dict):
        return data

    if not isinstance(data, str) or not data.strip():
        return default

    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError) as e:
        logger.debug(f"safe_json_parse failed: {e}, data[:100]={str(data)[:100]}")
        return default


# ============================================================
# 简单对话检测
# ============================================================

# 统一的简单对话模式列表
_SIMPLE_CONVERSATION_PATTERNS = [
    r"^(你好|您好|hi|hello|嗨|hey|早上好|下午好|晚上好)",
    r"^(在吗|在不在|有人吗|你在吗)",
    r"^(你是谁|你叫什么|你的名字|自我介绍|你是什么)",
    r"^(谢谢|感谢|辛苦|多谢|thanks)",
    r"^(天气|心情|无聊|开心|难过|累了|困了|饿了)",
]


def detect_simple_conversation(
    user_task: str,
    min_length_threshold: int = 10,
    output_text: Optional[str] = None,
    output_min_length: int = 200,
) -> bool:
    """检测是否为简单对话/闲聊，跨 Agent 通用。

    Args:
        user_task: 用户输入文本
        min_length_threshold: 文本长度低于此值直接判定为简单对话
        output_text: 可选的输出内容，用于辅助判断（如 Review Agent 场景）
        output_min_length: 输出内容长度低于此值且无结构化标记时判定为简单

    Returns:
        True 表示是简单对话
    """
    task_lower = user_task.strip().lower()

    # 极短文本 → 简单对话
    if len(task_lower) < min_length_threshold:
        return True

    # 模式匹配
    for pattern in _SIMPLE_CONVERSATION_PATTERNS:
        if re.search(pattern, task_lower):
            return True

    # 复杂问题保护：用户输入含强复杂性信号词时，即使输出短也不判定为简单对话
    # （解决"复杂问题 + 短输出"被误判为简单对话的问题）
    if _has_complexity_signal(user_task):
        return False

    # 输出辅助判断（仅当提供了 output_text 时）
    if output_text is not None:
        if len(output_text) < output_min_length and not re.search(
            r"(# |## |一、|二、|1\.|2\.)", output_text
        ):
            return True

    return False


# 强复杂性信号词 — 出现这些词的用户输入绝不判定为简单对话
# 与 review_rules.yaml 的 complex_keywords 互补，这里放"强信号"（短语级）
_COMPLEXITY_SIGNALS = [
    "深度分析", "全面分析", "系统分析", "深入分析", "详细分析",
    "全面评估", "深度评估", "系统评估", "综合评估",
    "系统论述", "详细论述", "深入论述",
    "多维度", "多角度", "多层次", "三个维度", "四个维度", "五个维度",
    "深度对比", "全面对比", "系统对比",
    "发展趋势", "演变", "颠覆性",
    "关键路径", "关键成功因素", "关键因素",
    "成因", "深层原因", "多重原因",
    "系统设计", "顶层设计", "整体方案",
    "治理体系", "治理能力", "智慧城市", "营商环境",
    "学科建设", "产学研", "教学改革",
]


def _has_complexity_signal(text: str) -> bool:
    """检测用户输入是否包含强复杂性信号词"""
    for signal in _COMPLEXITY_SIGNALS:
        if signal in text:
            return True
    return False


# ============================================================
# 分数钳位
# ============================================================

def clamp_score(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """将分数钳位到指定范围。

    Args:
        value: 原始分数值
        min_val: 最小值（默认 0.0）
        max_val: 最大值（默认 1.0）

    Returns:
        钳位后的分数
    """
    return max(min_val, min(max_val, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    """安全转换为 float，失败时返回默认值。

    Args:
        value: 待转换的值
        default: 转换失败时的默认值

    Returns:
        float 值
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default