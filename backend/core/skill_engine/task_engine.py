"""
Task Engine V2.1 — 任务类型分类器（Task Classifier）

核心功能：
- 在 Skill Path 导航之前，先判定用户查询的 TaskType
- 使用规则引擎（关键词匹配）进行快速、确定性分类
- 不依赖 LLM，保证分类稳定性和低延迟

TaskType 定义：
  QA:       问答类 — "Git是什么？"、"Docker有什么优势？"
  CODING:   编码类 — "写一个快速排序"、"Python读取文件示例"
  WRITING:  写作类 — "写一首诗"、"写一封情书"、"写一篇日记"
  PLANNING: 规划类 — "设计方案"、"写报告"、"制定计划"、"策划活动"
  ANALYSIS: 分析类 — "SWOT分析"、"影响分析"、"评估"
  CHAT:     闲聊类 — "你好"、"天气怎么样"、"推荐电影"

分类优先级：CODING > PLANNING > ANALYSIS > WRITING > QA > CHAT
"""

import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


# ============================================================
# TaskType 枚举
# ============================================================

class TaskType(Enum):
    """任务类型枚举"""
    QA = "qa"             # 问答类（知识问答、概念解释）
    CODING = "coding"     # 编码类（写代码、算法实现）
    WRITING = "writing"   # 写作类（创意写作、诗歌、日记）
    PLANNING = "planning" # 规划类（方案、报告、计划、策划）
    ANALYSIS = "analysis" # 分析类（SWOT、影响分析、评估）
    CHAT = "chat"         # 闲聊类（问候、天气、推荐）


# ============================================================
# TaskProfile 数据模型
# ============================================================

@dataclass
class TaskProfile:
    """任务分类结果 — 在 Agent 之间传递的标准化任务描述"""
    task_id: str = "general"
    task_type: TaskType = TaskType.CHAT
    domain: str = "daily"
    skill_path: List[str] = field(default_factory=lambda: ["root", "daily"])
    confidence: float = 0.5
    complexity: float = 0.0  # V3: 任务复杂度 (0.0-1.0)，供 CognitiveController 使用
    raw_query: str = ""
    matched_patterns: List[str] = field(default_factory=list)

    # Execution hints
    handler: str = ""           # 建议的 Handler 名称
    review_mode: str = ""       # 建议的 Review 模式
    cloud_threshold: float = 0.65  # 云端阈值
    template: bool = False      # 是否允许模板
    allow_followup: bool = True # 是否允许追问
    min_length: int = 40        # 最小回答长度建议

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "domain": self.domain,
            "skill_path": self.skill_path,
            "confidence": self.confidence,
            "complexity": self.complexity,
            "raw_query": self.raw_query,
            "matched_patterns": self.matched_patterns,
            "handler": self.handler,
            "review_mode": self.review_mode,
            "cloud_threshold": self.cloud_threshold,
            "template": self.template,
            "allow_followup": self.allow_followup,
            "min_length": self.min_length,
        }


# ============================================================
# TaskClassifier 规则引擎
# ============================================================

class TaskClassifier:
    """任务类型分类器 — 规则引擎驱动，不依赖 LLM

    分类策略（优先级从高到低）：
    1. CODING: 检测编码相关关键词（算法、函数、代码、编程语言）
    2. PLANNING: 检测规划类关键词（方案、报告、计划、策划）
    3. ANALYSIS: 检测分析类关键词（SWOT、分析、评估、影响）
    4. WRITING: 检测创意写作关键词（写诗、情书、日记、故事）
    5. QA: 检测问答类关键词（是什么、如何、怎么、为什么）
    6. CHAT: 默认兜底
    """

    # 编码类关键词
    CODING_KEYWORDS = [
        # 编程语言
        "python", "java", "javascript", "typescript", "golang", "rust", "c++", "c语言",
        "ruby", "php", "swift", "kotlin", "scala", "shell", "bash",
        # 算法与数据结构
        "算法", "排序", "搜索", "二叉树", "链表", "哈希", "递归", "动态规划",
        "二分查找", "贪心", "回溯", "分治", "图论", "堆栈", "队列",
        # 编码指令
        "写一个函数", "实现一个", "写代码", "编写一个", "编程实现",
        "示例代码", "代码示例", "用代码", "写段代码", "代码实现",
        "快速排序", "冒泡排序", "归并排序",
        # 数据结构
        "数组", "字符串处理", "设计模式", "接口", "类", "对象",
        # 框架与工具
        "react", "vue", "django", "flask", "spring", "docker", "k8s",
        "kubernetes", "nginx", "redis", "mongodb", "mysql", "postgresql",
        "git", "linux", "命令行", "api", "rest", "grpc",
        # 设计类
        "设计一个系统", "系统架构", "微服务", "架构设计",
    ]

    # 规划类关键词
    PLANNING_KEYWORDS = [
        "方案", "计划", "报告", "策划", "总结", "会议纪要", "需求文档",
        "设计方案", "技术方案", "系统方案", "架构设计",
        "分析报告", "评估报告", "调研报告", "项目报告",
        "活动方案", "项目方案", "策划方案", "策划书",
        "年度计划", "工作计划", "项目计划", "学习计划",
        "周报", "月报", "年报", "工作总结", "项目总结",
        "制定", "拟定", "起草", "编写方案",
        "组织一场", "举办一场", "安排一次",
        # V3.1: 旅游规划类（旅游攻略/行程设计/路线规划等）
        "旅游", "旅行", "游玩", "行程", "攻略", "路线",
        "旅游攻略", "旅游路程", "旅游路线", "旅行计划",
        "天数", "晚", "酒店", "预订", "预算",
        "景点", "小吃", "特色", "习俗", "食宿",
        "出行安排", "旅游行程", "旅行攻略",
        # V3.2: 生活类 — 烹饪/饮食规划（需要结构化输出，如一周食谱、营养方案）
        "食谱", "菜谱", "一周菜单", "每周菜单", "营养搭配", "膳食计划",
        "减脂餐", "增肌餐", "减肥食谱", "健身餐", "轻食搭配",
        "宝宝辅食", "婴儿辅食", "月子餐", "孕妇食谱",
        "宴客菜单", "家宴菜谱", "节日菜谱", "年夜饭",
        "食材采购清单", "采购清单",
        # V3.2: 生活类 — 收纳整理规划
        "收纳方案", "整理方案", "收纳清单", "整理清单",
        "断舍离清单", "衣橱整理", "衣柜收纳", "厨房收纳",
        "全屋收纳", "搬家整理", "物品分类",
        # V3.2: 生活类 — 清洁打扫规划
        "清洁计划", "打扫方案", "大扫除清单", "清洁清单",
        "家务分工", "家务计划", "卫生值日表",
        # V3.2: 生活类 — 家电配置/家居规划
        "家电配置方案", "家电选购指南", "装修方案", "装修计划",
        "家居布局", "房间布置", "空间规划",
        # V3.2: Word/PPT 办公文档类（需要结构化大纲/模板设计）
        "ppt大纲", "ppt方案", "演示文稿大纲", "幻灯片大纲",
        "汇报ppt", "年终总结ppt", "项目汇报ppt", "答辩ppt",
        "商业计划书ppt", "产品介绍ppt", "培训ppt",
        "word模板", "文档模板", "合同模板", "简历模板",
        "公文模板", "报告模板", "策划书模板",
        "排版方案", "文档结构", "文档大纲",
        # V3.2: 学校类 — 学习规划/学术写作
        "复习计划", "考研计划", "备考方案", "冲刺计划",
        "课程设计", "教学计划", "教案", "教学大纲",
        "论文大纲", "开题报告", "毕业设计", "毕业论文",
        "实验方案", "实验设计", "研究方案", "课题设计",
        "课外活动方案", "社团活动方案", "班会方案",
        "学期计划", "假期计划", "暑假计划", "寒假计划",
        "读书计划", "阅读清单", "书单",
        "课程表", "时间表", "作息表", "时间规划",
    ]

    # 分析类关键词
    ANALYSIS_KEYWORDS = [
        "swot", "分析", "评估", "影响", "比较", "对比",
        "优缺点", "利弊", "风险", "可行性", "调研",
        "诊断", "审查", "审计", "复盘",
        "深度分析", "全面分析", "系统分析",
        "竞争力", "市场分析", "竞品", "趋势",
    ]

    # 创意写作类关键词
    WRITING_KEYWORDS = [
        # 正式写作请求
        "写一首", "写一篇", "写一封", "写一段", "写一个故事",
        "创作一首", "创作一篇", "创作",
        "写诗", "写歌", "写词", "歌词",
        "写情书", "写日记", "写散文", "写小说",
        # 非正式写作请求
        "来一首", "来一篇", "来一段", "来一句",
        "编一个", "编一段", "编一首",
        "作一首", "作诗",
        # 主题写作
        "写关于", "写个", "写点",
        "写一写", "写写",
        # 特定格式
        "文案", "广告语", "口号", "宣传语", "标语",
        "情书", "日记", "周记", "随笔", "散文",
        "诗歌", "童话", "寓言", "故事", "小说",
        # 表达类
        "表达", "抒发", "描述", "描绘",
        "想象", "畅想", "幻想",
        "以...为题", "围绕...写",
    ]

    # 问答类关键词
    QA_KEYWORDS = [
        "是什么", "什么是", "什么叫做", "什么叫",
        "如何", "怎么", "怎样", "怎么样",
        "为什么", "为啥", "原因",
        "区别", "不同", "异同", "比较",
        "有哪些", "哪几种", "哪些",
        "介绍一下", "解释一下", "说明一下",
        "简述", "概述", "简要说明", "简要介绍",
        "定义", "概念", "原理", "机制",
        "用途", "作用", "功能", "特点",
        "优势", "缺点", "好处", "坏处",
        "步骤", "流程", "方法", "技巧",
        "注意事项", "最佳实践",
        # V3.2: 生活类 — 烹饪/食材问答
        "怎么做", "如何烹饪", "烹饪方法", "烹饪技巧",
        "食材搭配", "调料比例", "火候", "刀工",
        "怎么炒", "怎么炖", "怎么煮", "怎么蒸", "怎么烤",
        "怎么腌制", "怎么去腥", "怎么调味",
        "营养价值", "热量", "卡路里",
        # V3.2: 生活类 — 日常电器使用/故障
        "怎么用", "如何使用", "使用方法", "操作步骤",
        "怎么开", "怎么关", "怎么设置",
        "故障排除", "故障代码", "维修方法", "怎么修理",
        "洗衣机", "空调", "冰箱", "微波炉", "电饭煲",
        "扫地机器人", "热水器", "空气净化器",
        # V3.2: 生活类 — 清洁/去污问答
        "怎么清洗", "如何清洗", "怎么去除", "如何去除",
        "清洁方法", "去污", "除垢", "除味", "除霉",
        "怎么除油污", "怎么水垢",
        # V3.2: 生活类 — 收纳技巧问答
        "怎么折叠", "如何折叠", "收纳技巧", "整理技巧",
        "怎么叠衣服", "怎么收纳",
        # V3.2: Word/PPT 操作问答
        "怎么插入", "如何插入", "怎么设置", "如何设置",
        "怎么排版", "如何排版", "怎么调整", "如何调整",
        "word操作", "ppt操作", "excel操作",
        "怎么制作", "如何制作",
        "页码", "目录", "页眉", "页脚", "分页",
        "公式", "函数", "图表", "表格",
        "动画", "切换效果", "幻灯片",
        "怎么导出", "如何导出", "怎么转换", "如何转换",
        # V3.2: 学校类 — 知识点/解题问答
        "怎么计算", "如何计算", "怎么求解", "如何求解",
        "解题步骤", "解题思路", "公式推导",
        "怎么写", "如何写", "写作方法", "写作技巧",
        "语法", "句型", "时态", "单词",
        "怎么翻译", "如何翻译",
        "怎么背诵", "怎么记忆", "记忆方法",
        "怎么复习", "复习方法", "备考技巧",
        "怎么报名", "报名条件", "考试时间",
    ]

    # 闲聊类关键词
    CHAT_KEYWORDS = [
        "你好", "嗨", "早上好", "晚上好", "下午好",
        "谢谢", "再见", "拜拜",
        "天气", "今天天气", "明天天气",
        "推荐", "介绍", "有什么好",
        "喜欢", "觉得", "认为",
        "聊天", "聊聊", "谈谈",
        "怎么办", "帮帮我", "求助",
    ]

    def classify(self, user_input: str) -> TaskProfile:
        """分类用户查询，返回 TaskProfile

        按优先级顺序检测：CODING(带Guard) > PLANNING > ANALYSIS > WRITING > QA > CHAT

        CODING Guard: 技术名词匹配后，若同时包含 QA/ANALYSIS 模式则降级
        """
        query = user_input.strip()
        query_lower = query.lower()
        profile = TaskProfile(raw_query=query)

        # Priority 1: CODING — 编码类（带 Guard 防止技术名词误判）
        profile = self._try_classify(query, query_lower, self.CODING_KEYWORDS,
                                      TaskType.CODING, profile)
        if profile.task_type == TaskType.CODING:
            profile = self._apply_coding_guard(query_lower, profile)
            if profile.task_type == TaskType.CODING:
                return self._apply_coding_config(profile)
            # Guard 降级后继续走后续优先级

        # Priority 2: PLANNING — 规划类
        if profile.task_type != TaskType.PLANNING:
            profile = self._try_classify(query, query_lower, self.PLANNING_KEYWORDS,
                                          TaskType.PLANNING, profile)
        if profile.task_type == TaskType.PLANNING:
            return self._apply_planning_config(profile)

        # Priority 3: ANALYSIS — 分析类
        if profile.task_type != TaskType.ANALYSIS:
            profile = self._try_classify(query, query_lower, self.ANALYSIS_KEYWORDS,
                                          TaskType.ANALYSIS, profile)
        if profile.task_type == TaskType.ANALYSIS:
            return self._apply_analysis_config(profile)

        # Priority 4: WRITING — 创意写作类
        if profile.task_type != TaskType.WRITING:
            profile = self._try_classify(query, query_lower, self.WRITING_KEYWORDS,
                                          TaskType.WRITING, profile)
        if profile.task_type == TaskType.WRITING:
            return self._apply_writing_config(profile)

        # Priority 5: QA — 问答类
        if profile.task_type != TaskType.QA:
            profile = self._try_classify(query, query_lower, self.QA_KEYWORDS,
                                          TaskType.QA, profile)
        if profile.task_type == TaskType.QA:
            return self._apply_qa_config(profile)

        # Priority 6: CHAT — 闲聊兜底
        profile = self._try_classify(query, query_lower, self.CHAT_KEYWORDS,
                                      TaskType.CHAT, profile)
        return self._apply_chat_config(profile)

    # ============================================================
    # CODING Guard — 防止技术名词误判
    # ============================================================

    # 强 QA/ANALYSIS 模式 — 若查询包含这些，优先判定为非 CODING
    _CODING_OVERRIDE_PATTERNS = [
        # QA 模式
        "是什么", "什么是", "什么叫做", "什么叫",
        "如何", "怎么", "怎样", "怎么样",
        "为什么", "区别", "不同", "异同",
        "有哪些", "哪几种", "哪些",
        "介绍一下", "解释一下", "说明一下",
        "简述", "概述", "简要说明", "简要介绍",
        "用一句话", "一句话",
        "定义", "概念", "原理",
        "用途", "作用", "功能", "特点",
        "优势", "缺点", "好处", "坏处",
        # ANALYSIS 模式
        "比较", "对比", "优缺点", "利弊",
        "分析", "评估", "swot",
        "影响", "可行性",
    ]

    def _apply_coding_guard(self, query_lower: str, profile: TaskProfile) -> TaskProfile:
        """CODING Guard: 检查是否只是技术名词提及而非编码意图

        若查询同时包含 CODING 关键词和 QA/ANALYSIS 模式，
        则降级为 QA 或 ANALYSIS（取决于匹配到的模式）。

        例外：若查询包含强编码意图模式（实现/编写/写代码等），保持 CODING。
        """
        # 检查是否有强 QA/ANALYSIS 模式
        override_matched = []
        for pattern in self._CODING_OVERRIDE_PATTERNS:
            if pattern in query_lower:
                override_matched.append(pattern)

        if not override_matched:
            return profile  # 纯编码意图，保持 CODING

        # CODING Keeper: 强编码意图模式 — 即使有 QA 模式也保持 CODING
        coding_keepers = [
            "实现", "写代码", "编写", "编程", "代码实现",
            "写一个", "写段", "示例代码", "代码示例",
            "算法实现", "函数实现",
        ]
        if any(k in query_lower for k in coding_keepers):
            return profile  # 保持 CODING

        # 判断降级目标
        analysis_patterns = ["比较", "对比", "优缺点", "利弊", "分析", "评估", "swot", "影响", "可行性"]
        if any(p in query_lower for p in analysis_patterns):
            profile.task_type = TaskType.ANALYSIS
            profile.matched_patterns = override_matched
            profile.domain = self._get_default_domain(TaskType.ANALYSIS)
            profile.confidence = min(0.5 + len(override_matched) * 0.1, 0.90)
            logger.debug(f"CODING Guard: 降级为 ANALYSIS, matched={override_matched[:3]}")
        else:
            profile.task_type = TaskType.QA
            profile.matched_patterns = override_matched
            profile.domain = self._get_default_domain(TaskType.QA)
            profile.confidence = min(0.5 + len(override_matched) * 0.1, 0.90)
            logger.debug(f"CODING Guard: 降级为 QA, matched={override_matched[:3]}")

        return profile

    def _try_classify(self, query: str, query_lower: str,
                      keywords: List[str], task_type: TaskType,
                      profile: TaskProfile) -> TaskProfile:
        """尝试用关键词列表匹配，匹配成功则设置 TaskType"""
        matched = []
        for kw in keywords:
            if kw.lower() in query_lower:
                matched.append(kw)

        if matched:
            profile.task_type = task_type
            profile.matched_patterns = matched
            profile.confidence = min(0.5 + len(matched) * 0.1, 0.95)
            profile.domain = self._get_default_domain(task_type)

        return profile

    def _get_default_domain(self, task_type: TaskType) -> str:
        """获取 TaskType 对应的默认领域"""
        mapping = {
            TaskType.CODING: "tech",
            TaskType.QA: "daily",
            TaskType.WRITING: "creative",
            TaskType.PLANNING: "business",
            TaskType.ANALYSIS: "business",
            TaskType.CHAT: "daily",
        }
        return mapping.get(task_type, "daily")

    # ============================================================
    # TaskType 配置方法
    # ============================================================

    def _apply_coding_config(self, profile: TaskProfile) -> TaskProfile:
        """编码类配置"""
        profile.handler = "CodeHandler"
        profile.review_mode = "TechReview"
        profile.cloud_threshold = 0.70
        profile.template = False
        profile.min_length = 80
        profile.complexity = 0.4
        return profile

    def _apply_planning_config(self, profile: TaskProfile) -> TaskProfile:
        """规划类配置"""
        profile.handler = "TemplateHandler"
        profile.review_mode = "BusinessReview"
        profile.cloud_threshold = 0.65
        profile.template = True
        profile.min_length = 200
        profile.complexity = 0.7
        return profile

    def _apply_analysis_config(self, profile: TaskProfile) -> TaskProfile:
        """分析类配置"""
        profile.handler = "FactQuestionHandler"
        profile.review_mode = "BusinessReview"
        profile.cloud_threshold = 0.60
        profile.template = False
        profile.min_length = 150
        profile.complexity = 0.6
        return profile

    def _apply_writing_config(self, profile: TaskProfile) -> TaskProfile:
        """创意写作类配置"""
        profile.handler = "CreativeWritingHandler"
        profile.review_mode = "CreativeReview"
        profile.cloud_threshold = 0.40
        profile.template = False
        profile.min_length = 60
        profile.complexity = 0.5
        return profile

    def _apply_qa_config(self, profile: TaskProfile) -> TaskProfile:
        """问答类配置"""
        profile.handler = "FactQuestionHandler"
        profile.review_mode = "StandardReview"
        profile.cloud_threshold = 0.50
        profile.template = False
        profile.min_length = 80
        profile.complexity = 0.3
        return profile

    def _apply_chat_config(self, profile: TaskProfile) -> TaskProfile:
        """闲聊类配置"""
        profile.handler = "SimpleConversationHandler"
        profile.review_mode = "StandardReview"
        profile.cloud_threshold = 0.35
        profile.template = False
        profile.min_length = 40
        profile.complexity = 0.1
        return profile


# ============================================================
# 全局单例
# ============================================================

_task_classifier: Optional[TaskClassifier] = None


def get_task_classifier() -> TaskClassifier:
    """获取 TaskClassifier 全局单例"""
    global _task_classifier
    if _task_classifier is None:
        _task_classifier = TaskClassifier()
    return _task_classifier