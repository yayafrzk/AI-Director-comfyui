from typing import Any

from fastapi import WebSocket

_connections: set[WebSocket] = set()


async def connect_generation_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    _connections.add(websocket)


def disconnect_generation_socket(websocket: WebSocket) -> None:
    _connections.discard(websocket)


async def broadcast_generation_event(event: dict[str, Any]) -> None:
    for websocket in tuple(_connections):
        try:
            await websocket.send_json(event)
        except Exception:
            _connections.discard(websocket)
