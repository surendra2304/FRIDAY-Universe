"""SMT-v2 retest (TASK-STR-RD-002 addendum, owner decision 2026-11-15:
'Retest it in the mega-grid first, then decide by the same rule').

Module-faithful: signals come from the ACTUAL deployed code
(oanda_demo.strategy.StratexTrendStrategy with the default
StrategyConfig — EMA 20/50/200 stack + slope, RSI(14) gate 52/48,
ATR% regime band, v2.1 extension/strength filters, spread gate at
0.35 x ATR using the project's own DEFAULT_SPREADS table from
oanda_demo/backtest.py). Native setup per oanda_demo/trader.py:
timeframe 4h, watchlist EURUSD GBPUSD USDJPY AUDUSD USDCAD NZDUSD
EURJPY EURGBP.

Exits follow the strategy's declared risk box: SL 1.5 x ATR,
TP 2.25 x ATR, stop moved to breakeven at +1R; stop-first when both
touch in one bar. ONE disclosed difference from oanda_demo/backtest.py:
that simulator never checks exits on the entry bar itself; this
evaluation checks exits from the entry bar onward (the harness
standard, and how broker-held stops behave live). Net returns are
price fractions minus the grid's per-class costs (costs2), so the row
is judged on identical accounting to every other RD-002 cell. The
project's own R-multiple accounting is reported as a cross-check in
the row detail.

Rows land in results_rd2/smt_rows/ and count in the global counter.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from oanda_demo.backtest import DEFAULT_SPREADS  # noqa: E402
from oanda_demo.strategy import StrategyConfig, StratexTrendStrategy  # noqa: E402

from ..simulator import Trade  # noqa: E402
from ..rd.common import dump_json, trades_to_json  # noqa: E402
from .costs2 import costs_for  # noqa: E402
from .panels import fold_profile, load_panel  # noqa: E402
from .stats2 import check_bar2, fold_report, holdout2, trade_stats  # noqa: E402

WATCHLIST = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
             "NZDUSD", "EURJPY", "EURGBP"]


def simulate_smt(df: pd.DataFrame, symbol: str, panel: str):
    """Faithful SMT-v2 simulation on one series. Returns (trades,
    project_accounting) where trades carry costs2-netted returns."""
    strat = StratexTrendStrategy(StrategyConfig())
    cfg = strat.cfg
    d = strat.add_indicators(df)
    cost = costs_for(panel, symbol)
    rt_frac = (2.0 * cost.fee_bps_per_side
               + 2.0 * cost.slip_bps_per_side) / 10000.0
    spread = DEFAULT_SPREADS.get(symbol)  # None: gate n/a (see detail)
    trades: list[Trade] = []
    rs = []
    pos = None
    n = len(d)
    opens = d["open"].to_numpy(dtype=float)
    highs = d["high"].to_numpy(dtype=float)
    lows = d["low"].to_numpy(dtype=float)
    closes = d["close"].to_numpy(dtype=float)
    index = d.index
    for i in range(cfg.min_bars, n - 1):
        if pos is None:
            side, _checks = strat.signal_at(d.iloc[i])
            if not side:
                continue
            a = float(d["atr"].iloc[i])
            if a <= 0 or (spread is not None and spread > cfg.max_spread_frac_atr * a):
                continue
            entry = opens[i + 1]
            if side == "LONG":
                sl, tp = entry - cfg.sl_atr_mult * a, entry + cfg.tp_atr_mult * a
            else:
                sl, tp = entry + cfg.sl_atr_mult * a, entry - cfg.tp_atr_mult * a
            risk = abs(entry - sl)
            if risk <= 0:
                continue
            pos = {"side": side, "entry": entry, "sl": sl, "tp": tp,
                   "risk": risk, "be": False, "i0": i + 1}
            j = i + 1  # exits checked from the entry bar onward
        else:
            j = i
            if j == pos["i0"]:
                continue  # entry bar already exit-checked at entry time
        direction = 1 if pos["side"] == "LONG" else -1
        exit_price = None
        hi, lo = highs[j], lows[j]
        if direction == 1:
            if lo <= pos["sl"]:
                exit_price = pos["sl"]
            elif hi >= pos["tp"]:
                exit_price = pos["tp"]
            elif not pos["be"] and hi >= pos["entry"] + cfg.breakeven_r * pos["risk"]:
                pos["sl"] = max(pos["sl"], pos["entry"])
                pos["be"] = True
        else:
            if hi >= pos["sl"]:
                exit_price = pos["sl"]
            elif lo <= pos["tp"]:
                exit_price = pos["tp"]
            elif not pos["be"] and lo <= pos["entry"] - cfg.breakeven_r * pos["risk"]:
                pos["sl"] = min(pos["sl"], pos["entry"])
                pos["be"] = True
        if exit_price is None:
            continue
        gross = direction * (exit_price - pos["entry"]) / pos["entry"]
        rs.append(direction * (exit_price - pos["entry"]) / pos["risk"])
        trades.append(Trade(
            symbol=symbol, entry_time=index[pos["i0"]], exit_time=index[j],
            side=pos["side"],
            entry_price=float(pos["entry"]), exit_price=float(exit_price),
            net_return=float(gross - rt_frac),
            exit_reason="SMT_BOX"))
        pos = None
    proj = {"trades": len(rs),
            "total_r": round(sum(rs), 2) if rs else 0.0,
            "avg_r": round(sum(rs) / len(rs), 3) if rs else 0.0,
            "winrate_pct": round(100.0 * sum(1 for r in rs if r > 0) / len(rs), 1) if rs else 0.0}
    return trades, proj


def run_cell(symbols: list[str], variant: str, out_dir: Path) -> dict:
    datasets = load_panel("forex12", "4h")
    datasets = {s: datasets[s] for s in symbols if s in datasets}
    all_trades, proj_all = [], {"trades": 0, "total_r": 0.0}
    per_proj = {}
    for sym, ds in datasets.items():
        trades, proj = simulate_smt(ds.df, sym, "forex12")
        all_trades.extend(trades)
        per_proj[sym] = proj
        proj_all["trades"] += proj["trades"]
        proj_all["total_r"] += proj["total_r"]
    syms = sorted(datasets.keys())
    profile = fold_profile("forex12", "4h")
    rep = fold_report(all_trades, profile, syms)
    hold = holdout2(rep, syms)
    start = pd.Timestamp(rep["per_fold"][profile[0]]["oos_start"], tz="UTC")
    row = {
        "family": "smt_v2", "variant": variant, "panel": "forex12",
        "timeframe": "4h", "asset_class": "forex", "status": "EVALUATED",
        "symbols": syms, "report": rep, "holdout": hold,
        "bar": check_bar2(rep, hold),
        "trade_stats": trade_stats(
            [t for t in all_trades if t.entry_time >= start]),
        "detail": {
            "declared_parameterisation": "oanda_demo StrategyConfig() defaults (deployed)",
            "native_timeframe": "4h (trader _DEFAULT_TF['smt'])",
            "project_accounting_pooled": proj_all,
            "project_accounting_by_symbol": per_proj,
            "cost_basis": "costs2 forex majors/minors RT bps (grid-consistent); spread gate uses project DEFAULT_SPREADS where the project declares a spread (the 8 watchlist pairs); the panel12 robustness cell includes 4 pairs with no project-declared spread, where the gate is not applicable and entries are ungated — disclosed extrapolation beyond the deployed watchlist",
            "simulator_note": "exits checked from entry bar onward (oanda_demo/backtest.py skips the entry bar — disclosed difference)",
        },
        "trades": trades_to_json(all_trades),
    }
    dump_json(out_dir / "smt_rows" / f"smt_v2__{variant}__forex12__4h.json", row)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    (out_dir / "smt_rows").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    row = run_cell(WATCHLIST, "default_deployed_watchlist8", out_dir)
    po = row["report"]["pooled_oos"]
    print(f"[smt] watchlist8@4h: trades={po['trades']} exp={po['expectancy_net']} "
          f"pf={po['profit_factor_net']} bar={row['bar']['passes_bar']} "
          f"proj={row['detail']['project_accounting_pooled']} ({time.time()-t0:.0f}s)",
          flush=True)
    row2 = run_cell(sorted(load_panel("forex12", "4h").keys()),
                    "default_deployed_panel12", out_dir)
    po2 = row2["report"]["pooled_oos"]
    print(f"[smt] panel12@4h: trades={po2['trades']} exp={po2['expectancy_net']} "
          f"pf={po2['profit_factor_net']} bar={row2['bar']['passes_bar']} "
          f"proj={row2['detail']['project_accounting_pooled']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
