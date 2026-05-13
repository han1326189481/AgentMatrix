from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__("writer", "Writer Agent")
        self.local_model = "qwen2.5:1.5b"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"内容生成: {input_data.content[:50]}...")
        
        try:
            parsed = self._parse_summary(input_data.content)
            
            if input_data.use_llm:
                content = await self._generate_content_with_llm(parsed)
            else:
                content = self._generate_content(parsed)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=content,
                success=True,
                message="内容生成完成",
                metadata={"content_length": len(content), "model_used": self.local_model},
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
    
    def _parse_summary(self, content: str) -> Dict[str, Any]:
        try:
            return json.loads(content)
        except:
            return {"task": content, "keywords": [], "summary": content}
    
    def _generate_content(self, parsed: Dict[str, Any]) -> str:
        task = parsed.get("task", "")
        keywords = parsed.get("keywords", [])
        
        content = f"# {task}\n\n"
        content += "## 一、需求分析\n"
        content += "根据用户需求，本方案旨在解决以下问题：\n"
        content += "- 需求概述\n"
        content += "- 目标分析\n"
        
        if keywords:
            content += f"\n## 二、核心关键词\n"
            content += ", ".join(keywords) + "\n"
        
        content += "\n## 三、方案内容\n"
        content += "### 3.1 方案概述\n"
        content += "本方案基于用户需求，结合行业最佳实践，提出以下解决方案。\n\n"
        
        content += "### 3.2 实施步骤\n"
        content += "1. 需求确认与分析\n"
        content += "2. 方案设计与规划\n"
        content += "3. 实施与验证\n"
        content += "4. 验收与交付\n\n"
        
        content += "## 四、总结\n"
        content += "以上是根据您的需求生成的初步方案，如需进一步细化，请提供更多信息。\n"
        
        return content
    
    async def _generate_content_with_llm(self, parsed: Dict[str, Any]) -> str:
        task = parsed.get("task", "")
        keywords = parsed.get("keywords", [])
        summary = parsed.get("summary", "")
        
        prompt = f"""
请根据以下信息生成一份完整的方案文档：

任务：{task}
关键词：{", ".join(keywords)}
摘要：{summary}

请按照以下结构输出：
1. 需求分析
2. 方案概述
3. 实施步骤
4. 预期效果
5. 总结

请输出详细、专业的内容。
"""
        response = await self._call_llm(prompt, model=self.local_model, temperature=0.7, max_tokens=4096)
        return response or self._generate_content(parsed)