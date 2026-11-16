"""TASK-IG2-STR-09 — tax-ready trade-ledger export tests."""

import json

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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
