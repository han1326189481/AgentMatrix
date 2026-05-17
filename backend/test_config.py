from app.config import settings
from core.llm.client import get_llm_client

print("当前配置:")
print(f"ollama_host: {settings.ollama_host}")
print(f"ollama_model: {settings.ollama_model}")
print(f"deepseek_api_key: {'已设置' if settings.deepseek_api_key else '未设置'}")

llm_client = get_llm_client()
print(f"\nLLM Client 配置:")
print(f"ollama_host: {llm_client.ollama_host}")
print(f"ollama_model: {llm_client.ollama_model}")