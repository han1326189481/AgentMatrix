from typing import Dict, Any, List, Optional
from agents.base.agent import AgentInput, AgentOutput
from agents.base.agent_registry import AgentRegistry
from models.workflow import WorkflowInput, WorkflowOutput, WorkflowStep
from core.dynamic_router import get_dynamic_router
from api.v1.metrics.router import get_metrics_store
import time
from datetime import datetime
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
        start_time = time.time()
        workflow_start = datetime.now()

        metrics = get_metrics_store()
        metrics["total_requests"] += 1

        try:
            current_input = input_data.user_input

            for agent_id in self.agent_order:
                agent_start = time.time()
                agent_name = self.agent_names.get(agent_id, agent_id)

                output = await self.agent_registry.execute_agent(
                    agent_id,
                    AgentInput(content=current_input, context=current_context)
                )
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
                current_input = output.content

                if agent_id == "judge":
                    executed_locally = output.metadata.get("executed_locally", True)
                    complexity_score = output.metadata.get("complexity_score", 0.0)

                    if executed_locally:
                        metrics["local_executions"] += 1
                        metrics["cost_saved"] += 0.01
                    else:
                        metrics["cloud_executions"] += 1
                        metrics["api_calls"] += 1

            final_result = steps[-1].output if steps else ""
            total_duration = time.time() - start_time
            workflow_end = datetime.now()

            logger.info(f"Workflow completed: complexity={complexity_score:.2f}, local={executed_locally}, duration={total_duration:.2f}s")

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
        workflow_result = await self.execute(input_data)
        
        if not workflow_result.executed_locally and workflow_result.complexity_score:
            logger.info(f"Enhancing with LLM: complexity={workflow_result.complexity_score}")
            
            routing_result = await self.dynamic_router.route(
                complexity_score=workflow_result.complexity_score,
                prompt=workflow_result.final_result,
                system_prompt="请优化以下内容，使其更加专业和完善"
            )
            
            if routing_result.get("success", False):
                workflow_result.final_result = routing_result.get("result", workflow_result.final_result)
        
        return workflow_result

    async def get_step_by_agent(self, steps: List[WorkflowStep], agent_id: str) -> Optional[WorkflowStep]:
        for step in steps:
            if step.agent_id == agent_id:
                return step
        return None

    def calculate_cost_savings(self, cloud_executions: int, local_executions: int) -> float:
        cloud_cost_per_call = 0.01  
        local_cost_per_call = 0.001  
        return cloud_executions * (cloud_cost_per_call - local_cost_per_call)
