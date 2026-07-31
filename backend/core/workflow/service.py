"""工作流服务 - 更新版：5 Agent 流水线（knowledge → writer → review → judge → result）

Skill Engine V2 集成:
- IntentCache: 两层缓存（L1技能路径/L2完整结果），跳过重复计算
- SkillLearner: Review 反馈收集，自动生成 Skill Patch

WebSocket 推送（规则五）:
- 每个 Agent 执行后推送 workflow_step 消息
- 最终结果推送 final_result 消息
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from agents.base.agent import AgentInput, AgentOutput
from agents.base.agent_registry import AgentRegistry
from agents.base.utils import safe_json_parse
from models.workflow import WorkflowInput, WorkflowOutput, WorkflowStep, TaskStep
from core.dynamic_router import get_dynamic_router
from api.v1.metrics.router import get_metrics_store
import asyncio
import time
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def _get_ws_manager():
    """获取全局 WebSocketManager（懒加载，避免循环导入）"""
    try:
        from app.main import app
        return getattr(app.state, 'ws_manager', None)
    except Exception:
        return None


class WorkflowService:
    def __init__(self, agent_registry: AgentRegistry):
        self.agent_registry = agent_registry
        self.dynamic_router = get_dynamic_router()
        self.agent_order = ["knowledge", "writer", "review", "judge", "result"]

        # V3: Cognitive Controller 接入
        try:
            from core.engines.cognitive_controller import CognitiveController
            self.controller = CognitiveController()
        except ImportError:
            self.controller = None

        # V3: Personal Brain 接入
        try:
            from core.personal_brain.brain import PersonalBrain
            self.brain = PersonalBrain(user_id="default")
        except ImportError:
            self.brain = None

        # V3: Intent Graph 接入 — 记录用户会话意图时间线
        try:
            from core.graphs.intent_graph import IntentGraph
            self.intent_graph = IntentGraph(user_id="default")
        except ImportError:
            self.intent_graph = None

        # V3: MemoryStore 接入 — 长期记忆上下文注入
        try:
            from core.memory_store.store import get_memory_store
            self.memory_store = get_memory_store(user_id="default")
        except ImportError:
            self.memory_store = None

        # V3: MemoryExtractor 接入 — 对话结束后自动提取记忆
        try:
            from core.memory_store.extractor import get_memory_extractor
            from core.llm.client import LLMClient
            llm_client = LLMClient()
            self.memory_extractor = get_memory_extractor(
                llm_client=llm_client,
                memory_store=self.memory_store,
            )
        except ImportError:
            self.memory_extractor = None

        # V3: Learning Engine 接入
        self.learning_engine = None
        try:
            from core.graphs import get_skill_graph
            from core.graphs.reasoning_graph import ReasoningGraph
            from core.engines.learning_engine import LearningEngine
            self.learning_engine = LearningEngine(
                skill_graph=get_skill_graph(),
                reasoning_graph=ReasoningGraph(),
                validator=None  # PatchValidator 自动创建
            )
        except ImportError as e:
            logger.debug(f"LearningEngine not available: {e}")

        # V3: Knowledge Recommendation 接入 — 基于 Graph Traversal 的精准推荐
        # 推荐来源: 当前任务/Goal/Capability/Skill Graph 四类 + 提示词模板
        # 介入条件: IntentGraph 检测到连续3次同领域提问（should_intervene=True）
        self.knowledge_recommender = None
        try:
            from core.graphs import get_skill_graph
            from core.engines.knowledge_recommendation import KnowledgeRecommendation
            self.knowledge_recommender = KnowledgeRecommendation(
                get_skill_graph(), brain=self.brain
            )
        except ImportError as e:
            logger.debug(f"KnowledgeRecommendation not available: {e}")
        self.agent_names = {
            "knowledge": "Knowledge Agent",
            "writer": "Writer Agent",
            "review": "Review Agent",
            "judge": "Judge Agent",
            "result": "Result Agent"
        }

    async def execute(self, input_data: WorkflowInput) -> WorkflowOutput:
        steps: List[WorkflowStep] = []
        current_context = input_data.context or {}
        executed_locally = True
        difficulty_threshold = 0.0
        review_score = 0.0
        decision = None  # V3: Cognitive Controller decision
        judge_decision = "local_output"
        cloud_mode = "none"
        knowledge_found = False
        start_time = time.time()
        workflow_start = datetime.now()
        error_summary: List[str] = []
        partial_success = False

        metrics = get_metrics_store()
        metrics["total_requests"] += 1

        # V3.3: 记录用户活动（供 AuditScheduler 判断空闲触发）
        try:
            from core.engines.audit_scheduler import get_audit_scheduler
            get_audit_scheduler().record_user_activity()
        except Exception:
            pass  # 调度器未初始化时忽略

        current_input = input_data.user_input
        original_user_input = input_data.user_input
        writer_output = ""
        knowledge_result = ""
        review_result = ""
        skill_path = ["root", "daily"]  # Skill Engine V2: 默认路径
        cache_hit = False

        # ============================================================
        # V3.4 (2026-07-30): 用户指责/抱怨检测
        # ------------------------------------------------------------
        # 检测到抱怨时：
        # 1. 跳过所有缓存（强制重新生成，避免返回历史错误答案）
        # 2. 在 context 标记 complaint_type，供 Writer Agent 注入道歉指令
        # 3. 让系统先道歉，再根据上下文重新认真思考后重新回答
        # ============================================================
        is_complaint = False  # 默认值，确保后续 skip_l2_cache 判断稳定
        # V3.4 BUGFIX: 如果是澄清后的重答（前端传入 is_clarification=True），
        # 跳过抱怨检测，直接使用前端传入的 complaint_type（保留道歉指令注入）
        is_clarification = bool(current_context.get("is_clarification", False))
        try:
            if is_clarification and current_context.get("complaint_type"):
                # 澄清后的重答：不触发澄清弹窗，但保留complaint_type供Writer注入道歉
                complaint_type = current_context.get("complaint_type")
                logger.info(
                    f"[ComplaintDetection] 澄清后重答: 复用 complaint_type={complaint_type}, "
                    f"跳过抱怨检测（避免重复触发弹窗）"
                )
                is_complaint = False  # 不再触发澄清弹窗
            else:
                from agents.knowledge.complaint_keywords import detect_complaint
                is_complaint, complaint_type, matched_kw = detect_complaint(original_user_input)
                if is_complaint:
                    logger.info(
                        f"[ComplaintDetection] 检测到用户抱怨: type={complaint_type}, "
                        f"keyword='{matched_kw}', 将跳过缓存并触发道歉重答流程"
                    )
                    current_context["complaint_type"] = complaint_type
                    current_context["complaint_matched_keyword"] = matched_kw
                    metrics["complaint_detected"] = metrics.get("complaint_detected", 0) + 1

                    # ============================================================
                    # V3.4 (2026-07-30): 推送抱怨澄清请求到前端
                    # ------------------------------------------------------------
                    # 检测到抱怨后，生成2-5个澄清问题推送到前端弹窗
                    # 让用户选择系统理解的方向或自行输入，帮助系统快速定位问题
                    # 用户在前端选择/输入后，会将结果作为新的 user_input 重新提交
                    # ============================================================
                    try:
                        from agents.knowledge.clarify_generator import generate_clarify_questions
                        # 提取对话历史（如有）
                        conv_history = ""
                        if current_context.get("history"):
                            try:
                                history_list = current_context["history"]
                                if isinstance(history_list, list):
                                    conv_history = "\n".join(
                                        f"{h.get('role','user')}: {h.get('content','')}"
                                        for h in history_list[-4:]  # 最近4轮
                                    )
                            except Exception:
                                pass

                        clarify_data = generate_clarify_questions(
                            complaint_type=complaint_type,
                            user_input=original_user_input,
                            conversation_history=conv_history,
                        )

                        # 通过 WebSocket 推送到前端
                        ws_mgr = _get_ws_manager()
                        if ws_mgr:
                            import asyncio as _asyncio
                            # 在事件循环中异步推送
                            try:
                                loop = _asyncio.get_running_loop()
                                _asyncio.create_task(
                                    ws_mgr.broadcast_clarify_request(clarify_data)
                                )
                                logger.info(
                                    f"[ClarifyRequest] 已推送澄清请求到前端: "
                                    f"{len(clarify_data['questions'])} 个问题，workflow暂停等待用户澄清"
                                )
                            except RuntimeError:
                                logger.warning("[ClarifyRequest] 无可用事件循环，跳过推送")

                        # ============================================================
                        # BUGFIX (2026-07-31): 暂停workflow，等待用户澄清
                        # ------------------------------------------------------------
                        # 原问题: 推送clarify_request后workflow继续执行，导致弹窗
                        #         还没选择完系统就输出答案了
                        # 修复: 检测到抱怨并推送澄清请求后，立即返回占位响应
                        #       不执行后续agent流程。用户在弹窗选择后会重新
                        #       调用executeWorkflow，那时才真正执行
                        # ============================================================
                        pending_step = WorkflowStep(
                            agent_id="knowledge",
                            agent_name="Knowledge Agent",
                            input=original_user_input,
                            output="检测到用户抱怨，已推送澄清请求，等待用户确认真实需求...",
                            success=True,
                            duration_seconds=0.1,
                            timestamp=datetime.now().isoformat(),
                            metadata={"complaint_detected": True, "clarify_pushed": True},
                        )
                        return WorkflowOutput(
                            final_result="我注意到您对之前的回答有意见，为了更准确地帮助您，请先在弹窗中确认您的真实需求，我会根据您的选择重新认真回答。",
                            steps=[pending_step],
                            executed_locally=True,
                            total_duration_seconds=0.1,
                            start_time=workflow_start,
                            end_time=datetime.now(),
                            complexity_score=0.0,
                            partial_success=False,
                            error_summary=None,
                        )
                    except ImportError:
                        logger.warning("clarify_generator 模块未加载，跳过澄清请求推送")
                    except Exception as e:
                        logger.warning(f"推送澄清请求失败: {e}")
        except ImportError:
            logger.debug("complaint_keywords 模块未加载，跳过抱怨检测")
        except Exception as e:
            logger.warning(f"抱怨检测异常，继续正常流程: {e}")

        # Skill Engine V2: 意图缓存检查
        # 有对话历史时跳过 L2 缓存（上下文不同，结果应不同）
        # V3.4: 检测到抱怨时也跳过 L2 缓存（必须重新生成，不能返回历史错误答案）
        has_history = bool(current_context and current_context.get("history"))
        skip_l2_cache = has_history or is_complaint
        try:
            from core.skill_engine.intent_cache import get_intent_cache
            intent_cache = get_intent_cache()

            # L2: 完整结果缓存（无对话历史且非抱怨时才查）
            if not skip_l2_cache:
                cached_result = intent_cache.lookup_result(original_user_input)
                if cached_result:
                    logger.info(f"IntentCache L2 HIT: 直接返回缓存结果")
                    metrics["cache_hits"] = metrics.get("cache_hits", 0) + 1
                    return WorkflowOutput(**cached_result)

            # L1: 技能路径缓存
            cached_path = intent_cache.lookup_skill_path(original_user_input)
            if cached_path:
                skill_path = cached_path
                cache_hit = True
                logger.info(f"IntentCache L1 HIT: skill_path={cached_path}")
        except ImportError:
            pass  # 缓存模块未就绪，继续正常流程
        except Exception as e:
            logger.warning(f"IntentCache 查询失败，继续正常流程: {e}")

        # 用于暴露给前端 UI 的提示词模板列表（由 KnowledgeRecommendation 填充）
        # 在外层初始化，确保即使 controller 未启用也能引用
        prompt_templates_for_ui = []

        # V3: Cognitive Controller 决策
        if self.controller:
            try:
                from core.skill_engine.task_engine import TaskClassifier
                classifier = TaskClassifier()
                task_profile = classifier.classify(original_user_input)
                decision = self.controller.decide(task_profile, brain=self.brain)
                logger.info(
                    f"Controller decision: task_type={decision.task_type}, "
                    f"engines={decision.engines}, "
                    f"complexity={decision.complexity:.2f}, "
                    f"latency={self.controller.get_expected_latency(decision)}, "
                    f"reason={decision.reason}"
                )

                # V3: Decomposer — 问题分解
                if "decomposer" in decision.engines:
                    try:
                        from core.graphs import get_skill_graph
                        from core.engines.decomposer import Decomposer
                        decomposer = Decomposer(get_skill_graph())
                        decomposer_result = decomposer.decompose(original_user_input)
                        if decomposer_result and decomposer_result.get("matched_nodes"):
                            current_context["decomposer_result"] = decomposer_result
                            logger.info(
                                f"Decomposer: topic={decomposer_result['topic']}, "
                                f"matched={len(decomposer_result['matched_nodes'])}, "
                                f"sub_topics={len(decomposer_result['sub_topics'])}"
                            )
                    except Exception as e:
                        logger.warning(f"Decomposer failed: {e}")

                # V3: LocalPlanner — 任务规划
                if "planner" in decision.engines:
                    try:
                        from core.graphs import get_skill_graph
                        from core.engines.local_planner import LocalPlanner
                        planner = LocalPlanner(get_skill_graph())
                        decomposer_result = current_context.get("decomposer_result", {})
                        plan_steps = planner.plan(decomposer_result)
                        if plan_steps:
                            current_context["plan_steps"] = plan_steps
                            current_context["skill_gaps"] = planner.detect_skill_gap(plan_steps)
                            logger.info(
                                f"Planner: steps={len(plan_steps)}, "
                                f"gaps={len(current_context.get('skill_gaps', []))}"
                            )
                    except Exception as e:
                        logger.warning(f"Planner failed: {e}")

                # V3: Reasoning Graph — 推理模式匹配
                if decision.use_reasoning:
                    try:
                        from core.graphs.reasoning_graph import ReasoningGraph
                        reasoning_graph = ReasoningGraph()
                        task_type = decision.task_type
                        domain = getattr(task_profile, 'domain', '')
                        keywords = getattr(task_profile, 'keywords', [])
                        pattern = reasoning_graph.match(task_type, domain, keywords)
                        if pattern:
                            current_context["reasoning_pattern"] = pattern
                            logger.info(
                                f"Reasoning pattern matched: {pattern.pattern_name} "
                                f"(id={pattern.pattern_id}, steps={len(pattern.steps)})"
                            )
                    except Exception as e:
                        logger.warning(f"Reasoning graph matching failed: {e}")

                # V3: Knowledge Recommendation — 提示词模板推荐
                # 策略: 首次命中即推荐（active_nodes 非空时立即调用）
                # 原因: IntentGraph 连续3次介入策略在实际使用中难以触发（重启清空、领域不一致），
                #       改为只要 Decomposer 匹配到节点就推荐，让用户首次提问就能看到模板
                # 注入位置: current_context["prompt_templates"]（供 Writer Agent 引用）
                #           + workflow_result.prompt_templates（供前端 UI 展示）
                #
                # 推荐控制（V3 增量）:
                #   - recommend_enabled (默认 True): 推荐总开关，前端按钮可关闭
                #   - skip_next_recommend (默认 False): 冷却期标记
                #     用户使用模板后前端置 True，下一次问答跳过推荐，再下一次恢复
                #     避免模板回答仍带模板影响观感
                prompt_templates_for_ui = []
                recommend_enabled = bool(current_context.get("recommend_enabled", True))
                skip_next_recommend = bool(current_context.get("skip_next_recommend", False))
                if not recommend_enabled:
                    logger.info("KnowledgeRecommendation: 推荐总开关已关闭，跳过推荐")
                elif skip_next_recommend:
                    logger.info("KnowledgeRecommendation: 冷却期中（用户刚使用过模板），跳过本次推荐")
                if self.knowledge_recommender and recommend_enabled and not skip_next_recommend:
                    try:
                        decomposer_result = current_context.get("decomposer_result", {})
                        matched_nodes = decomposer_result.get("matched_nodes", []) if decomposer_result else []
                        active_node_ids = [n.id for n in matched_nodes] if matched_nodes else []

                        if active_node_ids:
                            # 直接调用 recommend（不经过 should_intervene 判断）
                            all_recs = self.knowledge_recommender.recommend(
                                current_task=original_user_input,
                                active_nodes=active_node_ids,
                                limit=5,
                            )
                            # 从推荐结果中筛出提示词模板
                            prompt_templates = [
                                r for r in all_recs
                                if r.get("type") == "prompt_template"
                            ]

                            # ============================================================
                            # V2.2 (2026-07-30): 关键字匹配校验
                            # ------------------------------------------------------------
                            # 用户反馈: 模板推荐过于死板，只要 active_nodes 非空就推荐，
                            #          导致简单问题（如「ClusterIP 和 NodePort 区别」）也被推荐无关模板。
                            # 收紧策略: 只有当用户问题中拆解出的关键字与模板的
                            #          intent_tags / domain / title 匹配时才推荐。
                            # ============================================================
                            if prompt_templates:
                                # 复用 Decomposer 提取关键字（与节点匹配保持同一来源）
                                try:
                                    from core.graphs import get_skill_graph
                                    from core.engines.decomposer import Decomposer
                                    _decomposer = Decomposer(get_skill_graph())
                                    user_keywords = _decomposer._extract_keywords(original_user_input)
                                except Exception as kw_err:
                                    logger.warning(f"Keyword extraction for template filter failed: {kw_err}")
                                    user_keywords = []

                                if user_keywords:
                                    # 关键字小写化，便于不区分大小写匹配
                                    kw_lower = [k.lower() for k in user_keywords if k]

                                    # V2.4: 收集 active_nodes 的 domain，用于领域粗匹配兜底
                                    #   当关键字精确匹配未命中时，若模板 domain 与 active_nodes domain 同根，
                                    #   也允许推荐（避免中文关键字与英文模板标签不匹配导致漏推荐）。
                                    active_domains = set()
                                    for n in (matched_nodes or []):
                                        nd = getattr(n, "domain", "") or ""
                                        if nd:
                                            # domain 如 "tech.ai.llm"，取各级前缀作为粗匹配键
                                            parts = nd.split(".")
                                            for i in range(1, len(parts) + 1):
                                                active_domains.add(".".join(parts[:i]))
                                    active_domains.discard("")  # 移除空串

                                    def _template_matches_keywords(tpl: dict) -> bool:
                                        """检查模板是否命中关键字或与 active_nodes 同领域

                                        匹配策略（V2.4 两级）:
                                        1. 精确匹配: 用户关键字命中模板的 intent_tags/domain/title
                                        2. 领域粗匹配兜底: 模板 domain 与 active_nodes domain 同根
                                           （解决中文关键字与英文模板标签不匹配的问题）
                                        """
                                        # 收集模板的可匹配文本（intent_tags + domain + title）
                                        candidate_texts = []
                                        candidate_texts.extend(
                                            str(t).lower() for t in (tpl.get("intent_tags") or [])
                                        )
                                        domain = tpl.get("domain") or ""
                                        if domain:
                                            candidate_texts.append(domain.lower())
                                        title = tpl.get("node") or ""
                                        if title:
                                            candidate_texts.append(title.lower())

                                        # Level 1: 关键字精确匹配
                                        for kw in kw_lower:
                                            if not kw:
                                                continue
                                            for text in candidate_texts:
                                                if kw in text:
                                                    return True

                                        # Level 2: 领域粗匹配兜底
                                        #   模板 domain 与 active_nodes domain 同根时允许推荐
                                        if domain and active_domains:
                                            tpl_domain_lower = domain.lower()
                                            for ad in active_domains:
                                                if ad and (ad in tpl_domain_lower or tpl_domain_lower in ad):
                                                    return True

                                        return False

                                    filtered_templates = [t for t in prompt_templates if _template_matches_keywords(t)]
                                    logger.info(
                                        f"KnowledgeRecommendation: 关键字+领域过滤 "
                                        f"{len(prompt_templates)}→{len(filtered_templates)} "
                                        f"(keywords={kw_lower[:5]}, active_domains={list(active_domains)[:3]})"
                                    )
                                    prompt_templates = filtered_templates

                            if prompt_templates:
                                current_context["prompt_templates"] = prompt_templates
                                # 同时存一份用于 UI 暴露（含完整模板内容，供前端点击填充输入框）
                                prompt_templates_for_ui = [
                                    {
                                        "node_id": r.get("node_id", ""),
                                        "title": r.get("node", ""),
                                        "domain": r.get("domain", ""),
                                        "quality_score": r.get("quality_score", 0.0),
                                        "intent_tags": r.get("intent_tags", []),
                                        "reason": r.get("reason", ""),
                                        # 完整模板内容 + 变量定义 + 难度（供前端填充输入框）
                                        "template_text": r.get("template_text", ""),
                                        "variables": r.get("variables", []),
                                        "difficulty": r.get("difficulty", ""),
                                    }
                                    for r in prompt_templates
                                ]
                                logger.info(
                                    f"KnowledgeRecommendation: 注入 {len(prompt_templates)} 条提示词模板 "
                                    f"(active_nodes={active_node_ids[:3]})"
                                )
                    except Exception as e:
                        logger.warning(f"KnowledgeRecommendation failed: {e}")

            except ImportError:
                logger.debug("TaskClassifier not available, skipping controller decision")
            except Exception as e:
                logger.warning(f"Controller decision failed: {e}")

        # V3: Personal Brain — Context 注入
        if self.brain:
            try:
                brain_context = self.brain.build_context()
                if brain_context:
                    current_context["brain_context"] = brain_context
                    logger.info(f"Brain context injected: {brain_context[:100]}...")
            except Exception as e:
                logger.warning(f"Brain context build failed: {e}")

        # V3: MemoryStore — 长期记忆上下文注入
        if self.memory_store:
            try:
                memory_context = self.memory_store.build_context()
                if memory_context:
                    current_context["memory_context"] = memory_context
                    logger.info(f"MemoryStore context injected ({self.memory_store.count()} memories)")
            except Exception as e:
                logger.warning(f"MemoryStore context build failed: {e}")

        for i, agent_id in enumerate(self.agent_order):
            agent_start = time.time()
            agent_name = self.agent_names.get(agent_id, agent_id)

            try:
                # 构建 Agent 输入
                agent_input = self._build_agent_input(
                    agent_id, current_input, current_context,
                    knowledge_result, writer_output, review_result,
                    original_user_input, executed_locally,
                    difficulty_threshold, judge_decision, cloud_mode,
                    skill_path  # Skill Engine V2
                )

                # 设置 Agent 执行超时
                need_cloud = agent_id == "result" and judge_decision == "cloud_enhance" and cloud_mode != "none"
                if agent_id == "review":
                    timeout = 45  # Review Agent LLM 调用可能较慢
                elif need_cloud:
                    timeout = 120  # 云端增强需要更长时间
                else:
                    timeout = 60

                try:
                    output = await asyncio.wait_for(
                        self.agent_registry.execute_agent(agent_id, agent_input),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Agent '{agent_name}' ({agent_id}) 执行超时 ({timeout}s)")
                    raise TimeoutError(f"Agent '{agent_name}' 执行超时 ({timeout}s)")
                agent_duration = time.time() - agent_start

                step = WorkflowStep(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    input=current_input,
                    output=output.content,
                    success=output.success,
                    duration_seconds=agent_duration,
                    metadata=output.metadata or {}
                )
                steps.append(step)

                # WebSocket 推送：每个 Agent 执行完成后推送 workflow_step（规则五）
                # 使用 model_dump(mode='json') 将 datetime 等转为 JSON 可序列化类型
                ws_mgr = _get_ws_manager()
                if ws_mgr:
                    try:
                        await ws_mgr.broadcast_workflow_step(step.model_dump(mode='json'))
                    except Exception as e:
                        logger.debug(f"WebSocket broadcast_workflow_step failed: {e}")

                current_context[agent_id] = output.content

                if agent_id == "knowledge":
                    knowledge_result = output.content
                    knowledge_found = (
                        output.metadata.get("knowledge_count", 0) > 0
                        if output.metadata else False
                    )
                    # Skill Engine V2: 提取 skill_path
                    skill_path = output.metadata.get("skill_path", ["root", "daily"]) if output.metadata else ["root", "daily"]

                    # 存储 L1 缓存（技能路径）
                    if not cache_hit:
                        try:
                            from core.skill_engine.intent_cache import get_intent_cache
                            get_intent_cache().store_skill_path(original_user_input, skill_path)
                        except Exception:
                            pass

                if agent_id == "writer":
                    writer_output = output.content

                if agent_id == "review":
                    review_result = output.content
                    try:
                        review_data = json.loads(output.content)
                        review_score = review_data.get("review_score", 0.0)
                        # Skill Engine V2: 兼容新旧 ReviewReport 格式
                        difficulty = review_data.get("difficulty", {})
                        difficulty_threshold = difficulty.get("threshold", review_data.get("difficulty_threshold", 0.5))
                    except (json.JSONDecodeError, TypeError):
                        review_score = 0.0
                        difficulty_threshold = 0.5

                    # Skill Engine V2: SkillLearner 反馈收集
                    try:
                        from core.skill_engine.skill_learner import get_skill_learner
                        learner = get_skill_learner()
                        learner.collect_feedback(skill_path, review_data)
                        if learner.should_learn(skill_path[-1]):
                            logger.info(
                                f"SkillLearner: 领域 '{skill_path[-1]}' 已积累 {learner.get_buffer_size(skill_path[-1])} 条反馈，"
                                f"可触发学习"
                            )
                    except Exception:
                        pass

                if agent_id == "judge":
                    try:
                        judge_data = json.loads(output.content)
                        difficulty_threshold = judge_data.get("difficulty_threshold", difficulty_threshold)
                        review_score = judge_data.get("review_score", review_score)
                        judge_decision = judge_data.get("decision", "local_output")
                        cloud_mode = judge_data.get("cloud_mode", "none")
                        executed_locally = judge_decision == "local_output"

                        logger.info(
                            f"Judge decision: {judge_decision}, "
                            f"difficulty_threshold={difficulty_threshold:.2f}, "
                            f"review_score={review_score:.2f}, "
                            f"cloud_mode={cloud_mode}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to parse judge result: {e}")
                        executed_locally = True

                current_input = output.content

            except Exception as e:
                # 错误降级：记录失败步骤，继续执行后续 Agent
                agent_duration = time.time() - agent_start
                error_msg = f"Agent '{agent_name}' ({agent_id}) 执行失败: {str(e)}"
                logger.error(error_msg)
                error_summary.append(error_msg)
                partial_success = True

                # 创建失败步骤
                step = WorkflowStep(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    input=current_input,
                    output="",
                    success=False,
                    duration_seconds=agent_duration,
                    metadata={"error": str(e)}
                )
                steps.append(step)

                # WebSocket 推送：失败步骤也推送（规则五）
                ws_mgr = _get_ws_manager()
                if ws_mgr:
                    try:
                        await ws_mgr.broadcast_workflow_step(step.model_dump(mode='json'))
                    except Exception as e_ws:
                        logger.debug(f"WebSocket broadcast_workflow_step failed: {e_ws}")

                # 如果 knowledge 或 writer 失败，后续 Agent 无法正常工作
                if agent_id == "knowledge":
                    knowledge_result = json.dumps({
                        "task": original_user_input,
                        "original_question": original_user_input,
                        "keywords": [],
                        "knowledge_items": [],
                        "requirements": [],
                        "outline": ["一、任务概述", "二、核心需求", "三、解决方案", "四、实施计划"],
                        "task_type": "通用任务",
                        "summary": f"用户需求：{original_user_input}"
                    })
                    current_input = knowledge_result
                elif agent_id == "writer":
                    writer_output = "内容生成失败，请稍后重试。"
                    current_input = writer_output
                elif agent_id == "review":
                    review_result = json.dumps({
                        "review_score": 0.7,
                        "difficulty_threshold": 0.5,
                        "dimensions": {"structure": 0.7, "relevance": 0.7, "richness": 0.7, "professional": 0.7, "actionable": 0.7},
                        "issues": [], "suggestions": [], "pass": True
                    })
                    current_input = review_result
                elif agent_id == "judge":
                    current_input = json.dumps({
                        "decision": "local_output", "cloud_mode": "none",
                        "difficulty_threshold": 0.5, "review_score": 0.7,
                        "reason": ["Judge 执行失败，降级为本地输出"]
                    })
                elif agent_id == "result":
                    current_input = writer_output

        # 最终结果
        final_result = writer_output
        if judge_decision == "cloud_enhance" and cloud_mode != "none":
            final_result = steps[-1].output if steps else writer_output

        if not executed_locally:
            metrics["cloud_executions"] += 1
            metrics["api_calls"] += 1
        else:
            metrics["local_executions"] += 1
            metrics["cost_saved"] += 0.01

        total_duration = time.time() - start_time
        workflow_end = datetime.now()

        if partial_success:
            logger.warning(
                f"Workflow completed with partial success: {len(error_summary)} error(s). "
                f"Errors: {'; '.join(error_summary[:3])}"
            )

        logger.info(
            f"Workflow completed: difficulty_threshold={difficulty_threshold:.2f}, "
            f"review={review_score:.2f}, local={executed_locally}, "
            f"decision={judge_decision}, duration={total_duration:.2f}s, "
            f"partial_success={partial_success}"
        )

        # V3.1: 构建任务拆分步骤（取代笼统的工作流动画图）
        # 从 current_context 中提取 plan_steps（由 LocalPlanner 生成）
        # 映射到 Agent：第1步→Knowledge，中间→Writer，最后→Result
        task_steps_for_ui = self._build_task_steps(current_context, steps)

        # V3.1: 提取 CognitiveController 真实调度结果
        controller_engines = []
        task_type_value = None
        if decision:
            controller_engines = list(decision.engines)
            task_type_value = decision.task_type

        workflow_output = WorkflowOutput(
            final_result=final_result,
            steps=steps,
            executed_locally=executed_locally,
            total_duration_seconds=total_duration,
            start_time=workflow_start,
            end_time=workflow_end,
            complexity_score=difficulty_threshold,
            partial_success=partial_success,
            error_summary=error_summary if error_summary else None,
            prompt_templates=prompt_templates_for_ui,
            task_steps=task_steps_for_ui,
            controller_engines=controller_engines,
            task_type=task_type_value,
        )

        # Skill Engine V2: 存储 L2 结果缓存
        if executed_locally:
            try:
                from core.skill_engine.intent_cache import get_intent_cache
                get_intent_cache().store_result(original_user_input, {
                    "final_result": final_result,
                    "steps": [s.dict() for s in steps],
                    "executed_locally": executed_locally,
                    "total_duration_seconds": total_duration,
                    "start_time": workflow_start.isoformat(),
                    "end_time": workflow_end.isoformat(),
                    "complexity_score": difficulty_threshold,
                    "partial_success": partial_success,
                    "error_summary": error_summary if error_summary else None,
                })
            except Exception:
                pass

        # V3: Personal Brain — 会话更新
        if self.brain and skill_path:
            try:
                session_data = {
                    "session_id": f"session_{int(time.time())}",
                    "skill_nodes": skill_path,
                    "review_score": review_score,
                }
                self.brain.update_from_session(session_data)
                logger.debug(f"Brain updated: skill_nodes={skill_path}")
            except Exception as e:
                logger.warning(f"Brain session update failed: {e}")

        # V3: Intent Graph — 记录本次会话意图（上下文记忆时间线）
        if self.intent_graph:
            try:
                domain = skill_path[-1] if skill_path else "daily"
                # 从 Knowledge Agent 输出中解析 task_type_v2（安全获取）
                recorded_task_type = "chat"
                try:
                    if knowledge_result:
                        k_data = json.loads(knowledge_result) if isinstance(knowledge_result, str) else knowledge_result
                        recorded_task_type = k_data.get("task_type_v2", "chat")
                except Exception:
                    pass
                self.intent_graph.record(
                    session_id=f"session_{int(time.time())}",
                    question=original_user_input,
                    domain=domain,
                    task_type=recorded_task_type,
                    skill_nodes=skill_path,
                )
                logger.debug(f"IntentGraph recorded: domain={domain}, question={original_user_input[:30]}")
            except Exception as e:
                logger.warning(f"IntentGraph record failed: {e}")

        # WebSocket 推送：最终结果 + Agent 状态汇总（规则五）
        ws_mgr = _get_ws_manager()
        if ws_mgr:
            try:
                # 推送 agent_status（所有 Agent 状态汇总）
                agent_statuses = {}
                for s in steps:
                    agent_statuses[s.agent_id] = {
                        "agent_id": s.agent_id,
                        "agent_name": s.agent_name,
                        "status": "completed" if s.success else "error",
                        "duration_seconds": s.duration_seconds,
                    }
                await ws_mgr.broadcast_agent_status(agent_statuses)

                # 推送 final_result（model_dump mode='json' 确保 datetime 可序列化）
                await ws_mgr.broadcast_final_result(workflow_output.model_dump(mode='json'))
            except Exception as e:
                logger.debug(f"WebSocket final broadcast failed: {e}")

        # V3: MemoryExtractor — 对话结束后自动提取关键信息存入长期记忆
        if self.memory_extractor and not partial_success:
            try:
                # 使用 asyncio.create_task 异步执行，不阻塞主流程返回
                asyncio.create_task(
                    self.memory_extractor.extract_and_store(
                        user_input=original_user_input,
                        response=final_result,
                        user_id="default",
                    )
                )
                logger.debug("MemoryExtractor: scheduled auto memory extraction")
            except Exception as e:
                logger.warning(f"MemoryExtractor scheduling failed: {e}")

        # V3: Learning Engine — 自动学习闭环
        # 触发条件（用户决策 2026-07-28）:
        #   1. 触发云端增强（cloud_mode != "none"）— 润色后的高质量答案才值得学习
        #   2. 或高复杂度（complexity > 0.7）— 复杂任务即使本地处理也值得学习
        # 不再仅依赖 decision.use_learning（避免简单问答也触发学习）
        # 质量门槛（review_score >= 0.70）仍由 LearningEngine.learn() 内部把关
        trigger_cloud_enhance = cloud_mode != "none"
        trigger_high_complexity = bool(decision and decision.complexity > 0.7)
        should_learn = trigger_cloud_enhance or trigger_high_complexity
        if self.learning_engine and should_learn:
            try:
                learning_result = self.learning_engine.learn(
                    user_task=original_user_input,
                    writer_output=writer_output,
                    skill_path=skill_path,
                    review_score=review_score,
                    cloud_enhanced=trigger_cloud_enhance,
                )
                if learning_result["validated"] > 0:
                    applied = self.learning_engine.apply_patches(learning_result)
                    logger.info(
                        f"LearningEngine: validated={learning_result['validated']}, "
                        f"rejected={learning_result['rejected']}, "
                        f"applied={applied}, "
                        f"deepseek={learning_result['deepseek_used']}"
                    )
                    # V3.3: 通知 AuditScheduler 有新增知识点
                    # 仅当 applied > 0 时才计数，避免被拒绝的 patch 触发质检
                    if applied > 0:
                        try:
                            from core.engines.audit_scheduler import get_audit_scheduler
                            get_audit_scheduler().record_knowledge_added(applied)
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"LearningEngine failed: {e}")

        return workflow_output

    async def execute_stream(self, input_data: WorkflowInput) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行工作流，实时返回每个步骤的结果（含错误降级）"""
        steps: List[WorkflowStep] = []
        current_context = input_data.context or {}
        executed_locally = True
        difficulty_threshold = 0.0
        complexity_score = 0.0
        review_score = 0.0
        judge_decision = "local_output"
        cloud_mode = "none"
        knowledge_found = False
        start_time = time.time()
        error_summary: List[str] = []

        current_input = input_data.user_input
        original_user_input = input_data.user_input
        writer_output = ""
        knowledge_result = ""
        review_result = ""
        skill_path = ["root", "daily"]  # Skill Engine V2
        cache_hit = False

        # Skill Engine V2: 意图缓存检查
        try:
            from core.skill_engine.intent_cache import get_intent_cache
            intent_cache = get_intent_cache()

            cached_path = intent_cache.lookup_skill_path(original_user_input)
            if cached_path:
                skill_path = cached_path
                cache_hit = True
                yield {"type": "cache_hit", "message": f"L1 Cache Hit: {cached_path}", "timestamp": time.time()}
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[STREAM] IntentCache 查询失败: {e}")

        logger.info(f"[STREAM] Starting workflow for input: {input_data.user_input[:50]}...")

        yield {"type": "start", "message": "工作流开始执行", "timestamp": time.time()}

        for agent_id in self.agent_order:
            agent_start = time.time()
            agent_name = self.agent_names.get(agent_id, agent_id)

            yield {
                "type": "agent_start", "agent_id": agent_id,
                "agent_name": agent_name, "timestamp": time.time()
            }

            try:
                agent_input = self._build_agent_input(
                    agent_id, current_input, current_context,
                    knowledge_result, writer_output, review_result,
                    original_user_input, executed_locally,
                    difficulty_threshold, judge_decision, cloud_mode,
                    skill_path  # Skill Engine V2
                )

                need_cloud = agent_id == "result" and judge_decision == "cloud_enhance" and cloud_mode != "none"
                timeout = 120 if (agent_id == "result" and need_cloud) else 90

                try:
                    output = await asyncio.wait_for(
                        self.agent_registry.execute_agent(agent_id, agent_input),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"[STREAM] Agent {agent_id} execution timed out")
                    output = AgentOutput(
                        success=False,
                        content=f"Error: Agent {agent_id} 执行超时",
                        metadata={}
                    )

                agent_duration = time.time() - agent_start

                step = WorkflowStep(
                    agent_id=agent_id, agent_name=agent_name,
                    input=agent_input.content[:100] + "..." if len(agent_input.content) > 100 else agent_input.content,
                    output=output.content, success=output.success,
                    duration_seconds=agent_duration,
                    metadata=output.metadata or {}
                )
                steps.append(step)

                current_context[agent_id] = output.content

                if agent_id == "knowledge":
                    knowledge_found = step.metadata.get("knowledge_count", 0) > 0
                    knowledge_result = output.content
                    # Skill Engine V2: 提取 skill_path
                    skill_path = step.metadata.get("skill_path", ["root", "daily"])

                    # 存储 L1 缓存
                    if not cache_hit:
                        try:
                            from core.skill_engine.intent_cache import get_intent_cache
                            get_intent_cache().store_skill_path(original_user_input, skill_path)
                        except Exception:
                            pass

                if agent_id == "writer":
                    writer_output = output.content

                if agent_id == "review":
                    review_result = output.content
                    try:
                        review_data = json.loads(output.content)
                        review_score = review_data.get("review_score", 0.0)
                        difficulty_threshold = review_data.get("difficulty_threshold", 0.5)
                        complexity_score = difficulty_threshold
                    except (json.JSONDecodeError, TypeError):
                        review_score = 0.0
                        difficulty_threshold = 0.5
                        complexity_score = 0.5

                    # Skill Engine V2: SkillLearner 反馈收集
                    try:
                        from core.skill_engine.skill_learner import get_skill_learner
                        get_skill_learner().collect_feedback(skill_path, review_data)
                    except Exception:
                        pass

                if agent_id == "judge":
                    try:
                        judge_data = json.loads(output.content)
                        difficulty_threshold = judge_data.get("difficulty_threshold", difficulty_threshold)
                        complexity_score = difficulty_threshold
                        review_score = judge_data.get("review_score", review_score)
                        judge_decision = judge_data.get("decision", "local_output")
                        cloud_mode = judge_data.get("cloud_mode", "none")
                        executed_locally = judge_decision == "local_output"
                    except Exception as e:
                        logger.error(f"[STREAM] Failed to parse judge result: {e}")
                        executed_locally = True

                current_input = output.content

                yield {
                    "type": "agent_complete", "agent_id": agent_id,
                    "agent_name": agent_name, "duration": round(agent_duration, 2),
                    "success": output.success, "output_length": len(output.content),
                    "timestamp": time.time(),
                    "complexity_score": complexity_score if agent_id == "judge" else None,
                    "executed_locally": executed_locally if agent_id == "judge" else None,
                }

                if agent_id == "judge":
                    yield {
                        "type": "judge_decision",
                        "complexity_score": complexity_score,
                        "executed_locally": executed_locally,
                        "decision": judge_decision,
                        "cloud_mode": cloud_mode,
                        "reason": [],
                        "timestamp": time.time()
                    }

            except Exception as e:
                agent_duration = time.time() - agent_start
                error_msg = f"Agent '{agent_name}' ({agent_id}) 执行失败: {str(e)}"
                logger.error(error_msg)
                error_summary.append(error_msg)

                step = WorkflowStep(
                    agent_id=agent_id, agent_name=agent_name,
                    input=current_input, output="", success=False,
                    duration_seconds=agent_duration,
                    metadata={"error": str(e)}
                )
                steps.append(step)

                yield {
                    "type": "agent_error", "agent_id": agent_id,
                    "agent_name": agent_name, "duration": round(agent_duration, 2),
                    "error": str(e), "timestamp": time.time()
                }

                # 错误降级：继续执行后续 Agent
                if agent_id == "knowledge":
                    knowledge_result = json.dumps({
                        "task": original_user_input, "original_question": original_user_input,
                        "keywords": [], "knowledge_items": [], "requirements": [],
                        "outline": ["一、任务概述", "二、核心需求", "三、解决方案", "四、实施计划"],
                        "task_type": "通用任务", "summary": f"用户需求：{original_user_input}"
                    })
                    current_input = knowledge_result
                elif agent_id == "writer":
                    writer_output = "内容生成失败，请稍后重试。"
                    current_input = writer_output
                elif agent_id == "review":
                    review_result = json.dumps({
                        "review_score": 0.7, "difficulty_threshold": 0.5,
                        "dimensions": {"structure": 0.7, "relevance": 0.7, "richness": 0.7, "professional": 0.7, "actionable": 0.7},
                        "issues": [], "suggestions": [], "pass": True
                    })
                    current_input = review_result
                elif agent_id == "judge":
                    current_input = json.dumps({
                        "decision": "local_output", "cloud_mode": "none",
                        "difficulty_threshold": 0.5, "review_score": 0.7,
                        "reason": ["Judge 执行失败，降级为本地输出"]
                    })
                elif agent_id == "result":
                    current_input = writer_output

        final_result = writer_output
        if judge_decision == "cloud_enhance" and cloud_mode != "none":
            final_result = steps[-1].output if steps else writer_output

        total_duration = time.time() - start_time

        logger.info(f"[STREAM] Final result length: {len(final_result)}, first 100 chars: {final_result[:100]}")

        yield {
            "type": "complete",
            "final_result": final_result,
            "executed_locally": executed_locally,
            "complexity_score": complexity_score,
            "total_duration": round(total_duration, 2),
            "steps_count": len(steps),
            "error_summary": error_summary if error_summary else None,
            "timestamp": time.time()
        }

    def _build_task_steps(self, current_context: Dict, steps: List[WorkflowStep]) -> List[TaskStep]:
        """V3.1: 构建"用户能看懂的逐条任务列表"，取代笼统的工作流动画图

        数据来源：LocalPlanner 生成的 plan_steps（List[str]）
        映射规则：
          - 第 1 条 → Knowledge Agent（知识检索与需求理解）
          - 中间条 → Writer Agent（内容生成）
          - 最后 1 条 → Result Agent（结果格式化）
        Review/Judge 是内部质量管控步骤，不直接对应任务

        兜底：无 plan_steps 时返回空列表（前端显示 Agent 执行进度作为兜底）
        """
        plan_steps = current_context.get("plan_steps", [])
        if not plan_steps:
            return []

        # Agent 名称映射
        agent_names = {
            "knowledge": "Knowledge Agent",
            "writer": "Writer Agent",
            "result": "Result Agent",
        }

        # 各 Agent 实际耗时（从 steps 中提取）
        agent_durations = {}
        for s in steps:
            if s.agent_id in ("knowledge", "writer", "result"):
                agent_durations[s.agent_id] = s.duration_seconds

        task_steps = []
        total = len(plan_steps)
        for idx, title in enumerate(plan_steps):
            step_num = idx + 1
            # 映射到 Agent
            if step_num == 1:
                agent_id = "knowledge"
            elif step_num == total:
                agent_id = "result"
            else:
                agent_id = "writer"

            task_steps.append(TaskStep(
                step_id=step_num,
                title=title,
                agent_id=agent_id,
                agent_name=agent_names.get(agent_id, ""),
                status="completed",  # 执行完成后全部标记为 completed
                duration_seconds=round(agent_durations.get(agent_id, 0.0), 2),
            ))

        return task_steps

    def _build_agent_input(self, agent_id: str, current_input: str,
                           current_context: Dict, knowledge_result: str,
                           writer_output: str, review_result: str,
                           original_user_input: str, executed_locally: bool,
                           difficulty_threshold: float, judge_decision: str,
                           cloud_mode: str, skill_path: List[str] = None) -> AgentInput:
        """构建 Agent 输入"""
        if skill_path is None:
            skill_path = ["root", "daily"]

        if agent_id == "knowledge":
            return AgentInput(
                content=current_input, context=current_context,
                use_llm=True, use_cloud=False
            )
        elif agent_id == "writer":
            writer_context = dict(current_context)
            # V3: 注入推理模式到 Writer Agent
            if "reasoning_pattern" in current_context:
                writer_context["reasoning_pattern"] = current_context["reasoning_pattern"]
            return AgentInput(
                content=knowledge_result if knowledge_result else current_input,
                context=writer_context, use_llm=True, use_cloud=False
            )
        elif agent_id == "review":
            review_input = json.dumps({
                "user_task": original_user_input,
                "summary": knowledge_result,
                "writer_output": writer_output,
                "skill_path": skill_path  # Skill Engine V2
            })
            return AgentInput(
                content=review_input, context=current_context,
                use_llm=True, use_cloud=False
            )
        elif agent_id == "judge":
            # V2.4: 从 knowledge_result 提取自学习知识信号，透传给 Judge 做质量补救加成
            skill_graph_used = False
            skill_graph_contents = []
            try:
                kg_data = safe_json_parse(knowledge_result) if knowledge_result else {}
                if isinstance(kg_data, dict):
                    skill_graph_used = bool(kg_data.get("skill_graph_used", False))
                    skill_graph_contents = kg_data.get("skill_graph_contents", []) or []
            except Exception:
                pass

            judge_input = json.dumps({
                "user_task": original_user_input,
                "review_result": review_result,
                "writer_output": writer_output,
                "skill_path": skill_path,  # Skill Engine V2
                # V2.4: 自学习知识信号（供 Judge 检测 Writer 是否基于自学习知识回答）
                "skill_graph_used": skill_graph_used,
                "skill_graph_contents": skill_graph_contents,
            })
            return AgentInput(
                content=judge_input, context=current_context,
                use_llm=False, use_cloud=False
            )
        elif agent_id == "result":
            result_input = json.dumps({
                "user_task": original_user_input,
                "summary_result": knowledge_result,
                "review_result": review_result,
                "judge_result": current_context.get("judge", "{}"),
                "writer_output": writer_output,
                "executed_locally": executed_locally,
                "difficulty_threshold": difficulty_threshold,
                "judge_decision": judge_decision,
                "cloud_mode": cloud_mode,
                "skill_path": skill_path  # Skill Engine V2
            })
            need_cloud = judge_decision == "cloud_enhance" and cloud_mode != "none"
            return AgentInput(
                content=result_input, context=current_context,
                use_llm=True, use_cloud=need_cloud
            )
        else:
            return AgentInput(
                content=current_input, context=current_context,
                use_llm=True, use_cloud=False
            )