"""TASK-IG-WEB-03 follow-up regression: /api/memory/browser gate alignment.

The Memory Galaxy layer fetches GET /api/memory/browser exactly the way the
rest of the dashboard fetches its read-only surfaces: no API key, no control
token (FRIDAY/ui/lib/wire.ts `fetchMemories` -> `requestJson`, which sends
only a Content-Type header). The endpoint was gated by
`_require_control_access`, so a remote browser session got 401 and the layer
always landed in its "Memora didn't answer" state, while every sibling
read-only UI endpoint (/api/agents/live, /api/agents/usage,
/api/owner/preferences, /api/voice/diagnostics) is gated by
`_require_origin_gate` only. The TASK-IG-WEB-03 board entry pre-prescribed
the fix: align this gate with the siblings.

Contract locked here:
- a same-origin read in the exact UI shape (no credentials) returns 200 with
  the MemoryBrowserSnapshot payload (status / count / memories / summary);
- a forged Origin is refused 403 and Origin "null" is refused 403 — exactly
  as the siblings behave;
- the route is wired to `_require_origin_gate` and NOT
  `_require_control_access`, and a control-gated surface (/api/doctor) keeps
  its gate — no other endpoint's gating moves.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
_CORE_SRC = REPO / "FRIDAY" / "apps" / "core" / "src"
for _p in (str(_CORE_SRC), str(REPO), str(REPO / "FRIDAY" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import friday.memory.memora_client as memora_module  # noqa: E402
from friday.api import server  # noqa: E402
from friday.api.server import app  # noqa: E402

ATTACKER_ORIGIN = "https://attacker.example"

_ROWS = [
    {
        "id": "mem_1",
        "content_text": "my favorite chai is masala chai",
        "provenance": {"category": "preference"},
        "created_at": "2026-11-13 10:00:00",
    },
    {
        "id": "mem_2",
        "content_text": "GOAL (active): double the demo account",
        "provenance": {"category": "goal"},
        "created_at": "2026-11-13 10:05:00",
    },
]


class _FakeMemora:
    """Stand-in for the live Memora client (recent_memories only)."""

    def recent_memories(self, agent_name, limit=100, since=""):
        assert agent_name == "friday"
        return list(_ROWS)[:limit]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("FRIDAY_API_KEY", raising=False)
    monkeypatch.delenv("FRIDAY_UNIVERSE_API_KEY", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(memora_module, "memora_client", _FakeMemora(), raising=False)
    with TestClient(app) as test_client:
        yield test_client


def _route_dependency_calls(path: str) -> set:
    """The gate callables wired into a route's dependency tree."""
    calls = set()
    for route in app.routes:
        if getattr(route, "path", None) != path:
            continue
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dependency in dependant.dependencies:
            if dependency.call is not None:
                calls.add(dependency.call)
    return calls


class TestMemoryBrowserGate:
    def test_ui_shape_read_succeeds_without_credentials(self, client: TestClient) -> None:
        # Exactly what the shipped UI sends: same-origin GET, no key header,
        # no control token header, no Authorization.
        response = client.get(
            "/api/memory/browser",
            headers={"Origin": "http://testserver", "Host": "testserver"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["count"] == 2
        assert len(body["memories"]) == 2
        for memory in body["memories"]:
            for field in ("id", "text", "tier", "score", "category", "created_at", "active_goal"):
                assert field in memory
        assert any("masala chai" in m["text"] for m in body["memories"])
        assert body["summary"]["active_goals"] == 1
        assert set(body["summary"]["tiers"]) == {"pinned", "normal", "trivial", "other"}

    def test_no_origin_read_succeeds_like_siblings(self, client: TestClient) -> None:
        # Non-browser callers carry no Origin; the sibling surfaces answer
        # them (the origin gate judges them allowed) and so must this one.
        response = client.get("/api/memory/browser")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_forged_origin_refused(self, client: TestClient) -> None:
        response = client.get(
            "/api/memory/browser", headers={"Origin": ATTACKER_ORIGIN}
        )
        assert response.status_code == 403

    def test_null_origin_refused(self, client: TestClient) -> None:
        # "null" is what sandboxed iframes / data: / file:// pages send.
        response = client.get("/api/memory/browser", headers={"Origin": "null"})
        assert response.status_code == 403

    def test_route_wired_to_origin_gate_not_control_gate(self) -> None:
        calls = _route_dependency_calls("/api/memory/browser")
        assert server._require_origin_gate in calls
        assert server._require_control_access not in calls

    def test_other_endpoints_gating_unchanged(self) -> None:
        # A control surface keeps the control gate...
        doctor_calls = _route_dependency_calls("/api/doctor")
        assert server._require_control_access in doctor_calls
        assert server._require_origin_gate not in doctor_calls
        # ...and a sibling keeps the origin gate.
        live_calls = _route_dependency_calls("/api/agents/live")
        assert server._require_origin_gate in live_calls
        assert server._require_control_access not in live_calls


if __name__ == "__main__":  # manual evidence run
    raise SystemExit(pytest.main([__file__, "-q"]))
