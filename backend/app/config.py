from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict, Optional
import httpx
from shared.platform import get_log_file_path, get_env_file_path


async def detect_ollama_port() -> str:
    """自动检测 Ollama 服务端口"""
    ports = ["11434", "11435", "8080"]
    for port in ports:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://localhost:{port}/api/tags", timeout=2)
                if response.status_code == 200:
                    return f"http://localhost:{port}"
        except:
            continue
    return "http://localhost:11434"


class ModelConfig(BaseSettings):
    name: str
    provider: str
    host: str = ""
    api_key: str = ""
    parameters: Dict[str, float] = {}


class AgentModelMapping(BaseSettings):
    agent_id: str
    local_model: str
    cloud_model: str


class Settings(BaseSettings):
    app_name: str = "AgentMatrix"
    app_version: str = "0.1.0"
    app_env: str = "development"

    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = True

    log_level: str = "INFO"
    log_file: str = get_log_file_path()

    # 默认使用 SQLite（零配置，打开即用），用户可通过 .env 覆盖为 MySQL
    database_url: str = ""  # 空字符串表示使用 SQLite 默认路径

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    # 按 Agent 分配模型（可选，格式: "writer:qwen2.5:14b,review:deepseek-r1:7b"）
    ollama_agent_models: str = ""
    # V3.2: 视觉模型（MiniCPM-V，插件式加载，与主模型互斥）
    # 遵循规则十一：8GB VRAM 只能用 q4_0，禁止 q6_K/q8_0
    ollama_vision_model: str = "minicpm-v:latest"

    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-pro"

    # V3.5 (2026-07-31): Web Search 插件 — 时效性知识库（地点/美食/天气/旅行/评价）
    # 启用后 Knowledge Agent 检测到时效性场景时调用 DuckDuckGo + DeepSeek 摘要
    deepseek_search_enabled: bool = True
    # 时效性知识库 TTL（天）：默认 30 天，过期标记 is_stale=True，再次提问触发刷新
    timely_knowledge_ttl_days: int = 30

    gemini_api_key: str = ""
    gemini_model: str = "gemini-pro"

    complexity_threshold: float = 0.65

    # V4.2: 上下文管理 — 共享上下文窗口上限（token 数）
    # 本地模型 qwen2.5:7b 支持 128K，但 8GB VRAM 约束下保守设为 16K
    context_max_tokens: int = 16384
    # 触发自动压缩的阈值（使用率百分比）
    context_compress_threshold: float = 0.80
    # 触发溢出弹窗的阈值（使用率百分比）
    context_overflow_threshold: float = 0.90

    max_concurrent_tasks: int = 10
    max_retry_attempts: int = 3

    allowed_origins_list: Optional[str] = "*"

    model_config = SettingsConfigDict(env_file=get_env_file_path(), env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origins(self) -> List[str]:
        if self.allowed_origins_list == "*":
            return ["*"]
        if self.allowed_origins_list:
            return [origin.strip() for origin in self.allowed_origins_list.split(",")]
        return ["http://localhost:3000", "http://localhost:8000", "http://localhost:8080"]


settings = Settings()