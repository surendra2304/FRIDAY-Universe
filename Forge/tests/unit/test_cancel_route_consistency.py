"""
Regression test for a route-shadowing bug found via live adversarial testing.

`app/api/tasks.py` (tasks_router) and `app/api/routes.py` (api_router) both
registered a handler for the logical path `/tasks/{task_id}/cancel`.
Depending on URL prefix, FastAPI's registration-order route resolution made
either the "rich" tasks.py handler (progress-tracker close-out, WebSocket
broadcast, webhook dispatch) or the "thin" routes.py handler (state
transition only) win:

- `/api/tasks/{id}/cancel`    -> tasks.py's rich handler (intended)
- `/api/v1/tasks/{id}/cancel` -> routes.py's thin handler (bug: silently
  skipped webhook/WebSocket notification)

Both routers now call the single shared `execute_task_cancellation()`
implementation, so every mount point behaves identically. This test asserts
that equivalence directly rather than re-deriving FastAPI's route-resolution
order, so it would fail again if the two handlers ever drift apart.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.memory.db import DatabaseManager


async def _submit_task(client: AsyncClient, goal: str) -> str:
    res = await client.post("/api/tasks", json={"goal": goal})
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.asyncio
async def test_v1_and_plain_cancel_routes_both_fire_full_side_effects(
    isolated_db_manager: DatabaseManager,
):
    await isolated_db_manager.init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        task_a = await _submit_task(client, "Cancel-route-consistency probe A")
        task_b = await _submit_task(client, "Cancel-route-consistency probe B")

        resp_plain = await client.post(
            f"/api/tasks/{task_a}/cancel", json={"reason": "plain path"}
        )
        resp_v1 = await client.post(
            f"/api/v1/tasks/{task_b}/cancel", json={"reason": "v1 path"}
        )

        assert resp_plain.status_code == 200
        assert resp_v1.status_code == 200

        body_plain = resp_plain.json()
        body_v1 = resp_v1.json()

        # Both routes must report the same current_state...
        assert body_plain["current_state"] == "CANCELLED"
        assert body_v1["current_state"] == "CANCELLED"

        # ...and -- the actual regression -- both must use the rich message
        # format that only the tasks.py implementation produces (it embeds
        # the reason; the old routes.py handler always said just "Task
        # cancelled successfully" with no reason).
        assert body_plain["message"] == "Task cancelled successfully: plain path"
        assert body_v1["message"] == "Task cancelled successfully: v1 path"
