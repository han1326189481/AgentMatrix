import httpx
from typing import Dict, Any, Optional, List
from app.config import settings
import json
import logging

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, host: str = None):
        self.host = host or settings.ollama_host
        self.client = httpx.AsyncClient(base_url=self.host, timeout=120.0)
    
    async def generate(self, model: str, prompt: str, **kwargs) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            **kwargs
        }
        
        try:
            response = await self.client.post("/api/generate", json=payload)
            response.raise_for_status()
            
            raw_content = response.content
            
            try:
                result = json.loads(raw_content.decode("utf-8"))
            except UnicodeDecodeError:
                result = json.loads(raw_content.decode("gbk"))
            
            response_text = result.get("response", "")
            
            if isinstance(response_text, bytes):
                response_text = response_text.decode("utf-8")
            
            response_text = self._fix_chinese_encoding(response_text)
            
            return response_text
        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama client error: {e}")
            raise
    
    def _fix_chinese_encoding(self, text: str) -> str:
        try:
            return text.encode("gbk").decode("utf-8")
        except:
            try:
                return text.encode("gb18030").decode("utf-8")
            except:
                try:
                    return text.encode("latin-1").decode("utf-8")
                except:
                    return text
    
    async def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        try:
            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
            
            raw_content = response.content
            
            try:
                result = json.loads(raw_content.decode("utf-8"))
            except UnicodeDecodeError:
                result = json.loads(raw_content.decode("gbk"))
            
            content = result.get("message", {}).get("content", "")
            content = self._fix_chinese_encoding(content)
            
            return content
        except httpx.HTTPError as e:
            logger.error(f"Ollama chat API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Ollama chat client error: {e}")
            raise
    
    async def list_models(self) -> List[Dict[str, Any]]:
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            result = response.json()
            return result.get("models", [])
        except httpx.HTTPError as e:
            logger.error(f"Ollama list models error: {e}")
            return []
    
    async def pull_model(self, model: str) -> bool:
        try:
            async with self.client.stream("POST", "/api/pull", json={"name": model, "stream": False}) as response:
                response.raise_for_status()
                return True
        except httpx.HTTPError as e:
            logger.error(f"Ollama pull model error: {e}")
            return False
    
    async def close(self):
        await self.client.aclose()


class LLMService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ollama_client = None
        return cls._instance
    
    async def initialize(self):
        self._ollama_client = OllamaClient()
    
    async def get_ollama_client(self) -> OllamaClient:
        if not self._ollama_client:
            await self.initialize()
        return self._ollama_client
    
    async def generate(self, model: str, prompt: str, **kwargs) -> str:
        client = await self.get_ollama_client()
        return await client.generate(model, prompt, **kwargs)
    
    async def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        client = await self.get_ollama_client()
        return await client.chat(model, messages, **kwargs)
    
    async def list_local_models(self) -> List[str]:
        client = await self.get_ollama_client()
        models = await client.list_models()
        return [model["name"] for model in models]
    
    async def close(self):
        if self._ollama_client:
            await self._ollama_client.close()


llm_service = LLMService()