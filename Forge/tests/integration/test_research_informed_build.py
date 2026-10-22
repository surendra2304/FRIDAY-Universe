"""
Integration Test: End-to-End Research-Informed Build Flow.
Validates: Unfamiliar Tech Goal -> IntelX Research Submission -> Context Injection -> Verification Passes.
"""

import tempfile
from pathlib import Path

import pytest

from app.integrations.intelx_client import get_intelx_client
from app.monitoring.production_monitor import production_monitor
from app.verification.advanced_battery import AdvancedVerificationEngine


@pytest.fixture
def complex_workspace():
    """Create a temporary workspace for a research-informed real-time WebSocket service."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        # Pre-synthesize clean researched code matching IntelX recommendations
        service_py = """
import asyncio
from typing import Dict, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

app = FastAPI(title="Researched WebSocket Chat Service")

class MessagePayload(BaseModel):
    user: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

class ResearchedConnectionManager:
    # Research Finding [S:201]: Stateful connection tracking with disconnect idempotency
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ResearchedConnectionManager()

@app.websocket("/ws/chat")
async def chat_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            payload = MessagePayload(**data)
            await manager.broadcast({"user": payload.user, "content": payload.content})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
"""
        (ws / "main.py").write_text(service_py, encoding="utf-8")

        # Tests
        test_py = """
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_app_initialization():
    assert app.title == "Researched WebSocket Chat Service"
"""
        (ws / "test_main.py").write_text(test_py, encoding="utf-8")
        (ws / "requirements.txt").write_text(
            "fastapi>=0.110.0\npydantic>=2.6.0\npytest>=8.0.0\n", encoding="utf-8"
        )

        yield ws


@pytest.mark.asyncio
async def test_research_informed_build_flow(complex_workspace: Path):
    """
    Test complete flow:
    1. Unfamiliar goal detected (WebSockets + Redis).
    2. IntelX client queried for technical research.
    3. Research context formatted with citations.
    4. Code verification passes with security manifest.
    """
    goal = "Build a real-time chat service using WebSockets and Redis caching"

    intelx = get_intelx_client()
    detected_techs = intelx.detect_unfamiliar_technologies(goal)

    assert "websockets" in detected_techs
    assert "redis" in detected_techs

    # Perform technical research
    research_results = []
    for tech in detected_techs:
        res = await intelx.research_technology(tech, goal_context=goal)
        research_results.append(res)
        production_monitor.record_intelx_query()

    assert len(research_results) == 2
    assert any(r.technology == "websockets" for r in research_results)
    assert any(r.technology == "redis" for r in research_results)

    # Format research context for generation prompt
    prompt_context = intelx.format_research_context_for_prompt(research_results)
    assert "INTELX TECHNICAL RESEARCH FINDINGS" in prompt_context
    assert "[S:201]" in prompt_context or "WEBSOCKETS" in prompt_context
    assert "[S:301]" in prompt_context or "REDIS" in prompt_context

    production_monitor.record_research_informed_build()

    # Run verification battery
    manifest = AdvancedVerificationEngine.run_full_battery(complex_workspace)
    assert (complex_workspace / "verification_manifest.json").exists()
    assert manifest.failed_checks == 0
