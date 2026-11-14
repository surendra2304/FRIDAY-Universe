"""STAGE 4 — "everything else" experiments (TASK-STR-RD-001).

One variable at a time against a named baseline; OOS judged; harness
folds/costs unless the experiment IS the cost model.

Subjects (selection rule declared before Stage 3 results were read):
the top-2 Stage-3 variants by pooled OOS expectancy among variants with
>= 100 OOS trades ("best signals"), plus adx_ema production (Stage 2),
plus the BT-001 near-breakeven modules atr_breakout / adx_trend for the
cost experiment (the only governed-adjacent signals whose gross edge is
close enough to costs for execution quality to matter).

Experiments:
  E1 cost sensitivity — round-trip cost scenarios (fee, slip) per side:
     (5,3)=16bps [baseline taker], (3,2)=10, (2,1)=6, (1,0.5)=3,
     (0.5,0.25)=1.5 [maker-optimistic]. Fastsim subjects re-simulated;
     module subjects re-evaluated via evaluate_module at each cost.
  E2 instrument selection — per-symbol and pair subsets from the stored
     pooled trade lists (positions are per-symbol independent in this
     harness, so subset metrics are exact, not approximations).
  E3 regime gating — BTC same-timeframe close>EMA(200) gate applied to
     the best trend-family variant's entries: production-style (blocks
     longs only) and aligned (also blocks shorts above the line).
  E4 sizing / compounding — notional-weight compounding w in
     {0.25, 0.5, 1.0, 2.0} over the time-ordered pooled trade list:
     total return, max drawdown, Calmar. Sizing shapes the ride; it does
     not create edge — reported as such. (Risk-based sizing needs stop
     distances per trade and is left to the forward protocol.)
  E5 timeframe selection — the best trend family's winning variant spec
     re-run at 15m and 4h (baseline 1h).
  E6 exit engineering — the best signal's entries under an exit-spec
     grid (brackets, trails, time exits).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..module_eval import evaluate_module
from ..simulator import Costs, trade_metrics
from ..walkforward import oos_report
from .common import (COSTS, SYMBOLS, atr, dump_json, ema, full_report,
                     load_timeframe, trades_from_json, trades_to_json)
from .fastsim import simulate_entries
from . import stage3 as s3

COST_SCENARIOS = [
    ("taker_16bps", Costs(5.0, 3.0)),
    ("10bps", Costs(3.0, 2.0)),
    ("6bps", Costs(2.0, 1.0)),
    ("3bps", Costs(1.0, 0.5)),
    ("maker_1.5bps", Costs(0.5, 0.25)),
]
TREND_FAMILIES = {"donchian_turtle", "vol_adaptive_trend", "mtf_confluence",
                  "volume_breakout", "ts_momentum"}


def pick_subjects(out_dir: Path):
    rows = []
    for p in sorted((out_dir / "stage3_rows").glob("*.json")):
        r = json.loads(p.read_text())
        po = r["report"]["pooled_oos"]
        rows.append({"key": f"{r['family']}__{r['variant']}", "family": r["family"],
                     "variant": r["variant"], "timeframe": r["timeframe"],
                     "spec": r["spec"], "pooled": po, "row": r})
    eligible = [r for r in rows if (r["pooled"].get("trades") or 0) >= 100]
    eligible.sort(key=lambda r: r["pooled"].get("expectancy_net") or -9,
                  reverse=True)
    best = eligible[:2]
    trend = [r for r in eligible if r["family"] in TREND_FAMILIES]
    best_trend = trend[0] if trend else (best[0] if best else None)
    return rows, best, best_trend


def entries_for_variant(row, datasets_by_tf, aux4h):
    fam, vname = row["family"], row["variant"]
    for (f2, v2, tf, fn, spec) in s3.build_variants():
        if f2 == fam and v2 == vname:
            tf_use = row["timeframe"]
            out = {}
            for sym in SYMBOLS:
                ds = datasets_by_tf[tf_use][sym]
                out[sym] = fn(ds.df, aux4h.get(sym) if tf_use == "1h" else None)
            return out, spec
    raise KeyError(f"variant not found: {fam}/{vname}")


def compounding_stats(trades, w: float) -> dict:
    ordered = sorted(trades, key=lambda t: t.entry_time)
    if not ordered:
        return {"trades": 0}
    eq = np.cumprod([1.0 + w * t.net_return for t in ordered])
    curve = np.concatenate([[1.0], eq])
    rm = np.maximum.accumulate(curve)
    dd = float((curve / rm - 1.0).min())
    total = float(curve[-1] - 1.0)
    return {"trades": len(ordered), "total_return": total,
            "max_drawdown": dd,
            "calmar": (total / abs(dd)) if dd < 0 else None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stratex-root", default=".")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    stratex_root = Path(args.stratex_root).resolve()
    out_dir = Path(args.out_dir)
    cache = Path(args.cache_dir)
    results: dict = {"stage": 4}

    all_rows, best, best_trend = pick_subjects(out_dir)
    results["subjects"] = {"best_signals": [b["key"] for b in best],
                           "best_trend": best_trend["key"] if best_trend else None}
    print(f"[stage4] subjects: {[b['key'] for b in best]} trend={results['subjects']['best_trend']}",
          flush=True)

    ds1h = load_timeframe("1h", cache)
    ds4h = load_timeframe("4h", cache)
    datasets_by_tf = {"1h": ds1h, "4h": ds4h}
    aux4h = {sym: ds.df for sym, ds in ds4h.items()}

    # adx_ema production trades (stage 2 part A)
    partA = json.loads((out_dir / "stage2_partA.json").read_text())
    adx_prod = next(c for c in partA["configs"] if c["config"] == "production")
    adx_trades = trades_from_json(adx_prod["trades"])

    subjects_trades: dict[str, list] = {"adx_ema_production": adx_trades}
    subjects_entries: dict[str, tuple[dict, dict, str]] = {}
    for b in best:
        entries, spec = entries_for_variant(b, datasets_by_tf, aux4h)
        subjects_entries[b["key"]] = (entries, spec, b["timeframe"])
        subjects_trades[b["key"]] = trades_from_json(b["row"]["trades"])

    # ---------------- E1: cost sensitivity ----------------
    e1: dict[str, dict] = {}
    for key, (entries, spec, tf) in subjects_entries.items():
        per = {}
        for cname, costs in COST_SCENARIOS:
            tr = []
            for sym in SYMBOLS:
                ds = datasets_by_tf[tf][sym]
                a = atr(ds.df, 14).to_numpy(dtype=float)
                tr.extend(simulate_entries(ds.df, entries[sym], a, spec, sym, costs))
            per[cname] = oos_report(tr)["pooled_oos"]
        e1[key] = per
        print(f"[stage4-E1] {key}: " + " | ".join(
            f"{c}:{per[c]['expectancy_net']:.4%}" for c, _ in COST_SCENARIOS), flush=True)
    # adx_ema: re-derive entries from its stored trades is not possible
    # (brackets are module-anchored); approximate cost sensitivity by
    # re-running stage-2 extraction at each cost via simulate_module on the
    # production-filtered signals.
    from .stage2 import extract_signals, apply_filters, btc_gate_series
    from ..module_eval import _load_module
    from ..simulator import simulate_module
    mod = _load_module("strategy_adx_ema", stratex_root / "strategy_adx_ema.py",
                       [str(stratex_root), str(stratex_root / "strategies")])
    gate_ok = btc_gate_series(ds4h["BTCUSDT"].df)
    kept_by_sym = {}
    for sym in SYMBOLS:
        sigs, _a, _w = extract_signals(mod, ds4h[sym].df)
        kept_by_sym[sym] = apply_filters(sigs, sym, gate_ok, ds4h[sym].df.index, True, True)
    per = {}
    for cname, costs in COST_SCENARIOS:
        tr = []
        for sym in SYMBOLS:
            tr.extend(simulate_module(ds4h[sym].df, kept_by_sym[sym], sym, costs))
        per[cname] = oos_report(tr)["pooled_oos"]
    e1["adx_ema_production"] = per
    print(f"[stage4-E1] adx_ema_production: " + " | ".join(
        f"{c}:{per[c]['expectancy_net']:.4%}" for c, _ in COST_SCENARIOS), flush=True)
    # Module subjects: extract signals ONCE (replica of evaluate_module's
    # pipeline choice + extraction loop), validate the replica against
    # BT-001's discovery row at baseline costs, then sweep costs by
    # re-simulation only. (Re-running evaluate_module per cost level
    # re-extracts per bar — measured at ~1 CPU-hour per module here.)
    from ..module_eval import (_extract, _features_causal, _load_module,
                               WARMUP_BARS, WINDOW)
    from ..simulator import simulate_module as _sim_mod
    import importlib as _il
    bt_disc = json.loads((stratex_root / "rigorous_backtest" / "results" /
                          "phase_discovery.json").read_text())
    for mod_name in ("strategy_atr_breakout", "strategy_adx_trend"):
        sp = [str(stratex_root), str(stratex_root / "strategies")]
        mod = _load_module(mod_name, stratex_root / f"{mod_name}.py", sp)
        pipelines = []
        if callable(getattr(mod, "add_features", None)):
            pipelines.append(("module.add_features", mod.add_features))
        try:
            shared = _il.import_module("features")
            if callable(getattr(shared, "add_features", None)):
                pipelines.append(("features.add_features (shared)", shared.add_features))
        except Exception:
            pass
        pipelines.append(("identity (raw OHLCV)", None))
        first_df = ds1h["BTCUSDT"].df
        chosen_fn = "unset"
        for pname, fn in pipelines:
            if fn is not None and not _features_causal(fn, first_df):
                continue
            chosen_fn = fn
            break
        if chosen_fn == "unset":
            e1[mod_name] = {"error": "no causal feature pipeline"}
            continue
        sig_by_sym = {}
        for sym in SYMBOLS:
            ds = ds1h[sym]
            work = chosen_fn(ds.df.copy()) if chosen_fn is not None else ds.df
            sigs = []
            for i in range(WARMUP_BARS, len(work) - 1):
                res = mod.get_signal(work.iloc[max(0, i - WINDOW + 1): i + 1].copy())
                ex = _extract(res)
                if ex is not None:
                    sigs.append((i, ex[0], ex[1], ex[2]))
            sig_by_sym[sym] = sigs
        base_tr = []
        for sym in SYMBOLS:
            base_tr.extend(_sim_mod(ds1h[sym].df, sig_by_sym[sym], sym, COSTS))
        base_po = oos_report(base_tr)["pooled_oos"]
        ref_row = next(r for r in bt_disc["rows"] if r["strategy"] == mod_name)
        ref_po = ref_row["pooled_oos"]
        match = (base_po["trades"] == ref_po["trades"] and
                 abs(base_po["expectancy_net"] - ref_po["expectancy_net"]) < 1e-9)
        per = {"replica_matches_bt001": match,
               "replica_baseline": base_po, "bt001_baseline": ref_po}
        if match:
            for cname, costs in COST_SCENARIOS:
                tr = []
                for sym in SYMBOLS:
                    tr.extend(_sim_mod(ds1h[sym].df, sig_by_sym[sym], sym, costs))
                per[cname] = oos_report(tr)["pooled_oos"]
        e1[mod_name] = per
        print(f"[stage4-E1] {mod_name}: replica_match={match} " + " | ".join(
            f"{c}:{(per.get(c) or {}).get('expectancy_net', float('nan')):.4%}"
            for c, _ in COST_SCENARIOS), flush=True)
    results["E1_cost_sensitivity"] = e1
    dump_json(out_dir / "stage4_experiments.json", results)

    # ---------------- E2: instrument selection ----------------
    e2 = {}
    for key, trades in subjects_trades.items():
        subsets = {}
        combos = [("BTCUSDT",), ("ETHUSDT",), ("SOLUSDT",),
                  ("BTCUSDT", "ETHUSDT"), ("BTCUSDT", "SOLUSDT"),
                  ("ETHUSDT", "SOLUSDT"), tuple(SYMBOLS)]
        for combo in combos:
            sub = [t for t in trades if t.symbol in combo]
            subsets["+".join(s.replace("USDT", "") for s in combo)] = \
                oos_report(sub)["pooled_oos"]
        e2[key] = subsets
        print(f"[stage4-E2] {key}: " + " | ".join(
            f"{k}:{v['expectancy_net']:.4%}({v['trades']})" for k, v in subsets.items()),
            flush=True)
    results["E2_instrument_selection"] = e2
    dump_json(out_dir / "stage4_experiments.json", results)

    # ---------------- E3: regime gating on best trend variant ----------------
    if best_trend is not None:
        entries, spec, tf = subjects_entries[best_trend["key"]]
        btc = datasets_by_tf[tf]["BTCUSDT"].df
        btc_ema = ema(btc["close"], 200)
        gate_ok_bars = (btc["close"] > btc_ema).to_numpy()
        variants = {}
        for gname, mode in (("nogate", None), ("production_style", "longs"),
                            ("aligned", "both")):
            tr = []
            for sym in SYMBOLS:
                ds = datasets_by_tf[tf][sym]
                ent = entries[sym]
                if mode is not None:
                    filtered = []
                    for (i, side) in ent:
                        bull = bool(gate_ok_bars[i]) if i < len(gate_ok_bars) else False
                        if mode == "longs" and side == "LONG" and not bull:
                            continue
                        if mode == "both" and ((side == "LONG" and not bull) or
                                               (side == "SHORT" and bull)):
                            continue
                        filtered.append((i, side))
                    ent = filtered
                a = atr(ds.df, 14).to_numpy(dtype=float)
                tr.extend(simulate_entries(ds.df, ent, a, spec, sym, COSTS))
            variants[gname] = full_report(tr)
            po = variants[gname]["pooled_oos"]
            print(f"[stage4-E3] {gname}: trades={po['trades']} exp={po['expectancy_net']} pf={po['profit_factor_net']}", flush=True)
        results["E3_regime_gating"] = {"subject": best_trend["key"],
                                       "variants": variants}
        dump_json(out_dir / "stage4_experiments.json", results)

    # ---------------- E4: sizing / compounding ----------------
    e4 = {}
    for key, trades in subjects_trades.items():
        e4[key] = {f"w={w}": compounding_stats(trades, w)
                   for w in (0.25, 0.5, 1.0, 2.0)}
        print(f"[stage4-E4] {key}: " + " | ".join(
            f"w{w}: tot={e4[key][f'w={w}']['total_return']:.2%} dd={e4[key][f'w={w}']['max_drawdown']:.2%}"
            for w in (0.25, 0.5, 1.0, 2.0)), flush=True)
    results["E4_sizing"] = e4
    dump_json(out_dir / "stage4_experiments.json", results)

    # ---------------- E5: timeframe for best trend family ----------------
    if best_trend is not None:
        fam = best_trend["family"]
        fam_variants = [v for v in s3.build_variants() if v[0] == fam]
        # the family's 1h variants re-run at 15m and 4h under their own specs
        e5 = {}
        for tf2 in ("15m", "4h"):
            dstf = load_timeframe(tf2, cache)
            fam_trades = {}
            for (f2, v2, tf0, fn, spec) in fam_variants:
                if tf0 != "1h":
                    continue
                tr = []
                for sym in SYMBOLS:
                    ds = dstf[sym]
                    ent = fn(ds.df, aux4h[sym] if fam == "mtf_confluence" else None)
                    a = atr(ds.df, 14).to_numpy(dtype=float)
                    tr.extend(simulate_entries(ds.df, ent, a, spec, sym, COSTS))
                fam_trades[v2] = tr
            from .common import wf_select_judge
            sel = wf_select_judge(fam_trades)
            e5[tf2] = sel
            po = sel["procedure_pooled_oos"]
            print(f"[stage4-E5] {fam}@{tf2}: wf-select trades={po['trades']} exp={po['expectancy_net']} pf={po['profit_factor_net']}", flush=True)
        results["E5_timeframe"] = {"family": fam, "by_timeframe": e5}
        dump_json(out_dir / "stage4_experiments.json", results)

    # ---------------- E6: exit engineering on best signal ----------------
    if best:
        top = best[0]
        entries, _spec, tf = subjects_entries[top["key"]]
        specs = [
            ("bracket_2_2", {"type": "bracket", "sl_atr": 2.0, "tp_atr": 2.0}),
            ("bracket_2_4", {"type": "bracket", "sl_atr": 2.0, "tp_atr": 4.0}),
            ("bracket_3_6", {"type": "bracket", "sl_atr": 3.0, "tp_atr": 6.0}),
            ("trail_2_2.5", {"type": "trail", "sl_atr": 2.0, "trail_atr": 2.5}),
            ("trail_3_3", {"type": "trail", "sl_atr": 3.0, "trail_atr": 3.0}),
            ("bracket_time_24", {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0, "max_bars": 24}),
            ("bracket_time_72", {"type": "bracket_time", "sl_atr": 2.0, "tp_atr": 4.0, "max_bars": 72}),
        ]
        e6 = {}
        for label, spec in specs:
            tr = []
            for sym in SYMBOLS:
                ds = datasets_by_tf[tf][sym]
                a = atr(ds.df, 14).to_numpy(dtype=float)
                tr.extend(simulate_entries(ds.df, entries[sym], a, spec, sym, COSTS))
            rep = full_report(tr)
            e6[label] = {"spec": spec, "report": rep}
            po = rep["pooled_oos"]
            print(f"[stage4-E6] {label}: trades={po['trades']} exp={po['expectancy_net']} pf={po['profit_factor_net']}", flush=True)
        results["E6_exit_engineering"] = {"subject": top["key"], "variants": e6}

    dump_json(out_dir / "stage4_experiments.json", results)
    print("[stage4] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
