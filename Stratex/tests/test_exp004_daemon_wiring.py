"""TASK-STR-EXP-004 — daemon wiring for the self-experiment loop.

EXP-001 shipped run_forever()/start_if_enabled() deliberately
unhooked. This suite pins the activation wiring's hard requirement:

(b) INERT WHEN OFF: with STRATEX_SELF_EXPERIMENTS unset or any value
    other than exactly "on", the wiring starts nothing — no loop is
    constructed (start_if_enabled is never called), no thread is
    created, no data directory or counter file appears, and the
    daemon hook returns without touching the wiring at all.
(c) LIVE WHEN ON: with the switch exactly "on", the wiring builds
    the loop through start_if_enabled WITH the daemon-activity
    probe, drives run_forever on a thread, and stops cleanly. The
    daemon hook passes the engine's own probe (idle between scans)
    and a wiring failure never takes the daemon down.
(a) SEED: the wired loop boots on the reconciled counter — its
    counter file in a fresh data dir reads the 3,979 seed (the
    seed-value pins themselves live in
    test_exp001_self_experiments.py).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
)

from self_experiments import daemon_wiring
from self_experiments.store import StoreError

FIXTURE_STORE = Path(__file__).parent / "fixtures" / "selfexp_stream_store"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeLoop:
    """A stand-in for SelfExperimentLoop: records that run_forever
    was driven and stops when its stop event is set."""

    def __init__(self):
        self.started = threading.Event()
        self.stopped = False

    async def run_forever(self, poll_seconds=900.0, stop_event=None):
        assert stop_event is not None
        self.started.set()
        await stop_event.wait()
        self.stopped = True


class RecordingThread:
    """threading.Thread replacement that records constructions."""

    instances: list = []

    def __init__(self, *args, **kwargs):
        RecordingThread.instances.append((args, kwargs))

    def start(self):  # pragma: no cover - must never be reached when off
        raise AssertionError("a thread was started while the switch is off")


def _forbid_start_if_enabled(monkeypatch):
    import self_experiments.loop as loop_module

    def _boom(*args, **kwargs):
        raise AssertionError("start_if_enabled called while the switch is off")

    monkeypatch.setattr(loop_module, "start_if_enabled", _boom)


# ---------------------------------------------------------------------------
# (b) Inert when the switch is not exactly "on"
# ---------------------------------------------------------------------------


def test_wiring_inert_when_switch_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("STRATEX_SELF_EXPERIMENTS", raising=False)
    _forbid_start_if_enabled(monkeypatch)
    RecordingThread.instances = []
    monkeypatch.setattr(daemon_wiring.threading, "Thread", RecordingThread)
    data_dir = tmp_path / "loop_data"
    handle = daemon_wiring.start(
        work_probe=lambda: True, store_dir=FIXTURE_STORE, data_dir=data_dir
    )
    assert handle is None
    assert RecordingThread.instances == []  # no thread was even created
    assert not data_dir.exists()  # no counter/ledger writes


@pytest.mark.parametrize("value", ["off", "yes", "1", "true", "", "onn"])
def test_wiring_inert_when_switch_not_on(tmp_path, monkeypatch, value):
    # These are the values EXP-001's gate itself refuses. (The gate —
    # experiments_enabled, mirrored exactly by the wiring — strips
    # and lowercases before comparing to "on", so case/whitespace
    # variants of "on" are the gate's own designed acceptance, not
    # the wiring's invention.)
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", value)
    _forbid_start_if_enabled(monkeypatch)
    handle = daemon_wiring.start(
        work_probe=lambda: True,
        store_dir=FIXTURE_STORE,
        data_dir=tmp_path / "loop_data",
    )
    assert handle is None
    assert not (tmp_path / "loop_data").exists()


# ---------------------------------------------------------------------------
# (c) Live when the switch is exactly "on"
# ---------------------------------------------------------------------------


def test_wiring_starts_loop_with_probe_when_on(tmp_path, monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    import self_experiments.loop as loop_module

    fake = FakeLoop()
    captured = {}

    def fake_start_if_enabled(store_dir, data_dir, **kwargs):
        captured["store_dir"] = store_dir
        captured["data_dir"] = data_dir
        captured["kwargs"] = kwargs
        return fake

    monkeypatch.setattr(loop_module, "start_if_enabled", fake_start_if_enabled)
    probe = lambda: False  # daemon busy
    handle = daemon_wiring.start(
        work_probe=probe, store_dir=FIXTURE_STORE, data_dir=tmp_path / "d"
    )
    assert handle is not None
    assert handle.loop is fake
    # The daemon-activity probe is handed to the loop construction.
    assert captured["kwargs"]["work_probe"] is probe
    assert captured["store_dir"] == FIXTURE_STORE
    assert fake.started.wait(timeout=5.0)  # run_forever is being driven
    assert handle.is_alive
    assert handle.stop(timeout=5.0) is True
    assert fake.stopped
    assert not handle.is_alive


def test_wiring_real_loop_boots_on_reconciled_seed(tmp_path, monkeypatch):
    # End-to-end with the REAL start_if_enabled + fixture store: the
    # wired loop's counter file must read the reconciled 3,979 seed,
    # and with the daemon-activity probe reporting busy, cycles skip
    # (work_in_progress) and the counter never advances.
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    monkeypatch.setattr(os, "getloadavg", lambda: (0.1, 0.1, 0.1))
    data_dir = tmp_path / "loop_data"
    handle = daemon_wiring.start(
        work_probe=lambda: False, store_dir=FIXTURE_STORE, data_dir=data_dir
    )
    assert handle is not None
    try:
        counter_file = data_dir / "trial_counter.json"
        assert counter_file.exists()
        recorded = json.loads(counter_file.read_text())
        assert recorded["value"] == 3979
        assert recorded["seed"] == 3979
        report = handle.loop.run_one_cycle()
        assert report.status == "skipped"
        assert report.reason == "work_in_progress"  # probe-gated
        assert json.loads(counter_file.read_text())["value"] == 3979
    finally:
        assert handle.stop(timeout=5.0) is True


def test_wiring_missing_store_is_loud_not_silent(tmp_path, monkeypatch):
    # With the switch on but no production store built, start()
    # raises (the daemon hook catches + logs): a failed activation
    # must never look like a working one.
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    with pytest.raises(StoreError):
        daemon_wiring.start(
            work_probe=lambda: True,
            store_dir=tmp_path / "no_such_store",
            data_dir=tmp_path / "loop_data",
        )


# ---------------------------------------------------------------------------
# The daemon hook (autonomy/run_daemon.py)
# ---------------------------------------------------------------------------


def _bare_engine():
    """A StratexTradingEngine with only the wiring-touching state —
    the hook methods use nothing else."""
    import autonomy.run_daemon as run_daemon

    engine = run_daemon.StratexTradingEngine.__new__(
        run_daemon.StratexTradingEngine
    )
    engine._scan_in_progress = False
    engine._selfexp_handle = None
    return engine


def test_daemon_probe_reflects_scan_activity():
    engine = _bare_engine()
    assert engine._daemon_idle_probe() is True
    engine._scan_in_progress = True
    assert engine._daemon_idle_probe() is False


def test_daemon_hook_inert_when_switch_unset(monkeypatch):
    monkeypatch.delenv("STRATEX_SELF_EXPERIMENTS", raising=False)
    engine = _bare_engine()

    def _boom(*args, **kwargs):
        raise AssertionError("daemon_wiring.start called while switch is off")

    monkeypatch.setattr(daemon_wiring, "start", _boom)
    engine._start_self_experiments()  # must not raise, must not wire
    assert engine._selfexp_handle is None
    engine._stop_self_experiments()  # no-op, must not raise


def test_daemon_hook_inert_when_switch_off(monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "off")
    engine = _bare_engine()

    def _boom(*args, **kwargs):
        raise AssertionError("daemon_wiring.start called while switch is off")

    monkeypatch.setattr(daemon_wiring, "start", _boom)
    engine._start_self_experiments()
    assert engine._selfexp_handle is None


def test_daemon_hook_starts_and_stops_when_on(monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    engine = _bare_engine()
    captured = {}

    class FakeHandle:
        def __init__(self):
            self.stopped = False

        def stop(self, timeout=10.0):
            self.stopped = True
            return True

    fake_handle = FakeHandle()

    def fake_start(work_probe, store_dir=None, data_dir=None):
        captured["work_probe"] = work_probe
        return fake_handle

    monkeypatch.setattr(daemon_wiring, "start", fake_start)
    engine._start_self_experiments()
    assert engine._selfexp_handle is fake_handle
    # The hook passes the engine's own daemon-activity probe.
    assert captured["work_probe"] == engine._daemon_idle_probe
    assert captured["work_probe"]() is True
    engine._scan_in_progress = True
    assert captured["work_probe"]() is False
    engine._stop_self_experiments()
    assert fake_handle.stopped
    assert engine._selfexp_handle is None


def test_daemon_hook_survives_wiring_failure(monkeypatch):
    monkeypatch.setenv("STRATEX_SELF_EXPERIMENTS", "on")
    engine = _bare_engine()

    def _explode(*args, **kwargs):
        raise RuntimeError("store not built yet")

    monkeypatch.setattr(daemon_wiring, "start", _explode)
    engine._start_self_experiments()  # logged, never raised
    assert engine._selfexp_handle is None
