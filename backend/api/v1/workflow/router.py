from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
from app.dependencies import get_agent_registry
from agents.base.agent import AgentInput, AgentOutput

router = APIRouter()


class WorkflowInput(BaseModel):
    user_input: str
    context: Optional[Dict[str, Any]] = None


class WorkflowOutput(BaseModel):
    final_result: str
    steps: List[Dict[str, Any]]
    executed_locally: bool
    total_time: float


@router.post("/execute", response_model=WorkflowOutput)
async def execute_workflow(
    input_data: WorkflowInput,
    registry=Depends(get_agent_registry)
):
    steps = []
    current_context = input_data.context or {}
    executed_locally = True
    
    try:
        knowledge_output = await registry.execute_agent(
            "knowledge",
            AgentInput(content=input_data.user_input, context=current_context)
        )
        steps.append({"agent": "knowledge", "output": knowledge_output.dict()})
        current_context["knowledge"] = knowledge_output.content
        
        summary_output = await registry.execute_agent(
            "summary",
            AgentInput(content=knowledge_output.content, context=current_context)
        )
        steps.append({"agent": "summary", "output": summary_output.dict()})
        current_context["summary"] = summary_output.content
        
        writer_output = await registry.execute_agent(
            "writer",
            AgentInput(content=summary_output.content, context=current_context)
        )
        steps.append({"agent": "writer", "output": writer_output.dict()})
        current_context["writer"] = writer_output.content
        
        review_output = await registry.execute_agent(
            "review",
            AgentInput(content=writer_output.content, context=current_context)
        )
        steps.append({"agent": "review", "output": review_output.dict()})
        current_context["review"] = review_output.content
        
        judge_output = await registry.execute_agent(
            "judge",
            AgentInput(content=review_output.content, context=current_context)
        )
        steps.append({"agent": "judge", "output": judge_output.dict()})
        current_context["judge"] = judge_output.content
        
        executed_locally = judge_output.metadata.get("executed_locally", True)
        
        result_output = await registry.execute_agent(
            "result",
            AgentInput(content=judge_output.content, context=current_context)
        )
        steps.append({"agent": "result", "output": result_output.dict()})
        
        return WorkflowOutput(
            final_result=result_output.content,
            steps=steps,
            executed_locally=executed_locally,
            total_time=0.0
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))