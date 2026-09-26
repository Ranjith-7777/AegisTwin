from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import WebSocket


@dataclass
class ConnectionManager:
    _connections: dict[str, WebSocket] = field(default_factory=dict)

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        connection_id = str(uuid4())
        self._connections[connection_id] = websocket
        return connection_id

    def disconnect(self, connection_id: str) -> None:
        self._connections.pop(connection_id, None)

    async def send(self, connection_id: str, message: dict[str, object]) -> None:
        websocket = self._connections.get(connection_id)
        if websocket is not None:
            await websocket.send_json(message)

    async def broadcast(self, message: dict[str, object]) -> None:
        for websocket in tuple(self._connections.values()):
            await websocket.send_json(message)
