#!/usr/bin/env python3
"""backtest_engine.py — event-driven backtester mirroring the LIVE Stratex governor.

Runs on the server against the CSVs from pull_history.py. Imports each
strategy_* module and calls get_signal(df) exactly like the live daemon,
then simulates the governor's gates and fills:

Gates mirrored from autonomy/run_daemon.py:
  - stop_pct must be within [0.5%, 3%]
  - TP must clear the same 0.5% fee floor
  - expectancy >= 0.1R using the strategy's own win-rate prior
  - one position per symbol (no pyramiding)
  - re-entry cooldown after exit
  - daily loss breaker at -3% (stops new entries for the day)
Costs: 0.08% round-trip fees + 0.05% slippage per side (market orders).
Sizing: risk 0.5% of equity per trade (matches live).

Performance: get_signal costs ~24 ms/call (pandas op overhead), so this
engine evaluates signals on a STRIDE with backward refinement: candidate
bars every `stride` bars; when a candidate fires, bars inside the skipped
gap are re-checked (earliest-first) so the entry bar equals what a
per-bar evaluation would have produced for persistent conditions.
Stride=1 is exactly per-bar. Position exits are vectorized numpy scans.

Usage: python backtest_engine.py <strategy_module> <symbol> <timeframe> [start] [end] [stride]
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pandas as pd

DATA = "/opt/friday_universe/backtest_data"
OUT = "/opt/friday_universe/backtest_results"

# --- governor constants (mirror autonomy/run_daemon.py defaults) ---
RISK_PER_TRADE = 0.005
MIN_STOP_PCT = 0.005
MAX_STOP_PCT = 0.030
FEE_RT = 0.0008          # round-trip taker fees
SLIP = 0.0005            # per-side slippage on market fills
MIN_EXPECTANCY_R = 0.10
COOLDOWN_BARS = {"1d": 1, "4h": 6, "1h": 15, "15m": 60, "5m": 180, "1m": 900}
DAILY_LOSS_PCT = 0.03
START_EQUITY = 10_000.0
WARMUP = 150             # bars before the first candidate
WINDOW = 300             # history rows passed to get_signal
TF_SECONDS = {"1d": 86400, "4h": 14400, "1h": 3600, "15m": 900, "5m": 300, "1m": 60}

_DF_CACHE: dict[tuple, pd.DataFrame] = {}


def load_df(symbol: str, tf: str) -> pd.DataFrame | None:
    key = (symbol, tf)
    if key in _DF_CACHE:
        return _DF_CACHE[key]
    p = f"{DATA}/{symbol}_{tf}.csv"
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    _DF_CACHE[key] = df
    return df


def _prepare(mod, symbol: str, tf: str, start, end):
    """Returns (dfw, ts_n, high, low, close, day, entry_from_ts) or None."""
    df = load_df(symbol, tf)
    if df is None or len(df) < 120:
        return None
    if start:  # OOS: keep warm-up history before start, but gate entries
        buf = pd.Timedelta(seconds=400 * TF_SECONDS.get(tf, 3600))
        df = df[df.index >= pd.Timestamp(start) - buf]
        entry_from_ts = pd.Timestamp(start).value
    else:
        entry_from_ts = 0
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    if len(df) < 100:
        return None

    get_signal = getattr(mod, "get_signal", None)
    if get_signal is None:
        return None

    bars = df.reset_index()
    if "index" in bars.columns:
        bars = bars.rename(columns={"index": "ts"})
    elif "timestamp" in bars.columns:
        bars = bars.rename(columns={"timestamp": "ts"})
    if "ts" not in bars.columns:  # index had no name
        bars.columns = ["ts"] + list(bars.columns[1:])

    ts_n = bars["ts"].values.astype("int64")
    high = bars["high"].values.astype(float)
    low = bars["low"].values.astype(float)
    close = bars["close"].values.astype(float)
    day = ts_n // 86_400_000_000_000
    return df, ts_n, high, low, close, day, entry_from_ts


def run_backtest(mod, symbol: str, tf: str, start=None, end=None,
                 equity=START_EQUITY, stride: int = 1) -> dict | None:
    prep = _prepare(mod, symbol, tf, start, end)
    if prep is None:
        return None
    df, ts_n, high, low, close, day, entry_from_ts = prep
    n = len(df)
    get_signal = mod.get_signal
    prior = float(getattr(mod, "_OOS_WIN_RATE_PRIOR", 0.5) or 0.5)
    cd = COOLDOWN_BARS.get(tf, 15)
    stride = max(1, int(stride))

    trades = []
    fills = []            # (bar_idx, eq_after)
    n_evals = 0
    cooldown_until = 0
    first_allowed = int(np.searchsorted(ts_n, entry_from_ts)) if entry_from_ts else 0
    i = max(WARMUP, first_allowed)

    def window(k):
        nonlocal n_evals
        n_evals += 1
        try:
            return get_signal(df.iloc[max(0, k - WINDOW):k + 1])
        except Exception:
            return None

    def day_start_equity(d):
        eq0 = equity
        for j, eq_after in fills:
            if day[j] < d:
                eq0 = eq_after
        return eq0

    while i < n:
        # --- flat: skip cooldown / OOS gate, then scan candidates on the stride grid ---
        if i < cooldown_until:
            i = cooldown_until
            if i >= n:
                break
        k = i
        sig = None
        entry_k = -1
        orig_k = -1
        while k < n:
            s = window(k)
            if s is not None and getattr(s, "side", None) in ("BUY", "SELL"):
                sig = s
                orig_k = k
                entry_k = k
                lo = max(i, k - (stride - 1))
                for m in range(lo, k):  # earliest-first refinement within the gap
                    s2 = window(m)
                    if s2 is not None and getattr(s2, "side", None) in ("BUY", "SELL"):
                        sig = s2
                        entry_k = m
                        break
                break
            k += stride
        if sig is None:
            break

        # daily loss breaker: skip to the next UTC day if this day is stopped
        d = day[entry_k]
        eq0 = day_start_equity(d)
        if eq0 > 0 and (eq0 - equity) / eq0 >= DAILY_LOSS_PCT:
            nxt = int(np.searchsorted(day, d + 1))
            if nxt >= n:
                break
            i = max(nxt, orig_k + 1)
            continue

        px = float(close[entry_k])
        sl = float(sig.sl) if sig.sl else None
        tp = float(sig.tp) if sig.tp else None
        entered = False
        if sl and tp and px > 0:
            stop_pct = abs(px - sl) / px
            tp_pct = abs(tp - px) / px
            if (MIN_STOP_PCT <= stop_pct <= MAX_STOP_PCT and tp_pct >= MIN_STOP_PCT):
                rr = tp_pct / stop_pct
                fee_r = FEE_RT / stop_pct
                exp = prior * rr - (1 - prior) - fee_r
                if exp >= MIN_EXPECTANCY_R:
                    qty = (equity * RISK_PER_TRADE) / abs(px - sl)
                    entry_px = px * (1 + SLIP if sig.side == "BUY" else 1 - SLIP)
                    side = sig.side
                    entered = True

        if not entered:
            i = orig_k + stride  # skip the known-firing region; resume the grid
            continue

        # --- in position: vectorized exit scan (SL wins if both hit in one bar) ---
        seg_sl = (low[entry_k + 1:] <= sl) if side == "BUY" else (high[entry_k + 1:] >= sl)
        seg_tp = (high[entry_k + 1:] >= tp) if side == "BUY" else (low[entry_k + 1:] <= tp)
        hit = seg_sl | seg_tp
        exit_j = n - 1
        hit_sl_final = False
        if hit.any():
            rel = int(np.argmax(hit))
            exit_j = entry_k + 1 + rel
            hit_sl_final = bool(seg_sl[rel])
        if side == "BUY":
            exit_px = sl if hit_sl_final else tp
            exit_px *= (1 - SLIP)
            pnl = (exit_px - entry_px) * qty
        else:
            exit_px = sl if hit_sl_final else tp
            exit_px *= (1 + SLIP)
            pnl = (entry_px - exit_px) * qty
        equity += pnl
        fills.append((exit_j, equity))
        cooldown_until = exit_j + cd
        trades.append({
            "ts": pd.Timestamp(ts_n[entry_k]), "exit_ts": pd.Timestamp(ts_n[exit_j]),
            "side": side, "entry": entry_px, "exit": exit_px, "pnl": pnl,
            "bars_held": exit_j - entry_k,
        })
        i = exit_j + 1

    if not trades:
        return None

    t = pd.DataFrame(trades)
    wins = t[t.pnl > 0]
    losses = t[t.pnl <= 0]
    ret = equity - START_EQUITY
    days = max((ts_n[-1] - ts_n[0]) / 86_400_000_000_000, 1)
    curve = START_EQUITY + t.pnl.cumsum()
    dd = (curve - curve.cummax()).min()

    return {
        "trades": len(t), "win_rate": len(wins) / len(t),
        "net_pnl": ret, "ret_pct": ret / START_EQUITY * 100,
        "sharpe_trade": t.pnl.mean() / t.pnl.std() * math.sqrt(len(t)) if len(t) > 2 and t.pnl.std() > 0 else 0,
        "avg_win": wins.pnl.mean() if len(wins) else 0,
        "avg_loss": losses.pnl.mean() if len(losses) else 0,
        "profit_factor": wins.pnl.sum() / abs(losses.pnl.sum()) if len(losses) and losses.pnl.sum() != 0 else float("inf") if len(wins) else 0,
        "max_dd": dd, "avg_bars_held": t.bars_held.mean(),
        "start": str(pd.Timestamp(ts_n[0]).date()), "end": str(pd.Timestamp(ts_n[-1]).date()),
        "n_evals": n_evals,
    }


def main():
    import importlib
    mod_name, symbol, tf = sys.argv[1], sys.argv[2], sys.argv[3]
    start = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    end = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "-" else None
    stride = int(sys.argv[6]) if len(sys.argv) > 6 else 1
    mod = importlib.import_module(mod_name)
    res = run_backtest(mod, symbol, tf, start, end, stride=stride)
    tag = "OOS" if start else "IS"
    if res:
        print(f"OK {mod_name} {symbol} {tf} {tag}: {res['trades']} trades "
              f"net {res['net_pnl']:+.0f} wr {res['win_rate']:.2f} "
              f"pf {res['profit_factor']:.2f} evals {res['n_evals']}")
    else:
        print(f"NONE {mod_name} {symbol} {tf} {tag}")


if __name__ == "__main__":
    main()
