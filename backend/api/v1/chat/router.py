from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
from app.dependencies import get_agent_registry
from api.websocket.manager import WebSocketManager

router = APIRouter()


class ChatMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: float


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    registry=Depends(get_agent_registry),
    ws_manager: WebSocketManager = Depends()
):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            
            await ws_manager.send_message(
                {"type": "agent_status", "data": registry.get_all_agent_statuses()}
            )
            
            await ws_manager.send_message(
                {"type": "thinking", "data": {"agent": "knowledge", "status": "processing"}}
            )
            
            await ws_manager.send_message(
                {"type": "message", "data": {
                    "role": "assistant",
                    "content": "正在处理您的请求...",
                    "timestamp": data.get("timestamp", 0)
                }}
            )
            
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@router.post("/send")
async def send_message(
    message: Dict[str, Any],
    registry=Depends(get_agent_registry)
):
    user_input = message.get("content", "")
    
    from api.v1.workflow.router import execute_workflow, WorkflowInput
    result = await execute_workflow(
        WorkflowInput(user_input=user_input),
        registry
    )
    
    return {
        "response": result.final_result,
        "steps": result.steps,
        "executed_locally": result.executed_locally
    }