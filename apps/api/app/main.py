from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.api.router import router as api_router
from app.services.generation_broadcast import connect_generation_socket, disconnect_generation_socket


app = FastAPI(title="AI Director API")
app.include_router(api_router)


@app.websocket("/ws/generation")
async def generation_websocket(websocket: WebSocket) -> None:
    await connect_generation_socket(websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        disconnect_generation_socket(websocket)
