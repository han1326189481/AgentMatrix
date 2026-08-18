from typing import Dict, Any, List
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_counter = 0

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = f"conn_{self.connection_counter}"
        self.connection_counter += 1
        self.active_connections[connection_id] = websocket
        logger.info(f"WebSocket connection established: {connection_id}")
        return connection_id

    def disconnect(self, websocket: WebSocket) -> None:
        conn_id_to_remove = None
        for conn_id, conn in self.active_connections.items():
            if conn == websocket:
                conn_id_to_remove = conn_id
                break
        if conn_id_to_remove:
            del self.active_connections[conn_id_to_remove]
            logger.info(f"WebSocket connection disconnected: {conn_id_to_remove}")

    async def send_message(self, message: Dict[str, Any], connection_id: str = None) -> None:
        if connection_id:
            websocket = self.active_connections.get(connection_id)
            if websocket:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to {connection_id}: {e}")
        else:
            dead_connections = []
            for conn_id, websocket in list(self.active_connections.items()):
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {conn_id}: {e}")
                    dead_connections.append(conn_id)
            # 清理已断开的连接，避免后续广播重复报错
            for conn_id in dead_connections:
                self.active_connections.pop(conn_id, None)
                logger.info(f"WebSocket dead connection removed: {conn_id}")

    async def broadcast_agent_status(self, agent_statuses: Dict[str, Any]) -> None:
        message = {
            "type": "agent_status",
            "data": agent_statuses
        }
        await self.send_message(message)

    async def broadcast_workflow_step(self, step: Dict[str, Any]) -> None:
        message = {
            "type": "workflow_step",
            "data": step
        }
        await self.send_message(message)

    async def broadcast_final_result(self, result: Dict[str, Any]) -> None:
        message = {
            "type": "final_result",
            "data": result
        }
        await self.send_message(message)

    async def broadcast_vision_progress(self, progress: Dict[str, Any]) -> None:
        """V3.2: 推送视觉识别进度（前端用于更新缩略图弹窗的进度条）

        progress 结构:
        {
            "current": int,       # 当前第几张（0=切换模型中，1..total=识别中）
            "total": int,         # 总图片数
            "status": str,        # 状态描述（如"正在识别第 1/3 张图片..."）
            "phase": str,         # 阶段: "switching" | "recognizing" | "completed"
        }
        """
        message = {
            "type": "vision_progress",
            "data": progress
        }
        await self.send_message(message)

    async def broadcast_audit_progress(self, progress: Dict[str, Any]) -> None:
        """V3.3: 推送知识库质检进度（前端用于显示质检弹窗）

        progress 结构:
        {
            "phase": str,         # 阶段: "start" | "processing" | "completed" | "error"
            "current": int,       # 当前已处理数量
            "total": int,         # 总数量
            "message": str,       # 进度描述
            "stats": dict,        # 质检统计（filtered/replaced/removed/...）
            "timestamp": str,     # ISO 8601 时间戳
        }
        """
        message = {
            "type": "audit_progress",
            "data": progress
        }
        logger.info(
            f"[WebSocket] broadcast_audit_progress: phase={progress.get('phase')}, "
            f"current={progress.get('current')}/{progress.get('total')}, "
            f"connections={len(self.active_connections)}"
        )
        await self.send_message(message)

    async def broadcast_clarify_request(self, clarify_data: Dict[str, Any]) -> None:
        """V3.4: 推送抱怨澄清请求（前端用于显示澄清弹窗，让用户选择理解方向）

        clarify_data 结构:
        {
            "questions": [
                {
                    "id": "q1",
                    "question": "请问您真正想了解的是哪方面？",
                    "options": ["A: ...", "B: ..."]
                },
                ...
            ],
            "complaint_type": str,            # 抱怨类型
            "user_input_summary": str,        # 用户输入摘要（前80字）
            "timestamp": str                  # ISO 8601 时间戳
        }
        """
        message = {
            "type": "clarify_request",
            "data": clarify_data
        }
        logger.info(
            f"[WebSocket] broadcast_clarify_request: "
            f"questions={len(clarify_data.get('questions', []))}, "
            f"type={clarify_data.get('complaint_type')}, "
            f"connections={len(self.active_connections)}"
        )
        await self.send_message(message)

    def get_connection_count(self) -> int:
        return len(self.active_connections)

    async def broadcast_metrics_update(self, metrics: Dict[str, Any]) -> None:
        """V4.1: 推送实时指标更新（成本和缓存命中率）

        metrics 结构:
        {
            "timestamp": str,     # ISO 8601
            "cache": {
                "workflow_cache_hit_rate": float,
                "intent_cache_hit_rate": float,
                "overall_hit_rate": float,
            },
            "cost": {
                "estimated_cost": float,
                "estimated_savings": float,
                "savings_rate": float,
                "avg_cost_per_workflow": float,
                "total_cloud_tokens": int,
                "total_local_tokens": int,
                "workflow_count": int,
                "local_workflow_count": int,
                "cloud_workflow_count": int,
            },
        }
        """
        message = {
            "type": "metrics_update",
            "data": metrics
        }
        logger.info(
            f"[WebSocket] broadcast_metrics_update: "
            f"hit_rate={metrics.get('cache', {}).get('overall_hit_rate', 0):.1%}, "
            f"cost=¥{metrics.get('cost', {}).get('estimated_cost', 0):.6f}, "
            f"connections={len(self.active_connections)}"
        )
        await self.send_message(message)
