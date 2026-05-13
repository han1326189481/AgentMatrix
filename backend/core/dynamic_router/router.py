from typing import Dict, Any, Optional
import httpx
from app.config import settings


class DeepSeekClient:
    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.api_base = settings.deepseek_api_base
        self.model = settings.deepseek_model
    
    async def call(self, prompt: str, model: str = None) -> str:
        if not self.api_key:
            return "DeepSeek API密钥未配置"
        
        url = f"{self.api_base}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model or self.model,
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"DeepSeek调用失败: {str(e)}"


class DynamicRouter:
    def __init__(self):
        self.cloud_client = DeepSeekClient()
        self.threshold = settings.complexity_threshold
    
    def should_use_cloud(self, complexity_score: float) -> bool:
        return complexity_score > self.threshold
    
    async def route(self, prompt: str, complexity_score: float, agent_id: str) -> Dict[str, Any]:
        use_cloud = self.should_use_cloud(complexity_score)
        
        if use_cloud:
            response = await self.cloud_client.call(prompt)
            source = "cloud"
            model_used = "deepseek-r1-distill"
        else:
            response = None
            source = "local"
            model_used = self._select_local_model(agent_id)
        
        return {
            "response": response,
            "source": source,
            "complexity_score": complexity_score,
            "threshold": self.threshold,
            "agent_id": agent_id,
            "model_used": model_used
        }
    
    def _select_local_model(self, agent_id: str) -> str:
        model_map = {
            "review": "phi4-mini:3.8b",
            "writer": "qwen2.5:1.5b",
            "judge": "qwen2.5:1.5b",
            "summary": "qwen2.5:1.5b",
            "knowledge": "qwen2.5:1.5b",
            "result": "qwen2.5:1.5b",
        }
        
        return model_map.get(agent_id, "qwen2.5:1.5b")


_dynamic_router_instance = None

def get_dynamic_router() -> DynamicRouter:
    global _dynamic_router_instance
    if _dynamic_router_instance is None:
        _dynamic_router_instance = DynamicRouter()
    return _dynamic_router_instance
