from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from typing import Dict, Any, List, Tuple
import json
import logging
import re

logger = logging.getLogger(__name__)

CATEGORY_RULES = {
    "greeting": {
        "base_complexity": 0.10,
        "force_decision": "local_output",
        "patterns": [r"^(你好|您好|hi|hello|嗨|hey|早上好|下午好|晚上好|good morning|good afternoon|good evening)[\s!！。.,，]*$",
                     r"^(在吗|在不在|有人吗|你在吗)[\s!！。.,，]*$"],
        "examples": "你好, hi, 早上好"
    },
    "identity": {
        "base_complexity": 0.12,
        "force_decision": "local_output",
        "patterns": [r"你是谁", r"你叫什么", r"你的名字", r"介绍自己", r"自我介绍", r"你是干什么的",
                     r"你是什么", r"你是做什么的", r"你的身份", r"你是哪个平台", r"你是哪个公司"],
        "examples": "你是谁, 你叫什么名字"
    },
    "chitchat": {
        "base_complexity": 0.15,
        "force_decision": "local_output",
        "patterns": [r"^(天气|心情|无聊|开心|难过|累了|困了|饿了|谢谢|感谢|辛苦)",
                     r"(怎么样|好不好|行不行|可以吗|对吗|是吗|对吧)[\s!！。.,，]*$"],
        "examples": "今天天气不错, 我心情好, 谢谢你"
    },
    "simple_fact": {
        "base_complexity": 0.25,
        "force_decision": None,
        "patterns": [r"^(什么是|什么叫|是什么|是谁|哪一个|哪一种|什么时候|在哪里|在哪里能|多少钱)",
                     r"(的定义|的意思|含义|概念).*[\s!！。.,，]*$",
                     r"^(介绍|简述|概述).*(是什么|特点|功能|作用)"],
        "examples": "什么是麒麟OS, 苹果多少钱一斤"
    },
    "knowledge_qa": {
        "base_complexity": 0.45,
        "force_decision": None,
        "patterns": [r"(有什么|有哪些|怎么样|如何|为什么|怎么|怎样)",
                     r"(特点|优势|缺点|区别|对比|比较|优劣|不同).*$"],
        "examples": "麒麟OS有什么特点, AI和机器学习有什么区别"
    },
    "howto": {
        "base_complexity": 0.55,
        "force_decision": None,
        "patterns": [r"^(怎么|如何|怎样)(安装|配置|使用|操作|设置|部署|搭建|编写|开发|创建|建立)",
                     r"(教程|指南|步骤|方法|技巧|攻略).*$"],
        "examples": "怎么安装麒麟系统, 如何配置AI开发环境"
    },
    "creation": {
        "base_complexity": 0.65,
        "force_decision": None,
        "patterns": [r"(帮我写|帮我生成|帮我创作|帮我做|写一封|写一篇|写一个|生成一篇|生成一个|创作)",
                     r"(情书|信件|诗歌|小说|故事|祝福语|感谢信|邀请函|演讲稿|文案|脚本|诗歌)",
                     r"(代写|代笔)"],
        "examples": "帮我写一封情书, 写一篇演讲稿"
    },
    "planning": {
        "base_complexity": 0.75,
        "force_decision": None,
        "patterns": [r"(策划|规划|方案|计划|安排|组织|筹备)(.*(校园|活动|项目|会议|赛事|运动会|晚会|展览|比赛))",
                     r"(校园|活动|项目|赛事|运动会|晚会)(.*(策划|规划|方案|计划))",
                     r"(制定|拟定|编制).*(方案|计划|规划|预算)"],
        "examples": "校园运动会策划方案, 活动规划"
    },
    "complex_task": {
        "base_complexity": 0.85,
        "force_decision": None,
        "patterns": [r"(完整|全面|详细|深度|专业).*(方案|报告|设计|分析|论文|文档|PPT|答辩)",
                     r"(系统|架构|平台).*(设计|开发|实现|搭建|构建)",
                     r"(多步骤|多阶段|综合性|系统性).*(任务|项目|工程)",
                     r"(技术选型|架构设计|系统设计|项目设计).*$"],
        "examples": "完整AI项目答辩方案与PPT, 系统架构设计"
    }
}

COMPLEXITY_KEYWORDS = {
    "medium": ["方案", "规划", "报告", "分析", "设计", "演示", "文档", "论文", "PPT", "思维导图", "流程图"],
    "high": ["详细", "完整", "全面", "深度", "专业", "系统性", "综合性", "预算", "时间线", "风险评估"],
    "critical": ["多步骤推理", "技术方案", "架构设计", "系统设计", "算法设计", "技术选型",
                 "端云协同", "多智能体", "RAG", "检索增强", "知识蒸馏"]
}


class JudgeAgent(BaseAgent):
    def __init__(self):
        super().__init__("judge", "Judge Agent")
        self.local_model = "phi4-mini:3.8b"

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"复杂度判断: {input_data.content[:50]}...")

        try:
            input_data_dict = json.loads(input_data.content)
            user_task = input_data_dict.get("user_task", "")
            summary_result = input_data_dict.get("summary_result", {})
            review_result = input_data_dict.get("review_result", {})
            writer_output = input_data_dict.get("writer_output", "")
            knowledge_found = input_data_dict.get("knowledge_found", False)

            judge_result = self._judge_complexity(
                user_task, summary_result, review_result, writer_output, knowledge_found
            )

            await self._set_status("idle")
            await self._set_current_task(None)

            executed_locally = judge_result["decision"] == "local_output"
            model_used = "rule-engine"

            logger.info(
                f"Judge Agent - Category: {judge_result['category']}, "
                f"Decision: {judge_result['decision']}, "
                f"Complexity: {judge_result['complexity_score']:.2f}, "
                f"Review Score: {judge_result['review_score']:.2f}, "
                f"Local: {executed_locally}"
            )

            return AgentOutput(
                content=json.dumps(judge_result, ensure_ascii=False),
                success=True,
                message=judge_result["decision"],
                metadata={
                    "complexity_score": judge_result["complexity_score"],
                    "review_score": judge_result["review_score"],
                    "decision": judge_result["decision"],
                    "cloud_mode": judge_result["cloud_mode"],
                    "category": judge_result["category"],
                    "executed_locally": executed_locally,
                    "model_used": model_used,
                    "reason": judge_result.get("reason", [])
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

    def _classify_question(self, user_task: str) -> Tuple[str, float, str]:
        user_task_clean = user_task.strip()

        for category, config in CATEGORY_RULES.items():
            for pattern in config["patterns"]:
                if re.search(pattern, user_task_clean, re.IGNORECASE):
                    return category, config["base_complexity"], config.get("force_decision", None)

        if len(user_task_clean) < 5:
            return "chitchat", 0.15, "local_output"

        if len(user_task_clean) < 15:
            return "simple_fact", 0.25, None

        return "knowledge_qa", 0.45, None

    def _calculate_complexity(self, user_task: str, writer_output: str, category: str,
                              base_complexity: float, knowledge_found: bool) -> float:
        score = base_complexity

        input_len = len(user_task.strip())
        if input_len > 500:
            score += 0.25
        elif input_len > 300:
            score += 0.18
        elif input_len > 150:
            score += 0.10
        elif input_len > 50:
            score += 0.05

        output_len = len(writer_output.strip())
        if output_len > 2000:
            score += 0.15
        elif output_len > 1000:
            score += 0.10
        elif output_len > 500:
            score += 0.05

        medium_count = sum(1 for kw in COMPLEXITY_KEYWORDS["medium"] if kw in user_task or kw in writer_output)
        high_count = sum(1 for kw in COMPLEXITY_KEYWORDS["high"] if kw in user_task or kw in writer_output)
        critical_count = sum(1 for kw in COMPLEXITY_KEYWORDS["critical"] if kw in user_task or kw in writer_output)

        score += medium_count * 0.04
        score += high_count * 0.06
        score += critical_count * 0.10

        if not knowledge_found and category not in ("greeting", "identity", "chitchat"):
            score += 0.15

        if "?" in user_task or "？" in user_task:
            question_count = user_task.count("?") + user_task.count("？")
            if question_count >= 2:
                score += 0.10

        if any(sep in user_task for sep in ["\n", "\r", "；", ";"]):
            parts = re.split(r'[\n\r；;]', user_task)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 3:
                score += 0.15

        return round(min(1.0, max(0.0, score)), 2)

    def _judge_complexity(self, user_task: str, summary_result: Dict[str, Any],
                          review_result: Dict[str, Any], writer_output: str,
                          knowledge_found: bool) -> Dict[str, Any]:

        category, base_complexity, force_decision = self._classify_question(user_task)

        if isinstance(review_result, str):
            try:
                review_result = json.loads(review_result)
            except:
                review_result = {}

        review_score = review_result.get("review_score", 0.7)
        if review_score == 0.0:
            review_score = 0.55

        complexity_score = self._calculate_complexity(
            user_task, writer_output, category, base_complexity, knowledge_found
        )

        decision, cloud_mode, reason = self._make_decision(
            category, complexity_score, review_score, user_task,
            knowledge_found, force_decision
        )

        return {
            "complexity_score": complexity_score,
            "review_score": round(review_score, 2),
            "decision": decision,
            "cloud_mode": cloud_mode,
            "category": category,
            "reason": reason
        }

    def _make_decision(self, category: str, complexity_score: float,
                       review_score: float, user_task: str,
                       knowledge_found: bool, force_decision: str) -> Tuple[str, str, List[str]]:

        from app.config import settings
        has_api_key = settings.deepseek_api_key and settings.deepseek_api_key.strip()

        if force_decision is not None:
            reason = [f"问题类别为 {category}（{CATEGORY_RULES[category]['examples']}），强制{force_decision}",
                      f"复杂度评分: {complexity_score:.2f}"]
            if not has_api_key and force_decision == "cloud_enhance":
                reason.append("DeepSeek API Key 未设置，降级为本地输出")
                return ("local_output", "none", reason)
            return (force_decision, "none", reason)

        if not has_api_key:
            return ("local_output", "none", ["DeepSeek API Key 未设置，强制本地输出"])

        reason = [f"问题类别: {category}"]

        if knowledge_found:
            reason.append(f"知识库已命中，本地直接输出（复杂度: {complexity_score:.2f}）")
            return ("local_output", "none", reason)

        if not knowledge_found and complexity_score < 0.50:
            reason.append(f"知识库未命中但复杂度较低（{complexity_score:.2f} < 0.50），本地输出")
            return ("local_output", "none", reason)

        if not knowledge_found and complexity_score >= 0.50:
            reason.append(f"知识库未命中且复杂度较高（{complexity_score:.2f} >= 0.50），调用DeepSeek云端重写")
            return ("cloud_enhance", "full_rewrite", reason)

        reason.append(f"综合判定，云端增强")
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

        category_info = "\n".join([
            f"- {cat}: 基数{cfg['base_complexity']}, 示例: {cfg['examples']}"
            for cat, cfg in CATEGORY_RULES.items()
        ])

        prompt = f"""
你是 Judge Agent。你必须严格遵循规则引擎的逻辑做决策。

=== 问题分类体系 ===
{category_info}

=== 决策矩阵（严格遵循）===

1. greeting/identity/chitchat → 强制 local_output（无论knowledge是否命中）
2. simple_fact + knowledge命中 → local_output
3. simple_fact + knowledge未命中 → cloud_enhance + full_rewrite
4. 其他类别:
   - complexity < 0.35 → local_output
   - complexity 0.35-0.60 + review >= 0.70 → local_output
   - complexity 0.35-0.60 + review < 0.70 → cloud_enhance + polish
   - complexity 0.60-0.80 + review >= 0.80 → local_output
   - complexity 0.60-0.80 + review < 0.80 → cloud_enhance + full_rewrite
   - complexity > 0.80 → cloud_enhance + full_rewrite

=== 当前任务 ===
用户输入: {user_task}
Writer输出长度: {len(writer_output)}
Review评分: {review_score}

请分类并输出JSON:
{{
  "category": "问题类别",
  "complexity_score": 0.0,
  "review_score": {review_score},
  "decision": "local_output或cloud_enhance",
  "cloud_mode": "none/polish/full_rewrite",
  "reason": ["理由1", "理由2"]
}}
"""

        response = await self._call_llm(prompt, model=self.local_model, use_cloud=use_cloud, temperature=0.1)

        try:
            result = json.loads(response)
            if all(k in result for k in ["complexity_score", "decision", "cloud_mode", "reason"]):
                result["review_score"] = round(review_score, 2)
                result["complexity_score"] = round(float(result["complexity_score"]), 2)
                if "category" not in result:
                    result["category"] = "unknown"
                return result
        except Exception:
            pass

        return self._judge_complexity(user_task, summary_result, review_result, writer_output, True)
