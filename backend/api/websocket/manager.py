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
            for conn_id, websocket in list(self.active_connections.items()):
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {conn_id}: {e}")

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

    def get_connection_count(self) -> int:
        return len(self.active_connections)
