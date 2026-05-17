from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any, List
import json
import os
import re

class ReviewAgent(BaseAgent):
    def __init__(self):
        super().__init__("review", "Review Agent")
        self.local_model = "phi4-mini:3.8b"
        self.world_rules = self._load_world_rules()

    def _load_world_rules(self) -> List[Dict[str, Any]]:
        rules = []
        role_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "roletxt", "review.txt")
        
        if os.path.exists(role_file):
            try:
                with open(role_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    try:
                        rules = json.loads(content)
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                pass
        
        if not rules:
            rules = [
                {"keywords": ["校园", "活动", "策划"], "inject": "必须检查是否包含活动流程、预算、时间安排。"},
                {"keywords": ["项目", "方案"], "inject": "必须检查是否包含实施步骤与目标分析。"},
                {"keywords": ["ppt", "汇报"], "inject": "必须检查是否具备结构化章节。"}
            ]
        
        return rules

    def _get_injection_rules(self, content: str) -> str:
        injections = []
        content_lower = content.lower()
        for rule in self.world_rules:
            for kw in rule.get("keywords", []):
                if kw.lower() in content_lower:
                    injections.append(rule.get("inject", ""))
                    break
        return "\n".join(injections)

    def _detect_simple_conversation(self, user_task: str, writer_output: str) -> bool:
        task_lower = user_task.strip().lower()
        if len(task_lower) < 10:
            return True
        simple_patterns = [
            r"^(你好|您好|hi|hello|嗨|hey|早上好|下午好|晚上好)",
            r"^(在吗|在不在|有人吗|你在吗)",
            r"^(你是谁|你叫什么|你的名字|自我介绍|你是什么)",
            r"^(谢谢|感谢|辛苦|多谢|thanks)",
            r"^(天气|心情|无聊|开心|难过|累了|困了|饿了)",
        ]
        for pattern in simple_patterns:
            if re.search(pattern, task_lower):
                return True
        if len(writer_output) < 200 and not re.search(r"(# |## |一、|二、|1\.|2\.)", writer_output):
            return True
        return False

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"质量评审: {input_data.content[:50]}...")
        
        try:
            input_data_dict = json.loads(input_data.content)
            user_task = input_data_dict.get("user_task", "")
            summary = input_data_dict.get("summary", "")
            writer_output = input_data_dict.get("writer_output", "")
            
            if input_data.use_llm:
                review_result = await self._review_content_with_llm(user_task, summary, writer_output, use_cloud=input_data.use_cloud)
            else:
                review_result = self._review_content(user_task, summary, writer_output)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            model_used = self.cloud_model if input_data.use_cloud else self.local_model
            
            return AgentOutput(
                content=json.dumps(review_result, ensure_ascii=False),
                success=True,
                message="质量评审完成",
                metadata={
                    "review_score": review_result["review_score"],
                    "dimensions": review_result["dimensions"],
                    "issues": review_result["issues"],
                    "suggestions": review_result["suggestions"],
                    "pass": review_result["pass"],
                    "model_used": model_used,
                    "use_cloud": input_data.use_cloud
                },
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

    def _review_content(self, user_task: str, summary: str, writer_output: str) -> Dict[str, Any]:
        is_simple_conversation = self._detect_simple_conversation(user_task, writer_output)

        if is_simple_conversation:
            return {
                "review_score": 0.85,
                "dimensions": {
                    "structure": 0.80,
                    "relevance": 0.90,
                    "richness": 0.80,
                    "professional": 0.85,
                    "actionable": 0.85
                },
                "issues": [],
                "suggestions": ["简单对话，内容自然合理"],
                "pass": True
            }

        structure = 0.5
        relevance = 0.7
        richness = 0.4
        professional = 0.5
        actionable = 0.5
        
        issues = []
        suggestions = []
        
        if len(writer_output) < 100:
            issues.append("内容过短")
            richness -= 0.2
        elif len(writer_output) > 500:
            richness += 0.2
        
        if "活动流程" not in writer_output and "流程" not in writer_output:
            if "活动" in user_task or "策划" in user_task:
                issues.append("缺少活动流程")
                structure -= 0.2
                actionable -= 0.2
        
        if "预算" not in writer_output:
            if "预算" in user_task or "活动" in user_task or "方案" in user_task:
                issues.append("缺少预算安排")
                structure -= 0.15
                actionable -= 0.15
        
        if "时间" not in writer_output and "日期" not in writer_output:
            if "活动" in user_task or "策划" in user_task:
                issues.append("缺少时间安排")
                structure -= 0.15
                actionable -= 0.15
        
        if "# " in writer_output or "一、" in writer_output or "1." in writer_output:
            structure += 0.2
        
        if "## " in writer_output or "（一）" in writer_output or "1.1" in writer_output:
            structure += 0.1
        
        task_lower = user_task.lower()
        output_lower = writer_output.lower()
        task_keywords = ["活动", "策划", "方案", "项目", "报告"]
        matched_keywords = sum(1 for kw in task_keywords if kw in task_lower and kw in output_lower)
        if matched_keywords >= 2:
            relevance += 0.2
        
        if "总结" in writer_output or "结论" in writer_output:
            structure += 0.1
            professional += 0.1
        
        if "具体" in writer_output or "详细" in writer_output or "步骤" in writer_output:
            actionable += 0.2
        
        structure = max(0.0, min(1.0, structure))
        relevance = max(0.0, min(1.0, relevance))
        richness = max(0.0, min(1.0, richness))
        professional = max(0.0, min(1.0, professional))
        actionable = max(0.0, min(1.0, actionable))
        
        review_score = (structure + relevance + richness + professional + actionable) / 5
        
        if "内容过短" in issues:
            suggestions.append("增加内容详细度")
        if "缺少活动流程" in issues:
            suggestions.append("补充活动流程章节")
        if "缺少预算安排" in issues:
            suggestions.append("增加预算模块")
        if "缺少时间安排" in issues:
            suggestions.append("添加时间线")
        if not suggestions:
            suggestions.append("内容质量良好，建议检查是否有遗漏细节")
        
        return {
            "review_score": round(review_score, 2),
            "dimensions": {
                "structure": round(structure, 2),
                "relevance": round(relevance, 2),
                "richness": round(richness, 2),
                "professional": round(professional, 2),
                "actionable": round(actionable, 2)
            },
            "issues": issues,
            "suggestions": suggestions,
            "pass": review_score >= 0.65
        }

    async def _review_content_with_llm(self, user_task: str, summary: str, writer_output: str, use_cloud: bool = False) -> Dict[str, Any]:
        if self._detect_simple_conversation(user_task, writer_output):
            return self._review_content(user_task, summary, writer_output)

        injection_rules = self._get_injection_rules(user_task)

        few_shot = """
=== Few-shot 示例 ===

示例1（低质量）:
输入任务：写校园活动策划
Writer输出：举办活动促进同学交流。
输出：
{"review_score":0.42,"dimensions":{"structure":0.3,"relevance":0.7,"richness":0.2,"professional":0.4,"actionable":0.5},"issues":["内容过短","缺少活动流程","缺少预算与时间安排"],"suggestions":["增加活动目标","补充时间线","增加预算模块"],"pass":false}

示例2（高质量）:
输入任务：生成完整的XX系统设计方案
Writer输出：（包含完整章节、详细分析、实施步骤的专业文档）
输出：
{"review_score":0.86,"dimensions":{"structure":0.9,"relevance":0.9,"richness":0.8,"professional":0.9,"actionable":0.8},"issues":["预算部分略简略"],"suggestions":["补充详细预算表"],"pass":true}
"""

        prompt = f"""
你是 Review Agent。

你的职责：
1. 检查内容是否完整
2. 检查是否偏离用户需求
3. 检查结构是否合理
4. 检查内容是否专业
5. 给出质量评分与修改建议

你不能重新生成全文。

{injection_rules}

{few_shot}

你必须：
- 使用结构化JSON输出
- 不允许输出废话
- 必须指出问题
- 必须给出评分
- 必须给出建议

评分标准：
1. structure（结构完整性）- 检查是否有清晰的章节、标题、逻辑层次
2. relevance（需求相关性）- 检查是否符合用户原始需求
3. richness（内容丰富度）- 检查内容是否详细、全面
4. professional（专业性）- 检查语言表达是否专业、正式
5. actionable（可执行性）- 检查方案是否具体、可落地

每项评分范围：0~1

最终总分：review_score = 五项平均值

决策规则：
- review_score >= 0.8 → 高质量，允许直接输出
- 0.65 ~ 0.8 → 中等质量，建议本地增强
- < 0.65 → 低质量，建议调用云端API

用户任务：{user_task}

需求摘要：{summary}

Writer输出：
{writer_output}

输出格式必须严格遵守JSON：
{{
  "review_score": 0.0,
  "dimensions": {{
    "structure": 0.0,
    "relevance": 0.0,
    "richness": 0.0,
    "professional": 0.0,
    "actionable": 0.0
  }},
  "issues": [
    ""
  ],
  "suggestions": [
    ""
  ],
  "pass": true
}}
"""

        response = await self._call_llm(prompt, model=self.local_model, use_cloud=use_cloud, temperature=0.2)

        try:
            result = json.loads(response)
            if "review_score" in result and "dimensions" in result:
                if result["review_score"] == 0.0:
                    return self._review_content(user_task, summary, writer_output)
                result["pass"] = result["review_score"] >= 0.65
                return result
        except Exception as e:
            pass

        return self._review_content(user_task, summary, writer_output)