"""Daily Stratex fill-ledger reconciliation job (TASK-STR-044).

Reconciles the daemon's append-only fill/close ledger
(``Stratex/state/fill_ledger.jsonl``) against the venue's own record
(Binance Demo Futures, ``demo-fapi.binance.com``) once a day and files
the fills, closes and net P&L evidence for the forward window as a dated
JSON report in ``Stratex/state/reconciliation/daily_YYYY-MM-DD.json``.

This is the recurring form of the one-off verification in
``docs/collaboration/TASK-STR-LEDGER-001-FILL-LEDGER-VERIFICATION.md``
(STR-LEDGER-001, merged PR #1350): same method, automated —

  * ledger read end to end (all rows; forward-window slice),
  * venue read with signed GETs only (account, open positions, user
    trades, income, all orders),
  * row-by-row match (side, qty, VWAP, time) into BOTH / ENTRY_ONLY /
    EXIT_ONLY / NO_MATCH,
  * venue closes with no ledger row, with their realized P&L,
  * equity walk split at detected faucet resets (a reset wipes open
    positions and re-grants the balance; a single-segment walk across
    one reports a phantom DISCREPANCY — LEDGER-001 section 6),
  * forward-window state filed: fills, closes, net P&L.

Read-only on the venue BY CONSTRUCTION: the venue client below exposes
GET only — there is no POST / DELETE / PUT method anywhere in this
module, and it refuses to run unless ``BINANCE_ENV=demo`` with an
Ed25519 key (the daemon's own signing scheme). It never places,
cancels or modifies an order, never restarts a service, never writes
the ledger — it only appends one dated report file and latches a
measurement alert when a material mismatch is found. Keys are loaded
from the Stratex ``.env`` into memory only and are never printed or
stored.

Schedule: ``Stratex/deployment/friday-stratex-reconciliation.timer``
(daily 01:00 UTC, Persistent), installed by the fleet CD
(``.github/workflows/deploy-monorepo.yml``, S1 job). The timer runs
this file from the deployed checkout; the report lands in the live
state directory, where the forward scorecard and the daemon heartbeat
already live.

Exit codes: 0 = report filed (a DISCREPANCY is a finding, filed plus an
alert latched — it does not fail the job); 2 = venue unreachable or
ledger unreadable, no report filed; 1 = usage error.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# The script lives in Stratex/scripts/; its own package root (Stratex/)
# goes on sys.path so `measurement` imports resolve exactly as they do
# for the daemon and the forward scorecard.
_STRATEX_ROOT = Path(__file__).resolve().parent.parent
if str(_STRATEX_ROOT) not in sys.path:
    sys.path.insert(0, str(_STRATEX_ROOT))

try:
    from measurement.forward_scorecard import (  # type: ignore
        GLOBAL_FORWARD_START,
        GLOBAL_FORWARD_START_ISO,
    )
except Exception:  # pragma: no cover - standalone fallback
    GLOBAL_FORWARD_START_ISO = "2026-11-15T11:29:49+05:30"
    GLOBAL_FORWARD_START = (
        datetime.datetime.fromisoformat(GLOBAL_FORWARD_START_ISO).timestamp()
    )

TASK_ID = "TASK-STR-044"
VENUE_BASE_URL = "https://demo-fapi.binance.com"
# Owner demo-account reset, 2026-11-14T13:03:53Z (LEDGER-001 section 3):
# the income-history floor. Fills before it belong to the retired
# pre-reset account and must not enter the forward reconciliation.
RESET_MS = 1794661433311
FORWARD_WINDOW_START_MS = int(GLOBAL_FORWARD_START * 1000)

# Matching tolerances, as proven in LEDGER-001 (probe8): qty within 1%
# (0.001 floor), price within 0.5%, fill within 5 minutes of the
# ledger's entry/exit time. Rows whose exit time is a fallback (the
# Nov-19 reset-wiped rows) match nothing by design and land NO_MATCH.
QTY_TOL_FRAC = 0.01
QTY_TOL_FLOOR = 0.001
PRICE_TOL_FRAC = 0.005
TIME_TOL_MS = 300_000

# Reconciliation tolerance, same rule as measurement.forward_scorecard:
# max($2.00, 0.1% of baseline equity).
RECON_TOLERANCE_USD = 2.0
RECON_TOLERANCE_FRAC = 0.001

# A venue close whose |realized P&L| is at most this is indistinguishable
# from a breakeven close; it is listed under unmatched fills, not
# counted as a missing close (see find_missing_closes).
MISSING_CLOSE_MIN_ABS_PNL = 0.005


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _iso_utc(ms: float) -> str:
    return datetime.datetime.fromtimestamp(
        ms / 1000.0, datetime.timezone.utc
    ).isoformat()


def _today_ist() -> str:
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime.now(ist).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        return []
    return rows


def summarize_ledger(
    rows: List[Dict[str, Any]], window_start_epoch: float
) -> Dict[str, Any]:
    """Totals for the whole ledger and for the forward window."""
    window_rows = [
        r for r in rows if _finite(r.get("exit_time"), 0.0) >= window_start_epoch
    ]
    by_venue: Dict[str, Dict[str, Any]] = {}
    by_lane: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        venue = str(r.get("venue") or "unknown")
        lane = str(r.get("lane") or "(none)")
        for bucket, key in ((by_venue, venue), (by_lane, lane)):
            entry = bucket.setdefault(key, {"rows": 0, "net_pnl": 0.0})
            entry["rows"] += 1
            entry["net_pnl"] = round(
                entry["net_pnl"] + _finite(r.get("net_pnl")), 4
            )
    window_by_venue: Dict[str, float] = {}
    for r in window_rows:
        venue = str(r.get("venue") or "unknown")
        window_by_venue[venue] = round(
            window_by_venue.get(venue, 0.0) + _finite(r.get("net_pnl")), 4
        )
    return {
        "rows": len(rows),
        "net_pnl": round(sum(_finite(r.get("net_pnl")) for r in rows), 4),
        "gross_pnl": round(sum(_finite(r.get("gross_pnl")) for r in rows), 4),
        "fees": round(sum(_finite(r.get("fees")) for r in rows), 4),
        "window_rows": len(window_rows),
        "window_net_pnl": round(
            sum(_finite(r.get("net_pnl")) for r in window_rows), 4
        ),
        "window_by_venue": window_by_venue,
        "by_venue": by_venue,
        "by_lane": by_lane,
        "symbols": sorted({str(r.get("symbol") or "") for r in rows} - {""}),
        "first_recorded_at": rows[0].get("recorded_at") if rows else None,
        "last_recorded_at": rows[-1].get("recorded_at") if rows else None,
        "rows_without_order_id": sum(
            1 for r in rows if not str(r.get("order_id") or "")
        ),
    }


# ---------------------------------------------------------------------------
# Venue client — signed GETs only (Ed25519), demo only
# ---------------------------------------------------------------------------
def load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip("\"").strip("'")
    return env


class DemoFuturesReader:
    """Read-only Binance Demo Futures client.

    GET only — this class has no POST / DELETE / PUT method and never
    submits anything to the venue. Construction refuses (fail-closed)
    unless the environment is the demo venue with an Ed25519 key and
    live trading is off. Credentials live in memory only.
    """

    def __init__(self, env_file: Path, base_url: str = VENUE_BASE_URL):
        env = load_env_file(env_file)
        if (env.get("BINANCE_ENV", "") or "").strip().lower() != "demo":
            raise PermissionError(
                "refusing: BINANCE_ENV is not demo "
                f"(got {env.get('BINANCE_ENV')!r})"
            )
        if (env.get("BINANCE_KEY_TYPE", "") or "").strip().lower() != "ed25519":
            raise PermissionError(
                "refusing: BINANCE_KEY_TYPE is not ed25519 "
                f"(got {env.get('BINANCE_KEY_TYPE')!r})"
            )
        if (env.get("TRADING_MODE", "") or "").strip().upper() == "LIVE":
            raise PermissionError("refusing: TRADING_MODE is LIVE")
        if (env.get("LIVE_TRADING_ENABLED", "") or "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            raise PermissionError("refusing: LIVE_TRADING_ENABLED is set")
        self.api_key = env.get("BINANCE_API_KEY", "")
        key_path = env.get("BINANCE_PRIVATE_KEY_PATH", "")
        if not self.api_key or not key_path:
            raise PermissionError(
                "refusing: BINANCE_API_KEY / BINANCE_PRIVATE_KEY_PATH missing"
            )
        # Lazy import: the pure reconciliation core (and its tests) must
        # run without the cryptography package installed.
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
        )

        with open(key_path, "rb") as fh:
            self._private_key = load_pem_private_key(fh.read(), password=None)
        self.base_url = base_url
        self._time_offset_ms = 0
        self._sync_time()

    # -- transport (GET only) -------------------------------------------
    def _sync_time(self) -> None:
        with urllib.request.urlopen(
            self.base_url + "/fapi/v1/time", timeout=20
        ) as resp:
            server_time = json.loads(resp.read().decode())["serverTime"]
        self._time_offset_ms = int(server_time) - int(time.time() * 1000)

    def signed_get(self, path: str, params: Optional[Dict[str, Any]] = None):
        query = dict(params or {})
        query["timestamp"] = int(time.time() * 1000) + self._time_offset_ms
        query["recvWindow"] = 5000
        qs = urllib.parse.urlencode(query, doseq=True)
        signature = base64.b64encode(
            self._private_key.sign(qs.encode("utf-8"))
        ).decode("ascii")
        url = (
            f"{self.base_url}{path}?{qs}"
            f"&signature={urllib.parse.quote(signature, safe='')}"
        )
        req = urllib.request.Request(
            url, headers={"X-MBX-APIKEY": self.api_key}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    # -- read endpoints ----------------------------------------------------
    def account(self) -> Dict[str, Any]:
        return self.signed_get("/fapi/v2/account", {})

    def open_positions(self) -> List[Dict[str, Any]]:
        risk = self.signed_get("/fapi/v2/positionRisk", {})
        return [
            p for p in risk if _finite(p.get("positionAmt")) != 0.0
        ]

    def user_trades(self, symbol: str) -> List[Dict[str, Any]]:
        # No startTime: LEDGER-001 proved a startTime-bounded userTrades
        # call silently misses recent fills on demo-fapi (28 missed).
        return self.signed_get(
            "/fapi/v1/userTrades", {"symbol": symbol, "limit": 1000}
        )

    def income(
        self, start_ms: int, income_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"startTime": start_ms, "limit": 1000}
        if income_type:
            params["incomeType"] = income_type
        return self.signed_get("/fapi/v1/income", params)

    def all_orders(self, symbol: str) -> List[Dict[str, Any]]:
        return self.signed_get(
            "/fapi/v1/allOrders", {"symbol": symbol, "limit": 1000}
        )


# ---------------------------------------------------------------------------
# Matching: ledger rows vs venue fills
# ---------------------------------------------------------------------------
def _side_ok(ledger_side: str, trade_side: str, is_entry: bool) -> bool:
    # Entry fill: LONG->BUY, SHORT->SELL. Exit fill: LONG->SELL, SHORT->BUY.
    if ledger_side == "LONG":
        return trade_side == ("BUY" if is_entry else "SELL")
    if ledger_side == "SHORT":
        return trade_side == ("SELL" if is_entry else "BUY")
    return True


def _find_fill(
    row: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    price: float,
    ts_epoch: float,
    is_entry: bool,
) -> Optional[Dict[str, Any]]:
    best = None
    qty = _finite(row.get("qty"))
    for trade in candidates:
        if not _side_ok(str(row.get("side") or ""), str(trade.get("side") or ""), is_entry):
            continue
        if abs(_finite(trade.get("qty")) - qty) > max(QTY_TOL_FLOOR, QTY_TOL_FRAC * qty):
            continue
        if abs(_finite(trade.get("price")) - price) > max(
            1e-9, PRICE_TOL_FRAC * abs(price)
        ):
            continue
        dt_ms = abs(int(trade.get("time") or 0) - int(ts_epoch * 1000))
        if dt_ms > TIME_TOL_MS:
            continue
        score = dt_ms + abs(_finite(trade.get("price")) - price) * 1000.0
        if best is None or score < best[0]:
            best = (score, trade)
    return best[1] if best else None


def match_ledger_rows(
    rows: List[Dict[str, Any]],
    trades_by_symbol: Dict[str, List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Match every binance_futures ledger row against venue fills.

    Returns (per-row results, class counts). ``used`` marks the venue
    fill ids consumed, so a fill can only explain one ledger row.
    """
    used: Dict[Tuple[str, str], int] = {}
    results: List[Dict[str, Any]] = []
    for row in rows:
        if str(row.get("venue") or "") != "binance_futures":
            continue
        symbol = str(row.get("symbol") or "")
        # Only unused fills may match (a fill explains one row).
        candidates = [
            t
            for t in trades_by_symbol.get(symbol, [])
            if used.get((symbol, str(t.get("id"))), 0) == 0
        ]
        entry = None
        exit_fill = None
        if row.get("entry_time"):
            entry = _find_fill(
                row, candidates, _finite(row.get("entry_price")),
                _finite(row.get("entry_time")), True,
            )
        if row.get("exit_time"):
            exit_fill = _find_fill(
                row, candidates, _finite(row.get("exit_price")),
                _finite(row.get("exit_time")), False,
            )
        if entry is not None and entry is exit_fill:
            exit_fill = None
        if entry is not None:
            used[(symbol, str(entry.get("id")))] = 1
        if exit_fill is not None:
            used[(symbol, str(exit_fill.get("id")))] = 1
        if entry is not None and exit_fill is not None:
            cls = "BOTH"
        elif entry is not None:
            cls = "ENTRY_ONLY"
        elif exit_fill is not None:
            cls = "EXIT_ONLY"
        else:
            cls = "NO_MATCH"
        oid_match = None
        if str(row.get("order_id") or ""):
            oid_match = any(
                str(t.get("orderId")) == str(row.get("order_id"))
                for t in trades_by_symbol.get(symbol, [])
            )
        results.append(
            {
                "symbol": symbol,
                "side": row.get("side"),
                "strategy": row.get("strategy"),
                "recorded_at": row.get("recorded_at"),
                "net_pnl": _finite(row.get("net_pnl")),
                "class": cls,
                "entry_fill_id": str(entry.get("id")) if entry else None,
                "exit_fill_id": str(exit_fill.get("id")) if exit_fill else None,
                "exit_realized_pnl": (
                    _finite(exit_fill.get("realizedPnl"))
                    if exit_fill is not None
                    else None
                ),
                "order_id_on_venue": oid_match,
            }
        )
    counts: Dict[str, int] = {}
    for res in results:
        counts[res["class"]] = counts.get(res["class"], 0) + 1
    return results, counts


def group_venue_orders(
    trades_by_symbol: Dict[str, List[Dict[str, Any]]],
    orders_by_symbol: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    """Group venue fills by (symbol, orderId) with order metadata."""
    groups: Dict[str, Dict[str, Any]] = {}
    for symbol, trades in trades_by_symbol.items():
        for trade in trades:
            key = f"{symbol}:{trade.get('orderId')}"
            group = groups.setdefault(
                key,
                {
                    "symbol": symbol,
                    "order_id": str(trade.get("orderId")),
                    "side": str(trade.get("side") or ""),
                    "fills": [],
                    "qty": 0.0,
                    "realized_pnl": 0.0,
                    "commission": 0.0,
                },
            )
            group["fills"].append(trade)
            group["qty"] = round(group["qty"] + _finite(trade.get("qty")), 8)
            group["realized_pnl"] = round(
                group["realized_pnl"] + _finite(trade.get("realizedPnl")), 4
            )
            group["commission"] = round(
                group["commission"] + _finite(trade.get("commission")), 4
            )
    for symbol, orders in orders_by_symbol.items():
        for order in orders:
            key = f"{symbol}:{order.get('orderId')}"
            group = groups.get(key)
            if group is None:
                group = groups.setdefault(
                    key,
                    {
                        "symbol": symbol,
                        "order_id": str(order.get("orderId")),
                        "side": str(order.get("side") or ""),
                        "fills": [],
                        "qty": 0.0,
                        "realized_pnl": 0.0,
                        "commission": 0.0,
                    },
                )
            group["status"] = str(order.get("status") or "")
            group["order_type"] = str(order.get("type") or "")
            group["order_time"] = order.get("time")
            group["order_update_time"] = order.get("updateTime")
    return groups


def find_missing_closes(
    groups: Dict[str, Dict[str, Any]],
    used_fill_ids: Dict[Tuple[str, str], int],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Venue order groups that closed a position with no ledger row.

    A FILLED order whose fills were all unused by ledger matching and
    whose aggregate realized P&L is non-zero is a missing close: an
    entry fill realizes ~0, a close realizes its P&L. Zero-realized
    unused fills (open-position entries, breakeven closes) are listed
    separately as unmatched fills — visible, never silently dropped.
    """
    missing: List[Dict[str, Any]] = []
    unmatched_zero: List[Dict[str, Any]] = []
    for key, group in groups.items():
        if group.get("status") != "FILLED":
            continue
        fills = group.get("fills") or []
        if not fills:
            continue
        if any(
            used_fill_ids.get((group["symbol"], str(f.get("id"))), 0)
            for f in fills
        ):
            continue
        entry = {
            "symbol": group["symbol"],
            "order_id": group["order_id"],
            "side": group["side"],
            "qty": group["qty"],
            "realized_pnl": group["realized_pnl"],
            "commission": group["commission"],
            "fills": len(fills),
            "first_fill_time": min(int(f.get("time") or 0) for f in fills),
            "last_fill_time": max(int(f.get("time") or 0) for f in fills),
        }
        if abs(group["realized_pnl"]) > MISSING_CLOSE_MIN_ABS_PNL:
            missing.append(entry)
        else:
            unmatched_zero.append(entry)
    missing.sort(key=lambda e: e["first_fill_time"])
    unmatched_zero.sort(key=lambda e: e["first_fill_time"])
    return missing, unmatched_zero


# ---------------------------------------------------------------------------
# Resets + equity walk
# ---------------------------------------------------------------------------
def detect_resets(
    income_rows: List[Dict[str, Any]],
    known_reset_times_ms: Optional[List[int]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Faucet re-grants are TRANSFER income rows (tranId 0 on demo-fapi).

    Each one resets the balance and wipes open positions (LEDGER-001
    section 3). Returns (all resets, newly-seen resets).
    """
    known = set(known_reset_times_ms or [])
    all_resets: List[Dict[str, Any]] = []
    new_resets: List[Dict[str, Any]] = []
    for row in income_rows:
        if str(row.get("incomeType") or "") != "TRANSFER":
            continue
        item = {
            "time_ms": int(row.get("time") or 0),
            "time": _iso_utc(_finite(row.get("time"))),
            "asset": str(row.get("asset") or ""),
            "amount": _finite(row.get("income")),
            "tran_id": str(row.get("tranId") or ""),
        }
        all_resets.append(item)
        if item["time_ms"] not in known:
            new_resets.append(item)
    all_resets.sort(key=lambda r: r["time_ms"])
    new_resets.sort(key=lambda r: r["time_ms"])
    return all_resets, new_resets


def income_sums(
    income_rows: List[Dict[str, Any]],
    start_ms: int,
    end_ms: int,
) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for row in income_rows:
        ts = int(row.get("time") or 0)
        if not (start_ms <= ts < end_ms):
            continue
        key = str(row.get("incomeType") or "UNKNOWN")
        totals[key] = round(
            totals.get(key, 0.0) + _finite(row.get("income")), 4
        )
    return totals


def reconcile_window(
    ledger_window_net: float,
    ledger_window_fees: float,
    venue_realized: float,
    missing_closes_realized: float,
    baseline_equity: float,
) -> Dict[str, Any]:
    """LEDGER-001 section 6 identity, whole forward window.

    venue realized == ledger window net + missing closes + ledger fees
    (within rounding). A residual beyond tolerance is a DISCREPANCY
    finding, filed in the report — never absorbed.
    """
    expected = ledger_window_net + missing_closes_realized + ledger_window_fees
    residual = round(venue_realized - expected, 4)
    tolerance = round(
        max(RECON_TOLERANCE_USD, RECON_TOLERANCE_FRAC * abs(baseline_equity)),
        2,
    )
    return {
        "venue_realized_pnl": round(venue_realized, 4),
        "ledger_window_net": round(ledger_window_net, 4),
        "missing_closes_realized": round(missing_closes_realized, 4),
        "ledger_window_fees": round(ledger_window_fees, 4),
        "expected_venue_realized": round(expected, 4),
        "residual": residual,
        "tolerance_usd": tolerance,
        "status": "RECONCILED" if abs(residual) <= tolerance else "DISCREPANCY",
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def latch_alert(kind: str, detail: str, stamp: Optional[Dict[str, Any]] = None) -> None:
    """Latch a measurement alert when the module is available (S1).

    Best-effort by design: a bookkeeping failure must never fail the
    reconciliation run itself.
    """
    try:
        from measurement import fill_ledger  # type: ignore

        fill_ledger.raise_alert(kind, detail, stamp=stamp)
    except Exception as exc:  # pragma: no cover - offline / standalone
        print(f"[STR-044] alert latch unavailable ({kind}): {exc}")


def build_report(
    *,
    date_str: str,
    run_at: str,
    ledger_summary: Dict[str, Any],
    ledger_rows: List[Dict[str, Any]],
    match_results: List[Dict[str, Any]],
    match_counts: Dict[str, int],
    missing_closes: List[Dict[str, Any]],
    unmatched_zero: List[Dict[str, Any]],
    resets: List[Dict[str, Any]],
    new_resets: List[Dict[str, Any]],
    account: Optional[Dict[str, Any]],
    open_positions: List[Dict[str, Any]],
    income_rows: List[Dict[str, Any]],
    window_identity: Dict[str, Any],
    errors: List[str],
) -> Dict[str, Any]:
    window_rows = [
        r
        for r in ledger_rows
        if _finite(r.get("exit_time"), 0.0) >= GLOBAL_FORWARD_START
    ]
    matched_exit_realized = round(
        sum(
            _finite(res.get("exit_realized_pnl"))
            for res in match_results
            if res.get("exit_realized_pnl") is not None
        ),
        4,
    )
    matched_ledger_net = round(
        sum(
            _finite(res.get("net_pnl"))
            for res in match_results
            if res.get("exit_realized_pnl") is not None
        ),
        4,
    )
    diffs = [
        {
            "symbol": res["symbol"],
            "recorded_at": res.get("recorded_at"),
            "venue_exit_realized": res.get("exit_realized_pnl"),
            "ledger_net": res.get("net_pnl"),
            "diff": round(
                _finite(res.get("exit_realized_pnl")) - _finite(res.get("net_pnl")),
                4,
            ),
        }
        for res in match_results
        if res.get("exit_realized_pnl") is not None
        and abs(
            _finite(res.get("exit_realized_pnl")) - _finite(res.get("net_pnl"))
        )
        > 0.5
    ]
    gaps: List[str] = []
    if missing_closes:
        gaps.append(
            "G1 — %d venue closes have no ledger row (%+.2f USDT realized): %s"
            % (
                len(missing_closes),
                sum(_finite(m.get("realized_pnl")) for m in missing_closes),
                ", ".join(
                    f"{m['symbol']} {m['realized_pnl']:+.2f}"
                    for m in sorted(
                        missing_closes,
                        key=lambda e: -abs(_finite(e.get("realized_pnl"))),
                    )[:5]
                ),
            )
        )
    if new_resets:
        gaps.append(
            "G-reset — %d new faucet reset(s) detected since the last report: %s"
            % (
                len(new_resets),
                ", ".join(
                    f"{r['asset']} {r['amount']:+.2f} at {r['time']}"
                    for r in new_resets
                ),
            )
        )
    if window_identity.get("status") == "DISCREPANCY" and account is not None:
        gaps.append(
            "G-recon — forward-window identity residual %+.2f USDT exceeds "
            "tolerance %.2f (venue realized %.2f vs expected %.2f)"
            % (
                window_identity.get("residual"),
                window_identity.get("tolerance_usd"),
                window_identity.get("venue_realized_pnl"),
                window_identity.get("expected_venue_realized"),
            )
        )
    if ledger_summary.get("rows_without_order_id"):
        gaps.append(
            "G-trace — %d/%d ledger rows carry no order_id; row-to-venue "
            "traceability rests on price/qty/time matching"
            % (
                ledger_summary.get("rows_without_order_id"),
                ledger_summary.get("rows"),
            )
        )
    account_block = None
    if account is not None:
        account_block = {
            "total_wallet_balance": _finite(account.get("totalWalletBalance")),
            "total_margin_balance": _finite(account.get("totalMarginBalance")),
            "total_unrealized_profit": _finite(
                account.get("totalUnrealizedProfit")
            ),
            "available_balance": _finite(account.get("availableBalance")),
            "assets": [
                {
                    "asset": a.get("asset"),
                    "wallet_balance": _finite(a.get("walletBalance")),
                    "unrealized_profit": _finite(a.get("unrealizedProfit")),
                }
                for a in (account.get("assets") or [])
                if a.get("asset") in ("USDT", "USDC", "BTC")
            ],
        }
    # No venue account read (offline run or venue failure) means the
    # window identity could not be checked against the venue at all.
    status = (
        window_identity.get("status", "ERROR")
        if account is not None
        else "ERROR"
    )
    report = {
        "task": TASK_ID,
        "date": date_str,
        "run_at_utc": run_at,
        "venue": "binance_futures_demo",
        "venue_base_url": VENUE_BASE_URL,
        "window_start": GLOBAL_FORWARD_START_ISO,
        "window_start_epoch": GLOBAL_FORWARD_START,
        "ledger": ledger_summary,
        "venue_account": account_block,
        "open_positions": {
            "count": len(open_positions),
            "unrealized_pnl": round(
                sum(_finite(p.get("unRealizedProfit")) for p in open_positions),
                4,
            ),
            "positions": [
                {
                    "symbol": p.get("symbol"),
                    "amount": _finite(p.get("positionAmt")),
                    "entry_price": _finite(p.get("entryPrice")),
                    "mark_price": _finite(p.get("markPrice")),
                    "unrealized": _finite(p.get("unRealizedProfit")),
                    "leverage": p.get("leverage"),
                }
                for p in sorted(
                    open_positions, key=lambda p: str(p.get("symbol") or "")
                )
            ],
        },
        "matching": {
            "classes": match_counts,
            "rows_matched": len(match_results),
            "matched_exit_realized_pnl": matched_exit_realized,
            "matched_ledger_net": matched_ledger_net,
            "diffs_over_0.5": diffs,
        },
        "missing_closes": {
            "count": len(missing_closes),
            "realized_pnl": round(
                sum(_finite(m.get("realized_pnl")) for m in missing_closes), 4
            ),
            "orders": missing_closes,
        },
        "unmatched_zero_realized_fills": {
            "count": len(unmatched_zero),
            "orders": unmatched_zero,
        },
        "resets_detected": resets,
        "new_resets": new_resets,
        "income_since_reset": income_sums(
            income_rows, RESET_MS, int(time.time() * 1000)
        ),
        "window_identity": window_identity,
        "forward_window": {
            "fills": len(window_rows),
            "ledger_net_pnl": round(
                sum(_finite(r.get("net_pnl")) for r in window_rows), 4
            ),
            "closes_on_venue": len(window_rows)
            + len(
                [
                    m
                    for m in missing_closes
                    if m["first_fill_time"] >= FORWARD_WINDOW_START_MS
                ]
            ),
            "venue_true_net_pnl": round(
                sum(_finite(r.get("net_pnl")) for r in window_rows)
                + sum(
                    _finite(m.get("realized_pnl"))
                    for m in missing_closes
                    if m["first_fill_time"] >= FORWARD_WINDOW_START_MS
                ),
                4,
            ),
        },
        "gaps": gaps,
        "status": status,
        "errors": errors,
    }
    return report


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def default_state_dir() -> Path:
    override = os.getenv("STRATEX_STATE_DIR")
    if override:
        return Path(override)
    return _STRATEX_ROOT / "state"


def default_env_file(state_dir: Path) -> Path:
    override = os.getenv("STRATEX_ENV_FILE")
    if override:
        return Path(override)
    return _STRATEX_ROOT / ".env"


def default_out_dir(state_dir: Path) -> Path:
    return state_dir / "reconciliation"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def run(
    *,
    state_dir: Path,
    env_file: Optional[Path] = None,
    out_dir: Optional[Path] = None,
    date_str: Optional[str] = None,
    venue_offline: bool = False,
) -> Tuple[Dict[str, Any], int]:
    """Run one reconciliation and file the dated report. Returns (report, exit_code)."""
    date_str = date_str or _today_ist()
    out_dir = out_dir or default_out_dir(state_dir)
    run_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    errors: List[str] = []

    ledger_path = state_dir / "fill_ledger.jsonl"
    ledger_rows = read_jsonl(ledger_path)
    if not ledger_rows and not ledger_path.exists():
        errors.append(f"ledger not found: {ledger_path}")
    ledger_summary = summarize_ledger(ledger_rows, GLOBAL_FORWARD_START)
    ledger_window_rows = [
        r
        for r in ledger_rows
        if _finite(r.get("exit_time"), 0.0) >= GLOBAL_FORWARD_START
    ]
    ledger_window_fees = round(
        sum(_finite(r.get("fees")) for r in ledger_window_rows), 4
    )

    # Previous report (if any) tells us which resets were already filed.
    prev_path = out_dir / f"daily_{date_str}.json"
    known_resets: List[int] = []
    if prev_path.exists():
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
            known_resets = [
                int(r.get("time_ms") or 0)
                for r in prev.get("resets_detected") or []
            ]
        except Exception:
            pass
    if not known_resets:
        for existing in sorted(out_dir.glob("daily_*.json")) if out_dir.exists() else []:
            try:
                prev = json.loads(existing.read_text(encoding="utf-8"))
                known_resets.extend(
                    int(r.get("time_ms") or 0)
                    for r in prev.get("resets_detected") or []
                )
            except Exception:
                continue

    account = None
    open_positions: List[Dict[str, Any]] = []
    trades_by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    orders_by_symbol: Dict[str, List[Dict[str, Any]]] = {}
    income_rows: List[Dict[str, Any]] = []
    if venue_offline:
        errors.append("venue read skipped (--venue-offline)")
    else:
        try:
            reader = DemoFuturesReader(env_file or default_env_file(state_dir))
            account = reader.account()
            open_positions = reader.open_positions()
            symbols = sorted(
                {str(r.get("symbol") or "") for r in ledger_rows} - {""}
            )
            for symbol in symbols:
                try:
                    trades_by_symbol[symbol] = reader.user_trades(symbol)
                except Exception as exc:
                    errors.append(f"userTrades {symbol} failed: {type(exc).__name__}")
                    trades_by_symbol[symbol] = []
                try:
                    orders_by_symbol[symbol] = reader.all_orders(symbol)
                except Exception as exc:
                    errors.append(f"allOrders {symbol} failed: {type(exc).__name__}")
                    orders_by_symbol[symbol] = []
                time.sleep(0.2)
            income_rows = reader.income(RESET_MS)
        except PermissionError as exc:
            errors.append(f"venue refused: {exc}")
        except Exception as exc:
            errors.append(f"venue read failed: {type(exc).__name__}: {exc}")

    match_results, match_counts = match_ledger_rows(ledger_rows, trades_by_symbol)
    used_fill_ids: Dict[Tuple[str, str], int] = {}
    for res in match_results:
        for fill_id in (res.get("entry_fill_id"), res.get("exit_fill_id")):
            if fill_id is not None:
                used_fill_ids[(res["symbol"], str(fill_id))] = 1
    groups = group_venue_orders(trades_by_symbol, orders_by_symbol)
    missing_closes, unmatched_zero = find_missing_closes(groups, used_fill_ids)

    resets, new_resets = detect_resets(income_rows, known_resets)
    venue_realized = round(
        sum(
            _finite(row.get("income"))
            for row in income_rows
            if str(row.get("incomeType") or "") == "REALIZED_PNL"
            and int(row.get("time") or 0) >= FORWARD_WINDOW_START_MS
        ),
        4,
    )
    baseline_equity = 5000.0
    if account is not None:
        baseline_equity = _finite(account.get("totalMarginBalance")) or 5000.0
    window_identity = reconcile_window(
        ledger_window_net=ledger_summary["window_net_pnl"],
        ledger_window_fees=ledger_window_fees,
        venue_realized=venue_realized,
        missing_closes_realized=round(
            sum(
                _finite(m.get("realized_pnl"))
                for m in missing_closes
                if m["first_fill_time"] >= FORWARD_WINDOW_START_MS
            ),
            4,
        ),
        baseline_equity=baseline_equity,
    )

    report = build_report(
        date_str=date_str,
        run_at=run_at,
        ledger_summary=ledger_summary,
        ledger_rows=ledger_rows,
        match_results=match_results,
        match_counts=match_counts,
        missing_closes=missing_closes,
        unmatched_zero=unmatched_zero,
        resets=resets,
        new_resets=new_resets,
        account=account,
        open_positions=open_positions,
        income_rows=income_rows,
        window_identity=window_identity,
        errors=errors,
    )
    _atomic_write_json(out_dir / f"daily_{date_str}.json", report)
    print(
        f"[STR-044] {date_str}: ledger {ledger_summary['rows']} rows "
        f"(window {ledger_summary['window_rows']}, net "
        f"{ledger_summary['window_net_pnl']:+.2f}), matching "
        f"{match_counts}, missing closes {len(missing_closes)} "
        f"({report['missing_closes']['realized_pnl']:+.2f}), "
        f"resets {len(resets)} ({len(new_resets)} new), "
        f"status {report['status']} -> {out_dir / f'daily_{date_str}.json'}"
    )
    if report["status"] == "DISCREPANCY":
        latch_alert(
            "fill_ledger_reconciliation_discrepancy",
            f"STR-044 {date_str}: window identity residual "
            f"{window_identity['residual']:+.2f} exceeds tolerance "
            f"{window_identity['tolerance_usd']:.2f}",
            stamp={"date": date_str, "residual": window_identity["residual"]},
        )
    if new_resets:
        latch_alert(
            "fill_ledger_reconciliation_reset",
            f"STR-044 {date_str}: {len(new_resets)} new faucet reset(s): "
            + ", ".join(
                f"{r['asset']} {r['amount']:+.2f} at {r['time']}"
                for r in new_resets
            ),
            stamp={"date": date_str, "resets": len(new_resets)},
        )
    if account is None and not venue_offline:
        latch_alert(
            "fill_ledger_reconciliation_venue_unavailable",
            f"STR-044 {date_str}: venue read failed: {'; '.join(errors)}",
            stamp={"date": date_str},
        )
        return report, 2
    return report, 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Daily Stratex fill-ledger reconciliation (TASK-STR-044). "
        "Read-only on the venue (signed GETs, demo only)."
    )
    parser.add_argument("--state-dir", type=Path, default=None,
                        help="Stratex state dir (default: STRATEX_STATE_DIR or Stratex/state)")
    parser.add_argument("--env-file", type=Path, default=None,
                        help="Stratex .env with demo keys (default: Stratex/.env)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Report dir (default: <state-dir>/reconciliation)")
    parser.add_argument("--date", default=None,
                        help="Report date YYYY-MM-DD in IST (default: today)")
    parser.add_argument("--venue-offline", action="store_true",
                        help="Ledger-only run: skip all venue reads (CI / dry-run)")
    args = parser.parse_args(argv)
    state_dir = args.state_dir or default_state_dir()
    _, code = run(
        state_dir=state_dir,
        env_file=args.env_file,
        out_dir=args.out_dir,
        date_str=args.date,
        venue_offline=args.venue_offline,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
