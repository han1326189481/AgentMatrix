from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional, List, Tuple
from app.dependencies import get_agent_registry
from agents.base.agent import AgentInput, AgentOutput
from models.workflow import WorkflowInput, WorkflowOutput, WorkflowStep
from api.v1.metrics.router import get_metrics_store
import asyncio
import time
from datetime import datetime

router = APIRouter()

class SimpleCache:
    def __init__(self, maxsize: int = 100, ttl: int = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache: Dict[str, Tuple[Any, float]] = {}
    
    def __contains__(self, key: str) -> bool:
        if key in self.cache:
            _, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return True
            del self.cache[key]
        return False
    
    def __getitem__(self, key: str) -> Any:
        if key in self:
            return self.cache[key][0]
        raise KeyError(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        if len(self.cache) >= self.maxsize:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]
        self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        self.cache.clear()
    
    @property
    def size(self) -> int:
        return len(self.cache)

workflow_cache = SimpleCache(maxsize=100, ttl=300)


async def execute_agent_with_timing(
    registry,
    agent_id: str,
    agent_name: str,
    current_input: str,
    current_context: Dict[str, Any]
) -> Tuple[WorkflowStep, str]:
    agent_start = time.time()
    
    try:
        output = await registry.execute_agent(
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
        
        return step, output.content
    
    except Exception as e:
        agent_duration = time.time() - agent_start
        step = WorkflowStep(
            agent_id=agent_id,
            agent_name=agent_name,
            input=current_input,
            output="",
            success=False,
            duration_seconds=agent_duration,
            metadata={"error": str(e)}
        )
        return step, ""


@router.post("/execute", response_model=WorkflowOutput)
async def execute_workflow(
    input_data: WorkflowInput,
    registry=Depends(get_agent_registry)
):
    cache_key = f"workflow_{hash(input_data.user_input)}_{hash(str(input_data.context))}"
    
    if cache_key in workflow_cache:
        cached_result = workflow_cache[cache_key]
        return cached_result
    
    steps: List[WorkflowStep] = []
    current_context = input_data.context or {}
    executed_locally = True
    complexity_score = 0.0
    start_time = time.time()
    workflow_start = datetime.now()
    
    metrics = get_metrics_store()
    metrics["total_requests"] += 1
    
    try:
        agent_order = ["knowledge", "summary", "writer", "review", "judge", "result"]
        agent_names = {
            "knowledge": "Knowledge Agent",
            "summary": "Summary Agent",
            "writer": "Writer Agent",
            "review": "Review Agent",
            "judge": "Judge Agent",
            "result": "Result Agent"
        }
        
        current_input = input_data.user_input
        
        for agent_id in agent_order:
            step, output_content = await execute_agent_with_timing(
                registry, agent_id, agent_names.get(agent_id, agent_id),
                current_input, current_context
            )
            steps.append(step)
            
            if not step.success:
                raise HTTPException(status_code=500, detail=f"Agent {agent_id} failed: {step.metadata.get('error', 'unknown')}")
            
            current_context[agent_id] = output_content
            current_input = output_content
            
            if agent_id == "judge":
                executed_locally = step.metadata.get("executed_locally", True)
                complexity_score = step.metadata.get("complexity_score", 0.0)
                
                if executed_locally:
                    metrics["local_executions"] += 1
                    metrics["cost_saved"] += 0.01
                else:
                    metrics["cloud_executions"] += 1
                    metrics["api_calls"] += 1
        
        final_result = steps[-1].output if steps else ""
        total_duration = time.time() - start_time
        workflow_end = datetime.now()
        
        result = WorkflowOutput(
            final_result=final_result,
            steps=steps,
            executed_locally=executed_locally,
            total_duration_seconds=total_duration,
            start_time=workflow_start,
            end_time=workflow_end,
            complexity_score=complexity_score
        )
        
        if executed_locally and len(final_result) < 5000:
            workflow_cache[cache_key] = result
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/parallel", response_model=WorkflowOutput)
async def execute_workflow_parallel(
    input_data: WorkflowInput,
    registry=Depends(get_agent_registry)
):
    cache_key = f"workflow_parallel_{hash(input_data.user_input)}_{hash(str(input_data.context))}"
    
    if cache_key in workflow_cache:
        return workflow_cache[cache_key]
    
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
        
        step_knowledge, knowledge_output = await execute_agent_with_timing(
            registry, "knowledge", "Knowledge Agent", current_input, current_context
        )
        steps.append(step_knowledge)
        
        if not step_knowledge.success:
            raise HTTPException(status_code=500, detail=f"Knowledge Agent failed")
        
        current_context["knowledge"] = knowledge_output
        
        step_summary, summary_output = await execute_agent_with_timing(
            registry, "summary", "Summary Agent", knowledge_output, current_context
        )
        steps.append(step_summary)
        
        if not step_summary.success:
            raise HTTPException(status_code=500, detail=f"Summary Agent failed")
        
        current_context["summary"] = summary_output
        
        writer_input = f"{knowledge_output}\n\n任务摘要: {summary_output}"
        step_writer, writer_output = await execute_agent_with_timing(
            registry, "writer", "Writer Agent", writer_input, current_context
        )
        steps.append(step_writer)
        
        if not step_writer.success:
            raise HTTPException(status_code=500, detail=f"Writer Agent failed")
        
        current_context["writer"] = writer_output
        
        review_input = f"待评审内容: {writer_output}\n任务摘要: {summary_output}"
        step_review, review_output = await execute_agent_with_timing(
            registry, "review", "Review Agent", review_input, current_context
        )
        steps.append(step_review)
        
        if not step_review.success:
            raise HTTPException(status_code=500, detail=f"Review Agent failed")
        
        current_context["review"] = review_output
        
        judge_input = f"内容: {writer_output}\n评审结果: {review_output}"
        step_judge, judge_output = await execute_agent_with_timing(
            registry, "judge", "Judge Agent", judge_input, current_context
        )
        steps.append(step_judge)
        
        if not step_judge.success:
            raise HTTPException(status_code=500, detail=f"Judge Agent failed")
        
        executed_locally = step_judge.metadata.get("executed_locally", True)
        complexity_score = step_judge.metadata.get("complexity_score", 0.0)
        
        if executed_locally:
            metrics["local_executions"] += 1
            metrics["cost_saved"] += 0.01
        else:
            metrics["cloud_executions"] += 1
            metrics["api_calls"] += 1
        
        current_context["judge"] = judge_output
        
        result_input = f"执行结果: {writer_output}\n评审: {review_output}\n复杂度: {complexity_score}"
        step_result, result_output = await execute_agent_with_timing(
            registry, "result", "Result Agent", result_input, current_context
        )
        steps.append(step_result)
        
        if not step_result.success:
            raise HTTPException(status_code=500, detail=f"Result Agent failed")
        
        final_result = result_output
        total_duration = time.time() - start_time
        workflow_end = datetime.now()
        
        result = WorkflowOutput(
            final_result=final_result,
            steps=steps,
            executed_locally=executed_locally,
            total_duration_seconds=total_duration,
            start_time=workflow_start,
            end_time=workflow_end,
            complexity_score=complexity_score
        )
        
        if executed_locally and len(final_result) < 5000:
            workflow_cache[cache_key] = result
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    return {
        "cache_size": workflow_cache.size,
        "max_size": workflow_cache.maxsize,
        "ttl": workflow_cache.ttl
    }


@router.post("/cache/clear")
async def clear_cache():
    workflow_cache.clear()
    return {"status": "success", "message": "Cache cleared"}