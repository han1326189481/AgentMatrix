from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any, List
import json

class JudgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("judge", "Judge Agent")
        self.local_model = "phi4-mini"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"复杂度判断: {input_data.content[:50]}...")
        
        try:
            input_data_dict = json.loads(input_data.content)
            user_task = input_data_dict.get("user_task", "")
            summary_result = input_data_dict.get("summary_result", {})
            review_result = input_data_dict.get("review_result", {})
            writer_output = input_data_dict.get("writer_output", "")
            
            if input_data.use_llm:
                judge_result = await self._judge_complexity_with_llm(user_task, summary_result, review_result, writer_output, use_cloud=input_data.use_cloud)
            else:
                judge_result = self._judge_complexity(user_task, summary_result, review_result, writer_output)
            
            await self._set_status("idle")
            await self._set_current_task(None)
            
            executed_locally = judge_result["decision"] == "local_output"
            model_used = self.cloud_model if input_data.use_cloud else ("rule-based" if not input_data.use_llm else self.local_model)
            
            return AgentOutput(
                content=json.dumps(judge_result, ensure_ascii=False),
                success=True,
                message=judge_result["decision"],
                metadata={
                    "complexity_score": judge_result["complexity_score"],
                    "review_score": judge_result["review_score"],
                    "decision": judge_result["decision"],
                    "cloud_mode": judge_result["cloud_mode"],
                    "executed_locally": executed_locally,
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

    def _calculate_complexity(self, user_task: str, writer_output: str) -> float:
        score = 0.2
        
        simple_questions = ["什么是", "什么叫", "是什么", "有什么", "有哪些", "怎么样", "如何", "为什么", "在哪"]
        is_simple_question = any(kw in user_task[:10] for kw in simple_questions)
        
        if is_simple_question and len(user_task) < 50:
            return min(0.35, max(0.1, score))
        
        complexity_keywords_1 = ["方案", "规划", "预算", "时间线", "ppt", "思维导图", "报告", "详细", "完整", "专业"]
        found_keywords = 0
        for kw in complexity_keywords_1:
            if kw in user_task or kw in writer_output:
                found_keywords += 1
                score += 0.05
        
        if found_keywords >= 3:
            score += 0.15
        
        if len(user_task) > 100:
            score += 0.1
        if len(user_task) > 300:
            score += 0.15
        
        if len(writer_output) > 500:
            score += 0.1
        
        complexity_keywords_2 = ["多步骤推理", "项目设计", "AI系统", "技术方案"]
        for kw in complexity_keywords_2:
            if kw in user_task or kw in writer_output:
                score += 0.25
                break
        
        complexity_keywords_3 = ["流程", "分工", "宣传", "应急", "预案", "分配", "主题", "安排"]
        found_advanced = 0
        for kw in complexity_keywords_3:
            if kw in user_task or kw in writer_output:
                found_advanced += 1
                if found_advanced >= 2:
                    score += 0.15
                    break
        
        return min(1.0, max(0.0, score))

    def _judge_complexity(self, user_task: str, summary_result: Dict[str, Any], 
                         review_result: Dict[str, Any], writer_output: str) -> Dict[str, Any]:
        
        complexity_score = self._calculate_complexity(user_task, writer_output)
        
        if isinstance(review_result, str):
            try:
                review_result = json.loads(review_result)
            except:
                review_result = {}
        
        review_score = review_result.get("review_score", 0.7)
        
        decision, cloud_mode, reason = self._make_decision(complexity_score, review_score, user_task)
        
        return {
            "complexity_score": round(complexity_score, 2),
            "review_score": round(review_score, 2),
            "decision": decision,
            "cloud_mode": cloud_mode,
            "reason": reason
        }

    def _make_decision(self, complexity_score: float, review_score: float, user_task: str) -> tuple:
        reason = []
        
        # 更宽松的决策规则：低复杂度问题尽量使用本地模型
        if complexity_score < 0.45:
            reason.append("任务简单")
            if review_score >= 0.5:
                reason.append("本地结果可接受")
                return ("local_output", "none", reason)
            elif review_score >= 0.4:
                reason.append("本地结果基本满足要求")
                return ("local_output", "none", reason)
            else:
                reason.append("本地结果质量一般，建议优化")
                return ("local_retry", "polish", reason)
        
        elif complexity_score < 0.6:
            reason.append("任务复杂度较低")
            if review_score >= 0.6:
                reason.append("本地结果质量良好")
                return ("local_output", "none", reason)
            elif review_score >= 0.5:
                reason.append("本地结果可接受")
                return ("local_output", "none", reason)
            else:
                reason.append("本地结果质量不足")
                return ("cloud_enhance", "polish", reason)
        
        elif complexity_score <= 0.8:
            reason.append("任务复杂度中等")
            if review_score >= 0.7:
                reason.append("本地结果质量较高")
                return ("local_output", "none", reason)
            elif review_score >= 0.6:
                reason.append("本地结果可接受，建议优化")
                return ("local_retry", "polish", reason)
            else:
                reason.append("本地生成质量不足")
                return ("cloud_enhance", "full_rewrite", reason)
        
        else:
            reason.append("任务复杂")
            if "方案" in user_task or "规划" in user_task:
                reason.append("涉及正式文档")
            if len(user_task) > 300:
                reason.append("长文本生成")
            if "预算" in user_task or "时间线" in user_task:
                reason.append("涉及规划与预算")
            if review_score < 0.65:
                reason.append("本地生成质量不足")
            return ("cloud_enhance", "full_rewrite", reason)

    async def _judge_complexity_with_llm(self, user_task: str, summary_result: Dict[str, Any],
                                         review_result: Dict[str, Any], writer_output: str,
                                         use_cloud: bool = False) -> Dict[str, Any]:
        
        if isinstance(review_result, str):
            try:
                review_result = json.loads(review_result)
            except:
                review_result = {}
        
        review_score = review_result.get("review_score", 0.7)
        
        # 规则引擎详细规则 - 喂给 LLM 作为参考
        rules_engine_knowledge = """
【规则引擎参考知识】

=== 复杂度评分细则 ===
基础分: 0.2

1. 简单问答检测:
   - 如果任务以"什么是"、"什么叫"、"是什么"、"有什么"、"有哪些"、"怎么样"、"如何"、"为什么"、"在哪"开头且长度<50字 → 低复杂度(0.1-0.35)

2. 复杂度关键词检测(每匹配一个+0.05):
   - 方案、规划、预算、时间线、ppt、思维导图、报告、详细、完整、专业
   - 如果匹配>=3个，额外+0.15

3. 文本长度检测:
   - 用户任务>100字 → +0.1
   - 用户任务>300字 → +0.15
   - Writer输出>500字 → +0.1

4. 高级复杂度关键词(匹配任意一个+0.25):
   - 多步骤推理、项目设计、AI系统、技术方案

5. 进阶关键词检测(匹配>=2个+0.15):
   - 流程、分工、宣传、应急、预案、分配、主题、安排

=== 决策规则 ===
条件1: complexity < 0.4 AND review_score > 0.75
       → decision: local_output, cloud_mode: none
       → 理由: 任务简单，本地结果可接受

条件2: 0.4 <= complexity <= 0.7 AND review_score >= 0.65
       → decision: local_retry, cloud_mode: polish
       → 理由: 任务复杂度中等，建议本地优化

条件3: complexity > 0.7 OR review_score < 0.65
       → decision: cloud_enhance, cloud_mode: full_rewrite
       → 理由: 任务复杂或本地结果质量不足
"""
        
        prompt = f"""
你是 Judge Agent。

你的职责：
1. 判断任务复杂度
2. 判断本地结果质量
3. 决定是否调用云端API
4. 决定增强模式

{rules_engine_knowledge}

=== 当前任务 ===
用户任务：{user_task}

Writer输出长度：{len(writer_output)}字符

Review评分：{review_score}

=== 输出格式 ===
你必须输出严格的JSON格式，不要有任何多余内容：
{{
  "complexity_score": 0.0,
  "review_score": {review_score},
  "decision": "",
  "cloud_mode": "",
  "reason": [
    ""
  ]
}}

说明：
- complexity_score: 0.0-1.0之间的浮点数
- decision: 只能是 "local_output", "local_retry", "cloud_enhance" 之一
- cloud_mode: 只能是 "none", "polish", "partial_rewrite", "full_rewrite" 之一
- reason: 决策理由列表，至少包含1条
"""
        
        response = await self._call_llm(prompt, model=self.local_model, use_cloud=use_cloud, temperature=0.2)
        
        try:
            result = json.loads(response)
            if all(k in result for k in ["complexity_score", "decision", "cloud_mode", "reason"]):
                result["review_score"] = round(review_score, 2)
                result["complexity_score"] = round(result["complexity_score"], 2)
                return result
        except Exception as e:
            pass
        
        return self._judge_complexity(user_task, summary_result, review_result, writer_output)