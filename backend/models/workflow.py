from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime


class WorkflowInput(BaseModel):
    user_input: str = Field(..., description="用户输入内容")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文信息")
    sandbox_id: Optional[str] = Field(default=None, description="沙盒ID（多沙盒隔离）")


class WorkflowStep(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent 名称")
    input: str = Field(..., description="输入内容")
    output: str = Field(..., description="输出内容")
    success: bool = Field(default=True, description="是否成功")
    duration_seconds: float = Field(default=0.0, description="执行耗时")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class PromptTemplateItem(BaseModel):
    """提示词模板推荐项（供前端 UI 展示 + 点击填充输入框）"""
    node_id: str = Field(..., description="模板节点 ID（如 speech_opening_009）")
    title: str = Field(..., description="模板标题")
    domain: str = Field(default="", description="所属领域（如 speech.speech_opening）")
    quality_score: float = Field(default=0.0, description="质量评分（0.0-1.0）")
    intent_tags: List[str] = Field(default_factory=list, description="意图标签")
    reason: str = Field(default="", description="推荐理由")
    # 完整模板内容（供用户点击后填充输入框使用）
    template_text: str = Field(default="", description="完整模板文本（含占位符）")
    variables: List[Dict[str, Any]] = Field(default_factory=list, description="模板变量定义")
    difficulty: str = Field(default="", description="难度等级（beginner/intermediate/advanced）")


class TaskStep(BaseModel):
    """任务拆分步骤（来自 Decomposer + LocalPlanner，供前端展示逐条任务列表）

    将用户问题拆分为多条"用户能看懂的任务"，取代笼统的工作流动画图。
    每条任务下面标注对应的 Agent，让用户直观看到系统在做什么。
    """
    step_id: int = Field(..., description="步骤序号（从 1 开始）")
    title: str = Field(..., description="任务标题（来自 plan_steps）")
    agent_id: str = Field(default="", description="主导该任务的 Agent ID（knowledge/writer/result）")
    agent_name: str = Field(default="", description="Agent 显示名称")
    status: str = Field(default="pending", description="任务状态：pending/running/completed/error")
    duration_seconds: float = Field(default=0.0, description="该步骤耗时（秒）")


class WorkflowOutput(BaseModel):
    final_result: str = Field(..., description="最终结果")
    steps: List[WorkflowStep] = Field(default_factory=list, description="执行步骤")
    executed_locally: bool = Field(default=True, description="是否本地执行")
    total_duration_seconds: float = Field(default=0.0, description="总耗时")
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: datetime = Field(default_factory=datetime.now, description="结束时间")
    complexity_score: Optional[float] = Field(default=None, description="复杂度评分")
    partial_success: bool = Field(default=False, description="部分成功（部分Agent失败）")
    error_summary: Optional[List[str]] = Field(default=None, description="错误摘要列表")
    # V3: Knowledge Recommendation — 提示词模板推荐（首次命中即推荐）
    # 默认空列表，向后兼容；前端可读取此字段展示系统消息
    prompt_templates: List[PromptTemplateItem] = Field(
        default_factory=list, description="推荐的提示词模板列表"
    )
    # V3.1: 任务拆分（取代笼统的工作流动画图）
    # 将 Decomposer + LocalPlanner 的 plan_steps 暴露给前端，展示逐条任务列表
    task_steps: List[TaskStep] = Field(
        default_factory=list, description="任务拆分步骤列表（供前端展示逐条任务）"
    )
    # V3.1: 认知引擎调度结果（真实下发，取代前端启发式推断）
    controller_engines: List[str] = Field(
        default_factory=list, description="CognitiveController 真实调度的引擎列表"
    )
    task_type: Optional[str] = Field(default=None, description="任务类型（chat/qa/coding/writing/planning/analysis）")


class ChatMessage(BaseModel):
    id: Optional[str] = Field(default=None, description="消息 ID")
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[float] = Field(default=None, description="时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
