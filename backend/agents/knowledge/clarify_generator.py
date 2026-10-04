"""抱怨澄清问题生成模块 V1.0 (2026-07-30)

当检测到用户抱怨后，根据抱怨类型和用户输入生成澄清问题，通过 WebSocket
推送到前端弹窗，让用户选择系统理解的方向或自行输入，帮助系统快速定位问题。

问题生成策略：
- 根据抱怨类型（understanding_error/answer_error/capability_complaint/
  repetition_complaint/explicit_redo）选择问题模板
- 每个问题提供2个系统猜测的方向（选项A/B），用户二选一或自行输入
- 问题数量: 2~5 个（根据输入长度和抱怨类型动态调整）
- 优先询问"理解偏差点"，其次询问"期望的输出形式"

推送数据结构:
{
    "questions": [
        {
            "id": "q1",
            "question": "请问您之前想要了解的是哪方面？",
            "options": ["选项A: ...", "选项B: ..."]
        },
        ...
    ],
    "complaint_type": "understanding_error",
    "user_input_summary": "用户输入前80字...",
    "timestamp": "2026-07-30T18:00:00"
}
"""
from datetime import datetime
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 澄清问题模板库（按抱怨类型分组）
# ============================================================
# 每个模板包含:
#   - question: 问题文本
#   - options: 2个猜测方向，{a, b}，a/b 是系统对用户意图的两种猜测
# 选项会根据用户输入内容动态填充（如提取关键词插入选项中）
CLARIFY_TEMPLATES = {
    # A. 指责理解错误 — 用户认为系统没理解真实意图
    "understanding_error": [
        {
            "question": "请问您真正想了解的是以下哪个方向？",
            "options": {
                "a": "我想了解某个具体概念/定义的准确含义",
                "b": "我想了解某个方案/流程的具体实施步骤",
            },
        },
        {
            "question": "我之前的回答偏离了您的真实需求，请问您期望的回答形式是？",
            "options": {
                "a": "简明扼要的要点列表，直击核心",
                "b": "详细完整的分析论述，包含背景和示例",
            },
        },
        {
            "question": "请问之前回答中哪部分让您觉得理解偏差最大？",
            "options": {
                "a": "回答的主题方向就错了（答非所问）",
                "b": "主题对但深度/角度不对（不够深入或偏离重点）",
            },
        },
    ],

    # B. 指责回答错误 — 用户认为系统给出了错误内容
    "answer_error": [
        {
            "question": "请问之前回答中哪类信息有误？",
            "options": {
                "a": "事实性错误（数据/名称/地址/日期等硬信息错误）",
                "b": "逻辑性错误（推理不当/结论错误/因果关系错误）",
            },
        },
        {
            "question": "您希望我如何修正这个错误？",
            "options": {
                "a": "直接给出正确的答案，无需解释错误原因",
                "b": "先说明错误原因，再给出修正后的完整答案",
            },
        },
        {
            "question": "请问您是从哪里发现答案有误的？",
            "options": {
                "a": "我有权威来源（官方文档/专业知识/亲身经历）",
                "b": "通过其他工具/平台交叉验证发现不一致",
            },
        },
    ],

    # C. 指责笨拙/能力差 — 用户对系统能力表达不满
    "capability_complaint": [
        {
            "question": "抱歉让您失望了，请问您期望的回答质量是？",
            "options": {
                "a": "专业级深度（类似专家咨询，含行业洞察）",
                "b": "实用级清晰（直接可用，含具体操作建议）",
            },
        },
        {
            "question": "请问您觉得之前回答最让您不满意的是？",
            "options": {
                "a": "内容太空洞，缺乏具体可执行的信息",
                "b": "理解能力差，没有抓住问题的核心",
            },
        },
    ],

    # D. 指责遗忘/重复犯错 — 用户认为系统没记住之前的信息
    "repetition_complaint": [
        {
            "question": "请问您之前提供的关键信息是哪一类？",
            "options": {
                "a": "背景条件（如身份/场景/约束条件等上下文）",
                "b": "具体需求（如想要的内容形式/侧重点/格式等）",
            },
        },
        {
            "question": "您希望我在重新回答时如何处理之前的信息？",
            "options": {
                "a": "严格沿用之前提供的所有条件，不要遗漏",
                "b": "在之前基础上深化，补充更专业的内容",
            },
        },
    ],

    # E. 直接要求重答
    "explicit_redo": [
        {
            "question": "请问您希望重新回答时重点改进哪方面？",
            "options": {
                "a": "改变回答的角度或立场（换一种思路）",
                "b": "提升内容的深度或详细程度（更专业/更具体）",
            },
        },
        {
            "question": "之前的回答形式您满意吗？希望新的回答是？",
            "options": {
                "a": "保持类似形式但修正内容",
                "b": "换一种形式（如从列表改为论述，或反之）",
            },
        },
    ],
}


def _extract_keywords_from_input(user_input: str, max_keywords: int = 3) -> List[str]:
    """从用户输入中提取关键词，用于动态填充选项

    简单策略：取输入中的名词性短语（这里用简单的分词+长度过滤）
    """
    if not user_input:
        return []

    # 简单分词：按标点和空格切分，取长度2-8的片段作为候选关键词
    import re
    segments = re.split(r'[，。？！,\.\?!；;：:\s\n]+', user_input)
    keywords = []
    for seg in segments:
        seg = seg.strip()
        if 2 <= len(seg) <= 12 and seg not in keywords:
            keywords.append(seg)
        if len(keywords) >= max_keywords:
            break
    return keywords


def generate_clarify_questions(
    complaint_type: str,
    user_input: str,
    conversation_history: str = "",
) -> Dict[str, Any]:
    """生成抱怨澄清问题

    Args:
        complaint_type: 抱怨类型（来自 complaint_keywords.detect_complaint）
        user_input: 用户原始输入
        conversation_history: 对话历史（可选，用于生成更精准的问题）

    Returns:
        推送到前端的澄清请求数据结构:
        {
            "questions": [...],
            "complaint_type": str,
            "user_input_summary": str,
            "timestamp": str
        }
    """
    templates = CLARIFY_TEMPLATES.get(complaint_type, CLARIFY_TEMPLATES["explicit_redo"])

    # 提取关键词，用于动态填充选项
    keywords = _extract_keywords_from_input(user_input, max_keywords=2)

    # 动态调整选项文本（如果有可用关键词）
    questions = []
    for i, tmpl in enumerate(templates, 1):
        opts = {
            "a": tmpl["options"]["a"],
            "b": tmpl["options"]["b"],
        }
        # 如果有提取到关键词，在第一个问题的选项中插入关键词提示
        if i == 1 and keywords:
            kw_hint = keywords[0]
            opts["a"] = f"{opts['a']}（例如：与「{kw_hint}」相关）"

        questions.append({
            "id": f"q{i}",
            "question": tmpl["question"],
            "options": [f"A: {opts['a']}", f"B: {opts['b']}"],
        })

    # 问题数量限制: 2~5 个
    # 根据输入长度动态调整：输入越长，可能需要越多问题
    input_len = len(user_input) if user_input else 0
    if input_len > 300:
        max_questions = 5
    elif input_len > 100:
        max_questions = 4
    else:
        max_questions = 3

    questions = questions[:max_questions]
    # 保证至少2个问题
    if len(questions) < 2:
        # 不足2个时，补充通用问题
        questions.append({
            "id": f"q{len(questions) + 1}",
            "question": "您还有其他需要补充的信息吗？",
            "options": [
                "A: 有，我会在下方输入框补充",
                "B: 没有了，请直接根据上述选择重新回答",
            ],
        })

    # 用户输入摘要（前80字）
    user_input_summary = (user_input or "")[:80]
    if len(user_input or "") > 80:
        user_input_summary += "..."

    result = {
        "questions": questions,
        "complaint_type": complaint_type,
        "user_input_summary": user_input_summary,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(
        f"[ClarifyGenerator] 生成 {len(questions)} 个澄清问题 "
        f"(type={complaint_type}, input_len={input_len})"
    )

    return result
