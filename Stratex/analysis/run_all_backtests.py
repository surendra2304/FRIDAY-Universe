#!/usr/bin/env python3
"""run_all_backtests.py — sweep every strategy x symbol x timeframe on the server.

In-sample (IS): full history up to 2023-12-31 (rank here)
Out-of-sample (OOS): 2024-01-01 -> now (validate here)

Writes per-run CSVs to /opt/friday_universe/backtest_results/ and a
consolidated summary CSV at the end. Skips missing data. Sequential and
polite (single process); prints progress.
"""
from __future__ import annotations

import importlib
import os
import sys
import time

import pandas as pd

sys.path.insert(0, "/opt/friday_universe/Stratex")
os.chdir("/opt/friday_universe/Stratex")

from analysis.backtest_engine import run_backtest  # noqa: E402

DATA = "/opt/friday_universe/backtest_data"
OUT = "/opt/friday_universe/backtest_results"

STRATEGIES = [
    "strategy_adx_ema", "strategy_adx_ema_mtf", "strategy_adx_trend",
    "strategy_aggressive_scalper", "strategy_aggressor", "strategy_atr_breakout",
    "strategy_bb_reversion", "strategy_bollinger", "strategy_breakout_retest",
    "strategy_breakout_vol", "strategy_channel_breakout",
    "strategy_donchian_observe_only", "strategy_ema_crossover",
    "strategy_factory_winner_1", "strategy_factory_winner_2",
    "strategy_factory_winner_3", "strategy_factory_winner_4",
    "strategy_factory_winner_5", "strategy_fast_ema_cross",
    "strategy_higher_highs", "strategy_hybrid", "strategy_mean_reversion_scalper",
    "strategy_ml", "strategy_momentum", "strategy_rsi_burst",
    "strategy_rsi_divergence_scalper", "strategy_rsi_extreme", "strategy_scalper",
    "strategy_scalping_breakout", "strategy_supertrend", "strategy_swing",
    "strategy_trend_continuation", "strategy_trend_daily", "strategy_trend_pullback",
    "strategy_volatility_breakout", "strategy_volume_breakout",
    "strategy_vwap_scalper", "strategy_vwap_trend",
]

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
           "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "ATOMUSDT", "TRXUSDT"]

# timeframes we have data for
TFS = ["1d", "1h", "15m"]

IS_END = "2023-12-31"
OOS_START = "2024-01-01"


def main():
    os.makedirs(OUT, exist_ok=True)
    # clean previous run
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))

    rows = []
    mods = {}
    for s in STRATEGIES:
        try:
            mods[s] = importlib.import_module(s)
        except Exception as e:
            print(f"IMPORT FAIL {s}: {e}", flush=True)

    combos = [(s, sym, tf) for s in mods for sym in SYMBOLS for tf in TFS
              if os.path.exists(f"{DATA}/{sym}_{tf}.csv")]
    total = len(combos) * 2  # IS + OOS
    n = 0
    t0 = time.time()
    for s, sym, tf in combos:
        for tag, start, end in (("IS", None, IS_END), ("OOS", OOS_START, None)):
            n += 1
            if n % 50 == 0:
                print(f"[{n}/{total}] {time.time()-t0:.0f}s elapsed", flush=True)
            try:
                r = run_backtest(mods[s], sym, tf, start, end)
            except Exception as e:
                print(f"RUN FAIL {s} {sym} {tf} {tag}: {type(e).__name__} {e}", flush=True)
                continue
            if r is None:
                continue
            r.update(strategy=s, symbol=sym, tf=tf, tag=tag)
            rows.append(r)

    df = pd.DataFrame(rows)
    df.to_csv(f"{OUT}/_summary_all.csv", index=False)
    print(f"DONE {len(df)} results in {time.time()-t0:.0f}s -> _summary_all.csv")


if __name__ == "__main__":
    main()
