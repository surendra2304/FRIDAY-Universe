"""Stage C — combinations (TASK-STR-RD-002).

Two mechanisms, both judged on COMPOUNDED EQUITY + max drawdown +
breadth (never per-trade averages alone — RD-001 E4):

(i) Portfolio combinations of the best Stage B trade streams: each
    stream's trades compound within the stream; streams are combined
    on a daily grid, equal-weight (daily-rebalanced mean of stream
    equities) and inverse-volatility (weights from EXPANDING trailing
    daily-return vol, 60-observation minimum, refreshed monthly — no
    look-ahead). Component daily-return correlations are reported so
    the diversification mechanism is visible either way.

(ii) Signal-level ensembles: on two panels, entries where >= 2 of 3
    declared base signals agree on bar+side, simulated with the
    harness MODULE/fastsim conventions and class costs.

Every (set x weighting) and every ensemble = one trial.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..rd.common import atr, dump_json, trades_from_json, trades_to_json
from ..rd.fastsim import simulate_entries
from .costs2 import costs_for
from .families2 import sig_donchian, sig_ts_momentum, sig_vol_trend
from .panels import load_panel
from .stats2 import fold_report, holdout2, check_bar2, trade_stats

ERA_START = pd.Timestamp("2024-07-01", tz="UTC")
ERA_END = pd.Timestamp("2026-11-01", tz="UTC")


def stream_daily_equity(trades) -> pd.Series:
    """Daily equity (start 1.0) compounding the stream's trades at exit."""
    if not trades:
        return pd.Series(dtype=float)
    # compound sequentially per exit day
    eq = {}
    cur = 1.0
    for t in sorted(trades, key=lambda x: x.exit_time):
        d = t.exit_time.normalize()
        cur *= (1.0 + t.net_return)
        eq[d] = cur
    days = pd.date_range(ERA_START, ERA_END, freq="D")
    s = pd.Series(eq).reindex(days).ffill().fillna(1.0)
    return s


def combine(streams: dict[str, list], weighting: str) -> dict:
    eqs = {k: stream_daily_equity(v) for k, v in streams.items()
           if len(v) > 0}
    if len(eqs) < 2:
        return {"status": "INSUFFICIENT_STREAMS", "n_streams": len(eqs)}
    E = pd.DataFrame(eqs)
    R = E.pct_change().fillna(0.0)
    if weighting == "equal":
        port_eq = E.mean(axis=1)
        port_eq = port_eq / port_eq.iloc[0]
    else:  # inverse-vol, expanding, monthly refresh
        weights = pd.DataFrame(0.0, index=E.index, columns=E.columns)
        cur_w = {c: 1.0 / len(E.columns) for c in E.columns}
        last_refresh = None
        for d in E.index:
            if last_refresh is None or (d - last_refresh).days >= 30:
                hist = R.loc[:d].iloc[:-1]  # strictly past returns
                if len(hist) >= 60:
                    vol = hist.std()
                    inv = {c: (1.0 / vol[c] if vol[c] > 1e-9 else 0.0)
                           for c in E.columns}
                    tot = sum(inv.values())
                    if tot > 0:
                        cur_w = {c: inv[c] / tot for c in E.columns}
                last_refresh = d
            for c in E.columns:
                weights.loc[d, c] = cur_w[c]
        port_ret = (weights.shift(1).fillna(
            {c: 1.0 / len(E.columns) for c in E.columns}) * R).sum(axis=1)
        port_eq = (1.0 + port_ret).cumprod()
    total = float(port_eq.iloc[-1] - 1.0)
    dd = float((port_eq / port_eq.cummax() - 1.0).min())
    daily = port_eq.pct_change().dropna()
    sharpe_d = float(daily.mean() / daily.std() * np.sqrt(252)) \
        if daily.std() > 0 else 0.0
    corr = R.corr()
    iu = np.triu_indices(len(corr), k=1)
    mean_corr = float(corr.values[iu].mean()) if len(corr) > 1 else None
    pos_streams = sum(1 for v in streams.values()
                      if v and np.prod([1 + t.net_return for t in v]) > 1.0)
    return {"status": "EVALUATED", "weighting": weighting,
            "n_streams": len(eqs), "total_return_compounded": total,
            "max_drawdown": dd, "sharpe_daily_ann": sharpe_d,
            "mean_pairwise_corr": mean_corr,
            "correlation_matrix": {a: {b: (None if pd.isna(corr.loc[a, b])
                                            else float(corr.loc[a, b]))
                                        for b in corr.columns}
                                   for a in corr.index},
            "streams_positive_share": pos_streams / max(1, len(eqs)),
            "streams": sorted(eqs.keys())}


def load_streams(out_dir: Path) -> list[dict]:
    rows = []
    for sub in ("grid_rows", "gov_rows", "disc_rows"):
        d = out_dir / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            r = json.loads(p.read_text())
            if "trades" not in r:
                continue
            trades = trades_from_json(r["trades"])
            start = pd.Timestamp(
                r["report"]["per_fold"][r["report"]["fold_profile"][0]]
                ["oos_start"], tz="UTC")
            oos = [t for t in trades if start <= t.entry_time < ERA_END]
            if not oos:
                continue
            po = r["report"]["pooled_oos"]
            rows.append({
                "id": f"{r['family']}/{r['variant']}@{r['panel']}/{r['timeframe']}",
                "family": r["family"], "variant": r["variant"],
                "panel": r["panel"], "timeframe": r["timeframe"],
                "asset_class": r.get("asset_class") or
                    ("crypto" if r["panel"].startswith("crypto") else
                     "forex" if r["panel"].startswith("forex") else
                     "comm" if r["panel"].startswith("comm") else "idx"),
                "expectancy": po.get("expectancy_net"),
                "pf": po.get("profit_factor_net"),
                "n_trades": len(oos), "trades": oos})
    return rows


ENSEMBLE_BASES = [
    ("ts_momentum/roc42", lambda df, w: sig_ts_momentum(df, 42, w)),
    ("donchian/n20", lambda df, w: sig_donchian(df, 20, w)),
    ("vol_trend/ema20_50", lambda df, w: sig_vol_trend(df, 20, 50, False, w)),
]
ENSEMBLE_SPEC = {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}


def eval_ensemble(panel: str, tf: str, vote: int = 2) -> dict:
    datasets = load_panel(panel, tf)
    from .families2 import warmup_for
    w = warmup_for(tf)
    all_trades = []
    for sym, ds in datasets.items():
        votes: dict[tuple[int, str], int] = {}
        for _name, fn in ENSEMBLE_BASES:
            for (i, side) in fn(ds.df, w):
                votes[(i, side)] = votes.get((i, side), 0) + 1
        entries = [(i, s) for (i, s), v in votes.items() if v >= vote]
        a = atr(ds.df, 14).to_numpy(dtype=float)
        all_trades.extend(simulate_entries(ds.df, entries, a, ENSEMBLE_SPEC,
                                           sym, costs_for(panel, sym)))
    symbols = sorted(datasets.keys())
    from .panels import fold_profile
    rep = fold_report(all_trades, fold_profile(panel, tf), symbols)
    hold = holdout2(rep, symbols)
    return {"family": "ensemble", "variant": f"vote{vote}_of3",
            "panel": panel, "timeframe": tf, "status": "EVALUATED",
            "report": rep, "holdout": hold,
            "bar": check_bar2(rep, hold),
            "trade_stats": trade_stats(all_trades),
            "trades": trades_to_json(all_trades)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    streams = load_streams(out_dir)
    elig = [s for s in streams if s["n_trades"] >= 100
            and (s["expectancy"] or -9) > -0.002]
    elig.sort(key=lambda s: s["expectancy"] or -9, reverse=True)
    print(f"[combo] {len(streams)} streams with trades, {len(elig)} eligible",
          flush=True)
    results = {"streams_available": len(streams), "eligible": len(elig),
               "combinations": [], "ensembles": []}
    sets: dict[str, dict[str, list]] = {}
    if len(elig) >= 2:
        sets["top5_overall"] = {s["id"]: s["trades"] for s in elig[:5]}
    for cls in ("crypto", "forex", "comm", "idx"):
        sub = [s for s in elig if s["asset_class"] == cls][:3]
        if len(sub) >= 2:
            sets[f"top3_{cls}"] = {s["id"]: s["trades"] for s in sub}
    best_per_class = {}
    for cls in ("crypto", "forex", "comm", "idx"):
        sub = [s for s in elig if s["asset_class"] == cls]
        if sub:
            best_per_class[sub[0]["id"]] = sub[0]["trades"]
    if len(best_per_class) >= 3:
        sets["best_per_class"] = best_per_class
    pos = [s for s in elig if (s["expectancy"] or -9) > 0][:15]
    if len(pos) >= 3:
        sets["all_positive_top15"] = {s["id"]: s["trades"] for s in pos}
    for name, members in sets.items():
        for weighting in ("equal", "invvol"):
            res = combine(members, weighting)
            res["set"] = name
            results["combinations"].append(res)
            print(f"[combo] {name}/{weighting}: total="
                  f"{res.get('total_return_compounded')} dd="
                  f"{res.get('max_drawdown')} corr="
                  f"{res.get('mean_pairwise_corr')}", flush=True)
    for panel, tf in (("crypto30", "4h"), ("forex12", "4h")):
        row = eval_ensemble(panel, tf)
        dump_json(out_dir / "combo_rows" /
                  f"ensemble__vote2__{panel}__{tf}.json", row)
        results["ensembles"].append(
            {k: row[k] for k in ("variant", "panel", "timeframe")})
        po = row["report"]["pooled_oos"]
        print(f"[combo] ensemble {panel} {tf}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
              flush=True)
    dump_json(out_dir / "stageC_combinations.json", results)
    print("[combo] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
