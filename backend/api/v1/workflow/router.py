from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional, List, Tuple, AsyncGenerator
from app.dependencies import get_agent_registry
from agents.base.agent import AgentInput, AgentOutput
from models.workflow import WorkflowInput, WorkflowOutput, WorkflowStep
from api.v1.metrics.router import get_metrics_store
import asyncio
import time
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

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
    review_score = 0.0
    judge_decision = "local_output"
    cloud_mode = "none"
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
        original_user_input = input_data.user_input
        writer_output = ""
        summary_result = ""
        review_result = ""
        
        for agent_id in agent_order:
            agent_start = time.time()
            agent_name = agent_names.get(agent_id, agent_id)
            
            # 根据 Agent 类型构建正确的输入格式
            if agent_id == "review":
                agent_input_content = json.dumps({
                    "user_task": original_user_input,
                    "summary": summary_result,
                    "writer_output": writer_output
                })
            elif agent_id == "judge":
                agent_input_content = json.dumps({
                    "user_task": original_user_input,
                    "summary_result": summary_result,
                    "review_result": review_result,
                    "writer_output": writer_output
                })
            elif agent_id == "result":
                agent_input_content = json.dumps({
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
            else:
                agent_input_content = current_input
            
            try:
                output = await registry.execute_agent(
                    agent_id,
                    AgentInput(content=agent_input_content, context=current_context, use_llm=True, use_cloud=False)
                )
                agent_duration = time.time() - agent_start
                
                step = WorkflowStep(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    input=agent_input_content[:100] + "..." if len(agent_input_content) > 100 else agent_input_content,
                    output=output.content,
                    success=output.success,
                    duration_seconds=agent_duration,
                    metadata=output.metadata or {}
                )
                steps.append(step)
                
                current_context[agent_id] = output.content
                
                # 保存关键 Agent 的输出
                if agent_id == "summary":
                    summary_result = output.content
                elif agent_id == "writer":
                    writer_output = output.content
                elif agent_id == "review":
                    review_result = output.content
                    try:
                        review_data = json.loads(output.content)
                        review_score = review_data.get("review_score", 0.0)
                    except:
                        review_score = 0.0
                elif agent_id == "judge":
                    try:
                        judge_data = json.loads(output.content)
                        complexity_score = judge_data.get("complexity_score", 0.0)
                        review_score = judge_data.get("review_score", review_score)
                        judge_decision = judge_data.get("decision", "local_output")
                        cloud_mode = judge_data.get("cloud_mode", "none")
                        executed_locally = judge_decision == "local_output"
                    except Exception as e:
                        executed_locally = True
                
                current_input = output.content
                
                if not output.success:
                    raise HTTPException(status_code=500, detail=f"Agent {agent_id} failed")
            
            except Exception as e:
                agent_duration = time.time() - agent_start
                step = WorkflowStep(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    input=agent_input_content[:100] if agent_input_content else "",
                    output="",
                    success=False,
                    duration_seconds=agent_duration,
                    metadata={"error": str(e)}
                )
                steps.append(step)
                raise HTTPException(status_code=500, detail=f"Agent {agent_id} failed: {str(e)}")
        
        final_result = steps[-1].output if steps else ""
        total_duration = time.time() - start_time
        workflow_end = datetime.now()
        
        if executed_locally:
            metrics["local_executions"] += 1
            metrics["cost_saved"] += 0.01
        else:
            metrics["cloud_executions"] += 1
            metrics["api_calls"] += 1
        
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


async def execute_workflow_stream(
    input_data: WorkflowInput,
    registry
) -> AsyncGenerator[Dict[str, Any], None]:
    """流式执行工作流，实时返回每个步骤的结果"""
    steps: List[WorkflowStep] = []
    current_context = input_data.context or {}
    executed_locally = True
    complexity_score = 0.0
    start_time = time.time()
    
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
        
        logger.info(f"[STREAM] Starting workflow for input: {input_data.user_input[:50]}...")
        
        yield {
            "type": "start",
            "message": "工作流开始执行",
            "timestamp": time.time()
        }
        
        for agent_id in agent_order:
            agent_start = time.time()
            agent_name = agent_names.get(agent_id, agent_id)
            
            yield {
                "type": "agent_start",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "timestamp": time.time()
            }
            
            try:
                if agent_id == "summary":
                    agent_input = f"{current_context.get('knowledge', '')}\n\n任务摘要: {current_input}"
                elif agent_id == "writer":
                    agent_input = f"{current_context.get('knowledge', '')}\n\n任务摘要: {current_context.get('summary', '')}"
                elif agent_id == "review":
                    agent_input = f"待评审内容: {current_input}\n任务摘要: {current_context.get('summary', '')}"
                elif agent_id == "judge":
                    agent_input = f"内容: {current_input}\n评审结果: {current_context.get('review', '')}"
                elif agent_id == "result":
                    agent_input = json.dumps({
                        "user_task": input_data.user_input,
                        "summary_result": current_context.get("summary", ""),
                        "review_result": current_context.get("review", ""),
                        "judge_result": current_context.get("judge", ""),
                        "writer_output": current_context.get("writer", ""),
                        "executed_locally": executed_locally,
                        "complexity_score": complexity_score,
                        "judge_decision": "local_output" if executed_locally else "cloud_enhance",
                        "cloud_mode": "none"
                    }, ensure_ascii=False)
                    logger.info(f"[DEBUG] Result Agent input: user_task={input_data.user_input[:50]}..., writer_output exists: {bool(current_context.get('writer'))}")
                else:
                    agent_input = current_input
                
                logger.info(f"[DEBUG] Executing {agent_id} with input length: {len(agent_input)}")
                
                try:
                    output = await asyncio.wait_for(
                        registry.execute_agent(
                            agent_id,
                            AgentInput(content=agent_input, context=current_context, use_llm=True, use_cloud=False)
                        ),
                        timeout=60  # 60秒超时
                    )
                except asyncio.TimeoutError:
                    logger.error(f"[DEBUG] Agent {agent_id} execution timed out")
                    output = AgentOutput(
                        success=False,
                        content=f"Error: Agent {agent_id} 执行超时",
                        metadata={}
                    )
                agent_duration = time.time() - agent_start
                
                step = WorkflowStep(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    input=agent_input[:100] + "..." if len(agent_input) > 100 else agent_input,
                    output=output.content,
                    success=output.success,
                    duration_seconds=agent_duration,
                    metadata=output.metadata or {}
                )
                steps.append(step)
                
                current_context[agent_id] = output.content
                current_input = output.content
                
                yield {
                    "type": "agent_complete",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "duration": round(agent_duration, 2),
                    "success": output.success,
                    "output_length": len(output.content),
                    "timestamp": time.time()
                }
                
                if agent_id == "judge":
                    executed_locally = step.metadata.get("executed_locally", True)
                    complexity_score = step.metadata.get("complexity_score", 0.0)
            
            except Exception as e:
                agent_duration = time.time() - agent_start
                yield {
                    "type": "agent_error",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "duration": round(agent_duration, 2),
                    "error": str(e),
                    "timestamp": time.time()
                }
                raise
        
        final_result = steps[-1].output if steps else ""
        total_duration = time.time() - start_time
        
        logger.info(f"[DEBUG] Final result length: {len(final_result)}, first 100 chars: {final_result[:100]}")
        
        yield {
            "type": "complete",
            "final_result": final_result,
            "executed_locally": executed_locally,
            "complexity_score": complexity_score,
            "total_duration": round(total_duration, 2),
            "steps_count": len(steps),
            "timestamp": time.time()
        }
        
    except Exception as e:
        yield {
            "type": "error",
            "error": str(e),
            "timestamp": time.time()
        }