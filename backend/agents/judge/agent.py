from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json
from app.config import settings


class JudgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("judge", "Judge Agent")
        self.threshold = settings.complexity_threshold
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"复杂度判断: {input_data.content[:50]}...")
        
        try:
            judge_result = self._judge_complexity(input_data.content)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=json.dumps(judge_result, ensure_ascii=False),
                success=True,
                message=judge_result["decision"],
                metadata={
                    "complexity_score": judge_result["complexity_score"],
                    "threshold": self.threshold,
                    "executed_locally": judge_result["execute_locally"]
                }
            )
        
        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(
                content="",
                success=False,
                message=str(e)
            )
    
    def _judge_complexity(self, content: str) -> Dict[str, Any]:
        score = self._calculate_complexity(content)
        execute_locally = score <= self.threshold
        
        return {
            "complexity_score": score,
            "threshold": self.threshold,
            "execute_locally": execute_locally,
            "decision": "本地执行" if execute_locally else "调用云端API",
            "reasons": self._get_decision_reasons(score, execute_locally),
            "confidence": self._calculate_confidence(score)
        }
    
    def _calculate_complexity(self, content: str) -> float:
        score = 0.3
        
        if len(content) > 500:
            score += 0.2
        
        complex_keywords = ["复杂", "深度", "分析", "研究", "算法", "模型", "架构", "系统"]
        for kw in complex_keywords:
            if kw in content:
                score += 0.08
        
        review = self._parse_review(content)
        if review and review.get("score", 85) < 70:
            score += 0.15
        
        return min(1.0, max(0.0, score))
    
    def _parse_review(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except:
            return {}
    
    def _get_decision_reasons(self, score: float, local: bool) -> list:
        reasons = []
        if score < 0.4:
            reasons.append("任务简单，适合本地处理")
        elif score < 0.6:
            reasons.append("任务复杂度中等")
        else:
            reasons.append("任务较为复杂")
        
        if local:
            reasons.append("将使用本地模型完成")
        else:
            reasons.append("将调用云端模型增强")
        
        return reasons
    
    def _calculate_confidence(self, score: float) -> float:
        distance = abs(score - self.threshold)
        if distance < 0.1:
            return 0.7 + distance * 3
        return min(1.0, 0.85 + distance)
