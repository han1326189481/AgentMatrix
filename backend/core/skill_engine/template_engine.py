"""
Template Engine — 独立模板管理引擎（Skill Engine V2.1）

从 YAML 文件加载模板，按 task_type + domain + keywords 匹配。
替代原来硬编码在 Writer Agent 中的 WRITER_TEMPLATES 和 TEMPLATE_KEYWORD_MAP。

用法：
    engine = TemplateEngine()
    template = engine.select_template(task_type="planning", domain="business", keywords=["方案"])
    if template:
        sections = engine.get_sections(template)
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============================================================
# Data Models
# ============================================================

@dataclass
class TemplateSection:
    """模板章节"""
    title: str
    content: str          # 章节内容描述
    required: bool = True  # 是否必填章节


@dataclass
class TemplateMeta:
    """模板元数据"""
    template_id: str
    name: str
    version: str
    description: str = ""


@dataclass
class TemplateApplicable:
    """模板适用条件"""
    task_types: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    min_length: int = 200


@dataclass
class TemplateOutput:
    """模板输出配置"""
    format: str = "markdown"
    header_level: str = "##"
    style: str = "professional"


@dataclass
class Template:
    """完整的模板定义"""
    meta: TemplateMeta
    applicable: TemplateApplicable
    sections: List[TemplateSection] = field(default_factory=list)
    output: TemplateOutput = field(default_factory=TemplateOutput)
    constraints: List[str] = field(default_factory=list)

    @property
    def section_titles(self) -> List[str]:
        """返回所有章节标题"""
        return [s.title for s in self.sections]

    @property
    def required_sections(self) -> List[TemplateSection]:
        """返回所有必填章节"""
        return [s for s in self.sections if s.required]


# ============================================================
# Template Engine
# ============================================================

class TemplateEngine:
    """从 YAML 文件加载模板，按规则匹配

    匹配优先级：
    1. 精确 keyword 匹配（keyword 在用户查询中）
    2. domain 匹配
    3. task_type 匹配
    4. 默认通用模板
    """

    def __init__(self, templates_dir: str = None):
        if templates_dir is None:
            from shared.platform import get_prompts_dir
            templates_dir = os.path.join(get_prompts_dir(), "templates")
        self._templates_dir = templates_dir
        self._templates: List[Template] = []
        self._loaded = False

    def _ensure_loaded(self):
        """懒加载模板文件"""
        if self._loaded:
            return
        self._load_templates()
        self._loaded = True

    def _load_templates(self):
        """从 templates/ 目录加载所有 YAML 模板文件"""
        if not os.path.isdir(self._templates_dir):
            logger.warning(f"Template directory not found: {self._templates_dir}")
            self._load_default_templates()
            return

        try:
            import yaml

            for fname in sorted(os.listdir(self._templates_dir)):
                if not fname.endswith(".yaml"):
                    continue

                fpath = os.path.join(self._templates_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}

                    template = self._parse_template(data)
                    if template:
                        self._templates.append(template)
                        logger.debug(f"Template loaded: {template.meta.template_id} from {fname}")
                except Exception as e:
                    logger.warning(f"Failed to load template {fname}: {e}")

            logger.info(f"TemplateEngine: {len(self._templates)} templates loaded")
        except ImportError:
            logger.warning("yaml not available, using default templates")
            self._load_default_templates()

    def _parse_template(self, data: dict) -> Optional[Template]:
        """解析 YAML 数据为 Template 对象"""
        if not data or "meta" not in data:
            return None

        meta = TemplateMeta(
            template_id=data["meta"].get("template_id", ""),
            name=data["meta"].get("name", ""),
            version=data["meta"].get("version", "1.0.0"),
            description=data["meta"].get("description", ""),
        )

        app_data = data.get("applicable", {})
        applicable = TemplateApplicable(
            task_types=app_data.get("task_types", []),
            domains=app_data.get("domains", []),
            keywords=app_data.get("keywords", []),
            min_length=app_data.get("min_length", 200),
        )

        sections = []
        for sec in data.get("sections", []):
            sections.append(TemplateSection(
                title=sec.get("title", ""),
                content=sec.get("content", ""),
                required=sec.get("required", True),
            ))

        out_data = data.get("output", {})
        output = TemplateOutput(
            format=out_data.get("format", "markdown"),
            header_level=out_data.get("header_level", "##"),
            style=out_data.get("style", "professional"),
        )

        return Template(
            meta=meta,
            applicable=applicable,
            sections=sections,
            output=output,
            constraints=data.get("constraints", []),
        )

    def _load_default_templates(self):
        """内置默认模板（当 YAML 文件不可用时）"""
        self._templates = [
            # ============================================================
            # 商业领域
            # ============================================================
            Template(
                meta=TemplateMeta("business_plan", "商业计划书", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["planning"],
                    domains=["business"],
                    keywords=["商业计划", "商业计划书", "融资计划", "创业计划", "BP"],
                    min_length=300
                ),
                sections=[
                    TemplateSection("执行摘要", "1-2页概括全局：项目亮点、市场机会、商业模式、财务预测、融资需求"),
                    TemplateSection("公司概况", "公司使命、愿景、发展历程、核心团队介绍"),
                    TemplateSection("市场分析", "行业规模、目标客户画像、竞争格局、SWOT分析"),
                    TemplateSection("产品与服务", "产品功能、核心卖点、技术壁垒、发展规划"),
                    TemplateSection("商业模式", "收入来源、成本结构、盈利预测、获客方式"),
                    TemplateSection("营销策略", "推广渠道、定价策略、销售计划、合作伙伴"),
                    TemplateSection("财务预测", "3-5年收入/成本/利润预测表，关键假设说明"),
                    TemplateSection("融资需求", "融资金额、估值、资金用途、退出机制"),
                    TemplateSection("风险与应对", "市场风险、竞争风险、技术风险、财务风险及应对措施"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["数据真实可查", "逻辑自洽", "图表辅助说明"],
            ),
            Template(
                meta=TemplateMeta("marketing_plan", "营销方案", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["planning"],
                    domains=["business"],
                    keywords=["营销方案", "营销计划", "推广方案", "营销策略", "市场推广"],
                    min_length=200
                ),
                sections=[
                    TemplateSection("营销目标", "量化的营销目标（覆盖人数、转化率、销售额等）"),
                    TemplateSection("目标受众", "受众画像（年龄、性别、收入、兴趣、行为习惯）"),
                    TemplateSection("核心卖点", "产品/服务的独特卖点和差异化定位"),
                    TemplateSection("渠道策略", "线上渠道和线下渠道的具体方案"),
                    TemplateSection("内容策略", "内容类型、发布频率、话题规划"),
                    TemplateSection("预算分配", "各渠道预算占比，预期ROI"),
                    TemplateSection("时间排期", "各阶段任务和时间节点"),
                    TemplateSection("效果评估", "关键指标和评估方法"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["目标量化", "渠道可执行", "预算合理"],
            ),
            # ============================================================
            # 活动策划领域
            # ============================================================
            Template(
                meta=TemplateMeta("event_planning", "活动策划案", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["planning"],
                    domains=["business", "daily"],
                    keywords=["运动会", "晚会", "团建", "庆典", "发布会", "活动策划", "策划方案", "活动方案", "策划"],
                    min_length=200
                ),
                sections=[
                    TemplateSection("项目背景", "说明策划的起因、背景和必要性"),
                    TemplateSection("策划目标", "明确策划要达成的具体目标"),
                    TemplateSection("活动/项目方案", "详细描述方案内容、流程和时间安排"),
                    TemplateSection("资源配置", "列出所需人员、物资、场地等资源"),
                    TemplateSection("预算规划", "各项费用的预算明细表"),
                    TemplateSection("风险评估与应对", "识别可能的风险及应急预案"),
                    TemplateSection("效果评估", "如何评估策划案的执行效果"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["流程完整", "预算合理", "风险可控", "时间可执行"],
            ),
            # ============================================================
            # 办公领域
            # ============================================================
            Template(
                meta=TemplateMeta("meeting_minutes", "会议纪要", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["writing"],
                    domains=["business"],
                    keywords=["会议纪要", "会议记录", "会议总结", "会议"],
                    min_length=150
                ),
                sections=[
                    TemplateSection("会议基本信息", "会议主题、时间、地点、主持人、记录人"),
                    TemplateSection("参会人员", "出席人员、缺席人员、列席人员"),
                    TemplateSection("会议议程", "逐项列出会议议程和讨论要点"),
                    TemplateSection("讨论内容", "各方观点摘要，重要发言记录"),
                    TemplateSection("决议事项", "表决结果、通过的决议"),
                    TemplateSection("行动计划", "责任人、具体任务、截止时间、交付物"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["客观记录", "决议明确", "行动项有责任人"],
            ),
            Template(
                meta=TemplateMeta("work_summary", "工作总结", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["writing"],
                    domains=["business"],
                    keywords=["工作总结", "年终总结", "述职报告", "述职", "工作汇报", "汇报"],
                    min_length=200
                ),
                sections=[
                    TemplateSection("工作概述", "时间段、岗位职责、工作范围"),
                    TemplateSection("主要成果", "按项目或指标分类，用数据量化成果"),
                    TemplateSection("亮点与创新", "突出贡献和创新做法"),
                    TemplateSection("问题与不足", "诚实复盘，分析原因"),
                    TemplateSection("经验教训", "可复用的方法论和改进思路"),
                    TemplateSection("下阶段计划", "具体目标、行动步骤、时间节点"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["数据说话", "实事求是", "重点突出"],
            ),
            Template(
                meta=TemplateMeta("notice", "通知公告", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["writing"],
                    domains=["business"],
                    keywords=["通知", "公告", "通报", "通告"],
                    min_length=100
                ),
                sections=[
                    TemplateSection("标题", "关于XXX的通知，简明扼要"),
                    TemplateSection("正文背景", "发布通知的原因和依据"),
                    TemplateSection("具体事项", "通知的核心内容，按条列明"),
                    TemplateSection("执行要求", "相关单位/人员需要做什么、怎么做"),
                    TemplateSection("时间节点", "起止时间、截止日期"),
                    TemplateSection("联系方式", "咨询联系人、电话、邮箱"),
                    TemplateSection("落款", "发布单位、日期"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["标题规范", "事项明确", "落款完整"],
            ),
            # ============================================================
            # 编码/技术领域
            # ============================================================
            Template(
                meta=TemplateMeta("tech_doc", "技术文档", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["writing"],
                    domains=["tech"],
                    keywords=["技术方案", "技术文档", "架构设计", "系统设计", "设计文档", "技术选型"],
                    min_length=200
                ),
                sections=[
                    TemplateSection("概述", "项目/系统/功能的简要介绍和背景"),
                    TemplateSection("技术架构", "整体架构图、核心组件说明"),
                    TemplateSection("技术选型", "使用的技术栈及其选型理由"),
                    TemplateSection("详细设计", "模块划分、接口定义、数据模型"),
                    TemplateSection("部署运维", "部署环境、配置说明、监控方案"),
                    TemplateSection("API参考", "主要接口的请求/响应格式说明"),
                    TemplateSection("注意事项", "已知限制、性能指标、安全建议"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["架构清晰", "选型有理", "接口完整"],
            ),
            Template(
                meta=TemplateMeta("api_doc", "API文档", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["writing"],
                    domains=["tech"],
                    keywords=["API文档", "接口文档", "API说明", "接口说明", "Swagger"],
                    min_length=150
                ),
                sections=[
                    TemplateSection("接口概述", "接口功能说明和适用场景"),
                    TemplateSection("请求方法", "GET/POST/PUT/DELETE 及请求URL"),
                    TemplateSection("请求参数", "参数名、类型、必填、说明、示例"),
                    TemplateSection("响应格式", "响应字段说明和示例JSON"),
                    TemplateSection("错误码", "错误码、错误信息、解决方法"),
                    TemplateSection("调用示例", "代码示例"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["参数完整", "示例可运行", "错误码覆盖"],
            ),
            # ============================================================
            # 校园领域
            # ============================================================
            Template(
                meta=TemplateMeta("campus_activity", "校园活动方案", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["planning"],
                    domains=["daily"],
                    keywords=["团课", "班会", "团日", "志愿者", "志愿服务", "支教", "社团", "校园活动"],
                    min_length=150
                ),
                sections=[
                    TemplateSection("活动主题", "活动主题名称"),
                    TemplateSection("活动目的", "本次活动的教育目标或意义"),
                    TemplateSection("主题导入", "开场方式：视频、案例、故事、问题（5-10分钟）"),
                    TemplateSection("主体环节", "讨论、分享、互动、游戏等活动设计（30-40分钟）"),
                    TemplateSection("知识讲解", "核心知识点和理论内容"),
                    TemplateSection("互动讨论", "讨论题目、分组方式、发言规则"),
                    TemplateSection("总结升华", "活动总结、价值升华、布置实践任务"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["主题鲜明", "互动充分", "时间可控"],
            ),
            Template(
                meta=TemplateMeta("academic_paper", "学术论文", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["writing"],
                    domains=["daily"],
                    keywords=["论文", "学术论文", "毕业论文", "课程论文", "学术文章", "研究"],
                    min_length=300
                ),
                sections=[
                    TemplateSection("摘要", "研究目的、方法、结果、结论，200-300字"),
                    TemplateSection("引言", "研究背景、文献综述、研究问题、论文结构"),
                    TemplateSection("文献综述", "国内外研究现状、研究空白、本文贡献"),
                    TemplateSection("研究方法", "数据来源、变量定义、模型设定"),
                    TemplateSection("实证分析", "描述性统计、回归结果、稳健性检验"),
                    TemplateSection("结论与建议", "主要发现、政策建议、研究局限、未来方向"),
                    TemplateSection("参考文献", "按GB/T 7714格式列出引用文献"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["引用规范", "数据真实", "逻辑严谨"],
            ),
            # ============================================================
            # 政府/公文领域
            # ============================================================
            Template(
                meta=TemplateMeta("gov_doc", "公文报告", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["writing"],
                    domains=["business"],
                    keywords=["公文", "请示", "批复", "函", "报告", "政府文件", "红头文件"],
                    min_length=200
                ),
                sections=[
                    TemplateSection("标题", "关于XXX的报告/请示/通知，规范格式"),
                    TemplateSection("主送机关", "收文单位的规范全称"),
                    TemplateSection("正文引言", "报告/请示的背景和依据"),
                    TemplateSection("正文主体", "具体事项：工作情况/问题分析/意见建议"),
                    TemplateSection("结尾用语", "特此报告/妥否请批示/请审阅等规范用语"),
                    TemplateSection("附件说明", "如有附件，列出名称和数量"),
                    TemplateSection("落款", "发文机关署名、成文日期、印章"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["一文一事", "语言规范", "格式标准"],
            ),
            # ============================================================
            # 通用（兜底）
            # ============================================================
            Template(
                meta=TemplateMeta("default_business", "通用商业方案", "1.0"),
                applicable=TemplateApplicable(
                    task_types=["planning"],
                    keywords=["方案", "计划", "需求文档"],
                    min_length=200
                ),
                sections=[
                    TemplateSection("任务概述", "介绍任务的背景和目标"),
                    TemplateSection("核心需求", "分析任务的核心需求"),
                    TemplateSection("解决方案", "提出解决问题的方案"),
                    TemplateSection("实施计划", "制定实施计划和时间表"),
                ],
                output=TemplateOutput(style="professional"),
                constraints=["结构完整", "内容专业", "数据支撑"],
            )
        ]
        logger.info("TemplateEngine: using default templates (YAML not available)")

    # ============================================================
    # 模板选择
    # ============================================================

    def select_template(self, task_type: str = None, domain: str = None,
                        user_query: str = None, keywords: List[str] = None) -> Optional[Template]:
        """按规则选择最佳模板

        匹配优先级：
        1. keyword 精确匹配（用户查询中包含模板关键词）→ 必须命中
        2. 多模板命中时按 domain 择优
        3. 多模板命中时按 task_type 择优
        4. 无关键词匹配 → 返回 None
        """
        self._ensure_loaded()

        if not self._templates:
            return None

        query_lower = (user_query or "").lower()

        # Level 1: keyword 精确匹配（必须命中）
        if not query_lower:
            return None

        matching = []
        for template in self._templates:
            for kw in template.applicable.keywords:
                if kw in query_lower:
                    matching.append(template)
                    break  # 一个模板只匹配一次

        if not matching:
            return None  # 无关键词匹配 → 不使用模板

        # Level 2: 多模板命中时按 domain 择优
        if domain:
            domain_match = [t for t in matching if domain in t.applicable.domains]
            if domain_match:
                matching = domain_match

        # Level 3: 多模板命中时按 task_type 择优
        if task_type and len(matching) > 1:
            type_match = [t for t in matching if task_type in t.applicable.task_types]
            if type_match:
                matching = type_match

        selected = matching[0]
        logger.debug(f"Template match: {selected.meta.template_id} via keywords")
        return selected

    def get_all_templates(self) -> List[Template]:
        """返回所有已加载的模板"""
        self._ensure_loaded()
        return list(self._templates)

    def get_template_by_id(self, template_id: str) -> Optional[Template]:
        """按 ID 查找模板"""
        self._ensure_loaded()
        for t in self._templates:
            if t.meta.template_id == template_id:
                return t
        return None

    # ============================================================
    # 模板渲染
    # ============================================================

    def build_template_prompt(self, template: Template, user_task: str,
                               summary: str = "", extra_context: Dict[str, Any] = None) -> str:
        """根据模板构建生成 Prompt

        Args:
            template: 选中的模板
            user_task: 用户原始任务
            summary: Knowledge Agent 的摘要
            extra_context: 额外上下文信息

        Returns:
            格式化的 Prompt 字符串
        """
        parts = [f"请根据以下模板结构和参考知识生成内容，每个章节都要有实质性内容，不要只写标题。\n"]

        if summary:
            parts.append(f"## 参考知识（请基于以下知识作答，不要编造与知识冲突的内容）\n{summary}\n")

        parts.append(f"## 用户需求\n{user_task}\n")

        # 模板结构
        parts.append(f"## 模板结构：{template.meta.name}")
        for i, sec in enumerate(template.sections, 1):
            req = "（必填）" if sec.required else "（可选）"
            parts.append(f"{i}. {template.output.header_level} {sec.title} {req}")
            parts.append(f"   {sec.content}")

        # 约束条件
        if template.constraints:
            parts.append(f"\n## 约束条件")
            for c in template.constraints:
                parts.append(f"- {c}")

        # 格式要求
        parts.append(f"\n## 格式要求")
        parts.append(f"- 使用 {template.output.format} 格式")
        parts.append(f"- 风格：{template.output.style}")
        parts.append(f"- 每个章节不少于 50 字")

        prompt = "\n".join(parts)
        return prompt

    def get_min_length(self, template: Optional[Template] = None) -> int:
        """获取模板建议的最小长度"""
        if template:
            return template.applicable.min_length
        return 40  # 默认最小长度


# ============================================================
# 全局单例
# ============================================================

_template_engine: Optional[TemplateEngine] = None


def get_template_engine() -> TemplateEngine:
    """获取全局 TemplateEngine 单例"""
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine