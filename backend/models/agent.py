from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class AgentStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentInfo(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent 名称")
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="状态")
    current_task: Optional[str] = Field(default=None, description="当前任务")
    last_error: Optional[str] = Field(default=None, description="最后错误")
    last_active: Optional[datetime] = Field(default=None, description="最后活跃时间")


class AgentExecutionResult(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    success: bool = Field(default=True, description="是否成功")
    content: str = Field(default="", description="输出内容")
    message: Optional[str] = Field(default=None, description="消息")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    duration_seconds: float = Field(default=0.0, description="执行耗时")
