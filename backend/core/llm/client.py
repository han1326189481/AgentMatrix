from typing import Dict, Any, Optional
import aiohttp
import logging
from app.config import settings
import sys
import os

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config.manager import load_config
except ImportError:
    def load_config():
        return {"models": [], "api_keys": {}}

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.ollama_host = settings.ollama_host
        self.ollama_model = settings.ollama_model
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        self.deepseek_api_key = getattr(settings, 'deepseek_api_key', '')
        self.deepseek_api_base = getattr(settings, 'deepseek_api_base', 'https://api.deepseek.com/v1')
        self.deepseek_model = getattr(settings, 'deepseek_model', 'deepseek-chat')
        self.dynamic_ollama_host = None

    async def generate_local(self, prompt: str, system_prompt: str = None, model: str = None) -> str:
        host = self.dynamic_ollama_host or self.ollama_host
        url = f"{host}/api/generate"
        payload = {
            "model": model or self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 2048,
                "num_thread": 4
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "")
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama error: {response.status} - {error_text}")
                        return f"Error: {response.status}"
        except Exception as e:
            logger.error(f"Failed to call Ollama: {e}")
            return f"Error: {str(e)}"

    async def generate_local_stream(self, prompt: str, system_prompt: str = None, model: str = None):
        """流式调用 Ollama"""
        host = self.dynamic_ollama_host or self.ollama_host
        url = f"{host}/api/generate"
        payload = {
            "model": model or self.ollama_model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_ctx": 2048,
                "num_thread": 4,
                "temperature": 0.3
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                try:
                                    data = line.decode('utf-8').strip()
                                    if data:
                                        import json
                                        json_data = json.loads(data)
                                        response_text = json_data.get("response", "")
                                        done = json_data.get("done", False)
                                        if response_text:
                                            yield response_text
                                        if done:
                                            break
                                except:
                                    continue
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama streaming error: {response.status} - {error_text}")
                        yield f"Error: {response.status}"
        except Exception as e:
            logger.error(f"Failed to call Ollama stream: {e}")
            yield f"Error: {str(e)}"

    async def generate_cloud(self, prompt: str, system_prompt: str = None) -> str:
        if not self.deepseek_api_key:
            logger.error("DeepSeek API key not set")
            return "Error: DeepSeek API Key 未设置"

        # 直接使用正确的 URL
        url = "https://api.deepseek.com/v1/chat/completions"
        
        logger.info(f"[DeepSeek] API URL: {url}")
        logger.info(f"[DeepSeek] API Key: {self.deepseek_api_key[:10]}... (长度: {len(self.deepseek_api_key)})")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # 使用 deepseek-chat 模型
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048
        }

        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    logger.info(f"[DeepSeek] Response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices", [])
                        if choices:
                            logger.info("[DeepSeek] API调用成功")
                            return choices[0].get("message", {}).get("content", "")
                        logger.warning("[DeepSeek] API返回但没有choices")
                        return ""
                    elif response.status == 401:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 认证失败: {error_text}")
                        return f"Error: 401 认证失败，请检查 API Key 是否正确 - {error_text}"
                    elif response.status == 400:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 请求错误: {response.status} - {error_text}")
                        return f"Error: 400 请求格式错误 - {error_text}"
                    elif response.status == 404:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 404错误: {error_text}")
                        return f"Error: 404 路径不存在 - {error_text}"
                    else:
                        error_text = await response.text()
                        logger.error(f"[DeepSeek] 错误: {response.status} - {error_text}")
                        return f"Error: {response.status} - {error_text}"
        except Exception as e:
            logger.error(f"[DeepSeek] 调用失败: {e}", exc_info=True)
            return f"Error: 调用 DeepSeek 失败 - {str(e)}"

    async def generate_by_config(self, prompt: str, model_config: dict, system_prompt: str = None) -> str:
        """使用配置好的模型来生成内容"""
        provider = model_config.get("provider", "deepseek")
        model_name = model_config.get("model", "deepseek-chat")
        api_key = model_config.get("api_key", self.deepseek_api_key)
        temperature = model_config.get("temperature", 0.7)
        max_tokens = model_config.get("max_tokens", 2048)
        
        logger.info(f"[ConfigModel] 使用配置模型: provider={provider}, model={model_name}")
        
        if provider == "ollama":
            return await self.generate_local(prompt, system_prompt, model_name)
        
        # 处理云服务商（DeepSeek/OpenAI等）
        if not api_key:
            logger.error(f"[ConfigModel] API Key未设置 (provider: {provider})")
            return f"Error: {provider} API Key 未设置"
        
        url = self._get_provider_url(provider)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    logger.info(f"[ConfigModel] Response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices", [])
                        if choices:
                            logger.info("[ConfigModel] API调用成功")
                            return choices[0].get("message", {}).get("content", "")
                        return ""
                    else:
                        error_text = await response.text()
                        logger.error(f"[ConfigModel] 错误: {response.status} - {error_text}")
                        return f"Error: {response.status} - {error_text}"
        except Exception as e:
            logger.error(f"[ConfigModel] 调用失败: {e}", exc_info=True)
            return f"Error: 调用失败 - {str(e)}"
    
    def _get_provider_url(self, provider: str) -> str:
        """根据服务商获取API URL"""
        urls = {
            "deepseek": "https://api.deepseek.com/v1/chat/completions",
            "openai": "https://api.openai.com/v1/chat/completions"
        }
        return urls.get(provider, "https://api.deepseek.com/v1/chat/completions")

    async def generate(self, prompt: str, use_cloud: bool = False, system_prompt: str = None, model: str = None) -> str:
        if use_cloud:
            return await self.generate_cloud(prompt, system_prompt)
        return await self.generate_local(prompt, system_prompt, model)

    async def generate_stream(self, prompt: str, use_cloud: bool = False, system_prompt: str = None, model: str = None):
        """流式生成内容"""
        if use_cloud:
            # 云服务暂时不支持流式，返回普通结果
            result = await self.generate_cloud(prompt, system_prompt)
            yield result
        else:
            async for chunk in self.generate_local_stream(prompt, system_prompt, model):
                yield chunk


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
