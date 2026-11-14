"""TASK-REL-003: /health must see the daemon that actually trades.

Production evidence (2026-11-14): the multi-venue Stratex daemon
(Stratex-Daemon.service, autonomy/run_daemon.py) was alive and evaluating
strategies while /health reported ``engine: offline`` for 12 days, because

1. the testnet-engine heartbeat it reads belonged to a manually started
   process that was gracefully stopped on 2026-11-02 and never restarted, and
2. the daemon fallback read state/cloud_portfolio_state.json, a file only
   the MT5 cTrader engine writes — the deployed daemon never writes it.

The daemon now writes state/daemon_heartbeat.json every scan cycle, and the
dashboard reads it (pid-checked, freshness-bounded) before the legacy
snapshot. These tests pin that behaviour.
"""

import datetime
import json
import os

import pytest

import config
import paper_runner_supervisor
from dashboard import _health_payload, get_engine_health_data


def _stale_testnet_hb(tmp_path, monkeypatch):
    """The production condition: a testnet heartbeat frozen on 2026-11-02."""
    hb = {
        "status": "STOPPED",
        "worker_alive": False,
        "binance_connected": True,
        "websocket_connected": True,
        "pid": os.getpid(),
        "timestamp": "2026-11-02T06:19:25Z",
        "strategies": ["bb_reversion", "supertrend"],
        "timeframes": ["15m", "1h", "4h"],
        "last_strategy_evaluation": "2026-11-02T06:15:22Z",
    }
    f = tmp_path / "testnet_heartbeat.json"
    f.write_text(json.dumps(hb))
    monkeypatch.setenv("TESTNET_HEARTBEAT_FILE", str(f))
    monkeypatch.setattr(
        paper_runner_supervisor,
        "get_status",
        lambda: {"paper_runner_status": "STOPPED", "alive": False},
    )
    monkeypatch.setattr(config, "TRADING_MODE", "FUTURES")
    return f


def _daemon_hb(tmp_path, monkeypatch, age_seconds=0, **overrides):
    hb = {
        "status": "RUNNING",
        "pid": os.getpid(),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.datetime.utcnow().timestamp(),
        "scan_count": 42,
        "scan_interval_seconds": 0,
        "last_strategy_evaluation": datetime.datetime.utcnow().isoformat() + "Z",
        "last_cycle": {"scanned": 100, "signals": 3, "executed": 0, "errors": 0},
        "total_balance": 1234.5,
        "total_equity": 1250.25,
        "unrealized_pnl": 12.345,
        "realized_pnl": -3.5,
        "open_positions": 3,
        "daily_loss_limit_hit": False,
        "venues": ["binance_futures", "oanda"],
    }
    hb.update(overrides)
    f = tmp_path / "daemon_heartbeat.json"
    f.write_text(json.dumps(hb))
    if age_seconds:
        old = datetime.datetime.utcnow().timestamp() - age_seconds
        os.utime(f, (old, old))
    monkeypatch.setenv("STRATEX_DAEMON_HEARTBEAT_FILE", str(f))
    return f


class TestMultiVenueDaemonSnapshot:
    def test_live_daemon_makes_engine_online_with_its_real_state(self, tmp_path, monkeypatch):
        _stale_testnet_hb(tmp_path, monkeypatch)
        _daemon_hb(tmp_path, monkeypatch)

        data = get_engine_health_data()

        assert data["healthy"] is True
        assert data["engine_status"] == "ONLINE"
        assert data["trading_capable"] is True
        assert data["capability_reasons"] == []
        assert data["engine_source"] == "multi_venue_daemon"
        assert data["daemon_balance"] == 1234.5
        assert data["open_positions"] == 3
        assert data["unrealized_pnl"] == 12.35
        assert data["environment"] == "multi_venue_testnet_practice"
        assert any("testnet" in w for w in data["capability_warnings"])

        payload = _health_payload("process_liveness")
        assert payload["engine"] == "online"
        assert payload["engine_healthy"] is True
        assert payload["daemon_balance"] == 1234.5
        assert payload["engine_source"] == "multi_venue_daemon"

    def test_stale_daemon_heartbeat_does_not_resurrect_the_engine(self, tmp_path, monkeypatch):
        _stale_testnet_hb(tmp_path, monkeypatch)
        _daemon_hb(tmp_path, monkeypatch, age_seconds=3600)

        data = get_engine_health_data()

        assert data["healthy"] is False
        assert data["engine_status"] == "OFFLINE"
        assert data.get("engine_source") is None

    def test_dead_daemon_pid_does_not_count_as_alive(self, tmp_path, monkeypatch):
        _stale_testnet_hb(tmp_path, monkeypatch)
        # A pid above the Linux pid_max ceiling cannot be a live process.
        _daemon_hb(tmp_path, monkeypatch, pid=99_999_999)

        data = get_engine_health_data()

        assert data["healthy"] is False
        assert data.get("engine_source") is None

    def test_stopped_daemon_heartbeat_is_not_a_live_engine(self, tmp_path, monkeypatch):
        _stale_testnet_hb(tmp_path, monkeypatch)
        _daemon_hb(tmp_path, monkeypatch, status="STOPPED")

        data = get_engine_health_data()

        assert data["healthy"] is False
        assert data.get("engine_source") is None

    def test_missing_testnet_heartbeat_still_consults_the_daemon(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TESTNET_HEARTBEAT_FILE", str(tmp_path / "absent.json"))
        monkeypatch.setattr(
            paper_runner_supervisor,
            "get_status",
            lambda: {"paper_runner_status": "STOPPED", "alive": False},
        )
        monkeypatch.setattr(config, "TRADING_MODE", "FUTURES")
        _daemon_hb(tmp_path, monkeypatch)

        data = get_engine_health_data()

        assert data["healthy"] is True
        assert data["engine_source"] == "multi_venue_daemon"

    def test_legacy_cloud_snapshot_remains_the_fallback(self, tmp_path, monkeypatch):
        _stale_testnet_hb(tmp_path, monkeypatch)
        monkeypatch.setenv("STRATEX_DAEMON_HEARTBEAT_FILE", str(tmp_path / "absent_daemon.json"))
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "cloud_portfolio_state.json").write_text(json.dumps({
            "balance": 10792.8,
            "updated_at": "2026-11-14T00:00:00Z",
            "positions": {"EURUSD": {"unrealized_pnl": 5.0}},
        }))
        monkeypatch.chdir(tmp_path)

        data = get_engine_health_data()

        assert data["healthy"] is True
        assert data["engine_source"] == "autonomous_daemon"
        assert data["daemon_balance"] == 10792.8
        assert data["open_positions"] == 1
        assert data["environment"] == "ctrader_demo"


class TestDaemonHeartbeatWriter:
    def _engine(self, tmp_path, monkeypatch):
        from autonomy.run_daemon import StratexTradingEngine

        class _StubEngine:
            venues = {"binance_futures": object(), "oanda": object()}

        eng = StratexTradingEngine.__new__(StratexTradingEngine)
        eng.engine = _StubEngine()
        eng.scan_count = 7
        eng.scan_interval = 0.0
        eng._last_risk_summary = {
            "total_balance": 999.0,
            "total_equity": 1001.0,
            "unrealized_pnl": 2.0,
            "realized_pnl": -1.0,
            "positions": 2,
            "daily_loss_limit_hit": False,
        }
        monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path))
        return eng

    def test_writer_emits_the_fields_the_dashboard_reads(self, tmp_path, monkeypatch):
        eng = self._engine(tmp_path, monkeypatch)

        eng._write_daemon_heartbeat(results={"scanned": 10, "signals": 1, "executed": 0, "errors": 0})

        hb = json.loads((tmp_path / "daemon_heartbeat.json").read_text())
        assert hb["status"] == "RUNNING"
        assert hb["pid"] == os.getpid()
        assert hb["scan_count"] == 7
        assert hb["total_balance"] == 999.0
        assert hb["open_positions"] == 2
        assert hb["last_strategy_evaluation"] == hb["timestamp"]
        assert hb["venues"] == ["binance_futures", "oanda"]

    def test_stopped_write_keeps_the_last_evaluation_time(self, tmp_path, monkeypatch):
        eng = self._engine(tmp_path, monkeypatch)
        eng._write_daemon_heartbeat(results={"scanned": 1, "signals": 0, "executed": 0, "errors": 0})
        first = json.loads((tmp_path / "daemon_heartbeat.json").read_text())

        eng._write_daemon_heartbeat(status="STOPPED")

        stopped = json.loads((tmp_path / "daemon_heartbeat.json").read_text())
        assert stopped["status"] == "STOPPED"
        assert stopped["last_strategy_evaluation"] == first["last_strategy_evaluation"]
