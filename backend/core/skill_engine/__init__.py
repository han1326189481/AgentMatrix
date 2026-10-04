"""
Skill Engine V2.1 — 技能引擎核心模块

从"Prompt Engineering"到"Workflow Engineering"：
Task Type → Skill Path → Execution Plan → Prompt → LLM

核心组件：
- TaskEngine: 任务类型分类器（V2.1 新增）
- SkillBook: 技能书数据模型
- SkillManager: 技能书加载、缓存、合并
- SkillTree: 技能树遍历、路径检测
- PromptBuilder: 从 Skill 数据构建 System Prompt
- IntentAnalyzer: 意图识别 + 领域检测
- IntentCache: 意图缓存（两层）
- ReviewEngine: 独立评审引擎（V2.1 新增）
- TemplateEngine: 独立模板引擎（V2.1 新增）
"""

from .models import SkillBook, ReviewReport, IntentCacheEntry
from .skill_tree import SkillTree, SkillTreeNode
from .skill_manager import SkillManager
from .prompt_builder import PromptBuilder
from .skill_learner import SkillLearner
from .intent_cache import IntentCache
from .task_engine import TaskType, TaskProfile, TaskClassifier, get_task_classifier
from .review_engine import ReviewEngine, get_review_engine
from .template_engine import TemplateEngine, Template, get_template_engine

__all__ = [
    "SkillBook",
    "SkillTree",
    "SkillTreeNode",
    "ReviewReport",
    "IntentCacheEntry",
    "SkillManager",
    "PromptBuilder",
    "SkillLearner",
    "IntentCache",
    "TaskType",
    "TaskProfile",
    "TaskClassifier",
    "get_task_classifier",
    "ReviewEngine",
    "get_review_engine",
    "TemplateEngine",
    "Template",
    "get_template_engine",
]