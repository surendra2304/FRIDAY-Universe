"""
reporting/tax_ledger_export.py — Tax-ready trade-ledger export (TASK-IG2-STR-09).

Pattern adopted from the claude-trading-skills catalogue (agiprolabs, MIT;
its tax/compliance skill family): generate a per-trade tax/compliance
export from Stratex's existing fill ledger on demand.

Reads the canonical demo/testnet fill ledger (``testnet_trade_ledger.jsonl``,
path overridable via ``TESTNET_LEDGER_FILE`` — the same env the engine and
dashboard use) and/or the live ledger (``live_trade_ledger.jsonl``), and
emits:

- a CSV with one row per closed trade: open/close timestamps (UTC ISO),
  venue, instrument, side, quantity, entry/exit price, proceeds, cost
  basis, fees, gross and realised (net) P&L, currency, strategy, order ids;
- a summary dict/JSON: row count, totals per venue / instrument / tax year,
  total fees and total realised P&L.

Honest scope note: this is a *per-trade realised-P&L* export taken straight
from the ledger's own recorded figures. It is NOT a FIFO/LIFO lot-matching
engine and not tax advice — it gives an accountant (or future tax tooling)
a clean, complete, auditable trail instead of one reconstructed after the
fact. Stratex is DEMO-ONLY; the export works identically for demo fills.

CLI:
    python -m reporting.tax_ledger_export --ledger testnet_trade_ledger.jsonl \
        --out tax_export.csv --summary tax_export_summary.json [--year 2026]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

try:
    from logger import get_logger
except Exception:  # pragma: no cover
    import logging

    def get_logger(name: str):  # type: ignore
        return logging.getLogger(name)


logger = get_logger("tax_ledger_export")

CSV_COLUMNS = [
    "trade_id", "date_open", "date_close", "venue", "instrument", "side",
    "quantity", "entry_price", "exit_price", "proceeds", "cost_basis",
    "fees", "gross_pnl", "realized_pnl", "currency", "strategy",
    "entry_order_id", "exit_order_id", "exit_reason",
]

_QUOTE_SUFFIXES = ("USDT", "USDC", "BUSD", "USD", "EUR", "GBP", "JPY", "BTC", "ETH")

_VENUE_BY_SOURCE_MARKER = (
    ("BINANCE", "Binance"),
    ("OANDA", "OANDA"),
    ("MT5", "MT5"),
    ("PAPER", "Paper"),
    ("TESTNET", "Testnet"),
)


def split_instrument(symbol: str) -> tuple[str, str]:
    """Split 'SOLUSDT' -> ('SOL', 'USDT'); 'USDJPY' -> ('USD', 'JPY')."""
    sym = (symbol or "").upper().replace("/", "").replace("-", "")
    for quote in _QUOTE_SUFFIXES:
        if sym.endswith(quote) and len(sym) > len(quote):
            return sym[: -len(quote)], quote
    return sym, ""


def venue_from_source(source: str) -> str:
    text = (source or "").upper()
    for marker, venue in _VENUE_BY_SOURCE_MARKER:
        if marker in text:
            return venue
    return (source or "Unknown").strip() or "Unknown"


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _epoch_to_iso(value: Any) -> str:
    """Convert an epoch timestamp (seconds, or ms when >= 1e12) to UTC ISO.

    Accepts an int/float/str epoch, or an already-ISO string (passed
    through). Returns "" for missing/unparseable values.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        text = value.strip()
        # Already ISO (e.g. "2026-09-09T15:52:32Z" or with offset).
        if "T" in text or "-" in text[4:5]:
            return text
        try:
            value = float(text)
        except ValueError:
            return ""
    try:
        epoch = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(epoch) >= 1e12:  # epoch milliseconds
        epoch /= 1000.0
    if epoch <= 0:  # 0.0 means "unset" in the daemon ledger — not 1970
        return ""
    try:
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return ""


def _derived_trade_id(rec: dict[str, Any]) -> str:
    """Stable export id for daemon records that carry no order id.

    Deterministic hash of the record's identifying fields, so the same
    ledger always exports the same id. Prefixed to make clear it is
    export-derived, not a venue order id.
    """
    canonical = {
        "symbol": rec.get("symbol"),
        "entry_time": rec.get("entry_time"),
        "exit_time": rec.get("exit_time"),
        "recorded_at": rec.get("recorded_at"),
        "side": rec.get("side") or rec.get("direction") or rec.get("action"),
        "qty": rec.get("qty") if rec.get("qty") is not None else rec.get("quantity"),
        "entry_price": rec.get("entry_price"),
        "exit_price": rec.get("exit_price"),
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()
    return f"LEDGER-{digest[:12]}"


def _venue(rec: dict[str, Any]) -> str:
    """Venue for a record: explicit `venue` wins, else derive from `source`.

    The live daemon ledger carries `venue: "binance_futures"`; the testnet
    shape carries only `source` (e.g. "BINANCE_FUTURES_EXECUTION").
    """
    explicit = str(rec.get("venue") or "").strip()
    if explicit:
        return venue_from_source(explicit)
    return venue_from_source(str(rec.get("source") or ""))


def build_tax_rows(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize raw ledger records into tax-export rows (pure function).

    Ledger rows are closed trades. Two shapes are accepted:

    - testnet shape: symbol, order_id/exit_order_id, action, direction,
      quantity, entry_price, exit_price, gross_pnl, net_pnl, fees,
      timestamp, exit_timestamp, exit_reason, strategy, source.
    - live daemon shape (TASK-STR-107): symbol, order_id (often empty),
      entry_order_id (sometimes set), qty, entry_price, exit_price,
      gross_pnl, net_pnl, fees, epoch entry_time/exit_time
      (+ ISO recorded_at), venue ("binance_futures"), side ("SHORT"/"LONG"),
      exit_reason, strategy. Daemon records carry no trade_id/exit_order_id,
      so trade_id falls back to order_id/entry_order_id, then to a
      deterministic export-derived id (see _derived_trade_id).
    """
    rows: list[dict[str, Any]] = []
    for rec in records:
        symbol = str(rec.get("symbol") or "")
        if not symbol:
            continue  # not a trade record (e.g. balance/risk event rows)
        # Daemon ledger uses `qty`; testnet uses `quantity`.
        qty_raw = rec.get("quantity") if rec.get("quantity") is not None \
            else rec.get("qty")
        quantity = abs(_f(qty_raw))
        entry_price = _f(rec.get("entry_price"))
        exit_price = _f(rec.get("exit_price"))
        fees = abs(_f(rec.get("fees")))
        gross = _f(rec.get("gross_pnl", rec.get("pnl")))
        # Prefer the ledger's own net figure; otherwise derive it.
        net = _f(rec.get("net_pnl"), default=gross - fees) \
            if rec.get("net_pnl") is not None else gross - fees
        _, currency = split_instrument(symbol)
        # Dates: testnet ISO timestamps, else daemon epoch entry/exit time.
        date_open = str(rec.get("timestamp") or "") \
            or _epoch_to_iso(rec.get("entry_time"))
        date_close = str(rec.get("exit_timestamp") or "") \
            or _epoch_to_iso(rec.get("exit_time")) \
            or str(rec.get("recorded_at") or "") \
            or str(rec.get("timestamp") or "")
        trade_id = str(rec.get("trade_id") or rec.get("exit_order_id")
                       or rec.get("order_id") or rec.get("entry_order_id")
                       or "")
        if not trade_id:
            trade_id = _derived_trade_id(rec)
        rows.append({
            "trade_id": trade_id,
            "date_open": date_open,
            "date_close": date_close,
            "venue": _venue(rec),
            "instrument": symbol,
            "side": str(rec.get("side") or rec.get("direction")
                        or rec.get("action") or "").upper(),
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "proceeds": round(quantity * exit_price, 8),
            "cost_basis": round(quantity * entry_price, 8),
            "fees": round(fees, 8),
            "gross_pnl": round(gross, 8),
            "realized_pnl": round(net, 8),
            "currency": currency,
            "strategy": str(rec.get("strategy") or ""),
            "entry_order_id": str(rec.get("order_id") or ""),
            "exit_order_id": str(rec.get("exit_order_id") or ""),
            "exit_reason": str(rec.get("exit_reason") or ""),
        })
    rows.sort(key=lambda r: (r["date_close"], r["trade_id"]))
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate totals per venue / instrument / tax year (pure function)."""
    def _bucket(key_fn):
        out: dict[str, dict[str, float]] = {}
        for row in rows:
            key = key_fn(row) or "Unknown"
            bucket = out.setdefault(key, {"trades": 0, "fees": 0.0, "realized_pnl": 0.0})
            bucket["trades"] += 1
            bucket["fees"] = round(bucket["fees"] + row["fees"], 8)
            bucket["realized_pnl"] = round(bucket["realized_pnl"] + row["realized_pnl"], 8)
        return out

    return {
        "trades": len(rows),
        "total_fees": round(sum(r["fees"] for r in rows), 8),
        "total_realized_pnl": round(sum(r["realized_pnl"] for r in rows), 8),
        "by_venue": _bucket(lambda r: r["venue"]),
        "by_instrument": _bucket(lambda r: r["instrument"]),
        "by_year": _bucket(lambda r: (r["date_close"] or "")[:4]),
        "method_note": ("Per-trade realised P&L as recorded in Stratex's fill "
                        "ledger; not FIFO/LIFO lot matching; not tax advice."),
    }


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})
    return buf.getvalue()


def load_ledger_records(path: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # skip corrupt lines, never abort an export
    return records


def export_tax_ledger(ledger_path: Optional[str] = None,
                      year: Optional[int] = None,
                      venue: Optional[str] = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load a ledger, build rows, apply optional year/venue filters."""
    path = ledger_path or os.getenv("TESTNET_LEDGER_FILE", "testnet_trade_ledger.jsonl")
    rows = build_tax_rows(load_ledger_records(path))
    if year is not None:
        rows = [r for r in rows if (r["date_close"] or "").startswith(str(year))]
    if venue:
        rows = [r for r in rows if r["venue"].lower() == venue.lower()]
    return rows, summarize(rows)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Tax-ready Stratex trade-ledger export")
    parser.add_argument("--ledger", default=None,
                        help="Ledger JSONL path (default: $TESTNET_LEDGER_FILE or "
                             "testnet_trade_ledger.jsonl)")
    parser.add_argument("--out", default="tax_export.csv", help="CSV output path")
    parser.add_argument("--summary", default=None, help="Summary JSON output path")
    parser.add_argument("--year", type=int, default=None, help="Only this tax year")
    parser.add_argument("--venue", default=None, help="Only this venue (e.g. Binance)")
    args = parser.parse_args(argv)

    rows, summary = export_tax_ledger(args.ledger, year=args.year, venue=args.venue)
    with open(args.out, "w", encoding="utf-8", newline="") as fh:
        fh.write(rows_to_csv(rows))
    summary_path = args.summary or (args.out + ".summary.json")
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    logger.info(f"[TAX_EXPORT] {summary['trades']} trades -> {args.out} "
                f"(fees {summary['total_fees']}, realised {summary['total_realized_pnl']})")
    print(f"{summary['trades']} trades exported to {args.out}; summary in {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
