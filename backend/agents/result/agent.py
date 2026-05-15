from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any
import json
from datetime import datetime

class ResultAgent(BaseAgent):
    def __init__(self):
        super().__init__("result", "Result Agent")
        self.local_model = "qwen2.5:1.5b"
        self.cloud_model = "deepseek-r1-distill"
    
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
            
            if judge_decision != "local_output" and cloud_mode != "none":
                writer_output = await self._enhance_with_cloud(user_task, writer_output, cloud_mode)
                executed_locally = False
            
            final_result = self._format_result(judge_result, input_data.context, writer_output, complexity_score, executed_locally, judge_decision, cloud_mode)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            return AgentOutput(
                content=final_result,
                success=True,
                message="结果生成完成",
                metadata={"format": "markdown", "length": len(final_result), "model_used": self.local_model, "executed_locally": executed_locally},
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

    async def _enhance_with_cloud(self, user_task: str, writer_output: str, cloud_mode: str) -> str:
        system_prompt = "请根据用户需求优化以下内容"
        
        if cloud_mode == "full_rewrite":
            prompt = f"根据用户需求重新生成专业内容：\n\n用户需求：{user_task}\n\n已有内容：{writer_output}\n\n请提供完整的专业回复。"
        elif cloud_mode == "polish":
            prompt = f"请优化以下内容，使其更加专业和完善：\n\n{writer_output}"
        else:
            prompt = f"请完善以下内容：\n\n{writer_output}"
        
        response = await self._call_llm(prompt, model=self.cloud_model, use_cloud=True, system_prompt=system_prompt)
        return response

    def _format_result(self, judge_result: Dict[str, Any], context: Dict[str, Any], writer_output: str, 
                      complexity_score: float, executed_locally: bool, judge_decision: str, cloud_mode: str) -> str:
        
        if isinstance(judge_result, str):
            try:
                judge_result = json.loads(judge_result)
            except:
                judge_result = {}
        
        result = "# [Report] 任务执行结果\n\n"
        
        result += "## [Agent] 执行流程\n"
        result += "| 智能体 | 状态 | 模型 |\n"
        result += "|--------|------|------|\n"
        result += "| Knowledge Agent | [OK] 完成 | qwen2.5 |\n"
        result += "| Summary Agent | [OK] 完成 | qwen2.5 |\n"
        result += "| Writer Agent | [OK] 完成 | phi4-mini |\n"
        result += "| Review Agent | [OK] 完成 | phi4-mini |\n"
        result += "| Judge Agent | [OK] 完成 | rule-based |\n"
        
        if not executed_locally:
            result += "| Cloud Enhancement | [OK] 完成 | DeepSeek |\n"
        
        result += "| Result Agent | [OK] 完成 | qwen2.5 |\n\n"
        
        result += "## [Details] 执行详情\n"
        result += f"- 复杂度评分: {complexity_score:.2f}\n"
        
        review_score = judge_result.get("review_score", 0.0)
        result += f"- Review评分: {review_score:.2f}\n"
        result += f"- 执行方式: {judge_decision}\n"
        result += f"- Cloud模式: {cloud_mode}\n"
        
        reasons = judge_result.get("reason", []) or judge_result.get("reasons", [])
        if reasons:
            result += "\n## [Reason] 决策原因\n"
            for reason in reasons:
                result += f"- {reason}\n"
        
        review_result = {}
        if context and "review" in context:
            try:
                review_result = json.loads(context["review"])
            except:
                pass
        
        if review_result:
            result += "\n## [Review] 质量评审详情\n"
            result += "| 维度 | 评分 |\n"
            result += "|------|------|\n"
            dimensions = review_result.get("dimensions", {})
            result += f"| 结构完整性 | {dimensions.get('structure', 0):.2f} |\n"
            result += f"| 需求相关性 | {dimensions.get('relevance', 0):.2f} |\n"
            result += f"| 内容丰富度 | {dimensions.get('richness', 0):.2f} |\n"
            result += f"| 专业性 | {dimensions.get('professional', 0):.2f} |\n"
            result += f"| 可执行性 | {dimensions.get('actionable', 0):.2f} |\n"
            
            issues = review_result.get("issues", [])
            if issues:
                result += "\n### [Issue] 发现的问题\n"
                for issue in issues:
                    result += f"- {issue}\n"
            
            suggestions = review_result.get("suggestions", [])
            if suggestions:
                result += "\n### [Suggestion] 修改建议\n"
                for suggestion in suggestions:
                    result += f"- {suggestion}\n"
        
        result += "\n---\n\n"
        result += "## [Output] 最终输出\n\n"
        if writer_output:
            cleaned_content = self._clean_content(writer_output)
            result += cleaned_content
        else:
            result += "暂无生成内容，请重试。\n"
        
        result += "\n\n---\n\n"
        result += "## [Complexity] 复杂度评估\n"
        result += "| 指标 | 数值 |\n"
        result += "|------|------|\n"
        result += f"| 复杂度评分 | {complexity_score:.2f} |\n"
        result += f"| Review评分 | {review_score:.2f} |\n"
        result += f"| 执行方式 | {judge_decision} |\n"
        result += f"| Cloud模式 | {cloud_mode} |\n"
        
        return result

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