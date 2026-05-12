from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.dependencies import get_agent_registry
from agents.base.agent import AgentInput, AgentOutput

router = APIRouter()


@router.get("/")
async def get_all_agents(registry=Depends(get_agent_registry)):
    return registry.get_all_agent_statuses()


@router.get("/{agent_id}")
async def get_agent_status(agent_id: str, registry=Depends(get_agent_registry)):
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.get_status()


@router.post("/{agent_id}/execute")
async def execute_agent(
    agent_id: str,
    input_data: AgentInput,
    registry=Depends(get_agent_registry)
) -> AgentOutput:
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        result = await agent.execute(input_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))