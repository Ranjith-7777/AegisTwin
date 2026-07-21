from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket) -> None:
    manager = websocket.app.state.connection_manager
    connection_id = await manager.connect(websocket)
    logger.info("WebSocket connected connection_id=%s", connection_id)
    await manager.send(
        connection_id,
        {
            "type": "connection.ack",
            "payload": {
                "connection_id": connection_id,
                "connected": True,
                "simulation_only": True,
            },
        },
    )
    try:
        while True:
            try:
                message: Any = await websocket.receive_json()
            except json.JSONDecodeError:
                await manager.send(
                    connection_id,
                    {
                        "type": "error",
                        "payload": {
                            "error_code": "MALFORMED_JSON",
                            "message": "The WebSocket message must be valid JSON.",
                        },
                    },
                )
                continue
            if not isinstance(message, dict) or message.get("type") != "ping":
                await manager.send(
                    connection_id,
                    {
                        "type": "error",
                        "payload": {
                            "error_code": "UNSUPPORTED_MESSAGE",
                            "message": "Only the 'ping' message type is supported.",
                        },
                    },
                )
                continue
            await manager.send(
                connection_id,
                {"type": "pong", "payload": {"simulation_only": True}},
            )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected connection_id=%s", connection_id)
    finally:
        manager.disconnect(connection_id)
