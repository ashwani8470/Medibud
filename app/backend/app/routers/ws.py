import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Realtime WebSockets"])


@router.websocket("/ws/live")
async def live_updates_websocket(websocket: WebSocket):
    """
    Real-time push channel for hospital bed telemetry, doctor shifts, and booking holds.
    Clients connect once and receive instant JSON events without polling.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; accept client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"event": "pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
