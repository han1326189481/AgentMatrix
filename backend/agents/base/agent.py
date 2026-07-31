from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel
from core.llm.client import get_llm_client
import logging

logger = logging.getLogger(__name__)


class AgentInput(BaseModel):
    content: str
    context: Optional[Dict[str, Any]] = None
    use_llm: bool = False
    use_cloud: bool = False


class AgentOutput(BaseModel):
    content: str
    success: bool = True
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    model_used: Optional[str] = None


class BaseAgent(ABC):
    def __init__(self, agent_id: str, name: str, settings: Any = None):
        self.agent_id = agent_id
        self.name = name
        self.status = "idle"
        self.current_task = None
        self.last_error = None
        # 从 ModelRegistry 读取模型配置（单一数据源）
        from core.model_registry import get_model, get_cloud_model
        self.local_model = get_model(self.agent_id)
        self.cloud_model = get_cloud_model()
        self.llm_client = get_llm_client()
        self._settings = settings
        self._system_prompt: Optional[str] = None

    def _load_system_prompt(self) -> str:
        """从 PromptManager 加载系统提示模板，失败时返回空字符串"""
        if self._system_prompt is not None:
            return self._system_prompt
        try:
            from prompts.template_manager import get_prompt_manager
            pm = get_prompt_manager()
            template = pm.get_template(self.agent_id, "system")
            if template:
                self._system_prompt = template.template
                return self._system_prompt
        except Exception as e:
            logger.warning(f"Failed to load system prompt for {self.agent_id}: {e}")
        self._system_prompt = ""
        return self._system_prompt

    def _get_settings(self):
        """获取配置，优先使用注入的 settings，否则回退到全局"""
        if self._settings is not None:
            return self._settings
        from app.config import settings
        return settings

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

            if use_cloud:
                try:
                    from api.v1.config.router import _runtime_config
                    runtime_api_key = _runtime_config.get("deepseek_api_key")
                    if runtime_api_key:
                        self.llm_client.deepseek_api_key = runtime_api_key
                except:
                    pass
            
            # 根据 use_cloud 参数选择模型
            if use_cloud:
                llm_model = self.cloud_model
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[Cloud] 正在调用云服务 DeepSeek，模型: {llm_model}")
            else:
                llm_model = model or self.local_model
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[Local] 正在调用本地模型 Ollama，模型: {llm_model}")
            
            response = await self.llm_client.generate(prompt, use_cloud=use_cloud, system_prompt=system_prompt, model=llm_model)
            return response
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"LLM调用失败: {str(e)}", exc_info=True)
            return f"LLM调用失败: {str(e)}"

    async def _call_llm_chat(self, messages: list, model: str = None, **kwargs) -> str:
        """调用真实的 LLM 聊天接口"""
        try:
            # 将消息列表转换为单个 prompt
            prompt = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages])
            return await self._call_llm(prompt, model=model, **kwargs)
        except Exception as e:
            return f"LLM聊天调用失败: {str(e)}"