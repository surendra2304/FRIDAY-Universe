"""TASK-VOI-006: a Stratex status read must never pay for the market
analysis refresh inline.

The supervision status summary backs both GET
/v1/friday/supervision/status and the mesh ``status`` task that FRIDAY's
voice brain waits on (60 s budget, brain_bridge). The figures a status
answer reports — balance, positions, ledger P&L — come from the engine's
local state and the fill ledger, NOT from the market analysis; the
analysis only feeds the ``last_market_analysis`` / ``market_conditions``
fields. Yet ``_get_engine_status_summary`` used to run the refresh
synchronously whenever the snapshot was older than the 60 s TTL:
evaluating up to 5 symbols through the strategy engine with market-data
fetches, measured live at 24.5 s cold on Server 1 and 69 s under load
(2026-11-15 03:19 IST) — which is what pushed spoken Stratex delegations
past the voice budget (TASK-VOI-005: 63.28 s timeout, 46.99 s).

The fix: ``_ensure_market_analysis`` schedules at most one background
refresh and returns immediately; status serves the last computed
snapshot with its ``analysis_timestamp`` visible. These tests pin that
contract with a slow fake refresh (3 s): on the pre-fix code the status
paths block for the whole fake; with the fix they answer at once and
the refresh still happens — off the request path, single-flight.
"""

from __future__ import annotations

import threading
import time

from api import friday_supervision as fs

_REFRESH_SLEEP_S = 3.0
_FAST_BUDGET_S = 2.0


def _reset_analysis_state(monkeypatch, snapshot=None, ts=0.0):
    monkeypatch.setattr(fs, "_LAST_MARKET_ANALYSIS", snapshot)
    monkeypatch.setattr(fs, "_LAST_MARKET_ANALYSIS_TS", ts)
    # The single-flight flag exists only with the fix; raising=False keeps
    # this helper usable when the suite runs against the pre-fix module.
    monkeypatch.setattr(fs, "_ANALYSIS_REFRESH_RUNNING", False, raising=False)


def _slow_refresh(monkeypatch, *, publish=True):
    """Replace the analysis run with a 3 s fake; return (calls, done)."""
    calls: list[float] = []
    done = threading.Event()

    def _fake(payload):
        calls.append(time.time())
        time.sleep(_REFRESH_SLEEP_S)
        if publish:
            # Mirror the real run's publication contract.
            fs._LAST_MARKET_ANALYSIS = {
                "analysis_timestamp": "test",
                "signal_count": 0,
                "buy_signals": 0,
                "sell_signals": 0,
            }
            fs._LAST_MARKET_ANALYSIS_TS = time.time()
        done.set()
        return {}

    monkeypatch.setattr(fs, "_run_market_analysis", _fake)
    return calls, done


def _wait_refresh_done(done: threading.Event, timeout: float = 15.0) -> None:
    """Never leak a still-running fake refresh into the next test."""
    assert done.wait(timeout=timeout), "background refresh never completed"


def test_status_summary_does_not_wait_for_the_analysis_refresh(monkeypatch):
    _reset_analysis_state(monkeypatch)
    calls, done = _slow_refresh(monkeypatch)
    try:
        start = time.time()
        summary = fs._get_engine_status_summary()
        elapsed = time.time() - start

        assert elapsed < _FAST_BUDGET_S, (
            f"status summary blocked {elapsed:.2f}s on the analysis refresh; "
            "a read must serve the last snapshot, not compute a new one"
        )
        # The figures the answer exists for are present regardless.
        assert summary["engine"] == "Stratex"
        assert "balance" in summary and "positions" in summary
    finally:
        _wait_refresh_done(done)
    assert len(calls) == 1, "the stale snapshot must still trigger exactly one refresh"


def test_supervision_endpoint_is_fast_with_a_cold_analysis_cache(monkeypatch):
    _reset_analysis_state(monkeypatch)
    calls, done = _slow_refresh(monkeypatch)
    try:
        from dashboard import app

        app.config["TESTING"] = True
        with app.test_client() as client:
            start = time.time()
            res = client.get("/v1/friday/supervision/status")
            elapsed = time.time() - start

        assert res.status_code == 200
        assert elapsed < _FAST_BUDGET_S, (
            f"supervision endpoint blocked {elapsed:.2f}s on the analysis refresh"
        )
        data = res.get_json()["data"]
        assert data["engine"] == "Stratex"
        assert "balance" in data
    finally:
        _wait_refresh_done(done)
    assert len(calls) == 1


def test_refresh_is_single_flight_while_one_is_running(monkeypatch):
    _reset_analysis_state(monkeypatch)
    # publish=False: the snapshot stays stale for the whole fake run, so a
    # second ensure call can only be turned away by the single-flight
    # guard — on the pre-fix code it runs the refresh a second time.
    calls, done = _slow_refresh(monkeypatch, publish=False)
    try:
        start = time.time()
        fs._ensure_market_analysis()
        first_elapsed = time.time() - start
        fs._ensure_market_analysis()
        total_elapsed = time.time() - start

        assert first_elapsed < _FAST_BUDGET_S, (
            f"_ensure_market_analysis blocked {first_elapsed:.2f}s inline"
        )
        assert total_elapsed < _FAST_BUDGET_S + 1.0
    finally:
        _wait_refresh_done(done)
    assert len(calls) == 1, f"refresh ran {len(calls)} times; expected single-flight 1"


def test_fresh_snapshot_triggers_no_refresh(monkeypatch):
    snapshot = {
        "analysis_timestamp": "just-now",
        "signal_count": 1,
        "buy_signals": 1,
        "sell_signals": 0,
    }
    _reset_analysis_state(monkeypatch, snapshot=snapshot, ts=time.time())
    calls, _done = _slow_refresh(monkeypatch)

    fs._ensure_market_analysis()
    time.sleep(0.3)  # a wrongly scheduled background refresh would have started

    assert calls == [], "a snapshot inside its TTL must not be refreshed"


def test_status_summary_serves_the_last_snapshot_with_its_timestamp(monkeypatch):
    snapshot = {
        "analysis_timestamp": "2026-11-15T00:00:00Z",
        "signal_count": 2,
        "buy_signals": 1,
        "sell_signals": 1,
    }
    _reset_analysis_state(monkeypatch, snapshot=snapshot, ts=time.time())

    summary = fs._get_engine_status_summary()

    assert summary["last_market_analysis"] == snapshot
    assert summary["market_conditions"]["last_analysis"] == "2026-11-15T00:00:00Z"
