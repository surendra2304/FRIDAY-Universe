"""TASK-STR-FWD-011 — sleeve _book_close hardening (trade 470).

Trade 470 (USDJPY LONG 15 @ 159.691, OANDA demo sleeve) was booked
BROKER_CLOSE at $0.00 on 2026-11-16T13:08:45Z from a CLOSED record
carrying NO close fields: exit_time was the time.time() fallback
(12.9us BEFORE the ledger append's own timestamp — impossible for a
broker closeTime), exit_price the open price via the
averageClosePrice->price fallback, realized 0.0 via the
realizedPL->0 fallback. The venue position persisted (daemon
re-adopted it from live reads at 15:31/16:29/19:33Z; direct OANDA
probe 2026-11-17 ~11:35 IST: still open, uPnL -0.0546) while the
sleeve believed it closed and the leg sat unmanaged.

These tests pin: a CLOSED record with no closeTime AND no
averageClosePrice must NEVER be booked — the trade stays in
own_trades, the unrecorded_close alert latches, retry next cycle.
A record with SOME close fields still books, with the fallback
flagged loudly in the log.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from measurement import fill_ledger  # noqa: E402
from oanda_demo.sleeve_runner import SleeveRunner, _rfc3339_to_unix  # noqa: E402

CLOSE_TIME = "2026-11-16T13:08:45.123456Z"

_META_470 = {
    "symbol": "USDJPY",
    "side": "BUY",
    "units": 15,
    "entry_price": 159.691,
    "entry_time": 1794780546.004498,
    "order_id": "470",
}


class _CloseFakeAdapter:
    """OANDA-shaped fake: GET /trades/{id} returns one canned record."""

    account_id = "101-001-FAKE"

    def __init__(self, trade_record):
        self.trade_record = trade_record

    def normalize_symbol(self, s):
        return s.replace("_", "")

    def denormalize_symbol(self, s):
        return s[:3] + "_" + s[3:] if len(s) == 6 else s

    def get_account_summary(self):
        return {"balance": 10000.0, "equity": 10000.0,
                "margin_used": 0.0, "margin_available": 10000.0,
                "unrealized_pl": 0.0, "margin_rate": 0.02}

    def open_trades(self):
        return []

    def get_pricing(self, symbols):
        return {s: {"bid": 1.0, "ask": 1.0, "mid": 1.0, "spread": 0.0}
                for s in symbols}

    def _request(self, method, path, params=None):
        if "/trades/" in path:
            if self.trade_record is None:
                return {}
            return {"trade": dict(self.trade_record)}
        if "/candles" in path:
            return {"candles": []}
        return {}


def _make_runner(tmp_path, adapter):
    return SleeveRunner(
        adapter=adapter,
        dry_run=False,
        state_file=tmp_path / "sleeve_state.json",
        data_dir=tmp_path,
    )


@pytest.fixture
def _isolated_state(tmp_path, monkeypatch):
    """Point the measurement store at a scratch dir (never the repo state)."""
    monkeypatch.setenv("STRATEX_STATE_DIR", str(tmp_path / "state"))
    return tmp_path


def test_closed_with_no_close_fields_is_never_booked(_isolated_state, tmp_path):
    """Trade-470 shape: CLOSED + no closeTime + no averageClosePrice."""
    adapter = _CloseFakeAdapter({"state": "CLOSED", "price": "159.691"})
    runner = _make_runner(tmp_path, adapter)
    assert runner._book_close("470", dict(_META_470)) is False
    assert fill_ledger.read_fills() == []  # no fallback $0.00 fill
    alerts = fill_ledger.active_alerts()
    assert "unrecorded_close" in alerts
    detail = alerts["unrecorded_close"]["detail"]
    assert "470" in detail
    assert "TASK-STR-FWD-011" in detail


def test_closed_with_no_close_fields_trade_retained_for_retry(
    _isolated_state, tmp_path
):
    """The unbooked trade stays in own_trades; run_once reports it unbooked."""
    (tmp_path / "sleeve_entries_paused").write_text("pause")
    state = {"day": "2026-11-17", "own_trades": {"470": dict(_META_470)}}
    (tmp_path / "sleeve_state.json").write_text(json.dumps(state))
    adapter = _CloseFakeAdapter({"state": "CLOSED", "price": "159.691"})
    runner = _make_runner(tmp_path, adapter)
    out = runner.run_once()
    assert "470" in out.get("closes_unbooked", [])
    assert "470" not in out.get("closes", [])
    saved = json.loads((tmp_path / "sleeve_state.json").read_text())
    assert "470" in saved["own_trades"]  # retry queue intact
    assert fill_ledger.read_fills() == []


def test_closed_with_full_fields_books_from_broker_truth(
    _isolated_state, tmp_path
):
    """Both close fields present: booked exactly as before (regression guard)."""
    record = {
        "state": "CLOSED",
        "closeTime": CLOSE_TIME,
        "averageClosePrice": "159.800",
        "realizedPL": "1.65",
        "price": "159.691",
    }
    adapter = _CloseFakeAdapter(record)
    runner = _make_runner(tmp_path, adapter)
    assert runner._book_close("470", dict(_META_470)) is True
    fills = fill_ledger.read_fills()
    assert len(fills) == 1
    row = fills[0]
    assert row["symbol"] == "USDJPY"
    assert row["side"] == "BUY"
    assert row["qty"] == pytest.approx(15)
    assert row["entry_price"] == pytest.approx(159.691)
    assert row["exit_price"] == pytest.approx(159.800)
    assert row["gross_pnl"] == pytest.approx(1.65)
    assert row["net_pnl"] == pytest.approx(1.65)
    assert row["exit_time"] == pytest.approx(_rfc3339_to_unix(CLOSE_TIME))
    assert row["exit_reason"] == "BROKER_CLOSE"
    assert row["order_id"] == "470"
    assert row["entry_order_id"] == "470"


def test_closed_with_close_time_only_books_with_flagged_price_fallback(
    _isolated_state, tmp_path, caplog
):
    """closeTime real, averageClosePrice missing: book, but log the fallback LOUDLY."""
    record = {"state": "CLOSED", "closeTime": CLOSE_TIME, "price": "159.691"}
    adapter = _CloseFakeAdapter(record)
    runner = _make_runner(tmp_path, adapter)
    with caplog.at_level(logging.WARNING, logger="oanda_sleeve_runner"):
        assert runner._book_close("470", dict(_META_470)) is True
    fills = fill_ledger.read_fills()
    assert len(fills) == 1
    row = fills[0]
    assert row["exit_time"] == pytest.approx(_rfc3339_to_unix(CLOSE_TIME))
    assert row["exit_price"] == pytest.approx(159.691)  # open-price fallback
    assert row["net_pnl"] == pytest.approx(0.0)
    assert any(
        "fallback" in r.message.lower()
        and "averagecloseprice" in r.message.lower()
        for r in caplog.records
    ), "missing-field fallback must be logged loudly"


def test_closed_with_close_price_only_books_with_flagged_time_fallback(
    _isolated_state, tmp_path, caplog
):
    """averageClosePrice real, closeTime missing: book, but log the fallback LOUDLY."""
    record = {
        "state": "CLOSED",
        "averageClosePrice": "159.800",
        "realizedPL": "1.65",
        "price": "159.691",
    }
    adapter = _CloseFakeAdapter(record)
    runner = _make_runner(tmp_path, adapter)
    with caplog.at_level(logging.WARNING, logger="oanda_sleeve_runner"):
        assert runner._book_close("470", dict(_META_470)) is True
    fills = fill_ledger.read_fills()
    assert len(fills) == 1
    row = fills[0]
    assert row["exit_price"] == pytest.approx(159.800)
    assert row["net_pnl"] == pytest.approx(1.65)
    assert abs(row["exit_time"] - time.time()) < 120  # time.time() fallback
    assert any(
        "fallback" in r.message.lower() and "closetime" in r.message.lower()
        for r in caplog.records
    ), "missing-field fallback must be logged loudly"
