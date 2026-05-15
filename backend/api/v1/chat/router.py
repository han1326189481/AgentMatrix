from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, AsyncGenerator
from pydantic import BaseModel
from app.dependencies import get_agent_registry
from api.v1.workflow.router import execute_workflow, execute_workflow_stream, WorkflowInput, workflow_cache, SimpleCache
import json

router = APIRouter()

chat_cache = SimpleCache(maxsize=200, ttl=300)


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: float


class ChatRequest(BaseModel):
    content: str
    use_cloud: bool = False
    model_name: str = None


@router.post("/send")
async def send_message(
    request: ChatRequest,
    registry=Depends(get_agent_registry)
):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    
    cache_key = f"chat_{hash(request.content)}_{request.use_cloud}_{request.model_name}"
    
    if cache_key in chat_cache:
        return chat_cache[cache_key]
    
    try:
        # 如果指定了模型名称，使用配置好的模型
        if request.model_name:
            from core.llm.client import get_llm_client
            from config.manager import load_config
            import time
            import logging
            logger = logging.getLogger(__name__)
            
            start_time = time.time()
            
            config = load_config()
            models = config.get("models", [])
            model_config = None
            
            for m in models:
                if m.get("name") == request.model_name:
                    model_config = m
                    break
            
            if not model_config:
                raise HTTPException(status_code=400, detail=f"未找到模型: {request.model_name}")
            
            logger.info(f"[Chat] 使用配置模型: {model_config}")
            
            llm_client = get_llm_client()
            response_text = await llm_client.generate_by_config(
                request.content,
                model_config,
                system_prompt="你是一个专业、友好的AI助手。请直接回答用户的问题，提供准确、有帮助的信息。"
            )
            
            total_duration = (time.time() - start_time) * 1000
            
            response = {
                "response": response_text,
                "executed_locally": False,
                "complexity_score": 0.0,
                "total_duration": total_duration,
                "steps_count": 1,
                "mode": "model",
                "model_used": request.model_name
            }
            
            if len(response_text) < 5000:
                chat_cache[cache_key] = response
            
            return response
        # 云端模式：直接调用默认LLM
        elif request.use_cloud:
            from core.llm.client import get_llm_client
            import time
            import logging
            logger = logging.getLogger(__name__)
            
            start_time = time.time()
            
            llm_client = get_llm_client()
            
            # 使用运行时配置的 API Key
            from api.v1.config.router import _runtime_config
            runtime_api_key = _runtime_config.get("deepseek_api_key")
            if runtime_api_key:
                logger.info("[Chat] 使用运行时配置的 API Key")
                llm_client.deepseek_api_key = runtime_api_key
            else:
                logger.info("[Chat] 使用默认配置的 API Key")
            
            logger.info(f"[Chat] 开始云端调用，内容长度: {len(request.content)}")
            
            response_text = await llm_client.generate_cloud(
                request.content,
                system_prompt="你是一个专业、友好的AI助手。请直接回答用户的问题，提供准确、有帮助的信息。"
            )
            
            logger.info(f"[Chat] 云端调用完成，响应长度: {len(response_text) if response_text else 0}")
            
            total_duration = (time.time() - start_time) * 1000
            
            response = {
                "response": response_text,
                "executed_locally": False,
                "complexity_score": 0.0,
                "total_duration": total_duration,
                "steps_count": 1,
                "mode": "cloud"
            }
            
            if len(response_text) < 5000:
                chat_cache[cache_key] = response
            
            return response
        
        # 本地模式：使用完整的工作流
        result = await execute_workflow(
            WorkflowInput(user_input=request.content),
            registry
        )
        
        response = {
            "response": result.final_result,
            "executed_locally": result.executed_locally,
            "complexity_score": result.complexity_score,
            "total_duration": result.total_duration_seconds,
            "steps_count": len(result.steps),
            "mode": "local"
        }
        
        if result.executed_locally and len(result.final_result) < 5000:
            chat_cache[cache_key] = response
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")


@router.post("/send/stream")
async def send_message_stream(
    request: ChatRequest,
    registry=Depends(get_agent_registry)
):
    """流式发送消息，实时返回结果"""
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        async for chunk in execute_workflow_stream(
            WorkflowInput(user_input=request.content),
            registry
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/event-stream")


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
    return {"status": "ok", "service": "chat", "cache_size": chat_cache.size}


@router.get("/cache/stats")
async def get_chat_cache_stats():
    return {
        "chat_cache_size": chat_cache.size,
        "chat_cache_max_size": chat_cache.maxsize,
        "chat_cache_ttl": chat_cache.ttl,
        "workflow_cache_size": workflow_cache.size,
        "workflow_cache_max_size": workflow_cache.maxsize,
        "workflow_cache_ttl": workflow_cache.ttl
    }


@router.post("/cache/clear")
async def clear_chat_cache():
    chat_cache.clear()
    return {"status": "success", "message": "Chat cache cleared"}