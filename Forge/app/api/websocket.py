"""
WebSocket Streaming Subsystem for Project FORGE.
Provides authenticated real-time telemetry streaming for task-specific and global events.
"""

import hmac
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("api.websocket")
ws_router = APIRouter()


class WebSocketConnectionManager:
    """Manages active WebSocket subscriptions and multiplexed broadcasting."""

    def __init__(self):
        # task_id -> list of WebSockets
        self.task_subscribers: dict[str, list[WebSocket]] = defaultdict(list)
        # Global subscribers listening to all events
        self.global_subscribers: list[WebSocket] = []

    async def connect_task(self, websocket: WebSocket, task_id: str):
        """Accept WebSocket and subscribe to a specific task stream."""
        await websocket.accept()
        self.task_subscribers[task_id].append(websocket)
        logger.info(f"WebSocket client connected to task stream: {task_id}")

    async def connect_global(self, websocket: WebSocket):
        """Accept WebSocket and subscribe to global task stream."""
        await websocket.accept()
        self.global_subscribers.append(websocket)
        logger.info("WebSocket client connected to global task stream.")

    def disconnect_task(self, websocket: WebSocket, task_id: str):
        """Unsubscribe WebSocket from task stream."""
        if websocket in self.task_subscribers[task_id]:
            self.task_subscribers[task_id].remove(websocket)
            logger.info(f"WebSocket client disconnected from task stream: {task_id}")

    def disconnect_global(self, websocket: WebSocket):
        """Unsubscribe WebSocket from global task stream."""
        if websocket in self.global_subscribers:
            self.global_subscribers.remove(websocket)
            logger.info("WebSocket client disconnected from global task stream.")

    async def broadcast_to_task(self, task_id: str, message: dict[str, Any]):
        """Send message to all subscribers of a specific task."""
        subscribers = list(self.task_subscribers.get(task_id, []))
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect_task(ws, task_id)

    async def broadcast_global(self, message: dict[str, Any]):
        """Send message to all global subscribers."""
        subscribers = list(self.global_subscribers)
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect_global(ws)


ws_manager = WebSocketConnectionManager()


def verify_ws_auth(websocket: WebSocket, api_key: str | None) -> bool:
    """Verify WebSocket authentication via query parameter or header."""
    settings = get_settings()
    valid_keys = {settings.ai_universe_api_key}
    # Add from production settings or api key manager
    try:
        from app.security.api_keys import api_key_manager

        valid_keys.update(api_key_manager.valid_keys)
    except Exception:
        pass

    valid_keys = {k for k in valid_keys if k}

    # No keys configured at all: only allow when the deployment explicitly does
    # not require authentication. This used to return True whenever the key set
    # was empty regardless of policy, i.e. it failed OPEN for any deployment that
    # forgot to set a key.
    if not valid_keys:
        from app.config.production import production_settings

        return not production_settings.api_key_required

    active_keys = [k for k in valid_keys if isinstance(k, str) and k]

    # Check query param
    if api_key and any(hmac.compare_digest(api_key.encode(), key.encode()) for key in active_keys):
        return True

    # Check headers
    header_key = websocket.headers.get("x-friday-api-key") or websocket.headers.get("x-api-key")
    if header_key and any(hmac.compare_digest(header_key.encode(), key.encode()) for key in active_keys):
        return True

    return False


@ws_router.websocket("/ws/tasks/{task_id}")
async def task_websocket_endpoint(
    websocket: WebSocket,
    task_id: str,
    api_key: str | None = Query(default=None),
):
    """Real-time event stream for a specific task."""
    if not verify_ws_auth(websocket, api_key):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    await ws_manager.connect_task(websocket, task_id)
    try:
        # Send initial connected greeting
        await websocket.send_json(
            {
                "event": "connected",
                "task_id": task_id,
                "message": f"Subscribed to real-time telemetry for task {task_id}",
            }
        )
        while True:
            # Keep connection open and receive client heartbeats/pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_task(websocket, task_id)
    except Exception as e:
        logger.debug(f"WebSocket connection error for task {task_id}: {e}")
        ws_manager.disconnect_task(websocket, task_id)


@ws_router.websocket("/ws/tasks")
async def global_tasks_websocket_endpoint(
    websocket: WebSocket,
    api_key: str | None = Query(default=None),
):
    """Real-time broadcast stream for all task lifecycle events."""
    if not verify_ws_auth(websocket, api_key):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    await ws_manager.connect_global(websocket)
    try:
        await websocket.send_json(
            {
                "event": "connected",
                "message": "Subscribed to global task event broadcast stream",
            }
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_global(websocket)
    except Exception as e:
        logger.debug(f"Global WebSocket connection error: {e}")
        ws_manager.disconnect_global(websocket)
