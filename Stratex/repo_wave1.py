"""repo_wave1.py — TASK-STR-076: REPO-IMPLEMENT wave 1 for Stratex.

Adapts two scouted repos into Stratex's live production path and records the
live-evidence verdict for the four reference-only repos.

ADAPTED
- day-trader-skill (Jakeschincariol/day-trader-skill, MIT): the skill-pack
  *structure* — scanner -> entry timer -> exit planner -> Time Machine
  replay -> budget sizing -> pre-trade risk check, with a human-yes gate —
  re-implemented here in Stratex terms (stdlib only, no network, no orders
  placed by this module). Adapted from, in the upstream repo:
  ``trader-scanner/scan.py`` (opening-range breakout), ``trader-entry/entry.py``
  (first completed bar closing above the range high), ``trader-exit/exit.py``
  (or-mid stop, 2R target), ``trader-timemachine/timemachine.py``
  (Monte-Carlo replay: pool of historical bar ratios, stop checked before
  target), ``trader-budget/size.py`` (floor of max-loss / position-cap /
  max-order / cash) and ``trader-risk/check.py`` (block rules). The US-equities
  content is NOT imported: the chain runs on Stratex's own Binance
  demo-futures symbols and bars. The module produces a decision record only;
  execution still goes through Stratex's governed daemon path, demo only.
- claude-trading-skills / tradermonty (MIT): trade-memory/journaling and
  structured review — ``TradeJournal`` (thesis records in the
  trader-memory-core shape), ``postmortem`` (signal-postmortem skill:
  true/false positive, missed opportunity, regime mismatch) and
  ``weekly_digest`` (weekly-performance-digest skill: win rate, expectancy,
  profit factor, mean R). Journal entries are appended to the Stratex
  advisory ledger, the live ledger of record.

REFERENCE-ONLY (evidence in ``WAVE1_REFERENCE_ONLY`` + ``guard_reference_only_absent``)
- agiprolabs/claude-trading-skills, OpenTerminal (ErTasselli/openterminal),
  NautilusTrader (nautechsystems/nautilus_trader), TradingAgents
  (TauricResearch/TradingAgents): pattern catalogue only. The upstream
  packages are absent from every Stratex production path — proven by the
  AST guard below and by the live-server probe (``find_spec`` False for
  ``nautilus_trader``, ``tradingagents``, ``langgraph``, ``openterminal``;
  zero upstream imports in live ``/opt/friday_universe/Stratex``).
  Honest nuance: Stratex already ships LOCAL re-implementations
  (``stratex_nautilus_adapter/``, ``api/nautilus_routes.py``,
  ``app/agents/real_trading_agents.py``) — stdlib/Python ports written
  in-repo, NOT the upstream Rust engine or LangGraph framework. The guard
  proves the *upstream packages* are absent; it does not claim no
  Nautilus-named code exists.

Failure injection (venue disconnect, stale feed) is HELD pending separate
owner clearance (coordinator 21:57 watch, hub 7138466832, ruling 3) and is
NOT attempted here. The chain's own failure handling is offline: a stale
or empty feed returns a BLOCKED decision with the reason recorded.
"""

from __future__ import annotations

import ast
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Reference-only registry: live-verified upstream metadata, 2026-11-24.
# ---------------------------------------------------------------------------

WAVE1_REFERENCE_ONLY: dict[str, dict[str, Any]] = {
    "agiprolabs/claude-trading-skills": {
        "fit": "reference-only",
        "license": "MIT",
        "default_branch": "main",
        "pushed_at": "2026-09-03T02:19:36Z",
        "stars": 589,
        "language": "Markdown SKILL.md files with Python examples",
        "why_not_integrated": "Broad 68-skill crypto/DeFi pattern catalogue; "
        "thinly maintained. Cherry-pick backtesting/risk patterns only — "
        "no wholesale adoption, no code imported.",
    },
    "ErTasselli/openterminal": {
        "fit": "reference-only",
        "license": "MIT",
        "default_branch": "main",
        "pushed_at": "2026-10-06T15:25:18Z",
        "stars": 2485,
        "language": "TypeScript (Next.js/React + Node/Express)",
        "why_not_integrated": "TypeScript stack does not fit the fleet's Python "
        "services. Transferable assets are the dense multi-panel layout and "
        "the free-data fallback-chain pattern only — no code imported.",
    },
    "nautechsystems/nautilus_trader": {
        "fit": "reference-only",
        "license": "LGPL-3.0",
        "default_branch": "develop",
        "pushed_at": "2026-11-24T14:13:12Z",
        "stars": 31781,
        "language": "Rust core + Python control plane",
        "why_not_integrated": "Backtest=live parity discipline is the design "
        "lesson. As a runtime it is far beyond the ~1GB servers and unnecessary "
        "for the current demo venues (Binance demo-fapi, OANDA practice) — "
        "do not adopt; revisit only if the fleet gets real hardware. "
        "Upstream package NOT installed on the live server; local "
        "stratex_nautilus_adapter/ is an in-repo Python port, not upstream.",
    },
    "TauricResearch/TradingAgents": {
        "fit": "reference-only",
        "license": "Apache-2.0",
        "default_branch": "main",
        "pushed_at": "2026-11-24T11:07:14Z",
        "stars": 123679,
        "language": "TypeScript per GitHub (registry says Python 3.11+)",
        "why_not_integrated": "Bull/bear debate + risk-team veto + auditable "
        "decision log is the pattern lesson. Cannot run as-is: needs Python "
        "3.11+ (fleet is 3.10), every decision burns 15+ LLM calls against "
        "free-tier quotas, no execution layer, US-equity focus while Stratex "
        "trades Binance demo-fapi / OANDA practice. Upstream package NOT "
        "installed on the live server; local real_trading_agents.py is an "
        "in-repo port, not upstream.",
    },
}

WAVE1_ADAPTED: dict[str, dict[str, Any]] = {
    "Jakeschincariol/day-trader-skill": {
        "fit": "adapt",
        "license": "MIT",
        "default_branch": "main",
        "pushed_at": "2026-10-20T14:18:00Z",
        "stars": 9438,
        "adapted_as": "DayTraderChain in this module (scanner -> entry -> "
        "exit plan -> Time Machine replay -> budget sizing -> risk check).",
    },
    "tradermonty/claude-trading-skills": {
        "fit": "adapt",
        "license": "MIT",
        "default_branch": "main",
        "pushed_at": "2026-11-23T21:39:16Z",
        "stars": 8249,
        "adapted_as": "TradeJournal + postmortem + weekly_digest in this module.",
    },
}

# Upstream packages that must never appear in a Stratex production import.
_BANNED_IMPORTS = frozenset(
    {"nautilus_trader", "tradingagents", "langgraph", "openterminal", "agiprolabs"}
)

# Default chain limits (day-trader-skill defaults, Stratex demo terms).
DEFAULTS: dict[str, Any] = {
    "or_minutes": 15,
    "bar_minutes": 5,
    "min_volume_x": 1.0,
    "target_r": 2.0,
    "max_loss_per_trade_usd": 50.0,
    "max_position_pct": 0.02,  # 2% of budget per position (forward-test terms)
    "max_order_usd": 500.0,
    "cash_buffer_pct": 0.05,
    "min_reward_risk": 1.0,
    "min_order_usd": 10.0,
    "max_feed_age_sec": 900,  # bars older than this are a stale feed -> BLOCKED
    "min_qty": 0.001,  # Stratex trades Binance demo-futures: fractional units
    # are normal (min qty 0.001 BTC). Upstream size.py floors to WHOLE shares
    # because Alpaca takes no fractions in a bracket — that rule is wrong for
    # a crypto venue and would refuse every BTC-scale trade (see E2E evidence).
    # whole_units=True restores the upstream equities rule when needed.
    "whole_units": False,
    "timemachine_replays": 2000,
    "timemachine_seed": 19,
    "min_timemachine_green": 0.0,  # replay is evidence, not a gate
}


# ---------------------------------------------------------------------------
# Bars
# ---------------------------------------------------------------------------

@dataclass
class Bar:
    """One OHLCV bar. ``ts`` is epoch seconds (Binance ms timestamps / 1000)."""

    ts: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0


def bars_from_candles(candles: list[Any]) -> list[Bar]:
    """Normalise daemon dict-candles or Binance list-klines into ``Bar``s.

    Dict candles carry ``timestamp`` (epoch seconds), ``open``/``high``/
    ``low``/``close``/``volume``. Binance klines are lists whose first six
    fields are ``[open_time_ms, open, high, low, close, volume]``.
    Malformed rows are skipped, never fatal.
    """
    bars: list[Bar] = []
    for c in candles or []:
        try:
            if isinstance(c, dict):
                ts = float(c.get("timestamp") or c.get("ts") or c.get("time") or 0)
                bars.append(
                    Bar(
                        ts=ts,
                        open=float(c["open"]),
                        high=float(c["high"]),
                        low=float(c["low"]),
                        close=float(c["close"]),
                        volume=float(c.get("volume", 0) or 0),
                    )
                )
            elif isinstance(c, (list, tuple)) and len(c) >= 6:
                bars.append(
                    Bar(
                        ts=float(c[0]) / 1000.0,
                        open=float(c[1]),
                        high=float(c[2]),
                        low=float(c[3]),
                        close=float(c[4]),
                        volume=float(c[5]),
                    )
                )
        except (KeyError, TypeError, ValueError):
            continue
    bars.sort(key=lambda b: b.ts)
    return bars


# ---------------------------------------------------------------------------
# day-trader-skill chain
# ---------------------------------------------------------------------------

def opening_range(bars: list[Bar], or_minutes: int = 15, bar_minutes: int = 5) -> tuple[float, float] | None:
    """High/low of the first ``or_minutes`` of bars (scan.py orb rule)."""
    n = max(1, or_minutes // bar_minutes)
    if len(bars) < n:
        return None
    first = bars[:n]
    return (max(b.high for b in first), min(b.low for b in first))


def scan_orb(
    bars: list[Bar],
    symbol: str,
    or_minutes: int = 15,
    bar_minutes: int = 5,
    min_volume_x: float = 1.0,
) -> dict[str, Any]:
    """Opening-range breakout scan (scan.py orb + entry.py trigger rule).

    Triggers on the first COMPLETED bar after the range that CLOSES above
    the range high; a wick above the high is not a trigger. The trigger bar
    must also carry at least ``min_volume_x`` times the average volume of
    the opening-range bars.
    """
    rng = opening_range(bars, or_minutes, bar_minutes)
    if rng is None:
        return {"symbol": symbol, "status": "no-data",
                "reason": "fewer bars than the opening range"}
    or_high, or_low = rng
    n = max(1, or_minutes // bar_minutes)
    avg_vol = sum(b.volume for b in bars[:n]) / n if n else 0.0
    for bar in bars[n:]:
        if bar.close > or_high:
            if avg_vol > 0 and bar.volume < min_volume_x * avg_vol:
                return {"symbol": symbol, "status": "waiting",
                        "reason": "close above range high but volume below "
                        f"{min_volume_x}x opening-range average",
                        "or_high": or_high, "or_low": or_low}
            return {"symbol": symbol, "status": "triggered",
                    "or_high": or_high, "or_low": or_low,
                    "entry": round(bar.close, 2), "trigger_ts": bar.ts,
                    "trigger_volume": bar.volume}
    return {"symbol": symbol, "status": "waiting",
            "reason": "no completed bar closed above the opening-range high",
            "or_high": or_high, "or_low": or_low}


def exit_plan(entry: float, or_high: float, or_low: float, target_r: float = 2.0) -> dict[str, Any]:
    """Exit plan (exit.py): or-mid stop, ``target_r``R target, flat by plan.

    The stop rounds DOWN to the cent, away from the entry. Refused with a
    reason when the stop is at/above the entry or the risk is under 0.05%
    of the price (too tight to survive the spread).
    """
    or_mid = (or_high + or_low) / 2.0
    stop = math.floor(or_mid * 100) / 100.0
    risk = entry - stop
    if stop >= entry:
        return {"status": "refused", "reason": "stop at or above entry"}
    if risk < 0.0005 * entry:
        return {"status": "refused",
                "reason": "risk under 0.05% of entry price (too tight)"}
    target = round(entry + target_r * risk, 2)
    if target <= entry:
        return {"status": "refused", "reason": "target at or below entry"}
    return {"status": "planned", "entry": entry, "stop": stop,
            "target": target, "risk": round(risk, 2), "target_r": target_r}


def timemachine(
    bars: list[Bar],
    entry: float,
    stop: float,
    target: float,
    replays: int = 2000,
    seed: int = 19,
) -> dict[str, Any]:
    """Monte-Carlo replay (timemachine.py algorithm, single-session pool).

    Upstream replays a trade against 60 past sessions of 5-minute bars.
    The live leg here has ONE live session (100 x 5m bars from the server),
    so the pool is that session's own bar ratios — the algorithm (pick a
    nearby slot, scale one past bar to the current price, stop checked
    before target in every bar) is unchanged, and the deviation is recorded
    in the result. Deterministic for a fixed seed.
    """
    if len(bars) < 10 or entry <= 0 or stop >= entry or target <= entry:
        return {"status": "refused",
                "reason": "need >= 10 bars and stop < entry < target"}
    # Pool: per-bar ratios to the previous bar's close.
    pool: list[tuple[float, float, float, float]] = []
    for prev, bar in zip(bars, bars[1:]):
        if prev.close > 0:
            pool.append((bar.open / prev.close, bar.high / prev.close,
                         bar.low / prev.close, bar.close / prev.close))
    if not pool:
        return {"status": "refused", "reason": "empty replay pool"}
    rng = random.Random(seed)
    outcomes = {"target": 0, "stop": 0, "neither": 0}
    rs: list[float] = []
    end_prices: list[float] = []
    risk = entry - stop
    steps = len(bars)
    for _ in range(max(1, replays)):
        price = entry
        hit = "neither"
        for _i in range(steps):
            o, h, l, c = pool[rng.randrange(len(pool))]
            bar_high = price * h
            bar_low = price * l
            # Stop is checked before the target in every bar (conservative).
            if bar_low <= stop:
                hit = "stop"
                break
            if bar_high >= target:
                hit = "target"
                break
            price = price * c
        outcomes[hit] += 1
        if hit == "target":
            rs.append((target - entry) / risk)
        elif hit == "stop":
            rs.append(-1.0)
        else:
            rs.append((price - entry) / risk)
        end_prices.append(price)
    n = float(max(1, replays))
    green = sum(1 for r in rs if r > 0) / n
    end_sorted = sorted(end_prices)
    def _pct(q: float) -> float:
        return end_sorted[min(len(end_sorted) - 1, int(q * len(end_sorted)))]
    return {"status": "ok", "replays": int(replays), "seed": seed,
            "pool_bars": len(pool), "pool": "single live session (deviation noted)",
            "target_pct": round(outcomes["target"] / n, 4),
            "stop_pct": round(outcomes["stop"] / n, 4),
            "neither_pct": round(outcomes["neither"] / n, 4),
            "green_pct": round(green, 4),
            "mean_r": round(sum(rs) / len(rs), 4) if rs else 0.0,
            "median_end_price": round(_pct(0.5), 2),
            "p5_end_price": round(_pct(0.05), 2),
            "p95_end_price": round(_pct(0.95), 2)}


def size_position(
    budget: float,
    entry: float,
    stop: float,
    max_loss_per_trade_usd: float = 50.0,
    max_position_pct: float = 0.02,
    max_order_usd: float = 500.0,
    cash_buffer_pct: float = 0.05,
    cash_available: float | None = None,
    min_qty: float = 0.001,
    whole_units: bool = False,
) -> dict[str, Any]:
    """Budget sizing (size.py): floor of max-loss / position-cap / max-order
    / cash, quantised to the venue minimum quantity.

    Upstream floors to whole shares (Alpaca brackets take no fractions).
    Stratex's venue takes fractional units, so the default quantises to
    ``min_qty`` (0.001); ``whole_units=True`` restores the upstream rule.
    Zero units is a refusal.
    """
    if entry <= 0 or stop >= entry or budget <= 0:
        return {"status": "refused",
                "reason": "need budget > 0 and stop < entry < target (entry>0)"}
    if whole_units:
        min_qty = 1.0
    if min_qty <= 0:
        min_qty = 1.0
    risk_per_unit = entry - stop
    by_loss = max_loss_per_trade_usd / risk_per_unit
    by_cap = budget * max_position_pct / entry
    by_order = max_order_usd / entry
    by_cash = (budget * (1.0 - cash_buffer_pct)) / entry
    qty = math.floor(min(by_loss, by_cap, by_order, by_cash) / min_qty) * min_qty
    qty = round(qty, 10)
    if cash_available is not None:
        qty = min(qty, math.floor(cash_available / entry / min_qty) * min_qty)
        qty = round(qty, 10)
    if qty <= 0:
        return {"status": "refused",
                "reason": "zero units: stop too far for max loss per trade",
                "by_loss": by_loss, "by_cap": by_cap,
                "by_order": by_order, "by_cash": by_cash}
    return {"status": "sized", "qty": qty, "notional": round(qty * entry, 2),
            "risk_usd": round(qty * risk_per_unit, 2)}


def risk_check(
    symbol: str,
    side: str,
    qty: float,
    entry: float,
    stop: float | None,
    budget: float,
    account_cash: float,
    blocked: tuple[str, ...] = (),
    max_loss_per_trade_usd: float = 50.0,
    max_position_pct: float = 0.02,
    max_order_usd: float = 500.0,
    min_order_usd: float = 10.0,
    cash_buffer_pct: float = 0.05,
    already_placed_today: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Pre-trade risk check (check.py rules, Stratex demo terms).

    Blocks: blocked symbol, size bounds, position % of budget, cash buffer
    breach, missing stop, max loss per trade, duplicate order today.
    An exit (reducing a position) is never blocked here — this function
    only gates entries, matching the upstream rule that getting out must
    always be possible.
    """
    reasons: list[str] = []
    if not symbol or side not in ("BUY", "SELL"):
        reasons.append("format: symbol and BUY/SELL side required")
    if symbol in blocked:
        reasons.append(f"blocked: {symbol} is on the blocked list")
    notional = qty * entry
    if notional < min_order_usd:
        reasons.append(f"size: notional {notional:.2f} under min {min_order_usd}")
    if notional > max_order_usd:
        reasons.append(f"size: notional {notional:.2f} over max {max_order_usd}")
    if budget > 0 and notional > budget * max_position_pct:
        reasons.append("position: over max_position_pct of budget")
    if entry > 0 and qty * entry > account_cash - budget * cash_buffer_pct:
        reasons.append("cash: buy would dip into the cash buffer")
    if stop is None:
        reasons.append("stop: no stop while require_stop is true")
    elif stop >= entry:
        reasons.append("stop: stop on the wrong side of the entry")
    elif qty * (entry - stop) > max_loss_per_trade_usd:
        reasons.append("loss: qty x (entry - stop) over max_loss_per_trade_usd")
    if symbol in already_placed_today:
        reasons.append(f"duplicate: {symbol} already placed today")
    return {"symbol": symbol, "verdict": "BLOCK" if reasons else "PASS",
            "reasons": reasons}


def run_day_trader_chain(
    symbol: str,
    bars: list[Bar],
    budget: float,
    account_cash: float,
    now: float | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One end-to-end run of the adapted day-trader chain.

    Returns a decision record: ``verdict`` is ``GO`` only when every step
    passes; anything else is ``BLOCKED``/``WAITING`` with the reason. The
    function never places an order and never touches the network.
    """
    cfg = {**DEFAULTS, **(config or {})}
    now = now if now is not None else time.time()
    steps: dict[str, Any] = {}
    if not bars:
        return {"symbol": symbol, "verdict": "BLOCKED", "reason": "no-data",
                "steps": {"feed": {"status": "no-data"}}}
    age = now - bars[-1].ts
    if age > float(cfg["max_feed_age_sec"]):
        return {"symbol": symbol, "verdict": "BLOCKED", "reason": "stale-feed",
                "steps": {"feed": {"status": "stale", "age_sec": round(age, 1),
                                   "max_age_sec": cfg["max_feed_age_sec"]}}}
    steps["feed"] = {"status": "ok", "bars": len(bars), "age_sec": round(age, 1)}
    scan = scan_orb(bars, symbol, int(cfg["or_minutes"]), int(cfg["bar_minutes"]),
                    float(cfg["min_volume_x"]))
    steps["scan"] = scan
    if scan["status"] != "triggered":
        return {"symbol": symbol,
                "verdict": "WAITING" if scan["status"] == "waiting" else "BLOCKED",
                "reason": scan.get("reason", scan["status"]), "steps": steps}
    plan = exit_plan(float(scan["entry"]), float(scan["or_high"]), float(scan["or_low"]),
                     float(cfg["target_r"]))
    steps["exit_plan"] = plan
    if plan["status"] != "planned":
        return {"symbol": symbol, "verdict": "BLOCKED",
                "reason": f"exit plan refused: {plan.get('reason')}", "steps": steps}
    replay = timemachine(bars, float(plan["entry"]), float(plan["stop"]),
                         float(plan["target"]), int(cfg["timemachine_replays"]),
                         int(cfg["timemachine_seed"]))
    steps["timemachine"] = replay
    if replay["status"] != "ok":
        return {"symbol": symbol, "verdict": "BLOCKED",
                "reason": f"time machine refused: {replay.get('reason')}", "steps": steps}
    sizing = size_position(budget, float(plan["entry"]), float(plan["stop"]),
                           float(cfg["max_loss_per_trade_usd"]),
                           float(cfg["max_position_pct"]),
                           float(cfg["max_order_usd"]),
                           float(cfg["cash_buffer_pct"]), account_cash,
                           min_qty=float(cfg["min_qty"]),
                           whole_units=bool(cfg["whole_units"]))
    steps["sizing"] = sizing
    if sizing["status"] != "sized":
        return {"symbol": symbol, "verdict": "BLOCKED",
                "reason": f"sizing refused: {sizing.get('reason')}", "steps": steps}
    risk = risk_check(symbol, "BUY", float(sizing["qty"]), float(plan["entry"]),
                      float(plan["stop"]), budget, account_cash,
                      max_loss_per_trade_usd=float(cfg["max_loss_per_trade_usd"]),
                      max_position_pct=float(cfg["max_position_pct"]),
                      max_order_usd=float(cfg["max_order_usd"]),
                      min_order_usd=float(cfg["min_order_usd"]),
                      cash_buffer_pct=float(cfg["cash_buffer_pct"]))
    steps["risk"] = risk
    if risk["verdict"] != "PASS":
        return {"symbol": symbol, "verdict": "BLOCKED",
                "reason": "risk check: " + "; ".join(risk["reasons"]), "steps": steps}
    return {"symbol": symbol, "verdict": "GO",
            "entry": plan["entry"], "stop": plan["stop"], "target": plan["target"],
            "qty": sizing["qty"], "notional": sizing["notional"],
            "risk_usd": sizing["risk_usd"],
            "timemachine_green_pct": replay["green_pct"],
            "timemachine_mean_r": replay["mean_r"],
            "steps": steps}


# ---------------------------------------------------------------------------
# tradermonty: trade journal / postmortem / weekly digest
# ---------------------------------------------------------------------------

@dataclass
class Thesis:
    """A closed-trade thesis record (trader-memory-core shape)."""

    thesis_id: str
    symbol: str
    direction: str  # LONG | SHORT
    entry: float
    stop: float
    target: float
    exit_price: float
    exit_reason: str
    source_skill: str = "repo_wave1"
    sector: str = ""
    mechanism: str = ""

    @property
    def risk(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def r_multiple(self) -> float | None:
        """R-multiple; None when the recorded risk is not positive (gap
        through the stop, stop raised to/above entry) — the trade stays in
        P&L and win/loss stats but out of R averages (digest skill rule)."""
        if self.risk <= 0:
            return None
        signed = (self.exit_price - self.entry) if self.direction == "LONG" \
            else (self.entry - self.exit_price)
        return signed / self.risk

    @property
    def pnl(self) -> float:
        signed = (self.exit_price - self.entry) if self.direction == "LONG" \
            else (self.entry - self.exit_price)
        return signed

    @property
    def won(self) -> bool:
        return self.pnl > 0


class TradeJournal:
    """Append-only in-memory journal; persistence is the advisory ledger
    (``record_to_ledger``), never a new local store."""

    def __init__(self) -> None:
        self.theses: list[Thesis] = []

    def record(self, thesis: Thesis) -> Thesis:
        self.theses.append(thesis)
        return thesis

    def record_to_ledger(self, thesis: Thesis, filepath: str | None = None) -> bool:
        """Append one closed thesis to the Stratex advisory ledger.

        Lazy import so this module stays importable without Stratex deps.
        Returns False (never raises) when the ledger is unavailable.
        """
        try:
            from advisory_ledger import append_advisory_entry
        except Exception:
            return False
        try:
            return bool(append_advisory_entry({
                "decision_id": f"wave1-{thesis.thesis_id}",
                "consultation_reason": "WAVE1_JOURNAL",
                "ai_status": "WAVE1",
                "confidence": 1.0,
                "requested_changes": [],
                "verdict": "SHADOW_LOG_ONLY",
                "applied_changes": [],
                "rejected_changes": [],
                "ai_debate_summary": "",
                "regime_analysis": {
                    "symbol": thesis.symbol, "direction": thesis.direction,
                    "entry": thesis.entry, "stop": thesis.stop,
                    "target": thesis.target, "exit_price": thesis.exit_price,
                    "exit_reason": thesis.exit_reason,
                    "source_skill": thesis.source_skill,
                    "r_multiple": thesis.r_multiple, "pnl": thesis.pnl,
                },
                "latency_ms": 0.0,
                "shadow_mode": True,
                "bounds_checked": {},
            }, filepath=filepath))
        except Exception:
            return False


def postmortem(
    thesis: Thesis,
    realized_5d: float | None = None,
    realized_20d: float | None = None,
) -> dict[str, Any]:
    """Signal postmortem (signal-postmortem skill).

    Compares the predicted direction against realised returns: a winning
    thesis in the predicted direction is a true positive; a losing thesis
    whose market then moved the predicted way is a false positive / missed
    opportunity by direction; a thesis that lost while the 5d/20d realised
    move contradicted the prediction is a regime mismatch.
    """
    predicted_up = thesis.direction == "LONG"
    if thesis.won:
        category = "true_positive"
    elif realized_5d is not None and ((realized_5d > 0) == predicted_up):
        category = "false_positive"
    elif realized_20d is not None and ((realized_20d > 0) == predicted_up):
        category = "missed_opportunity"
    else:
        category = "regime_mismatch"
    return {"thesis_id": thesis.thesis_id, "symbol": thesis.symbol,
            "category": category, "r_multiple": thesis.r_multiple,
            "pnl": thesis.pnl, "exit_reason": thesis.exit_reason,
            "realized_5d": realized_5d, "realized_20d": realized_20d}


def weekly_digest(theses: list[Thesis]) -> dict[str, Any]:
    """Weekly performance digest (weekly-performance-digest skill).

    Pure calculation over closed theses: win rate, expectancy (mean R),
    profit factor, mean R. Trades with no R-multiple stay in P&L and
    win/loss stats but out of R averages.
    """
    closed = list(theses)
    if not closed:
        return {"trades": 0, "win_rate": 0.0, "expectancy_r": 0.0,
                "profit_factor": 0.0, "mean_r": 0.0, "wins": 0, "losses": 0}
    wins = [t for t in closed if t.won]
    losses = [t for t in closed if not t.won]
    rs = [t.r_multiple for t in closed if t.r_multiple is not None]
    gross_win = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_win > 0 else 0.0)
    return {"trades": len(closed), "wins": len(wins), "losses": len(losses),
            "win_rate": round(len(wins) / len(closed), 4),
            "expectancy_r": round(sum(rs) / len(rs), 4) if rs else 0.0,
            "mean_r": round(sum(rs) / len(rs), 4) if rs else 0.0,
            "profit_factor": round(profit_factor, 4)
            if profit_factor != float("inf") else "inf",
            "gross_win": round(gross_win, 4), "gross_loss": round(gross_loss, 4)}


# ---------------------------------------------------------------------------
# Reference-only guardrail
# ---------------------------------------------------------------------------

def guard_reference_only_absent(stratex_root: str | Path) -> list[dict[str, str]]:
    """Prove the upstream reference-only packages are absent from every
    Stratex production path.

    AST-scans every ``*.py`` under ``stratex_root`` for real imports of the
    banned upstream packages (string mentions in comments/docstrings/URLs
    do not count) and scans ``requirements*.txt`` for the package names.
    Returns the list of violations (empty = proof of absence).
    """
    root = Path(stratex_root)
    violations: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in _BANNED_IMPORTS:
                        violations.append({"file": str(path.relative_to(root)),
                                           "import": alias.name})
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                if top in _BANNED_IMPORTS:
                    violations.append({"file": str(path.relative_to(root)),
                                       "import": f"from {node.module}"})
    for req in sorted(root.rglob("requirements*.txt")):
        try:
            text = req.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        for banned in sorted(_BANNED_IMPORTS):
            if banned.replace("_", "-") in text or banned in text:
                violations.append({"file": str(req.relative_to(root)),
                                   "import": f"requirements: {banned}"})
    return violations


# ---------------------------------------------------------------------------
# Production-path cycle + full-allowlist load scan
# ---------------------------------------------------------------------------

def run_wave1_cycle(
    symbol: str,
    bars: list[Bar],
    budget: float,
    account_cash: float,
    now: float | None = None,
    config: dict[str, Any] | None = None,
    ledger_filepath: str | None = None,
) -> dict[str, Any]:
    """Run the adapted chain once and file the verdict in the advisory ledger.

    This is the production-path entry point: the daemon calls it once per
    review with live candles and live equity (see
    ``StratexTradingEngine._maybe_run_wave1_review`` in
    ``autonomy/run_daemon.py``). The ledger write is best-effort and never
    raises; the decision record is always returned.
    """
    decision = run_day_trader_chain(symbol, bars, budget, account_cash,
                                    now=now, config=config)
    decision["ledger_appended"] = False
    try:
        from advisory_ledger import append_advisory_entry
        decision["ledger_appended"] = bool(append_advisory_entry({
            "decision_id": f"wave1-{symbol}-{int((now or time.time()))}",
            "consultation_reason": "WAVE1_CYCLE",
            "ai_status": "WAVE1",
            "confidence": 1.0,
            "requested_changes": [],
            "verdict": "SHADOW_LOG_ONLY",
            "applied_changes": [],
            "rejected_changes": [],
            "ai_debate_summary": "",
            "regime_analysis": {
                "symbol": symbol, "verdict": decision.get("verdict"),
                "reason": decision.get("reason", ""),
                "entry": decision.get("entry"), "stop": decision.get("stop"),
                "target": decision.get("target"), "qty": decision.get("qty"),
                "timemachine_green_pct": decision.get("timemachine_green_pct"),
            },
            "latency_ms": 0.0,
            "shadow_mode": True,
            "bounds_checked": {},
        }, filepath=ledger_filepath))
    except Exception:
        decision["ledger_appended"] = False
    return decision


def scan_allowlist(
    symbols: list[str],
    bars: list[Bar],
    budget: float,
    account_cash: float,
    now: float | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full-allowlist load scan: run the chain once per allowlisted symbol
    on the same live feed and report pass/block counts and wall time.

    A symbol that produces no trigger is WAITING, not an error — the scan
    proves the chain loads and evaluates every allowlist entry without
    crashing, and that no entry can emit an order without passing risk.
    """
    started = time.time()
    results: dict[str, str] = {}
    for symbol in symbols:
        decision = run_day_trader_chain(symbol, bars, budget, account_cash,
                                        now=now, config=config)
        results[symbol] = str(decision.get("verdict", "UNKNOWN"))
    elapsed = time.time() - started
    counts: dict[str, int] = {}
    for verdict in results.values():
        counts[verdict] = counts.get(verdict, 0) + 1
    return {"symbols": len(symbols), "elapsed_sec": round(elapsed, 3),
            "counts": counts, "results": results}
