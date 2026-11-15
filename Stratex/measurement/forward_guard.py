"""Phase-3 forward-protocol guard (TASK-STR-FWD-002).

Pure evaluation over measurement fill-ledger rows. The Stratex daemon
calls :func:`evaluate` on its governance cadence for every strategy
registered with ``forward_protocol: True`` in
``config_strategy.PRODUCTION_STRATEGY_REGISTRY`` and auto-pauses
(persisted denylist, so the pause survives restarts) any strategy that
breaches the phase-3 kill criteria:

* at least ``MIN_TRADES_FOR_KILL`` (50) closed trades AND
  (expectancy < 0 OR profit factor < 1.0), or
* strategy drawdown — peak-to-trough of the strategy's cumulative net
  PnL curve — exceeding ``DD_LIMIT_PCT`` (5%) of account equity.

Ledger rows record the strategy by daemon module name (e.g.
``strategy_ichimoku_trend``); this module works in module names, which
is what the daemon's denylist stores.

This module also owns :func:`time_exit_due`, the canonical arithmetic
for judged ``bracket_time`` exits (the dow_effect winner): a position
entered in bar E exits at the close of bar E + max_bars - 1, i.e. when
bar E + max_bars has fully elapsed.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List

MIN_TRADES_FOR_KILL = 50
DD_LIMIT_PCT = 0.05


def time_exit_due(
    opened_at_s: float,
    now_s: float,
    max_bars: int,
    bar_seconds: int,
) -> bool:
    """True when the judged bracket_time exit point has been reached.

    ``opened_at_s`` is the fill timestamp (seconds); fills land inside
    the entry bar, so the entry bar's open is its floor. The exit is
    due once ``max_bars`` full bars have elapsed since that open —
    exactly the close of bar (entry + max_bars - 1) at which the judged
    simulator books reason=TIME exits.
    """
    if max_bars <= 0 or bar_seconds <= 0:
        return False
    entry_bar_open = math.floor(opened_at_s / bar_seconds) * bar_seconds
    return now_s >= entry_bar_open + max_bars * bar_seconds


def strategy_stats(rows: Iterable[Dict[str, Any]], strategy: str) -> Dict[str, Any]:
    """Closed-trade statistics for one strategy from fill-ledger rows."""
    fills = [
        r
        for r in rows
        if r.get("strategy") == strategy and r.get("net_pnl") is not None
    ]
    fills.sort(key=lambda r: float(r.get("exit_time") or 0.0))
    n = len(fills)
    pnls = [float(r["net_pnl"]) for r in fills]
    net = sum(pnls)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    elif gross_profit > 0:
        pf = float("inf")
    else:
        pf = 0.0
    # Drawdown of the strategy's own cumulative-PnL curve.
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return {
        "strategy": strategy,
        "trades": n,
        "net_pnl": net,
        "expectancy": (net / n) if n else 0.0,
        "profit_factor": pf,
        "max_drawdown_usd": max_dd,
        "current_drawdown_usd": (peak - cumulative) if n else 0.0,
    }


def evaluate_sleeves(
    rows: List[Dict[str, Any]],
    equity_usd: float,
    sleeves: Dict[str, List[str]],
    dd_limit_pct: float = DD_LIMIT_PCT,
) -> List[Dict[str, Any]]:
    """Sleeve-level kill rule (TASK-STR-FWD-002 sleeve extension).

    A portfolio sleeve is judged on compounded equity + max drawdown
    ONLY (the claim its backtest supports) — there is deliberately no
    per-trade expectancy/PF kill for sleeve components. The sleeve's
    book is the COMBINED cumulative net-PnL curve of all its component
    strategies' fills; the sleeve breaches when that curve's
    peak-to-trough drawdown exceeds ``dd_limit_pct`` of account equity.
    A breach pauses the WHOLE sleeve (the daemon denylists its own
    sleeve components and writes the OANDA sleeve runner's pause
    file).
    """
    dd_limit_usd = max(0.0, float(equity_usd)) * dd_limit_pct
    decisions: List[Dict[str, Any]] = []
    for sleeve, components in sleeves.items():
        fills = [
            r
            for r in rows
            if r.get("strategy") in components and r.get("net_pnl") is not None
        ]
        fills.sort(key=lambda r: float(r.get("exit_time") or 0.0))
        pnls = [float(r["net_pnl"]) for r in fills]
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnls:
            cumulative += p
            peak = max(peak, cumulative)
            max_dd = max(max_dd, peak - cumulative)
        breached = dd_limit_usd > 0 and max_dd > dd_limit_usd
        decisions.append(
            {
                "sleeve": sleeve,
                "components": list(components),
                "trades": len(fills),
                "net_pnl": sum(pnls),
                "max_drawdown_usd": max_dd,
                "drawdown_limit_usd": dd_limit_usd,
                "breached": breached,
                "reasons": (
                    [
                        f"sleeve drawdown ${max_dd:.2f} exceeds 5% of equity "
                        f"(${dd_limit_usd:.2f})"
                    ]
                    if breached
                    else []
                ),
            }
        )
    return decisions


def evaluate(
    rows: List[Dict[str, Any]],
    equity_usd: float,
    module_names: Iterable[str],
    min_trades: int = MIN_TRADES_FOR_KILL,
    dd_limit_pct: float = DD_LIMIT_PCT,
) -> List[Dict[str, Any]]:
    """Evaluate the kill criteria for each named strategy.

    Returns one decision dict per strategy with its statistics, whether
    it breached, and the human-readable reasons (journal evidence).
    """
    dd_limit_usd = max(0.0, float(equity_usd)) * dd_limit_pct
    decisions: List[Dict[str, Any]] = []
    for name in module_names:
        stats = strategy_stats(rows, name)
        reasons: List[str] = []
        if stats["trades"] >= min_trades:
            if stats["expectancy"] < 0:
                reasons.append(
                    f"expectancy {stats['expectancy']:.4f} < 0 after "
                    f"{stats['trades']} closed trades"
                )
            if stats["profit_factor"] < 1.0:
                reasons.append(
                    f"profit factor {stats['profit_factor']:.3f} < 1.0 after "
                    f"{stats['trades']} closed trades"
                )
        if dd_limit_usd > 0 and stats["max_drawdown_usd"] > dd_limit_usd:
            reasons.append(
                f"strategy drawdown ${stats['max_drawdown_usd']:.2f} exceeds "
                f"5% of equity (${dd_limit_usd:.2f})"
            )
        decisions.append(
            {
                **stats,
                "drawdown_limit_usd": dd_limit_usd,
                "breached": bool(reasons),
                "reasons": reasons,
            }
        )
    return decisions
