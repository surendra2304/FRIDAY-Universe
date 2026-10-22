"""
Unit tests for Web Dashboard route.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_web_dashboard_html():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/dashboard")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "FORGE" in res.text
        assert "task-list" in res.text
        assert "/api/analytics/summary" in res.text
        assert "/timeline" in res.text
        assert "No persisted timeline events are available" in res.text
        assert "Connected to log stream" not in res.text
        assert "Implementation</div>" not in res.text
