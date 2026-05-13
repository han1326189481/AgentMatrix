from typing import Dict, Any, Optional, Callable
from app.config import settings
from core.llm import get_llm_client
import logging

logger = logging.getLogger(__name__)


class DynamicRouter:
    def __init__(self):
        self.llm_client = get_llm_client()
        self.threshold = settings.complexity_threshold
        self.routing_history = []

    async def route(self, complexity_score: float, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        use_cloud = complexity_score > self.threshold
        
        logger.info(f"Routing decision: complexity={complexity_score:.2f}, threshold={self.threshold}, use_cloud={use_cloud}")
        
        result = await self.llm_client.generate(
            prompt=prompt,
            use_cloud=use_cloud,
            system_prompt=system_prompt
        )
        
        routing_info = {
            "complexity_score": complexity_score,
            "threshold": self.threshold,
            "use_cloud": use_cloud,
            "model": "cloud" if use_cloud else "local",
            "result": result,
            "success": len(result) > 0
        }
        
        self.routing_history.append(routing_info)
        
        return routing_info

    async def route_with_fallback(self, complexity_score: float, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        try:
            return await self.route(complexity_score, prompt, system_prompt)
        except Exception as e:
            logger.error(f"Primary routing failed, falling back: {e}")
            
            fallback_info = await self.llm_client.generate(
                prompt=prompt,
                use_cloud=False,
                system_prompt=system_prompt
            )
            
            return {
                "complexity_score": complexity_score,
                "threshold": self.threshold,
                "use_cloud": False,
                "model": "local (fallback)",
                "result": fallback_info,
                "success": len(fallback_info) > 0,
                "fallback": True,
                "error": str(e)
            }

    def get_routing_stats(self) -> Dict[str, Any]:
        total = len(self.routing_history)
        if total == 0:
            return {
                "total_requests": 0,
                "cloud_calls": 0,
                "local_calls": 0,
                "fallbacks": 0,
                "success_rate": 0.0
            }
        
        cloud_calls = sum(1 for r in self.routing_history if r.get("use_cloud", False))
        local_calls = total - cloud_calls
        fallbacks = sum(1 for r in self.routing_history if r.get("fallback", False))
        successes = sum(1 for r in self.routing_history if r.get("success", False))
        
        return {
            "total_requests": total,
            "cloud_calls": cloud_calls,
            "local_calls": local_calls,
            "fallbacks": fallbacks,
            "success_rate": successes / total,
            "cloud_ratio": cloud_calls / total
        }

    def clear_history(self) -> None:
        self.routing_history.clear()


_router: Optional[DynamicRouter] = None


def get_dynamic_router() -> DynamicRouter:
    global _router
    if _router is None:
        _router = DynamicRouter()
    return _router
