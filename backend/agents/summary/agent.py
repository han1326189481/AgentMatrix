from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json


class SummaryAgent(BaseAgent):
    def __init__(self):
        super().__init__("summary", "Summary Agent")
        self.local_model = "qwen2.5:1.5b"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"摘要生成: {input_data.content[:50]}...")
        
        try:
            if input_data.use_llm:
                summary_result = await self._generate_summary_with_llm(input_data.content)
            else:
                summary_result = self._generate_summary(input_data.content)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=json.dumps(summary_result, ensure_ascii=False),
                success=True,
                message="摘要生成完成",
                metadata={"word_count": len(summary_result["task"]), "model_used": self.local_model},
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
    
    def _generate_summary(self, content: str) -> Dict[str, Any]:
        cleaned_content = self._clean_content(content)
        task = self._extract_task(cleaned_content)
        keywords = self._extract_keywords(cleaned_content)
        
        return {
            "task": task,
            "keywords": keywords,
            "summary": cleaned_content[:200] + "..." if len(cleaned_content) > 200 else cleaned_content
        }
    
    async def _generate_summary_with_llm(self, content: str) -> Dict[str, Any]:
        prompt = f"""
请分析以下用户输入，提取任务和关键词：

用户输入：{content}

请以JSON格式输出：
{{
  "task": "提取的任务描述",
  "keywords": ["关键词1", "关键词2", ...],
  "summary": "简要摘要"
}}
"""
        response = await self._call_llm(prompt, model=self.local_model, temperature=0.3)
        
        try:
            return json.loads(response)
        except:
            return self._generate_summary(content)
    
    def _clean_content(self, content: str) -> str:
        lines = content.split("\n")
        clean_lines = [line for line in lines if not line.startswith("【") and not line.startswith("参考知识:")]
        return " ".join(clean_lines).strip()
    
    def _extract_task(self, content: str) -> str:
        task_keywords = ["生成", "创建", "设计", "规划", "方案", "报告", "分析"]
        for keyword in task_keywords:
            idx = content.find(keyword)
            if idx != -1:
                result = content[idx:idx+50].strip()
                if "。" in result:
                    result = result[:result.find("。")+1]
                if "?" in result:
                    result = result[:result.find("?")+1]
                if len(result) < 5:
                    continue
                return result
        return content[:50].strip()
    
    def _extract_keywords(self, content: str) -> list:
        common_keywords = [
            "AI", "人工智能", "校园", "教育", "规划", "方案", "系统", 
            "开发", "设计", "报告", "分析", "研究", "评估", "优化"
        ]
        found = []
        for kw in common_keywords:
            if kw in content and kw not in found:
                found.append(kw)
        return found[:5]