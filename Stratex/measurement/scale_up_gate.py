"""Scale-up gate (TASK-STR-082, leg 1; source S-08, item DX6peBwCRW3).

Pure evaluation over fill-ledger rows: decides whether a strategy may
SCALE UP its size. It encodes ONLY the scale-up gate CONDITIONS from
the source item — the source item's own ladder percentages are NOT
adopted. FWD-006 parameters govern and stay as they are (per-trade
risk 0.1% of venue equity, aggregate portfolio-heat cap 2%).

The gate allows scale-up only when EVERY condition holds:

1. THREE MONTHS PROFITABLE — net PnL > 0 in EACH of the three
   calendar months ending in the current month (UTC). A month with no
   trades is not profitable.
2. 50+ TRADES LOGGED — at least ``SCALE_UP_MIN_TRADES`` closed trades
   in the same three-month window.
3. MAX DRAWDOWN UNDER 10% — the window's mark-to-market max drawdown
   is under ``SCALE_UP_MAX_DD_PCT`` of venue equity (same peak-to-
   trough arithmetic as :mod:`measurement.forward_guard`; the 5% kill
   limit still applies separately and is stricter).
4. CONSISTENT RULES — the strategy's rules did not change inside the
   window. Rule-change history must be supplied by the caller
   (``rule_change_times``); when it is not supplied the condition is
   UNVERIFIED and the gate denies (fail-closed: "consistent rules"
   cannot be claimed without a record).
5. NEVER SCALE AFTER A BIG WIN — the most recent closed trade is not
   a big win. A big win is a single trade netting at least
   ``BIG_WIN_MULTIPLE`` (10x) the FWD-006 per-trade risk unit, i.e.
   1% of venue equity. The multiple is the one number the source does
   not give; 10x the risk unit is frozen here and can be tightened
   through the normal gate.
6. NEVER SCALE TO RECOVER LOSSES — the strategy is not underwater:
   its current mark-to-market drawdown must be zero (at a fresh peak).
   Scaling from below the peak is scaling to recover losses.

Like :mod:`measurement.forward_guard` this module is bookkeeping: it
never places, sizes, or blocks an order. It only answers allow/deny
with per-condition evidence. Demo/testnet only, like the rest of
Stratex's governed execution.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, List, Optional

from measurement.forward_guard import strategy_stats

# --- FROZEN GATE CONSTANTS (TASK-STR-082; source S-08) ---
SCALE_UP_MIN_MONTHS = 3
SCALE_UP_MIN_TRADES = 50
SCALE_UP_MAX_DD_PCT = 0.10
# FWD-006 per-trade risk (TASK-STR-FWD-006): 0.1% of venue equity.
PER_TRADE_RISK_PCT = 0.001
# A "big win" is this many per-trade risk units in one trade
# (10 x 0.1% = 1% of venue equity).
BIG_WIN_MULTIPLE = 10.0


def _month_key(epoch_s: float):
    dt = datetime.datetime.fromtimestamp(epoch_s, tz=datetime.timezone.utc)
    return (dt.year, dt.month)


def _three_month_window(now_s: float):
    """The three calendar months ending in the current month (UTC).

    Returns (months, window_start_s) with months oldest-first.
    """
    now = datetime.datetime.fromtimestamp(now_s, tz=datetime.timezone.utc)
    months: List[tuple] = []
    year, month = now.year, now.month
    for _ in range(SCALE_UP_MIN_MONTHS):
        months.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    months.reverse()
    start = datetime.datetime(
        months[0][0], months[0][1], 1, tzinfo=datetime.timezone.utc
    ).timestamp()
    return months, start


def evaluate_scale_up(
    rows: List[Dict[str, Any]],
    equity_usd: float,
    strategy: str,
    now_s: float,
    unrealized_pnl: float = 0.0,
    rule_change_times: Optional[Iterable[float]] = None,
) -> Dict[str, Any]:
    """Decide whether ``strategy`` may scale up, with per-condition evidence.

    ``rows`` are fill-ledger rows (``strategy``, ``net_pnl``,
    ``exit_time``). Only rows inside the three-month window count;
    rows without an ``exit_time`` cannot be placed in a month and are
    excluded (counted in the evidence). ``rule_change_times`` lists the
    epoch seconds at which the strategy's rules changed; ``None``
    means no rule-change history was supplied and the consistency
    condition is unverified (the gate denies).
    """
    equity = float(equity_usd or 0.0)
    months, window_start = _three_month_window(float(now_s))
    reasons: List[str] = []

    if equity <= 0:
        reasons.append("venue equity must be positive to evaluate scale-up")

    strategy_rows = [r for r in rows if r.get("strategy") == strategy]
    windowed = [
        r
        for r in strategy_rows
        if r.get("net_pnl") is not None
        and r.get("exit_time") is not None
        and window_start <= float(r["exit_time"]) <= float(now_s)
    ]
    excluded = len(strategy_rows) - len(windowed)
    windowed.sort(key=lambda r: float(r["exit_time"]))

    # Condition 1: profitable in EACH of the three calendar months.
    month_pnl = {m: 0.0 for m in months}
    month_trades = {m: 0 for m in months}
    for r in windowed:
        key = _month_key(float(r["exit_time"]))
        month_pnl[key] += float(r["net_pnl"])
        month_trades[key] += 1
    month_evidence = [
        {
            "year": y,
            "month": m,
            "trades": month_trades[(y, m)],
            "net_pnl": month_pnl[(y, m)],
            "profitable": month_pnl[(y, m)] > 0,
        }
        for (y, m) in months
    ]
    losing_months = [e for e in month_evidence if not e["profitable"]]
    if losing_months:
        desc = ", ".join(
            f"{e['year']}-{e['month']:02d} (net {e['net_pnl']:.2f} over "
            f"{e['trades']} trades)"
            for e in losing_months
        )
        reasons.append(
            "not profitable in each of the last 3 months: " + desc
        )

    # Conditions 2, 3, 6 via the shared forward-guard statistics.
    stats = strategy_stats(windowed, strategy, float(unrealized_pnl or 0.0))
    if stats["trades"] < SCALE_UP_MIN_TRADES:
        reasons.append(
            f"only {stats['trades']} closed trades logged in the window "
            f"(minimum {SCALE_UP_MIN_TRADES})"
        )

    dd_limit_usd = max(0.0, equity) * SCALE_UP_MAX_DD_PCT
    if equity > 0 and stats["max_drawdown_usd"] >= dd_limit_usd:
        reasons.append(
            f"window drawdown ${stats['max_drawdown_usd']:.2f} is not under "
            f"{SCALE_UP_MAX_DD_PCT * 100:.0f}% of venue equity "
            f"(${dd_limit_usd:.2f})"
        )

    if stats["current_drawdown_usd"] > 0:
        reasons.append(
            f"currently ${stats['current_drawdown_usd']:.2f} below peak — "
            "scaling now would be scaling to recover losses"
        )

    # Condition 4: consistent rules (fail-closed when unverified).
    rules_consistent: Optional[bool] = None
    in_window_changes: List[float] = []
    if rule_change_times is None:
        reasons.append(
            "rule-change history not supplied — 'consistent rules' is "
            "unverified; supply rule_change_times to evaluate it"
        )
    else:
        in_window_changes = sorted(
            float(t) for t in rule_change_times if window_start <= float(t) <= float(now_s)
        )
        rules_consistent = not in_window_changes
        if in_window_changes:
            reasons.append(
                f"rules changed {len(in_window_changes)} time(s) inside "
                "the window — rules were not consistent"
            )

    # Condition 5: never scale after a big win.
    big_win_threshold_usd = BIG_WIN_MULTIPLE * PER_TRADE_RISK_PCT * equity
    last_trade_pnl: Optional[float] = None
    if windowed:
        last_trade_pnl = float(windowed[-1]["net_pnl"])
        if equity > 0 and last_trade_pnl >= big_win_threshold_usd:
            reasons.append(
                f"most recent trade netted ${last_trade_pnl:.2f}, a big win "
                f"(>= ${big_win_threshold_usd:.2f} = {BIG_WIN_MULTIPLE:.0f}x "
                "the per-trade risk unit) — never scale after a big win"
            )

    return {
        "strategy": strategy,
        "allowed": not reasons,
        "reasons": reasons,
        "window_start_s": window_start,
        "window_end_s": float(now_s),
        "months": month_evidence,
        "trades": stats["trades"],
        "trades_required": SCALE_UP_MIN_TRADES,
        "net_pnl": stats["net_pnl"],
        "max_drawdown_usd": stats["max_drawdown_usd"],
        "drawdown_limit_usd": dd_limit_usd,
        "current_drawdown_usd": stats["current_drawdown_usd"],
        "rules_consistent": rules_consistent,
        "rule_changes_in_window": in_window_changes,
        "rows_excluded_outside_window": excluded,
        "last_trade_pnl": last_trade_pnl,
        "big_win_threshold_usd": big_win_threshold_usd,
    }
