"""TASK-IG2-STR-09 — tax-ready trade-ledger export tests."""

import calendar
import json
from datetime import datetime

import pytest

from reporting.tax_ledger_export import (
    CSV_COLUMNS,
    build_tax_rows,
    export_tax_ledger,
    rows_to_csv,
    split_instrument,
    summarize,
    venue_from_source,
)

# Shape mirrors the real testnet_trade_ledger.jsonl rows.
RECORDS = [
    {"symbol": "SOLUSDT", "order_id": "111", "exit_order_id": "111", "action": "BUY",
     "direction": "SHORT", "quantity": 1.84, "exit_price": 103.17, "gross_pnl": 0.5696,
     "pnl": 0.5696, "net_pnl": 0.4937, "fees": 0.0759,
     "timestamp": "2026-09-09T15:52:32.268000Z", "exit_timestamp": "2026-09-09T15:52:32.268000Z",
     "exit_reason": "WIN", "strategy": "SUPERTREND", "source": "BINANCE_FUTURES_EXECUTION",
     "entry_price": 103.4796},
    {"symbol": "USDJPY", "order_id": "222", "exit_order_id": "223", "action": "BUY",
     "direction": "LONG", "quantity": 15, "exit_price": 161.0, "gross_pnl": 20.0,
     "net_pnl": 19.5, "fees": 0.5, "timestamp": "2026-11-15T22:09:05Z",
     "exit_timestamp": "2026-11-16T01:00:00Z", "exit_reason": "TP",
     "strategy": "SLEEVE", "source": "OANDA_DEMO", "entry_price": 159.691},
    {"event": "balance_snapshot", "equity": 10000},  # non-trade row: skipped
    {"symbol": "BTCUSDT", "order_id": "333", "direction": "LONG", "quantity": 0.01,
     "entry_price": 90000.0, "exit_price": 91000.0, "gross_pnl": 10.0,
     "timestamp": "2025-12-31T00:00:00Z", "exit_timestamp": "2025-12-31T01:00:00Z",
     "source": "BINANCE_SPOT"},  # no fees/net_pnl recorded -> derived
]


def test_split_instrument():
    assert split_instrument("SOLUSDT") == ("SOL", "USDT")
    assert split_instrument("USDJPY") == ("USD", "JPY")
    assert split_instrument("ETHBTC") == ("ETH", "BTC")
    assert split_instrument("") == ("", "")


def test_venue_from_source():
    assert venue_from_source("BINANCE_FUTURES_EXECUTION") == "Binance"
    assert venue_from_source("OANDA_DEMO") == "OANDA"
    assert venue_from_source("") == "Unknown"


def test_build_tax_rows_normalizes_and_skips_non_trades():
    rows = build_tax_rows(RECORDS)
    assert len(rows) == 3
    sol = next(r for r in rows if r["instrument"] == "SOLUSDT")
    assert sol["venue"] == "Binance" and sol["currency"] == "USDT"
    assert sol["realized_pnl"] == 0.4937 and sol["fees"] == 0.0759
    assert sol["side"] == "SHORT" and sol["strategy"] == "SUPERTREND"
    fx = next(r for r in rows if r["instrument"] == "USDJPY")
    assert fx["venue"] == "OANDA" and fx["currency"] == "JPY"
    btc = next(r for r in rows if r["instrument"] == "BTCUSDT")
    assert btc["fees"] == 0.0 and btc["realized_pnl"] == 10.0  # derived gross - fees
    # Sorted by close time: BTC (2025) first.
    assert rows[0]["instrument"] == "BTCUSDT"


def test_summarize_buckets():
    summary = summarize(build_tax_rows(RECORDS))
    assert summary["trades"] == 3
    assert summary["total_fees"] == pytest.approx(0.5759)
    assert summary["total_realized_pnl"] == pytest.approx(29.9937)
    assert summary["by_venue"]["Binance"]["trades"] == 2
    assert summary["by_year"]["2025"]["trades"] == 1
    assert "not tax advice" in summary["method_note"]


def test_csv_has_stable_columns_and_rows():
    text = rows_to_csv(build_tax_rows(RECORDS))
    lines = text.strip().splitlines()
    assert lines[0].split(",") == CSV_COLUMNS
    assert len(lines) == 4  # header + 3 trades


def test_export_from_file_with_filters(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in RECORDS) + "\nnot-json\n")
    rows, summary = export_tax_ledger(str(ledger), year=2026, venue="Binance")
    assert [r["instrument"] for r in rows] == ["SOLUSDT"]
    assert summary["trades"] == 1


# TASK-STR-107 — live daemon ledger shape (Muse 3 checkpoint 3, hub
# 7231107638): `qty` not `quantity`, epoch `entry_time`/`exit_time`,
# explicit `venue`, `side`, and usually an empty `order_id`.
def _epoch(iso: str) -> int:
    return calendar.timegm(
        datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").timetuple())


DAEMON_RECORDS = [
    {"symbol": "SOLUSDT", "order_id": "", "side": "SHORT", "qty": 1.84,
     "entry_price": 103.4796, "exit_price": 103.17, "gross_pnl": 0.5696,
     "net_pnl": 0.4937, "fees": 0.0759,
     "entry_time": _epoch("2026-11-27T02:20:00Z"),
     "exit_time": _epoch("2026-11-27T02:26:00Z"),
     "recorded_at": "2026-11-27T02:26:00Z", "exit_reason": "WIN",
     "strategy": "SUPERTREND", "venue": "binance_futures"},
    {"symbol": "USDJPY", "order_id": "999", "side": "LONG", "qty": 15,
     "entry_price": 159.691, "exit_price": 161.0, "gross_pnl": 20.0,
     "net_pnl": 19.5, "fees": 0.5,
     "entry_time": _epoch("2026-11-15T22:09:05Z"),
     "exit_time": _epoch("2026-11-16T01:00:00Z"),
     "recorded_at": "2026-11-16T01:00:00Z", "exit_reason": "TP",
     "strategy": "SLEEVE", "venue": "binance_futures"},
]


def test_trade_id_prefers_entry_order_id():
    rec = dict(DAEMON_RECORDS[0], entry_order_id="4245510187")
    row = build_tax_rows([rec])[0]
    assert row["trade_id"] == "4245510187"


def test_build_tax_rows_daemon_shape():
    rows = build_tax_rows(DAEMON_RECORDS)
    assert len(rows) == 2
    sol = next(r for r in rows if r["instrument"] == "SOLUSDT")
    # The 6 columns that were empty/zero on live daemon records.
    assert sol["quantity"] == 1.84
    assert sol["proceeds"] == round(1.84 * 103.17, 8)
    assert sol["cost_basis"] == round(1.84 * 103.4796, 8)
    assert sol["date_open"] == "2026-11-27T02:20:00Z"
    assert sol["date_close"] == "2026-11-27T02:26:00Z"
    assert sol["venue"] == "Binance"
    assert sol["side"] == "SHORT"
    assert sol["trade_id"].startswith("LEDGER-") and len(sol["trade_id"]) > 7
    # Derived id is stable across runs.
    again = build_tax_rows(DAEMON_RECORDS)
    sol2 = next(r for r in again if r["instrument"] == "SOLUSDT")
    assert sol2["trade_id"] == sol["trade_id"]
    fx = next(r for r in rows if r["instrument"] == "USDJPY")
    assert fx["trade_id"] == "999"  # present order_id still wins
    assert fx["date_close"] == "2026-11-16T01:00:00Z"
    assert fx["venue"] == "Binance" and fx["side"] == "LONG"


def test_export_daemon_shape_year_filter(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in DAEMON_RECORDS) + "\n")
    rows, summary = export_tax_ledger(str(ledger), year=2026)
    assert len(rows) == 2  # --year 2026 returned 0 trades before the fix
    assert summary["by_year"]["2026"]["trades"] == 2
    rows25, _ = export_tax_ledger(str(ledger), year=2025)
    assert rows25 == []


def test_daemon_and_testnet_shapes_mix():
    rows = build_tax_rows(RECORDS + DAEMON_RECORDS)
    assert len(rows) == 5
    assert sum(1 for r in rows if r["venue"] == "Binance") == 4
    assert all(r["date_close"] for r in rows)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
