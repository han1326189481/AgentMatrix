import os
import sys

backend_dir = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings
from core.llm.client import get_llm_client

print("=== 配置调试 ===")
print(f"配置文件路径: {os.path.join(backend_dir, 'app', 'config.py')}")
print(f"ollama_host 配置值: '{settings.ollama_host}'")
print(f"是否包含 http:// : {'http://' in settings.ollama_host}")
print(f"是否包含 localhost : {'localhost' in settings.ollama_host}")

llm_client = get_llm_client()
print(f"\nLLM Client ollama_host: '{llm_client.ollama_host}'")

# 测试连接
import asyncio
import httpx

async def test_connection():
    host = llm_client.ollama_host
    if not host.startswith("http://") and not host.startswith("https://"):
        host = f"http://{host}"
    
    print(f"\n测试连接到: {host}")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{host}/api/tags")
            print(f"连接成功! 状态码: {response.status_code}")
            data = response.json()
            print(f"可用模型: {[m['name'] for m in data.get('models', [])]}")
    except Exception as e:
        print(f"连接失败: {str(e)}")

asyncio.run(test_connection())