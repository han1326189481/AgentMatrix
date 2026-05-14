from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel
from core.llm.client import get_llm_client


class AgentInput(BaseModel):
    content: str
    context: Optional[Dict[str, Any]] = None
    use_llm: bool = False


class AgentOutput(BaseModel):
    content: str
    success: bool = True
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    model_used: Optional[str] = None


class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.status = "idle"
        self.current_task = None
        self.last_error = None
        self.local_model = "qwen2.5:1.5b"
        self.cloud_model = "deepseek-r1-distill"
        self.llm_client = get_llm_client()

    @abstractmethod
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        pass

    async def initialize(self) -> None:
        self.status = "ready"

    async def shutdown(self) -> None:
        self.status = "shutdown"

    def get_status(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status,
            "current_task": self.current_task,
            "last_error": self.last_error,
            "local_model": self.local_model,
            "cloud_model": self.cloud_model,
        }

    async def _set_status(self, status: str) -> None:
        self.status = status

    async def _set_current_task(self, task: Optional[str]) -> None:
        self.current_task = task

    async def _set_error(self, error: Optional[str]) -> None:
        self.last_error = error

    async def _call_llm(self, prompt: str, model: str = None, use_cloud: bool = False, **kwargs) -> str:
        """调用真实的 LLM 生成内容"""
        try:
            system_prompt = kwargs.get("system_prompt", None)
            response = await self.llm_client.generate(prompt, use_cloud=use_cloud, system_prompt=system_prompt)
            return response
        except Exception as e:
            return f"LLM调用失败: {str(e)}"

    async def _call_llm_chat(self, messages: list, model: str = None, **kwargs) -> str:
        """调用真实的 LLM 聊天接口"""
        try:
            # 将消息列表转换为单个 prompt
            prompt = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages])
            return await self._call_llm(prompt, model=model, **kwargs)
        except Exception as e:
            return f"LLM聊天调用失败: {str(e)}"