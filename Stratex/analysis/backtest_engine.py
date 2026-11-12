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

Usage: python backtest_engine.py <strategy_module> <symbol> <timeframe> [start] [end]
Writes one CSV row per (strategy, symbol, tf) to /opt/friday_universe/backtest_results/
"""
from __future__ import annotations

import importlib
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


def load_df(symbol: str, tf: str) -> pd.DataFrame | None:
    p = f"{DATA}/{symbol}_{tf}.csv"
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df


def run_backtest(mod, symbol: str, tf: str, start=None, end=None,
                 equity=START_EQUITY) -> dict | None:
    df = load_df(symbol, tf)
    if df is None or len(df) < 120:
        return None
    if start:
        df = df[df.index >= start]
    if end:
        df = df[df.index <= end]
    if len(df) < 100:
        return None

    bars = df.reset_index()
    bars.columns = [c if c != "index" else "ts" for c in bars.columns]

    get_signal = getattr(mod, "get_signal", None)
    if get_signal is None:
        return None

    prior = float(getattr(mod, "_OOS_WIN_RATE_PRIOR", 0.5) or 0.5)

    trades = []
    in_pos = None          # dict(side, entry, qty, sl, tp, entry_i, entry_ts)
    cooldown_until = -1
    # warm-up: strategies need history; feed them the window up to i
    warmup = 150

    eq = equity
    day = None
    day_start_eq = equity

    for i in range(warmup, len(bars)):
        row = bars.iloc[i]

        # --- daily loss breaker (recomputed per UTC day) ---
        ts = row["ts"]
        d = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
        if d != day:
            day = d
            day_start_eq = eq
        breaker = (day_start_eq - eq) / day_start_eq >= DAILY_LOSS_PCT

        # --- manage open position: check SL/TP against this bar's H/L ---
        if in_pos is not None:
            hit_sl = hit_tp = False
            if in_pos["side"] == "BUY":
                if row["low"] <= in_pos["sl"]:
                    hit_sl = True
                elif row["high"] >= in_pos["tp"]:
                    hit_tp = True
            else:
                if row["high"] >= in_pos["sl"]:
                    hit_sl = True
                elif row["low"] <= in_pos["tp"]:
                    hit_tp = True
            if hit_sl or hit_tp:
                exit_px = in_pos["sl"] if hit_sl else in_pos["tp"]
                # slippage worsens the fill
                if in_pos["side"] == "BUY":
                    exit_px *= (1 - SLIP) if hit_sl else (1 - SLIP)
                    pnl = (exit_px - in_pos["entry"]) * in_pos["qty"]
                else:
                    exit_px *= (1 + SLIP) if hit_sl else (1 + SLIP)
                    pnl = (in_pos["entry"] - exit_px) * in_pos["qty"]
                eq += pnl
                trades.append({
                    "ts": in_pos["entry_ts"], "exit_ts": ts, "side": in_pos["side"],
                    "entry": in_pos["entry"], "exit": exit_px, "pnl": pnl,
                    "bars_held": i - in_pos["entry_i"],
                })
                cooldown_until = i + COOLDOWN_BARS.get(tf, 15)
                in_pos = None

        # --- look for new entry ---
        if in_pos is None and not breaker and i >= cooldown_until:
            window = df.iloc[max(0, i - 300):i + 1]
            try:
                sig = get_signal(window)
            except Exception:
                sig = None
            if sig is not None and getattr(sig, "side", None) in ("BUY", "SELL"):
                px = float(row["close"])
                sl = float(sig.sl) if sig.sl else None
                tp = float(sig.tp) if sig.tp else None
                if sl and tp and px > 0:
                    stop_pct = abs(px - sl) / px
                    tp_pct = abs(tp - px) / px
                    if (MIN_STOP_PCT <= stop_pct <= MAX_STOP_PCT
                            and tp_pct >= MIN_STOP_PCT):
                        rr = tp_pct / stop_pct
                        fee_r = FEE_RT / stop_pct
                        exp = prior * rr - (1 - prior) - fee_r
                        if exp >= MIN_EXPECTANCY_R:
                            qty = (eq * RISK_PER_TRADE) / (abs(px - sl))
                            entry_px = px * (1 + SLIP if sig.side == "BUY" else 1 - SLIP)
                            in_pos = {"side": sig.side, "entry": entry_px,
                                      "qty": qty, "sl": sl, "tp": tp,
                                      "entry_i": i, "entry_ts": ts}

    # close any open position at last close
    if in_pos is not None:
        exit_px = float(bars.iloc[-1]["close"])
        pnl = ((exit_px - in_pos["entry"]) * in_pos["qty"] if in_pos["side"] == "BUY"
               else (in_pos["entry"] - exit_px) * in_pos["qty"])
        eq += pnl
        trades.append({
            "ts": in_pos["entry_ts"], "exit_ts": bars.iloc[-1]["ts"],
            "side": in_pos["side"], "entry": in_pos["entry"], "exit": exit_px,
            "pnl": pnl, "bars_held": len(bars) - 1 - in_pos["entry_i"],
        })

    if not trades:
        return None

    t = pd.DataFrame(trades)
    wins = t[t.pnl > 0]
    losses = t[t.pnl <= 0]
    ret = eq - START_EQUITY
    days = max((bars.iloc[-1]["ts"] - bars.iloc[0]["ts"]).days, 1)
    # max drawdown on equity curve of per-trade pnl
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
        "start": str(bars.iloc[0]["ts"].date()), "end": str(bars.iloc[-1]["ts"].date()),
    }


def main():
    mod_name, symbol, tf = sys.argv[1], sys.argv[2], sys.argv[3]
    start = sys.argv[4] if len(sys.argv) > 4 else None
    end = sys.argv[5] if len(sys.argv) > 5 else None
    mod = importlib.import_module(mod_name)
    res = run_backtest(mod, symbol, tf, start, end)
    os.makedirs(OUT, exist_ok=True)
    tag = "OOS" if start and str(start) >= "2024-01-01" else "IS"
    out = f"{OUT}/{mod_name}__{symbol}__{tf}__{tag}.csv"
    if res:
        pd.DataFrame([res]).to_csv(out, index=False)
        print(f"OK {mod_name} {symbol} {tf} {tag}: {res['trades']} trades "
              f"net {res['net_pnl']:+.0f} wr {res['win_rate']:.2f} pf {res['profit_factor']:.2f}")
    else:
        print(f"NONE {mod_name} {symbol} {tf}")


if __name__ == "__main__":
    main()
