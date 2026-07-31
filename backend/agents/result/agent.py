"""Result Agent - 结果格式化与云端增强（Skill Engine V2.1）

V2.1 变更：
- 优先使用 Judge Agent 提供的 weak_dimensions，避免重复解析
- 支持精确 cloud_mode：polish_professional / polish_completeness / polish_reasoning 等
- _cloud_full_rewrite() 针对性增强弱维度
- _cloud_polish() 针对性润色
"""
import json
import logging
from typing import Dict, Any, List, Optional
from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from agents.base.utils import safe_json_parse

logger = logging.getLogger(__name__)


class ResultAgent(BaseAgent):
    def __init__(self, settings=None):
        super().__init__("result", "Result Agent", settings=settings)
        # local_model 和 cloud_model 由 BaseAgent 从 ModelRegistry 读取，无需在此硬编码

    @staticmethod
    def _is_cloud_error(response: str) -> bool:
        """检测云端API响应是否为错误"""
        if not response:
            return True
        error_patterns = ["Error:", "Authentication Fails", "invalid_request_error",
                         "authentication_error", "rate_limit", "timeout", "connection error"]
        return any(pattern.lower() in response.lower() for pattern in error_patterns)

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"结果格式化: {input_data.content[:50]}...")

        try:
            input_data_dict = safe_json_parse(input_data.content)

            user_task = input_data_dict.get("user_task", "")
            writer_output = input_data_dict.get("writer_output", "")
            judge_decision = input_data_dict.get("judge_decision", "local_output")
            cloud_mode = input_data_dict.get("cloud_mode", "none")
            summary_result = input_data_dict.get("summary_result", {})

            # Skill Engine V2: 提取 review_result 和 skill_path
            review_result_raw = input_data_dict.get("review_result", "")
            skill_path = input_data_dict.get("skill_path", ["root", "daily"])

            # V2.1: 优先使用 Judge 提供的 weak_dimensions，避免重复解析
            judge_result = safe_json_parse(input_data_dict.get("judge_result", "{}"))
            weak_dimensions = judge_result.get("weak_dimensions", [])
            if not weak_dimensions:
                # 回退：Judge 未提供时自行从 review_result 提取
                weak_dimensions = self._extract_weak_dimensions(review_result_raw)
                logger.debug("Result Agent: Judge 未提供 weak_dimensions，自行提取")
            else:
                logger.debug(f"Result Agent: 使用 Judge 提供的 weak_dimensions "
                           f"({[d['key'] for d in weak_dimensions]})")

            model_used = self.local_model
            executed_locally = True
            cloud_failed = False

            settings = self._get_settings()
            has_api_key = bool(settings.deepseek_api_key and settings.deepseek_api_key.strip())

            # 云端增强逻辑（带失败回退）
            if has_api_key and judge_decision == "cloud_enhance" and cloud_mode != "none":
                try:
                    # V2.1: 支持精确 cloud_mode（polish_professional / polish_completeness 等）
                    if cloud_mode == "full_rewrite":
                        cloud_result = await self._cloud_full_rewrite(
                            user_task, summary_result, writer_output,
                            weak_dimensions=weak_dimensions, skill_path=skill_path
                        )
                    elif cloud_mode.startswith("polish"):
                        cloud_result = await self._cloud_polish(
                            user_task, writer_output,
                            weak_dimensions=weak_dimensions, skill_path=skill_path,
                            polish_mode=cloud_mode  # V2.1: 传递精确模式
                        )
                    else:
                        cloud_result = None

                    # 检测云端调用是否失败
                    if cloud_result and not self._is_cloud_error(cloud_result):
                        writer_output = cloud_result
                        executed_locally = False
                        model_used = self.cloud_model
                    else:
                        logger.warning(f"云端增强失败，回退到本地输出。错误: {cloud_result[:200] if cloud_result else 'empty response'}")
                        cloud_failed = True
                except Exception as cloud_err:
                    logger.error(f"云端增强异常，回退到本地输出: {cloud_err}")
                    cloud_failed = True

            # 清理和格式化最终输出
            final_result = self._clean_content(writer_output)

            await self._set_status("idle")
            await self._set_current_task(None)

            return AgentOutput(
                content=final_result,
                success=True,
                message="结果格式化完成",
                metadata={
                    "format": "markdown",
                    "length": len(final_result),
                    "model_used": model_used,
                    "executed_locally": executed_locally,
                    "cloud_failed": cloud_failed,
                    "weak_dimensions": weak_dimensions,
                    "skill_path": skill_path,
                },
                model_used=model_used
            )

        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(content="", success=False, message=str(e))

    # ============================================================
    # 弱维度分析
    # ============================================================

    @staticmethod
    def _extract_weak_dimensions(review_result_raw) -> List[Dict[str, Any]]:
        """从 review_result 中提取弱维度（评分 < 0.70 的维度）

        Args:
            review_result_raw: Review Agent 的原始输出（JSON 字符串或 dict）

        Returns:
            弱维度列表，按评分升序排列 [{"name": "accuracy", "score": 0.45, "issues": [...], "suggestion": "..."}, ...]
        """
        if not review_result_raw:
            return []

        try:
            if isinstance(review_result_raw, str):
                data = safe_json_parse(review_result_raw)
                if data is None:
                    data = json.loads(review_result_raw)
            else:
                data = review_result_raw
        except (json.JSONDecodeError, TypeError):
            return []

        if not isinstance(data, dict):
            return []

        # 兼容 V2 ReviewReport 格式: {"dimensions": {"accuracy": {"score": ..., "issues": ...}, ...}}
        dimensions = data.get("dimensions", {})

        # 兼容旧格式: {"dimensions": {"structure": 0.7, "relevance": 0.7, ...}}
        weak = []
        for name, dim_data in dimensions.items():
            if isinstance(dim_data, dict):
                score = dim_data.get("score", 0.0)
                issues = dim_data.get("issues", [])
                suggestion = dim_data.get("suggestion", "")
            elif isinstance(dim_data, (int, float)):
                score = float(dim_data)
                issues = []
                suggestion = ""
            else:
                continue

            if score < 0.70:
                weak.append({
                    "name": name,
                    "score": round(score, 2),
                    "issues": issues,
                    "suggestion": suggestion,
                })

        # 按评分升序排列（最弱的排前面）
        weak.sort(key=lambda x: x["score"])
        return weak

    # ============================================================
    # 云端增强方法
    # ============================================================

    async def _cloud_full_rewrite(self, user_task: str, summary_result: Any,
                                   writer_output: str, weak_dimensions: List[Dict] = None,
                                   skill_path: List[str] = None) -> str:
        """云端完整重写（针对性增强弱维度）

        Args:
            user_task: 用户原始任务
            summary_result: Knowledge Agent 的需求摘要
            writer_output: Writer Agent 的本地输出
            weak_dimensions: 弱维度列表（来自 ReviewReport）
            skill_path: 技能路径
        """
        summary_text = self._build_summary_text(summary_result)

        # 构建弱维度增强指令
        weak_enhancement = self._build_weak_enhancement_prompt(weak_dimensions)

        prompt = f"""请根据以下信息，重新生成一份高质量、专业的完整回复。

【用户问题】
{user_task}

【需求摘要】
{summary_text}

【本地草稿（供参考）】
{writer_output[:1000]}

【重写要求】
1. 内容必须专业、准确、有深度
2. 直接回应用户的问题，不要偏离
3. 使用清晰的 Markdown 格式
4. 确保内容的可执行性和实用性
5. 不要包含"根据您的要求"等开场白
{weak_enhancement}
请直接输出最终内容："""

        response = await self._call_llm(
            prompt, model=self.cloud_model, use_cloud=True,
            system_prompt=self._load_system_prompt(), temperature=0.3, max_tokens=4096
        )
        return response if response else writer_output

    async def _cloud_polish(self, user_task: str, writer_output: str,
                            weak_dimensions: List[Dict] = None,
                            skill_path: List[str] = None,
                            polish_mode: str = "polish") -> str:
        """V2.1: 云端润色优化（支持精确 polish_mode）

        Args:
            user_task: 用户原始任务
            writer_output: Writer Agent 的本地输出
            weak_dimensions: 弱维度列表
            skill_path: 技能路径
            polish_mode: 精确润色模式 (polish / polish_professional / polish_completeness / ...)
        """
        weak_enhancement = self._build_weak_enhancement_prompt(weak_dimensions, for_polish=True)

        # V2.1: 根据精确 polish_mode 调整润色重点
        polish_directives = self._get_polish_directive(polish_mode)

        prompt = f"""请对以下内容进行润色优化，保持原意和结构，只提升表达质量。

【用户需求】
{user_task}

【原始内容】
{writer_output[:2000]}

【润色要求】
{polish_directives}
{weak_enhancement}
请直接输出润色后的内容："""

        response = await self._call_llm(
            prompt, model=self.cloud_model, use_cloud=True,
            system_prompt=self._load_system_prompt(), temperature=0.3, max_tokens=4096
        )
        return response if response else writer_output

    @staticmethod
    def _get_polish_directive(polish_mode: str) -> str:
        """V2.1: 根据精确 polish_mode 返回针对性润色指令"""
        directives = {
            "polish_professional": (
                "1. 保持原有结构和核心内容\n"
                "2. 重点提升专业术语的准确性和权威性\n"
                "3. 使用更正式、专业的表达方式\n"
                "4. 确保技术概念的准确性"
            ),
            "polish_completeness": (
                "1. 保持原有核心内容\n"
                "2. 重点补充缺失的关键细节和步骤\n"
                "3. 确保内容覆盖全面，不遗漏要点\n"
                "4. 适当添加必要的背景说明"
            ),
            "polish_reasoning": (
                "1. 保持原有内容\n"
                "2. 重点优化逻辑推理链条\n"
                "3. 确保因果关系清晰，论证充分\n"
                "4. 消除逻辑跳跃和矛盾"
            ),
            "polish_structure": (
                "1. 保持原有内容\n"
                "2. 重点优化段落结构和层次\n"
                "3. 确保内容组织合理，层次分明\n"
                "4. 使用适当的标题和分段"
            ),
            "polish_actionable": (
                "1. 保持原有内容\n"
                "2. 重点增强可执行性\n"
                "3. 添加具体的行动步骤和产出物\n"
                "4. 确保建议可落地实施"
            ),
        }
        default = (
            "1. 保持原有结构和核心内容\n"
            "2. 提升语言表达的专业性和流畅度\n"
            "3. 修正可能的语法错误\n"
            "4. 不要添加新的内容章节"
        )
        return directives.get(polish_mode, default)

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _build_summary_text(summary_result: Any) -> str:
        """从 summary_result 构建摘要文本"""
        if isinstance(summary_result, str):
            summary_data = safe_json_parse(summary_result)
            if summary_data:
                summary_text = summary_data.get("summary", "")
                keywords = summary_data.get("keywords", [])
                if keywords:
                    summary_text += f"\n关键词：{', '.join(keywords)}"
                return summary_text
            return str(summary_result)
        if isinstance(summary_result, dict):
            text = summary_result.get("summary", "")
            keywords = summary_result.get("keywords", [])
            if keywords:
                text += f"\n关键词：{', '.join(keywords)}"
            return text
        return str(summary_result) if summary_result else ""

    @staticmethod
    def _build_weak_enhancement_prompt(weak_dimensions: List[Dict], for_polish: bool = False) -> str:
        """根据弱维度构建针对性增强 Prompt

        Args:
            weak_dimensions: 弱维度列表
            for_polish: 是否为润色模式（True=轻量修正, False=完整重写）

        Returns:
            增强指令字符串
        """
        if not weak_dimensions:
            return ""

        # 维度名称映射
        DIM_NAMES = {
            "accuracy": "准确性",
            "professional": "专业性",
            "completeness": "完整性",
            "reasoning": "逻辑性",
            "structure": "结构性",
            "actionable": "可执行性",
        }

        # 维度增强建议
        DIM_ENHANCEMENTS = {
            "accuracy": "请重点修正事实性错误和不准确的表述，确保所有信息准确无误",
            "professional": "请提升内容的专业深度，使用更专业的术语和行业表达",
            "completeness": "请补充缺失的关键信息，确保内容全面完整，覆盖用户问题的所有方面",
            "reasoning": "请加强逻辑推理链条，确保论证过程清晰、有说服力",
            "structure": "请优化内容结构，使用更清晰的层次和段落组织",
            "actionable": "请增加具体可操作的步骤和建议，让内容更具实用性",
        }

        # 配对构建 (name, enhancement)，过滤无增强建议的维度
        pairs = []
        for d in weak_dimensions[:3]:
            dim_name = d["name"]
            enhancement = DIM_ENHANCEMENTS.get(dim_name, "")
            if enhancement:
                pairs.append((DIM_NAMES.get(dim_name, dim_name), enhancement))

        if not pairs:
            return ""

        if for_polish:
            # 润色模式：轻量级修正
            lines = ["\n## 针对性修正（检测到以下维度较弱）"]
            for i, (name, enhancement) in enumerate(pairs):
                lines.append(f"{i+1}. 【{name}】{enhancement}")
            return "\n".join(lines)
        else:
            # 完整重写模式：重点增强
            lines = ["\n## 重点增强维度（本地模型输出在这些维度得分较低，需要重点加强）"]
            for i, (name, enhancement) in enumerate(pairs):
                # 安全获取原始分数
                score = weak_dimensions[i]["score"] if i < len(weak_dimensions) else 0.0
                lines.append(f"{i+1}. 【{name}（当前得分: {score}）】{enhancement}")
            return "\n".join(lines)

    def _clean_content(self, content: str) -> str:
        """清理内容中的中间过程标记"""
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "content" in parsed:
                return str(parsed["content"])
            elif isinstance(parsed, dict) and "task" in parsed:
                return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, TypeError):
            pass

        # 移除中间过程标记
        content = content.replace("【知识增强】", "")
        content = content.replace("【领域知识】", "")
        content = content.replace("【通用知识】", "")
        content = content.replace("【匹配关键词】", "")
        content = content.replace("【知识库内容】", "")
        content = content.replace("【需求分析】", "")

        return content.strip() if content.strip() else "暂无生成内容，请重试。"