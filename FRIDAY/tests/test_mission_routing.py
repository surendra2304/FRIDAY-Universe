"""Checklist G6/G12 — route-level contract: the mission fast-path in the REAL
_dispatch_command chain (Batch 5, ZAI Agent 2).

Locks the ordering lessons the E2E run surfaced:
- "run my missions now" must RUN (the list matcher also matches it — run
  wins by chain order);
- add/list phrasings are answered deterministically with mission metadata;
- the mission path never hijacks remember/recall, delegation, fleet-status
  or research requests (the neighbors in the chain).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture(scope="module")
def server():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "friday_server_under_test", str(REPO / "FRIDAY" / "src" / "friday" / "api" / "server.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import friday.proactive.mission_queue as mqm

    q = mqm.MissionQueue(str(tmp_path / "m" / "queue.json"))
    monkeypatch.setattr(mqm, "mission_queue", q)
    # the server module imports the singleton at call time via the module
    yield q


async def _dispatch(server, command: str):
    return await server._dispatch_command(command)


class TestMissionRoutingChain:
    @pytest.mark.asyncio
    async def test_add_mission_routes_to_queue(self, server, queue):
        result = await _dispatch(server, "add to tonight's missions: research the sky")
        assert result["metadata"].get("mission_queued") is True
        assert queue.pending()[0]["command"] == "research the sky"
        assert "Queued for tonight" in result["reply"]

    @pytest.mark.asyncio
    async def test_list_missions_routes_to_queue(self, server, queue):
        queue.add("check the fleet")
        result = await _dispatch(server, "show my missions")
        assert result["metadata"].get("mission_list") is True
        assert "check the fleet" in result["reply"]

    @pytest.mark.asyncio
    async def test_run_intent_wins_over_list_matcher(self, server, queue, monkeypatch):
        # "run my missions now" ALSO matches the list patterns; the chain
        # must run, not list (E2E lesson 2026-11-11).
        queue.add("hello task")
        executed: list[str] = []

        def fake_execute_pending(brain, **kw):
            executed.append("ran")
            return {"executed": 1, "completed": 1, "failed": 0, "skipped": 0,
                    "results": [{"id": "m_x", "command": "hello task", "status": "completed", "reply": "hi"}]}

        monkeypatch.setattr(queue, "execute_pending", fake_execute_pending)
        result = await _dispatch(server, "run my missions now")
        assert result["metadata"].get("mission_run") is True
        assert executed == ["ran"]
        assert "Ran 1 mission" in result["reply"]

    @pytest.mark.asyncio
    async def test_remember_not_hijacked_by_missions(self, server, queue):
        result = await _dispatch(server, "remember this: my favorite chai is masala chai")
        meta = result.get("metadata") or {}
        # The contract here is ROUTING: the remember path owns this message
        # (no mission metadata), whether or not the sandbox has a live store
        # (without one the reply is the honest "couldn't reach" line).
        assert not meta.get("mission_queued")
        assert meta.get("fast_path")
        # The remember path owns the message: the fact was extracted; whether
        # the store answered is reported honestly (memory_store: False in a
        # sandbox without Oracle, True with a live store).
        assert "fact" in meta and "memory_store" in meta

    @pytest.mark.asyncio
    async def test_delegation_not_hijacked(self, server, queue):
        result = await _dispatch(server, "assign a quick task to IntelX: one-line research note")
        meta = result.get("metadata") or {}
        assert not meta.get("mission_queued") and not meta.get("mission_list")

    @pytest.mark.asyncio
    async def test_fleet_status_not_hijacked(self, server, queue):
        result = await _dispatch(server, "how's the fleet doing right now")
        meta = result.get("metadata") or {}
        assert not meta.get("mission_queued") and not meta.get("mission_list")

    @pytest.mark.asyncio
    async def test_plain_chat_not_hijacked(self, server, queue):
        result = await _dispatch(server, "what is the time right now")
        meta = result.get("metadata") or {}
        assert not meta.get("mission_queued") and not meta.get("mission_list")
