from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any, List
import json
import re

WRITER_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "发言稿": [
        {"title": "开场问候", "content": "向听众问好，介绍自己身份和发言场合。"},
        {"title": "发言主题", "content": "明确本次发言的核心主题和目的。"},
        {"title": "主体内容", "content": "围绕主题分点阐述，包括背景、现状、观点。"},
        {"title": "案例分析", "content": "用具体例子或数据支撑观点。"},
        {"title": "号召或展望", "content": "总结发言，提出呼吁或展望未来。"},
        {"title": "结束致谢", "content": "感谢听众，礼貌结束。"}
    ],
    "竞选稿": [
        {"title": "自我介绍", "content": "介绍个人基本信息、竞选职位。"},
        {"title": "竞选动机", "content": "说明为什么参加竞选，个人优势。"},
        {"title": "工作思路", "content": "如果当选后的具体工作规划和措施。"},
        {"title": "过往成绩", "content": "相关经历和取得的成绩证明能力。"},
        {"title": "承诺与决心", "content": "对选举人的承诺和服务决心。"},
        {"title": "结束语", "content": "感谢聆听，请求支持。"}
    ],
    "工作报告": [
        {"title": "报告概述", "content": "说明报告的时间范围、主题和目的。"},
        {"title": "工作回顾", "content": "按时间或项目梳理完成的主要工作。"},
        {"title": "成果与数据", "content": "用具体数据和成果展示工作成效。"},
        {"title": "问题与不足", "content": "客观分析存在的问题和不足之处。"},
        {"title": "原因分析", "content": "分析问题产生的原因。"},
        {"title": "改进措施", "content": "提出具体的改进方案和措施。"},
        {"title": "下阶段计划", "content": "明确下一步工作重点和时间安排。"}
    ],
    "操作指南": [
        {"title": "概述", "content": "说明本指南的目的、适用范围和前置条件。"},
        {"title": "准备工作", "content": "列出所需工具、材料、环境要求。"},
        {"title": "操作步骤", "content": "按顺序详细描述每个操作步骤，每一步配说明。"},
        {"title": "注意事项", "content": "列出容易出错的地方和安全警示。"},
        {"title": "常见问题", "content": "列出常见问题及解决方法。"},
        {"title": "附录", "content": "相关参考信息、术语解释或快捷方式。"}
    ],
    "策划案": [
        {"title": "项目背景", "content": "说明策划的起因、背景和必要性。"},
        {"title": "策划目标", "content": "明确策划要达成的具体目标。"},
        {"title": "活动/项目方案", "content": "详细描述方案内容、流程和时间安排。"},
        {"title": "资源配置", "content": "列出所需人员、物资、场地等资源。"},
        {"title": "预算规划", "content": "各项费用的预算明细表。"},
        {"title": "风险评估与应对", "content": "识别可能的风险及应急预案。"},
        {"title": "效果评估", "content": "如何评估策划案的执行效果。"}
    ],
    "会议纪要": [
        {"title": "会议基本信息", "content": "记录会议时间、地点、主持人、参会人员。"},
        {"title": "会议议程", "content": "列出会议讨论的主要议题。"},
        {"title": "讨论内容", "content": "逐条记录各议题的讨论要点和意见。"},
        {"title": "决议事项", "content": "明确会议形成的决议和决定。"},
        {"title": "行动项", "content": "列出待办任务、责任人和截止时间。"},
        {"title": "下次会议安排", "content": "下次会议的时间和议题预告。"}
    ],
    "方案设计": [
        {"title": "需求分析", "content": "分析用户需求和痛点。"},
        {"title": "方案目标", "content": "明确方案要达到的目标。"},
        {"title": "方案设计", "content": "详细描述方案的设计思路和架构。"},
        {"title": "实施步骤", "content": "制定实施方案的具体步骤。"},
        {"title": "风险评估", "content": "评估可能遇到的风险和应对措施。"},
        {"title": "预期成果", "content": "描述方案实施后的预期效果。"}
    ],
    "通用任务": [
        {"title": "任务概述", "content": "介绍任务的背景和目标。"},
        {"title": "核心需求", "content": "分析任务的核心需求。"},
        {"title": "解决方案", "content": "提出解决问题的方案。"},
        {"title": "实施计划", "content": "制定实施计划和时间表。"}
    ]
}

TEMPLATE_KEYWORD_MAP = [
    (["发言稿", "演讲稿", "讲话稿", "发言", "致辞", "演讲", "讲话"], "发言稿"),
    (["竞选稿", "竞选", "选举", "竞聘", "参选"], "竞选稿"),
    (["工作报告", "工作汇报", "工作总结", "年终总结", "述职报告", "汇报", "述职"], "工作报告"),
    (["操作指南", "使用指南", "用户手册", "操作手册", "教程", "使用说明", "说明书", "入门指南"], "操作指南"),
    (["策划案", "策划方案", "活动方案", "项目方案", "策划书"], "策划案"),
    (["会议纪要", "会议记录", "会谈纪要", "纪要", "会议"], "会议纪要"),
    (["方案设计", "设计方案", "系统方案", "技术方案", "架构设计"], "方案设计"),
]


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__("writer", "Writer Agent")
        self.local_model = "qwen2.5:1.5b"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"内容生成: {input_data.content[:50]}...")

        try:
            parsed = self._parse_summary(input_data.content)

            if self._detect_simple_conversation(parsed):
                content = await self._generate_simple_response(parsed)
                return AgentOutput(
                    content=content, success=True, message="简单对话完成",
                    metadata={"content_length": len(content), "model_used": self.local_model, "task_type": "简单对话"},
                    model_used=self.local_model
                )

            if self._detect_simple_fact_question(parsed):
                content = await self._generate_fact_answer(parsed)
                return AgentOutput(
                    content=content, success=True, message="知识问答完成",
                    metadata={"content_length": len(content), "model_used": self.local_model, "task_type": "知识问答"},
                    model_used=self.local_model
                )

            task_type = self._determine_task_type(parsed)
            template = WRITER_TEMPLATES.get(task_type, WRITER_TEMPLATES["通用任务"])

            content = await self._generate_with_template_and_llm(parsed, template, task_type)

            await self._set_status("idle")
            await self._set_current_task(None)

            return AgentOutput(
                content=content, success=True, message="内容生成完成",
                metadata={"content_length": len(content), "model_used": self.local_model, "task_type": task_type},
                model_used=self.local_model
            )

        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(content="", success=False, message=str(e))

    def _parse_summary(self, content: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(content)
            return {
                "task": parsed.get("task", ""),
                "original_question": parsed.get("original_question", ""),
                "keywords": parsed.get("keywords", []),
                "knowledge_points": parsed.get("knowledge_points", []),
                "requirements": parsed.get("requirements", []),
                "outline": parsed.get("outline", []),
                "summary": parsed.get("summary", "")
            }
        except:
            return {"task": content, "original_question": content, "keywords": [], "knowledge_points": [],
                    "requirements": [], "outline": [], "summary": content}

    def _detect_simple_conversation(self, parsed: Dict[str, Any]) -> bool:
        task = parsed.get("original_question", parsed.get("task", ""))
        task_lower = task.strip().lower()

        patterns = [
            r"^(你好|您好|hi|hello|嗨|hey|早上好|下午好|晚上好)[\s!！。.,，]*$",
            r"^(在吗|在不在|有人吗|你在吗)[\s!！。.,，]*$",
            r"^(你是谁|你叫什么|你的名字|自我介绍|你是什么)",
            r"^(谢谢|感谢|辛苦|多谢|thanks)[\s!！。.,，]*$",
        ]
        for p in patterns:
            if re.search(p, task_lower):
                return True
        return False

    def _determine_task_type(self, parsed: Dict[str, Any]) -> str:
        task = parsed.get("task", "")
        keywords = parsed.get("keywords", [])
        combined = (task + " " + " ".join(keywords)).lower()

        for patterns, template_name in TEMPLATE_KEYWORD_MAP:
            for pattern in patterns:
                if pattern.lower() in combined:
                    return template_name

        if any(kw in combined for kw in ["活动", "策划", "组织", "赛事", "运动会", "晚会"]):
            return "策划案"
        if any(kw in combined for kw in ["设计", "规划", "系统"]):
            return "方案设计"

        return "通用任务"

    def _build_knowledge_text(self, knowledge_points: List[Dict]) -> str:
        if not knowledge_points:
            return ""
        text = ""
        for i, kp in enumerate(knowledge_points, 1):
            text += f"{i}. {kp.get('content', '')}\n"
        return text

    def _detect_simple_fact_question(self, parsed: Dict[str, Any]) -> bool:
        task = parsed.get("original_question", parsed.get("task", ""))
        task_lower = task.strip().lower()

        knowledge_points = parsed.get("knowledge_points", [])
        if not knowledge_points:
            return False

        fact_patterns = [
            r"^(什么是|什么叫|是什么|是谁|哪一个|哪一种|什么时候|在哪里|多少钱)",
            r"(的定义|的意思|含义|概念)",
            r"^(介绍|简述|概述)",
        ]
        for p in fact_patterns:
            if re.search(p, task_lower):
                return True

        if len(task_lower) < 30 and not any(
            kw in task_lower for kw in ["写", "生成", "策划", "方案", "规划", "设计", "报告", "总结"]
        ):
            return True

        return False

    async def _generate_fact_answer(self, parsed: Dict[str, Any]) -> str:
        task = parsed.get("original_question", parsed.get("task", ""))
        knowledge_points = parsed.get("knowledge_points", [])
        knowledge_text = self._build_knowledge_text(knowledge_points)

        prompt = f"""请根据以下参考知识直接回答用户的问题。

## 用户问题
{task}

## 参考知识（必须严格基于以下知识作答，不要编造）
{knowledge_text}

## 回答要求
1. 直接回答问题，不要跑题
2. 语言简洁准确，像百科条目
3. 使用 Markdown 格式组织，但不要用"任务概述"等模板标题
4. 如果参考知识不够完整，就基于已有知识诚实作答

请直接回答："""

        response = await self._call_llm(prompt, model=self.local_model, use_cloud=False, temperature=0.3, max_tokens=2048)
        return response.strip() if response else task

    async def _generate_simple_response(self, parsed: Dict[str, Any]) -> str:
        task = parsed.get("original_question", parsed.get("task", ""))
        task_lower = task.strip().lower()

        from shared.platform import PLATFORM_IDENTITY

        if re.search(r"(你是谁|你叫什么|你的名字|自我介绍|你是什么)", task_lower):
            prompt = f"""{PLATFORM_IDENTITY.strip()}

用户问："{task}"

请直接以第一人称回复用户。要求：以"我是 AgentMatrix 平台的 AI 助手"开头，简短介绍平台（多智能体协同+国产算力优化，简单任务本地处理，复杂任务云端增强），50-150字，像真人对话，不要标题大纲。"""
        elif re.search(r"(你好|您好|hi|hello|嗨|hey|早上好|下午好|晚上好)", task_lower):
            prompt = f"""用户向你打招呼："{task}"

请友好自然地回复用户，20-60字，像真人对话。不要自我介绍。"""
        else:
            prompt = f"""用户说："{task}"

请友好自然地简短回复，20-60字，像真人对话。"""

        response = await self._call_llm(prompt, model=self.local_model, use_cloud=False, temperature=0.7, max_tokens=256)
        return response.strip() if response else task

    async def _generate_with_template_and_llm(self, parsed: Dict[str, Any],
                                               template: List[Dict[str, str]],
                                               task_type: str) -> str:
        task = parsed.get("task", "")
        original_question = parsed.get("original_question", "")
        keywords = parsed.get("keywords", [])
        knowledge_points = parsed.get("knowledge_points", [])
        requirements = parsed.get("requirements", [])
        outline = parsed.get("outline", [])

        knowledge_text = self._build_knowledge_text(knowledge_points)
        requirements_text = "\n".join(f"- {r}" for r in requirements) if requirements else "无"
        outline_text = "\n".join(f"- {s}" for s in outline) if outline else "无"

        template_str = ""
        for i, section in enumerate(template, 1):
            template_str += f"{i}. **{section['title']}**：{section['content']}\n"

        if knowledge_text:
            prompt = f"""请按以下模板生成一份{task_type}。

## 用户需求
{original_question or task}

## 参考知识（必须基于以下知识作答，不要编造）
{knowledge_text}

## 写作模板
{template_str}

## 关键要求
{requirements_text}

## 输出要求
1. 严格按模板的章节结构组织内容
2. 内容基于参考知识，确保准确专业
3. 每个章节必须充实完整，不能只有一两句话
4. 使用 Markdown 格式：## 二级标题、### 三级标题
5. 直接输出最终文档，不要多余说明

请开始撰写："""
        else:
            prompt = f"""请按以下模板生成一份{task_type}。

## 用户需求
{original_question or task}

## 写作模板
{template_str}

## 关键要求
{requirements_text}

## 参考大纲
{outline_text}

## 关键词
{', '.join(keywords) if keywords else '无'}

## 输出要求
1. 严格按模板的章节结构组织内容
2. 每个章节必须充实完整，不能只有一两句话
3. 使用 Markdown 格式：## 二级标题、### 三级标题
4. 直接输出最终文档，不要多余说明

请开始撰写："""
        response = await self._call_llm(prompt, model=self.local_model, use_cloud=False, temperature=0.3, max_tokens=4096)
        return response if response else f"# {original_question or task}\n\n生成失败，请重试。"
