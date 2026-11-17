"""Tests for TASK-FRD-023 — the autonomous daemon is armed at boot.

The goal-execution daemon (friday/autonomous/daemon.py) had no startup
hook: nothing in FRIDAY's boot sequence called ``start()``, and its only
callers were the manual ``POST /api/autonomous/toggle`` endpoint
(runtime-only, lost at every restart) and goal submission. The owner's
standing flag ``FRIDAY_AUTONOMOUS_MODE=true`` was set in production but
read only by status/authorization surfaces, never to start the daemon —
so the daemon did not execute a single loop iteration between
2026-11-10 and the diagnosis on 2026-11-17 (its persistence file's mtime
is the witness), while looking exactly like an armed-but-idle daemon.

These tests pin the fix:

* the lifespan starts the daemon on boot when ``settings.autonomous_mode``
  is true, and does not start it when the flag is off;
* shutdown stops it cleanly;
* the running loop emits a periodic INFO heartbeat, so "alive and idle"
  is provable from the journal instead of only from a file mtime.

The lifespan tests drive the REAL lifespan with its other background
loops replaced by sleepers — the daemon wiring is what is under test,
not the fleet loops.
"""

from __future__ import annotations

import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from friday.api import server
from friday.autonomous.daemon import AutonomousDaemon

SERVER = Path(__file__).resolve().parents[1] / "src" / "friday" / "api" / "server.py"

_LOOP_FACTORIES = (
    "_fleet_supervision_loop",
    "_memora_event_loop",
    "_reflex_loop",
    "_configure_memory_mirror",
    "_nightly_consolidation_loop",
    "_proactive_followup_loop",
    "_daily_report_loop",
    "_mission_execution_loop",
    "_agent_watch_loop",
    "_ensure_history_hydrated",
    "_stratex_watch_loop",
    "_intelx_watch_loop",
)


async def _sleeper() -> None:
    await asyncio.sleep(3600)


async def _aclose() -> None:
    return None


class _FakeDaemon:
    def __init__(self) -> None:
        self.starts = 0
        self.stops = 0

    async def start(self) -> None:
        self.starts += 1

    async def stop(self) -> None:
        self.stops += 1


def _stub_lifespan_surroundings(monkeypatch: pytest.MonkeyPatch, flag_on: bool) -> _FakeDaemon:
    fake = _FakeDaemon()
    monkeypatch.setattr(server, "autonomous_daemon", fake)
    monkeypatch.setattr(
        server, "get_settings", lambda: SimpleNamespace(autonomous_mode=flag_on)
    )
    monkeypatch.setattr(
        server, "validate_runtime_environment", lambda fail_fast=False: None
    )
    for name in _LOOP_FACTORIES:
        monkeypatch.setattr(server, name, _sleeper)
    monkeypatch.setattr(server, "repair_loop", SimpleNamespace(run_forever=_sleeper))
    monkeypatch.setattr(server, "fleet_client", SimpleNamespace(aclose=_aclose))

    from friday.proactive import telegram_gateway as tg_module
    from friday.proactive import whatsapp_gateway as wg_module

    gateway = SimpleNamespace(set_brain=lambda f: None, start=lambda: None, stop=lambda: None)
    monkeypatch.setattr(tg_module, "telegram_gateway", gateway)
    monkeypatch.setattr(wg_module, "whatsapp_gateway", gateway)
    return fake


@pytest.mark.asyncio
async def test_lifespan_starts_daemon_when_autonomous_mode_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag on: the daemon is started at boot and stopped at shutdown."""
    fake = _stub_lifespan_surroundings(monkeypatch, flag_on=True)

    async with server.lifespan(server.app):
        assert fake.starts == 1, "lifespan did not start the autonomous daemon"
        assert fake.stops == 0
    assert fake.stops == 1, "shutdown did not stop the autonomous daemon"


@pytest.mark.asyncio
async def test_lifespan_does_not_start_daemon_when_autonomous_mode_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flag off: boot must not arm the daemon (the toggle stays the only
    runtime arming path, exactly as before this fix)."""
    fake = _stub_lifespan_surroundings(monkeypatch, flag_on=False)

    async with server.lifespan(server.app):
        assert fake.starts == 0


def test_lifespan_gates_daemon_start_on_the_owner_flag() -> None:
    """The start call must sit under the settings.autonomous_mode check —
    an unconditional start would arm the daemon for owners who never
    opted in (the flag defaults to False)."""
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    lifespan = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "lifespan"
    )

    gated_start = False
    stop_called = False
    for node in ast.walk(lifespan):
        if isinstance(node, ast.If) and "autonomous_mode" in ast.unparse(node.test):
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "start"
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "autonomous_daemon"
                ):
                    gated_start = True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "stop"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "autonomous_daemon"
        ):
            stop_called = True

    assert gated_start, "lifespan never starts autonomous_daemon under the flag"
    assert stop_called, "lifespan never stops autonomous_daemon on shutdown"


def _idle_daemon(tmp_path: Path) -> AutonomousDaemon:
    """A daemon with an empty queue and scratch persistence, so the test
    can never pick up a real queued goal."""
    daemon = AutonomousDaemon()
    daemon._goal_queue.clear()
    daemon._running_goals.clear()
    daemon._completed_goals.clear()
    daemon._persistence_path = tmp_path / "autonomous_goals.json"
    return daemon


@pytest.mark.asyncio
async def test_daemon_start_stop_lifecycle(tmp_path: Path) -> None:
    daemon = _idle_daemon(tmp_path)
    assert not daemon.is_running
    await daemon.start()
    assert daemon.is_running
    await daemon.stop()
    assert not daemon.is_running


@pytest.mark.asyncio
async def test_daemon_emits_heartbeat_while_idle(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An armed-but-idle daemon must say so in the journal, periodically.

    Without the heartbeat, the loop logs nothing per cycle and a healthy
    idle daemon is indistinguishable from one that was never started —
    the observability hole that hid the 2026-11-10 → 2026-11-17 outage.
    """
    daemon = _idle_daemon(tmp_path)
    daemon._heartbeat_interval_s = 0.05
    with caplog.at_level(logging.INFO, logger="friday.autonomous.daemon"):
        await daemon.start()
        # Each wake releases one loop iteration immediately; without this
        # the loop polls on its 5 s cadence and the test would crawl.
        for _ in range(40):
            daemon._wake.set()
            await asyncio.sleep(0.01)
        await daemon.stop()

    heartbeats = [
        r.getMessage() for r in caplog.records if "Autonomous daemon alive" in r.getMessage()
    ]
    assert len(heartbeats) >= 2, f"expected periodic heartbeats, got {heartbeats}"
    assert any("0 queued, 0 running" in m for m in heartbeats)
