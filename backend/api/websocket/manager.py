from fastapi import WebSocket
from typing import List, Dict, Any


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: Dict[str, Any], websocket: WebSocket = None):
        if websocket:
            await websocket.send_json(message)
        else:
            for connection in self.active_connections:
                await connection.send_json(message)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            await connection.send_json(message)