"""用户指责/抱怨关键词检测模块 V1.0 (2026-07-30)

用于识别用户对系统回答的不满/指责/抱怨，触发"先道歉再重新思考回答"流程。

触发后系统行为：
1. 在回答开头添加真诚道歉
2. 根据上下文重新认真思考
3. 给出新的、更贴合用户意图的回答

关键词分5类：
- A. 指责理解错误（理解错/不是这个意思）
- B. 指责回答错误（弄错了/给错了）
- C. 指责笨拙/能力差（怎么这么笨/这么简单都不会）
- D. 指责遗忘/重复犯错（不是刚说过吗/又忘了）
- E. 直接要求重答（重新回答/再答一次）
"""
import re
from typing import Tuple, Optional


# ============================================================
# 抱怨关键词字库
# ============================================================
# 每个关键词建议匹配用户原话中的常见口语表达
COMPLAINT_KEYWORDS = {
    # A. 指责理解错误 — 用户认为系统没理解真实意图
    "understanding_error": [
        "你理解错了", "你理解错了我的意思", "理解错了", "理解错了我的意思",
        "不是这个意思", "不是你想的那个", "我要的是这个意思不是你想的那个",
        "我要的不是这个", "我说的不是这个", "不是我想问的",
        "答非所问", "你没理解我", "你根本没理解", "理解能力太差",
        "领会错了", "会错意了", "误会我的意思",
        "我要的是这个不是那个", "我意思是", "我的意思是",
    ],

    # B. 指责回答错误 — 用户认为系统给出了错误内容
    "answer_error": [
        "你这里弄错了", "弄错了", "你弄错了", "这里错了", "给错了",
        "你自己检查了吗为什么给我的还是错误的", "为什么给我的还是错误的",
        "还是错误的", "还是错的", "又错了", "怎么又错了",
        "这个答案不对", "答案是错的", "回答有误", "信息有误",
        "这个不对", "这里不对", "不对", "错的",
        "给的是错的", "你给错了", "你写错了",
    ],

    # C. 指责笨拙/能力差 — 用户对系统能力表达不满
    "capability_complaint": [
        "你怎么这么笨", "怎么这么笨", "这么笨", "笨",
        "我要的这个你怎么都不懂", "你怎么都不懂", "这么简单都不会",
        "这么简单都理解不了", "连这个都不会", "连这都不懂",
        "太差了", "太蠢了", "太笨了", "能力太差",
        "你这水平", "就这能力", "还AI呢", "还不如我自己",
        "你这也不行", "那也不行",
    ],

    # D. 指责遗忘/重复犯错 — 用户认为系统没记住之前的信息
    "repetition_complaint": [
        "我不是刚刚说过了", "不是刚刚说过了", "刚刚不是说过了吗",
        "你怎么又忘了", "又忘了", "不是说了吗", "不是说过吗",
        "我刚才不是说过了吗", "我刚才说过了", "前面不是说过了",
        "你怎么没记住", "没记住", "怎么记不住",
        "又犯同样的错", "又犯了", "老问题",
    ],

    # E. 直接要求重答
    "explicit_redo": [
        "重新回答", "重新答", "再答一次", "重新来过",
        "重新给我答案", "重答", "重新做", "重新写",
        "别这样答", "不要这样回答", "换个方式回答",
    ],
}

# ============================================================
# 抱怨类型 → 道歉话术 + 重答指引
# ============================================================
COMPLAINT_RESPONSES = {
    "understanding_error": {
        "apology": "非常抱歉，我理解错了您的意思。",
        "guidance": "请允许我重新理解您的真实需求，并根据上下文重新作答。",
    },
    "answer_error": {
        "apology": "非常抱歉，我的回答出现了错误。",
        "guidance": "我重新检查并认真思考后，给出修正的回答。",
    },
    "capability_complaint": {
        "apology": "非常抱歉，我的表现没能达到您的要求，对此我深表歉意。",
        "guidance": "我重新认真思考您的需求，尽力给出更准确的回答。",
    },
    "repetition_complaint": {
        "apology": "非常抱歉，我没有记住您之前提供的信息，这是我的疏忽。",
        "guidance": "我结合之前的对话上下文重新作答，避免再犯同样的错误。",
    },
    "explicit_redo": {
        "apology": "好的，我重新为您回答。",
        "guidance": "我根据上下文重新组织回答，力求更贴合您的需求。",
    },
}


def detect_complaint(user_input: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """检测用户输入是否包含指责/抱怨

    Args:
        user_input: 用户原始输入文本

    Returns:
        tuple: (is_complaint, complaint_type, matched_keyword)
            - is_complaint: 是否检测到抱怨
            - complaint_type: 抱怨类型（understanding_error/answer_error/...）
            - matched_keyword: 命中的关键词（用于日志）
              若未命中，三者分别为 (False, None, None)

    判定规则：
        - 优先级从高到低：A > B > C > D > E
        - 一旦命中某类，立即返回该类（避免多重判定）
        - 大小写不敏感
    """
    if not user_input:
        return False, None, None

    text = user_input.strip()

    # 按优先级依次检测
    for complaint_type, keywords in COMPLAINT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return True, complaint_type, kw

    return False, None, None


def build_apology_prompt(complaint_type: str, conversation_history: str = "") -> str:
    """构建道歉+重答的 system prompt 补充指令

    Args:
        complaint_type: 抱怨类型
        conversation_history: 对话历史（若有，用于提醒系统参考上下文）

    Returns:
        注入到 Writer system prompt 末尾的指令文本
    """
    response = COMPLAINT_RESPONSES.get(complaint_type, COMPLAINT_RESPONSES["explicit_redo"])
    apology = response["apology"]
    guidance = response["guidance"]

    instruction = f"""

## 用户反馈处理（重要）
检测到用户对前一次回答表达了不满（类型：{complaint_type}）。
请在回答时严格遵循以下要求：

1. **先道歉**：回答开头必须以这句话开始（可适当润色但保持诚意）：
   "{apology}"

2. **重新理解上下文**：{guidance}
   - 仔细对照对话历史，找出之前回答中可能偏离用户真实意图的部分
   - 不要简单复述之前的答案，要真正重新思考

3. **给出新的回答**：
   - 紧贴用户真实意图，避免再次理解偏差
   - 内容要具体、准确，避免空洞套话
   - 如不确定用户意图，可在道歉后简短确认"我理解您这次想要的是XXX，对吗？"
"""

    if conversation_history:
        instruction += f"""
4. **对话历史参考**：
{conversation_history}

请在重新作答时充分考虑上述历史信息。
"""

    return instruction
