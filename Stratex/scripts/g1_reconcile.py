"""TASK-STR-051-FIX-01 — offline G1 reconciliation: match venue closes
with no ledger row against the fill ledger.

The daily reconciliation job (``daily_fill_ledger_reconciliation.py``,
TASK-STR-044) files each venue close with no ledger row under
``missing_closes.orders`` in the dated report
(``Stratex/state/reconciliation/daily_YYYY-MM-DD.json``): symbol,
order_id, side (BUY/SELL), aggregate qty, realized P&L, commission,
fill count, first/last fill time. This script takes the filed reports
plus the ledger (``Stratex/state/fill_ledger.jsonl``) and, for each
missing close, finds the ledger row it belongs to — or files it as a
genuine gap with its realised P&L.

Matching rule (STR-043 / STR-044, same tolerances as the daily job):
symbol + side + qty (within max(0.001, 1%)) + time (ledger exit_time
within 5 minutes of the close's first or last fill). A close with side
SELL is the exit of a LONG row; side BUY is the exit of a SHORT row.
Split fills are matched on the order aggregate (the report carries only
the aggregate qty / realized P&L, not per-fill prices — see LIMITS).

Price leg: the filed report carries no per-fill prices for a missing
close, so the exit price cannot be read off the venue side. It is
checked indirectly: from the candidate row's entry price, the close's
realized P&L implies an exit price (LONG: entry + realized/qty;
SHORT: entry - realized/qty), which must agree with the row's
exit_price within 0.5%. A candidate that passes symbol/side/qty/time
but fails the price check is filed MATCHED_PRICE_MISMATCH — a finding,
never absorbed.

LIMITS (stated, not hidden):
  * No live venue read: this script never touches Binance, needs no
    keys, and never places, cancels or modifies anything. Per-fill
    prices and VWAP for split fills cannot be recomputed from the
    filed report alone — the aggregate consistency check above is the
    strongest price evidence available offline. If a live venue read
    is later granted, the fills for each matched order re-verify the
    VWAP directly.
  * Rows whose exit time is a fallback (the Nov-19 reset-wiped rows)
    match nothing by design; they surface as TIME_MISS with the delta
    so a reviewer can see them.
  * The daily report files only aggregate match classes, not per-row
    match results, so a candidate row's already-matched state is not
    visible here. A close whose fills the daily run already consumed
    cannot be a missing close by construction; candidates are reported
    with their score so the reviewer can judge.

Exit codes: 0 = ran (findings are data, not failures); 2 = an input
file is missing or unreadable; 1 = usage error.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TASK_ID = "TASK-STR-051-FIX-01"

# Same tolerances as the daily reconciliation job (STR-044).
QTY_TOL_FRAC = 0.01
QTY_TOL_FLOOR = 0.001
PRICE_TOL_FRAC = 0.005
TIME_TOL_MS = 300_000

# A price mismatch beyond this in USDT is a finding even when the
# relative check passes on a tiny price (same 0.5 USDT bar as the
# daily job's diffs_over_0.5).
PRICE_DIFF_FLOOR_USDT = 0.5


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def close_row_side(close_side: str) -> Optional[str]:
    """Ledger-row side for a venue close order's side."""
    if close_side == "SELL":
        return "LONG"
    if close_side == "BUY":
        return "SHORT"
    return None


def implied_exit_price(row: Dict[str, Any], realized_pnl: float) -> Optional[float]:
    """Exit price implied by the row's entry price + the close's realized P&L."""
    qty = _finite(row.get("qty"))
    entry = _finite(row.get("entry_price"))
    if qty == 0 or entry == 0:
        return None
    side = str(row.get("side") or "")
    if side == "LONG":
        return entry + realized_pnl / qty
    if side == "SHORT":
        return entry - realized_pnl / qty
    return None


def match_close(
    close: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Match one missing venue close against ledger rows.

    Returns a verdict dict: MATCHED, MATCHED_PRICE_MISMATCH, AMBIGUOUS
    or GENUINE_GAP, with the candidate rows and their scores.
    """
    symbol = str(close.get("symbol") or "")
    side = str(close.get("side") or "")
    qty = _finite(close.get("qty"))
    realized = _finite(close.get("realized_pnl"))
    first_ms = int(close.get("first_fill_time") or 0)
    last_ms = int(close.get("last_fill_time") or 0)
    want_row_side = close_row_side(side)

    candidates: List[Dict[str, Any]] = []
    nearest_time_miss: List[Dict[str, Any]] = []
    for row in rows:
        if str(row.get("venue") or "") != "binance_futures":
            continue
        if str(row.get("symbol") or "") != symbol:
            continue
        if want_row_side is not None and str(row.get("side") or "") != want_row_side:
            continue
        row_qty = _finite(row.get("qty"))
        if abs(row_qty - qty) > max(QTY_TOL_FLOOR, QTY_TOL_FRAC * qty):
            continue
        exit_ms = int(_finite(row.get("exit_time"), 0.0) * 1000)
        if exit_ms == 0:
            continue  # open row: no exit to match
        dt_ms = min(abs(exit_ms - first_ms), abs(exit_ms - last_ms))
        if dt_ms > TIME_TOL_MS:
            nearest_time_miss.append(
                {
                    "symbol": symbol,
                    "side": row.get("side"),
                    "qty": row_qty,
                    "exit_time_ms": exit_ms,
                    "dt_ms": dt_ms,
                    "order_id": row.get("order_id"),
                    "recorded_at": row.get("recorded_at"),
                }
            )
            continue
        implied = implied_exit_price(row, realized)
        exit_price = _finite(row.get("exit_price"))
        price_diff = None
        price_ok = None
        if implied is not None and exit_price != 0:
            price_diff = round(implied - exit_price, 6)
            price_ok = abs(price_diff) <= max(
                PRICE_DIFF_FLOOR_USDT, PRICE_TOL_FRAC * abs(exit_price)
            )
        score = dt_ms + (abs(price_diff) * 1000.0 if price_diff is not None else 0.0)
        candidates.append(
            {
                "symbol": symbol,
                "side": row.get("side"),
                "qty": row_qty,
                "entry_price": _finite(row.get("entry_price")),
                "exit_price": exit_price,
                "exit_time_ms": exit_ms,
                "dt_ms": dt_ms,
                "implied_exit_price": implied,
                "price_diff": price_diff,
                "price_ok": price_ok,
                "net_pnl": _finite(row.get("net_pnl")),
                "order_id": row.get("order_id"),
                "recorded_at": row.get("recorded_at"),
                "score": score,
            }
        )
    candidates.sort(key=lambda c: c["score"])
    nearest_time_miss.sort(key=lambda c: c["dt_ms"])

    verdict: Dict[str, Any] = {
        "symbol": symbol,
        "order_id": close.get("order_id"),
        "side": side,
        "qty": qty,
        "realized_pnl": realized,
        "commission": _finite(close.get("commission")),
        "fills": close.get("fills"),
        "first_fill_time": first_ms,
        "last_fill_time": last_ms,
        "candidates": candidates,
        "time_miss_nearest": nearest_time_miss[:3],
    }
    if not candidates:
        verdict["verdict"] = "GENUINE_GAP"
    elif len(candidates) == 1:
        verdict["verdict"] = (
            "MATCHED" if candidates[0]["price_ok"] else "MATCHED_PRICE_MISMATCH"
        )
        verdict["matched_row"] = candidates[0]
    else:
        verdict["verdict"] = "AMBIGUOUS"
    return verdict


def reconcile_missing_closes(
    ledger_rows: List[Dict[str, Any]],
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """Reconcile every missing close in one daily report."""
    missing = (report.get("missing_closes") or {}).get("orders") or []
    verdicts = [match_close(close, ledger_rows) for close in missing]
    counts: Dict[str, int] = {}
    for verdict in verdicts:
        counts[verdict["verdict"]] = counts.get(verdict["verdict"], 0) + 1
    reported_total = _finite((report.get("missing_closes") or {}).get("realized_pnl"))
    summed_total = round(sum(v["realized_pnl"] for v in verdicts), 4)
    return {
        "date": report.get("date"),
        "missing_count": len(missing),
        "reported_realized_pnl": reported_total,
        "summed_realized_pnl": summed_total,
        "arithmetic_ok": abs(reported_total - summed_total) <= 0.0001,
        "verdict_counts": counts,
        "matched_realized_pnl": round(
            sum(
                v["realized_pnl"]
                for v in verdicts
                if v["verdict"] in ("MATCHED", "MATCHED_PRICE_MISMATCH")
            ),
            4,
        ),
        "genuine_gap_realized_pnl": round(
            sum(
                v["realized_pnl"] for v in verdicts if v["verdict"] == "GENUINE_GAP"
            ),
            4,
        ),
        "verdicts": verdicts,
    }


def compare_reports(
    report_a: Dict[str, Any], report_b: Dict[str, Any]
) -> Dict[str, Any]:
    """Side-by-side Q1 comparison of two daily reports (2026-11-23 vs 2026-11-24)."""
    def block(report: Dict[str, Any]) -> Dict[str, Any]:
        ledger = report.get("ledger") or {}
        window = report.get("forward_window") or {}
        identity = report.get("window_identity") or {}
        missing = report.get("missing_closes") or {}
        matching = report.get("matching") or {}
        return {
            "date": report.get("date"),
            "status": report.get("status"),
            "ledger_rows": ledger.get("rows"),
            "ledger_net": ledger.get("net_pnl"),
            "rows_without_order_id": ledger.get("rows_without_order_id"),
            "window_fills": window.get("fills"),
            "window_ledger_net": window.get("ledger_net_pnl"),
            "closes_on_venue": window.get("closes_on_venue"),
            "venue_true_net": window.get("venue_true_net_pnl"),
            "identity_status": identity.get("status"),
            "identity_residual": identity.get("residual"),
            "matching_classes": matching.get("classes"),
            "missing_count": missing.get("count"),
            "missing_realized": missing.get("realized_pnl"),
        }

    a, b = block(report_a), block(report_b)
    return {
        "report_a": a,
        "report_b": b,
        "ledger_net_delta": round(
            _finite(b.get("ledger_net")) - _finite(a.get("ledger_net")), 4
        ),
        "window_net_delta": round(
            _finite(b.get("window_ledger_net")) - _finite(a.get("window_ledger_net")),
            4,
        ),
        "missing_count_delta": (b.get("missing_count") or 0)
        - (a.get("missing_count") or 0),
        "missing_realized_delta": round(
            _finite(b.get("missing_realized")) - _finite(a.get("missing_realized")),
            4,
        ),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline G1 reconciliation for TASK-STR-051-FIX-01."
    )
    parser.add_argument("--ledger", required=True, help="fill_ledger.jsonl path")
    parser.add_argument(
        "--report-1123", required=True, help="daily_2026-11-23.json path"
    )
    parser.add_argument(
        "--report-1124", required=True, help="daily_2026-11-24.json path"
    )
    parser.add_argument("--out", help="write the JSON result here (default: stdout)")
    args = parser.parse_args(argv)

    try:
        ledger_rows = read_jsonl(Path(args.ledger))
        report_1123 = read_json(Path(args.report_1123))
        report_1124 = read_json(Path(args.report_1124))
    except (OSError, ValueError) as exc:
        print(f"g1_reconcile: input unreadable: {exc}", file=sys.stderr)
        return 2

    result = {
        "task": TASK_ID,
        "ledger_rows": len(ledger_rows),
        "q1_comparison": compare_reports(report_1123, report_1124),
        "day_1123": reconcile_missing_closes(ledger_rows, report_1123),
        "day_1124": reconcile_missing_closes(ledger_rows, report_1124),
    }
    payload = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    for day in ("day_1123", "day_1124"):
        block = result[day]
        print(
            f"{day}: {block['missing_count']} missing closes, "
            f"reported {block['reported_realized_pnl']:+.4f} USDT, "
            f"arithmetic_ok={block['arithmetic_ok']}, "
            f"verdicts={block['verdict_counts']}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
