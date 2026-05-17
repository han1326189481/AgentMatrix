from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json
from datetime import datetime

class ResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("result", "Result Agent")
        self.local_model = "qwen2.5:1.5b"
        from app.config import settings
        self.cloud_model = settings.deepseek_model if hasattr(settings, 'deepseek_model') else "deepseek-chat"
    
    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"结果导出: {input_data.content[:50]}...")
        
        try:
            input_data_dict = json.loads(input_data.content)
            
            user_task = input_data_dict.get("user_task", "")
            summary_result = input_data_dict.get("summary_result", {})
            review_result = input_data_dict.get("review_result", {})
            judge_result = input_data_dict.get("judge_result", {})
            writer_output = input_data_dict.get("writer_output", "")
            executed_locally = input_data_dict.get("executed_locally", True)
            complexity_score = input_data_dict.get("complexity_score", 0.0)
            judge_decision = input_data_dict.get("judge_decision", "local_output")
            cloud_mode = input_data_dict.get("cloud_mode", "none")
            
            model_used = self.local_model
            
            # 检查是否有 DeepSeek API Key
            from app.config import settings
            has_api_key = settings.deepseek_api_key and settings.deepseek_api_key.strip()
            
            if has_api_key and input_data.use_cloud and cloud_mode != "none":
                writer_output = await self._enhance_with_cloud(user_task, summary_result, writer_output, cloud_mode)
                executed_locally = False
                model_used = self.cloud_model
            
            final_result = self._format_result(judge_result, input_data.context, writer_output, complexity_score, executed_locally, judge_decision, cloud_mode)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=final_result,
                success=True,
                message="结果生成完成",
                metadata={"format": "markdown", "length": len(final_result), "model_used": model_used, "executed_locally": executed_locally},
                model_used=model_used
            )
        
        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(
                content="",
                success=False,
                message=str(e)
            )

    async def _enhance_with_cloud(self, user_task: str, summary_result: Any, writer_output: str, cloud_mode: str) -> str:
        summary_text = ""
        if isinstance(summary_result, str):
            try:
                summary_data = json.loads(summary_result)
                summary_text = summary_data.get("summary", summary_result)
                keywords = summary_data.get("keywords", [])
                requirements = summary_data.get("requirements", [])
                if keywords:
                    summary_text += f"\n关键词：{', '.join(keywords)}"
                if requirements:
                    summary_text += f"\n需求点：{'; '.join(requirements)}"
            except:
                summary_text = str(summary_result)

        system_prompt = "你是 AgentMatrix 平台的 AI 助手。你需要根据用户需求、任务摘要，重新生成一份更高质量、更专业的完整回复。你永远不代表任何其他公司的AI助手。"

        prompt = f"""
请根据以下信息，重新生成一份高质量、专业的完整回复。

【用户问题】
{user_task}

【需求摘要】
{summary_text}

【重写要求】
1. 内容必须专业、准确、有深度
2. 直接回应用户的问题，不要偏离
3. 使用清晰的 Markdown 格式
4. 确保内容的可执行性和实用性
5. 不要包含"根据您的要求"等开场白

请直接输出最终内容：
"""

        response = await self._call_llm(prompt, model=self.cloud_model, use_cloud=True, system_prompt=system_prompt)
        return response

    def _format_result(self, judge_result: Dict[str, Any], context: Dict[str, Any], writer_output: str, 
                      complexity_score: float, executed_locally: bool, judge_decision: str, cloud_mode: str) -> str:
        
        if isinstance(judge_result, str):
            try:
                judge_result = json.loads(judge_result)
            except:
                judge_result = {}
        
        # 直接返回Writer的内容，不要添加那些复杂的报告信息
        if writer_output:
            cleaned_content = self._clean_content(writer_output)
            return cleaned_content
        else:
            return "暂无生成内容，请重试。"

    def _clean_content(self, content: str) -> str:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "content" in parsed:
                return str(parsed["content"])
            elif isinstance(parsed, dict) and "task" in parsed:
                return json.dumps(parsed, ensure_ascii=False, indent=2)
        except:
            pass
        
        content = content.replace("【知识增强】", "")
        content = content.replace("【领域知识】", "")
        content = content.replace("【通用知识】", "")
        content = content.replace("【匹配关键词】", "")
        
        return content.strip()