"""TASK-STR-FWD-015: the daemon heartbeat must not depend on scan cycles.

Production evidence (2026-11-17): Stratex-Daemon rewrote
state/daemon_heartbeat.json only at scan-cycle boundaries, and under
S1 memory pressure its cycles stretched from a healthy ~21s to
~200s and beyond 9 minutes. Every consumer that gates on heartbeat
freshness — FRIDAY's stratex_watch snapshot gate (60s), the
dashboard's daemon snapshot (600s) — therefore read a live,
error-free daemon as stale almost all the time.

The fix: the scan loop publishes an in-memory snapshot of the last
completed cycle, and a dedicated pulse thread rewrites the file
every heartbeat_pulse_seconds, advancing ONLY the pulse fields
(timestamp / updated_at). These tests pin:

(a) the file is rewritten on cadence while a scan cycle is blocked;
(b) a republish carries the last completed cycle's state verbatim —
    no field is refreshed without a real cycle behind it;
(c) the pulsed file's schema is identical to the legacy writer's;
(d) the pre-cycle state is honest (scan_count 0, last_cycle null,
    no invented figures), and nothing is written before the first
    publish;
(e) shutdown lands the STOPPED snapshot via the pulse's final flush;
(f) a dead pulse thread is loud and final (logged at ERROR, never
    silently restarted);
(g) a publish wakes the pulse promptly (startup/boundary immediacy).
"""

import json
import os
import time

import pytest

import autonomy.run_daemon as run_daemon
from autonomy.run_daemon import StratexTradingEngine


RISK_A = {
    "total_balance": 999.0,
    "total_equity": 1001.0,
    "unrealized_pnl": 2.0,
    "realized_pnl": -1.0,
    "positions": 2,
    "daily_loss_limit_hit": False,
    "daily_start_equity": 1000.0,
    "venue_alerts": [],
}

RESULTS_1 = {"scanned": 242, "signals": 3, "executed": 1, "errors": 0}


def _engine(tmp_path, monkeypatch, pulse_seconds=None):
    """An engine built like the production one, minus __init__."""

    class _StubEngine:
        venues = {"binance_futures": object(), "oanda": object()}

    eng = StratexTradingEngine.__new__(StratexTradingEngine)
    eng.engine = _StubEngine()
    eng.scan_count = 0
    eng.scan_interval = 15.0
    eng._last_risk_summary = dict(RISK_A)
    if pulse_seconds is not None:
        eng.heartbeat_pulse_seconds = pulse_seconds
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
    return eng


def _read_hb(tmp_path):
    return json.loads((tmp_path / "daemon_heartbeat.json").read_text())


def _wait_for(predicate, timeout=5.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestPulseCadence:
    def test_file_rewrites_on_cadence_while_cycle_blocked(self, tmp_path, monkeypatch):
        """(a) After one publish, no further cycle completes (the
        scan is 'blocked'), yet the file keeps being rewritten."""
        eng = _engine(tmp_path, monkeypatch, pulse_seconds=0.2)
        eng.scan_count = 3
        eng._publish_daemon_heartbeat(results=dict(RESULTS_1))
        eng._start_heartbeat_pulse()
        try:
            assert _wait_for(lambda: (tmp_path / "daemon_heartbeat.json").exists())
            first = _read_hb(tmp_path)
            seen = {first["updated_at"]}

            def _collect():
                try:
                    seen.add(_read_hb(tmp_path)["updated_at"])
                except Exception:
                    pass
                return len(seen) >= 4

            assert _wait_for(_collect, timeout=3.0)
            latest = _read_hb(tmp_path)
            # The pulse advanced; the cycle fields never moved.
            assert latest["updated_at"] > first["updated_at"]
            assert latest["scan_count"] == 3
            assert latest["last_cycle"] == RESULTS_1
            assert latest["status"] == "RUNNING"
        finally:
            eng._publish_daemon_heartbeat(status="STOPPED")
            eng._stop_heartbeat_pulse()

    def test_publish_wakes_the_pulse_promptly(self, tmp_path, monkeypatch):
        """(g) With a 30s cadence, a publish is flushed ~immediately,
        so startup and cycle boundaries behave like the old writer."""
        eng = _engine(tmp_path, monkeypatch, pulse_seconds=30.0)
        eng._start_heartbeat_pulse()
        try:
            eng.scan_count = 1
            eng._publish_daemon_heartbeat(results=dict(RESULTS_1))
            assert _wait_for(
                lambda: (tmp_path / "daemon_heartbeat.json").exists(), timeout=2.0
            )
            assert _read_hb(tmp_path)["scan_count"] == 1
        finally:
            eng._publish_daemon_heartbeat(status="STOPPED")
            eng._stop_heartbeat_pulse()


class TestRepublishTruthfulness:
    def test_flush_republishes_last_cycle_verbatim(self, tmp_path, monkeypatch):
        """(b) Engine attributes may move on mid-cycle; the flushed
        heartbeat still carries the last PUBLISHED cycle's state."""
        eng = _engine(tmp_path, monkeypatch)
        eng.scan_count = 5
        eng._publish_daemon_heartbeat(results=dict(RESULTS_1))
        published = dict(eng._heartbeat_snapshot)

        # Mid-cycle mutation: a new cycle is under way but has NOT
        # completed, so none of this may leak into the heartbeat.
        eng.scan_count = 99
        eng._last_risk_summary = {
            "total_balance": 1.0,
            "total_equity": 1.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "positions": 0,
            "daily_loss_limit_hit": True,
        }
        eng._last_evaluation_iso = "2999-01-01T00:00:00Z"

        time.sleep(0.05)
        assert eng._flush_heartbeat_snapshot() is True
        hb = _read_hb(tmp_path)
        for key, value in published.items():
            if key in ("timestamp", "updated_at"):
                continue
            assert hb[key] == value, key
        assert hb["scan_count"] == 5
        assert hb["last_cycle"] == RESULTS_1
        assert hb["total_balance"] == RISK_A["total_balance"]
        assert hb["daily_loss_limit_hit"] is False
        assert hb["last_strategy_evaluation"] == published["last_strategy_evaluation"]
        # Only the pulse moved.
        assert hb["updated_at"] >= published["updated_at"]

    def test_schema_identical_to_legacy_writer(self, tmp_path, monkeypatch):
        """(c) Same keys, same order, same values as _write_daemon_heartbeat."""
        eng = _engine(tmp_path, monkeypatch)
        eng.scan_count = 7
        eng._write_daemon_heartbeat(results=dict(RESULTS_1))
        legacy = _read_hb(tmp_path)

        eng._publish_daemon_heartbeat(results=dict(RESULTS_1))
        snapshot = eng._heartbeat_snapshot
        assert eng._flush_heartbeat_snapshot() is True
        pulsed = _read_hb(tmp_path)

        # Identical schema (keys + order) to the legacy writer, and
        # every non-pulse field identical to the published snapshot.
        assert list(pulsed.keys()) == list(legacy.keys())
        for key in legacy:
            if key in ("timestamp", "updated_at"):
                continue
            assert pulsed[key] == snapshot[key], key

        # The error variant keeps last_error, in the same position.
        eng._write_daemon_heartbeat(error=ValueError("boom"), status="ERROR")
        legacy_err = _read_hb(tmp_path)
        eng._publish_daemon_heartbeat(error=ValueError("boom"), status="ERROR")
        assert eng._flush_heartbeat_snapshot() is True
        pulsed_err = _read_hb(tmp_path)
        assert list(pulsed_err.keys()) == list(legacy_err.keys())
        assert pulsed_err["status"] == "ERROR"
        assert pulsed_err["last_error"] == "boom"


class TestPreCycleHonesty:
    def test_nothing_written_before_first_publish(self, tmp_path, monkeypatch):
        """(d) A flush with no snapshot writes nothing — the pulse
        must not invent a payload for a daemon that has not run."""
        eng = _engine(tmp_path, monkeypatch)
        assert eng._flush_heartbeat_snapshot() is False
        assert not (tmp_path / "daemon_heartbeat.json").exists()

    def test_startup_snapshot_is_honest(self, tmp_path, monkeypatch):
        """(d) Before the first cycle: scan_count 0, last_cycle null,
        risk figures null when no risk summary exists yet."""
        eng = _engine(tmp_path, monkeypatch)
        eng._last_risk_summary = None
        eng._publish_daemon_heartbeat()
        assert eng._flush_heartbeat_snapshot() is True
        hb = _read_hb(tmp_path)
        assert hb["status"] == "RUNNING"
        assert hb["pid"] == os.getpid()
        assert hb["scan_count"] == 0
        assert hb["last_cycle"] is None
        assert hb["total_balance"] is None
        assert hb["total_equity"] is None
        assert hb["open_positions"] is None


class TestShutdownAndFailure:
    def test_stopped_snapshot_lands_via_final_flush(self, tmp_path, monkeypatch):
        """(e) run()'s shutdown path: publish STOPPED, stop the
        pulse — the final flush writes STOPPED despite a long
        cadence, and the thread is joined."""
        eng = _engine(tmp_path, monkeypatch, pulse_seconds=30.0)
        eng._start_heartbeat_pulse()
        eng.scan_count = 2
        eng._publish_daemon_heartbeat(results=dict(RESULTS_1))
        assert _wait_for(lambda: (tmp_path / "daemon_heartbeat.json").exists())

        eng._publish_daemon_heartbeat(status="STOPPED")
        eng._stop_heartbeat_pulse()

        assert not eng._heartbeat_thread.is_alive()
        hb = _read_hb(tmp_path)
        assert hb["status"] == "STOPPED"
        assert hb["scan_count"] == 2
        # The STOPPED republish keeps the last real evaluation time.
        assert hb["last_strategy_evaluation"] is not None

    def test_pulse_thread_death_is_loud_and_final(self, tmp_path, monkeypatch):
        """(f) If the pulse loop dies, it logs at ERROR and exits;
        the file then goes stale — detectable, never masked."""
        errors = []

        class _RecordingLogger:
            def error(self, *args, **kwargs):
                errors.append((args, kwargs))

            def __getattr__(self, _name):
                return lambda *a, **k: None

        monkeypatch.setattr(run_daemon, "logger", _RecordingLogger())
        eng = _engine(tmp_path, monkeypatch, pulse_seconds=0.1)

        def _explode():
            raise RuntimeError("pulse boom")

        eng._flush_heartbeat_snapshot = _explode
        eng._start_heartbeat_pulse()
        thread = eng._heartbeat_thread
        thread.join(timeout=3.0)

        assert not thread.is_alive()
        assert errors, "pulse death must be logged"
        assert "Heartbeat pulse thread died" in str(errors[0][0])
