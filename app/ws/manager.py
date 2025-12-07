from typing import Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        for ws in list(self.active_connections):
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(ws)


manager = ConnectionManager()