"""TASK-ORCH-003 — fleet supervision and autonomy-boundary guard tests.

These lock the honesty contracts the autonomy audit (docs/autonomy/
AUTONOMY_AUDIT_2026-11-10.md) depends on before ANY autonomy claim:

1. The supervision loop reports a failed poll (``last_error``) while keeping
   the last good snapshot, and keeps polling instead of dying silently.
2. A successful poll refreshes the snapshot with a timestamp.
3. Autonomy is runtime-only: flipping it on does not survive a settings
   rebuild (simulated restart), so a rebooted FRIDAY is never accidentally
   autonomous.
4. The controller's public status tells the truth about what authorization
   still permits (no autonomy theatre).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


@pytest.fixture()
def server(monkeypatch):
    """Import the API server with its background loops neutral to this suite."""
    from friday.api import server as srv

    # Never let a real loop spawn during these tests.
    monkeypatch.setattr(srv, "FLEET_SUPERVISION_INTERVAL_SECONDS", 0)
    return srv


class _FakeStatus:
    def __init__(self, name: str, ok: bool) -> None:
        self.agent = name
        self.ok = ok

    def __dict__(self):  # parity with AgentStatus dataclass usage in the loop
        return {"agent": self.agent, "ok": self.ok}


def _drive_loop(server, monkeypatch, *, poll_results, max_cycles=3):
    """Run _fleet_supervision_loop for a fixed number of cycles, then cancel it."""
    calls = {"n": 0}

    async def fake_get_all_statuses(force_refresh=False):
        idx = calls["n"]
        calls["n"] += 1
        if idx >= len(poll_results):
            raise asyncio.CancelledError
        result = poll_results[idx]
        if isinstance(result, Exception):
            raise result
        return result

    sleeps = {"n": 0}

    async def fake_sleep(_seconds):
        sleeps["n"] += 1
        if sleeps["n"] >= max_cycles:
            raise asyncio.CancelledError

    monkeypatch.setattr(server.fleet_client, "get_all_statuses", fake_get_all_statuses)
    monkeypatch.setattr(server.asyncio, "sleep", fake_sleep)
    try:
        asyncio.run(server._fleet_supervision_loop())
    except asyncio.CancelledError:
        pass  # the intended stop mechanism
    return calls["n"]


class TestSupervisionLoopHonesty:
    def test_failed_poll_sets_last_error_and_keeps_last_snapshot(self, server, monkeypatch):
        state = server.fleet_supervision_state
        state["last_error"] = None
        state["last_completed_at"] = "2026-11-10T00:00:00+00:00"
        state["agents"] = [{"agent": "INTELX", "ok": True}]  # previous good snapshot

        _drive_loop(
            server, monkeypatch,
            poll_results=[RuntimeError("fleet unreachable")],
            max_cycles=1,
        )

        assert state["last_error"] == "RuntimeError"
        # The failed poll did NOT clear the previous snapshot or timestamp…
        assert state["agents"] == [{"agent": "INTELX", "ok": True}]
        assert state["last_completed_at"] == "2026-11-10T00:00:00+00:00"
        # …and the loop stopped cleanly (running flag restored).
        assert state["running"] is False

    def test_successful_poll_refreshes_snapshot_and_clears_error(self, server, monkeypatch):
        state = server.fleet_supervision_state
        state["last_error"] = "RuntimeError"
        state["agents"] = []

        _drive_loop(
            server, monkeypatch,
            poll_results=[[SimpleNamespace(agent="FRIDAY", ok=True), SimpleNamespace(agent="MEMORA", ok=True)]],
            max_cycles=1,
        )

        assert state["last_error"] is None
        assert state["last_completed_at"] is not None
        assert [a["agent"] for a in state["agents"]] == ["FRIDAY", "MEMORA"]

    def test_loop_survives_a_failed_cycle_and_polls_again(self, server, monkeypatch):
        """A crash in cycle 1 must not prevent cycle 2 from succeeding."""
        state = server.fleet_supervision_state
        state["last_error"] = None

        calls = _drive_loop(
            server, monkeypatch,
            poll_results=[
                RuntimeError("first poll dies"),
                [SimpleNamespace(agent="FRIDAY", ok=True)],
            ],
            max_cycles=2,
        )
        assert calls == 2  # the loop actually polled twice
        assert state["last_error"] is None  # second poll cleared it
        assert state["agents"], "snapshot from the second poll must be present"

    def test_loop_marks_running_while_alive(self, server, monkeypatch):
        state = server.fleet_supervision_state
        seen_while_running = {}

        original = server._fleet_supervision_loop

        async def probe_then_cancel():
            # Observe the flag from inside the loop, then end it.
            seen_while_running["running"] = state["running"]
            raise asyncio.CancelledError

        # Drive one probe cycle: start the real loop but cancel on first sleep.
        async def fake_sleep(_s):
            seen_while_running["running"] = state["running"]
            raise asyncio.CancelledError

        monkeypatch.setattr(server.asyncio, "sleep", fake_sleep)
        monkeypatch.setattr(
            server.fleet_client, "get_all_statuses",
            lambda force_refresh=False: _async_return([]),
        )
        try:
            asyncio.run(server._fleet_supervision_loop())
        except asyncio.CancelledError:
            pass
        assert seen_while_running.get("running") is True
        assert state["running"] is False  # finally-block restored it


def _async_return(value):
    async def _coro():
        return value
    return _coro()


class TestAutonomyIsRuntimeOnly:
    def _controller(self):
        from friday.autonomous.controller import AutonomousController
        return AutonomousController()

    def test_enabling_autonomy_does_not_survive_a_settings_rebuild(self, monkeypatch, tmp_path):
        """Simulate a process restart: a fresh Settings must default autonomous_mode OFF."""
        from friday.core import config

        controller = self._controller()

        # Owner flips autonomy on at runtime…
        controller.enabled = True
        assert controller.is_autonomous() is True
        assert config.get_settings().autonomous_mode is True

        # …the process restarts (cache cleared = fresh Settings)…
        config.get_settings(reload=True)
        # …and autonomy is OFF again unless the owner re-enables it.
        assert config.get_settings().autonomous_mode is False, (
            "autonomous_mode must be runtime-only: a restarted FRIDAY must never "
            "inherit a flipped-on autonomy flag from a previous process"
        )
        controller.enabled = False  # leave the shared test state clean

    def test_status_reports_runtime_only_persistence(self, monkeypatch):
        controller = self._controller()
        controller.enabled = False
        status = controller.get_status()
        assert status["autonomous_mode_persistence"] == "runtime_only"
        assert status["autonomous_mode"] is False
        # No autonomy theatre: the status never claims more than authorization permits.
        assert status["sensitive_actions_auto_approved"] is False

    def test_toggle_flips_and_reports(self, monkeypatch):
        controller = self._controller()
        controller.enabled = False
        assert controller.toggle() is True  # False -> True
        assert controller.is_autonomous() is True
        assert controller.toggle(False) is False
        assert controller.is_autonomous() is False


class TestControllerHistoryDurability:
    def test_action_history_survives_controller_reinstantiation(self, tmp_path, monkeypatch):
        """The audit trail is disk-backed; a new controller instance reloads it."""
        import json
        from pathlib import Path

        from friday.autonomous.controller import AutonomousController

        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps({
            "actions": [{
                "timestamp": "2026-11-10T00:00:00Z", "action_type": "test",
                "target": "INTELX", "directive": "drill", "result": "ok",
                "success": True, "details": {},
            }],
            "agent_activity": {"intelx": {"last": "drill"}},
        }))

        monkeypatch.setenv("FRIDAY_ACTION_HISTORY", str(history_file))
        # Fresh controller instance reads the persisted history…
        controller = AutonomousController()
        controller._history_path = Path(str(history_file))
        # The singleton may carry history from earlier tests; isolate to the file.
        controller.action_history = []
        controller._agent_activity = {}
        controller._load_history()
        assert len(controller.action_history) == 1
        assert controller.action_history[0].target == "INTELX"
        assert controller._agent_activity.get("intelx") == {"last": "drill"}
        assert controller.get_status()["history_count"] == 1
