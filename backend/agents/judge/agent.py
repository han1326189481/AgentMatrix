from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json
from app.config import settings


class JudgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("judge", "Judge Agent")
        self.local_model = "qwen2.5:1.5b"
        self.threshold = settings.complexity_threshold
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"复杂度判断: {input_data.content[:50]}...")
        
        try:
            if input_data.use_llm:
                judge_result = await self._judge_complexity_with_llm(input_data.content)
            else:
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
                    "executed_locally": judge_result["execute_locally"],
                    "model_used": self.local_model
                },
                model_used=self.local_model
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
    
    async def _judge_complexity_with_llm(self, content: str) -> Dict[str, Any]:
        prompt = f"""
请分析以下任务的复杂度：

任务内容：{content}

请从以下维度评估：
1. 任务长度（短/中/长）
2. 涉及领域（通用/专业/复杂专业）
3. 需要的推理深度（简单/中等/深度）
4. 是否需要外部知识（否/少量/大量）

请输出JSON格式：
{{
  "complexity_score": 0.0-1.0,
  "reasoning": "判断理由",
  "factors": ["因素1", "因素2"]
}}
"""
        response = await self._call_llm(prompt, model=self.local_model, temperature=0.2)
        
        try:
            llm_result = json.loads(response)
            score = max(0.0, min(1.0, llm_result.get("complexity_score", 0.5)))
        except:
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