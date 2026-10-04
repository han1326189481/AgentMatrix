from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.dependencies import get_agent_registry
from agents.base.agent import AgentInput

router = APIRouter()


@router.get("/")
async def get_all_agents(registry=Depends(get_agent_registry)):
    return {
        "agents": registry.get_all_agent_statuses(),
        "count": len(registry.get_all_agents())
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: str, registry=Depends(get_agent_registry)):
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent.get_status()


@router.post("/{agent_id}/execute")
async def execute_agent(
    agent_id: str,
    input_data: AgentInput,
    registry=Depends(get_agent_registry)
):
    try:
        result = await registry.execute_agent(agent_id, input_data)
        return result.dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str, registry=Depends(get_agent_registry)):
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return agent.get_status()
