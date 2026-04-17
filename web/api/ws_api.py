"""
WebSocket endpoint — /ws
Принимает подключение, авторизует через сессию, обрабатывает ping/pong.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from web.ws_manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Принять WebSocket соединение.
    Авторизация через сессию Starlette (SessionMiddleware).
    """
    # Проверяем авторизацию через сессию
    user_id = websocket.session.get("user_id") if hasattr(websocket, "session") else None
    if not user_id:
        await websocket.close(code=1008)  # Policy Violation
        return

    await manager.connect(websocket)
    try:
        while True:
            try:
                data = await websocket.receive_json()
                if isinstance(data, dict) and data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
