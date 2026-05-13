from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime


class WorkflowInput(BaseModel):
    user_input: str = Field(..., description="用户输入内容")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="上下文信息")


class WorkflowStep(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    agent_name: str = Field(..., description="Agent 名称")
    input: str = Field(..., description="输入内容")
    output: str = Field(..., description="输出内容")
    success: bool = Field(default=True, description="是否成功")
    duration_seconds: float = Field(default=0.0, description="执行耗时")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class WorkflowOutput(BaseModel):
    final_result: str = Field(..., description="最终结果")
    steps: List[WorkflowStep] = Field(default_factory=list, description="执行步骤")
    executed_locally: bool = Field(default=True, description="是否本地执行")
    total_duration_seconds: float = Field(default=0.0, description="总耗时")
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: datetime = Field(default_factory=datetime.now, description="结束时间")
    complexity_score: Optional[float] = Field(default=None, description="复杂度评分")


class ChatMessage(BaseModel):
    id: Optional[str] = Field(default=None, description="消息 ID")
    role: str = Field(..., description="角色: user/assistant/system")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[float] = Field(default=None, description="时间戳")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
