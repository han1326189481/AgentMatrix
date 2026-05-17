from typing import Dict, Any, List, Optional
from agents.base.agent import AgentInput, AgentOutput
from agents.base.agent_registry import AgentRegistry
from models.workflow import WorkflowInput, WorkflowOutput, WorkflowStep
from core.dynamic_router import get_dynamic_router
from api.v1.metrics.router import get_metrics_store
from core.llm.client import get_llm_client
import time
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(self, agent_registry: AgentRegistry):
        self.agent_registry = agent_registry
        self.dynamic_router = get_dynamic_router()
        self.agent_order = ["knowledge", "summary", "writer", "review", "judge", "result"]
        self.agent_names = {
            "knowledge": "Knowledge Agent",
            "summary": "Summary Agent",
            "writer": "Writer Agent",
            "review": "Review Agent",
            "judge": "Judge Agent",
            "result": "Result Agent"
        }

    async def execute(self, input_data: WorkflowInput) -> WorkflowOutput:
        steps: List[WorkflowStep] = []
        current_context = input_data.context or {}
        executed_locally = True
        complexity_score = 0.0
        review_score = 0.0
        judge_decision = "local_output"
        cloud_mode = "none"
        knowledge_found = False
        start_time = time.time()
        workflow_start = datetime.now()

        metrics = get_metrics_store()
        metrics["total_requests"] += 1

        try:
            current_input = input_data.user_input
            original_user_input = input_data.user_input
            writer_output = ""
            summary_result = ""
            review_result = ""
            
            for i, agent_id in enumerate(self.agent_order):
                agent_start = time.time()
                agent_name = self.agent_names.get(agent_id, agent_id)
                
                if agent_id == "review":
                    review_input = json.dumps({
                        "user_task": original_user_input,
                        "summary": summary_result,
                        "writer_output": writer_output
                    })
                    agent_input = AgentInput(content=review_input, context=current_context, use_llm=True, use_cloud=False)
                elif agent_id == "judge":
                    judge_input = json.dumps({
                        "user_task": original_user_input,
                        "summary_result": summary_result,
                        "review_result": review_result,
                        "writer_output": writer_output,
                        "knowledge_found": knowledge_found
                    })
                    agent_input = AgentInput(content=judge_input, context=current_context, use_llm=False, use_cloud=False)
                elif agent_id == "result":
                    # Result Agent 需要的格式
                    result_input = json.dumps({
                        "user_task": original_user_input,
                        "summary_result": summary_result,
                        "review_result": review_result,
                        "judge_result": current_context.get("judge", "{}"),
                        "writer_output": writer_output,
                        "executed_locally": executed_locally,
                        "complexity_score": complexity_score,
                        "judge_decision": judge_decision,
                        "cloud_mode": cloud_mode
                    })
                    # 只有cloud_enhance才真正调云端；local_retry只是建议本地增强，不调云端
                    need_cloud_enhance = judge_decision == "cloud_enhance" and cloud_mode != "none"
                    agent_input = AgentInput(content=result_input, context=current_context, use_llm=True, use_cloud=need_cloud_enhance)
                else:
                    agent_input = AgentInput(content=current_input, context=current_context, use_llm=True, use_cloud=False)

                output = await self.agent_registry.execute_agent(agent_id, agent_input)
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

                current_context[agent_id] = output.content
                
                if agent_id == "knowledge":
                    knowledge_found = output.metadata.get("knowledge_count", 0) > 0 if output.metadata else False
                
                if agent_id == "summary":
                    summary_result = output.content
                
                if agent_id == "writer":
                    writer_output = output.content
                
                if agent_id == "review":
                    review_result = output.content
                    try:
                        review_data = json.loads(output.content)
                        review_score = review_data.get("review_score", 0.0)
                    except:
                        review_score = 0.0
                
                if agent_id == "judge":
                    try:
                        judge_data = json.loads(output.content)
                        complexity_score = judge_data.get("complexity_score", 0.0)
                        review_score = judge_data.get("review_score", review_score)
                        judge_decision = judge_data.get("decision", "local_output")
                        cloud_mode = judge_data.get("cloud_mode", "none")
                        executed_locally = judge_decision == "local_output"
                        
                        logger.info(f"Judge decision: {judge_decision}, complexity={complexity_score:.2f}, review_score={review_score:.2f}, cloud_mode={cloud_mode}")
                    except Exception as e:
                        logger.error(f"Failed to parse judge result: {e}")
                        executed_locally = True
                
                current_input = output.content

            # 找到Writer和Judge的输出
            writer_output = ""
            for step in steps:
                if step.agent_id == "writer":
                    writer_output = step.output
                    break
            
            # 如果需要云端增强，则使用Result Agent的云端输出
            final_result = writer_output
            if judge_decision == "cloud_enhance" and cloud_mode != "none":
                final_result = output.content if steps else writer_output
            
            if not executed_locally:
                metrics["cloud_executions"] += 1
                metrics["api_calls"] += 1
            else:
                metrics["local_executions"] += 1
                metrics["cost_saved"] += 0.01

            total_duration = time.time() - start_time
            workflow_end = datetime.now()

            logger.info(f"Workflow completed: complexity={complexity_score:.2f}, review={review_score:.2f}, local={executed_locally}, decision={judge_decision}, duration={total_duration:.2f}s")

            return WorkflowOutput(
                final_result=final_result,
                steps=steps,
                executed_locally=executed_locally,
                total_duration_seconds=total_duration,
                start_time=workflow_start,
                end_time=workflow_end,
                complexity_score=complexity_score
            )

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise

    async def execute_with_llm_enhancement(self, input_data: WorkflowInput) -> WorkflowOutput:
        return await self.execute(input_data)

    async def get_step_by_agent(self, steps: List[WorkflowStep], agent_id: str) -> Optional[WorkflowStep]:
        for step in steps:
            if step.agent_id == agent_id:
                return step
        return None

    def calculate_cost_savings(self, cloud_executions: int, local_executions: int) -> float:
        cloud_cost_per_call = 0.01  
        local_cost_per_call = 0.001  
        return cloud_executions * (cloud_cost_per_call - local_cost_per_call)