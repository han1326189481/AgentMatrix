from typing import Dict, Any, Optional
import aiohttp
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.ollama_host = settings.ollama_host
        self.ollama_model = settings.ollama_model
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model

    async def generate_local(self, prompt: str, system_prompt: str = None) -> str:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with aiohttp.ClientSession() as session:
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

    async def generate_cloud(self, prompt: str, system_prompt: str = None) -> str:
        if not self.gemini_api_key:
            logger.warning("Gemini API key not set, falling back to local")
            return await self.generate_local(prompt, system_prompt)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"

        contents = [{"parts": [{"text": prompt}]}]
        if system_prompt:
            contents.insert(0, {"role": "system", "parts": [{"text": system_prompt}]})

        payload = {"contents": contents}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "")
                        return ""
                    else:
                        error_text = await response.text()
                        logger.error(f"Gemini error: {response.status} - {error_text}")
                        return f"Error: {response.status}"
        except Exception as e:
            logger.error(f"Failed to call Gemini: {e}")
            return f"Error: {str(e)}"

    async def generate(self, prompt: str, use_cloud: bool = False, system_prompt: str = None) -> str:
        if use_cloud:
            return await self.generate_cloud(prompt, system_prompt)
        return await self.generate_local(prompt, system_prompt)


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
