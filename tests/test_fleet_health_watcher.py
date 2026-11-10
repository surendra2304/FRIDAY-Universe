"""TASK-OBS-001 — fleet health watcher unit tests.

Covers the pure decision logic of scripts/fleet_health_watcher.py:
crash-loop detection via NRestarts deltas, service-down/health-fail alerting,
recovery transitions, alert deduplication/cooldown and state persistence.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_WATCHER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fleet_health_watcher.py"
_spec = importlib.util.spec_from_file_location("fleet_health_watcher", _WATCHER_PATH)
watcher = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("fleet_health_watcher", watcher)
_spec.loader.exec_module(watcher)


def snap(name="FRIDAY", active="active", sub="running", restarts=0, http=200, error="", detail=""):
    s = watcher.ServiceSnapshot(name=name)
    s.active_state, s.sub_state, s.n_restarts = active, sub, restarts
    s.health_http, s.health_detail, s.error = http, detail, error
    return s


class TestParseServices:
    def test_default_is_full_server1_map(self):
        svcs = watcher.parse_services(None)
        names = [s.name for s in svcs]
        assert names == ["FRIDAY", "Inference", "Memora", "Stratex",
                         "Futuris", "IntelX", "Forge", "Stratex-Daemon"]
        assert svcs[0].port == 10000
        assert svcs[-1].port is None  # daemon has no HTTP health endpoint

    def test_custom_spec(self):
        svcs = watcher.parse_services("Sentinel:8008,Cortex:8009,VyralX-Daemon:-")
        assert [s.name for s in svcs] == ["Sentinel", "Cortex", "VyralX-Daemon"]
        assert [s.port for s in svcs] == [8008, 8009, None]


class TestEvaluate:
    def test_healthy_service_emits_no_alert(self):
        state = watcher.WatchState(previous_restarts={"FRIDAY": 0})
        alerts = watcher.evaluate(snap(restarts=0), state, crash_loop_delta=3, first_seen=False)
        assert alerts == []

    def test_crash_loop_detected_on_restart_delta(self):
        state = watcher.WatchState(previous_restarts={"Stratex": 1})
        alerts = watcher.evaluate(snap("Stratex", restarts=5), state, crash_loop_delta=3, first_seen=False)
        kinds = [a["alert"] for a in alerts]
        assert "CRASH_LOOP" in kinds
        crash = next(a for a in alerts if a["alert"] == "CRASH_LOOP")
        assert "1 -> 5" in crash["detail"]
        assert crash["severity"] == "critical"

    def test_small_restart_delta_is_not_a_crash_loop(self):
        state = watcher.WatchState(previous_restarts={"FRIDAY": 2})
        alerts = watcher.evaluate(snap(restarts=4), state, crash_loop_delta=3, first_seen=False)
        assert all(a["alert"] != "CRASH_LOOP" for a in alerts)

    def test_first_seen_never_claims_crash_loop(self):
        # No baseline exists yet: one deploy restart must not read as a crash loop.
        state = watcher.WatchState()
        alerts = watcher.evaluate(snap(restarts=999), state, crash_loop_delta=3, first_seen=True)
        assert all(a["alert"] != "CRASH_LOOP" for a in alerts)

    def test_service_down_alerts(self):
        state = watcher.WatchState()
        alerts = watcher.evaluate(snap(active="failed", sub="failed", http=None),
                                  state, crash_loop_delta=3, first_seen=True)
        assert any(a["alert"] == "SERVICE_DOWN" for a in alerts)

    def test_health_fail_alerts_when_http_not_200(self):
        state = watcher.WatchState()
        alerts = watcher.evaluate(snap(http=503), state, crash_loop_delta=3, first_seen=True)
        assert any(a["alert"] == "HEALTH_FAIL" for a in alerts)
        assert all(a["alert"] != "RECOVERED" for a in alerts)

    def test_health_unreachable_while_active(self):
        state = watcher.WatchState()
        alerts = watcher.evaluate(snap(http=None, error="ConnectionRefusedError: x"),
                                  state, crash_loop_delta=3, first_seen=True)
        assert any(a["alert"] == "HEALTH_UNREACHABLE" for a in alerts)

    def test_daemon_without_http_healthy_when_active(self):
        state = watcher.WatchState()
        alerts = watcher.evaluate(snap("Stratex-Daemon", http=None, error=""),
                                  state, crash_loop_delta=3, first_seen=True)
        assert alerts == []

    def test_recovery_alert_after_previous_incident(self):
        state = watcher.WatchState(open_alerts={"Stratex:HEALTH_FAIL": "1", "Stratex:last": "HEALTH_FAIL"})
        alerts = watcher.evaluate(snap("Stratex", restarts=0), state, crash_loop_delta=3, first_seen=False)
        assert any(a["alert"] == "RECOVERED" for a in alerts)

    def test_no_recovery_alert_without_prior_incident(self):
        state = watcher.WatchState()
        alerts = watcher.evaluate(snap(), state, crash_loop_delta=3, first_seen=False)
        assert all(a["alert"] != "RECOVERED" for a in alerts)

    def test_baseline_updates_after_evaluation(self):
        state = watcher.WatchState(previous_restarts={"FRIDAY": 0})
        watcher.evaluate(snap(restarts=2), state, crash_loop_delta=3, first_seen=False)
        assert state.previous_restarts["FRIDAY"] == 2


class TestDispatchAlerts:
    def test_new_alert_dispatches_and_records(self, capsys):
        state = watcher.WatchState()
        watcher.dispatch_alerts(
            [{"alert": "SERVICE_DOWN", "service": "Memora", "detail": "down", "severity": "critical"}],
            state, cooldown_s=1800, alert_command=None,
        )
        assert "SERVICE_DOWN" in capsys.readouterr().out
        assert any(k == "Memora:SERVICE_DOWN" for k in state.open_alerts)

    def test_cooldown_suppresses_repeat(self, capsys):
        state = watcher.WatchState(open_alerts={"Memora:SERVICE_DOWN": "9999999999"})
        watcher.dispatch_alerts(
            [{"alert": "SERVICE_DOWN", "service": "Memora", "detail": "down", "severity": "critical"}],
            state, cooldown_s=1800, alert_command=None,
        )
        assert "SUPPRESSED" in capsys.readouterr().out

    def test_recovery_closes_alert_family(self):
        state = watcher.WatchState(open_alerts={
            "Memora:SERVICE_DOWN": "1", "Memora:HEALTH_FAIL": "2", "Memora:last": "x"})
        watcher.dispatch_alerts(
            [{"alert": "RECOVERED", "service": "Memora", "detail": "back", "severity": "info"}],
            state, cooldown_s=1800, alert_command=None,
        )
        assert not any(k.startswith("Memora:") and k != "Memora:last" for k in state.open_alerts)

    def test_alert_command_failure_never_raises(self, capsys):
        state = watcher.WatchState()
        watcher.dispatch_alerts(
            [{"alert": "SERVICE_DOWN", "service": "X", "detail": "d", "severity": "critical"}],
            state, cooldown_s=1800, alert_command="exit 7",
        )
        assert "X" in capsys.readouterr().out  # alert logged even when the command fails


class TestWatchStatePersistence:
    def test_roundtrip(self, tmp_path):
        path = str(tmp_path / "state.json")
        state = watcher.WatchState(previous_restarts={"FRIDAY": 3},
                                   open_alerts={"FRIDAY:SERVICE_DOWN": "123.0"},
                                   last_cycle="2026-11-10T00:00:00Z")
        state.save(path)
        loaded = watcher.WatchState.load(path)
        assert loaded.previous_restarts == {"FRIDAY": 3}
        assert loaded.open_alerts == {"FRIDAY:SERVICE_DOWN": "123.0"}
        assert loaded.last_cycle == "2026-11-10T00:00:00Z"

    def test_load_missing_file_returns_fresh_state(self, tmp_path):
        loaded = watcher.WatchState.load(str(tmp_path / "nope.json"))
        assert loaded.previous_restarts == {}
        assert loaded.open_alerts == {}

    def test_load_corrupt_file_returns_fresh_state(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json")
        loaded = watcher.WatchState.load(str(p))
        assert loaded.open_alerts == {}


class TestProbeHealth:
    def test_none_port_means_daemon(self):
        code, detail, err = watcher.probe_health(None)
        assert code is None
        assert "no http health endpoint" in detail
        assert err == ""

    def test_unreachable_port_is_reported_not_raised(self):
        code, detail, err = watcher.probe_health(1)  # tcpmux port, nothing there
        assert code is None
        assert err  # error string captured, no exception


class TestObserve:
    def test_observe_graceful_without_systemctl(self, monkeypatch):
        # Sandbox has no systemd; observe must still produce a snapshot.
        spec = watcher.ServiceSpec("NoSuchUnit", None)
        snap_obj = watcher.observe(spec)
        assert snap_obj.name == "NoSuchUnit"
        assert snap_obj.active_state in {"unknown", "active", "failed"}
        # health port None -> healthy depends only on systemd state


class TestHealthiness:
    def test_healthy_requires_active_and_200(self):
        assert snap().healthy is True
        assert snap(http=500).healthy is False
        assert snap(active="activating").healthy is False

    def test_daemon_healthy_with_active_only(self):
        assert snap("Stratex-Daemon", http=None).healthy is True


class TestCycleIntegration:
    def test_run_cycle_updates_state_and_baseline(self, monkeypatch, tmp_path):
        calls = []
        monkeypatch.setattr(watcher, "observe", lambda spec: calls.append(spec.name) or snap(spec.name))
        state = watcher.WatchState()
        services = watcher.parse_services("FRIDAY:10000,Memora:8002")
        snaps = watcher.run_cycle(services, state, crash_loop_delta=3,
                                  cooldown_s=1800, alert_command=None, first_seen=True)
        assert [s.name for s in snaps] == ["FRIDAY", "Memora"]
        assert state.previous_restarts == {"FRIDAY": 0, "Memora": 8002 and 0}
        assert state.last_cycle != ""
