from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel
from app.dependencies import get_agent_registry
from api.v1.workflow.router import execute_workflow, WorkflowInput, workflow_cache
from cachetools import TTLCache

router = APIRouter()

chat_cache = TTLCache(maxsize=200, ttl=300)


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: float


class ChatRequest(BaseModel):
    content: str


@router.post("/send")
async def send_message(
    request: ChatRequest,
    registry=Depends(get_agent_registry)
):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    
    cache_key = f"chat_{hash(request.content)}"
    
    if cache_key in chat_cache:
        return chat_cache[cache_key]
    
    try:
        result = await execute_workflow(
            WorkflowInput(user_input=request.content),
            registry
        )
        
        response = {
            "response": result.final_result,
            "executed_locally": result.executed_locally,
            "complexity_score": result.complexity_score,
            "total_duration": result.total_duration_seconds,
            "steps_count": len(result.steps)
        }
        
        if result.executed_locally and len(result.final_result) < 5000:
            chat_cache[cache_key] = response
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/send/batch")
async def send_batch_messages(
    requests: List[ChatRequest],
    registry=Depends(get_agent_registry)
):
    results = []
    
    for request in requests:
        if not request.content.strip():
            results.append({"error": "内容不能为空"})
            continue
        
        try:
            cache_key = f"chat_{hash(request.content)}"
            
            if cache_key in chat_cache:
                results.append(chat_cache[cache_key])
                continue
            
            result = await execute_workflow(
                WorkflowInput(user_input=request.content),
                registry
            )
            
            response = {
                "input": request.content,
                "response": result.final_result,
                "executed_locally": result.executed_locally,
                "complexity_score": result.complexity_score,
                "total_duration": result.total_duration_seconds
            }
            
            if result.executed_locally and len(result.final_result) < 5000:
                chat_cache[cache_key] = response
            
            results.append(response)
        except Exception as e:
            results.append({"error": str(e)})
    
    return {"results": results}


@router.get("/health")
async def chat_health():
    return {"status": "ok", "service": "chat", "cache_size": len(chat_cache)}


@router.get("/cache/stats")
async def get_chat_cache_stats():
    return {
        "chat_cache_size": len(chat_cache),
        "chat_cache_max_size": chat_cache.maxsize,
        "chat_cache_ttl": chat_cache.ttl,
        "workflow_cache_size": len(workflow_cache),
        "workflow_cache_max_size": workflow_cache.maxsize,
        "workflow_cache_ttl": workflow_cache.ttl
    }


@router.post("/cache/clear")
async def clear_chat_cache():
    chat_cache.clear()
    return {"status": "success", "message": "Chat cache cleared"}