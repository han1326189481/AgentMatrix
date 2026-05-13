from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json
from datetime import datetime


class ResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("result", "Result Agent")
        self.local_model = "qwen2.5:1.5b"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"结果导出: {input_data.content[:50]}...")
        
        try:
            judge_result = self._parse_judge(input_data.content)
            final_result = self._format_result(judge_result, input_data.context)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=final_result,
                success=True,
                message="结果生成完成",
                metadata={"format": "markdown", "length": len(final_result), "model_used": self.local_model},
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
    
    def _parse_judge(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except:
            return {"complexity_score": 0.5, "execute_locally": True, "decision": "本地执行"}
    
    def _format_result(self, judge_result: Dict[str, Any], context: Dict[str, Any]) -> str:
        writer_content = context.get("writer", "") if context else ""
        
        result = "# 任务执行结果\n\n"
        result += "## 执行路径\n"
        result += f"- 复杂度评分: {judge_result.get('complexity_score', 0):.2f}\n"
        result += f"- 执行方式: {judge_result.get('decision', '未知')}\n"
        
        reasons = judge_result.get("reasons", [])
        if reasons:
            result += "\n## 决策原因\n"
            for reason in reasons:
                result += f"- {reason}\n"
        
        if writer_content:
            result += "\n---\n\n"
            result += "## 生成内容\n"
            result += writer_content
        
        result += "\n---\n\n"
        result += "**导出格式**: Markdown\n"
        result += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return result