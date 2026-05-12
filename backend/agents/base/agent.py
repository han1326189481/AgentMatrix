from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel


class AgentInput(BaseModel):
    content: str
    context: Optional[Dict[str, Any]] = None


class AgentOutput(BaseModel):
    content: str
    success: bool = True
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.status = "idle"
        self.current_task = None
        self.last_error = None

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
        }

    async def _set_status(self, status: str) -> None:
        self.status = status

    async def _set_current_task(self, task: Optional[str]) -> None:
        self.current_task = task

    async def _set_error(self, error: Optional[str]) -> None:
        self.last_error = error