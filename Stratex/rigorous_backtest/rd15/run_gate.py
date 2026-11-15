"""Regime-gating evaluation for TASK-STR-RD-015.

Pre-declared in results_rd15/declaration.json (frozen before the first
gated execution). Method: RESIMULATION with RD-002's own machinery —
entries are regenerated from the RD-002 config objects, a gate drops
candidate entries BEFORE simulation (so a stood-down entry frees its
position slot, exactly as a live stand-down would), and trades are
simulated by rd.fastsim.simulate_entries under the entrant's declared
exit spec and the RD-002 crypto cost model. Metrics come from
rd2.stats2.fold_report / simulator.trade_metrics, folds W1..W5, trades
attributed by entry time — the identical chain that produced the
RD-002 rows. Each ungated run must reproduce the RD-002 published
pooled OOS trades / expectancy / PF within 1e-9 (the anchor) before
any gated number for that entrant is trusted.

Run (from the Stratex directory):
  python3 -m rigorous_backtest.rd15.run_gate \
      --declaration results_rd15/declaration.json \
      --out-dir results_rd15
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from rigorous_backtest.rd.common import adx, atr, ema
from rigorous_backtest.rd.fastsim import simulate_entries
from rigorous_backtest.rd2.costs2 import costs_for, double as costs_double
from rigorous_backtest.rd2.families2 import build_configs, warmup_for
from rigorous_backtest.rd2.families3 import build_configs3
from rigorous_backtest.rd2.panels import fold_profile, load_panel
from rigorous_backtest.rd2.stats2 import fold_report

GATES = ("gate_range", "gate_vol", "gate_both", "gate_counter")
ENTRANTS = (("ichimoku_trend", "tk_cloud", "crypto30", "4h"),
            ("dow_effect", "reversal", "crypto30", "1d"))
VOL_WINDOW = 252
VOL_HIGH_Q = 2.0 / 3.0
ADX_RANGE_MAX = 20.0


def regime_frame(df) -> dict:
    """Causal regime components for one series (bar i uses bars <= i)."""
    close = df["close"]
    atr_pct = (atr(df, 14) / close).to_numpy(dtype=float)
    n = len(df)
    vol_pct = np.full(n, np.nan)
    for i in range(VOL_WINDOW - 1, n):
        w = atr_pct[i - VOL_WINDOW + 1: i + 1]
        if not np.isnan(w).any():
            vol_pct[i] = float((w < atr_pct[i]).mean())
    return {
        "adx": adx(df, 14).to_numpy(dtype=float),
        "e50": ema(close, 50).to_numpy(dtype=float),
        "e200": ema(close, 200).to_numpy(dtype=float),
        "vol_pct": vol_pct,
    }


def is_hostile(gate: str, side: str, R: dict, i: int) -> tuple[bool, bool]:
    """(hostile, unknown) for one candidate entry at signal bar i."""
    if gate == "gate_counter":
        e50, e200 = R["e50"][i], R["e200"][i]
        if np.isnan(e50) or np.isnan(e200):
            return False, True
        hostile = (side == "LONG" and e50 < e200) or \
                  (side == "SHORT" and e50 > e200)
        return hostile, False
    ranging = vol_high = False
    unknown = False
    if gate in ("gate_range", "gate_both"):
        a = R["adx"][i]
        if np.isnan(a):
            unknown = True
        else:
            ranging = a < ADX_RANGE_MAX
    if gate in ("gate_vol", "gate_both"):
        v = R["vol_pct"][i]
        if np.isnan(v):
            unknown = True
        else:
            vol_high = v >= VOL_HIGH_Q
    if unknown:
        return False, True
    return (ranging or vol_high), False


def compact(rep: dict) -> dict:
    """Report shape stored on rows (pooled + per-fold; the per-symbol
    breakdown is reproducible from the row's configuration and is
    omitted to keep rows review-sized)."""
    return {"per_fold": rep["per_fold"], "pooled_oos": rep["pooled_oos"],
            "fold_profile": rep["fold_profile"]}


def find_config(family: str, variant: str) -> dict:
    for cfg in build_configs() + build_configs3():
        if cfg["family"] == family and cfg["variant"] == variant:
            return cfg
    raise KeyError(f"config not found: {family}/{variant}")


def run_cell(cfg, panel_name, tf, datasets, gate=None, double_costs=False):
    """Mirror of rd2.grid.eval_single with an optional pre-sim gate."""
    warmup = warmup_for(tf)
    all_trades = []
    n_signals = n_dropped = n_unknown = 0
    for sym, ds in datasets.items():
        entries = cfg["fn"](ds.df, None, None, warmup)
        if cfg.get("atr_fn"):
            a = cfg["atr_fn"](ds.df)
        else:
            a = atr(ds.df, 14).to_numpy(dtype=float)
        if gate is not None:
            R = regime_frame(ds.df)
            kept = []
            for (i, side) in entries:
                n_signals += 1
                hostile, unknown = is_hostile(gate, side, R, i)
                if unknown:
                    n_unknown += 1
                if hostile:
                    n_dropped += 1
                else:
                    kept.append((i, side))
            entries = kept
        else:
            n_signals += len(entries)
        costs = costs_for(panel_name, sym)
        if double_costs:
            costs = costs_double(costs)
        all_trades.extend(simulate_entries(ds.df, entries, a, cfg["spec"],
                                           sym, costs))
    symbols = sorted(datasets.keys())
    rep = fold_report(all_trades, fold_profile(panel_name, tf), symbols)
    return rep, {"signals_total": n_signals, "signals_dropped": n_dropped,
                 "signals_unknown_state": n_unknown}


def improvement(base: dict, gated: dict) -> dict:
    b, g = base["pooled_oos"], gated["pooled_oos"]
    checks = {
        "expectancy_up": (g["expectancy_net"] or -9) > (b["expectancy_net"] or -9),
        "pf_not_down": (g["profit_factor_net"] or 0) >= (b["profit_factor_net"] or 0),
        "dd_not_deeper": (g["max_drawdown_net"] or -9) >= (b["max_drawdown_net"] or -9),
        "retains_half_trades": (g["trades"] or 0) >= 0.5 * (b["trades"] or 0),
    }
    return {"checks": checks, "improves": all(checks.values())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--declaration", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    decl = json.loads(Path(args.declaration).read_text())
    published = {(e["family"], e["variant"]): e["rd002_published_oos"]
                 for e in decl["entrants"]}
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "rows"
    rows_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    anchors = {}
    for family, variant, panel, tf in ENTRANTS:
        cfg = find_config(family, variant)
        datasets = load_panel(panel, tf)
        pub = published[(family, variant)]
        t0 = time.time()
        rep, sig = run_cell(cfg, panel, tf, datasets, gate=None)
        po = rep["pooled_oos"]
        anchor = {
            "trades_match": po["trades"] == pub["trades"],
            "expectancy_abs_err": abs((po["expectancy_net"] or 0) - pub["expectancy_net"]),
            "pf_abs_err": abs((po["profit_factor_net"] or 0) - pub["profit_factor_net"]),
        }
        anchor["pass"] = anchor["trades_match"] and \
            anchor["expectancy_abs_err"] <= 1e-9 and anchor["pf_abs_err"] <= 1e-9
        anchors[f"{family}__{variant}"] = anchor
        row = {"family": family, "variant": variant, "panel": panel,
               "timeframe": tf, "gate": "none_anchor", "status": "EVALUATED",
               "spec": cfg["spec"], "signals": sig, "report": compact(rep),
               "anchor_vs_rd002": anchor, "seconds": round(time.time() - t0, 2)}
        rows.append(row)
        (rows_dir / f"{family}__{variant}__{panel}__{tf}__none.json").write_text(
            json.dumps(row, indent=2, default=str))
        print(f"[anchor] {family}/{variant} {tf}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']} "
              f"anchor_pass={anchor['pass']}", flush=True)
        if not anchor["pass"]:
            print(f"[anchor] FAILED for {family}/{variant} — gated cells "
                  f"for this entrant are VOID", flush=True)
            continue
        base_rep = rep
        for gate in GATES:
            t0 = time.time()
            grep_, gsig = run_cell(cfg, panel, tf, datasets, gate=gate)
            imp = improvement(base_rep, grep_)
            grow = {"family": family, "variant": variant, "panel": panel,
                    "timeframe": tf, "gate": gate, "status": "EVALUATED",
                    "spec": cfg["spec"], "signals": gsig, "report": compact(grep_),
                    "improvement": imp,
                    "seconds": round(time.time() - t0, 2)}
            if imp["improves"]:
                srep, _ = run_cell(cfg, panel, tf, datasets, gate=gate,
                                   double_costs=True)
                grow["sensitivity_2x_costs_pooled_oos"] = srep["pooled_oos"]
            rows.append(grow)
            (rows_dir / f"{family}__{variant}__{panel}__{tf}__{gate}.json"
             ).write_text(json.dumps(grow, indent=2, default=str))
            g = grep_["pooled_oos"]
            print(f"[gate] {family}/{variant} {tf} {gate}: trades={g['trades']} "
                  f"exp={g['expectancy_net']} pf={g['profit_factor_net']} "
                  f"dd={g['max_drawdown_net']} improves={imp['improves']} "
                  f"(dropped {gsig['signals_dropped']}/{gsig['signals_total']})",
                  flush=True)

    synthesis = {
        "task": decl["task"],
        "declaration": "results_rd15/declaration.json",
        "trials": decl["trials"],
        "anchors": anchors,
        "rows": [{k: r[k] for k in ("family", "variant", "panel", "timeframe",
                                    "gate", "status", "signals")}
                 | {"pooled_oos": r["report"]["pooled_oos"],
                    "per_fold_expectancy": {
                        f: r["report"]["per_fold"][f]["expectancy_net"]
                        for f in r["report"]["per_fold"]},
                    "improvement": r.get("improvement"),
                    "sensitivity_2x_costs_pooled_oos":
                        r.get("sensitivity_2x_costs_pooled_oos")}
                 for r in rows],
        "full_rows_dir": "results_rd15/rows/",
    }
    (out_dir / "synthesis.json").write_text(
        json.dumps(synthesis, indent=2, default=str))
    print(f"[done] {len(rows)} rows -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
