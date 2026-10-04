"""Review Agent - 质量评审 + 难度阈值评估（Skill Engine V2 — 多维评审）

配置加载优先级：
  1. prompts/skills/review/base_scoring.yaml（V2 基础评分）
  2. prompts/skills/review/difficulty_matrix.yaml（V2 难度矩阵）
  3. configs/review_rules.yaml（V1 兼容）
  4. 内置默认规则（兜底）

Review Guard（V2.1 新增）:
  - 保证 Review Agent 永远输出合法 JSON，不会因解析失败返回 success=False
  - 三层容错：直接解析 → JSON 修复 → 规则引擎回退
  - 消除 NoneType 比较导致的崩溃
"""
import json
import re
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from agents.base.agent import BaseAgent, AgentInput, AgentOutput
from agents.base.utils import safe_json_parse, detect_simple_conversation, clamp_score, safe_float

logger = logging.getLogger(__name__)


class ReviewAgent(BaseAgent):
    def __init__(self, settings=None):
        super().__init__("review", "Review Agent", settings=settings)
        # local_model 由 BaseAgent 从 ModelRegistry 读取，无需在此硬编码
        self._rules: Optional[Dict[str, Any]] = None
        self._v2_configs: Optional[Dict[str, Any]] = None
        self._skill_manager = None
        self._review_engine = None

    @property
    def skill_manager(self):
        if self._skill_manager is None:
            from core.skill_engine.skill_manager import get_skill_manager
            self._skill_manager = get_skill_manager()
        return self._skill_manager

    @property
    def review_engine(self):
        """V2.1: 独立评审引擎（懒加载）"""
        if self._review_engine is None:
            from core.skill_engine.review_engine import get_review_engine
            self._review_engine = get_review_engine()
        return self._review_engine

    def _load_rules(self) -> Dict[str, Any]:
        """从 YAML 配置文件加载评分规则"""
        if self._rules is not None:
            return self._rules
        try:
            import yaml
            from shared.platform import get_configs_dir
            config_path = os.path.join(get_configs_dir(), "review_rules.yaml")
            with open(config_path, "r", encoding="utf-8") as f:
                self._rules = yaml.safe_load(f)
            logger.info("Review rules loaded from configs/review_rules.yaml")
        except Exception as e:
            logger.warning(f"Failed to load review_rules.yaml: {e}, using defaults")
            self._rules = self._default_rules()
        return self._rules

    def _default_rules(self) -> Dict[str, Any]:
        """内置默认规则（当 YAML 文件不可用时）"""
        return {
            "dimensions": {"structure": 0.5, "relevance": 0.7, "richness": 0.4, "professional": 0.5, "actionable": 0.5},
            "pass_threshold": 0.65,
            "simple_conversation": {
                "review_score": 0.85, "difficulty_threshold": 0.15,
                "dimensions": {"structure": 0.80, "relevance": 0.90, "richness": 0.80, "professional": 0.85, "actionable": 0.85}
            },
            "difficulty_threshold": {
                "complex_keywords": [
                    {"keyword": kw, "weight": 0.03} for kw in
                    ["方案", "策划", "设计", "架构", "系统", "分析", "报告", "论文", "PPT", "预算", "风险评估", "技术选型", "多智能体", "端云协同",
                     "治理", "政策", "政务", "基层", "数字化", "现代化", "行政许可", "放管服", "监管", "公共服务", "智慧城市", "营商环境", "行政审批", "治理体系", "治理能力",
                     "就业", "教育", "培养", "科研", "课程", "文献", "研究", "学分", "学术", "学位", "导师", "毕业", "招生", "学科建设", "产学研", "答辩"]
                ] + [
                    {"keyword": kw, "weight": 0.06} for kw in
                    ["深度分析", "全面分析", "系统论述", "深度评估", "全面评估", "深度对比", "全面对比", "系统对比"]
                ] + [
                    {"keyword": kw, "weight": 0.05} for kw in
                    ["多维度", "发展趋势", "关键路径", "演变", "颠覆性", "深层原因", "多重原因", "顶层设计"]
                ],
                "content_length_boost": [
                    {"threshold": 2000, "operator": ">", "boost": 0.1},
                    {"threshold": 1000, "operator": ">", "boost": 0.05}
                ],
                "multi_question_boost": 0.08, "multi_paragraph_boost": 0.08,
                "low_structure_penalty": 0.05, "low_professional_penalty": 0.05,
                "low_threshold": 0.5
            }
        }

    def _load_v2_configs(self) -> Dict[str, Any]:
        """加载 V2 评分配置（base_scoring + difficulty_matrix）

        配置路径：prompts/skills/review/
        缓存：实例级，首次加载后缓存
        """
        if self._v2_configs is not None:
            return self._v2_configs

        try:
            import yaml
            from shared.platform import get_prompts_dir
            review_dir = os.path.join(get_prompts_dir(), "skills", "review")

            base_config = {}
            diff_config = {}
            tech_config = {}

            # 加载基础评分配置
            base_path = os.path.join(review_dir, "base_scoring.yaml")
            if os.path.exists(base_path):
                with open(base_path, "r", encoding="utf-8") as f:
                    base_config = yaml.safe_load(f) or {}
                logger.info("V2 base scoring config loaded from base_scoring.yaml")

            # 加载难度矩阵
            diff_path = os.path.join(review_dir, "difficulty_matrix.yaml")
            if os.path.exists(diff_path):
                with open(diff_path, "r", encoding="utf-8") as f:
                    diff_config = yaml.safe_load(f) or {}
                logger.info("V2 difficulty matrix loaded from difficulty_matrix.yaml")

            # 加载技术领域评分配置
            tech_path = os.path.join(review_dir, "tech_scoring.yaml")
            if os.path.exists(tech_path):
                with open(tech_path, "r", encoding="utf-8") as f:
                    tech_config = yaml.safe_load(f) or {}
                logger.info("V2 tech scoring config loaded from tech_scoring.yaml")

            self._v2_configs = {
                "base": base_config,
                "difficulty": diff_config,
                "tech": tech_config,
            }
        except Exception as e:
            logger.warning(f"Failed to load V2 scoring configs: {e}, using embedded defaults")
            self._v2_configs = self._default_v2_configs()

        return self._v2_configs

    def _default_v2_configs(self) -> Dict[str, Any]:
        """内置 V2 默认配置（当 YAML 文件不可用时）"""
        return {
            "base": {
                "dimensions": {
                    "accuracy": {"weight": 0.25},
                    "professional": {"weight": 0.20},
                    "completeness": {"weight": 0.20},
                    "reasoning": {"weight": 0.15},
                    "structure": {"weight": 0.10},
                    "actionable": {"weight": 0.10},
                },
                "scoring": {
                    "pass_threshold": 0.65,
                    "weak_threshold": 0.70,
                },
                "length_scoring": [
                    {"threshold": 50, "operator": "<", "adjustments": {"completeness": -0.25, "reasoning": -0.15}},
                    {"threshold": 150, "operator": "<", "adjustments": {"completeness": -0.10}},
                    {"threshold": 500, "operator": ">", "adjustments": {"completeness": 0.10, "structure": 0.05}},
                    {"threshold": 1000, "operator": ">", "adjustments": {"completeness": 0.15, "professional": 0.05}},
                ],
                "markdown_checks": [
                    {"pattern": "#{1,3}\\s", "bonus": {"structure": 0.15, "professional": 0.05}},
                    {"pattern": "\\*\\*|__", "bonus": {"structure": 0.05}},
                    {"pattern": "- |\\* |\\d+\\.", "bonus": {"structure": 0.10}},
                ],
            },
            "difficulty": {
                "complexity_keywords": [
                    {"keyword": kw, "weight": 0.03} for kw in
                    ["方案", "策划", "设计", "架构", "系统", "分析", "报告", "论文", "PPT", "预算", "风险评估", "技术选型", "多智能体", "端云协同",
                     "详细", "具体", "步骤", "时间安排", "花费", "食谱", "日程", "流程", "明细", "细化", "展开", "改进", "完善"]
                ],
                "content_length_boost": [
                    {"threshold": 2000, "operator": ">", "boost": 0.10},
                    {"threshold": 1000, "operator": ">", "boost": 0.05},
                ],
                "multi_question_boost": 0.08,
                "multi_paragraph_boost": 0.08,
                "weak_dimension_boost": [
                    {"weak_count": 1, "boost": 0.0},
                    {"weak_count": 2, "boost": 0.03},
                    {"weak_count": 3, "boost": 0.06},
                    {"weak_count": 4, "boost": 0.10},
                    {"weak_count": 5, "boost": 0.15},
                    {"weak_count": 6, "boost": 0.20},
                ],
            },
            "tech": {},
        }

    # ============================================================
    # Review Guard（V2.1 新增）— 保证永远输出合法 JSON
    # ============================================================

    @staticmethod
    def _repair_json(raw: str) -> Optional[dict]:
        """修复常见 JSON 格式问题

        处理场景：
        1. LLM 输出包裹在 markdown 代码块中
        2. JSON 前后有多余文本
        3. 尾部逗号
        4. 单引号替换为双引号
        5. 缺失闭合括号
        """
        if not raw or not raw.strip():
            return None

        raw = raw.strip()

        # 1. 提取 markdown 代码块中的 JSON
        code_block = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
        if code_block:
            raw = code_block.group(1).strip()

        # 2. 提取花括号包围的 JSON
        brace_match = re.search(r'\{[\s\S]*\}', raw)
        if brace_match:
            raw = brace_match.group(0)

        # 3. 修复尾部逗号
        raw = re.sub(r',\s*}', '}', raw)
        raw = re.sub(r',\s*]', ']', raw)

        # 4. 尝试补全缺失的闭合括号
        open_braces = raw.count('{') - raw.count('}')
        if open_braces > 0:
            raw += '}' * open_braces

        # 5. 尝试解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        return None

    def _review_guard(self, raw_llm_output: str, user_task: str, summary: str,
                      writer_output: str, skill_path: List[str],
                      domain_weights: Dict[str, float]) -> Dict[str, Any]:
        """Review Guard: 三层容错，保证永远返回合法的 ReviewReport JSON

        Layer 1: 直接 JSON 解析
        Layer 2: JSON 修复（_repair_json）
        Layer 3: 规则引擎回退（_review_content_v2）

        返回格式始终为 V2 ReviewReport 结构。
        """
        # Layer 1: 直接解析
        try:
            result = json.loads(raw_llm_output)
            if "review_score" in result and "dimensions" in result:
                # V2.1: 规范化评分到 0-1 范围
                result["review_score"] = self._normalize_score(result["review_score"])
                if result["review_score"] == 0.0:
                    logger.info("Review Guard: LLM returned score=0 (likely timeout), falling back to rules")
                    return self._review_content_v2(user_task, summary, writer_output, skill_path, domain_weights)
                if "difficulty_threshold" not in result:
                    result["difficulty_threshold"] = round(1.0 - result["review_score"], 2)
                result["difficulty_threshold"] = self._normalize_score(result["difficulty_threshold"])
                rules = self._load_rules()
                result["pass"] = result["review_score"] >= rules.get("pass_threshold", 0.65)
                return result
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Layer 2: JSON 修复
        repaired = self._repair_json(raw_llm_output)
        if repaired and "review_score" in repaired:
            # V2.1: 规范化评分到 0-1 范围
            repaired["review_score"] = self._normalize_score(repaired["review_score"])
            if repaired["review_score"] == 0.0:
                return self._review_content_v2(user_task, summary, writer_output, skill_path, domain_weights)
            if "difficulty_threshold" not in repaired:
                repaired["difficulty_threshold"] = round(1.0 - repaired["review_score"], 2)
            repaired["difficulty_threshold"] = self._normalize_score(repaired["difficulty_threshold"])
            rules = self._load_rules()
            repaired["pass"] = repaired["review_score"] >= rules.get("pass_threshold", 0.65)
            logger.info("Review Guard: JSON repaired successfully")
            return repaired

        # Layer 3: 规则引擎回退（最终兜底）
        logger.warning("Review Guard: LLM output irreparable, falling back to rule engine")
        return self._review_content_v2(user_task, summary, writer_output, skill_path, domain_weights)

    @staticmethod
    def _normalize_score(score: Any) -> float:
        """V2.1: 规范化评分到 0.0-1.0 范围

        处理 LLM 可能输出的非标准评分：
        - 0-10 分制（如 8.5 → 0.85）
        - 0-100 分制（如 85 → 0.85）
        - 负值
        - 非数值
        """
        try:
            value = float(score)
        except (ValueError, TypeError):
            return 0.5  # 默认中等评分

        # 0-100 分制检测
        if value > 10:
            value = value / 100.0
        # 0-10 分制检测
        elif value > 1.0:
            value = value / 10.0

        # 限幅到 0.0-1.0
        return max(0.0, min(1.0, round(value, 2)))

    def _safe_config_value(self, config: dict, key: str, default: Any) -> Any:
        """安全获取配置值，避免 NoneType 比较错误"""
        value = config.get(key)
        if value is None:
            return default
        return value

    # ============================================================
    # 执行入口
    # ============================================================

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        await self._set_status("processing")
        await self._set_current_task(f"质量评审: {input_data.content[:50]}...")

        try:
            input_data_dict = safe_json_parse(input_data.content)
            user_task = input_data_dict.get("user_task", "")
            summary = input_data_dict.get("summary", "")
            writer_output = input_data_dict.get("writer_output", "")
            skill_path = input_data_dict.get("skill_path", ["root", "daily"])

            # Skill Engine V2: 加载领域评分权重
            domain_weights = self._get_domain_weights(skill_path)

            if input_data.use_llm:
                # V2: LLM 评审也使用 V2 格式（向后兼容处理）
                review_result = await self._review_with_llm_v2(user_task, summary, writer_output,
                                                                skill_path, domain_weights, use_cloud=input_data.use_cloud)
            else:
                review_result = self._review_content_v2(user_task, summary, writer_output,
                                                         skill_path, domain_weights)

            await self._set_status("idle")
            await self._set_current_task(None)

            model_used = self.cloud_model if input_data.use_cloud else self.local_model

            return AgentOutput(
                content=json.dumps(review_result, ensure_ascii=False),
                success=True,
                message="质量评审与难度评估完成",
                metadata={
                    "review_score": review_result["overall"]["weighted_score"],
                    "difficulty_threshold": review_result["difficulty"]["threshold"],
                    "dimensions": review_result["dimensions"],
                    "risk_level": review_result["risk"]["level"],
                    "confidence": review_result["confidence"],
                    "pass": review_result["overall"]["pass"],
                    "model_used": model_used,
                    "skill_domain": skill_path[-1] if skill_path else "daily",
                },
                model_used=model_used
            )

        except Exception as e:
            await self._set_error(str(e))
            await self._set_status("error")
            return AgentOutput(content="", success=False, message=str(e))

    def _get_domain_weights(self, skill_path: List[str]) -> Dict[str, float]:
        """从 Skill Book 获取领域评分权重"""
        try:
            merged = self.skill_manager.load_skill_stack_merged(skill_path)
            if merged.scoring and merged.scoring.dimensions:
                return merged.scoring.dimensions
        except Exception:
            pass
        # 默认权重
        return {
            "accuracy": 0.25, "professional": 0.20, "completeness": 0.20,
            "reasoning": 0.15, "structure": 0.10, "actionable": 0.10
        }

    def _review_content_v2(self, user_task: str, summary: str, writer_output: str,
                             skill_path: List[str], domain_weights: Dict[str, float]) -> Dict[str, Any]:
        """Skill Engine V2: 委托 ReviewEngine 执行多维评审"""
        # 简单对话检测
        from agents.base.utils import _has_complexity_signal
        has_signal = _has_complexity_signal(user_task)
        is_simple = detect_simple_conversation(user_task, output_text=writer_output)
        logger.info(
            f"_review_content_v2 DEBUG: user_task_bytes={user_task[:80].encode('utf-8')}, "
            f"len={len(user_task)}, has_signal={has_signal}, "
            f"output_len={len(writer_output) if writer_output else 0}, "
            f"is_simple={is_simple}, skill_path={skill_path}"
        )
        if is_simple:
            return self._build_simple_report("简单对话，内容自然合理")

        # V2.1: 委托独立 ReviewEngine 执行评审（含缓存）
        result = self.review_engine.review(
            user_task=user_task,
            summary=summary,
            writer_output=writer_output,
            skill_path=skill_path,
            domain_weights=domain_weights,
        )
        logger.info(
            f"_review_content_v2 DEBUG: ReviewEngine returned "
            f"review_score={result.get('review_score')}, "
            f"difficulty={result.get('difficulty_threshold')}"
        )
        return result

    def _score_dimensions(self, user_task: str, writer_output: str,
                            rules: dict, weights: Dict[str, float]) -> Dict[str, Dict]:
        """对6个维度独立评分（从 YAML 配置驱动）

        评分策略：
        1. 基础分（从 YAML 配置或默认值）
        2. 内容长度调整（从 base_scoring.yaml length_scoring）
        3. Markdown 格式加分（从 base_scoring.yaml markdown_checks）
        4. 技术领域专项检查（从 tech_scoring.yaml tech_checks）
        """
        v2 = self._load_v2_configs()
        base = v2.get("base", {}) or {}
        tech = v2.get("tech", {}) or {}

        dims = {}
        output_len = len(writer_output) if writer_output else 0
        user_lower = user_task.lower() if user_task else ""
        output_lower = writer_output.lower() if writer_output else ""

        # 基础分（从 YAML 或默认值）— 所有值使用 safe_float 防护 None
        default_scores = base.get("default_scores", {}) or {}
        _DEFAULT_SCORES = {
            "accuracy": 0.75, "professional": 0.70, "completeness": 0.65,
            "reasoning": 0.80, "structure": 0.75, "actionable": 0.70,
        }

        dims["accuracy"] = {"score": safe_float(default_scores.get("accuracy"), _DEFAULT_SCORES["accuracy"]), "weight": safe_float(weights.get("accuracy"), 0.25), "issues": [], "suggestion": ""}
        dims["professional"] = {"score": safe_float(default_scores.get("professional"), _DEFAULT_SCORES["professional"]), "weight": safe_float(weights.get("professional"), 0.20), "issues": [], "suggestion": ""}
        dims["completeness"] = {"score": safe_float(default_scores.get("completeness"), _DEFAULT_SCORES["completeness"]), "weight": safe_float(weights.get("completeness"), 0.20), "issues": [], "suggestion": ""}
        dims["reasoning"] = {"score": safe_float(default_scores.get("reasoning"), _DEFAULT_SCORES["reasoning"]), "weight": safe_float(weights.get("reasoning"), 0.15), "issues": []}
        dims["structure"] = {"score": safe_float(default_scores.get("structure"), _DEFAULT_SCORES["structure"]), "weight": safe_float(weights.get("structure"), 0.10), "issues": []}
        dims["actionable"] = {"score": safe_float(default_scores.get("actionable"), _DEFAULT_SCORES["actionable"]), "weight": safe_float(weights.get("actionable"), 0.10), "issues": []}

        # 内容长度调整（从 YAML 配置）
        for rule in (base.get("length_scoring") or []):
            threshold = safe_float(rule.get("threshold"), 0)
            operator = rule.get("operator", ">")
            if operator == "<" and output_len < threshold:
                for dim, adj in (rule.get("adjustments") or {}).items():
                    if dim in dims:
                        dims[dim]["score"] += safe_float(adj, 0)
                break
            elif operator == ">" and output_len > threshold:
                for dim, adj in (rule.get("adjustments") or {}).items():
                    if dim in dims:
                        dims[dim]["score"] += safe_float(adj, 0)

        # Markdown 格式检查（从 YAML 配置）
        for check in (base.get("markdown_checks") or []):
            pattern = check.get("pattern", "")
            if pattern and re.search(pattern, writer_output, re.MULTILINE):
                for dim, bonus in (check.get("bonus") or {}).items():
                    if dim in dims:
                        dims[dim]["score"] += safe_float(bonus, 0)

        # 技术领域专项检查（从 tech_scoring.yaml）
        for check_name, check_cfg in (tech.get("tech_checks") or {}).items():
            if not isinstance(check_cfg, dict):
                continue
            pattern = check_cfg.get("pattern", "")
            if pattern and re.search(pattern, writer_output, re.MULTILINE):
                for dim, bonus in (check_cfg.get("bonus") or {}).items():
                    if dim in dims:
                        dims[dim]["score"] += safe_float(bonus, 0)

        # 逻辑性检测
        if any(kw in output_lower for kw in ["因为", "因此", "所以", "首先", "其次", "然后", "最后"]):
            dims["reasoning"]["score"] = safe_float(dims["reasoning"]["score"] + 0.05, dims["reasoning"]["score"])

        # 短内容结构性调整
        if output_len < 50:
            dims["structure"]["score"] = clamp_score(safe_float(dims["structure"]["score"] + 0.10, dims["structure"]["score"]))

        # 锁定所有分数在 0-1 范围
        for dim in dims:
            dims[dim]["score"] = clamp_score(safe_float(dims[dim]["score"], 0.5))

        return dims

    def _calculate_difficulty_v2(self, user_task: str, writer_output: str,
                                    weighted_score: float, dims: dict,
                                    skill_path: List[str]) -> Dict[str, Any]:
        """Skill Engine V2: 使用 YAML 难度矩阵计算难度

        从 difficulty_matrix.yaml 加载：
        - domain_base_difficulty: 领域基础难度
        - complexity_keywords: 复杂度关键词加权
        - content_length_boost: 内容长度加成
        - weak_dimension_boost: 弱维度数量加成

        V2.4 (2026-07-30): base_difficulty 与 weighted_score 解耦
          - 旧逻辑: base_difficulty = 1.0 - weighted_score
            问题: review_score 偏低 → base_difficulty 虚高 → 触发云端增强，
                  导致简单问题（如「ClusterIP vs NodePort」）因 Writer 回答简短就被误判为复杂任务。
                  且 difficulty 与 review_score 完全反相关，使 Judge 双门槛矩阵退化。
          - 新逻辑: base_difficulty = 领域基础难度（domain_base_difficulty）
            难度反映「任务本身的复杂度」，review_score 反映「回答质量」，
            两者作为独立信号供 Judge 双门槛矩阵使用。
        """
        v2 = self._load_v2_configs()
        diff_cfg = v2.get("difficulty", {}) or {}

        # V2.4: base_difficulty 改为领域基础难度（任务维度），不再用 1.0 - weighted_score
        domain = skill_path[-1] if skill_path else "daily"
        domain_diffs = diff_cfg.get("domain_base_difficulty", {}) or {}
        base_difficulty = safe_float(self._lookup_domain_difficulty(domain, domain_diffs), 0.20)
        complexity_boost = 0.0
        reason_parts = [f"{domain}领域({base_difficulty:.2f})"]
        user_lower = user_task.lower() if user_task else ""

        # 复杂度关键词加权（从 YAML 配置）
        for item in (diff_cfg.get("complexity_keywords") or []):
            if not isinstance(item, dict):
                continue
            if (item.get("keyword") or "") in user_lower:
                complexity_boost += safe_float(item.get("weight"), 0.03)

        # 内容长度反映复杂度（从 YAML 配置）
        output_len = len(writer_output) if writer_output else 0
        for rule in (diff_cfg.get("content_length_boost") or []):
            if not isinstance(rule, dict):
                continue
            if rule.get("operator") == ">" and output_len > safe_float(rule.get("threshold"), 0):
                complexity_boost += safe_float(rule.get("boost"), 0)

        # 多问题/多段落
        if user_task and (user_task.count("?") + user_task.count("？") >= 2):
            complexity_boost += safe_float(diff_cfg.get("multi_question_boost"), 0.08)
            reason_parts.append("多问题")
        if user_task and "\n" in user_task and len(user_task.split("\n")) >= 3:
            complexity_boost += safe_float(diff_cfg.get("multi_paragraph_boost"), 0.08)

        # 弱维度数量加成（从 YAML 配置）
        # V2.4 (2026-07-30): 弱阈值跟随 base_scoring.yaml 的 weak_threshold（0.60），
        #   不再硬编码 0.70。这样只有真正低于阈值的维度才被判弱，避免误判放大难度。
        #   注意: 解耦后弱维度加成是难度对「回答质量」的唯一反馈通道，
        #         保留但已削弱（见 difficulty_matrix.yaml V2.4 调整）。
        base_cfg = v2.get("base", {}) or {}
        base_scoring = base_cfg.get("scoring", {}) or {}
        weak_threshold = safe_float(base_scoring.get("weak_threshold"), 0.60)
        weak_count = sum(1 for d in (dims or {}).values() if isinstance(d, dict) and safe_float(d.get("score"), 1.0) < weak_threshold)
        for rule in (diff_cfg.get("weak_dimension_boost") or []):
            if not isinstance(rule, dict):
                continue
            if rule.get("weak_count") == weak_count:
                complexity_boost += safe_float(rule.get("boost"), 0)
                if weak_count >= 2:
                    reason_parts.append(f"{weak_count}个弱维度")

        difficulty = base_difficulty + complexity_boost
        difficulty = max(0.0, min(1.0, difficulty))

        # 难度等级
        if difficulty < 0.35:
            level = "simple"
        elif difficulty < 0.65:
            level = "medium"
        elif difficulty < 0.80:
            level = "complex"
        else:
            level = "expert"

        return {
            "threshold": round(difficulty, 2),
            "level": level,
            "reason": " | ".join(reason_parts) if reason_parts else f"{domain}领域({base_difficulty:.2f})"
        }

    @staticmethod
    def _lookup_domain_difficulty(domain: str, domain_diffs: dict) -> float:
        """在领域难度字典中查找指定领域的难度加成

        支持嵌套字典结构的层级查找：
        tech.crypto.quantum → tech.crypto → tech → root
        例如 YAML: {tech: {crypto: {quantum: 0.75}}}
        """
        # 精确匹配
        if domain in domain_diffs:
            val = domain_diffs[domain]
            if isinstance(val, dict):
                return float(val.get("base", 0.0))
            return float(val)

        # 按点号分割，逐级深入嵌套字典
        parts = domain.split(".")
        current = domain_diffs
        for i, part in enumerate(parts):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # 当前层级找不到，返回之前找到的基准值
                return 0.0

        # 遍历完所有部分，返回最终值
        if isinstance(current, dict):
            return float(current.get("base", 0.0))
        return float(current)

    def _assess_risk_level(self, dims: dict, weighted_score: float) -> Dict[str, Any]:
        """评估风险等级"""
        if weighted_score < 0.4:
            level = "critical"
        elif weighted_score < 0.55:
            level = "high"
        elif weighted_score < 0.70:
            level = "medium"
        else:
            level = "low"

        factors = []
        if dims.get("accuracy", {}).get("score", 0) < 0.6:
            factors.append("准确性不足")
        if dims.get("completeness", {}).get("score", 0) < 0.5:
            factors.append("完整性严重不足")

        return {
            "level": level,
            "factors": factors,
            "mitigation": "云端增强" if level in ("critical", "high") else "本地处理"
        }

    def _calculate_confidence(self, dims: dict) -> float:
        """计算评审置信度"""
        scores = [d["score"] for d in dims.values()]
        if not scores:
            return 0.7
        # 分数离散度低 → 置信度高
        avg = sum(scores) / len(scores)
        variance = sum((s - avg) ** 2 for s in scores) / len(scores)
        return round(max(0.5, min(1.0, 1.0 - variance)), 2)

    def _collect_issues(self, dims: dict) -> List[str]:
        issues = []
        for name, dim in dims.items():
            if dim["score"] < 0.6:
                issues.append(f"{name}评分偏低({dim['score']:.2f})")
        return issues

    def _collect_suggestions(self, dims: dict) -> List[str]:
        suggestions = []
        if dims.get("completeness", {}).get("score", 0) < 0.6:
            suggestions.append("补充缺失的关键内容章节")
        if dims.get("professional", {}).get("score", 0) < 0.6:
            suggestions.append("提升专业术语准确性和一致性")
        if dims.get("accuracy", {}).get("score", 0) < 0.6:
            suggestions.append("修正事实性错误")
        if not suggestions:
            suggestions.append("内容质量良好，建议检查是否有遗漏细节")
        return suggestions

    def _build_simple_report(self, suggestion: str) -> Dict[str, Any]:
        """构建简单对话的评审报告"""
        return {
            "dimensions": {
                "accuracy": {"score": 0.85, "weight": 0.25, "issues": [], "suggestion": ""},
                "professional": {"score": 0.85, "weight": 0.20, "issues": [], "suggestion": ""},
                "completeness": {"score": 0.85, "weight": 0.20, "issues": [], "suggestion": ""},
                "reasoning": {"score": 0.85, "weight": 0.15, "issues": []},
                "structure": {"score": 0.85, "weight": 0.10, "issues": []},
                "actionable": {"score": 0.85, "weight": 0.10, "issues": []},
            },
            "overall": {"weighted_score": 0.85, "pass": True},
            "risk": {"level": "low", "factors": [], "mitigation": ""},
            "confidence": 0.95,
            "difficulty": {"threshold": 0.15, "level": "simple", "reason": "简单对话"},
            "review_score": 0.85, "difficulty_threshold": 0.15,
            "issues": [], "suggestions": [suggestion], "pass": True
        }

    def _review_content(self, user_task: str, summary: str, writer_output: str) -> Dict[str, Any]:
        rules = self._load_rules()

        if detect_simple_conversation(user_task, output_text=writer_output):
            sc = rules["simple_conversation"]
            return {
                "review_score": sc["review_score"],
                "difficulty_threshold": sc["difficulty_threshold"],
                "dimensions": sc["dimensions"],
                "issues": [],
                "suggestions": ["简单对话，内容自然合理"],
                "pass": True
            }

        dims = rules["dimensions"]
        structure = dims["structure"]
        relevance = dims["relevance"]
        richness = dims["richness"]
        professional = dims["professional"]
        actionable = dims["actionable"]

        issues = []
        suggestions = []

        # 内容长度评估（来自 YAML 配置）
        output_len = len(writer_output)
        if "length_scoring" in rules:
            for rule in rules["length_scoring"]:
                t = rule["threshold"]
                op = rule["operator"]
                if op == "<" and output_len < t:
                    richness += rule.get("richness_delta", 0)
                    if "issues" in rule:
                        issues.extend(rule["issues"])
                    break
                elif op == ">" and output_len > t:
                    richness += rule.get("richness_delta", 0)
                    break

        # 结构检查（来自 YAML 配置）
        if "structure_checks" in rules:
            for check in rules["structure_checks"]:
                target_tasks = check.get("target_tasks", [])
                if not any(tt in user_task for tt in target_tasks):
                    continue
                keywords = check.get("keywords", [])
                if not any(kw in writer_output for kw in keywords):
                    issues.extend(check.get("missing_issues", []))
                    structure += check.get("structure_penalty", 0)
                    actionable += check.get("actionable_penalty", 0)

        # Markdown 格式检查（来自 YAML 配置）
        if "markdown_scoring" in rules:
            for rule in rules["markdown_scoring"]:
                if re.search(rule["pattern"], writer_output):
                    structure += rule.get("structure_bonus", 0)

        # 关键词匹配检查（来自 YAML 配置）
        if "keyword_matching" in rules:
            km = rules["keyword_matching"]
            task_lower = user_task.lower()
            output_lower = writer_output.lower()
            task_keywords = km.get("task_keywords", [])
            matched = sum(1 for kw in task_keywords if kw in task_lower and kw in output_lower)
            if matched >= km.get("min_match_count", 2):
                relevance += km.get("relevance_bonus", 0.2)

        # 内容质量加分（来自 YAML 配置）
        if "quality_bonuses" in rules:
            for bonus in rules["quality_bonuses"]:
                if re.search(bonus["pattern"], writer_output):
                    structure += bonus.get("structure_bonus", 0)
                    professional += bonus.get("professional_bonus", 0)
                    actionable += bonus.get("actionable_bonus", 0)

        # 限制范围
        structure = clamp_score(structure)
        relevance = clamp_score(relevance)
        richness = clamp_score(richness)
        professional = clamp_score(professional)
        actionable = clamp_score(actionable)

        review_score = (structure + relevance + richness + professional + actionable) / 5

        # 计算 difficulty_threshold
        difficulty_threshold = self._calculate_difficulty_threshold(
            user_task, writer_output, review_score, structure, professional
        )

        # 生成建议
        for issue in issues:
            if "内容过短" in issue:
                suggestions.append("增加内容详细度")
            elif "活动流程" in issue:
                suggestions.append("补充活动流程章节")
            elif "预算" in issue:
                suggestions.append("增加预算模块")
            elif "时间" in issue:
                suggestions.append("添加时间线")
        if not suggestions:
            suggestions.append("内容质量良好，建议检查是否有遗漏细节")

        pass_threshold = rules.get("pass_threshold", 0.65)

        return {
            "review_score": round(review_score, 2),
            "difficulty_threshold": round(difficulty_threshold, 2),
            "dimensions": {
                "structure": round(structure, 2),
                "relevance": round(relevance, 2),
                "richness": round(richness, 2),
                "professional": round(professional, 2),
                "actionable": round(actionable, 2)
            },
            "issues": issues,
            "suggestions": suggestions,
            "pass": review_score >= pass_threshold
        }

    def _calculate_difficulty_threshold(self, user_task: str, writer_output: str,
                                          review_score: float, structure: float,
                                          professional: float) -> float:
        """基于配置规则计算难度阈值

        V2.4 (2026-07-30): base_difficulty 与 review_score 解耦
          - 旧逻辑: base_difficulty = 1.0 - review_score
            问题: review_score 偏低直接推高 base_difficulty，简单问题因回答简短被误判为复杂。
                  且该值作为 V2.3 融合的 rule_difficulty，与 llm_difficulty 融合后仍受 review_score 支配。
          - 新逻辑: base_difficulty = 固定基线 0.20（简单任务默认值）
            难度仅由任务信号（关键词/长度/多问题/结构不足）叠加决定。
            review_score 仅作为 Judge 双门槛矩阵的独立信号，不直接注入难度。
        """
        rules = self._load_rules()
        dt_cfg = rules.get("difficulty_threshold", {})

        # V2.4: 固定基线，不再用 1.0 - review_score
        base_difficulty = 0.20
        task_lower = user_task.lower()
        complexity_boost = 0.0

        # 复杂关键词加分（来自 YAML）
        for item in dt_cfg.get("complex_keywords", []):
            if item["keyword"] in task_lower:
                complexity_boost += item.get("weight", 0.03)

        # 内容长度反映复杂度
        output_len = len(writer_output)
        for rule in dt_cfg.get("content_length_boost", []):
            if rule["operator"] == ">" and output_len > rule["threshold"]:
                complexity_boost += rule.get("boost", 0)

        # 多问题/多段落
        if user_task.count("?") + user_task.count("？") >= 2:
            complexity_boost += dt_cfg.get("multi_question_boost", 0.08)
        if "\n" in user_task and len(user_task.split("\n")) >= 3:
            complexity_boost += dt_cfg.get("multi_paragraph_boost", 0.08)

        # 结构/专业性不足
        low_threshold = dt_cfg.get("low_threshold", 0.5)
        if structure < low_threshold:
            complexity_boost += dt_cfg.get("low_structure_penalty", 0.05)
        if professional < low_threshold:
            complexity_boost += dt_cfg.get("low_professional_penalty", 0.05)

        # V2.4 (2026-07-30): 移除 review_score < 0.65 时 +0.05 的反馈环
        #   原因: 该规则与「弱维度数量加成」叠加后形成恶性循环——
        #         review_score 偏低 → +0.05 → 难度上升 → 弱维度增多 → 再加成 → 触发云端增强。
        #         对简单问题（如「Kubernetes ClusterIP vs NodePort」）造成误判。
        #         难度评估应基于任务本身，而非 LLM 输出质量的双层反向加成。

        difficulty = base_difficulty + complexity_boost
        return round(max(0.0, min(1.0, difficulty)), 2)

    async def _review_with_llm_v2(self, user_task: str, summary: str, writer_output: str,
                                 skill_path: List[str], domain_weights: Dict[str, float],
                                 use_cloud: bool = False) -> Dict[str, Any]:
        """Skill Engine V2: LLM 评审 + V2 格式转换（使用 Review Guard）

        V2.3 新增：LLM 评审后用规则引擎重新校正 difficulty_threshold
        解决 LLM 评审路径"向 0.65 收敛"的问题，确保难度阈值反映任务真实复杂度
        """
        # V2.1: 传递 skill_path 和 domain_weights 给 Review Guard
        old_result = await self._review_with_llm(user_task, summary, writer_output,
                                                   skill_path, domain_weights, use_cloud)

        # 检测是否为规则引擎回退结果
        dims = old_result.get("dimensions", {})
        if dims and len(dims) >= 5 and "review_score" in old_result:
            review_score = self._normalize_score(old_result.get("review_score", 0.7))
            # 如果旧结果来自简单对话检测，用V2规则引擎重新评估
            if review_score >= 0.80 and self._normalize_score(old_result.get("difficulty_threshold", 0.5)) <= 0.20:
                logger.info("LLM review fell back to simple conversation, retrying with V2 rule engine")
                return self._review_content_v2(user_task, summary, writer_output, skill_path, domain_weights)

            # 将旧维度映射到 V2 6维
            v2_dims = {
                "accuracy": {"score": safe_float(dims.get("relevance", dims.get("richness", 0.75)), 0.75), "weight": safe_float(domain_weights.get("accuracy"), 0.25), "issues": [], "suggestion": ""},
                "professional": {"score": safe_float(dims.get("professional"), 0.70), "weight": safe_float(domain_weights.get("professional"), 0.20), "issues": [], "suggestion": ""},
                "completeness": {"score": safe_float(dims.get("richness", dims.get("structure", 0.65)), 0.65), "weight": safe_float(domain_weights.get("completeness"), 0.20), "issues": [], "suggestion": ""},
                "reasoning": {"score": 0.80, "weight": safe_float(domain_weights.get("reasoning"), 0.15), "issues": []},
                "structure": {"score": safe_float(dims.get("structure"), 0.75), "weight": safe_float(domain_weights.get("structure"), 0.10), "issues": []},
                "actionable": {"score": safe_float(dims.get("actionable"), 0.70), "weight": safe_float(domain_weights.get("actionable"), 0.10), "issues": []},
            }
            weighted_score = review_score

            # V2.3 难度校正：LLM 评审路径"向 0.65 收敛"问题
            # 用规则引擎基于 user_task 和 writer_output 重新计算 difficulty_threshold
            llm_difficulty = safe_float(old_result.get("difficulty_threshold"), 0.5)
            structure_score = safe_float(dims.get("structure"), 0.75)
            professional_score = safe_float(dims.get("professional"), 0.70)
            rule_difficulty = self._calculate_difficulty_threshold(
                user_task, writer_output, weighted_score, structure_score, professional_score
            )

            # V2.3 智能融合策略：
            # - 强复杂度信号词 >= 2 → 取 max（高难度问题需升级到 full_rewrite 区间）
            # - Review 评分 < 0.65 → 偏重规则引擎的加权平均（规则 0.6 + LLM 0.4）
            #   原因：LLM 评审倾向向 0.65 收敛，会把中等问题误判为复杂；
            #         规则引擎基于关键词计算更稳定，应主导校正
            # - 其他中低复杂度（评分 >= 0.65）→ 偏重 LLM 的加权平均（LLM 0.6 + 规则 0.4）
            from agents.base.utils import _has_complexity_signal, _COMPLEXITY_SIGNALS
            signal_count = sum(1 for s in _COMPLEXITY_SIGNALS if s in user_task)

            original_llm_difficulty = llm_difficulty
            if signal_count >= 2:
                # 高难度问题：取 max，确保进入 full_rewrite 区间
                difficulty = max(llm_difficulty, rule_difficulty)
                strategy = "max(高复杂度)"
            elif weighted_score < 0.65:
                # V2.3: Review 评分未过门槛 → 偏重规则引擎（规则 0.6 + LLM 0.4）
                # 解决 LLM 向 0.65 收敛把中等问题误判为复杂的问题
                difficulty = round(rule_difficulty * 0.6 + llm_difficulty * 0.4, 2)
                strategy = "weighted_rule(Review未过门槛)"
            else:
                # 中等/简单问题且评分较高：偏重 LLM（LLM 0.6 + 规则 0.4）
                difficulty = round(llm_difficulty * 0.6 + rule_difficulty * 0.4, 2)
                strategy = "weighted_llm(中低复杂度)"

            logger.info(
                f"V2.3 难度校正: LLM={original_llm_difficulty:.2f} + 规则引擎={rule_difficulty:.2f} → "
                f"最终={difficulty:.2f} (策略={strategy}, 信号词={signal_count}, "
                f"review_score={weighted_score:.2f}, user_task='{user_task[:40]}...')"
            )
        else:
            # LLM 评审完全失败，回退到 V2 规则引擎
            return self._review_content_v2(user_task, summary, writer_output, skill_path, domain_weights)

        return {
            "dimensions": v2_dims,
            "overall": {
                "weighted_score": round(weighted_score, 2),
                "pass": weighted_score >= 0.65
            },
            "risk": {"level": "low", "factors": [], "mitigation": ""},
            "confidence": 0.85,
            "difficulty": {"threshold": round(difficulty, 2), "level": "medium", "reason": ""},
            "review_score": round(weighted_score, 2),
            "difficulty_threshold": round(difficulty, 2),
            "issues": old_result.get("issues", []),
            "suggestions": old_result.get("suggestions", []),
            "pass": weighted_score >= 0.65
        }

    async def _review_with_llm(self, user_task: str, summary: str, writer_output: str,
                                 skill_path: List[str] = None, domain_weights: Dict[str, float] = None,
                                 use_cloud: bool = False) -> Dict[str, Any]:
        if skill_path is None:
            skill_path = ["root", "daily"]
        if domain_weights is None:
            domain_weights = {}
        if detect_simple_conversation(user_task, output_text=writer_output):
            return self._review_content_v2(user_task, summary, writer_output, skill_path, domain_weights)

        prompt = f"""你是 Review Agent，负责评审内容质量和评估难度阈值。

## 评审维度（每项 0-1 分）
1. structure（结构完整性）2. relevance（需求相关性）3. richness（内容丰富度）
4. professional（专业性）5. actionable（可执行性）

## difficulty_threshold 评估标准
- 0.0-0.35：简单任务 → 建议本地模型
- 0.35-0.65：中等任务 → 可在本地处理
- 0.65-0.80：复杂任务 → 建议云端增强
- 0.80-1.0：高难度任务 → 强烈建议云端模型

## 评分规则
- review_score = 五项维度平均值
- difficulty_threshold 基于 review_score 和任务复杂度综合计算
- review_score >= 0.8 时 difficulty_threshold 应偏低
- 任务越复杂、内容越不完整，difficulty_threshold 应越高

用户任务：{user_task}
需求摘要：{summary}
Writer输出：{writer_output[:2000]}

输出严格 JSON：
{{
  "review_score": 0.0,
  "difficulty_threshold": 0.0,
  "dimensions": {{"structure": 0.0, "relevance": 0.0, "richness": 0.0, "professional": 0.0, "actionable": 0.0}},
  "issues": [""],
  "suggestions": [""],
  "pass": true
}}"""

        try:
            response = await asyncio.wait_for(
                self._call_llm(prompt, model=self.local_model, use_cloud=use_cloud,
                               temperature=0.2, system_prompt=self._load_system_prompt()),
                timeout=30
            )
        except asyncio.TimeoutError:
            logger.warning(f"Review LLM 调用超时(30s)，回退到 V2 规则引擎评分")
            return self._review_content_v2(user_task, summary, writer_output, skill_path, domain_weights)

        # V2.1: 使用 Review Guard 替代直接 JSON 解析，传递实际领域参数
        return self._review_guard(response, user_task, summary, writer_output,
                                   skill_path, domain_weights)