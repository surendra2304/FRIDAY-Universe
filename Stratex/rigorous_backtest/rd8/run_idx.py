"""Runner for TASK-STR-RD-008 (index strategies, panel idx2).

Mirrors rd3/run_families.py's judgement exactly where the harness
provides it (fold_report / check_bar2 / trade_stats / wf_select_judge /
costs2), with the three pre-declared RD-008 adaptations implemented
locally and ONLY here:

- holdout_idx2: stats2.holdout2 with the 2-symbol gate (>= 2 active
  symbols; subset = {SPX}) — declaration deviation 2;
- SHORT fold profile for 15m (first 10 sessions warm-up era, then 4
  consecutive session blocks S1-S4) — declaration deviation 3;
- session-flat exit rule for the intraday day-trading families —
  declaration deviation 4.

One (config, panel, timeframe) cell = one trial. Rows checkpoint to
<out-dir>/rows/ and are skipped on re-run. Every cell is also re-run at
2x costs; the sensitivity pooled metrics ride on the row (not a trial).

Usage (from the Stratex directory):
  python3 -m rigorous_backtest.rd8.run_idx --out-dir results_rd8
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ..rd.common import atr, dump_json, trades_to_json, wf_select_judge
from ..rd.fastsim import simulate_entries
from ..simulator import Trade, _net_return, trade_metrics
from ..walkforward import trades_in_window
from ..rd2.costs2 import costs_for, describe, double
from ..rd2.families2 import warmup_for
from ..rd2.stats2 import check_bar2, fold_report, holdout2, trade_stats
from .families_idx import build_configs_rd8, session_keys

PANEL = "idx2"
SYMBOLS = ["NDX", "SPX"]
RD2_CACHE = Path("/home/hatch/workspace/str-rd2/cache2")
CACHE15M = Path(os.environ.get("RD8_CACHE15M",
                               "/home/hatch/workspace/rd-008/cache15m"))
SAVE_SCREEN = lambda po: (po.get("expectancy_net") or -9) > -0.005 or \
    (po.get("profit_factor_net") or 0) >= 0.98

PROFILES = {"1d": ("STANDARD", ["W1", "W2", "W3", "W4", "W5"]),
            "1h": ("LATE", ["W2", "W3", "W4", "W5"]),
            "15m": ("SHORT", ["S1", "S2", "S3", "S4"])}


# ---------------------------------------------------------------- data

def load_series(symbol: str, tf: str) -> pd.DataFrame:
    """Load one provenanced series, verifying the CSV's SHA-256 against
    its sidecar manifest (the RD-002 cache contract). Raises on any
    mismatch or absence — never substitutes."""
    cache = CACHE15M if tf == "15m" else RD2_CACHE
    f = cache / f"YH_{symbol}_{tf}.csv"
    meta = json.loads(f.with_suffix(".csv.json").read_text())
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    if digest != meta["csv_sha256"]:
        raise RuntimeError(f"cache integrity failure: {symbol} {tf}")
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    if getattr(df.index, "tz", None) is None:
        df.index = df.index.tz_localize("UTC")
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df


def load_idx2(tf: str) -> dict[str, pd.DataFrame]:
    return {sym: load_series(sym, tf) for sym in SYMBOLS}


def coverage_entry(symbol: str, tf: str, df: pd.DataFrame) -> dict:
    cache = CACHE15M if tf == "15m" else RD2_CACHE
    meta = json.loads((cache / f"YH_{symbol}_{tf}.csv.json").read_text())
    return {"symbol": symbol, "timeframe": tf,
            "source": meta.get("source"),
            "yahoo_symbol": meta.get("yahoo_symbol"),
            "rows": int(len(df)),
            "first_bar_utc": df.index[0].isoformat(),
            "last_bar_utc": df.index[-1].isoformat(),
            "csv_sha256": meta.get("csv_sha256"),
            "manifest_verified_at_load": True,
            "fold_profile": PROFILES[tf][0]}


# ---------------------------------------------------------------- exits

def apply_session_flat(df: pd.DataFrame, trades: list[Trade],
                       costs) -> list[Trade]:
    """Declared session-flat rule: a position still open at the end of
    its entry session closes at that session's final bar close."""
    if not trades:
        return trades
    keys = session_keys(df)
    pos_of = {ts: i for i, ts in enumerate(df.index)}
    last_pos: dict = {}
    for i, d in enumerate(keys):
        last_pos[d] = i
    closes = df["close"].to_numpy(dtype=float)
    out = []
    for t in trades:
        e_pos = pos_of[t.entry_time]
        x_pos = pos_of[t.exit_time]
        if keys[x_pos] <= keys[e_pos]:
            out.append(t)
            continue
        nb = max(last_pos[keys[e_pos]], e_pos)
        exit_price = float(closes[nb])
        out.append(Trade(t.symbol, t.entry_time, df.index[nb], t.side,
                         t.entry_price, exit_price,
                         _net_return(t.side, t.entry_price, exit_price,
                                     costs),
                         "TIME_SESSION"))
    return out


# ---------------------------------------------------------------- folds

def short_blocks(datasets: dict[str, pd.DataFrame]) -> list[tuple]:
    """SHORT profile: first 10 sessions are warm-up era; the remaining
    sessions split into 4 consecutive near-equal blocks."""
    first_bar: dict = {}
    last_bar: dict = {}
    for df in datasets.values():
        keys = session_keys(df)
        for i, d in enumerate(keys):
            if d not in first_bar or df.index[i] < first_bar[d]:
                first_bar[d] = df.index[i]
            if d not in last_bar or df.index[i] > last_bar[d]:
                last_bar[d] = df.index[i]
    dates = sorted(first_bar)
    oos_dates = dates[10:]
    blocks = []
    per = int(np.ceil(len(oos_dates) / 4)) if oos_dates else 0
    for k in range(4):
        chunk = oos_dates[k * per:(k + 1) * per]
        if not chunk:
            continue
        start = first_bar[chunk[0]]
        if k * per + len(chunk) < len(oos_dates):
            end = first_bar[oos_dates[k * per + len(chunk)]]
        else:
            end = last_bar[chunk[-1]] + pd.Timedelta(days=1)
        blocks.append((f"S{k + 1}", start, end))
    return blocks


def _window(trades, start, end):
    return [t for t in trades if start <= t.entry_time < end]


def fold_report_short(trades, blocks, symbols):
    per_fold, pooled = {}, []
    for fid, s, e in blocks:
        ft = _window(trades, s, e)
        per_fold[fid] = {"oos_start": s.isoformat(), "oos_end": e.isoformat(),
                         **trade_metrics(ft)}
        pooled.extend(ft)
    per_symbol = {sym: trade_metrics([t for t in pooled if t.symbol == sym])
                  for sym in symbols}
    return {"per_fold": per_fold, "pooled_oos": trade_metrics(pooled),
            "per_symbol_oos": per_symbol,
            "fold_profile": [b[0] for b in blocks]}


def report_for(trades, tf, datasets, symbols):
    name, ids = PROFILES[tf]
    if tf == "15m":
        return fold_report_short(trades, short_blocks(datasets), symbols), name
    return fold_report(trades, ids, symbols), name


# ---------------------------------------------------------------- holdout

def holdout_idx2(report: dict, symbols: list[str]) -> dict:
    """stats2.holdout2 under the declared 2-symbol adaptation: active
    gate >= 2, breadth >= 0.5, concentration cap 0.8 (small-panel rule),
    untouched subset = {SPX} (pre-declared), >= 30 trades, positive."""
    base = holdout2(report, symbols)
    per = report["per_symbol_oos"]
    active = {s: m for s, m in per.items() if (m.get("trades") or 0) >= 20}
    subset = ["SPX"]
    sub_n = sum(per[s].get("trades") or 0 for s in subset)
    sub_profit = sum((per[s].get("expectancy_net") or 0.0)
                     * (per[s].get("trades") or 0) for s in subset)
    sub_exp = (sub_profit / sub_n) if sub_n else None
    out = dict(base)
    out.update({
        "adaptation": "rd8 declared 2-symbol holdout (declaration deviation 2)",
        "untouched_subset": subset,
        "untouched_trades": sub_n,
        "untouched_expectancy": sub_exp,
        "passes": (len(active) >= 2
                   and (base.get("breadth_positive_share") or 0) >= 0.5
                   and (base.get("max_symbol_profit_share") or 1.0)
                   <= base.get("max_share_cap", 0.8)
                   and sub_n >= 30 and (sub_exp or 0) > 0),
    })
    return out


# ---------------------------------------------------------------- eval

def eval_cell(cfg, tf, datasets, costs_map):
    warmup = warmup_for(tf)
    trades = []
    for sym in sorted(datasets):
        df = datasets[sym]
        entries = cfg["fn"](df, warmup)
        a = atr(df, 14).to_numpy(dtype=float)
        tr = simulate_entries(df, entries, a, cfg["spec"], sym,
                              costs_map[sym])
        if cfg["session_flat"]:
            tr = apply_session_flat(df, tr, costs_map[sym])
        trades.extend(tr)
    trades.sort(key=lambda t: t.entry_time)
    return trades


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--families", default="")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)
    only = {s for s in args.families.split(",") if s}

    datasets_by_tf: dict[str, dict] = {}
    coverage = []

    def get_datasets(tf):
        if tf not in datasets_by_tf:
            datasets_by_tf[tf] = load_idx2(tf)
            for sym, df in datasets_by_tf[tf].items():
                coverage.append(coverage_entry(sym, tf, df))
                print(f"[rd8] data {sym} {tf}: {len(df)} bars "
                      f"{df.index[0]} -> {df.index[-1]}", flush=True)
        return datasets_by_tf[tf]

    fam_cell_trades: dict[tuple, dict[str, list]] = {}
    n = 0
    for cfg in build_configs_rd8():
        if only and cfg["family"] not in only:
            continue
        tf = cfg["tf"]
        key = f"{cfg['family']}__{cfg['variant']}__{PANEL}__{tf}"
        row_path = rows_dir / f"{key}.json"
        if row_path.exists():
            row = json.loads(row_path.read_text())
            if "trades" in row:
                from ..rd.common import trades_from_json
                fam_cell_trades.setdefault(
                    (cfg["family"], tf), {})[cfg["variant"]] = \
                    trades_from_json(row["trades"])
            continue
        datasets = get_datasets(tf)
        symbols = sorted(datasets.keys())
        base_costs = {s: costs_for(PANEL, s) for s in symbols}
        t0 = time.time()
        try:
            trades = eval_cell(cfg, tf, datasets, base_costs)
            status = "EVALUATED" if trades else "NO_TRADES"
            err = None
        except Exception as exc:  # noqa: BLE001 - recorded as verdict
            trades, status = [], "BROKEN"
            err = f"{type(exc).__name__}: {exc}"
        rep, profile_name = report_for(trades, tf, datasets, symbols)
        hold = holdout_idx2(rep, symbols)
        po = rep["pooled_oos"]
        # 2x-cost sensitivity (not a trial)
        dbl = {s: double(c) for s, c in base_costs.items()}
        try:
            trades2x = eval_cell(cfg, tf, datasets, dbl)
            rep2x, _ = report_for(trades2x, tf, datasets, symbols)
            sens = rep2x["pooled_oos"]
        except Exception as exc:  # noqa: BLE001
            sens = {"error": f"{type(exc).__name__}: {exc}"}
        first_fold = rep["fold_profile"][0]
        _os = pd.Timestamp(rep["per_fold"][first_fold]["oos_start"])
        oos_start = _os.tz_localize("UTC") if _os.tzinfo is None \
            else _os.tz_convert("UTC")
        row = {
            "family": cfg["family"], "variant": cfg["variant"],
            "panel": PANEL, "timeframe": tf, "stage": "rd8",
            "status": status, "error": err,
            "spec": cfg["spec"], "session_flat": cfg["session_flat"],
            "costs_rt_bps": {s: describe(PANEL, s)["round_trip_bps"]
                             for s in symbols},
            "symbols": symbols, "report": rep, "holdout": hold,
            "bar": check_bar2(rep, hold),
            "fold_profile_name": profile_name,
            "trade_stats": trade_stats(
                [t for t in trades if t.entry_time >= oos_start]),
            "sensitivity_2x": sens,
            "seconds": round(time.time() - t0, 2),
        }
        if SAVE_SCREEN(po) or row["bar"]["passes_bar"]:
            row["trades"] = trades_to_json(trades)
        dump_json(row_path, row)
        fam_cell_trades.setdefault((cfg["family"], tf), {})[cfg["variant"]] \
            = trades
        n += 1
        print(f"[rd8] {key}: {status} trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
              f"bar={row['bar']['passes_bar']} ({row['seconds']}s)",
              flush=True)

    # wf-select procedures: 1d/1h family groups with >= 2 variants only
    # (declared; 15m excluded — wf_select_judge is W1-W5-bound).
    sel_path = out_dir / "wf_select.json"
    summary = json.loads(sel_path.read_text()) if sel_path.exists() else {}
    n_proc = 0
    for (fam, tf), vt in sorted(fam_cell_trades.items()):
        if tf == "15m" or len(vt) < 2:
            continue
        sel = wf_select_judge(vt)
        summary[f"{fam}__{PANEL}__{tf}"] = {
            "family": fam, "panel": PANEL, "timeframe": tf,
            "variants_tried": len(vt), "wf_selection": sel}
        n_proc += 1
        po = sel["procedure_pooled_oos"]
        print(f"[rd8] WF-SELECT {fam} {tf}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
              flush=True)
    dump_json(sel_path, summary)
    dump_json(out_dir / "coverage_rd8.json", coverage)
    print(f"[rd8] done: {n} new cells, {n_proc} wf-select procedures",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
