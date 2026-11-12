#!/usr/bin/env python3
"""run_all_backtests.py — staged strategy sweep on the server.

get_signal costs ~24 ms/call, so the sweep is STAGED (screen wide cheap,
validate deep) and every worker runs at nice 19 so trading services are
never starved:

  Stage 0 (screen):  all strategies x 6 majors, 1d only, stride 10
  Stage 1 (confirm): top-N strategies x 4 majors, 1d stride 3 + 1h stride 5
  Stage 2 (final):   top-M strategies, all 6 majors, 1d+1h stride 3/5 + 15m stride 5 for top-M

Each run appends one row to /opt/friday_universe/backtest_results/stage_results.csv
incrementally; re-running a stage skips already-present (strategy,symbol,tf,tag)
rows, so interrupted sweeps resume for free.

IS  = history through 2023-12-31 (selection universe)
OOS = 2024-01-01 -> now (validation only)

Usage:
  python run_all_backtests.py --stage 0
  python run_all_backtests.py --stage 1 --strategies s1,s2 --symbols BTCUSDT,...
  python run_all_backtests.py --stage 2 --strategies s1,s2 [--tf 15m] [--stride 5]
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, "/opt/friday_universe/Stratex")
os.chdir("/opt/friday_universe/Stratex")

from analysis.backtest_engine import run_backtest  # noqa: E402

DATA = "/opt/friday_universe/backtest_data"
OUT = "/opt/friday_universe/backtest_results"
RESULTS_CSV = f"{OUT}/stage_results.csv"

ALL_STRATEGIES = [
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
    # new strategies (ZAI Agent 2)
    "strategy_donchian_turtle", "strategy_vol_regime",
    "strategy_momentum_rotation", "strategy_pullback_ema",
]

MAJORS6 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"]
TOPS4 = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]

IS_END = "2023-12-31"
OOS_START = "2024-01-01"

_FIELDS = ["strategy", "symbol", "tf", "tag", "trades", "win_rate", "net_pnl",
           "ret_pct", "sharpe_trade", "avg_win", "avg_loss", "profit_factor",
           "max_dd", "avg_bars_held", "start", "end", "n_evals", "error"]


def _worker_init():
    os.nice(19)


def _run_one(args):
    strat, symbol, tf, tag, stride = args
    try:
        mod = importlib.import_module(strat)
        if tag == "IS":
            r = run_backtest(mod, symbol, tf, start=None, end=IS_END, stride=stride)
        else:
            r = run_backtest(mod, symbol, tf, start=OOS_START, end=None, stride=stride)
        if r is None:
            return {"strategy": strat, "symbol": symbol, "tf": tf, "tag": tag,
                    "error": "no_trades"}
        r.update(strategy=strat, symbol=symbol, tf=tf, tag=tag, error="")
        return r
    except Exception as e:
        return {"strategy": strat, "symbol": symbol, "tf": tf, "tag": tag,
                "error": f"{type(e).__name__}: {e}"}


def _existing_keys():
    done = set()
    if os.path.exists(RESULTS_CSV):
        done = {(r["strategy"], r["symbol"], r["tf"], r["tag"])
                for r in _read_rows() if not (r.get("error") or "").strip()}
    return done


def _read_rows():
    import csv
    if not os.path.exists(RESULTS_CSV):
        return []
    with open(RESULTS_CSV) as f:
        return list(csv.DictReader(f))


def _append_row(r):
    import csv
    new = not os.path.exists(RESULTS_CSV)
    with open(RESULTS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: r.get(k, "") for k in _FIELDS})


def _build_jobs(stage: int, strategies, symbols, tf, stride, stride_is=None):
    jobs = []
    for s in strategies:
        for sym in symbols:
            path = f"{DATA}/{sym}_{tf}.csv"
            if not os.path.exists(path):
                continue
            jobs.append((s, sym, tf, "IS", stride_is if stride_is else stride))
            jobs.append((s, sym, tf, "OOS", stride))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, required=True)
    ap.add_argument("--strategies", default="")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--tf", default="1d")
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--stride-is", type=int, default=None)
    ap.add_argument("--processes", type=int, default=2)
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    strategies = ([s.strip() for s in args.strategies.split(",") if s.strip()]
                  or ALL_STRATEGIES)
    symbols = ([s.strip() for s in args.symbols.split(",") if s.strip()] or MAJORS6)

    jobs = _build_jobs(args.stage, strategies, symbols, args.tf,
                       args.stride, args.stride_is)
    done = _existing_keys()
    jobs = [j for j in jobs if (j[0], j[1], j[2], j[3]) not in done]
    print(f"stage {args.stage}: {len(jobs)} jobs to run "
          f"({len(done)} already done, {len(strategies)} strategies x {len(symbols)} symbols x {args.tf})",
          flush=True)
    if not jobs:
        print("NOTHING TO DO", flush=True)
        return

    t0 = time.time()
    n_done = 0
    with Pool(args.processes, initializer=_worker_init) as pool:
        for r in pool.imap_unordered(_run_one, jobs, chunksize=1):
            n_done += 1
            _append_row(r)
            err = r.get("error") or ""
            brief = (f"{r.get('trades')}t net{r.get('net_pnl', 0):+.0f} "
                     f"wr{r.get('win_rate', 0):.2f}" if not err else err)
            print(f"[{n_done}/{len(jobs)} {time.time()-t0:.0f}s] "
                  f"{r['strategy']} {r['symbol']} {r['tf']} {r['tag']}: {brief}",
                  flush=True)
    print(f"STAGE {args.stage} DONE {n_done} runs in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
