"""
Unit and WebSocket integration tests for real-time telemetry streaming.
"""

import pytest
from starlette.testclient import TestClient

from app.api.websocket import ws_manager
from app.core.config import get_settings
from app.main import app

_TEST_KEY = "forge_websocket_test_key_0123456789abcdef"


@pytest.fixture(autouse=True)
def configured_websocket_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_universe_api_key", _TEST_KEY)


def test_task_websocket_endpoint(configured_websocket_key):
    client = TestClient(app)
    task_id = "test_ws_task_100"

    with client.websocket_connect(f"/ws/tasks/{task_id}?api_key={_TEST_KEY}") as websocket:
        # Receive connected greeting
        data = websocket.receive_json()
        assert data["event"] == "connected"
        assert data["task_id"] == task_id

        # Send ping
        websocket.send_text("ping")
        resp = websocket.receive_text()
        assert resp == "pong"


def test_global_websocket_endpoint(configured_websocket_key):
    client = TestClient(app)

    with client.websocket_connect(f"/ws/tasks?api_key={_TEST_KEY}") as websocket:
        data = websocket.receive_json()
        assert data["event"] == "connected"

        websocket.send_text("ping")
        resp = websocket.receive_text()
        assert resp == "pong"


@pytest.mark.asyncio
async def test_websocket_broadcast():
    task_id = "test_ws_broadcast_task"
    # Ensure manager handles empty or disconnected clients without error
    await ws_manager.broadcast_to_task(task_id, {"event": "progress", "progress": 50})
    await ws_manager.broadcast_global({"event": "task.created", "task_id": task_id})
