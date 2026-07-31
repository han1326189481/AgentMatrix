"""Writer Agent - 内容生成专家

使用责任链模式（Chain of Responsibility）处理不同类型的任务：
  SimpleConversation → Polish → FactQuestion → Template(白名单) → CreativeWriting → NormalAnswer(兜底)

每个 Handler 自包含检测+生成逻辑，完全不依赖 WriterAgent 的 _detect_* 方法。

V2.1 变更：
- TemplateHandler 不再作为兜底，仅白名单匹配时触发
- 新增 NormalAnswerHandler 作为最终兜底，自然语言回答
- 模板白名单：方案/计划/报告/策划/总结/会议纪要/需求文档
- 集成 TaskType：Handler 按 TaskProfile 调整行为（min_length、template 标记）

Skill Engine V2 集成：
- execute() 中加载技能栈 → PromptBuilder 构建 System Prompt
- 所有 _generate_* 方法使用 Skill 注入的 System Prompt
"""
import re
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from agents.base.utils import safe_json_parse, detect_simple_conversation
from core.skill_engine.task_engine import TaskType

if TYPE_CHECKING:
    from agents.writer.agent import WriterAgent

logger = logging.getLogger(__name__)

# ============================================================
# Template WhiteList（V2.1 新增）
# ============================================================

TEMPLATE_WHITELIST = [
    "方案", "计划", "报告", "策划", "总结", "会议纪要", "需求文档",
    "设计方案", "技术方案", "系统方案", "架构设计",
    "分析报告", "评估报告", "调研报告", "项目报告",
    "活动方案", "项目方案", "策划方案", "策划书",
    "年度计划", "工作计划", "项目计划", "学习计划",
    "周报", "月报", "年报", "工作总结", "项目总结",
]

# ============================================================
# 模板定义
# ============================================================

WRITER_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    # ---- 校园/活动 ----
    "发言稿": [
        {"title": "开场问候", "content": "向听众问好，介绍自己身份和发言场合。"},
        {"title": "发言主题", "content": "明确本次发言的核心主题和目的。"},
        {"title": "主体内容", "content": "围绕主题分点阐述，包括背景、现状、观点。"},
        {"title": "案例分析", "content": "用具体例子或数据支撑观点。"},
        {"title": "号召或展望", "content": "总结发言，提出呼吁或展望未来。"},
        {"title": "结束致谢", "content": "感谢听众，礼貌结束。"}
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
    "方案设计": [
        {"title": "需求分析", "content": "分析用户需求和痛点。"},
        {"title": "方案目标", "content": "明确方案要达到的目标。"},
        {"title": "方案设计", "content": "详细描述方案的设计思路和架构。"},
        {"title": "实施步骤", "content": "制定实施方案的具体步骤。"},
        {"title": "风险评估", "content": "评估可能遇到的风险和应对措施。"},
        {"title": "预期成果", "content": "描述方案实施后的预期效果。"}
    ],
    "分析报告": [
        {"title": "问题描述", "content": "描述要分析的问题和背景。"},
        {"title": "现状分析", "content": "对当前状况进行深入分析。"},
        {"title": "解决方案", "content": "提出具体的解决方案和建议。"},
        {"title": "实施建议", "content": "给出可操作的实施建议。"}
    ],
    # ---- 商业 ----
    "商业计划书": [
        {"title": "执行摘要", "content": "1-2页概括全局：项目亮点、市场机会、商业模式、财务预测、融资需求。"},
        {"title": "公司概况", "content": "公司使命、愿景、发展历程、核心团队介绍。"},
        {"title": "市场分析", "content": "行业规模、目标客户画像、竞争格局、SWOT分析。"},
        {"title": "产品与服务", "content": "产品功能、核心卖点、技术壁垒、发展规划。"},
        {"title": "商业模式", "content": "收入来源、成本结构、盈利预测、获客方式。"},
        {"title": "营销策略", "content": "推广渠道、定价策略、销售计划、合作伙伴。"},
        {"title": "财务预测", "content": "3-5年收入/成本/利润预测表，关键假设说明。"},
        {"title": "融资需求", "content": "融资金额、估值、资金用途、退出机制。"},
        {"title": "风险与应对", "content": "市场风险、竞争风险、技术风险、财务风险及应对措施。"}
    ],
    "营销方案": [
        {"title": "营销目标", "content": "量化的营销目标（覆盖人数、转化率、销售额等）。"},
        {"title": "目标受众", "content": "受众画像（年龄、性别、收入、兴趣、行为习惯）。"},
        {"title": "核心卖点", "content": "产品/服务的独特卖点和差异化定位。"},
        {"title": "渠道策略", "content": "线上渠道（社交媒体、搜索引擎、内容营销）和线下渠道（活动、地推、合作）。"},
        {"title": "内容策略", "content": "内容类型（文案、视频、图文、直播）、发布频率、话题规划。"},
        {"title": "预算分配", "content": "各渠道预算占比，预期ROI。"},
        {"title": "时间排期", "content": "各阶段任务和时间节点，甘特图形式。"},
        {"title": "效果评估", "content": "关键指标（KPI）和评估方法。"}
    ],
    # ---- 办公 ----
    "会议纪要": [
        {"title": "会议基本信息", "content": "会议主题、时间、地点、主持人、记录人。"},
        {"title": "参会人员", "content": "出席人员、缺席人员、列席人员。"},
        {"title": "会议议程", "content": "逐项列出会议议程和讨论要点。"},
        {"title": "讨论内容", "content": "各方观点摘要，重要发言记录。"},
        {"title": "决议事项", "content": "表决结果、通过的决议，用\u201c会议决定\u201d开头。"},
        {"title": "行动计划", "content": "责任人、具体任务、截止时间、交付物。"},
        {"title": "下次会议", "content": "下次会议时间和议题预告。"}
    ],
    "工作总结": [
        {"title": "工作概述", "content": "时间段、岗位职责、工作范围。"},
        {"title": "主要成果", "content": "按项目或指标分类，用数据量化成果。"},
        {"title": "亮点与创新", "content": "突出贡献和创新做法。"},
        {"title": "问题与不足", "content": "诚实复盘，分析原因。"},
        {"title": "经验教训", "content": "可复用的方法论和改进思路。"},
        {"title": "下阶段计划", "content": "具体目标、行动步骤、时间节点。"},
        {"title": "支持需求", "content": "需要的资源、协调事项。"}
    ],
    "通知公告": [
        {"title": "标题", "content": "关于XXX的通知，简明扼要。"},
        {"title": "正文背景", "content": "发布通知的原因和依据。"},
        {"title": "具体事项", "content": "通知的核心内容，按条列明。"},
        {"title": "执行要求", "content": "相关单位/人员需要做什么、怎么做。"},
        {"title": "时间节点", "content": "起止时间、截止日期。"},
        {"title": "联系方式", "content": "咨询联系人、电话、邮箱。"},
        {"title": "落款", "content": "发布单位、日期、公章。"}
    ],
    "述职报告": [
        {"title": "基本情况", "content": "岗位、任职时间、职责范围。"},
        {"title": "履职情况", "content": "按职责逐项说明，量化成果。"},
        {"title": "重点业绩", "content": "突出贡献和典型案例。"},
        {"title": "能力提升", "content": "学习培训、技能提升、证书获取。"},
        {"title": "存在问题", "content": "自我剖析，坦诚不足。"},
        {"title": "改进措施", "content": "具体可行的改进计划。"},
        {"title": "未来规划", "content": "3-5年职业目标和发展路径。"}
    ],
    "邮件写作": [
        {"title": "主题行", "content": "简明扼要概括邮件目的，不超过15字。"},
        {"title": "称呼", "content": "尊敬的XX/XX总/XX老师。"},
        {"title": "正文开头", "content": "开门见山说明写信目的。"},
        {"title": "正文主体", "content": "分点说明具体事项，逻辑清晰。"},
        {"title": "行动期望", "content": "明确希望收件人做什么（回复/审批/确认）。"},
        {"title": "结尾礼貌语", "content": "感谢/期待回复/祝好。"},
        {"title": "落款", "content": "姓名、职位、联系方式、日期。"}
    ],
    # ---- 政府/公文 ----
    "公文报告": [
        {"title": "标题", "content": "关于XXX的报告/请示/通知，规范格式。"},
        {"title": "主送机关", "content": "收文单位的规范全称。"},
        {"title": "正文引言", "content": "报告/请示的背景和依据。"},
        {"title": "正文主体", "content": "具体事项：工作情况/问题分析/意见建议。"},
        {"title": "结尾用语", "content": "特此报告/妥否请批示/请审阅等规范用语。"},
        {"title": "附件说明", "content": "如有附件，列出名称和数量。"},
        {"title": "落款", "content": "发文机关署名、成文日期、印章。"}
    ],
    "政策解读": [
        {"title": "政策背景", "content": "政策出台的背景和原因。"},
        {"title": "核心内容", "content": "政策的主要规定和要点。"},
        {"title": "政策亮点", "content": "与以往政策的区别和创新之处。"},
        {"title": "影响分析", "content": "对哪些群体有影响，具体影响是什么。"},
        {"title": "落实建议", "content": "如何理解和执行政策，操作步骤。"},
        {"title": "常见问题", "content": "公众关心的热点问题解答。"}
    ],
    # ---- 编码/技术 ----
    "技术文档": [
        {"title": "概述", "content": "项目/系统/功能的简要介绍和背景。"},
        {"title": "技术架构", "content": "整体架构图、核心组件说明。"},
        {"title": "技术选型", "content": "使用的技术栈及其选型理由。"},
        {"title": "详细设计", "content": "模块划分、接口定义、数据模型。"},
        {"title": "部署运维", "content": "部署环境、配置说明、监控方案。"},
        {"title": "API参考", "content": "主要接口的请求/响应格式说明。"},
        {"title": "注意事项", "content": "已知限制、性能指标、安全建议。"}
    ],
    "API文档": [
        {"title": "接口概述", "content": "接口功能说明和适用场景。"},
        {"title": "请求方法", "content": "GET/POST/PUT/DELETE 及请求URL。"},
        {"title": "请求参数", "content": "参数名、类型、必填、说明、示例。"},
        {"title": "响应格式", "content": "响应字段说明和示例JSON。"},
        {"title": "错误码", "content": "错误码、错误信息、解决方法。"},
        {"title": "调用示例", "content": "curl/Python/JavaScript代码示例。"}
    ],
    # ---- 校园专项 ----
    "团课班会": [
        {"title": "活动主题", "content": "团课/班会的主题名称。"},
        {"title": "活动目的", "content": "本次团课/班会的教育目标。"},
        {"title": "主题导入", "content": "开场方式：视频、案例、故事、问题（5-10分钟）。"},
        {"title": "主体环节", "content": "讨论、分享、互动、游戏等活动设计（30-40分钟）。"},
        {"title": "知识讲解", "content": "核心知识点和理论内容。"},
        {"title": "互动讨论", "content": "讨论题目、分组方式、发言规则。"},
        {"title": "总结升华", "content": "活动总结、价值升华、布置实践任务（5-10分钟）。"}
    ],
    "志愿服务": [
        {"title": "服务背景", "content": "志愿服务的背景和意义。"},
        {"title": "服务目标", "content": "本次志愿服务要达成的具体目标。"},
        {"title": "服务内容", "content": "具体服务项目、服务对象、服务方式。"},
        {"title": "人员安排", "content": "志愿者招募、培训、分组、分工。"},
        {"title": "时间计划", "content": "服务时间、频次、周期。"},
        {"title": "物资准备", "content": "所需物资、装备、宣传材料。"},
        {"title": "注意事项", "content": "安全须知、礼仪规范、应急预案。"}
    ],
    "学术论文": [
        {"title": "摘要", "content": "研究目的、方法、结果、结论，200-300字。"},
        {"title": "引言", "content": "研究背景、文献综述、研究问题、论文结构。"},
        {"title": "文献综述", "content": "国内外研究现状、研究空白、本文贡献。"},
        {"title": "研究方法", "content": "数据来源、变量定义、模型设定。"},
        {"title": "实证分析", "content": "描述性统计、回归结果、稳健性检验。"},
        {"title": "结论与建议", "content": "主要发现、政策建议、研究局限、未来方向。"},
        {"title": "参考文献", "content": "按GB/T 7714格式列出引用文献。"}
    ],
    "报名申请": [
        {"title": "基本信息", "content": "姓名、学号/工号、班级/部门、联系方式。"},
        {"title": "申请项目", "content": "申请的具体项目或职位。"},
        {"title": "个人简介", "content": "个人特长、相关经历、获奖情况。"},
        {"title": "申请理由", "content": "为什么申请、自身优势、预期贡献。"},
        {"title": "工作设想", "content": "如果入选后的工作计划或目标。"},
        {"title": "附件清单", "content": "相关证明材料清单。"}
    ],
    # ---- 通用 ----
    "教程指南": [
        {"title": "概述", "content": "本教程的目标、适用人群、前置知识。"},
        {"title": "环境准备", "content": "所需工具、软件、账号等准备工作。"},
        {"title": "步骤一", "content": "第一步操作，含截图或代码示例。"},
        {"title": "步骤二", "content": "第二步操作，含截图或代码示例。"},
        {"title": "步骤三", "content": "第三步操作，含截图或代码示例。"},
        {"title": "常见问题", "content": "FAQ、常见错误和解决方法。"},
        {"title": "总结", "content": "内容回顾和进阶学习建议。"}
    ],
    "PPT大纲": [
        {"title": "封面设计", "content": "标题、副标题、汇报人、日期、单位标识。"},
        {"title": "目录导航", "content": "章节标题和页码，展示整体结构。"},
        {"title": "背景介绍", "content": "项目背景、问题陈述、目标说明。"},
        {"title": "核心内容-Page1", "content": "第一个核心观点，配图表和数据。"},
        {"title": "核心内容-Page2", "content": "第二个核心观点，配案例和分析。"},
        {"title": "核心内容-Page3", "content": "第三个核心观点，配方案和建议。"},
        {"title": "总结与展望", "content": "核心结论回顾、下一步计划、致谢。"}
    ],
    "通用任务": [
        {"title": "任务概述", "content": "介绍任务的背景和目标。"},
        {"title": "核心需求", "content": "分析任务的核心需求。"},
        {"title": "解决方案", "content": "提出解决问题的方案。"},
        {"title": "实施计划", "content": "制定实施计划和时间表。"}
    ]
}

TEMPLATE_KEYWORD_MAP = [
    # 校园/活动
    (["发言稿", "演讲稿", "讲话稿", "发言", "致辞", "演讲", "讲话", "国旗下讲话"], "发言稿"),
    (["策划案", "策划方案", "活动方案", "项目方案", "策划书", "策划", "活动策划", "方案策划"], "策划案"),
    (["方案设计", "设计方案", "系统方案", "技术方案", "架构设计", "架构方案", "方案"], "方案设计"),
    (["分析报告", "报告", "分析", "评估报告", "调研报告", "调查报告"], "分析报告"),
    (["团课", "班会", "主题班会", "主题团课", "团日活动", "团课方案", "班会方案"], "团课班会"),
    (["志愿者", "志愿服务", "志愿活动", "志愿方案", "义工", "支教", "公益活动"], "志愿服务"),
    (["学术论文", "论文", "毕业论文", "学术文章", "课程论文", "期刊论文"], "学术论文"),
    (["报名", "申请", "报名表", "申请表", "申请书", "招新报名", "入会申请"], "报名申请"),
    # 商业
    (["商业计划", "商业计划书", "BP", "融资计划", "融资计划书", "创业计划", "创业计划书"], "商业计划书"),
    (["营销方案", "营销计划", "推广方案", "市场方案", "营销策略", "推广计划", "运营方案"], "营销方案"),
    # 办公
    (["会议纪要", "会议记录", "会议总结", "纪要", "会议"], "会议纪要"),
    (["工作总结", "年终总结", "年度总结", "季度总结", "总结", "工作汇报", "汇报"], "工作总结"),
    (["通知", "公告", "通报", "通知公告", "通告", "告示"], "通知公告"),
    (["述职", "述职报告", "述职汇报", "履职报告", "转正述职"], "述职报告"),
    (["邮件", "email", "邮件模板", "写信", "邮件写作", "商务邮件"], "邮件写作"),
    # 政府/公文
    (["公文", "红头文件", "请示", "批复", "函", "政府文件", "行政公文"], "公文报告"),
    (["政策解读", "政策分析", "政策说明", "政策问答", "政策宣传"], "政策解读"),
    # 编码/技术
    (["技术文档", "开发文档", "技术说明", "接口文档", "技术方案文档", "设计文档"], "技术文档"),
    (["API", "接口", "API文档", "接口说明", "API说明", "Swagger"], "API文档"),
    # 通用
    (["教程", "指南", "指导", "教程文档", "使用指南", "操作指南", "入门教程"], "教程指南"),
    (["PPT", "幻灯片", "演示文稿", "PPT大纲", "PPT制作", "演示", "汇报PPT"], "PPT大纲"),
]


# ============================================================
# 责任链模式 - 任务处理器（每个 Handler 自包含 can_handle + handle）
# ============================================================

class TaskHandler:
    """责任链基类：每个处理器自行判断是否匹配，无法处理则传递给下一个"""

    def __init__(self, agent: 'WriterAgent', name: str):
        self.agent = agent
        self.name = name
        self._next: Optional['TaskHandler'] = None

    def set_next(self, handler: 'TaskHandler') -> 'TaskHandler':
        """设置下一个处理器，返回 handler 以支持链式调用"""
        self._next = handler
        return handler

    def can_handle(self, parsed: Dict[str, Any]) -> bool:
        """子类实现：判断当前处理器是否能处理该任务"""
        raise NotImplementedError

    async def handle(self, parsed: Dict[str, Any]) -> Optional[AgentOutput]:
        """尝试处理任务，若无法处理则传递给下一个处理器"""
        if self.can_handle(parsed):
            return await self._do_handle(parsed)
        if self._next:
            return await self._next.handle(parsed)
        return None

    async def _do_handle(self, parsed: Dict[str, Any]) -> AgentOutput:
        """子类实现：执行实际处理逻辑"""
        raise NotImplementedError


# ============================================================
# 具体处理器
# ============================================================

class SimpleConversationHandler(TaskHandler):
    """简单对话处理器：问候、自我介绍、闲聊等"""

    def __init__(self, agent: 'WriterAgent'):
        super().__init__(agent, "简单对话")

    def can_handle(self, parsed: Dict[str, Any]) -> bool:
        task = parsed.get("original_question", "")
        return detect_simple_conversation(task)

    async def _do_handle(self, parsed: Dict[str, Any]) -> AgentOutput:
        # V2.1: 从 TaskProfile 获取 min_length 建议
        task_data = parsed.get("task_data", {})
        min_length = task_data.get("min_length", 40)
        content = await self.agent._generate_simple_response(parsed, min_length)
        return AgentOutput(
            content=content, success=True, message="简单对话完成",
            metadata={"content_length": len(content), "model_used": self.agent.local_model, "task_type": "简单对话"},
            model_used=self.agent.local_model
        )


class PolishRequestHandler(TaskHandler):
    """润色/改写请求处理器

    检测策略：两级判断
    1. 先排除创作意图关键词（写一篇/设计/策划等），避免误判
    2. 再匹配强润色模式（润色以下/帮我润色等）
    """

    # 强创作意图关键词 — 如果请求主要目的是"创作/生成"，则不是润色
    _CREATION_KEYWORDS = [
        "写一篇", "写一个", "写一份", "写一段", "写一首",
        "生成一篇", "生成一个", "生成一份",
        "设计一个", "设计一套", "设计方案", "架构方案",
        "策划方案", "策划一个", "策划一份",
        "撰写", "编写", "创作", "制定",
        "请帮我写", "请写一篇", "请写一个",
        "写个", "来个", "弄个",
    ]

    # 强润色意图模式 — 必须明确表达"润色/修改已有内容"
    _STRONG_POLISH_PATTERNS = [
        "润色以下", "改写以下", "优化以下", "修改以下",
        "帮我润色", "帮我改写", "帮我优化", "帮我修改",
        "请帮我润色", "请帮我改写", "请帮我优化", "请帮我修改",
        "润色一下", "改写一下", "优化一下", "修改一下",
        "帮我改一下", "帮我改改",
        "润色：", "改写：", "优化：", "修改：",
    ]

    # 弱润色关键词 — 仅在请求较短且无创作意图时生效
    _WEAK_POLISH_KEYWORDS = ["润色", "改写", "polish", "rewrite"]

    def __init__(self, agent: 'WriterAgent'):
        super().__init__(agent, "润色改写")

    def can_handle(self, parsed: Dict[str, Any]) -> bool:
        task = parsed.get("original_question", "")
        task_lower = task.strip().lower()

        # 第一级：排除创作意图
        for kw in self._CREATION_KEYWORDS:
            if kw in task_lower:
                return False

        # 第二级：匹配强润色模式
        for pattern in self._STRONG_POLISH_PATTERNS:
            if pattern in task_lower:
                return True

        # 第三级：弱润色关键词
        if any(kw in task_lower for kw in self._WEAK_POLISH_KEYWORDS):
            return True

        return False

    async def _do_handle(self, parsed: Dict[str, Any]) -> AgentOutput:
        content = await self.agent._generate_polish_response(parsed)
        return AgentOutput(
            content=content, success=True, message="润色改写完成",
            metadata={"content_length": len(content), "model_used": self.agent.local_model, "task_type": "润色改写"},
            model_used=self.agent.local_model
        )


class FactQuestionHandler(TaskHandler):
    """知识问答处理器：事实性问题、简洁回答等

    检测策略：
    1. 简洁请求（一句话/简要说明）— 即使没有知识库也命中
    2. 有知识库 + 事实性模式（什么是/的定义等）
    3. 短文本 + 非创作关键词
    """

    _BREVITY_PATTERNS = [
        r"用一句话", r"一句话", r"简要说明", r"简要介绍", r"简短回答",
        r"简单说", r"简单解释", r"概括一下", r"总结一下",
    ]

    _FACT_PATTERNS = [
        r"^(什么是|什么叫|是什么|是谁|哪一个|什么时候|在哪里|多少钱|有哪些)",
        r"(的定义|的意思|含义|概念)",
        r"^(介绍|简述|概述)",
    ]

    _CREATION_KEYWORDS = ["写", "生成", "策划", "方案", "规划", "设计", "报告", "总结", "制作"]

    def __init__(self, agent: 'WriterAgent'):
        super().__init__(agent, "知识问答")

    def can_handle(self, parsed: Dict[str, Any]) -> bool:
        task = parsed.get("original_question", "")
        task_lower = task.strip().lower()
        knowledge_items = parsed.get("knowledge_items", [])

        # 简洁回答请求 — 即使没有知识库也按事实问答处理
        for p in self._BREVITY_PATTERNS:
            if re.search(p, task_lower):
                return True

        # 没有知识库匹配时，不作为事实问答
        if not knowledge_items:
            return False

        # 事实性模式匹配
        for p in self._FACT_PATTERNS:
            if re.search(p, task_lower):
                return True

        # 短文本且非创作类
        if len(task_lower) < 30 and not any(kw in task_lower for kw in self._CREATION_KEYWORDS):
            return True

        return False

    async def _do_handle(self, parsed: Dict[str, Any]) -> AgentOutput:
        content = await self.agent._generate_fact_answer(parsed)
        return AgentOutput(
            content=content, success=True, message="知识问答完成",
            metadata={"content_length": len(content), "model_used": self.agent.local_model, "task_type": "知识问答"},
            model_used=self.agent.local_model
        )


class CreativeWritingHandler(TaskHandler):
    """创意写作处理器：短文/文章/故事/诗歌/邮件/文案等，使用自由生成而非模板

    覆盖场景：
    - 正式写法：写一篇/一个/一首/一段 XXX
    - 非正式写法：写个/来个/弄个/编个 XXX
    - 主题式写法：关于XXX的YYY / XXX主题的YYY
    - 邮件/信件/邀请函等特殊格式
    - 文案/口号/标语等短创意
    """

    _CREATIVE_PATTERNS = [
        # === 正式写法 ===
        r"写一篇.*(?:短文|文章|作文|散文|随笔|故事|小说|诗歌|诗|词|文案|邮件|信件|邀请函|通知|公告|报道|新闻|评论|影评|书评|读后感|观后感)",
        r"写一首", r"写一段.*(?:故事|文字|描述|话|文案)",
        r"写点.*(?:东西|文字|内容|什么)",
        r"写篇", r"写首",
        r"创作一篇", r"创作一首",
        r"帮我写.*(?:短文|文章|故事|诗歌|邮件|信件|邀请函|散文|小说|文案|情书|日记)",
        r"请帮我写.*(?:短文|文章|故事|诗歌|邮件|信件|邀请函|散文|小说|文案)",
        r"请写一篇", r"请写一首",

        # === 非正式写法 ===
        r"(?:写个|来个|弄个|编个).*(?:短文|故事|诗歌|诗|散文|小说|文案|邮件|笑话|段子|情书)",
        r"写个关于", r"来个关于", r"编个关于",
        r"帮我写个", r"帮我写点", r"帮我编个",
        r"写个(?:关于|一个)", r"来个(?:关于|一个)",

        # === 主题式写法 ===
        r"(?:写|来|弄|编|创作).*(?:关于|主题).*(?:的)?(?:短文|故事|散文|诗歌|文章|小说|文案)",
        r"(?:关于|主题).*(?:的)?(?:短文|故事|散文|诗歌|文章).*(?:写|来|帮)",
        r"主题的(?:短文|故事|散文|诗歌|文章|小说|文案)",

        # === 邮件/信件类 ===
        r"写.*(?:一封|一个).*(?:邮件|信件|信|邀请函)",
        r"帮我写.*(?:邮件|信件|邀请函)",
        r"写封",

        # === 其他创意场景 ===
        r"写一句.*(?:文案|广告|口号|标语|slogan)",
        r"写(?:一份|一个).*(?:情书|日记|周记|年终总结|个人简介)",
    ]

    _TEMPLATE_KEYWORDS = ["策划案", "方案", "报告", "分析", "设计", "规划", "评估"]

    def __init__(self, agent: 'WriterAgent'):
        super().__init__(agent, "创意写作")

    def can_handle(self, parsed: Dict[str, Any]) -> bool:
        task = parsed.get("original_question", "")
        task_lower = task.strip().lower()

        # 正则模式匹配
        for p in self._CREATIVE_PATTERNS:
            if re.search(p, task_lower):
                return True

        # 额外判断：用户要求"生动/有感染力"等创意性修饰，且非模板化任务
        if re.search(r"(生动|有感染力|有趣|优美|感人|幽默|风趣|文艺)", task_lower):
            if not any(kw in task_lower for kw in self._TEMPLATE_KEYWORDS):
                return True

        return False

    async def _do_handle(self, parsed: Dict[str, Any]) -> AgentOutput:
        content = await self.agent._generate_creative_writing(parsed)
        return AgentOutput(
            content=content, success=True, message="创意写作完成",
            metadata={"content_length": len(content), "model_used": self.agent.local_model, "task_type": "创意写作"},
            model_used=self.agent.local_model
        )


class TemplateHandler(TaskHandler):
    """模板化内容生成处理器 — V2.1: 仅白名单匹配触发，不作为兜底"""

    def __init__(self, agent: 'WriterAgent'):
        super().__init__(agent, "模板生成")

    def can_handle(self, parsed: Dict[str, Any]) -> bool:
        """V2.1: 白名单匹配 + TaskProfile.template 双重检测
        V2.2: 排除"改进/重写/详细化"类请求（用户对已有内容不满意，要求展开补充）
        """
        # 从多个可能位置获取用户查询
        user_task = (
            parsed.get("user_task") or
            parsed.get("task") or
            parsed.get("original_question") or
            parsed.get("query") or
            ""
        )

        # V2.2: 排除"改进/重写/详细化"类请求
        # 这类请求的特征：用户对已有内容不满意，要求展开/补充/改进
        # 应交给 NormalAnswerHandler 自由生成，而不是套模板
        improvement_patterns = [
            "太草率", "太简单", "太笼统", "不够详细", "不够具体", "不够深入",
            "重新写", "重写", "改进", "完善", "补充", "展开",
            "详细步骤", "具体说明", "具体的时间", "具体的花费", "详细的",
            "写得太", "写的太", "过于简单", "过于笼统",
        ]
        for pattern in improvement_patterns:
            if pattern in user_task:
                logger.info(f"TemplateHandler: 检测到改进请求 '{pattern}' → 跳过模板，交给自然回答")
                return False

        # V2.5 (2026-07-30): 排除"质疑/反馈/纠错"类请求
        # 这类请求的特征：用户对之前的回答提出质疑、纠错、反馈问题
        # 系统应该认真阅读用户反馈并重新思考，而不是套用模板生成新方案
        # 修复场景: 用户说"针对你刚才的方案我提出质疑" → 不应触发"方案"模板
        challenge_patterns = [
            # 质疑类
            "质疑", "提出质疑", "我提出质疑", "表示怀疑", "存疑",
            # 纠错/核实类
            "核实", "查无此", "核对", "发现问题", "不少问题", "存在问题",
            "关键信息", "信息有误", "信息错误", "信息不准确", "信息过时",
            "严重不符", "地址不符", "名称不符", "店名不符",
            "不准确", "不真实", "不可靠", "可信度低", "不建议",
            # 直接指出错误
            "错误", "有误", "过时", "拼凑", "白跑一趟",
            # 上下文引用类（引用之前的回答）
            "针对你刚才的", "针对你的回答", "你之前的", "你刚才说的",
            "你给的", "你写的内容", "这份攻略", "这份方案", "这份报告",
        ]
        for pattern in challenge_patterns:
            if pattern in user_task:
                logger.info(f"TemplateHandler: 检测到质疑/反馈请求 '{pattern}' → 跳过模板，交给自然回答")
                return False

        # V2.5: 超长输入保护 — 超过300字的输入大概率不是简单的"生成方案"请求
        # 真正的方案生成请求通常较短（"帮我写一个活动方案"），而不是贴一篇长文
        # 超长输入往往是用户在详细描述需求、反馈或质疑，应该交给自然回答处理
        if len(user_task) > 300:
            logger.info(f"TemplateHandler: 输入超长({len(user_task)}字) → 跳过模板，交给自然回答")
            return False

        # V2.1: 优先检查 TaskProfile 的 template 标记
        task_data = parsed.get("task_data", {})
        if task_data.get("template", False):
            logger.info(f"TemplateHandler: TaskProfile.template=True → 启用模板")
            return True

        # 白名单关键词匹配
        for keyword in TEMPLATE_WHITELIST:
            if keyword in user_task:
                logger.info(f"TemplateHandler: 白名单匹配 '{keyword}' → 启用模板")
                return True

        return False  # 不在白名单且无 TaskProfile 标记 → 不触发模板

    async def _do_handle(self, parsed: Dict[str, Any]) -> AgentOutput:
        # V2.1: 使用 TemplateEngine 选择模板
        user_task = (
            parsed.get("user_task") or
            parsed.get("task") or
            parsed.get("original_question") or ""
        )
        task_type_v2 = parsed.get("task_type_v2", "planning")
        skill_domain = parsed.get("skill_domain", "business")
        keywords = parsed.get("keywords", [])

        # 尝试从 TemplateEngine 获取模板
        engine = self.agent.template_engine
        template = engine.select_template(
            task_type=task_type_v2,
            domain=skill_domain,
            user_query=user_task,
            keywords=keywords
        )

        # 判断是否使用了通用默认模板（只有4个section的generic模板）
        is_generic_template = (
            template is None or
            template.meta.template_id == "default_business" or
            len(template.sections) <= 4
        )

        if template and not is_generic_template:
            logger.info(f"TemplateHandler: using template '{template.meta.name}' from TemplateEngine")
            content = await self.agent._generate_with_template_engine(
                parsed, template, engine
            )
            task_type = template.meta.name
        else:
            # 回退到旧模板系统（WRITER_TEMPLATES 有更精准的策划案/方案设计等模板）
            task_type = self._determine_task_type(parsed)
            old_template = WRITER_TEMPLATES.get(task_type, WRITER_TEMPLATES["通用任务"])
            logger.info(f"TemplateHandler: using old template '{task_type}' ({len(old_template)} sections)")
            content = await self.agent._generate_with_template(parsed, old_template, task_type)

        return AgentOutput(
            content=content, success=True, message="内容生成完成",
            metadata={"content_length": len(content), "model_used": self.agent.local_model,
                       "task_type": task_type, "template_engine": "V2.1"},
            model_used=self.agent.local_model
        )

    def _determine_task_type(self, parsed: Dict[str, Any]) -> str:
        """根据任务内容确定模板类型"""
        task = parsed.get("task", "")
        keywords = parsed.get("keywords", [])
        combined = (task + " " + " ".join(keywords)).lower()

        for patterns, template_name in TEMPLATE_KEYWORD_MAP:
            for pattern in patterns:
                if pattern.lower() in combined:
                    return template_name

        if any(kw in combined for kw in ["活动", "策划", "组织", "赛事", "运动会", "晚会"]):
            return "策划案"
        if any(kw in combined for kw in ["设计", "规划", "系统", "架构"]):
            return "方案设计"
        if any(kw in combined for kw in ["分析", "报告", "评估"]):
            return "分析报告"

        return "通用任务"


class NormalAnswerHandler(TaskHandler):
    """V2.1: 自然语言回答处理器 — 最终兜底，不使用模板"""

    def __init__(self, agent: 'WriterAgent'):
        super().__init__(agent, "自然对话")

    def can_handle(self, parsed: Dict[str, Any]) -> bool:
        """始终匹配，作为最终兜底"""
        return True

    async def _do_handle(self, parsed: Dict[str, Any]) -> AgentOutput:
        """V2.1: 生成自然语言回答，不使用模板结构"""
        task = parsed.get("user_task", parsed.get("task", ""))
        summary = parsed.get("summary", "")
        keywords = parsed.get("keywords", [])
        # V2.1: 从 TaskProfile 获取 min_length
        task_data = parsed.get("task_data", {})
        min_length = task_data.get("min_length", 40)

        if not task:
            return AgentOutput(
                content="您好，请问有什么可以帮您的？",
                success=True, message="空任务默认回复",
                metadata={"task_type": "chat", "handler": "NormalAnswer"},
                model_used=self.agent.local_model
            )

        prompt = self.agent._build_normal_answer_prompt(task, summary, keywords, min_length)
        content = await self._call_model(prompt)

        return AgentOutput(
            content=content.strip(),
            success=True,
            message="自然语言回答",
            metadata={"task_type": "chat", "handler": "NormalAnswer",
                      "content_length": len(content)},
            model_used=self.agent.local_model
        )

    async def _call_model(self, prompt: str) -> str:
        """调用本地模型"""
        try:
            result = await self.agent._call_local_model(prompt)
            return result
        except Exception as e:
            logger.error(f"NormalAnswerHandler 模型调用失败: {e}")
            return "抱歉，我暂时无法处理这个请求，请稍后再试。"


# ============================================================
# WriterAgent（精简版：仅保留解析 + 生成方法 + 链构建）
# ============================================================

class WriterAgent(BaseAgent):
    def __init__(self, settings=None):
        super().__init__("writer", "Writer Agent", settings=settings)
        # local_model 由 BaseAgent 从 ModelRegistry 读取，无需在此硬编码
        self._handler_chain: Optional[TaskHandler] = None

        # Skill Engine V2 集成
        self._skill_manager = None
        self._prompt_builder = None
        self._template_engine = None
        self._current_skill_stack: List = []
        self._current_skill_path: List[str] = []
        self._current_system_prompt: str = ""

    @property
    def skill_manager(self):
        if self._skill_manager is None:
            from core.skill_engine.skill_manager import get_skill_manager
            self._skill_manager = get_skill_manager()
        return self._skill_manager

    @property
    def prompt_builder(self):
        if self._prompt_builder is None:
            from core.skill_engine.prompt_builder import PromptBuilder
            self._prompt_builder = PromptBuilder()
        return self._prompt_builder

    @property
    def template_engine(self):
        """V2.1: 独立模板引擎（懒加载）"""
        if self._template_engine is None:
            from core.skill_engine.template_engine import get_template_engine
            self._template_engine = get_template_engine()
        return self._template_engine

    def _build_handler_chain(self) -> TaskHandler:
        """构建责任链：简单对话 → 润色 → 知识问答 → 模板(白名单优先) → 创意写作 → 自然回答(兜底)

        V2.1: TemplateHandler 在 CreativeWritingHandler 之前，
        确保白名单匹配的模板请求（方案/报告/计划）优先于创意写作检测。
        """
        if self._handler_chain is None:
            simple = SimpleConversationHandler(self)
            polish = PolishRequestHandler(self)
            fact = FactQuestionHandler(self)
            template = TemplateHandler(self)
            creative = CreativeWritingHandler(self)
            normal = NormalAnswerHandler(self)

            simple.set_next(polish).set_next(fact).set_next(template).set_next(creative).set_next(normal)
            self._handler_chain = simple
        return self._handler_chain

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"内容生成: {input_data.content[:50]}...")

        try:
            parsed = self._parse_knowledge_output(input_data.content)

            # V2.1: 记录 TaskType 信息
            task_type_v2 = parsed.get("task_type_v2", "chat")
            logger.info(f"Writer Agent: TaskType={task_type_v2}, "
                       f"template={parsed.get('task_data', {}).get('template', False)}, "
                       f"min_length={parsed.get('task_data', {}).get('min_length', 'N/A')}")

            # Skill Engine V2: 加载技能栈并构建 System Prompt
            skill_path = parsed.get("skill_path", ["root", "daily"])
            self._current_skill_path = skill_path
            try:
                self._current_skill_stack = self.skill_manager.load_skill_stack(skill_path)
                self._current_system_prompt = self.prompt_builder.build_system_prompt(
                    "writer", self._current_skill_stack
                )
                logger.info(f"Writer Agent 加载技能栈: {skill_path}, "
                           f"能力: {self.skill_manager.get_capabilities(skill_path)}")
            except Exception as e:
                logger.warning(f"Skill Engine 加载失败，回退到模板 Prompt: {e}")
                self._current_system_prompt = self._load_system_prompt()
                self._current_skill_stack = []

            # V3: Reasoning Graph — 推理模式注入
            reasoning_pattern = input_data.context.get("reasoning_pattern") if input_data.context else None
            if reasoning_pattern:
                user_task = parsed.get("original_question", "")
                reasoning_instruction = reasoning_pattern.build_prompt(user_task)
                if self._current_system_prompt:
                    self._current_system_prompt = (
                        self._current_system_prompt + "\n\n## 推理模式指引\n" + reasoning_instruction
                    )
                else:
                    self._current_system_prompt = reasoning_instruction
                logger.info(
                    f"Writer Agent: Reasoning pattern injected: {reasoning_pattern.pattern_name} "
                    f"(id={reasoning_pattern.pattern_id})"
                )

            # V3: Prompt Templates — 提示词模板注入（来自 KnowledgeRecommendation）
            # 当 IntentGraph 检测到连续3次同领域提问时，注入该领域的精选提示词模板
            prompt_templates = input_data.context.get("prompt_templates") if input_data.context else None
            if prompt_templates and isinstance(prompt_templates, list) and prompt_templates:
                template_instruction = self._build_prompt_template_instruction(prompt_templates)
                if template_instruction:
                    if self._current_system_prompt:
                        self._current_system_prompt = (
                            self._current_system_prompt
                            + "\n\n## 精选提示词模板（可参考以提升回答质量）\n"
                            + template_instruction
                        )
                    else:
                        self._current_system_prompt = template_instruction
                    logger.info(
                        f"Writer Agent: Prompt templates injected: "
                        f"{len(prompt_templates)} templates "
                        f"(ids={[t.get('node_id', '') for t in prompt_templates]})"
                    )

            # 上下文记忆：注入对话历史（来自 Knowledge Agent 的 summary）
            conversation_history = parsed.get("conversation_history", "")
            if conversation_history:
                if self._current_system_prompt:
                    self._current_system_prompt = (
                        self._current_system_prompt
                        + "\n\n## 对话历史（请基于此上下文理解用户的指代和跟进问题）\n"
                        + conversation_history
                    )
                else:
                    self._current_system_prompt = "## 对话历史\n" + conversation_history
                logger.info("Writer Agent: 对话历史已注入 system prompt")

            # V3: 注入长期记忆上下文（MemoryStore）
            memory_context = parsed.get("memory_context", "")
            if memory_context and self._current_system_prompt:
                self._current_system_prompt = (
                    self._current_system_prompt
                    + "\n\n## 用户长期记忆（请参考这些信息进行个性化回复）\n"
                    + memory_context
                )
                logger.info("Writer Agent: 长期记忆上下文已注入 system prompt")

            # V3: 注入用户画像上下文（PersonalBrain）
            brain_context = parsed.get("brain_context", "")
            if brain_context and self._current_system_prompt:
                self._current_system_prompt = (
                    self._current_system_prompt
                    + "\n\n## 用户画像（请根据用户身份和偏好调整回复风格）\n"
                    + brain_context
                )
                logger.info("Writer Agent: 用户画像上下文已注入 system prompt")

            # V3.2: 注入视觉识别结果（来自 Knowledge Agent 调用 VisionPlugin）
            # 将 MiniCPM-V 识别出的图片内容（Markdown 格式）注入 system prompt，
            # 让 Writer Agent 在生成回答时能引用图片中的具体信息
            image_descriptions = parsed.get("image_descriptions", [])
            if image_descriptions and self._current_system_prompt:
                # V3.2 修复：同时过滤两种失败前缀
                # - [图片识别失败: ...] 来自 VisionPlugin 单张识别失败
                # - [视觉识别失败: ...] 来自 Knowledge Agent 整体流程失败
                valid_descs = [
                    d for d in image_descriptions
                    if d
                    and not d.startswith("[图片识别失败")
                    and not d.startswith("[视觉识别失败")
                ]
                if valid_descs:
                    # 格式化为带序号的图片内容块，便于 LLM 引用
                    desc_blocks = []
                    for i, desc in enumerate(valid_descs, 1):
                        desc_blocks.append(f"### 图片 {i}\n{desc}")
                    image_context = "\n\n".join(desc_blocks)

                    # M2 修复：限制图片描述注入的总长度，避免 system prompt 过长
                    # 中文 1 字 ≈ 1.5 token，4000 token ≈ 2600 字符
                    # 超过时按图片顺序截断，保留前 N 张完整描述 + 截断提示
                    MAX_IMAGE_CONTEXT_CHARS = 2600  # ≈ 4000 token
                    truncated_count = 0
                    if len(image_context) > MAX_IMAGE_CONTEXT_CHARS:
                        # 逐张累加，直到达到上限
                        kept_blocks = []
                        total_chars = 0
                        for i, desc in enumerate(valid_descs, 1):
                            block = f"### 图片 {i}\n{desc}"
                            if total_chars + len(block) + 2 > MAX_IMAGE_CONTEXT_CHARS:
                                break
                            kept_blocks.append(block)
                            total_chars += len(block) + 2
                            truncated_count += 1
                        # 添加截断提示
                        remaining_count = len(valid_descs) - truncated_count
                        image_context = "\n\n".join(kept_blocks)
                        if remaining_count > 0:
                            image_context += (
                                f"\n\n（注：剩余 {remaining_count} 张图片的描述"
                                f"因长度限制被省略，请优先参考已展示的图片内容）"
                            )
                        logger.warning(
                            f"Writer Agent: 图片描述总长度 {len(image_context)} 超过上限 "
                            f"{MAX_IMAGE_CONTEXT_CHARS}，已截断保留前 {truncated_count} 张"
                        )

                    self._current_system_prompt = (
                        self._current_system_prompt
                        + "\n\n## 用户上传的图片内容（视觉模型识别结果）\n"
                        + "用户上传了 " + str(len(valid_descs)) + " 张图片，"
                        + "以下是视觉模型识别出的图片内容。请在回答中引用图片中的"
                        + "具体信息来回答用户的问题，不要臆测图片中未出现的内容。\n\n"
                        + "## 重要：如果用户要求『提取文字/排版/原样输出/列出所有文字』，"
                        + "请按图片顺序原样输出上方识别到的所有文字内容，"
                        + "用 Markdown 标题（## 图片 1 / ## 图片 2 ...）分隔每张图片，"
                        + "不要概括、不要省略、不要添加解释。\n\n"
                        + image_context
                    )
                    logger.info(
                        f"Writer Agent: 视觉识别结果已注入 system prompt "
                        f"({len(valid_descs)}/{len(image_descriptions)} 张图片有效"
                        + (f", 截断保留前 {truncated_count} 张" if truncated_count > 0 else "")
                        + ")"
                    )
                elif image_descriptions:
                    # V3.2: 全部识别失败时注入简短提示，让 LLM 知道用户上传了图片但识别失败
                    # 避免 LLM 完全不知道有图片存在，无法在回答中提示用户
                    self._current_system_prompt = (
                        self._current_system_prompt
                        + "\n\n## 用户上传的图片（识别失败）\n"
                        + "用户上传了 " + str(len(image_descriptions)) + " 张图片，"
                        + "但视觉模型识别全部失败。请在回答中告知用户图片识别失败，"
                        + "建议重新上传或用文字描述图片内容。"
                    )
                    logger.warning(
                        f"Writer Agent: 全部 {len(image_descriptions)} 张图片识别失败，"
                        f"已注入失败提示"
                    )

            # ============================================================
            # V3.4 (2026-07-30): 用户抱怨处理 — 注入道歉+重答指令
            # ------------------------------------------------------------
            # 检测到用户对前一次回答表达不满时，在 system prompt 末尾追加：
            # 1. 必须先道歉（按抱怨类型使用对应道歉话术）
            # 2. 根据对话历史重新认真思考
            # 3. 给出新的、更贴合用户意图的回答
            # ============================================================
            complaint_type = input_data.context.get("complaint_type") if input_data.context else None
            if complaint_type and self._current_system_prompt:
                try:
                    from agents.knowledge.complaint_keywords import build_apology_prompt
                    conversation_history = parsed.get("conversation_history", "")
                    apology_instruction = build_apology_prompt(complaint_type, conversation_history)
                    self._current_system_prompt = self._current_system_prompt + apology_instruction
                    logger.info(
                        f"Writer Agent: 抱怨处理指令已注入 "
                        f"(type={complaint_type}, keyword="
                        f"'{input_data.context.get('complaint_matched_keyword', '')}')"
                    )
                except ImportError:
                    logger.warning("complaint_keywords 模块未加载，无法注入道歉指令")
                except Exception as e:
                    logger.warning(f"注入抱怨处理指令失败: {e}")

            chain = self._build_handler_chain()
            result = await chain.handle(parsed)

            if result is None:
                result = AgentOutput(content="", success=False, message="所有处理器均未匹配")

            # 追加 skill_path 和 task_type 到 metadata
            if result.metadata:
                result.metadata["skill_path"] = self._current_skill_path
                result.metadata["skill_domain"] = self._current_skill_path[-1] if len(self._current_skill_path) > 1 else "daily"
                result.metadata["task_type_v2"] = task_type_v2
                # V3: 记录推理模式
                if reasoning_pattern:
                    result.metadata["reasoning_pattern"] = reasoning_pattern.pattern_id

            await self._set_status("idle")
            await self._set_current_task(None)
            return result

        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(content="", success=False, message=str(e))

    # ============================================================
    # 解析 & 工具方法
    # ============================================================

    def _parse_knowledge_output(self, content: str) -> Dict[str, Any]:
        """解析 Knowledge Agent 的结构化 JSON 输出"""
        parsed = safe_json_parse(content)
        if parsed:
            # V2.1: 提取 TaskClassifier 数据
            task_data = parsed.get("task_data", {})
            task_type_v2 = parsed.get("task_type_v2", "chat")
            return {
                "task": parsed.get("task", ""),
                "user_task": parsed.get("user_task", parsed.get("task", "")),  # V2.1: 添加 user_task 别名
                "original_question": parsed.get("original_question", ""),
                "keywords": parsed.get("keywords", []),
                "knowledge_items": parsed.get("knowledge_items", []),
                "requirements": parsed.get("requirements", []),
                "outline": parsed.get("outline", []),
                "summary": parsed.get("summary", ""),
                "task_type": parsed.get("task_type", "通用任务"),
                # Skill Engine V2: 提取 skill_path
                "skill_path": parsed.get("skill_path", ["root", "daily"]),
                "skill_domain": parsed.get("skill_domain", "daily"),
                # V2.1: TaskClassifier 输出
                "task_type_v2": task_type_v2,
                "task_data": task_data,
                # 上下文记忆：对话历史（来自 Knowledge Agent）
                "conversation_history": parsed.get("conversation_history", ""),
                # V3: 长期记忆上下文（MemoryStore）和用户画像上下文（PersonalBrain）
                # V3.2 修复：之前 _parse_knowledge_output 遗漏了这两个字段，
                # 导致 Writer Agent 的注入逻辑（第833-851行）从未触发，
                # 系统回答无法参考用户画像和长期记忆
                "memory_context": parsed.get("memory_context", ""),
                "brain_context": parsed.get("brain_context", ""),
                # V3.2: 视觉识别结果（来自 Knowledge Agent 调用 VisionPlugin）
                # List[str]，每项是 MiniCPM-V 对一张图片的 Markdown 描述
                "image_descriptions": parsed.get("image_descriptions", []),
            }
        return {
            "task": content, "user_task": content, "original_question": content,
            "keywords": [], "knowledge_items": [],
            "requirements": [], "outline": [], "summary": content,
            "task_type": "通用任务",
            "skill_path": ["root", "daily"],
            "skill_domain": "daily",
            "task_type_v2": "chat",
            "task_data": {},
            "conversation_history": "",
            "image_descriptions": [],
        }

    def _build_knowledge_text(self, knowledge_items: List) -> str:
        """将知识条目列表格式化为 Writer Prompt 可读的文本

        V2.4 (2026-07-30) 修复: knowledge_items 可能是混合类型列表：
        - MySQL 知识库返回纯字符串
        - Skill Graph 注入的是 dict（含 keyword/content/source/domain 字段）
        旧逻辑直接 f"{item}" 会把 dict 序列化成 Python repr 字符串，
        导致 Writer 看到的是 {'keyword': '...', 'content': '...'} 这种脏字符串，
        既影响生成质量，也使 Judge 检测「是否基于自学习知识」失效。
        修复: 遇到 dict 时提取 content 字段。
        """
        if not knowledge_items:
            return ""
        lines = []
        for i, item in enumerate(knowledge_items, 1):
            if isinstance(item, dict):
                # Skill Graph 注入的 dict 条目，取 content 字段
                content = item.get("content", "") or item.get("keyword", "")
                lines.append(f"{i}. {content}")
            else:
                # MySQL 知识库返回的纯字符串
                lines.append(f"{i}. {item}")
        return "\n".join(lines)

    def _build_prompt_template_instruction(self, templates: List[Dict[str, Any]]) -> str:
        """将提示词模板列表格式化为 Writer Agent 可理解的指引文本

        Args:
            templates: KnowledgeRecommendation 推荐的模板列表，每个元素含
                       node_id, node(title), template_text, variables,
                       intent_tags, quality_score, domain

        Returns:
            格式化的指引文本，注入 system prompt 末尾
        """
        if not templates:
            return ""

        lines = [
            "系统检测到你正在处理用户连续关注的领域，已为你匹配以下精选提示词模板。",
            "请根据用户具体需求选择最匹配的模板，提取其结构与话术思路来提升回答质量。",
            "注意：不要照搬模板变量值（用户未提供时不要编造），只借鉴其结构、维度和话术策略。",
            "",
        ]

        for i, tpl in enumerate(templates, 1):
            title = tpl.get("node", "")
            tpl_id = tpl.get("node_id", "")
            domain = tpl.get("domain", "")
            quality = tpl.get("quality_score", 0.0)
            template_text = tpl.get("template_text", "")
            variables = tpl.get("variables", [])
            intent_tags = tpl.get("intent_tags", [])

            lines.append(f"### 模板 {i}: {title}")
            lines.append(f"- 模板ID: {tpl_id}")
            if domain:
                lines.append(f"- 领域: {domain}")
            if quality:
                lines.append(f"- 质量评分: {quality:.2f}")
            if intent_tags:
                lines.append(f"- 意图标签: {', '.join(intent_tags[:5])}")
            if variables:
                var_desc = ", ".join(
                    f"{v.get('name', '')}({'必填' if v.get('required') else '可选'})"
                    for v in variables[:5]
                )
                lines.append(f"- 所需变量: {var_desc}")
            if template_text:
                lines.append("- 模板内容:")
                # 缩进模板内容，避免破坏 markdown 结构
                indented = "\n".join(
                    "  " + line for line in template_text.strip().split("\n")
                )
                lines.append(indented)
            lines.append("")

        return "\n".join(lines)

    # ============================================================
    # 内容生成方法（由 Handler 调用）
    # ============================================================

    async def _generate_simple_response(self, parsed: Dict[str, Any], min_length: int = 40) -> str:
        task = parsed.get("original_question", "")
        task_lower = task.strip().lower()

        if re.search(r"(你是谁|你叫什么|你的名字|自我介绍|你是什么)", task_lower):
            prompt = f"""你是 AgentMatrix 平台的 AI 助手（多智能体协同+国产算力优化平台，简单任务本地处理，复杂任务云端增强）。

用户问："{task}"

请直接以第一人称回复，以"我是 AgentMatrix 平台的 AI 助手"开头，简短介绍平台，{min_length}-150字，像真人对话，不要标题大纲。"""
        elif re.search(r"(你好|您好|hi|hello|嗨|hey|早上好|下午好|晚上好)", task_lower):
            prompt = f'用户向你打招呼："{task}"\n\n请友好自然地回复用户，{min_length}-60字，像真人对话。'
        else:
            prompt = f'用户说："{task}"\n\n请友好自然地简短回复，{min_length}-60字，像真人对话。'

        response = await self._call_llm(prompt, model=self.local_model, use_cloud=False, temperature=0.7, max_tokens=256, system_prompt=self._current_system_prompt)
        return response.strip() if response else task

    async def _generate_fact_answer(self, parsed: Dict[str, Any]) -> str:
        task = parsed.get("original_question", "")
        task_lower = task.strip().lower()
        knowledge_items = parsed.get("knowledge_items", [])
        knowledge_text = self._build_knowledge_text(knowledge_items)

        is_concise = any(re.search(p, task_lower) for p in [
            r"用一句话", r"一句话", r"简要说明", r"简要介绍", r"简短回答",
            r"简单说", r"简单解释", r"概括一下",
        ])

        if is_concise:
            prompt = f"""请简洁地回答用户的问题。用户要求简短回答，不要展开。

## 用户问题
{task}

## 参考知识（如有）
{knowledge_text if knowledge_text else "无参考知识，请基于常识回答"}

## 要求
1. 回答要简洁精炼，尽量控制在1-3句话
2. 直接给出答案，不要加"答案是"、"根据问题"等前缀
3. 不要使用标题、大纲、分点等格式
4. 语言精炼准确

请直接回答："""
        else:
            prompt = f"""请根据以下参考知识直接回答用户的问题。

## 用户问题
{task}

## 参考知识（必须严格基于以下知识作答，不要编造）
{knowledge_text}

## 回答要求
1. 直接回答问题，不要跑题
2. 语言简洁准确，像百科条目
3. 使用 Markdown 格式组织
4. 如果参考知识不够完整，就基于已有知识诚实作答

请直接回答："""

        response = await self._call_llm(prompt, model=self.local_model, use_cloud=False, temperature=0.3, max_tokens=2048, system_prompt=self._current_system_prompt)
        return response.strip() if response else task

    async def _generate_polish_response(self, parsed: Dict[str, Any]) -> str:
        """生成润色/改写后的内容"""
        task = parsed.get("original_question", "")
        polish_keywords = ["润色以下内容", "改写以下内容", "优化以下内容", "修改以下内容",
                          "帮我润色", "帮我改写", "请帮我润色", "请帮我改写",
                          "润色：", "改写：", "优化：", "修改："]
        original_text = task
        for kw in polish_keywords:
            if kw in task:
                idx = task.index(kw) + len(kw)
                while idx < len(task) and task[idx] in "：:，,。. ":
                    idx += 1
                if idx < len(task):
                    original_text = task[idx:]
                break

        prompt = f"""请对以下内容进行润色优化，保持原意，只提升表达质量。

## 用户要求
{task[:500]}

## 需要润色的原文
{original_text[:2000]}

## 润色要求
1. 保持原有的核心意思和情感基调
2. 提升语言表达的专业性和流畅度
3. 修正语法错误和不自然的表达
4. 适当增加细节使内容更生动
5. 直接输出润色后的最终文本，不要添加任何解释、说明或标记
6. 不要输出"润色后"、"修改后"等前缀

请直接输出润色后的内容："""

        response = await self._call_llm(
            prompt, model=self.local_model, use_cloud=False,
            temperature=0.4, max_tokens=4096, system_prompt=self._current_system_prompt
        )
        return response.strip() if response else task

    async def _generate_creative_writing(self, parsed: Dict[str, Any]) -> str:
        """自由生成创意写作内容（不使用模板）"""
        task = parsed.get("original_question", "")
        task_lower = task.strip().lower()
        knowledge_items = parsed.get("knowledge_items", [])
        knowledge_text = self._build_knowledge_text(knowledge_items)

        is_email = any(kw in task_lower for kw in ["邮件", "信件", "邀请函", "email", "信函"])
        is_formal = any(kw in task_lower for kw in ["正式", "商务", "官方", "专业"])

        if is_email:
            style_guide = """## 写作要求
1. 直接输出邮件/信件内容，不要使用"任务概述"、"核心需求"等模板化标题
2. 使用正式的商务信函格式（称呼、正文、落款）
3. 语言专业得体，条理清晰
4. 根据用户要求包含所有必要信息（时间、地点、议程等）
5. 不要包含"根据您的要求"等开场白"""
        elif is_formal:
            style_guide = """## 写作要求
1. 直接输出写作内容，不要使用"任务概述"、"核心需求"等模板化标题
2. 保持正式、专业的写作风格
3. 根据用户要求控制篇幅和格式
4. 内容清晰有条理
5. 不要包含"根据您的要求"等开场白"""
        else:
            style_guide = """## 写作要求
1. 直接输出写作内容，不要使用"任务概述"、"核心需求"等模板化标题
2. 保持自然流畅的写作风格
3. 根据用户要求控制篇幅
4. 内容要有感染力，生动有趣
5. 不要包含"根据您的要求"等开场白"""

        prompt = f"""请根据用户要求进行写作。

## 用户要求
{task[:1500]}

## 参考知识（如有）
{knowledge_text if knowledge_text else "无"}

{style_guide}

请直接输出写作内容："""

        response = await self._call_llm(
            prompt, model=self.local_model, use_cloud=False,
            temperature=0.7, max_tokens=4096, system_prompt=self._current_system_prompt
        )
        return response.strip() if response else task

    async def _generate_with_template(self, parsed: Dict[str, Any],
                                       template: List[Dict[str, str]],
                                       task_type: str) -> str:
        task = parsed.get("original_question", "")
        keywords = parsed.get("keywords", [])
        knowledge_items = parsed.get("knowledge_items", [])
        requirements = parsed.get("requirements", [])
        outline = parsed.get("outline", [])

        knowledge_text = self._build_knowledge_text(knowledge_items)
        requirements_text = "\n".join(f"- {r}" for r in requirements) if requirements else "无"
        outline_text = "\n".join(f"- {s}" for s in outline) if outline else "无"

        template_str = "\n".join(
            f"{i}. **{section['title']}**：{section['content']}"
            for i, section in enumerate(template, 1)
        )

        if knowledge_text:
            prompt = f"""请按以下模板生成一份{task_type}。

## 用户需求
{task}

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
{task}

## 写作模板
{template_str}

## 参考大纲
{outline_text}

## 关键词
{', '.join(keywords) if keywords else '无'}

## 关键要求
{requirements_text}

## 输出要求
1. 严格按模板的章节结构组织内容
2. 每个章节必须充实完整，不能只有一两句话
3. 使用 Markdown 格式：## 二级标题、### 三级标题
4. 直接输出最终文档，不要多余说明

请开始撰写："""

        response = await self._call_llm(prompt, model=self.local_model, use_cloud=False, temperature=0.3, max_tokens=4096, system_prompt=self._current_system_prompt)
        return response if response else f"# {task}\n\n生成失败，请重试。"

    async def _generate_with_template_engine(self, parsed: Dict[str, Any],
                                               template, engine) -> str:
        """V2.1: 使用 TemplateEngine 生成内容

        Args:
            parsed: 解析后的 Knowledge Agent 输出
            template: TemplateEngine 选中的 Template 对象
            engine: TemplateEngine 实例
        """
        task = parsed.get("original_question", "")
        knowledge_items = parsed.get("knowledge_items", [])
        knowledge_text = self._build_knowledge_text(knowledge_items)

        # 使用 TemplateEngine 构建 Prompt
        prompt = engine.build_template_prompt(
            template=template,
            user_task=task,
            summary=knowledge_text if knowledge_text else "",
        )

        response = await self._call_llm(
            prompt, model=self.local_model, use_cloud=False,
            temperature=0.3, max_tokens=4096,
            system_prompt=self._current_system_prompt
        )
        return response if response else f"# {task}\n\n生成失败，请重试。"

    def _build_normal_answer_prompt(self, task: str, summary: str, keywords: List[str], min_length: int = 40) -> str:
        """V2.1: 构建自然语言回答 Prompt（不使用模板结构）
        V2.2: 检测"详细/具体"类请求，自动提高 min_length 并强调多维度输出
        """
        # V2.2: 检测用户是否要求详细/具体输出
        # V3.2: 增加"提取/排好版/原样/所有文字"等关键词，触发完整输出模式
        detail_patterns = [
            "详细", "具体", "步骤", "明细", "细化", "展开", "深入",
            "提取", "排好版", "原样", "所有文字", "列出", "整理出来",
        ]
        is_detailed_request = any(p in task for p in detail_patterns)
        if is_detailed_request:
            min_length = max(min_length, 1200)

        parts = [f"请根据以下信息，用自然流畅的语言直接回答问题。不要使用模板格式（如'任务概述/核心需求/解决方案'等），就像普通对话一样回答。"]

        if summary:
            parts.append(f"\n## 背景信息\n{summary}")

        if keywords:
            parts.append(f"\n## 关键词\n{', '.join(keywords)}")

        parts.append(f"\n## 用户问题\n{task}")
        if is_detailed_request:
            parts.append(f"\n## 要求\n1. 直接回答问题，不要套用模板格式\n2. 语言自然流畅，像真人对话\n3. **内容必须非常详细，回答至少{min_length}字以上**\n4. 用户要求详细/具体的回答，请务必展开每个要点，给出具体的时间、数字、步骤、示例\n5. 如果用户提到了多个维度（如时间安排、花费、食谱等），必须逐一覆盖每个维度，不要遗漏\n6. 用 Markdown 标题和列表组织内容，让结构清晰")
        else:
            parts.append(f"\n## 要求\n1. 直接回答问题，不要套用模板格式\n2. 语言自然流畅，像真人对话\n3. 内容充实，回答至少{min_length}字以上\n4. 如果问题简单，给出简洁但完整的回答\n5. 如果问题复杂，给出有深度的回答")

        prompt = "\n".join(parts)
        if self._current_system_prompt:
            prompt = self._current_system_prompt + "\n\n" + prompt
        return prompt

    async def _call_local_model(self, prompt: str) -> str:
        """V2.1: 调用本地模型（供 NormalAnswerHandler 使用）"""
        response = await self._call_llm(
            prompt,
            model=self.local_model,
            use_cloud=False,
            temperature=0.5,
            max_tokens=2048,
            system_prompt=self._current_system_prompt
        )
        return response if response else "抱歉，我暂时无法处理这个请求。"