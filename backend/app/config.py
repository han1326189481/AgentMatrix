from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict


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
    log_file: str = "logs/system.log"

    database_url: str = "sqlite:///./agentmatrix.db"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_review_model: str = "phi4-mini:3.8b"

    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-r1-distill"

    complexity_threshold: float = 0.65

    max_concurrent_tasks: int = 10
    max_retry_attempts: int = 3

    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()