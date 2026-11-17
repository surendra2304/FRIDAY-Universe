#!/usr/bin/env python3
"""ORB/VWAP signal + judging harness (TASK-STR-DISC-004) — DECLARED RULES ONLY.

Implements the frozen declaration `orb_vwap_declaration.json`
(SHA-256 43063a6cdf8089d7d41bd39e4b02c1c05bf5528c3837590c167f87d2907dafc9)
verbatim. If this code and the declaration disagree, the declaration
wins and this code is wrong.

Rules (declaration rules 1–10 + declared conventions):
  * Universe: the 15 frozen symbols; 15-minute bars; US regular
    session only, bars grouped by ET date, sorted by start time.
  * Opening range = max high / min low of the FIRST TWO 15m bars
    (bar-starts 09:30 and 09:45 ET). Missing either, or a zero-height
    range, -> no trade that symbol-session.
  * Session VWAP from the session's own bars only:
    VWAP_t = sum(TP_i * V_i) / sum(V_i), TP = (H+L+C)/3, cumulative
    from the session open through bar t inclusive. The vendor per-bar
    vwap field is NOT used. Cumulative volume zero -> VWAP undefined
    -> candidate rejected.
  * Entry candidate = the FIRST bar after the range bars that CLOSES
    beyond the range (close > range high LONG, close < range low
    SHORT). The candidate may not be the session's final bar.
  * VWAP veto: a long candidate needs close > VWAP (through the
    candidate bar inclusive); a short needs close < VWAP. If the
    first candidate fails the veto there is NO trade that
    symbol-session — no later breakout is considered.
  * Entry at the candidate bar's close; at most ONE trade per symbol
    per session. Stop = opposite end of the range; R = |entry-stop|;
    target = entry +/- 2.0 * R (TARGET_R frozen).
  * No lookahead: SL/TP evaluated from the NEXT bar onward. Within a
    bar, STOP is assumed hit before TARGET (programme worst case).
    A bar that opens beyond a level fills at the open (simulator gap
    convention).
  * HARD flat-by-close: if neither level triggers by the session's
    final bar, exit at that bar's close (SESSION_CLOSE). Never held
    overnight.
  * Costs (declaration, recorded reading identical to the SRS
    holdout addendum section 6): programme Costs() — 5 bps fee +
    3 bps slip per side = 16 bps round trip at 1x; the 2x shadow
    doubles the per-side rate (32 bps round trip). Net return in
    price space exactly as simulator._net_return.

Judging (pooled OOS, entry-time attribution, walkforward.FOLDS):
  >= 200 pooled trades (else the verdict is exactly
  "insufficient OOS trades") · expectancy_net > 0 at 1x AND at the
  2x shadow · PF_net >= 1.2 at 1x · >= 4/5 folds positive ·
  TEMPORAL HOLDOUT v1 H1–H4 on the pooled list (H = W5, D = W1–W4;
  H5 judged-once is procedural, reported NOT_EVALUATED_BY_CODE) ·
  breadth: no symbol > 50% of total positive net profit ·
  Bonferroni: one-sided normal-approx p vs alpha = 0.05 / final_N,
  final_N = entering trials + 1 (this family is ONE cell).

Stdlib only, so it runs identically in the sandbox and on the fleet.
Panel input: per-symbol CSVs written by pull_orb_panel.py
(timestamp_et, open, high, low, close, volume, ...).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DECLARATION_SHA256 = "43063a6cdf8089d7d41bd39e4b02c1c05bf5528c3837590c167f87d2907dafc9"
TARGET_R = 2.0
FEE_BPS_PER_SIDE = 5.0
SLIP_BPS_PER_SIDE = 3.0
UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO",
            "TSLA", "AMD", "NFLX", "XOM", "BAC", "MU", "INTC", "PLTR"]
FOLDS = [  # walkforward.FOLDS, verbatim (UTC, end exclusive)
    ("W1", "2024-07-01", "2025-01-01"),
    ("W2", "2025-01-01", "2025-07-01"),
    ("W3", "2025-07-01", "2026-01-01"),
    ("W4", "2026-01-01", "2026-07-01"),
    ("W5", "2026-07-01", "2026-11-01"),
]
BAR = {"expectancy_net_gt": 0.0, "profit_factor_net_gte": 1.2,
       "min_oos_trades": 200, "min_positive_folds": 4,
       "max_symbol_profit_share": 0.50}


# ---------------------------------------------------------------- costs
def net_return(side: str, entry: float, exit_: float,
               cost_multiplier: float = 1.0) -> float:
    r = (FEE_BPS_PER_SIDE + SLIP_BPS_PER_SIDE) / 10000.0 * cost_multiplier
    if side == "LONG":
        ea, xa = entry * (1 + r), exit_ * (1 - r)
        return (xa - ea) / ea
    ea, xa = entry * (1 - r), exit_ * (1 + r)
    return (ea - xa) / ea


# ----------------------------------------------------------------- bars
def load_panel(path: Path, symbol: str) -> list[dict]:
    bars = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            et = datetime.fromisoformat(r["timestamp_et"])
            bars.append({
                "symbol": symbol,
                "start_et": et, "date_et": et.date(),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]), "close": float(r["close"]),
                "volume": float(r.get("volume") or 0),
            })
    bars.sort(key=lambda b: b["start_et"])
    return bars


def group_sessions(bars: list[dict]) -> dict:
    sessions: dict = defaultdict(list)
    for b in bars:
        sessions[b["date_et"]].append(b)
    for s in sessions.values():
        s.sort(key=lambda b: b["start_et"])
    return dict(sorted(sessions.items()))


# ----------------------------------------------------------------- vwap
def session_vwap_through(session_bars: list[dict], idx: int) -> float | None:
    """Cumulative session VWAP through bar `idx` inclusive.

    TP = (H+L+C)/3, volume-weighted from the session's first bar.
    None when cumulative volume is zero (VWAP undefined)."""
    pv = 0.0
    vol = 0.0
    for b in session_bars[: idx + 1]:
        tp = (b["high"] + b["low"] + b["close"]) / 3.0
        pv += tp * b["volume"]
        vol += b["volume"]
    if vol <= 0:
        return None
    return pv / vol


# ---------------------------------------------------------------- signal
def session_trade(session_bars: list[dict], symbol: str,
                  cost_multiplier: float = 1.0) -> dict | None:
    """The declared ORB/VWAP rules for one symbol-session. None = no trade."""
    if len(session_bars) < 4:
        return None  # need 2 range bars + a candidate + a managing bar
    first, second = session_bars[0], session_bars[1]
    if first["start_et"].time() != time(9, 30) or \
            second["start_et"].time() != time(9, 45):
        return None  # first two candles missing -> no signals
    range_high = max(first["high"], second["high"])
    range_low = min(first["low"], second["low"])
    if range_high <= range_low:
        return None  # zero-height range -> no signals

    # First close beyond the range; the candidate may not be the
    # session's final bar (index len-1), so the scan stops at len-2.
    entry_idx = None
    side = None
    for i in range(2, len(session_bars) - 1):
        bar = session_bars[i]
        if bar["close"] > range_high:
            entry_idx, side = i, "LONG"
            break
        if bar["close"] < range_low:
            entry_idx, side = i, "SHORT"
            break
    if entry_idx is None:
        return None

    entry_bar = session_bars[entry_idx]
    entry_price = entry_bar["close"]

    # VWAP veto — the first candidate is the session's only candidate.
    vwap = session_vwap_through(session_bars, entry_idx)
    if vwap is None:
        return None  # VWAP undefined (zero cumulative volume) -> rejected
    if side == "LONG" and not entry_price > vwap:
        return None
    if side == "SHORT" and not entry_price < vwap:
        return None

    if side == "LONG":
        stop = range_low
        risk = entry_price - stop
        target = entry_price + TARGET_R * risk
    else:
        stop = range_high
        risk = stop - entry_price
        target = entry_price - TARGET_R * risk
    if risk <= 0:
        return None  # unreachable given close beyond range; fail closed

    exit_price = None
    exit_bar = None
    reason = None
    for j in range(entry_idx + 1, len(session_bars)):  # next bar onward
        bar = session_bars[j]
        if side == "LONG":
            if bar["open"] <= stop:
                exit_price, reason = bar["open"], "SL"
            elif bar["low"] <= stop:
                exit_price, reason = stop, "SL"
            elif bar["open"] >= target:
                exit_price, reason = bar["open"], "TP"
            elif bar["high"] >= target:
                exit_price, reason = target, "TP"
        else:
            if bar["open"] >= stop:
                exit_price, reason = bar["open"], "SL"
            elif bar["high"] >= stop:
                exit_price, reason = stop, "SL"
            elif bar["open"] <= target:
                exit_price, reason = bar["open"], "TP"
            elif bar["low"] <= target:
                exit_price, reason = target, "TP"
        if exit_price is not None:
            exit_bar = bar
            break
    if exit_price is None:
        exit_bar = session_bars[-1]
        exit_price = exit_bar["close"]
        reason = "SESSION_CLOSE"

    entry_time_utc = entry_bar["start_et"].astimezone(timezone.utc)
    exit_time_utc = exit_bar["start_et"].astimezone(timezone.utc)
    return {
        "symbol": symbol,
        "session_date_et": str(entry_bar["date_et"]),
        "entry_time": entry_time_utc.isoformat(),
        "exit_time": exit_time_utc.isoformat(),
        "side": side,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "range_high": range_high,
        "range_low": range_low,
        "vwap_at_entry": vwap,
        "stop_price": stop,
        "target_price": target,
        "risk_r": risk,
        "net_return": net_return(side, entry_price, exit_price,
                                 cost_multiplier),
        "exit_reason": reason,
    }


def generate_trades(bars_by_symbol: dict[str, list[dict]],
                    cost_multiplier: float = 1.0) -> list[dict]:
    trades = []
    for symbol in UNIVERSE:
        bars = bars_by_symbol.get(symbol)
        if not bars:
            continue
        for _date, s_bars in group_sessions(bars).items():
            t = session_trade(s_bars, symbol, cost_multiplier)
            if t is not None:
                trades.append(t)
    trades.sort(key=lambda t: t["entry_time"])
    return trades


# --------------------------------------------------------------- metrics
def trade_metrics(trades: list[dict]) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0, "win_rate": None, "expectancy_net": None,
                "profit_factor_net": None, "total_net_return": 0.0}
    rets = [t["net_return"] for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_win > 0 else None)
    return {"trades": n, "win_rate": len(wins) / n,
            "expectancy_net": sum(rets) / n,
            "profit_factor_net": pf, "total_net_return": sum(rets)}


def fold_of(entry_time_iso: str) -> str | None:
    et = datetime.fromisoformat(entry_time_iso)
    for fid, s, e in FOLDS:
        if datetime.fromisoformat(s).replace(tzinfo=timezone.utc) <= et < \
                datetime.fromisoformat(e).replace(tzinfo=timezone.utc):
            return fid
    return None


def oos_split(trades: list[dict]) -> dict:
    per_fold = {}
    pooled = []
    for fid, _s, _e in FOLDS:
        ft = [t for t in trades if fold_of(t["entry_time"]) == fid]
        per_fold[fid] = trade_metrics(ft)
        pooled.extend(ft)
    return {"per_fold": per_fold, "pooled_oos": trade_metrics(pooled),
            "pooled_trades": pooled}


def temporal_holdout(trades_oos: list[dict]) -> dict:
    """SRS TEMPORAL HOLDOUT v1, H1–H4 (addendum section 2.2), pooled list."""
    d = [t for t in trades_oos if fold_of(t["entry_time"]) in
         ("W1", "W2", "W3", "W4")]
    h = [t for t in trades_oos if fold_of(t["entry_time"]) == "W5"]
    md, mh = trade_metrics(d), trade_metrics(h)
    profits = {}
    for fid, _s, _e in FOLDS:
        ft = [t for t in trades_oos if fold_of(t["entry_time"]) == fid]
        profits[fid] = sum(t["net_return"] for t in ft)
    total_pos = sum(p for p in profits.values() if p > 0)
    max_share = (max(profits.values()) / total_pos) if total_pos > 0 else 1.0
    checks = {
        "H1_holdout_size_gte_20": len(h) >= 20,
        "H2_holdout_expectancy_gt_0": (mh["expectancy_net"] or 0) > 0
                                      if mh["trades"] else False,
        "H3_development_expectancy_gt_0": (md["expectancy_net"] or 0) > 0
                                          if md["trades"] else False,
        "H4_max_fold_profit_share_lte_0.80": total_pos > 0 and max_share <= 0.80,
    }
    return {"D_trades": len(d), "H_trades": len(h),
            "D_metrics": md, "H_metrics": mh,
            "fold_profits": profits, "max_fold_profit_share": max_share,
            "checks": checks, "passes": all(checks.values()),
            "H5_judged_once": "NOT_EVALUATED_BY_CODE — procedural burn "
                              "clause; enforced by the run procedure "
                              "(holdout addendum section 2.3), not by metrics."}


def breadth_check(trades_oos: list[dict]) -> dict:
    """No symbol > 50% of the pooled total positive net profit."""
    profits: dict[str, float] = {}
    for t in trades_oos:
        profits[t["symbol"]] = profits.get(t["symbol"], 0.0) + t["net_return"]
    total_pos = sum(p for p in profits.values() if p > 0)
    max_share = (max(profits.values()) / total_pos) if total_pos > 0 else 1.0
    return {"per_symbol_profit": profits,
            "total_positive_profit": total_pos,
            "max_symbol_profit_share": max_share,
            "passes": total_pos > 0 and
                      max_share <= BAR["max_symbol_profit_share"]}


def bonferroni_p(trades_oos: list[dict]) -> float | None:
    """One-sided normal-approx p for expectancy > 0 on pooled 1x returns."""
    rets = [t["net_return"] for t in trades_oos]
    n = len(rets)
    if n < 2:
        return None
    mean = sum(rets) / n
    var = sum((r - mean) ** 2 for r in rets) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0 if mean > 0 else 1.0
    z = mean / (sd / math.sqrt(n))
    return 0.5 * math.erfc(z / math.sqrt(2))


# ------------------------------------------------------------------ judge
def judge(bars_by_symbol: dict[str, list[dict]], entering_trials: int,
          label: str) -> dict:
    trades_1x = generate_trades(bars_by_symbol, 1.0)
    trades_2x = generate_trades(bars_by_symbol, 2.0)
    split_1x = oos_split(trades_1x)
    split_2x = oos_split(trades_2x)
    pooled_1x = split_1x["pooled_oos"]
    pooled_2x = split_2x["pooled_oos"]
    pooled_trades = split_1x["pooled_trades"]
    pos_folds = sum(1 for m in split_1x["per_fold"].values()
                    if (m["expectancy_net"] or 0) > 0 and m["trades"])
    holdout = temporal_holdout(pooled_trades)
    breadth = breadth_check(pooled_trades)
    per_symbol = {sym: trade_metrics(
        [t for t in pooled_trades if t["symbol"] == sym]) for sym in UNIVERSE}
    final_n = entering_trials + 1
    alpha = 0.05 / final_n
    p = bonferroni_p(pooled_trades)
    pf = pooled_1x["profit_factor_net"]
    checks = {
        "min_oos_trades_200": pooled_1x["trades"] >= BAR["min_oos_trades"],
        "expectancy_net_gt_0_1x": (pooled_1x["expectancy_net"] or 0) > 0,
        "expectancy_net_gt_0_2x_shadow": (pooled_2x["expectancy_net"] or 0) > 0,
        "profit_factor_net_gte_1.2": pf is not None and pf != float("inf")
                                     and pf >= BAR["profit_factor_net_gte"],
        "positive_folds_gte_4_of_5": pos_folds >= BAR["min_positive_folds"],
        "temporal_holdout_H1_H4": holdout["passes"],
        "breadth_max_symbol_share_lte_0.50": breadth["passes"],
        "bonferroni_p_lt_alpha": p is not None and p < alpha,
    }
    passes = all(checks.values())
    if pooled_1x["trades"] < BAR["min_oos_trades"]:
        verdict = "insufficient OOS trades"
    elif holdout["H_trades"] < 20:
        verdict = "FAIL (INSUFFICIENT_HOLDOUT_TRADES)"
    elif passes:
        verdict = "PASS"
    else:
        verdict = "FAIL"
    trade_blob = json.dumps(pooled_trades, sort_keys=True).encode()
    return {
        "label": label,
        "family": "orb_vwap_equity_intraday",
        "declaration_sha256": DECLARATION_SHA256,
        "trade_list_sha256": hashlib.sha256(trade_blob).hexdigest(),
        "all_trades_generated": len(trades_1x),
        "pooled_oos_1x": pooled_1x,
        "pooled_oos_2x_shadow": pooled_2x,
        "per_fold_1x": split_1x["per_fold"],
        "per_symbol_oos_1x": per_symbol,
        "positive_folds": pos_folds,
        "temporal_holdout": holdout,
        "breadth": breadth,
        "trial_accounting": {"entering_trials": entering_trials,
                             "final_N": final_n, "bonferroni_alpha": alpha,
                             "p_value_normal_approx_1x": p},
        "bar_checks": checks,
        "passes_full_bar": passes,
        "verdict": verdict,
        "trades": pooled_trades,
    }
