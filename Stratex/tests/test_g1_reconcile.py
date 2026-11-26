"""TASK-STR-051-FIX-01 — offline G1 reconciliation tests.

Pure-core tests: no venue, no keys, no network, no live files. The
module is imported from Stratex/scripts by path so these tests run in
any CI job that collects this file.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "g1_reconcile",
    SCRIPTS_DIR / "g1_reconcile.py",
)
assert SPEC is not None and SPEC.loader is not None
g1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g1)

BASE_MS = 1795500000000  # 2026-11-24 ~12:00 UTC, arbitrary fixed anchor


def _row(**overrides):
    row = {
        "strategy": "strategy_alpha",
        "engine": "daemon",
        "venue": "binance_futures",
        "symbol": "ETHUSDT",
        "side": "LONG",
        "qty": 0.5,
        "entry_price": 2000.0,
        "exit_price": 2010.0,
        "entry_time": (BASE_MS - 3600_000) / 1000.0,
        "exit_time": BASE_MS / 1000.0,
        "gross_pnl": 5.0,
        "fees": 0.1,
        "fees_source": "broker",
        "net_pnl": 4.9,
        "exit_reason": "TIME",
        "order_id": "OID-1",
        "entry_order_id": "OID-0",
        "recorded_at": "2026-11-24T12:00:00+00:00",
    }
    row.update(overrides)
    return row


def _close(**overrides):
    close = {
        "symbol": "ETHUSDT",
        "order_id": "1001",
        "side": "SELL",  # exit of a LONG row
        "qty": 0.5,
        "realized_pnl": 5.0,  # (2010 - 2000) * 0.5
        "commission": 0.1,
        "fills": 1,
        "first_fill_time": BASE_MS - 60_000,
        "last_fill_time": BASE_MS,
    }
    close.update(overrides)
    return close


def _report(date, orders):
    return {
        "date": date,
        "status": "RECONCILED",
        "ledger": {"rows": 80, "net_pnl": 138.75, "rows_without_order_id": 69},
        "forward_window": {
            "fills": 80,
            "ledger_net_pnl": 138.7507,
            "closes_on_venue": 80,
            "venue_true_net_pnl": 154.68,
        },
        "window_identity": {"status": "RECONCILED", "residual": 0.0},
        "matching": {"classes": {"BOTH": 70, "NO_MATCH": 10}},
        "missing_closes": {
            "count": len(orders),
            "realized_pnl": round(sum(o["realized_pnl"] for o in orders), 4),
            "orders": orders,
        },
        "unmatched_zero_realized_fills": {"count": 0, "orders": []},
    }


def test_exact_match_is_matched_with_price_ok():
    verdict = g1.match_close(_close(), [_row()])
    assert verdict["verdict"] == "MATCHED"
    assert verdict["matched_row"]["price_ok"] is True
    assert verdict["matched_row"]["implied_exit_price"] == pytest.approx(2010.0)
    assert verdict["matched_row"]["order_id"] == "OID-1"


def test_short_close_uses_buy_side_and_inverted_implied_exit():
    row = _row(side="SHORT", entry_price=2010.0, exit_price=2000.0)
    close = _close(side="BUY", realized_pnl=5.0)  # (2010 - 2000) * 0.5
    verdict = g1.match_close(close, [row])
    assert verdict["verdict"] == "MATCHED"
    assert verdict["matched_row"]["implied_exit_price"] == pytest.approx(2000.0)


def test_price_mismatch_is_a_finding_not_a_match():
    # Realized P&L implies an exit of 2024, the row says 2010: a 14 USDT
    # gap, beyond the 0.5% price tolerance (10.05 USDT at this price).
    close = _close(realized_pnl=12.0)
    verdict = g1.match_close(close, [_row()])
    assert verdict["verdict"] == "MATCHED_PRICE_MISMATCH"
    assert verdict["matched_row"]["price_ok"] is False
    assert verdict["matched_row"]["price_diff"] == pytest.approx(14.0)


def test_two_candidates_is_ambiguous():
    rows = [_row(order_id="OID-1"), _row(order_id="OID-2")]
    verdict = g1.match_close(_close(), rows)
    assert verdict["verdict"] == "AMBIGUOUS"
    assert len(verdict["candidates"]) == 2


def test_no_candidate_is_genuine_gap():
    verdict = g1.match_close(_close(), [_row(symbol="BTCUSDT")])
    assert verdict["verdict"] == "GENUINE_GAP"
    assert verdict["candidates"] == []


def test_oanda_and_open_rows_are_skipped():
    rows = [
        _row(venue="oanda", symbol="USDJPY"),
        _row(exit_time=0.0, order_id="OID-OPEN"),
    ]
    verdict = g1.match_close(_close(), rows)
    assert verdict["verdict"] == "GENUINE_GAP"


def test_fallback_time_row_surfaces_as_time_miss():
    # Same symbol/side/qty, but the row's exit is an hour off: a
    # fallback-time row matches nothing by design; the delta is filed.
    row = _row(exit_time=(BASE_MS - 3_600_000) / 1000.0)
    verdict = g1.match_close(_close(), [row])
    assert verdict["verdict"] == "GENUINE_GAP"
    assert verdict["time_miss_nearest"]
    assert verdict["time_miss_nearest"][0]["dt_ms"] == 3_540_000


def test_reconcile_sums_arithmetic_and_counts():
    report = _report("2026-11-24", [_close(), _close(order_id="1002", symbol="BTCUSDT")])
    out = g1.reconcile_missing_closes([_row()], report)
    assert out["missing_count"] == 2
    assert out["arithmetic_ok"] is True
    assert out["reported_realized_pnl"] == pytest.approx(10.0)
    assert out["verdict_counts"] == {"MATCHED": 1, "GENUINE_GAP": 1}
    assert out["genuine_gap_realized_pnl"] == pytest.approx(5.0)


def test_compare_reports_q1_deltas():
    a = _report("2026-11-23", [_close()])
    b = _report("2026-11-24", [_close(), _close(order_id="1002")])
    b["forward_window"]["ledger_net_pnl"] = 138.7507
    a["forward_window"]["ledger_net_pnl"] = 160.6847
    out = g1.compare_reports(a, b)
    assert out["missing_count_delta"] == 1
    assert out["missing_realized_delta"] == pytest.approx(5.0)
    assert out["window_net_delta"] == pytest.approx(-21.934)
    assert out["report_a"]["date"] == "2026-11-23"
    assert out["report_b"]["date"] == "2026-11-24"


def test_main_end_to_end_on_synthetic_files(tmp_path):
    ledger = tmp_path / "fill_ledger.jsonl"
    ledger.write_text(
        "\n".join(json.dumps(_row()) for _ in range(1)) + "\n", encoding="utf-8"
    )
    r23 = tmp_path / "daily_2026-11-23.json"
    r24 = tmp_path / "daily_2026-11-24.json"
    r23.write_text(json.dumps(_report("2026-11-23", [])), encoding="utf-8")
    r24.write_text(json.dumps(_report("2026-11-24", [_close()])), encoding="utf-8")
    out = tmp_path / "out.json"
    rc = g1.main(
        [
            "--ledger", str(ledger),
            "--report-1123", str(r23),
            "--report-1124", str(r24),
            "--out", str(out),
        ]
    )
    assert rc == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["task"] == "TASK-STR-051-FIX-01"
    assert result["ledger_rows"] == 1
    assert result["day_1124"]["verdict_counts"] == {"MATCHED": 1}


def test_main_missing_input_exits_2(tmp_path):
    rc = g1.main(
        [
            "--ledger", str(tmp_path / "nope.jsonl"),
            "--report-1123", str(tmp_path / "nope23.json"),
            "--report-1124", str(tmp_path / "nope24.json"),
        ]
    )
    assert rc == 2
