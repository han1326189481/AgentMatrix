from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any


class ReviewAgent(BaseAgent):
    def __init__(self):
        super().__init__("review", "Review Agent")
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"质量评审: {input_data.content[:50]}...")
        
        try:
            review_result = self._review_content(input_data.content)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=str(review_result),
                success=True,
                message="质量评审完成",
                metadata={"score": review_result["score"], "issues": review_result["issues"]}
            )
        
        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(
                content="",
                success=False,
                message=str(e)
            )
    
    def _review_content(self, content: str) -> Dict[str, Any]:
        issues = []
        score = 85
        
        if len(content) < 100:
            issues.append("内容长度较短，建议补充详细内容")
            score -= 10
        
        if "# " not in content:
            issues.append("缺少一级标题")
            score -= 5
        
        if "## " not in content:
            issues.append("建议添加二级标题结构")
            score -= 5
        
        if "总结" not in content and "结论" not in content:
            issues.append("建议添加总结部分")
            score -= 5
        
        return {
            "score": max(0, score),
            "issues": issues,
            "suggestions": self._generate_suggestions(issues),
            "content_length": len(content),
            "structure_valid": len(issues) < 3
        }
    
    def _generate_suggestions(self, issues: list) -> list:
        suggestions = []
        if "内容长度较短" in str(issues):
            suggestions.append("可以增加更多细节描述")
        if "缺少一级标题" in str(issues):
            suggestions.append("添加清晰的标题可以提升可读性")
        if "二级标题" in str(issues):
            suggestions.append("合理的章节划分有助于内容组织")
        if "总结" in str(issues):
            suggestions.append("总结部分可以帮助读者快速了解核心内容")
        
        if not suggestions:
            suggestions.append("内容质量良好，无需修改")
        
        return suggestions