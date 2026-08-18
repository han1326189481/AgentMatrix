"""Knowledge Agent - 知识检索与需求摘要一体化（Skill Engine V2.1）

V2.1 变更：
- 集成 TaskClassifier：先 TaskType 分类再 SkillPath 导航
- 输出 task_type_v2 + task_data 供 Writer Agent 使用
"""
import sys
import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from agents.base.agent import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger(__name__)

# 任务类型模板（原 Summary Agent 的 outline 功能）
TASK_TEMPLATES = {
    "活动策划": [
        "一、活动概述", "二、活动目标", "三、活动流程安排",
        "四、人员分工", "五、预算规划", "六、安全保障措施", "七、应急预案"
    ],
    "方案设计": [
        "一、需求分析", "二、方案目标", "三、方案设计",
        "四、实施步骤", "五、风险评估", "六、预期成果"
    ],
    "文档撰写": [
        "一、引言", "二、主体内容", "三、结论", "四、参考文献"
    ],
    "分析报告": [
        "一、问题描述", "二、现状分析", "三、解决方案", "四、实施建议"
    ],
    "通用任务": [
        "一、任务概述", "二、核心需求", "三、解决方案", "四、实施计划"
    ]
}


class KnowledgeAgent(BaseAgent):
    def __init__(self, settings=None):
        super().__init__("knowledge", "Knowledge Agent", settings=settings)
        # local_model 由 BaseAgent 从 ModelRegistry 读取，无需在此硬编码
        self._knowledge_service = None
        self._fallback_keywords = []
        self._fallback_knowledge = {}
        self._skill_manager = None
        self._intent_analyzer = None
        self._task_classifier = None
        # V3.5: WebSearch 插件与时效性知识库（懒加载）
        self._web_search_plugin = None
        self._timely_knowledge_service = None
        # V4.0: CodeMunch 代码检索插件（懒加载）
        self._code_munch_plugin = None

        self.system_keywords = ["我是谁", "你是谁", "knowledge agent", "知识助手", "你的职责", "你的任务"]

        # 保留基础关键词作为 fallback
        self.common_keywords = [
            "AI", "人工智能", "校园", "教育", "规划", "方案", "系统", "开发", "设计",
            "报告", "分析", "端云协同", "多智能体", "RAG", "检索增强", "知识蒸馏",
            "马拉松", "活动策划", "运动会", "志愿服务", "赛事", "跑步", "活动", "策划",
            "组织", "安全", "预算", "办公", "WPS", "Office", "会议", "邮件", "项目管理",
            "生活", "健康", "营养", "急救", "天气", "交通", "法律", "理财",
            "考试", "奖学金", "就业", "金融", "AIGC", "提示词", "深度学习",
            "机器学习", "大数据", "云计算", "数据可视化", "技术选型", "架构设计",
        ]

    # ===== Skill Engine 懒加载 =====

    @property
    def skill_manager(self):
        if self._skill_manager is None:
            from core.skill_engine.skill_manager import get_skill_manager
            self._skill_manager = get_skill_manager()
        return self._skill_manager

    @property
    def intent_analyzer(self):
        if self._intent_analyzer is None:
            from core.skill_engine.intent_analyzer import get_intent_analyzer
            self._intent_analyzer = get_intent_analyzer()
        return self._intent_analyzer

    @property
    def task_classifier(self):
        """V2.1: TaskClassifier 懒加载"""
        if self._task_classifier is None:
            from core.skill_engine.task_engine import get_task_classifier
            self._task_classifier = get_task_classifier()
        return self._task_classifier

    # ============================================================
    # V3.5 (2026-07-31): Web Search + 时效性知识库 懒加载
    # ============================================================

    @property
    def web_search_plugin(self):
        """懒加载 WebSearchPlugin"""
        if self._web_search_plugin is None:
            try:
                from core.llm.web_search_plugin import get_web_search_plugin
                self._web_search_plugin = get_web_search_plugin()
            except Exception as e:
                logger.warning(f"WebSearchPlugin 加载失败: {e}")
                self._web_search_plugin = False  # 标记不可用
        return self._web_search_plugin if self._web_search_plugin is not False else None

    @property
    def timely_knowledge_service(self):
        """懒加载 TimelyKnowledgeService"""
        if self._timely_knowledge_service is None:
            try:
                from knowledge.timely_knowledge_service import get_timely_knowledge_service
                self._timely_knowledge_service = get_timely_knowledge_service()
            except Exception as e:
                logger.warning(f"TimelyKnowledgeService 加载失败: {e}")
                self._timely_knowledge_service = False  # 标记不可用
        return self._timely_knowledge_service if self._timely_knowledge_service is not False else None

    # ============================================================
    # V4.0 (2026-08-17): CodeMunch 代码检索插件 懒加载
    # ============================================================

    @property
    def code_munch_plugin(self):
        """懒加载 CodeMunchPlugin — 基于 jCodeMunch MCP 的代码检索"""
        if self._code_munch_plugin is None:
            try:
                from core.llm.code_munch_plugin import get_code_munch_plugin
                self._code_munch_plugin = get_code_munch_plugin()
            except Exception as e:
                logger.warning(f"CodeMunchPlugin 加载失败: {e}")
                self._code_munch_plugin = False  # 标记不可用
        return self._code_munch_plugin if self._code_munch_plugin is not False else None

    async def _try_code_munch(
        self,
        user_input: str,
        knowledge_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """V4.0: 尝试使用 CodeMunch 插件检索代码知识

        流程:
        1. 检测用户问题是否为代码相关查询
        2. 初始化 CodeMunch MCP 子进程（如未初始化）
        3. 调用 search_and_extract 搜索符号并提取源代码
        4. 注入 knowledge_items 供 Writer Agent 使用

        Args:
            user_input: 用户输入内容
            knowledge_items: 知识条目列表（原地修改）

        Returns:
            {
                "used": bool,              # 是否使用了 CodeMunch
                "symbols_count": int,      # 搜索到的符号数
                "sources_count": int,      # 提取的源码数
                "error": Optional[str],
            }
        """
        result = {
            "used": False,
            "symbols_count": 0,
            "sources_count": 0,
            "error": None,
        }

        # 检测是否为代码相关查询
        from core.llm.code_munch_plugin import CodeMunchPlugin
        if not CodeMunchPlugin.detect_code_query(user_input):
            return result

        plugin = self.code_munch_plugin
        if plugin is None:
            result["error"] = "CodeMunchPlugin 不可用"
            return result

        try:
            # 确保 MCP 子进程已初始化
            if not await plugin._ensure_initialized():
                result["error"] = "CodeMunch MCP 初始化失败"
                return result

            # 一站式搜索 + 提取
            cm_result = await plugin.search_and_extract(
                query=user_input[:100],
                max_symbols=3,
            )

            if cm_result.get("used"):
                # 注入知识库条目
                for item in cm_result.get("knowledge_items", []):
                    knowledge_items.append(item)

                result.update({
                    "used": True,
                    "symbols_count": len(cm_result.get("symbols", [])),
                    "sources_count": len(cm_result.get("sources", [])),
                })
                logger.info(
                    f"[KnowledgeAgent V4.0] CodeMunch 检索到 "
                    f"{result['symbols_count']} 个符号，"
                    f"提取 {result['sources_count']} 个源码"
                )
            else:
                result["error"] = cm_result.get("error", "未找到匹配代码")
                logger.debug(
                    f"[KnowledgeAgent V4.0] CodeMunch 未找到匹配: "
                    f"{result['error']}"
                )
        except Exception as e:
            result["error"] = f"CodeMunch 调用失败: {e}"
            logger.warning(f"[KnowledgeAgent V4.0] CodeMunch 异常: {e}")

        return result

    def _detect_timely_scenario(self, content: str) -> str:
        """检测用户问题是否属于时效性场景

        Returns:
            分类字符串："food"/"location"/"travel"/"weather"/"review" 或 "" (非时效性)
        """
        try:
            from knowledge.timely_knowledge_service import _detect_category
            cat = _detect_category(content)
            return cat if cat != "other" else ""
        except Exception:
            return ""

    async def _try_timely_knowledge(
        self,
        user_input: str,
        knowledge_items: List[Dict[str, Any]],
        force: bool = False,
    ) -> Dict[str, Any]:
        """V3.5: 查询时效性知识库，必要时触发 Web Search 自学习入库

        流程:
        1. 检测是否为时效性场景（food/location/travel/weather/review）
           - force=True 时跳过场景检测，强制进入 Web Search 流程
        2. 查询时效性知识库
           - 有未过期条目 且 非强制 → 直接注入 knowledge_items
           - 无未过期条目 或 强制 → 触发 Web Search
        3. Web Search 结果经 DeepSeek 摘要后存入时效性知识库（自学习）
        4. 注入 knowledge_items 供 Writer Agent 使用

        Args:
            force: 抱怨澄清弹窗中用户选择"网络搜索再回答"时为 True，
                   跳过场景检测和 fresh 命中，直接联网搜索

        Returns:
            {
                "used": bool,              # 是否走了时效性知识/Web Search 路径
                "source": str,              # "fresh" / "web_search" / "stale_refresh"
                "category": str,            # 分类
                "content": str,             # 注入的内容
                "web_search_performed": bool,
                "stored_to_db": bool,
                "error": Optional[str],
            }
        """
        result = {
            "used": False, "source": "", "category": "",
            "content": "", "web_search_performed": False,
            "stored_to_db": False, "error": None,
        }

        # Step 1: 场景检测（force=True 时跳过，仍尝试推断 category 用于入库分类）
        category = self._detect_timely_scenario(user_input)
        if not category:
            if force:
                # 强制模式下即使不属于已知时效性场景，也用 "other" 兜底分类
                category = "other"
                logger.info(
                    f"[KnowledgeAgent V3.5] force_web_search=True，"
                    f"非时效性场景但强制联网搜索 (category=other)"
                )
            else:
                return result  # 非时效性问题，走原有流程

        result["category"] = category
        logger.info(
            f"[KnowledgeAgent V3.5] 进入时效性流程: category={category}, "
            f"force={force}, query='{user_input[:50]}'"
        )

        timely_svc = self.timely_knowledge_service
        if timely_svc is None:
            result["error"] = "TimelyKnowledgeService 不可用"
            return result

        # Step 2: 查询时效性知识库
        try:
            search_result = timely_svc.search(user_input, category=category, limit=3)
        except Exception as e:
            logger.warning(f"[KnowledgeAgent V3.5] 时效性知识库查询失败: {e}")
            search_result = {"fresh": [], "stale": [], "has_fresh": False, "has_stale": False}

        # Step 3a: 命中未过期条目 且 非强制 → 直接使用
        # 注意：force=True 时即使有 fresh 条目也要重新搜索，因为用户抱怨可能正是因为
        # 现有知识过时/错误，需要联网获取最新信息
        if search_result.get("has_fresh") and not force:
            fresh_items = search_result["fresh"]
            for entry in fresh_items:
                knowledge_items.append({
                    "keyword": entry.get("query", ""),
                    "content": f"[时效性知识-{entry['category']}] (created: {entry.get('created_at','')[:10]})\n{entry.get('content','')}",
                    "source": "timely_knowledge:fresh",
                    "domain": entry.get("category", category),
                })
            result.update({
                "used": True,
                "source": "fresh",
                "content": fresh_items[0].get("content", ""),
            })
            logger.info(
                f"[KnowledgeAgent V3.5] 命中时效性知识库 fresh 条目: {len(fresh_items)} 条"
            )
            return result

        # Step 3b: 无未过期条目 或 强制模式 → 触发 Web Search
        plugin = self.web_search_plugin
        if plugin is None:
            result["error"] = "WebSearchPlugin 不可用"
            # 过期条目作为降级数据使用（标记来源为 stale）
            if search_result.get("has_stale"):
                stale_items = search_result["stale"]
                for entry in stale_items:
                    knowledge_items.append({
                        "keyword": entry.get("query", ""),
                        "content": f"[时效性知识-已过期-{entry['category']}] (expired: {entry.get('expires_at','')[:10]})\n{entry.get('content','')}",
                        "source": "timely_knowledge:stale",
                        "domain": entry.get("category", category),
                    })
                result.update({
                    "used": True,
                    "source": "stale_degraded",
                    "content": stale_items[0].get("content", ""),
                })
            return result

        # Step 4: 调用 Web Search + DeepSeek 摘要
        result["web_search_performed"] = True
        try:
            ws_result = await plugin.search_and_summarize(
                query=user_input[:100],
                user_question=user_input,
                category=category,
            )
        except Exception as e:
            logger.error(f"[KnowledgeAgent V3.5] Web Search 调用失败: {e}", exc_info=True)
            result["error"] = f"Web Search 失败: {e}"
            return result

        if not ws_result.get("content"):
            result["error"] = ws_result.get("error", "Web Search 无结果")
            return result

        # Step 5: 自学习入库
        # 若有过期条目，刷新它；否则新建
        stored = False
        try:
            if search_result.get("has_stale"):
                stale_id = search_result["stale"][0].get("id")
                if stale_id:
                    ok = timely_svc.refresh_entry(
                        entry_id=stale_id,
                        new_content=ws_result["content"],
                        new_source="web_search:refreshed",
                    )
                    stored = ok
                    result["source"] = "stale_refresh"
            else:
                store_res = timely_svc.store(
                    query=user_input[:255],
                    content=ws_result["content"],
                    category=category,
                    source="web_search",
                    confidence=75,
                )
                stored = store_res.get("status") == "ok"
                result["source"] = "web_search"
        except Exception as e:
            logger.warning(f"[KnowledgeAgent V3.5] 入库失败（不影响当前回答）: {e}")

        result["stored_to_db"] = stored

        # Step 6: 注入 knowledge_items 供 Writer Agent 使用
        sources_str = ""
        if ws_result.get("sources"):
            src_list = [f"{s.get('title','')[:30]} ({s.get('url','')})" for s in ws_result["sources"][:3]]
            sources_str = "\n\n来源参考:\n" + "\n".join(f"- {s}" for s in src_list)

        knowledge_items.append({
            "keyword": user_input[:30],
            "content": f"[Web搜索-{category}] {ws_result['content']}{sources_str}",
            "source": "web_search",
            "domain": category,
        })

        result.update({
            "used": True,
            "content": ws_result["content"],
        })
        logger.info(
            f"[KnowledgeAgent V3.5] Web Search 完成: "
            f"summarized={ws_result.get('summarized')}, "
            f"stored={stored}, sources={len(ws_result.get('sources', []))}"
        )
        return result

    @property
    def knowledge_service(self):
        """懒加载知识库服务，并处理 MySQL 不可用时的降级"""
        if self._knowledge_service is None:
            try:
                from knowledge.mysql_service import get_knowledge_service
                self._knowledge_service = get_knowledge_service()
                # 尝试获取关键词以测试连接
                self._knowledge_service.get_all_keywords()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"MySQL knowledge service unavailable: {e}, using fallback"
                )
                self._knowledge_service = self._create_fallback_service()
        return self._knowledge_service

    def _create_fallback_service(self):
        """创建降级的内存知识库服务"""
        class FallbackKnowledgeService:
            def __init__(self):
                self._items = {
                    # ============================================================
                    # 一、商业领域 (Business)
                    # ============================================================
                    "商业/商业计划书": ["商业计划书是创业者向投资人或合作伙伴展示项目可行性的核心文档。标准结构包括：执行摘要（1-2页概括全局）、公司概况与愿景、市场分析（行业规模、目标客户、竞争格局）、产品与服务说明、商业模式与盈利方式、营销策略与推广计划、管理团队介绍、财务预测（3-5年收入/成本/利润表）、融资需求与资金用途、风险分析与应对措施。执行摘要应简练有力，能在3分钟内抓住读者兴趣。"],
                    "商业/市场分析": ["市场分析报告用于评估某个行业或细分市场的吸引力和可行性。核心要素：宏观环境分析（PEST：政治/经济/社会/技术）、行业生命周期阶段（导入期/成长期/成熟期/衰退期）、市场规模与增长率（TAM/SAM/SOM模型）、竞争格局（波特五力模型：现有竞争者/潜在进入者/替代品/供应商议价/买家议价）、消费者行为分析、SWOT分析（优势/劣势/机会/威胁）、市场趋势与预测。数据要标明来源，图表要清晰可读。"],
                    "商业/营销方案": ["营销方案是产品或服务推广的详细执行计划。典型结构：营销目标（SMART原则：具体/可衡量/可达成/相关/有时限）、目标受众画像（年龄/性别/收入/兴趣/行为习惯）、核心卖点与定位（USP，差异化）、渠道策略（线上：社交媒体/搜索引擎/内容营销；线下：活动/地推/合作）、内容策略（文案/视频/图文/直播）、预算分配（各渠道占比）、时间节点与排期（甘特图）、效果评估指标（ROI/转化率/获客成本/留存率）。A/B测试是优化营销方案的重要手段。"],
                    "商业/财务分析": ["财务分析是对企业财务状况和经营成果的系统评估。主要内容：财务报表分析（资产负债表/利润表/现金流量表）、财务比率分析（偿债能力：流动比率/速动比率；盈利能力：毛利率/净利率/ROE；运营效率：存货周转率/应收账款周转率）、杜邦分析体系、现金流分析（经营/投资/筹资活动）、预算与实际对比分析（差异率）、敏感性分析（关键变量变动对利润的影响）。分析结论要结合行业平均水平给出判断。"],
                    "商业/竞品分析": ["竞品分析是系统性地研究竞争对手的产品、策略和优劣势。分析维度：竞品基本信息（公司规模/融资情况/团队背景）、产品功能对比（核心功能/差异化功能/用户体验）、定价策略（免费/订阅/一次性/增值服务）、市场占有率与用户规模、技术架构与专利、营销渠道与获客方式、用户评价与口碑（应用商店评分/社交媒体反馈）、优势与劣势总结。常用工具：竞品矩阵（Feature Matrix）、用户旅程对比图。"],
                    "商业/融资计划": ["融资计划是企业向投资人阐述资金需求和投资回报的文档。关键内容：融资金额与估值（投前估值/投后估值）、资金用途明细（研发/市场/运营/人力占比）、预期里程碑（用这笔钱达成什么目标）、股权结构（现有股东/本轮投资人占比）、退出机制（IPO/并购/回购）、历史财务数据（如有）、未来3-5年财务预测、投资回报分析（IRR/ROI）。准备一份精炼的Elevator Pitch（1分钟电梯演讲）至关重要。"],
                    "商业/商业模式": ["商业模式描述企业如何创造价值、传递价值和获取价值。常见模式：B2B（企业对企业）/B2C（企业对消费者）/C2C（消费者对消费者）/B2B2C、订阅制（SaaS按月年收费）、平台模式（连接供需双方抽佣）、广告模式（免费内容+广告收入）、Freemium（免费基础+付费高级）、交易市场（撮合交易收手续费）。商业模式画布（Business Model Canvas）九要素：客户细分/价值主张/渠道/客户关系/收入来源/核心资源/关键业务/重要伙伴/成本结构。"],
                    # ============================================================
                    # 二、办公领域 (Office)
                    # ============================================================
                    "办公/会议纪要": ["会议纪要是对会议内容、决议和行动项的正式记录。标准格式：会议主题、时间地点、参会人员（出席/缺席/列席）、主持人、记录人、会议议程（逐项记录）、讨论要点（各方观点摘要）、决议事项（表决结果/通过事项）、行动计划（负责人/截止时间/交付物）、下次会议时间。写作要点：客观记录不掺杂个人观点、用词准确避免歧义、决议明确的用\u201c会议决定\u201d开头、行动项要有明确的责任人和时间节点。"],
                    "办公/工作总结": ["工作总结是对一段时间内工作成果和经验的系统梳理。结构：工作概述（时间段/岗位职责）、主要工作成果（按项目或指标分类，量化数据）、亮点与创新（突出贡献）、问题与不足（诚实复盘）、经验教训（可复用的方法论）、下阶段计划（目标/行动/时间表）、需要的支持与资源。写作要点：用STAR法则描述成果（情境/任务/行动/结果）、数据说话（完成率/增长率/排名）、避免流水账。"],
                    "办公/周报月报": ["工作周报/月报是向上级或团队汇报阶段性工作进展的书面材料。周报结构：本周完成事项（3-5项，简要说明+进度百分比）、下周计划（优先级排序）、遇到的问题与风险（需协调的资源）、个人思考与建议。月报结构：本月关键指标达成情况（KPI仪表盘）、重点项目进展（里程碑/偏差分析）、团队情况（人力/氛围/协作）、下月目标与资源需求。要点：简洁精炼（一页纸原则）、重点突出（二八法则）、问题前置（报忧不瞒报）。"],
                    "办公/邮件写作": ["商务邮件是职场沟通最常用的正式渠道。邮件结构：主题行（简明扼要概括邮件目的，不超过15字）、称呼（尊敬的XX/XX总/XX老师）、正文（开门见山说明目的，中间分点说明，结尾明确行动期望）、落款（姓名/职位/联系方式）。常见场景：请求类邮件（说明背景+请求事项+截止时间）、汇报类邮件（结论先行+数据支撑+下一步）、会议邀请（目的+议程+时间地点+参会准备）、感谢邮件（具体感谢事项+真诚表达）。注意：避免长篇大论、慎用全部回复、检查附件和收件人。"],
                    "办公/通知公告": ["通知公告是组织内部传达信息、发布决定的正式文书。类型：会议通知（时间/地点/议程/参会人员/准备事项）、活动通知（背景/时间地点/参与方式/注意事项）、人事通知（任免/调动/晋升，须注明生效日期）、制度通知（新规/修订/废止，附全文或概要）、紧急通知（事由/影响范围/应对措施/联系方式）。写作要点：标题明确（\u201c关于XXX的通知\u201d）、正文分段清晰（背景/事项/要求/联系方式）、日期和落款完整、紧急程度标注（紧急/普通/阅知）。"],
                    "办公/述职报告": ["述职报告是员工向组织汇报履职情况和业绩的正式文书。标准结构：基本情况（岗位/任职时间/职责范围）、履职情况（按职责逐项说明，量化成果）、重点业绩（突出贡献和典型案例）、能力提升（学习/培训/考证）、存在问题（自我剖析）、改进措施（具体可行）、未来规划（3-5年职业目标）。写作要点：实事求是（数据真实可查证）、重点突出（按重要性排序）、用具体案例支撑观点（如\u201c主导XX项目，将效率提升30%\u201d）、体现成长性（前后对比）。"],
                    "办公/PPT制作": ["PPT制作是职场中最重要的演示技能之一。设计原则：一页一主题（每页只传达一个核心观点）、少即是多（文字精简，用图表代替）、视觉层次（标题>要点>细节）、配色统一（主色+辅色≤3种，企业VI色优先）、字体规范（标题≤2种字体，正文统一）。结构：封面页（标题/副标题/汇报人/日期）、目录页（章节导航）、内容页（标题+要点+图表+结论）、过渡页（章节切换）、总结页（核心观点回顾）、致谢页。常用技巧：母版统一风格、SmartArt快速美化、动画简洁不花哨。"],
                    "办公/Word排版": ["Word文档排版是专业文档的基础技能。排版规范：标题层级（一级标题二号加粗，二级标题三号加粗，正文小四号）、字体选择（中文宋体/黑体，英文Times New Roman，正文统一）、行距（1.5倍行距，段前段后0.5行）、页边距（上下2.54cm，左右3.17cm，标准A4）、页码（目录页用罗马数字，正文用阿拉伯数字）、页眉页脚（页眉放章节标题，页脚放页码）。常用操作：样式统一设置（标题1/标题2/正文）、自动生成目录（插入→引用→目录）、表格与图片插入（题注+交叉引用）、分节符控制页码格式。"],
                    # ============================================================
                    # 三、校园领域 (Campus)
                    # ============================================================
                    "校园/运动会": ["运动会是学校年度大型综合性体育赛事，由学生会或体育部组织，面向全体师生。内容包括：比赛项目（田径类：100米/200米/400米/800米/1500米/4×100米/跳高/跳远/铅球；趣味类：拔河/三人四足/袋鼠跳/障碍跑；球类：篮球3v3/乒乓球/羽毛球）、开幕式（入场式/领导致辞/运动员宣誓/文艺表演）、闭幕式（颁奖/总结讲话）。组织要点：赛程表编排（避免冲突）、场地分配（田径场/篮球场/体育馆）、裁判培训、安全预案、医疗保障。时间通常为2-3天。"],
                    "校园/文艺晚会": ["校园文艺晚会是展示学生才艺和校园文化的重要活动。晚会类型：迎新晚会（9-10月）、元旦晚会（12月底）、毕业晚会（6月）、校庆晚会、主题晚会（如五四/国庆）。节目类型：歌舞类（独唱/合唱/舞蹈/乐队）、语言类（相声/小品/朗诵/话剧）、器乐类（独奏/合奏）、创意类（魔术/杂技/光影秀）。组织要点：海选与初审（2-3轮筛选）、节目单编排（节奏把控，高潮前置后置）、主持人选拔（形象/口才/应变）、舞台设计（灯光/音响/背景LED）、彩排（至少2次带妆联排）。"],
                    "校园/社团活动": ["大学社团活动是学生课外素质拓展的重要平台。社团类型：学术类（辩论社/英语角/读书会）、文艺类（音乐社/舞蹈社/话剧社/摄影社）、体育类（篮球社/羽毛球社/跑步社/瑜伽社）、公益类（志愿者协会/环保社/支教团）、科技类（编程社/机器人社/创新社）、创业类（创业俱乐部/商业模拟社）。活动形式：日常训练/排练/讨论、校内比赛/展示、校际交流/联谊、社会服务/实践。管理要点：社团注册与年审、经费申请与报销、活动审批（安全预案）、换届交接。"],
                    "校园/团课班会": ["团课和班会是高校思想政治教育的重要载体。团课主题：理想信念教育（党史/国史/团史）、爱国主义教育（英模事迹/国情教育）、社会主义核心价值观、团员意识教育、形势政策教育。班会主题：学风建设（考风考纪/学习方法）、安全教育（防诈骗/交通安全/消防）、心理健康（压力管理/人际交往）、职业规划（简历/面试/行业认知）、班级建设（班规/班委选举/评优评先）。流程设计：主题导入（视频/案例/故事5-10分钟）、主体环节（讨论/分享/互动/游戏30-40分钟）、总结升华（5-10分钟）。"],
                    "校园/志愿服务": ["大学生志愿服务是培养社会责任感的重要途径。服务类型：校内服务（迎新志愿者/图书馆义工/校园环保/大型活动志愿者）、社区服务（敬老院探访/社区支教/环保宣传/扶贫帮困）、大型赛事（马拉松/运动会/博览会志愿者）、专业服务（法律援助/医疗义诊/IT技术支持）。组织要点：招募与选拔（面试/培训）、岗前培训（礼仪/安全/技能）、服务时长记录（志愿汇/志愿中国平台）、评优与激励（星级志愿者/优秀志愿者表彰）。志愿精神：奉献、友爱、互助、进步。"],
                    "校园/报名申请": ["校园活动报名表是收集参与者信息的标准化工具。报名表要素：基本信息（姓名/学号/班级/学院/联系方式）、报名项目（单选/多选）、个人简介（特长/经历/获奖情况，限200字）、是否服从调剂、紧急联系人及电话。常见申请表类型：学生会/社团招新表（竞选职位/个人优势/工作计划）、评优评先申请表（学业成绩/综合表现/获奖情况）、活动参与表（项目选择/组队信息/特殊需求）。设计要点：必填项标注星号、说明填写规范、提供示例、设置截止时间。"],
                    "校园/学术论文": ["学术论文是大学生学术能力的重要体现。论文结构：标题（准确/简洁/20字以内）、摘要（目的/方法/结果/结论，200-300字）、关键词（3-5个）、引言（研究背景/文献综述/研究问题/论文结构）、文献综述（国内外研究现状/研究空白/本文贡献）、研究方法（数据来源/变量定义/模型设定）、实证分析（描述性统计/回归结果/稳健性检验）、结论与建议（主要发现/政策建议/研究局限/未来方向）、参考文献（GB/T 7714格式）。写作技巧：先写大纲再充实内容、图表要清晰标注、引用规范（查重率<15%）。"],
                    "校园/奖学金": ["奖学金申请是大学生获取资助和荣誉的重要途径。奖学金类型：国家奖学金（8000元/年，需成绩前10%+综合素质突出）、国家励志奖学金（5000元/年，需成绩前30%+家庭经济困难）、校级奖学金（一等/二等/三等，按综合测评排名）、社会奖学金（企业/校友设立，有特定条件）。申请材料：申请表（基本信息+获奖情况）、个人陈述（学业成绩/科研经历/社会实践/未来规划，1000字以内）、推荐信（辅导员/导师各一封）、成绩单（教务处盖章）、获奖证书复印件、论文/专利等成果证明。评审标准：学业成绩（占比60-70%）+综合素质（30-40%）。"],
                    "校园/考试复习": ["大学考试复习是取得好成绩的关键环节。复习策略：明确考试范围（划重点/老师提示/历年真题）、制定复习计划（按科目和剩余天数分配时间）、梳理知识框架（思维导图/知识树）、重点突破（高频考点/薄弱环节）、刷题巩固（历年真题/模拟题/课后习题）。备考方法：费曼学习法（用自己的话讲给别人听）、间隔重复（艾宾浩斯遗忘曲线）、主动回忆（盖住答案回忆知识点）、番茄工作法（25分钟专注+5分钟休息）。考试技巧：先易后难、时间分配（按分值比例）、检查（重点检查计算题和选择题）。"],
                    # ============================================================
                    # 四、政府领域 (Government)
                    # ============================================================
                    "政府/公文写作": ["政府公文是行政机关在行政管理过程中形成的具有法定效力和规范体式的文书。公文种类（15种）：决议/决定/命令/公报/公告/通告/意见/通知/通报/报告/请示/批复/议案/函/纪要。公文格式：版头（发文机关标志/发文字号/签发人）、主体（标题/主送机关/正文/附件说明/发文机关署名/成文日期/印章）、版记（抄送机关/印发机关/印发日期）。写作要求：一文一事（请示只写一个事项）、语言规范（准确/简洁/庄重/得体）、格式标准（GB/T 9704标准）。"],
                    "政府/工作报告": ["政府工作报告是政府向人大或上级机关汇报工作的正式文件。年度工作报告结构：上年工作回顾（主要指标完成情况/重点工作进展/存在问题和困难）、当年工作总体要求（指导思想/主要目标/基本原则）、当年重点工作任务（按领域分类：经济发展/民生保障/城市建设/生态环保/社会治理等）、加强政府自身建设（依法行政/效能提升/廉政建设）。写作要点：数据准确（与统计部门核实）、用词规范（如\u201c增长\u201dvs\u201c稳中有升\u201dvs\u201c大幅增长\u201d的区别）、亮点突出（标志性成果/创新举措）、实事求是（不回避问题）。"],
                    "政府/政策解读": ["政策解读是对政府发布的政策文件进行通俗化解释的说明性文本。解读类型：问答式（一问一答，针对公众关心的热点问题）、图表式（用可视化方式呈现政策要点）、案例式（通过具体案例说明政策如何落地）、专家解读（邀请学者/行业专家深度分析）。解读要素：政策出台背景（为什么出台）、政策核心内容（规定了什么）、政策亮点（与以往有什么不同）、政策影响（对谁有影响/有什么影响）、如何落实（具体操作步骤/咨询渠道）。注意事项：用群众听得懂的语言（避免官话套话）、突出获得感（惠民利企的实质内容）。"],
                    "政府/党建材料": ["党建材料是党组织开展工作的各类文书总称。常见类型：党建计划（年度/季度党建工作计划，含理论学习/组织生活/党员发展/作风建设等安排）、党建总结（成果/问题/改进方向）、组织生活会材料（对照检查材料/批评与自我批评/整改清单）、入党申请书（对党的认识/入党动机/个人经历/自我评价/决心表态）、思想汇报（理论学习体会/思想认识变化/实际行动表现）、党课讲稿（主题明确/理论联系实际/案例生动/时长控制在30-45分钟）、民主评议党员材料（自评/互评/组织评定）。"],
                    "政府/调研报告": ["调研报告是对某一问题或现象进行系统调查研究后形成的书面报告。结构：调研背景与目的（为什么调研/要解决什么问题）、调研方法（问卷/访谈/实地考察/文献研究，样本量/时间/范围）、调研对象（基本情况/样本特征）、调研发现（数据呈现/问题归纳/原因分析）、对策建议（具体/可行/分层次）、附件（问卷样本/访谈提纲/原始数据）。写作要点：问题导向（带着问题去调研）、数据说话（定量+定性分析结合）、案例佐证（典型个案/对比分析）、建议可操作（谁来做/做什么/什么时候做/怎么考核）。"],
                    # ============================================================
                    # 五、编码领域 (Coding)
                    # ============================================================
                    "编码/技术方案": ["技术方案文档是软件开发中用于描述系统设计和技术决策的文档。标准结构：背景与目标（业务需求/技术目标）、方案概述（整体架构图/核心流程）、技术选型（语言/框架/数据库/中间件，附带选型理由）、详细设计（模块划分/接口定义/数据模型/关键算法）、部署架构（服务器配置/网络拓扑/容灾方案）、性能指标（QPS/响应时间/并发数）、风险评估（技术风险/进度风险/依赖风险）。设计原则：高内聚低耦合、单一职责、开闭原则、接口隔离。"],
                    "编码/API文档": ["API文档是描述应用程序接口规范的文档。RESTful API文档要素：接口概述（功能说明/适用场景）、请求方法（GET/POST/PUT/DELETE/PATCH）、请求URL（Base URL + Endpoint）、请求参数（Query参数/Body参数/Header参数，含类型/必填/说明/示例）、响应格式（JSON/XML）、响应字段说明（字段名/类型/含义/示例值）、错误码说明（错误码/错误信息/可能原因/解决方法）、认证方式（Token/OAuth/API Key）、调用示例（curl/代码示例）。常用工具：Swagger/OpenAPI、Postman文档。"],
                    "编码/代码规范": ["代码规范是团队协作开发中统一代码风格和质量的标准。命名规范：类名大驼峰（PascalCase：UserController）、方法名小驼峰（camelCase：getUserById）、常量全大写下划线（UPPER_SNAKE：MAX_RETRY_COUNT）、私有变量下划线前缀（_privateField）。代码格式：缩进使用空格（4个或2个，统一）、每行不超过120字符、大括号不换行（K&R风格）。注释规范：文件头注释（作者/创建日期/功能描述）、函数注释（功能/参数/返回值/异常）、TODO标注（待办事项+负责人+日期）。Git提交规范：type(scope): description（feat: 新增用户登录功能）。"],
                    "编码/项目README": ["项目README是开源项目或内部项目的\u201c门面\u201d文档。标准结构：项目名称与Logo（居顶）、徽章（Badge：构建状态/版本/协议/下载量）、项目简介（一句话说明项目是什么，解决什么问题）、特性列表（核心功能亮点）、快速开始（安装依赖/配置/运行，3行命令搞定）、使用文档（API用法/配置说明/注意事项）、项目结构（目录树）、贡献指南（如何提Issue/PR/代码规范）、许可证（MIT/Apache/GPL）、致谢/引用。写作要点：站在使用者角度写（新用户5分钟能跑起来）、截图/GIF展示效果（一图胜千言）。"],
                    "编码/技术选型": ["技术选型是在多个技术方案中选择最优方案的系统决策过程。评估维度：功能满足度（是否满足业务需求）、性能（QPS/响应时间/资源消耗）、稳定性（Bug率/社区活跃度/版本迭代频率）、安全性（漏洞历史/安全审计/合规认证）、生态（插件/工具/文档/社区）、学习成本（团队技能匹配度）、运维成本（部署/监控/扩容）、许可证（开源协议兼容性）。决策流程：需求分析→候选方案调研→POC验证→决策矩阵打分→最终决策。常用工具：技术雷达（Technology Radar）、决策记录（ADR：Architecture Decision Record）。"],
                    "编码/架构设计": ["软件架构设计是对系统整体结构和组件关系的规划。架构模式：单体架构（简单/适合小团队）、微服务架构（独立部署/独立扩展/技术异构）、分层架构（表现层/业务层/持久层/数据库层）、事件驱动架构（消息队列/异步解耦）、CQRS（读写分离）、六边形架构（端口与适配器）。设计原则：SOLID原则、DRY（不重复自己）、KISS（保持简单）、YAGNI（你不会需要它）。架构文档：4+1视图（逻辑视图/进程视图/开发视图/物理视图+场景视图）。架构评审：可扩展性/可维护性/可靠性/安全性/性能。"],
                    # ============================================================
                    # 六、日常领域 (Daily)
                    # ============================================================
                    "日常/健康养生": ["健康养生是通过科学的生活方式维护身心健康。饮食方面：均衡膳食（蛋白质20%/脂肪25%/碳水55%）、多吃蔬菜水果（每天500g以上）、控制盐糖油（盐<6g/天，糖<25g/天）、足量饮水（每天1500-2000ml）。运动方面：每周至少150分钟中等强度有氧运动（快走/慢跑/游泳）、每周2次力量训练（深蹲/俯卧撑/引体向上）。睡眠方面：每天7-8小时、固定作息时间、睡前1小时远离电子屏幕。心理健康：正念冥想（每天10分钟）、社交互动（保持人际连接）、兴趣爱好（缓解压力）。常见误区：过度节食减肥、不吃早餐、熬夜补觉。"],
                    "日常/旅游攻略": ["旅游攻略是帮助旅行者规划行程的实用指南。攻略要素：目的地概览（最佳旅行季节/当地特色/文化禁忌）、交通方式（到达方式：飞机/高铁/自驾；市内交通：地铁/公交/打车/租车）、住宿推荐（区域选择/酒店类型/预算范围）、行程规划（3天/5天/7天行程模板，每日景点+交通+餐饮安排）、美食推荐（当地特色菜/人气餐厅/小吃街）、景点介绍（门票/开放时间/游玩时长/注意事项）、预算估算（交通/住宿/餐饮/门票/购物/应急）、实用贴士（天气/穿衣/语言/货币/APP推荐）。"],
                    "日常/美食推荐": ["美食推荐是通过文字描述激发读者食欲，帮助选择餐厅或菜品。推荐要素：菜名（准确/诱人）、外观描述（色泽/摆盘/份量）、口感描述（酥脆/嫩滑/Q弹/入口即化）、味道层次（前味/中味/后味/回味）、食材分析（新鲜度/产地/搭配原理）、烹饪手法（煎/炒/蒸/烤/炖的特点）、性价比（价格/份量/环境匹配度）、适合场景（一人食/朋友聚会/家庭聚餐/约会/商务宴请）。推荐餐厅时要包含：人均消费/推荐菜/排队情况/营业时间/地址/停车信息。注意：客观描述不夸大，如实说明不足。"],
                    "日常/理财规划": ["个人理财规划是系统管理个人或家庭财务以实现财务目标的过程。理财步骤：记账（了解收支结构，至少3个月数据）、设定目标（短期：旅行/购物；中期：买房/买车；长期：退休/子女教育）、建立应急基金（3-6个月生活费，放活期/货币基金）、保险配置（优先医疗险/意外险/重疾险，再考虑寿险/年金险）、投资组合（按风险承受能力配置：货币基金/债券/股票/基金/黄金，定期再平衡）、债务管理（优先还清高息债务如信用卡/网贷）。理财原则：先储蓄后消费（收入-储蓄=支出）、长期投资（时间是复利的朋友）、分散投资（不把所有鸡蛋放一个篮子）。"],
                    "日常/法律常识": ["日常生活法律常识是保护自身权益的基本法律知识。劳动合同：试用期（合同期限3个月-1年≤1个月，1-3年≤2个月，3年以上≤6个月）、社保缴纳（五险一金：养老/医疗/失业/工伤/生育+住房公积金）、加班费（工作日1.5倍/休息日2倍/法定节假日3倍）。消费者权益：七天无理由退货（网购，特殊商品除外）、假一赔三（欺诈行为，最低500元）、食品安全（假一赔十，最低1000元）。租房：押金不超过1个月租金、房东不得随意涨租（合同期内）、退租押金退还（无损坏）。交通事故：拍照留证/报警/保险报案/不私了（有人伤）。"],
                    "日常/人际关系": ["人际关系是个人在社会中与他人建立和维持联系的能力。沟通技巧：积极倾听（眼对眼/点头/不打断/复述确认）、非暴力沟通（观察-感受-需要-请求四步法）、赞美具体化（\u201c你这个方案的数据分析很到位\u201d比\u201c你做得很好\u201d更好）、批评对事不对人（\u201c这个报告有3处数据错误\u201d而非\u201c你太粗心了\u201d）。冲突处理：先处理情绪再处理问题、寻找共同利益点、用\u201c我\u201d而非\u201c你\u201d开头（\u201c我感到压力很大\u201dvs\u201c你总是催我\u201d）。职场关系：尊重上级（主动汇报/解决问题）、团结同事（协作共赢/不传闲话）、帮助新人（经验分享/耐心指导）。边界感：不越界介入他人私事、学会说\u201c不\u201d。"],
                    # ============================================================
                    # 七、活动策划领域 (Event Planning)
                    # ============================================================
                    "活动策划/运动会": ["运动会策划方案需包含：活动背景与目的（增强体质/促进交流/丰富校园文化）、活动主题（如\u201c青春飞扬 运动无限\u201d）、时间地点（日期/场地/备用场地）、参赛对象（分组：男/女/混合/教职工/学生）、比赛项目设置（田径类/趣味类/球类，每项规则说明）、赛程安排（开幕式-各项目比赛-闭幕式，具体时间表）、组织架构（组委会/裁判组/检录组/器材组/医疗组/宣传组/后勤组）、奖项设置（单项奖/团体奖/精神文明奖）、预算明细（器材/奖品/宣传/医疗/餐饮/应急预备金）、安全预案（天气/受伤/突发疾病/秩序维护）、报名方式（线上/线下/截止时间）。关键：赛程编排避免同一选手多项时间冲突，田赛和径赛穿插进行。"],
                    "活动策划/文艺晚会": ["文艺晚会策划方案需包含：晚会主题与基调（如\u201c青春绽放 梦想起航\u201d）、时间地点（具体日期/演出场地/彩排时间）、节目征集（海选-初审-复审-终审，每轮筛选比例）、节目类型配比（歌舞类40%/语言类30%/器乐类15%/创意类15%）、节目单编排（开场大气\u2192中间有起伏\u2192高潮\u2192压轴\u2192结尾温馨）、主持人（2男2女，主持稿+串词准备）、舞台设计（背景LED屏/灯光方案/音响方案/道具清单）、宣传推广（海报/推文/短视频预热）、嘉宾邀请（领导/校友/媒体）、预算（舞台搭建/灯光音响/服装化妆/奖品/宣传物料/工作餐）、应急预案（设备故障/演员缺席/停电/安全问题）。彩排至少2次，带妆联排1次。"],
                    "活动策划/团建活动": ["团建活动策划方案需包含：活动目的（增强凝聚力/提升沟通/释放压力/新人融入）、活动类型（户外拓展：攀岩/定向越野/漂流；室内游戏：密室逃脱/桌游/剧本杀；创意型：手工DIY/厨艺比拼/微电影拍摄）、时间地点（1天或2天1夜，交通便利的场地）、参与人员（分组方式：随机/部门/跨部门混合）、活动流程（破冰游戏→团队挑战→午餐→主题项目→总结分享→颁奖）、教练/主持（专业拓展教练或内部组织者）、物资准备（道具/服装/急救包/饮用水/零食）、预算（场地/教练/交通/餐饮/道具/奖品/保险）、安全措施（购买意外险/安全须知/急救人员）。活动设计原则：全员参与（照顾体力弱者）、挑战适度（有难度但可完成）、复盘总结（每个环节后分享感受）。"],
                    "活动策划/开业庆典": ["开业庆典策划方案需包含：活动主题（品牌调性+开业主题，如\u201c扬帆起航 共创辉煌\u201d）、时间地点（吉日吉时+具体地址+交通指引）、嘉宾邀请（领导/合作伙伴/媒体/客户代表，提前2周发邀请函）、活动流程（签到留影\u2192主持人开场\u2192领导致辞\u2192剪彩/揭牌仪式\u2192产品体验/参观\u2192答谢午宴/茶歇\u2192伴手礼发放）、场地布置（门头装饰/签到区/主舞台/展示区/休息区/就餐区）、物料准备（请柬/背景板/横幅/花篮/绶带/剪刀/托盘/红绸/伴手礼/宣传册）、宣传推广（预热海报/朋友圈/本地媒体/网红探店）、预算（场地/布置/餐饮/礼品/宣传/演出/应急）。注意事项：音响设备提前调试、剪彩环节彩排、天气预案（户外场地备雨棚）。"],
                    "活动策划/发布会": ["发布会（新品发布/新闻发布）策划方案需包含：发布主题（核心卖点一句话概括）、时间地点（避开节假日和竞品发布会，选择交通便利的酒店/会展中心）、目标受众（媒体/行业KOL/经销商/合作伙伴/核心用户）、活动流程（签到入场→暖场视频→主持人开场→领导致辞→产品发布/演示→嘉宾分享→媒体问答→体验环节→结束/答谢）、现场布置（主舞台/LED大屏/产品展示区/体验区/媒体区/茶歇区）、物料准备（邀请函/新闻稿/产品资料/伴手礼/工作证/指引牌）、演讲彩排（至少3次，控制20-30分钟/人）、媒体邀请（提前1个月发邀请函，提前3天确认）、预算（场地/搭建/AV设备/嘉宾/媒体/餐饮/礼品/宣传）。关键：核心信息反复强化（发布不超过3个核心卖点）、QA环节预设问题回答。"],
                    "活动策划/培训活动": ["培训活动策划方案需包含：培训需求分析（能力差距/业务需求/员工诉求）、培训目标（知识/技能/态度，可量化可评估）、培训对象（岗位/层级/人数/前置条件）、培训形式（线下授课/线上直播/翻转课堂/工作坊/沙盘模拟/案例研讨）、课程大纲（模块化设计，每个模块含目标/内容/时长/教学方法）、讲师选择（内部讲师/外部专家，需提供讲师简介和往期评价）、时间安排（避开业务高峰期，半天/1天/2天，每45分钟休息10分钟）、场地设备（教室/投影/白板/分组桌椅/茶歇/网络）、预算（讲师费/场地/教材/茶歇/交通/住宿/证书）、效果评估（柯氏四级评估：反应/学习/行为/结果，培训后1个月/3个月跟踪）。"],
                    # ============================================================
                    # 八、通用/基础 (General)
                    # ============================================================
                    "AI": ["人工智能是模拟人类智能的技术科学，包括机器学习、自然语言处理等。"],
                    "人工智能": ["人工智能技术快速发展，大语言模型具备强大的上下文理解与生成能力。"],
                    "WPS": ["WPS Office是金山办公开发的国产办公软件套件。"],
                    "方案": ["方案设计需要包含需求分析、目标设定、实施步骤、风险评估等。"],
                    "策划": ["活动策划方案通常包含：活动背景与目的、活动主题与名称、活动时间与地点、活动对象、活动流程、组织架构与人员分工、预算明细、安全预案与应急措施、预期效果与评估方式。"],
                    "系统": ["系统设计需要考虑可扩展性、可靠性、安全性和性能。"],
                    "项目管理": ["项目管理包括启动、规划、执行、监控和收尾五个阶段。"],
                    "预算": ["活动预算规划需列出详细费用明细表：场地租赁费、设备租赁费、物料采购费（横幅/海报/号码布）、奖品费（奖杯/奖牌/证书）、饮用水和医疗用品、工作人员餐补。预算应在总费用的10%预留应急资金。"],
                    "人员安排": ["人员安排包括：总指挥1人、副总指挥2人、裁判组（每项目2-3人）、计时计分组（3-5人）、检录组（3-5人）、场地器材组（5-8人）、宣传报道组（3-5人）、医疗急救组（2-3人）、秩序维护组（5-10人）、后勤保障组（5-8人）。所有人员需提前培训并明确职责。"],
                    "比赛项目": ["常见的校园运动会比赛项目包括：田径类（100米、200米、400米、800米、1500米、4×100米接力、跳高、跳远、铅球）、趣味类（拔河、三人四足、袋鼠跳、障碍跑）、球类（篮球3v3、足球点球、乒乓球、羽毛球）。每个项目需要安排裁判、计时员、记录员。"],
                    "活动策划": ["活动策划核心要素包括：活动目标与主题、时间地点选择、流程安排、人员分工（总负责人、执行组、宣传组、后勤组）、预算规划（场地费、物料费、奖品费、餐饮费）、风险评估与应急预案。"],
                    "运动会": ["运动会是学校或单位组织的综合性体育赛事，包括田径（跑步、跳远、铅球等）、球类（篮球、足球、乒乓球等）、趣味项目（拔河、接力等）。组织运动会需要：确定比赛项目、制定赛程表、安排裁判和工作人员、准备场地器材、制定安全预案。"],
                    "校园": ["校园活动通常包括运动会、文艺晚会、社团招新、学术讲座、志愿服务等。校园运动会是学校年度大型体育活动，由学生会或体育部组织，面向全体师生。"],
                    "general": ["持续学习是个人成长的关键，良好的沟通是团队协作的基础。"],
                }

            def search_by_keywords(self, keywords, limit=5):
                results = []
                for kw in keywords:
                    for kb_key, items in self._items.items():
                        if kw.lower() in kb_key.lower():
                            results.extend(items[:limit])
                return list(set(results))[:limit * 2]

            def get_all_keywords(self):
                return list(self._items.keys())

            def search(self, query, limit=5):
                results = {}
                for keyword, items in self._items.items():
                    if query.lower() in keyword.lower():
                        results[keyword] = items[:limit]
                return results

            def enhance_content(self, content, keywords):
                items = self.search_by_keywords(keywords)
                if not items:
                    return content
                return f"【知识增强】\n{content}\n\n参考知识:\n" + "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))

            def get_knowledge_stats(self):
                return {"total_keywords": len(self._items), "total_items": sum(len(v) for v in self._items.values())}

        return FallbackKnowledgeService()

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"知识检索与需求分析: {input_data.content[:50]}...")

        try:
            # 0. 读取对话历史（上下文记忆）— 用于理解指代和跟进问题
            conversation_history = ""
            memory_context = ""
            brain_context = ""
            if input_data.context and isinstance(input_data.context, dict):
                history = input_data.context.get("history", [])
                if isinstance(history, list) and history:
                    history_lines = []
                    for h in history[-3:]:
                        if isinstance(h, dict):
                            history_lines.append(f"用户: {h.get('user', '')}")
                            history_lines.append(f"助手: {str(h.get('assistant', ''))[:200]}")
                    if history_lines:
                        conversation_history = "\n".join(history_lines)
                        logger.info(f"Knowledge Agent: 提取到 {len(history)} 条对话历史，conversation_history 长度={len(conversation_history)}")
                    else:
                        logger.info(f"Knowledge Agent: history 列表存在但为空或不合法，history={history}")
                else:
                    logger.info(f"Knowledge Agent: context 中无 history 或 history 不是列表，context keys={list(input_data.context.keys()) if isinstance(input_data.context, dict) else 'N/A'}")

                # V3: 读取长期记忆上下文（MemoryStore）和用户画像上下文（PersonalBrain）
                memory_context = input_data.context.get("memory_context", "")
                brain_context = input_data.context.get("brain_context", "")
                if memory_context:
                    logger.info(f"Knowledge Agent: 获取到长期记忆上下文，长度={len(memory_context)}")
                if brain_context:
                    logger.info(f"Knowledge Agent: 获取到用户画像上下文，长度={len(brain_context)}")

            # 1. 检测身份查询（M1 修复：移到视觉识别之前，避免带图片问"你是谁"时浪费 GPU）
            if self._detect_identity_query(input_data.content):
                return self._handle_identity_query(input_data.content, conversation_history)

            # V3.2: 视觉识别 — 检测 context.images，有图片则先调用 VisionPlugin
            image_descriptions: List[str] = []
            vision_metadata = {}
            if input_data.context and isinstance(input_data.context, dict):
                images = input_data.context.get("images", [])
                if isinstance(images, list) and images:
                    logger.info(
                        f"Knowledge Agent: 检测到 {len(images)} 张图片，启动视觉识别"
                    )
                    # V3.2 修复：提前初始化 ws_mgr，避免 except 分支引用未定义变量
                    ws_mgr = None
                    try:
                        import asyncio
                        from core.llm.vision_plugin import VisionPlugin
                        from core.workflow.service import _get_ws_manager

                        plugin = VisionPlugin()
                        ws_mgr = _get_ws_manager()

                        # V3.2 修复：使用 get_running_loop() 替代弃用的 get_event_loop()
                        # 在协程上下文中 get_running_loop() 是推荐做法（Python 3.10+）
                        loop = asyncio.get_running_loop()

                        def _on_progress(current: int, total: int, phase: str, status: str):
                            if ws_mgr:
                                asyncio.run_coroutine_threadsafe(
                                    ws_mgr.broadcast_vision_progress({
                                        "current": current,
                                        "total": total,
                                        "status": status,
                                        "phase": phase,
                                    }),
                                    loop,
                                )

                        # 在线程池中执行同步的视觉识别（避免阻塞事件循环）
                        # V3.2: 主模型重载已在 recognize_images 内部完成（锁保护下），
                        # 无需再外部调用 plugin.reload_main_model()
                        image_descriptions = await asyncio.to_thread(
                            plugin.recognize_images,
                            images_base64=images,
                            on_progress=_on_progress,
                        )

                        # 推送完成状态
                        if ws_mgr:
                            await ws_mgr.broadcast_vision_progress({
                                "current": len(images),
                                "total": len(images),
                                "status": "视觉识别完成",
                                "phase": "completed",
                            })

                        vision_metadata = {
                            "image_count": len(images),
                            "vision_model": plugin.vision_model,
                            "descriptions_length": [len(d) for d in image_descriptions],
                        }
                        logger.info(
                            f"Knowledge Agent: 视觉识别完成，"
                            f"识别 {len(image_descriptions)} 张图片"
                        )
                    except Exception as e:
                        logger.error(
                            f"Knowledge Agent: 视觉识别失败: {e}",
                            exc_info=True
                        )
                        # V3.2 修复：识别失败时为每张图片生成对应的失败描述
                        # （保持与图片数量一致，避免 Writer Agent 引用时错位）
                        fail_msg = f"[视觉识别失败: {str(e)}]"
                        image_descriptions = [fail_msg] * len(images)
                        vision_metadata = {
                            "error": str(e),
                            "image_count": len(images),
                            "failed": True,
                        }
                        # V3.2: 推送失败状态到前端，避免进度条卡住
                        if ws_mgr:
                            try:
                                await ws_mgr.broadcast_vision_progress({
                                    "current": len(images),
                                    "total": len(images),
                                    "status": f"视觉识别失败: {str(e)}",
                                    "phase": "error",
                                })
                            except Exception as push_err:
                                logger.warning(
                                    f"Knowledge Agent: 推送失败状态时异常: {push_err}"
                                )

            # 2. V2.1: TaskClassifier — 先 TaskType 分类
            task_profile = self.task_classifier.classify(input_data.content)
            task_type_v2 = task_profile.task_type.value
            logger.info(f"Knowledge Agent: TaskType={task_type_v2}, "
                       f"confidence={task_profile.confidence:.2f}, "
                       f"matched={task_profile.matched_patterns[:3]}")

            # 3. Skill Engine: 意图分析 + 领域检测（参考 TaskProfile 的 domain 提示）
            intent = self.intent_analyzer.analyze(input_data.content)
            skill_path = intent.skill_path
            domain = task_profile.domain or intent.domain  # TaskProfile 优先
            logger.info(f"Knowledge Agent: domain={domain}, skill_path={skill_path}, confidence={intent.confidence}")

            # 4. 提取关键词（优先从 Skill 数据，fallback 到硬编码）
            keywords = self._extract_keywords_skill(input_data.content, skill_path)

            # 5. 从 MySQL 知识库检索
            knowledge_items = self.knowledge_service.search_by_keywords(keywords, limit=8)

            # V3.2 修复：从 Skill Graph 检索自学习知识节点
            # Decomposer 已在 WorkflowService 中匹配到 Skill Graph 节点（含自学习节点），
            # 但之前 Knowledge Agent 不读取 decomposer_result，导致自学习知识无法传递给 Writer。
            # 现在将匹配到的节点（特别是自学习的 concept 类型）注入 knowledge_items，
            # 让 Writer Agent 能通过现有的 knowledge_items 链路使用这些知识。
            #
            # V2.4 (2026-07-30): 暴露 skill_graph 信号供 Judge 做质量补救加成
            #   - skill_graph_used: 是否注入了自学习知识
            #   - skill_graph_contents: 注入的 content 文本列表（供 Judge 检测 Writer 是否引用）
            skill_graph_used = False
            skill_graph_contents = []
            if input_data.context and isinstance(input_data.context, dict):
                decomposer_result = input_data.context.get("decomposer_result", {})
                if decomposer_result and decomposer_result.get("matched_nodes"):
                    skill_graph_items = []
                    seen_ids = set()
                    # 去重：避免与 SQLite 知识库已有条目重复
                    for item in knowledge_items:
                        if isinstance(item, dict):
                            seen_ids.add(item.get("keyword", ""))
                            seen_ids.add(item.get("content", "")[:50])
                    for node in decomposer_result["matched_nodes"]:
                        node_id = getattr(node, "id", "")
                        node_name = getattr(node, "name", "")
                        node_desc = getattr(node, "description", "")
                        # 跳过无描述的节点（如纯分类节点）和重复节点
                        if not node_desc or node_id in seen_ids or node_name in seen_ids:
                            continue
                        # 只注入自学习节点（有 description 且非空）或 concept 类型
                        node_type = getattr(node, "node_type", "")
                        if node_type == "concept" or "自动提取" in str(node_desc):
                            sg_content = f"[自学习知识] {node_name}: {node_desc}"
                            skill_graph_items.append({
                                "keyword": node_name,
                                "content": sg_content,
                                "source": "skill_graph",
                                "domain": getattr(node, "domain", ""),
                            })
                            seen_ids.add(node_id)
                            seen_ids.add(node_name)
                            # V2.4: 收集 content 供 Judge 检测引用
                            skill_graph_contents.append(sg_content)
                    if skill_graph_items:
                        knowledge_items = list(knowledge_items) + skill_graph_items
                        skill_graph_used = True
                        logger.info(
                            f"Knowledge Agent: 从 Skill Graph 注入 "
                            f"{len(skill_graph_items)} 条自学习知识 "
                            f"(nodes: {[it['keyword'] for it in skill_graph_items]})"
                        )

            # ============================================================
            # V3.5 (2026-07-31): Web Search + 时效性知识库自学习
            # ------------------------------------------------------------
            # 检测时效性场景（旅游/美食/地点/天气/评价）:
            # - 命中 fresh 条目 → 直接注入 knowledge_items
            # - 无 fresh 条目 → 触发 Web Search + DeepSeek 摘要 → 入库 → 注入
            # - 30天TTL过期 → 自动标记 stale，再次提问触发刷新
            #
            # V3.5 扩展 (抱怨澄清): 用户在抱怨弹窗中选择"网络搜索再回答"时，
            # 前端传入 force_web_search=True，跳过场景检测和 fresh 命中，
            # 强制联网搜索最新信息（适用于信息过时/不准确的抱怨场景）
            # ============================================================
            force_web_search = False
            if input_data.context and isinstance(input_data.context, dict):
                force_web_search = bool(input_data.context.get("force_web_search", False))

            timely_result = await self._try_timely_knowledge(
                user_input=input_data.content,
                knowledge_items=knowledge_items,
                force=force_web_search,
            )
            web_search_used = timely_result.get("used", False)
            web_search_performed = timely_result.get("web_search_performed", False)
            web_search_source = timely_result.get("source", "")
            web_search_category = timely_result.get("category", "")
            web_search_stored = timely_result.get("stored_to_db", False)

            # ============================================================
            # V4.0 (2026-08-17): CodeMunch 代码检索
            # ------------------------------------------------------------
            # 检测代码相关查询（函数/类/方法/实现等关键词）:
            # - 命中 → 调用 jCodeMunch MCP 搜索符号并提取源代码
            # - 注入 knowledge_items 供 Writer Agent 使用
            # - 失败降级：不影响主流程，仅记录日志
            # ============================================================
            code_munch_result = await self._try_code_munch(
                user_input=input_data.content,
                knowledge_items=knowledge_items,
            )
            code_munch_used = code_munch_result.get("used", False)
            code_munch_symbols = code_munch_result.get("symbols_count", 0)
            code_munch_sources = code_munch_result.get("sources_count", 0)

            # 6. 判断任务类型（兼容旧 task_type + 新 task_type_v2）
            legacy_task_type = self._determine_task_type(input_data.content, keywords)

            # 7. 提取需求点
            requirements = self._extract_requirements(input_data.content)

            # 8. 生成结构化摘要
            summary_result = {
                "task": self._extract_task(input_data.content),
                "original_question": input_data.content,
                "keywords": keywords,
                "knowledge_items": knowledge_items,
                "knowledge_count": len(knowledge_items),
                "requirements": requirements,
                "outline": [],
                "task_type": legacy_task_type,
                "summary": self._generate_summary(input_data.content, keywords, requirements),
                # Skill Engine V2: 传递给下游 Agent
                "skill_path": skill_path,
                "skill_domain": domain,
                "skill_confidence": round(intent.confidence, 2),
                # V2.1: TaskClassifier 输出
                "task_type_v2": task_type_v2,
                "task_data": task_profile.to_dict(),
                # 上下文记忆：对话历史（供 Writer Agent 理解指代和跟进）
                "conversation_history": conversation_history,
                # V3: 长期记忆和用户画像（供 Writer Agent 个性化生成）
                "memory_context": memory_context,
                "brain_context": brain_context,
                # V3.2: 视觉识别结果（供 Writer Agent 引用图片内容）
                "image_descriptions": image_descriptions,
                # V2.4: 自学习知识信号（供 Judge Agent 做质量补救加成判断）
                "skill_graph_used": skill_graph_used,
                "skill_graph_contents": skill_graph_contents,
                # V3.5: Web Search + 时效性知识库信号
                "web_search_used": web_search_used,
                "web_search_performed": web_search_performed,
                "web_search_source": web_search_source,
                "web_search_category": web_search_category,
                "web_search_stored": web_search_stored,
                # V4.0: CodeMunch 代码检索信号
                "code_munch_used": code_munch_used,
                "code_munch_symbols": code_munch_symbols,
                "code_munch_sources": code_munch_sources,
            }

            await self._set_status("idle")
            await self._set_current_task(None)

            return AgentOutput(
                content=json.dumps(summary_result, ensure_ascii=False, indent=2),
                success=True,
                message="知识检索与需求分析完成",
                metadata={
                    "knowledge_count": len(knowledge_items),
                    "matched_keywords": keywords,
                    "task_type": legacy_task_type,
                    "task_type_v2": task_type_v2,
                    "requirement_count": len(requirements),
                    "model_used": self.local_model,
                    # Skill Engine V2
                    "skill_path": skill_path,
                    "skill_domain": domain,
                    "skill_confidence": round(intent.confidence, 2),
                    # V3.2: 视觉识别元数据
                    **vision_metadata,
                    # V3.5: Web Search 元数据（供前端展示来源标记）
                    "web_search_used": web_search_used,
                    "web_search_performed": web_search_performed,
                    "web_search_source": web_search_source,
                    "web_search_category": web_search_category,
                    # V4.0: CodeMunch 元数据
                    "code_munch_used": code_munch_used,
                    "code_munch_symbols": code_munch_symbols,
                    "code_munch_sources": code_munch_sources,
                },
                model_used=self.local_model
            )

        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(content="", success=False, message=str(e))

    def _detect_identity_query(self, content: str) -> bool:
        content_lower = content.lower()
        for kw in self.system_keywords:
            if kw.lower() in content_lower:
                return True
        return False

    def _handle_identity_query(self, query: str, conversation_history: str = "") -> AgentOutput:
        from shared.platform import PLATFORM_NAME, PLATFORM_DESCRIPTION
        identity_result = {
            "task": "平台身份查询",
            "original_question": query,
            "keywords": ["身份查询"],
            "knowledge_items": [],
            "knowledge_count": 0,
            "requirements": [],
            "outline": [],
            "task_type": "简单对话",
            "summary": f"用户询问 {PLATFORM_NAME} 平台身份信息，这是一个基础身份问答",
            # 上下文记忆：保留对话历史（修复：之前漏掉了此字段）
            "conversation_history": conversation_history,
        }
        return AgentOutput(
            content=json.dumps(identity_result, ensure_ascii=False),
            success=True,
            message="身份查询识别完成",
            metadata={
                "knowledge_type": "identity",
                "knowledge_count": 0,
                "matched_keywords": [],
                "enhanced": False,
                "model_used": self.local_model
            }
        )

    def _extract_keywords_skill(self, content: str, skill_path: List[str]) -> List[str]:
        """Skill Engine V2: 从 Skill Book 关键词库提取关键词（替代硬编码）"""
        keywords_found = []
        content_lower = content.lower()

        # 优先从 Skill 数据提取关键词
        try:
            skill_kw = self.skill_manager.get_keywords(skill_path)
            for category, kw_map in skill_kw.items():
                if isinstance(kw_map, dict):
                    for kw, aliases in kw_map.items():
                        all_terms = [kw]
                        if isinstance(aliases, list):
                            all_terms.extend(aliases)
                        if any(term.lower() in content_lower for term in all_terms):
                            if kw not in keywords_found:
                                keywords_found.append(kw)
        except Exception as e:
            logger.debug(f"Skill keyword extraction failed: {e}, using fallback")

        # Fallback: 硬编码关键词（保留兼容性）
        if not keywords_found:
            for kw in self.common_keywords:
                if kw.lower() in content_lower and kw not in keywords_found:
                    keywords_found.append(kw)

        # 数据库关键词匹配
        try:
            db_keywords = self.knowledge_service.get_all_keywords()
            for kw in db_keywords:
                if kw.lower() in content_lower and kw not in keywords_found:
                    keywords_found.append(kw)
        except Exception:
            pass

        return keywords_found[:12]

    def _extract_keywords(self, content: str) -> List[str]:
        """提取关键词（fallback 方法，保留向后兼容）"""
        return self._extract_keywords_skill(content, ["root", "daily"])

    def _determine_task_type(self, content: str, keywords: List[str]) -> str:
        combined = (content + " " + " ".join(keywords)).lower()

        # V2.5 (2026-07-30): 优先检测质疑/反馈/纠错类输入
        # 这类输入即使用户提到了"方案/报告"等词，也不应归类为对应任务类型
        # 修复场景: "针对你刚才的方案我提出质疑" → 不应归类为"方案设计"
        challenge_signals = [
            "质疑", "提出质疑", "核实", "查无此", "核对",
            "发现问题", "不少问题", "存在问题", "关键信息",
            "信息有误", "信息错误", "信息不准确", "信息过时",
            "严重不符", "地址不符", "名称不符",
            "不准确", "不真实", "不可靠", "可信度低",
            "针对你刚才的", "针对你的回答", "你之前的", "你刚才说的",
            "你给的", "你写的内容", "这份攻略", "这份方案", "这份报告",
        ]
        for signal in challenge_signals:
            if signal in combined:
                logger.info(f"Knowledge Agent: 检测到质疑/反馈信号 '{signal}' → 归类为通用任务")
                return "通用任务"

        if any(kw in combined for kw in ["活动", "策划", "组织", "赛事", "运动会", "晚会", "马拉松"]):
            return "活动策划"
        if any(kw in combined for kw in ["方案", "设计", "规划", "系统", "架构"]):
            return "方案设计"
        if any(kw in combined for kw in ["报告", "文档", "分析", "评估"]):
            return "分析报告"
        if any(kw in combined for kw in ["写", "生成", "撰写", "创作", "演讲稿", "发言", "致辞"]):
            return "文档撰写"

        return "通用任务"

    def _extract_task(self, content: str) -> str:
        patterns = [
            r"(生成|创建|设计|规划|撰写|制定|编写|分析|评估)\s+(.+?)(。|？|\n|$)",
            r"(需要|想要|希望|需求|请求)\s+(.+?)(。|？|\n|$)"
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return f"{match.group(1)}{match.group(2)}"

        clean = re.sub(r'【.*?】', '', content).strip()
        return clean[:80] if len(clean) > 80 else clean

    def _extract_requirements(self, content: str) -> List[str]:
        requirements = []
        patterns = [
            (r"(需要|必须|应该|应当)\s+(.+?)(。|？|\n|$)", "需要"),
            (r"(确保|保证)\s+(.+?)(。|？|\n|$)", "确保"),
            (r"(包含|包括)\s+(.+?)(。|？|\n|$)", "包含"),
            (r"(符合|遵循)\s+(.+?)(。|？|\n|$)", "符合"),
        ]
        for pattern, prefix in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                req = f"{prefix}{match[1]}"
                if req not in requirements and len(req) > 3:
                    requirements.append(req)
        return requirements[:8]

    def _generate_summary(self, question: str, keywords: List[str], requirements: List[str]) -> str:
        q = question[:60] + "..." if len(question) > 60 else question
        parts = [f"用户需求：{q}"]
        if keywords:
            parts.append(f"关键词：{', '.join(keywords[:5])}")
        if requirements:
            parts.append(f"需求点：{len(requirements)}项")
        return " | ".join(parts)