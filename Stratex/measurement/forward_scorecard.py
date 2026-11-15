"""
measurement/forward_scorecard.py — phase-3 FORWARD scorecard for Stratex.

TASK-STR-FWD-005. The existing measurement/scorecard.py answers "what has
the ledger recorded, all-time?" This module answers the forward-protocol
question: "for each strategy that entered governed forward trading, how
far is it from PROVING itself — and how close is it to being killed?"

Per forward entrant (window = fills with exit_time >= the entrant's
forward start; pre-window fills are counted separately as history and
never mixed in):

  closed trades, wins/losses, win rate, gross/net P&L, fees (with the
  estimated-fee count kept visible), expectancy (net per trade),
  profit factor, max drawdown of the strategy's cumulative net curve
  ($ and % of account equity, the forward_guard DD semantics),
  days in window, distance to the phase-3 bar (8 weeks AND >= 100
  closed trades) and to each kill criterion:

    * expectancy < 0 after >= 50 trades          (forward_guard)
    * profit factor < 1.0 after >= 50 trades     (forward_guard)
    * strategy drawdown > 5% of account equity   (forward_guard)
    * portfolio daily breaker: any UTC day whose realized net loss
      reaches 3% of that day's start equity (portfolio level, below)

  Sleeves are judged exactly as forward_guard.evaluate_sleeves judges
  them: combined-curve drawdown vs 5% of equity ONLY — no per-trade
  expectancy/PF kill is invented for them.

Reconciliation (the part that keeps this honest): per venue, the
scorecard checks

    exchange equity now  ~=  baseline equity at window start
                             + ledger net P&L inside the window
                             + change in unrealized P&L

and prints the unexplained remainder with a status. Inputs are, in
order of trust: (1) a live read-only exchange probe supplied by the
runner (--probe-json or the server-side probe hooks), (2) the engines'
own equity-snapshot stream. The composite supervision figure is NEVER
an input; if the runner supplies it, it is printed as a labelled
cross-reference only, with its delta against the exchange sum.

Entrants are resolved, in priority order, from:
  1. state/forward_entrants.json (operator override, same schema as
     DEFAULT_ENTRANTS below),
  2. config_strategy.PRODUCTION_STRATEGY_REGISTRY — entries flagged
     forward_protocol: True are standalone entrants (lane from
     forward_lane); entries carrying a "sleeve" field are grouped
     into one sleeve entrant per sleeve name (the TASK-STR-FWD-002
     construction). Ledger names are daemon module names, so each
     entrant claims both the "strategy_<key>" and bare-key spellings,
  3. DEFAULT_ENTRANTS (the TASK-STR-FWD-002 activation set).
Any strategy with fills inside the global forward window that no
entrant claims is reported as UNREGISTERED — visible, never dropped.

Run on demand (from the Stratex/ directory):
    python3 -m measurement.forward_scorecard            # write + print
    python3 -m measurement.forward_scorecard --stdout   # print only
    python3 -m measurement.forward_scorecard --probe-json probe.json

Output: state/forward_scorecard.json (atomic) plus stdout lines.
Demo/testnet data only — this module reads; it never places orders.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from measurement import fill_ledger, forward_guard
except ImportError:  # pragma: no cover - flat layout fallback
    import fill_ledger  # type: ignore
    import forward_guard  # type: ignore

try:
    from atomic_io import atomic_write_json
except Exception:  # pragma: no cover
    atomic_write_json = None  # type: ignore

try:
    from logger import get_logger

    logger = get_logger("measurement_forward_scorecard")
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger("measurement_forward_scorecard")

FORWARD_SCORECARD_FILE = "forward_scorecard.json"
ENTRANTS_FILE = "forward_entrants.json"

# Phase-3 protocol constants (owner-approved 2026-11-14/15). The kill
# gates mirror measurement/forward_guard.py — imported there, not
# re-typed, so the scorecard can never drift from the enforcer.
BAR_TRADES = 100
BAR_DAYS = 56  # 8 weeks
DAILY_BREAKER_PCT = 0.03
KILL_MIN_TRADES = forward_guard.MIN_TRADES_FOR_KILL  # 50
DD_LIMIT_PCT = forward_guard.DD_LIMIT_PCT  # 0.05

# TASK-STR-FWD-002 activation: governed forward trading began at
# 2026-11-15 11:29:49 IST. Parsed (not hand-computed) so the epoch
# follows the same ISO<->epoch convention as the ledger data itself.
GLOBAL_FORWARD_START_ISO = "2026-11-15T11:29:49+05:30"


def _epoch(value: Any) -> float:
    """ISO string (or epoch number) -> epoch seconds; never raises."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        return datetime.datetime.fromisoformat(text).timestamp()
    except ValueError:
        # Unparseable start: fall back to the FWD-002 activation instant
        # (constructed directly — GLOBAL_FORWARD_START may not exist yet
        # while this module is still initialising).
        return datetime.datetime(
            2026, 11, 15, 5, 59, 49, tzinfo=datetime.timezone.utc
        ).timestamp()


GLOBAL_FORWARD_START = _epoch(GLOBAL_FORWARD_START_ISO)

# Fallback entrant set (used only if the registry cannot be read).
# Ledger strategy names are daemon module names (see forward_guard);
# both spellings are listed per entrant ("strategy_<key>" module style
# and the bare registry key) because different engines have written
# both — a fill can only ever carry one of them, so matching the set
# is exact, never double-counted.
DEFAULT_ENTRANTS: List[Dict[str, Any]] = [
    {
        "id": "ichimoku_trend",
        "label": "Ichimoku tk_cloud (crypto30, 4h) — RD-002 candidate 1",
        "lane": "FORWARD",
        "strategies": ["strategy_ichimoku_trend", "ichimoku_trend"],
        "window_start": GLOBAL_FORWARD_START_ISO,
        "venues": ["binance_futures"],
    },
    {
        "id": "dow_effect",
        "label": "Dow-effect reversal (crypto30, 1d) — RD-002 candidate 2",
        "lane": "FORWARD",
        "strategies": ["strategy_dow_effect", "dow_effect"],
        "window_start": GLOBAL_FORWARD_START_ISO,
        "venues": ["binance_futures"],
    },
    {
        "id": "sleeve:best_per_class",
        "label": "Stage-C best-per-class sleeve (multi-venue)",
        "lane": "FORWARD",
        "sleeve": True,
        "strategies": [
            "strategy_sleeve_shock_breakout", "sleeve_shock_breakout",
            "strategy_sleeve_tsmom2_dual", "sleeve_tsmom2_dual",
        ],
        "window_start": GLOBAL_FORWARD_START_ISO,
        "venues": ["binance_futures", "oanda"],
    },
]

# The fleet's forward venues (post TASK-STR-RETIRE-001). Always
# reconciled, even before any fill names them.
KNOWN_VENUES = ("binance_futures", "oanda")

# Reconciliation tolerance: |unexplained| must be within this to be
# called RECONCILED. Fees are broker-sourced on the daemon venue, so a
# tight band is fair; anything outside it is a printed discrepancy.
RECON_TOLERANCE_USD = 2.0
RECON_TOLERANCE_FRAC = 0.001


def forward_scorecard_path() -> Path:
    override = os.getenv("STRATEX_FORWARD_SCORECARD_FILE")
    if override:
        return Path(override)
    return fill_ledger.state_dir() / FORWARD_SCORECARD_FILE


def entrants_path() -> Path:
    override = os.getenv("STRATEX_FORWARD_ENTRANTS_FILE")
    if override:
        return Path(override)
    return fill_ledger.state_dir() / ENTRANTS_FILE


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _pf_json(pf: float) -> Optional[float]:
    """Profit factor for JSON: inf (no losing trades) becomes None."""
    if pf is None or (isinstance(pf, float) and math.isinf(pf)):
        return None
    return round(float(pf), 3)


# ---------------------------------------------------------------------------
# Entrant resolution
# ---------------------------------------------------------------------------
def load_entrants() -> List[Dict[str, Any]]:
    """Resolve the forward entrant set (override file > registry > defaults)."""
    path = entrants_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            entrants = data.get("entrants") if isinstance(data, dict) else data
            if isinstance(entrants, list) and entrants:
                return _normalise(entrants)
    except Exception as e:
        logger.warning(f"[FWD-SCORECARD] entrants override unreadable: {e}")
    try:
        import os as _os
        import sys as _sys

        _stratex_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        if _stratex_dir not in _sys.path:
            _sys.path.insert(0, _stratex_dir)
        from config_strategy import PRODUCTION_STRATEGY_REGISTRY

        entrants = _entrants_from_registry(PRODUCTION_STRATEGY_REGISTRY)
        if entrants:
            return _normalise(entrants)
    except Exception as e:
        logger.warning(f"[FWD-SCORECARD] registry entrants unavailable: {e}")
    return _normalise(DEFAULT_ENTRANTS)


def _ledger_names(key: str, spec: Dict[str, Any]) -> List[str]:
    """Ledger strategy spellings for one registry entry.

    The daemon records fills by module name ("strategy_<key>", per
    forward_guard); other engines have written the bare key. Both
    spellings are claimed — a fill carries exactly one, so the union
    is exact. An explicit ledger/module field in the spec wins.
    """
    explicit = spec.get("ledger_strategy") or spec.get("daemon_module") or spec.get("module")
    names = [str(explicit)] if explicit else [f"strategy_{key}", str(key)]
    return list(dict.fromkeys(names))


def _entrants_from_registry(registry: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Forward entrants from PRODUCTION_STRATEGY_REGISTRY's real shape.

    * ``forward_protocol: True`` entries are standalone entrants
      (lane from ``forward_lane``, default FORWARD).
    * Entries carrying a ``sleeve`` field are components of that
      sleeve (TASK-STR-FWD-002: ``"sleeve": SLEEVE_NAME``); they are
      grouped into ONE sleeve entrant judged drawdown-only — even if
      such an entry also flags forward_protocol, the sleeve grouping
      wins, because the sleeve is the judged unit.
    * ``forward_protocol: False`` entries are excluded (their reason
      is recorded in the registry itself).
    """
    entrants: List[Dict[str, Any]] = []
    sleeve_groups: Dict[str, List[str]] = {}
    for key, spec in (registry or {}).items():
        if not isinstance(spec, dict):
            continue
        if spec.get("sleeve"):
            sleeve_groups.setdefault(str(spec["sleeve"]), []).extend(
                _ledger_names(str(key), spec)
            )
            continue
        if not spec.get("forward_protocol"):
            continue
        entrants.append(
            {
                "id": str(key),
                "label": str(spec.get("label") or key),
                "lane": str(spec.get("forward_lane") or "FORWARD"),
                "strategies": _ledger_names(str(key), spec),
                "window_start": str(spec.get("forward_start") or GLOBAL_FORWARD_START_ISO),
                "venues": list(spec.get("forward_venues") or ["binance_futures"]),
            }
        )
    for sleeve_name, components in sleeve_groups.items():
        entrants.append(
            {
                "id": f"sleeve:{sleeve_name}",
                "label": f"Stage-C sleeve '{sleeve_name}'",
                "lane": "FORWARD",
                "sleeve": True,
                "strategies": list(dict.fromkeys(components)),
                "window_start": GLOBAL_FORWARD_START_ISO,
                "venues": ["binance_futures", "oanda"],
            }
        )
    return entrants


def _normalise(entrants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for e in entrants:
        start_iso = str(e.get("window_start") or GLOBAL_FORWARD_START_ISO)
        out.append(
            {
                "id": str(e.get("id") or "unnamed"),
                "label": str(e.get("label") or e.get("id") or "unnamed"),
                "lane": str(e.get("lane") or "FORWARD"),
                "sleeve": bool(e.get("sleeve")),
                "strategies": [str(s) for s in (e.get("strategies") or [])],
                "window_start": start_iso,
                "window_start_epoch": _epoch(start_iso),
                "venues": [str(v) for v in (e.get("venues") or [])],
            }
        )
    return out


# ---------------------------------------------------------------------------
# Per-entrant forward scorecard
# ---------------------------------------------------------------------------
def _window_rows(
    fills: List[Dict[str, Any]], strategies: List[str], start_epoch: float
) -> List[Dict[str, Any]]:
    rows = [
        r
        for r in fills
        if str(r.get("strategy") or "") in strategies
        and _finite(r.get("exit_time"), 0.0) >= start_epoch
        and r.get("net_pnl") is not None
    ]
    rows.sort(key=lambda r: _finite(r.get("exit_time"), 0.0))
    return rows


def _combined_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """forward_guard.strategy_stats formulas over an arbitrary row set.

    Used for multi-module entrants and sleeves (combined cumulative
    curve — the evaluate_sleeves construction). Rows must already be
    window-filtered; they are (re)sorted by exit_time here.
    """
    rows = sorted(rows, key=lambda r: _finite(r.get("exit_time"), 0.0))
    nets = [_finite(r.get("net_pnl")) for r in rows]
    n = len(nets)
    net = sum(nets)
    gross_profit = sum(p for p in nets if p > 0)
    gross_loss = -sum(p for p in nets if p < 0)
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    elif gross_profit > 0:
        pf = float("inf")
    else:
        pf = 0.0
    cumulative = peak = max_dd = 0.0
    for p in nets:
        cumulative += p
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return {
        "trades": n,
        "net_pnl": net,
        "expectancy": (net / n) if n else 0.0,
        "profit_factor": pf,
        "max_drawdown_usd": max_dd,
    }


def _extra_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    nets = [_finite(r.get("net_pnl")) for r in rows]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n < 0]
    return {
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(rows), 4) if rows else 0.0,
        "gross_pnl": round(sum(_finite(r.get("gross_pnl")) for r in rows), 2),
        "fees": round(sum(abs(_finite(r.get("fees"))) for r in rows), 2),
        "estimated_fee_fills": sum(
            1 for r in rows if str(r.get("fees_source") or "") != "broker"
        ),
        "first_exit_at": rows[0].get("recorded_at") if rows else None,
        "last_exit_at": rows[-1].get("recorded_at") if rows else None,
        "venues_seen": sorted({str(r.get("venue") or "") for r in rows}),
        "symbols_seen": sorted({str(r.get("symbol") or "") for r in rows}),
    }


def _kill_block(
    stats: Dict[str, Any], equity_usd: float, sleeve: bool
) -> Dict[str, Any]:
    """Distance-to-kill for one entrant, forward_guard semantics."""
    n = int(stats["trades"])
    dd_limit_usd = max(0.0, equity_usd) * DD_LIMIT_PCT
    dd_usd = float(stats["max_drawdown_usd"])
    dd_pct = (dd_usd / equity_usd) if equity_usd > 0 else None
    block: Dict[str, Any] = {
        "drawdown": {
            "status": "TRIPPED" if (dd_limit_usd > 0 and dd_usd > dd_limit_usd) else "SAFE",
            "max_drawdown_usd": round(dd_usd, 2),
            "max_drawdown_pct_of_equity": round(dd_pct * 100, 3) if dd_pct is not None else None,
            "limit_pct": DD_LIMIT_PCT * 100,
            "limit_usd": round(dd_limit_usd, 2),
            "headroom_usd": round(dd_limit_usd - dd_usd, 2) if dd_limit_usd > 0 else None,
        }
    }
    if sleeve:
        block["note"] = (
            "Sleeve: drawdown-only kill (forward_guard.evaluate_sleeves); "
            "no expectancy/PF kill applies to sleeves."
        )
        return block
    active = n >= KILL_MIN_TRADES
    exp = float(stats["expectancy"])
    pf = float(stats["profit_factor"])
    block["expectancy"] = {
        "status": ("TRIPPED" if exp < 0 else "SAFE") if active else "NOT_ACTIVE",
        "value": round(exp, 4),
        "trades": n,
        "activates_at_trades": KILL_MIN_TRADES,
        "trades_until_active": max(0, KILL_MIN_TRADES - n),
    }
    block["profit_factor"] = {
        "status": ("TRIPPED" if pf < 1.0 else "SAFE") if active else "NOT_ACTIVE",
        "value": _pf_json(pf),
        "value_note": "no losing trades yet" if math.isinf(pf) else None,
        "trades": n,
        "activates_at_trades": KILL_MIN_TRADES,
        "trades_until_active": max(0, KILL_MIN_TRADES - n),
    }
    return block


def _bar_block(n: int, days_in_window: float, now: float, start_epoch: float) -> Dict[str, Any]:
    trades_to_go = max(0, BAR_TRADES - n)
    days_to_go = max(0.0, BAR_DAYS - days_in_window)
    projection = None
    if n > 0 and days_in_window > 0 and trades_to_go > 0:
        rate = n / days_in_window  # trades per day
        if rate > 0:
            eta_epoch = now + trades_to_go / rate * 86400
            projection = datetime.datetime.fromtimestamp(
                eta_epoch, datetime.timezone.utc
            ).isoformat()
    return {
        "bar": f"{BAR_DAYS} days (8 weeks) AND >={BAR_TRADES} closed trades",
        "trades": n,
        "trades_to_go": trades_to_go,
        "days_in_window": round(days_in_window, 2),
        "days_to_go": round(days_to_go, 2),
        "bar_met": n >= BAR_TRADES and days_in_window >= BAR_DAYS,
        "projected_100_trade_date": projection,
    }


def score_entrant(
    entrant: Dict[str, Any],
    fills: List[Dict[str, Any]],
    equity_usd: float,
    now: float,
) -> Dict[str, Any]:
    start = float(entrant["window_start_epoch"])
    rows = _window_rows(fills, entrant["strategies"], start)
    pre_window = [
        r
        for r in fills
        if str(r.get("strategy") or "") in entrant["strategies"]
        and _finite(r.get("exit_time"), 0.0) < start
        and r.get("net_pnl") is not None
    ]
    # Stats over the entrant's windowed rows. For a single-module
    # entrant this is forward_guard.strategy_stats itself — the exact
    # code the daemon enforces with. Multi-module entrants and sleeves
    # use _combined_stats, which repeats the same formulas over the
    # combined curve (the evaluate_sleeves construction); the test
    # suite pins the two to identical output on single-strategy rows.
    if len(entrant["strategies"]) == 1:
        stats = forward_guard.strategy_stats(rows, entrant["strategies"][0])
    elif entrant["strategies"]:
        stats = _combined_stats(rows)
    else:
        stats = {
            "trades": 0,
            "net_pnl": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_usd": 0.0,
        }
    days_in_window = max(0.0, (now - start) / 86400.0)
    kill = _kill_block(stats, equity_usd, entrant["sleeve"])
    if entrant["sleeve"] and not entrant["strategies"]:
        kill["note"] = (
            "Sleeve components UNRESOLVED (registry/state override did "
            "not name them): this row cannot see sleeve fills yet and "
            "must not be read as 'the sleeve has not traded'."
        )
    tripped = any(
        isinstance(v, dict) and v.get("status") == "TRIPPED" for v in kill.values()
    )
    if tripped:
        verdict = "KILL_TRIPPED"
    elif stats["trades"] == 0:
        verdict = "NO_TRADES_YET"
    elif _bar_block(int(stats["trades"]), days_in_window, now, start)["bar_met"]:
        verdict = "BAR_MET"
    else:
        verdict = "IN_WINDOW"
    return {
        "id": entrant["id"],
        "label": entrant["label"],
        "lane": entrant["lane"],
        "sleeve": entrant["sleeve"],
        "strategies": entrant["strategies"],
        "window_start": entrant["window_start"],
        "closed_trades": int(stats["trades"]),
        "net_pnl": round(float(stats["net_pnl"]), 2),
        "expectancy_net_per_trade": round(float(stats["expectancy"]), 4),
        "profit_factor": _pf_json(float(stats["profit_factor"])),
        "max_drawdown_usd": round(float(stats["max_drawdown_usd"]), 2),
        **_extra_stats(rows),
        "pre_window_fills_excluded": len(pre_window),
        "bar": _bar_block(int(stats["trades"]), days_in_window, now, start),
        "kill": kill,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Portfolio daily breaker (3% of day-start equity)
# ---------------------------------------------------------------------------
def _utc_day(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")


def daily_breaker(
    fills: List[Dict[str, Any]],
    snapshots: List[Dict[str, Any]],
    window_start: float,
    now: float,
) -> Dict[str, Any]:
    """Realized net per UTC day vs 3% of that day's start equity.

    Day-start equity comes from the engines' snapshot stream (last
    snapshot before the day begins; else the day's first snapshot).
    Days before the forward window are not judged.
    """
    snaps = sorted(
        (s for s in snapshots if s.get("record_type") == "EQUITY_SNAPSHOT"),
        key=lambda s: _finite(s.get("ts"), 0.0),
    )

    def day_start_equity(day: str) -> Optional[float]:
        day_open = datetime.datetime.strptime(day, "%Y-%m-%d").replace(
            tzinfo=datetime.timezone.utc
        ).timestamp()
        before = [s for s in snaps if _finite(s.get("ts"), 0.0) <= day_open]
        if before:
            return _finite(before[-1].get("total_equity"))
        same_day = [s for s in snaps if _utc_day(_finite(s.get("ts"), 0.0)) == day]
        if same_day:
            return _finite(same_day[0].get("total_equity"))
        return None

    by_day: Dict[str, float] = {}
    for r in fills:
        ts = _finite(r.get("exit_time"), 0.0)
        if ts >= window_start and r.get("net_pnl") is not None:
            by_day[_utc_day(ts)] = by_day.get(_utc_day(ts), 0.0) + _finite(r.get("net_pnl"))
    today = _utc_day(now)
    if today not in by_day:
        by_day[today] = 0.0
    days = []
    tripped_days = []
    worst = None
    for day in sorted(by_day):
        start_eq = day_start_equity(day)
        net = by_day[day]
        loss_pct = None
        tripped = False
        if start_eq and start_eq > 0 and net < 0:
            loss_pct = -net / start_eq
            tripped = loss_pct >= DAILY_BREAKER_PCT
        entry = {
            "day": day,
            "realized_net": round(net, 2),
            "day_start_equity": round(start_eq, 2) if start_eq else None,
            "loss_pct_of_start_equity": round(loss_pct * 100, 3) if loss_pct is not None else None,
            "breaker_pct": DAILY_BREAKER_PCT * 100,
            "tripped": tripped,
        }
        days.append(entry)
        if tripped:
            tripped_days.append(day)
        if loss_pct is not None and (worst is None or loss_pct > worst["loss_pct_of_start_equity"] / 100):
            worst = entry
    return {
        "breaker_pct": DAILY_BREAKER_PCT * 100,
        "days": days,
        "tripped_days": tripped_days,
        "worst_day": worst,
        "status": "TRIPPED" if tripped_days else "SAFE",
    }


# ---------------------------------------------------------------------------
# Reconciliation: ledger vs exchange-verified equity, per venue
# ---------------------------------------------------------------------------
_BOUNDARY_KEY_PREFERENCE = {
    "binance_futures": ["binance_futures_usdt_only", "binance_futures"],
    "oanda": ["oanda_nav", "oanda"],
}


def _venue_window_start(entrants: List[Dict[str, Any]], venue: str) -> float:
    starts = [
        float(e["window_start_epoch"]) for e in entrants if venue in (e.get("venues") or [])
    ]
    return min(starts) if starts else GLOBAL_FORWARD_START


def reconcile_venue(
    venue: str,
    fills: List[Dict[str, Any]],
    snapshots: List[Dict[str, Any]],
    boundaries: List[Dict[str, Any]],
    probe: Dict[str, Any],
    window_start: float,
    now: float,
) -> Dict[str, Any]:
    snaps = sorted(
        (s for s in snapshots if s.get("record_type") == "EQUITY_SNAPSHOT"),
        key=lambda s: _finite(s.get("ts"), 0.0),
    )
    # --- baseline equity at window start ---
    baseline = None
    baseline_method = None
    for b in sorted(boundaries, key=lambda b: _finite(b.get("ts"), 0.0)):
        if _finite(b.get("ts"), 0.0) <= window_start:
            post = b.get("venues_post") or {}
            for key in _BOUNDARY_KEY_PREFERENCE.get(venue, [venue]):
                if post.get(key) is not None:
                    baseline = _finite(post.get(key))
                    baseline_method = f"reset_boundary_post[{key}] @{b.get('timestamp')}"
    if baseline is None:
        at_or_before = [
            s for s in snaps if _finite(s.get("ts"), 0.0) <= window_start and venue in (s.get("venues") or {})
        ]
        if at_or_before:
            baseline = _finite(at_or_before[-1]["venues"].get(venue))
            baseline_method = f"snapshot_at_or_before_start @{at_or_before[-1].get('timestamp')}"
    if baseline is None:
        after = [s for s in snaps if venue in (s.get("venues") or {})]
        if after:
            baseline = _finite(after[0]["venues"].get(venue))
            baseline_method = f"first_snapshot_after_start @{after[0].get('timestamp')} (baseline uncertain)"
    # --- current equity: live probe first, snapshot stream second ---
    current = None
    current_method = None
    current_ts = None
    p = probe.get(venue) if isinstance(probe, dict) else None
    if isinstance(p, dict) and p.get("equity") is not None:
        current = _finite(p.get("equity"))
        current_method = f"live_probe[{p.get('source') or 'runner'}]"
        current_ts = p.get("ts")
    if current is None:
        venue_snaps = [s for s in snaps if venue in (s.get("venues") or {})]
        if venue_snaps:
            current = _finite(venue_snaps[-1]["venues"].get(venue))
            current_method = f"latest_snapshot @{venue_snaps[-1].get('timestamp')}"
            current_ts = venue_snaps[-1].get("timestamp")
    # --- ledger net inside the window, this venue, ALL strategies ---
    window_fills = [
        r
        for r in fills
        if str(r.get("venue") or "") == venue
        and _finite(r.get("exit_time"), 0.0) >= window_start
        and r.get("net_pnl") is not None
    ]
    ledger_net = sum(_finite(r.get("net_pnl")) for r in window_fills)
    unrealized_now = None
    if isinstance(p, dict) and p.get("unrealized") is not None:
        unrealized_now = _finite(p.get("unrealized"))
    # 4dp in the reconciliation block: the audit identity must close
    # visibly (the OANDA reset anchor is NAV 10000.0033, not 10000.00).
    out: Dict[str, Any] = {
        "venue": venue,
        "window_start_epoch": window_start,
        "baseline_equity": round(baseline, 4) if baseline is not None else None,
        "baseline_method": baseline_method,
        "current_equity": round(current, 4) if current is not None else None,
        "current_method": current_method,
        "current_ts": current_ts,
        "ledger_window_net": round(ledger_net, 4),
        "ledger_window_fills": len(window_fills),
        "unrealized_now": round(unrealized_now, 4) if unrealized_now is not None else None,
    }
    if baseline is None or current is None:
        out["status"] = "UNRECONCILABLE"
        out["unexplained"] = None
        out["note"] = "baseline or current equity unavailable from probe and snapshot stream"
        return out
    expected = baseline + ledger_net
    unexplained = current - expected
    check_value = unexplained
    if unrealized_now is not None:
        # Baseline was taken at the (flat) forward start; the current
        # margin balance carries open-position unrealized P&L.
        check_value = unexplained - unrealized_now
    tol = max(RECON_TOLERANCE_USD, RECON_TOLERANCE_FRAC * abs(baseline))
    out["expected_equity"] = round(expected, 4)
    out["unexplained"] = round(unexplained, 4)
    out["unexplained_ex_unrealized"] = round(check_value, 4)
    out["tolerance_usd"] = round(tol, 2)
    out["status"] = "RECONCILED" if abs(check_value) <= tol else "DISCREPANCY"
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def _current_total_equity(
    snapshots: List[Dict[str, Any]], probe: Dict[str, Any]
) -> (float, str):
    if isinstance(probe, dict):
        vals = [
            _finite(v.get("equity"))
            for k, v in probe.items()
            if not str(k).startswith("_")
            and isinstance(v, dict)
            and v.get("equity") is not None
        ]
        if vals:
            return sum(vals), "live_probe_sum"
    snaps = [
        s for s in snapshots if s.get("record_type") == "EQUITY_SNAPSHOT"
    ]
    if snaps:
        latest = max(snaps, key=lambda s: _finite(s.get("ts"), 0.0))
        return _finite(latest.get("total_equity")), f"latest_snapshot @{latest.get('timestamp')}"
    return 0.0, "unavailable"


def build_forward_scorecard(
    fills: Optional[List[Dict[str, Any]]] = None,
    snapshots: Optional[List[Dict[str, Any]]] = None,
    entrants: Optional[List[Dict[str, Any]]] = None,
    probe: Optional[Dict[str, Any]] = None,
    denylist: Optional[List[str]] = None,
    alerts: Optional[Dict[str, Any]] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    if fills is None:
        fills = fill_ledger.read_fills()
    if snapshots is None:
        snapshots = fill_ledger.read_equity_snapshots()
    if entrants is None:
        entrants = load_entrants()
    probe = probe or {}
    now = now if now is not None else time.time()
    equity_usd, equity_source = _current_total_equity(snapshots, probe)
    boundaries = [
        s for s in snapshots if s.get("record_type") == "RESET_BOUNDARY"
    ]
    scored = [score_entrant(e, fills, equity_usd, now) for e in entrants]
    if denylist:
        denied = set(denylist)
        for card in scored:
            if denied.intersection(card["strategies"]):
                card["guard_paused"] = True
    # Discovery: strategies trading inside the global window that no
    # entrant claims are scored as UNREGISTERED, never dropped.
    claimed = {s for e in entrants for s in e["strategies"]}
    discovered = sorted(
        {
            str(r.get("strategy") or "UNATTRIBUTED")
            for r in fills
            if _finite(r.get("exit_time"), 0.0) >= GLOBAL_FORWARD_START
            and str(r.get("strategy") or "UNATTRIBUTED") not in claimed
        }
    )
    for name in discovered:
        scored.append(
            score_entrant(
                {
                    "id": f"unregistered:{name}",
                    "label": f"UNREGISTERED strategy {name} (fills in forward window, no entrant claims it)",
                    "lane": "UNREGISTERED",
                    "sleeve": False,
                    "strategies": [name],
                    "window_start": GLOBAL_FORWARD_START_ISO,
                    "window_start_epoch": GLOBAL_FORWARD_START,
                    "venues": [],
                },
                fills,
                equity_usd,
                now,
            )
        )
    venues = sorted(
        {str(r.get("venue") or "") for r in fills if r.get("venue")}
        | {v for e in entrants for v in e["venues"]}
        | {k for k in probe.keys() if not str(k).startswith("_")}
        | set(KNOWN_VENUES)
    )
    reconciliation = [
        reconcile_venue(
            v, fills, snapshots, boundaries, probe, _venue_window_start(entrants, v), now
        )
        for v in venues
        if v
    ]
    composite = probe.get("_supervision_composite") if isinstance(probe, dict) else None
    card: Dict[str, Any] = {
        "generated_at": datetime.datetime.fromtimestamp(
            now, datetime.timezone.utc
        ).isoformat(),
        "source": "state/fill_ledger.jsonl + state/equity_snapshots.jsonl + live probe (if supplied)",
        "global_forward_start": GLOBAL_FORWARD_START_ISO,
        "account_equity_usd": round(equity_usd, 2),
        "account_equity_source": equity_source,
        "entrants": scored,
        "daily_breaker": daily_breaker(fills, snapshots, GLOBAL_FORWARD_START, now),
        "reconciliation": reconciliation,
        "active_measurement_alerts": alerts if alerts is not None else {},
    }
    if composite is not None:
        exchange_sum = sum(
            (r["current_equity"] or 0.0) for r in reconciliation
        )
        card["supervision_composite_crossref"] = {
            "reported": composite,
            "exchange_sum": round(exchange_sum, 2),
            "delta": round(_finite(composite) - exchange_sum, 2),
            "note": "Cross-reference ONLY — the composite is never an input to this scorecard.",
        }
    return card


def render_lines(card: Dict[str, Any]) -> List[str]:
    lines = [
        f"[FWD-SCORECARD] generated {card['generated_at']} — forward window from "
        f"{card['global_forward_start']}; account equity ${card['account_equity_usd']:,.2f} "
        f"({card['account_equity_source']})"
    ]
    for e in card["entrants"]:
        pf = e["profit_factor"] if e["profit_factor"] is not None else "n/a"
        bar = e["bar"]
        dd = e["kill"]["drawdown"]
        lines.append(
            f"[FWD-SCORECARD] {e['id']} [{e['lane']}] verdict={e['verdict']}: "
            f"trades={e['closed_trades']} (bar: {bar['trades_to_go']} to go) "
            f"days={bar['days_in_window']:.1f} (bar: {bar['days_to_go']:.1f} to go) "
            f"net=${e['net_pnl']:+.2f} expectancy=${e['expectancy_net_per_trade']:+.4f}/trade "
            f"PF={pf} maxDD=${e['max_drawdown_usd']:.2f} "
            f"({dd['max_drawdown_pct_of_equity']}% of equity, limit {dd['limit_pct']:.0f}%)"
        )
        for crit in ("expectancy", "profit_factor"):
            if crit in e["kill"]:
                k = e["kill"][crit]
                lines.append(
                    f"[FWD-SCORECARD]   kill[{crit}]: {k['status']} "
                    f"(value={k['value']}, activates at {k['activates_at_trades']} trades"
                    + (f", {k['trades_until_active']} to go" if k["status"] == "NOT_ACTIVE" else "")
                    + ")"
                )
        lines.append(
            f"[FWD-SCORECARD]   kill[drawdown]: {dd['status']} "
            f"(headroom ${dd['headroom_usd']})"
            + ("; GUARD-PAUSED (denylist)" if e.get("guard_paused") else "")
        )
    b = card["daily_breaker"]
    worst = b.get("worst_day")
    lines.append(
        f"[FWD-SCORECARD] daily breaker (3%): {b['status']}"
        + (
            f"; worst day {worst['day']} lost {worst['loss_pct_of_start_equity']}% of day-start equity"
            if worst
            else "; no losing day in window yet"
        )
        + (f"; TRIPPED days: {', '.join(b['tripped_days'])}" if b["tripped_days"] else "")
    )
    for r in card["reconciliation"]:
        lines.append(
            f"[FWD-SCORECARD] reconcile {r['venue']}: {r['status']} "
            f"baseline=${r['baseline_equity']} ({r['baseline_method']}) "
            f"current=${r['current_equity']} ({r['current_method']}) "
            f"ledger_window_net=${r['ledger_window_net']:+.2f} over {r['ledger_window_fills']} fill(s) "
            f"unexplained=${r['unexplained']}"
        )
    if card.get("supervision_composite_crossref"):
        c = card["supervision_composite_crossref"]
        lines.append(
            f"[FWD-SCORECARD] supervision composite cross-ref: reported=${c['reported']} "
            f"vs exchange sum=${c['exchange_sum']} (delta ${c['delta']:+.2f}) — informational only"
        )
    for kind, info in (card.get("active_measurement_alerts") or {}).items():
        lines.append(
            f"[FWD-SCORECARD] MEASUREMENT ALERT {kind}: {info.get('detail')} "
            f"(since {info.get('since')}, count {info.get('count')})"
        )
    return lines


# ---------------------------------------------------------------------------
# Live probe hooks (server-side, read-only, best-effort)
# ---------------------------------------------------------------------------
def probe_live_equity() -> Dict[str, Any]:
    """Best-effort live venue equity from the deployed engines' readers.

    Returns {} when no read path is available (e.g. off-server). The
    runner may instead supply --probe-json captured from the daemon's
    own reporting. This function NEVER places orders and never raises.
    """
    probe: Dict[str, Any] = {}
    try:
        heartbeat = fill_ledger.state_dir() / "daemon_heartbeat.json"
        if heartbeat.exists():
            hb = json.loads(heartbeat.read_text(encoding="utf-8"))
            venues = hb.get("venues") or {}
            if isinstance(venues, dict):
                for venue, val in venues.items():
                    if isinstance(val, dict) and val.get("equity") is not None:
                        probe[str(venue)] = {
                            "equity": _finite(val.get("equity")),
                            "unrealized": _finite(val.get("unrealized_pnl")),
                            "source": "daemon_heartbeat",
                            "ts": hb.get("timestamp"),
                        }
            if not probe and hb.get("total_equity") is not None:
                probe["_heartbeat_total"] = {
                    "equity": _finite(hb.get("total_equity")),
                    "source": "daemon_heartbeat_total_only",
                    "ts": hb.get("timestamp"),
                }
    except Exception as e:  # probe must never break the scorecard
        logger.warning(f"[FWD-SCORECARD] heartbeat probe failed: {e}")
    return probe


def _read_denylist() -> List[str]:
    try:
        path = fill_ledger.state_dir() / "strategy_denylist.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict):
                return [str(x) for x in data.keys()]
    except Exception:
        pass
    return []


def generate(write: bool = True, probe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if probe is None:
        probe = probe_live_equity()
    try:
        alerts = fill_ledger.active_alerts()
    except Exception:
        alerts = {}
    card = build_forward_scorecard(
        probe=probe, denylist=_read_denylist(), alerts=alerts
    )
    for line in render_lines(card):
        logger.info(line)
    if write:
        path = forward_scorecard_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if atomic_write_json is not None:
            atomic_write_json(str(path), card, indent=2)
        else:  # pragma: no cover
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(card, fh, indent=2)
            os.replace(tmp, path)
    return card


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stratex phase-3 forward scorecard (ledger + exchange reconciliation)"
    )
    parser.add_argument("--stdout", action="store_true", help="print only, do not write state/forward_scorecard.json")
    parser.add_argument("--probe-json", type=Path, help="JSON file with live venue probe results {venue: {equity, unrealized, source, ts}}")
    args = parser.parse_args()
    probe = None
    if args.probe_json:
        probe = json.loads(args.probe_json.read_text(encoding="utf-8"))
    card = generate(write=not args.stdout, probe=probe)
    for line in render_lines(card):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
