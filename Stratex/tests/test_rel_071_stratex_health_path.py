"""TASK-REL-071: the Stratex health path reads the daemon heartbeat, not the
retired testnet heartbeat — and surfaces the daemon evaluation age.

Live evidence (2026-11-22, Server 1 /opt/friday_universe/Stratex): the
retired testnet engine's heartbeat file is frozen since 2026-11-14
(status STOPPED, last evaluation 2026-11-14T21:31:03Z) while the
multi-venue daemon writes state/daemon_heartbeat.json every scan cycle.
The health path still read the frozen file first, so the detailed-health
feed pillar derived freshness from an 8-day-old heartbeat and /health
served the frozen evaluation stamp with no age. These tests pin the
retirement: the health path resolves the daemon heartbeat, the frozen
file is ignored even when present, and the evaluation age (seconds) is
surfaced next to its timestamp in /health, the feed pillar, and the
supervision payload.
"""

import datetime
import json
import os
import time
from pathlib import Path

import pytest

import config
import paper_runner_supervisor
from dashboard import _health_payload, get_engine_health_data

STRATEX_DIR = Path(__file__).resolve().parents[1]

# The retired heartbeat identifiers, assembled so this file never contains
# them literally (the guard below scans the health-path sources for them).
_LEGACY_ENV = "TESTNET_" + "HEARTBEAT_FILE"
_LEGACY_FILE = "testnet_" + "heartbeat.json"


def _daemon_hb(tmp_path, monkeypatch, **overrides):
    """Write a daemon-format heartbeat and point the health path at it."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    hb = {
        "status": "RUNNING",
        "pid": os.getpid(),
        "timestamp": now,
        "updated_at": datetime.datetime.utcnow().timestamp(),
        "scan_count": 42,
        "scan_interval_seconds": 15.0,
        "last_strategy_evaluation": now,
        "total_balance": 1234.5,
        "total_equity": 1250.25,
        "unrealized_pnl": 12.345,
        "open_positions": 3,
        "venues": ["binance_futures"],
    }
    hb.update(overrides)
    f = tmp_path / "daemon_heartbeat.json"
    f.write_text(json.dumps(hb))
    monkeypatch.setenv("STRATEX_HEARTBEAT_FILE", str(f))
    monkeypatch.setenv("STRATEX_DAEMON_HEARTBEAT_FILE", str(f))
    monkeypatch.setattr(
        paper_runner_supervisor,
        "get_status",
        lambda: {"paper_runner_status": "STOPPED", "alive": False},
    )
    monkeypatch.setattr(config, "TRADING_MODE", "FUTURES")
    return f


def _feed_hb(tmp_path, monkeypatch, **overrides):
    """Write a daemon-format heartbeat for the feed-freshness pillar."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    hb = {
        "status": "RUNNING",
        "pid": os.getpid(),
        "timestamp": now,
        "updated_at": time.time(),
        "scan_count": 7,
        "last_strategy_evaluation": now,
    }
    hb.update(overrides)
    f = tmp_path / "daemon_heartbeat.json"
    f.write_text(json.dumps(hb))
    monkeypatch.setenv("STRATEX_HEARTBEAT_FILE", str(f))
    monkeypatch.delenv("STRATEX_DAEMON_HEARTBEAT_FILE", raising=False)
    return f


def test_health_path_sources_do_not_read_the_retired_testnet_heartbeat():
    """No code reference to the retired heartbeat file/env in the health path.

    Comments may name the retired file (they explain the retirement); a
    live read would need the filename as a string literal or the env var.
    """
    for name in ("dashboard.py", "api/health.py"):
        src = (STRATEX_DIR / name).read_text(encoding="utf-8")
        assert _LEGACY_ENV not in src, f"{name} still reads {_LEGACY_ENV}"
        assert f'"{_LEGACY_FILE}"' not in src, f"{name} still reads {_LEGACY_FILE}"


def test_daemon_heartbeat_serves_online_with_evaluation_age(tmp_path, monkeypatch):
    """The daemon heartbeat (no worker_alive / strategies keys) reads ONLINE
    and the evaluation age is surfaced in the engine data and /health."""
    _daemon_hb(tmp_path, monkeypatch)

    data = get_engine_health_data()

    assert data["healthy"] is True
    assert data["engine_status"] == "ONLINE"
    assert data["trading_capable"] is True
    assert data["engine_source"] == "multi_venue_daemon"
    assert data["last_strategy_evaluation_age_sec"] is not None
    assert data["last_strategy_evaluation_age_sec"] < 10

    payload = _health_payload("process_liveness")
    assert payload["engine"] == "online"
    assert payload["daemon_last_evaluation"] == data["last_strategy_evaluation"]
    assert payload["daemon_last_evaluation_age_sec"] is not None
    assert payload["daemon_last_evaluation_age_sec"] < 10


def test_frozen_legacy_heartbeat_file_is_ignored_when_present(tmp_path, monkeypatch):
    """The production condition: a frozen retired heartbeat sits in cwd
    next to a live daemon heartbeat. The health path must serve the
    daemon's evaluation, never the frozen 2026-11-14 stamp."""
    frozen = {
        "status": "STOPPED",
        "worker_alive": False,
        "pid": 2503927,
        "timestamp": "2026-11-14T21:31:34.747351Z",
        "mode": "TESTNET",
        "strategies": ["bb_reversion"],
        "last_strategy_evaluation": "2026-11-14T21:31:03.925225Z",
        "open_positions": 0,
    }
    (tmp_path / _LEGACY_FILE).write_text(json.dumps(frozen))
    monkeypatch.chdir(tmp_path)
    _daemon_hb(tmp_path, monkeypatch)

    data = get_engine_health_data()

    assert data["engine_status"] == "ONLINE"
    assert data["healthy"] is True
    assert data["last_strategy_evaluation"] != "2026-11-14T21:31:03.925225Z"
    assert data["last_strategy_evaluation_age_sec"] is not None
    assert data["last_strategy_evaluation_age_sec"] < 10


def test_feed_freshness_uses_daemon_evaluation_as_evidence(tmp_path, monkeypatch):
    """A fresh daemon evaluation means a fresh feed: the evaluation implies
    a market-data fetch just completed."""
    import api.health as h

    _feed_hb(tmp_path, monkeypatch)

    data, status = h._measure_feed_freshness()

    assert status == "HEALTHY"
    assert data["feed_status"] == "REAL_TIME_STREAMING"
    assert data["heartbeat_source"] == "daemon_heartbeat"
    assert data["last_strategy_evaluation_age_sec"] is not None
    assert data["last_strategy_evaluation_age_sec"] < 10
    assert data["heartbeat_age_sec"] is not None
    assert data["heartbeat_age_sec"] < 10


def test_feed_freshness_reports_stale_daemon_evaluation(tmp_path, monkeypatch):
    """A daemon heartbeat whose last evaluation is 2 h old is STALE, not
    streaming — the pulse keeps the file fresh, the evaluation does not."""
    import api.health as h

    stale = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    ).isoformat().replace("+00:00", "Z")
    _feed_hb(tmp_path, monkeypatch, last_strategy_evaluation=stale)

    data, status = h._measure_feed_freshness()

    assert status == "STALE"
    assert data["feed_status"] == "STALE"
    assert data["last_strategy_evaluation_age_sec"] > 900


def test_feed_freshness_without_evaluation_stamp_is_unavailable(tmp_path, monkeypatch):
    """A daemon heartbeat with no timestamped evidence is UNAVAILABLE, not
    silently streaming."""
    import api.health as h

    f = _feed_hb(tmp_path, monkeypatch)
    hb = json.loads(f.read_text())
    hb.pop("last_strategy_evaluation")
    f.write_text(json.dumps(hb))

    data, status = h._measure_feed_freshness()

    assert status == "UNAVAILABLE"
    assert data["feed_status"] == "UNAVAILABLE"
    assert data["reason"] == "NO_TIMESTAMPED_FEED_EVIDENCE"


def test_feed_freshness_missing_daemon_heartbeat_is_unavailable(tmp_path, monkeypatch):
    """No daemon heartbeat anywhere means no feed evidence at all."""
    import api.health as h

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("STRATEX_HEARTBEAT_FILE", raising=False)
    monkeypatch.delenv("STRATEX_DAEMON_HEARTBEAT_FILE", raising=False)

    data, status = h._measure_feed_freshness()

    assert status == "UNAVAILABLE"
    assert data["feed_status"] == "UNAVAILABLE"
    assert data["reason"] == "HEARTBEAT_FILE_MISSING"
    assert data["heartbeat_source"] == "daemon_heartbeat"


def test_supervision_surfaces_last_analysis_age_sec(monkeypatch):
    """The supervision market_conditions carry the evaluation age next to
    its timestamp, so staleness is visible without parsing ISO strings."""
    from api import friday_supervision as fs

    monkeypatch.setattr(fs, "_LAST_MARKET_ANALYSIS", {
        "analysis_timestamp": "2026-11-22T00:00:00Z",
        "signal_count": 2,
        "buy_signals": 1,
        "sell_signals": 1,
    })
    monkeypatch.setattr(fs, "_LAST_MARKET_ANALYSIS_TS", time.time())

    data = fs._real_trading_data()

    assert data["market_conditions"]["last_analysis"] == "2026-11-22T00:00:00Z"
    age = data["market_conditions"]["last_analysis_age_sec"]
    assert age is not None
    assert 0 <= age < 10


def test_supervision_age_is_none_before_any_analysis(monkeypatch):
    """Cold process: no analysis snapshot, no age — never a fabricated 0."""
    from api import friday_supervision as fs

    monkeypatch.setattr(fs, "_LAST_MARKET_ANALYSIS", None)
    monkeypatch.setattr(fs, "_LAST_MARKET_ANALYSIS_TS", 0.0)

    data = fs._real_trading_data()

    assert data["market_conditions"]["last_analysis"] is None
    assert data["market_conditions"]["last_analysis_age_sec"] is None
