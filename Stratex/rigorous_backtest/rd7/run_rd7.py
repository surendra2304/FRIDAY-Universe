"""Runner for TASK-STR-RD-007 (gold & commodities intraday).

Executes EXACTLY the cells pre-declared in results_rd7/declaration.json:
5 families x 2 variants x 3 instruments (GOLD, SILVER, WTI) at 1h, plus
15 walk-forward-select procedures. Judgement is LATE-profile (W2-W5)
walk-forward OOS only, under the programme's standing bar.

Data: RD-002 Stage-A provenanced Yahoo series in the RD-002 cache dir,
SHA-256 re-verified against each sidecar manifest before use. A hash
mismatch aborts the run — no substitute data, ever.

Intraday containment (declared): every entry is simulated on the slice
of bars from its signal bar through the last bar starting before 21:00
UTC that date, with bracket_time max_bars spanning the slice, via
rd.fastsim.simulate_entries. Positions cannot cross a session end, a
weekend or a data gap by construction.

  python3 -m rigorous_backtest.rd7.run_rd7
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from ..rd.common import atr as atr_series
from ..rd.fastsim import simulate_entries
from ..simulator import Costs, trade_metrics
from ..walkforward import FOLDS, trades_in_window
from ..rd2 import costs2
from ..rd2.stats2 import check_bar2, fold_report, significance, trade_stats
from .families7 import CONFIGS

CACHE = Path("/home/hatch/workspace/str-rd2/cache2")
OUT = Path(__file__).resolve().parent.parent / "results_rd7"
INSTRUMENTS = ["GOLD", "SILVER", "WTI"]
LATE = ["W2", "W3", "W4", "W5"]
PRIOR_GLOBAL_TRIALS = 1557
RD7_TRIALS = 45
N_GLOBAL = PRIOR_GLOBAL_TRIALS + RD7_TRIALS  # 1602, declared lower bound
OOS_START, OOS_END = "2025-01-01", "2026-11-01"


# ------------------------------------------------------------------ data
def load_series(symbol: str) -> tuple[pd.DataFrame, dict]:
    csv_path = CACHE / f"YH_{symbol}_1h.csv"
    man = json.loads((CACHE / f"YH_{symbol}_1h.csv.json").read_text())
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    if digest != man["csv_sha256"]:
        raise RuntimeError(f"PROVENANCE FAILURE: {csv_path} sha256 "
                           f"{digest} != sidecar {man['csv_sha256']}")
    df = pd.read_csv(csv_path, parse_dates=["ts"])
    df = df.set_index("ts").sort_index()
    assert df.index.is_unique, f"{symbol}: duplicate timestamps"
    assert df.index.tz is not None, f"{symbol}: naive index"
    prov = {"source": man["source"], "yahoo_symbol": man["yahoo_symbol"],
            "csv_sha256": digest, "rows": int(len(df)),
            "first_bar_utc": str(df.index[0]),
            "last_bar_utc": str(df.index[-1]),
            "sidecar_rows": man["rows"], "hash_verified": True}
    return df, prov


def session_end_positions(df: pd.DataFrame) -> np.ndarray:
    """For each bar, the index of the last bar starting before 21:00 UTC
    on the same UTC date (the intraday flat-by boundary)."""
    ts = df.index
    ends = np.empty(len(df), dtype=int)
    days = ts.normalize()
    uniq, inverse = np.unique(days, return_inverse=True)
    for k, d in enumerate(uniq):
        boundary = d + pd.Timedelta(hours=21)
        last = int(ts.searchsorted(boundary, side="left")) - 1
        ends[inverse == k] = last
    return ends


# ------------------------------------------------------------ simulation
def simulate_cell(df: pd.DataFrame, entries: list[tuple[int, str]],
                  atr_arr: np.ndarray, spec: dict, symbol: str,
                  costs: Costs, end_pos: np.ndarray):
    """One-position-at-a-time simulation with per-entry session slices.

    Mirrors rd.fastsim.simulate_entries' cursor discipline (a signal is
    skipped while a position is open, i.e. signal bar < last exit bar).
    Returns (trades, signal_bars) — signal_bars[i] produced trades[i].
    """
    trades, sig_bars = [], []
    cursor = 0
    n = len(df)
    for sig, side in sorted(entries):
        if sig < cursor or sig + 1 >= n:
            continue
        end = int(end_pos[sig])
        if sig + 1 > end:
            continue  # no entry bar inside this session
        sub = df.iloc[sig:end + 1]
        atr_sub = atr_arr[sig:end + 1]
        spec_i = {**spec, "max_bars": end - sig}
        got = simulate_entries(sub, [(0, side)], atr_sub, spec_i,
                               symbol, costs)
        if not got:
            continue
        trade = got[0]
        trades.append(trade)
        sig_bars.append(sig)
        cursor = int(df.index.get_indexer([trade.exit_time])[0])
    return trades, sig_bars


def judge(trades: list, symbol: str) -> tuple[dict, dict, dict]:
    """fold_report + declared single-instrument holdout + check_bar2."""
    report = fold_report(trades, LATE, [symbol])
    w5 = report["per_fold"]["W5"]
    holdout = {"rule": "W5 fold expectancy > 0 on >= 30 trades "
                       "(declared single-instrument substitute)",
               "w5_trades": w5.get("trades"),
               "w5_expectancy_net": w5.get("expectancy_net"),
               "passes": bool((w5.get("trades") or 0) >= 30
                              and (w5.get("expectancy_net") or 0) > 0)}
    bar = check_bar2(report, holdout)
    return report, holdout, bar


def oos_trades(trades: list) -> list:
    return trades_in_window(trades, OOS_START, OOS_END)


# ---------------------------------------------------------------- sanity
def brute_force_check(df: pd.DataFrame, sig: int, side: str,
                      atr_arr: np.ndarray, spec: dict, costs: Costs,
                      end_pos: np.ndarray, trade) -> bool:
    """Independently re-derive one trade's exit by a plain bar scan and
    compare (exit time, exit price, net return) with fastsim's output."""
    opens = df["open"].to_numpy(); highs = df["high"].to_numpy()
    lows = df["low"].to_numpy(); closes = df["close"].to_numpy()
    entry_bar = sig + 1
    entry_price = float(opens[entry_bar])
    a = float(atr_arr[sig])
    if side == "LONG":
        sl, tp = entry_price - spec["sl_atr"] * a, entry_price + spec["tp_atr"] * a
    else:
        sl, tp = entry_price + spec["sl_atr"] * a, entry_price - spec["tp_atr"] * a
    end = int(end_pos[sig])
    first_sl = first_tp = None
    for j in range(entry_bar, end + 1):
        if side == "LONG":
            if first_sl is None and lows[j] <= sl:
                first_sl = (j, opens[j] if opens[j] <= sl else sl)
            if first_tp is None and highs[j] >= tp:
                first_tp = (j, opens[j] if opens[j] >= tp else tp)
        else:
            if first_sl is None and highs[j] >= sl:
                first_sl = (j, opens[j] if opens[j] >= sl else sl)
            if first_tp is None and lows[j] <= tp:
                first_tp = (j, opens[j] if opens[j] <= tp else tp)
        if first_sl is not None and first_tp is not None:
            break
    if first_sl is not None and (first_tp is None or first_sl[0] <= first_tp[0]):
        exit_bar, exit_price = first_sl
    elif first_tp is not None:
        exit_bar, exit_price = first_tp
    else:
        exit_bar, exit_price = end, float(closes[end])
    if df.index[exit_bar] != trade.exit_time:
        return False
    if abs(float(exit_price) - trade.exit_price) > 1e-9 * max(1.0, abs(float(exit_price))):
        return False
    from ..simulator import _net_return
    expect = _net_return(side, entry_price, float(exit_price), costs)
    return abs(expect - trade.net_return) < 1e-12


# ------------------------------------------------------------------- wf
def wf_select(variant_trades: dict[str, list]) -> list:
    """Declared wf-select procedure over the family's two variants."""
    fold_bounds = {fid: (s, e) for fid, s, e in FOLDS}
    names = list(variant_trades)
    chosen: list = []
    picks = {}
    for fid in LATE:
        s, e = fold_bounds[fid]
        best, best_key = None, None
        for name in names:
            is_trades = trades_in_window(variant_trades[name], None, s)
            m = trade_metrics(is_trades)
            eligible = (m.get("trades") or 0) >= 30
            key = (1 if eligible else 0,
                   (m.get("expectancy_net") or -9) if eligible else -9,
                   m.get("trades") or 0)
            if best_key is None or key > best_key:
                best, best_key = name, key
        picks[fid] = best
        chosen.extend(trades_in_window(variant_trades[best], s, e))
    wf_select.picks = picks  # type: ignore[attr-defined]
    return chosen


# ------------------------------------------------------------------ main
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data, prov, atrs, ends = {}, {}, {}, {}
    for sym in INSTRUMENTS:
        df, p = load_series(sym)
        data[sym], prov[sym] = df, p
        atrs[sym] = atr_series(df, 14).to_numpy(dtype=float)
        ends[sym] = session_end_positions(df)
        print(f"[data] {sym}: {p['rows']} bars {p['first_bar_utc']} -> "
              f"{p['last_bar_utc']} sha256 verified")

    # ---- fixed cells
    cell_trades: dict[tuple, list] = {}
    cell_entries: dict[tuple, list] = {}
    rows = []
    for sym in INSTRUMENTS:
        costs = costs2.costs_for("comm7", sym)
        for cfg in CONFIGS:
            entries = cfg["fn"](data[sym])
            trades, _sigs = simulate_cell(data[sym], entries, atrs[sym],
                                          cfg["spec"], sym, costs,
                                          ends[sym])
            key = (cfg["family"], cfg["variant"], sym)
            cell_trades[key] = trades
            cell_entries[key] = entries
            report, holdout, bar = judge(trades, sym)
            rows.append({
                "kind": "fixed_cell", "family": cfg["family"],
                "variant": cfg["variant"], "instrument": sym,
                "timeframe": "1h", "fold_profile": LATE,
                "provenance": prov[sym],
                "costs": costs2.describe("comm7", sym),
                "exit_spec": cfg["spec"], "entries_generated": len(entries),
                "report": report, "holdout": holdout, "bar": bar,
            })
            po = report["pooled_oos"]
            print(f"[cell] {cfg['family']}/{cfg['variant']} {sym}: "
                  f"OOS trades={po.get('trades')} exp={po.get('expectancy_net')} "
                  f"PF={po.get('profit_factor_net')} bar={bar['passes_bar']}")

    # ---- wf-select procedures
    wf_rows = []
    fam_variants: dict[str, list[str]] = {}
    for cfg in CONFIGS:
        fam_variants.setdefault(cfg["family"], []).append(cfg["variant"])
    for sym in INSTRUMENTS:
        for fam, variants in fam_variants.items():
            vt = {v: cell_trades[(fam, v, sym)] for v in variants}
            chosen = wf_select(vt)
            picks = dict(wf_select.picks)  # type: ignore[attr-defined]
            report, holdout, bar = judge(chosen, sym)
            row = {"kind": "wf_select", "family": fam,
                   "variant": "wf_select", "instrument": sym,
                   "timeframe": "1h", "fold_profile": LATE,
                   "provenance": prov[sym],
                   "costs": costs2.describe("comm7", sym),
                   "fold_picks": picks,
                   "report": report, "holdout": holdout, "bar": bar}
            wf_rows.append(row)
            po = report["pooled_oos"]
            print(f"[wf] {fam}/wf_select {sym}: picks={picks} "
                  f"OOS trades={po.get('trades')} exp={po.get('expectancy_net')} "
                  f"PF={po.get('profit_factor_net')} bar={bar['passes_bar']}")

    all_rows = rows + wf_rows

    # ---- significance (Bonferroni gate at N_GLOBAL; DSR disclosed)
    # Pooled OOS trade list per row (wf pools rebuilt deterministically).
    wf_pool: dict[tuple, list] = {}
    for r in wf_rows:
        fam, sym = r["family"], r["instrument"]
        vt = {v: cell_trades[(fam, v, sym)] for v in fam_variants[fam]}
        wf_pool[(fam, sym)] = wf_select(vt)
    pool_trades: dict[int, list] = {}
    for i, r in enumerate(all_rows):
        if r["kind"] == "fixed_cell":
            pool_trades[i] = oos_trades(cell_trades[
                (r["family"], r["variant"], r["instrument"])])
        else:
            pool_trades[i] = oos_trades(wf_pool[(r["family"],
                                                 r["instrument"])])
    srs = []
    for tr in pool_trades.values():
        st = trade_stats(tr)
        if st.get("sharpe_per_trade") is not None and (st.get("n") or 0) >= 30:
            srs.append(st["sharpe_per_trade"])
    sr_std = float(np.std(np.array(srs), ddof=1)) if len(srs) > 1 else 0.0
    for i, r in enumerate(all_rows):
        r["significance"] = significance(pool_trades[i], N_GLOBAL, sr_std)

    # ---- 2x-cost sensitivity for near-bar rows (RD-002 definition)
    for r in all_rows:
        po = r["report"]["pooled_oos"]
        near = ((po.get("expectancy_net") or -9) > 0
                and (po.get("profit_factor_net") or 0) >= 1.15
                and (po.get("trades") or 0) >= 200)
        r["sensitivity_2x_costs"] = None
        if near:
            sym = r["instrument"]
            costs2x = costs2.double(costs2.costs_for("comm7", sym))
            if r["kind"] == "fixed_cell":
                cfg = next(c for c in CONFIGS
                           if c["family"] == r["family"]
                           and c["variant"] == r["variant"])
                trades2x, _ = simulate_cell(
                    data[sym], cell_entries[(r["family"], r["variant"], sym)],
                    atrs[sym], cfg["spec"], sym, costs2x, ends[sym])
                pool2x = oos_trades(trades2x)
            else:  # wf_select: re-run both variants at 2x, re-select
                vt2 = {}
                for v in fam_variants[r["family"]]:
                    cfg = next(c for c in CONFIGS
                               if c["family"] == r["family"]
                               and c["variant"] == v)
                    t2, _ = simulate_cell(
                        data[sym], cell_entries[(r["family"], v, sym)],
                        atrs[sym], cfg["spec"], sym, costs2x, ends[sym])
                    vt2[v] = t2
                pool2x = oos_trades(wf_select(vt2))
            m2 = trade_metrics(pool2x)
            r["sensitivity_2x_costs"] = {
                **m2, "promotable_at_2x": bool(
                    (m2.get("expectancy_net") or -9) > 0
                    and (m2.get("profit_factor_net") or 0) >= 1.0)}
            print(f"[sens] {r['family']}/{r['variant']} {sym}: "
                  f"2x PF={m2.get('profit_factor_net')} "
                  f"exp={m2.get('expectancy_net')}")

    # ---- verdicts
    for r in all_rows:
        sens = r.get("sensitivity_2x_costs")
        sig_pass = bool(r["significance"].get("bonferroni_pass"))
        if r["bar"]["passes_bar"] and sig_pass and sens and sens["promotable_at_2x"]:
            r["verdict"] = "PROMOTABLE"
        elif r["bar"]["passes_bar"]:
            r["verdict"] = "WATCHLIST"
        else:
            r["verdict"] = "FAIL"

    # ---- sanity: brute-force re-derivation of sampled trades
    sanity = {"hash_verification": {s: prov[s]["hash_verified"]
                                    for s in INSTRUMENTS},
              "brute_force_trade_checks": []}
    sym = "GOLD"
    cfg = CONFIGS[0]
    entries = cell_entries[(cfg["family"], cfg["variant"], sym)]
    trades, sigs = simulate_cell(data[sym], entries, atrs[sym],
                                 cfg["spec"], sym,
                                 costs2.costs_for("comm7", sym), ends[sym])
    for t, s in list(zip(trades, sigs))[:5]:
        ok = brute_force_check(data[sym], s, t.side, atrs[sym],
                               cfg["spec"], costs2.costs_for("comm7", sym),
                               ends[sym], t)
        sanity["brute_force_trade_checks"].append(
            {"cell": f"{cfg['family']}/{cfg['variant']} {sym}",
             "entry_time": str(t.entry_time), "exit_time": str(t.exit_time),
             "side": t.side, "rederived_identical": bool(ok)})
    sanity["all_brute_force_identical"] = all(
        c["rederived_identical"] for c in sanity["brute_force_trade_checks"])
    print(f"[sanity] brute-force checks: {sanity['all_brute_force_identical']}")

    (OUT / "rows.json").write_text(json.dumps(
        {"task": "TASK-STR-RD-007", "n_global": N_GLOBAL,
         "prior_global_trials": PRIOR_GLOBAL_TRIALS,
         "rd7_trials": RD7_TRIALS, "sr_std_across_cells": sr_std,
         "rows": all_rows}, indent=1, default=str))
    ranked = sorted(
        ({"kind": r["kind"], "family": r["family"],
          "variant": r["variant"], "instrument": r["instrument"],
          "oos_trades": r["report"]["pooled_oos"].get("trades"),
          "expectancy_net": r["report"]["pooled_oos"].get("expectancy_net"),
          "profit_factor_net": r["report"]["pooled_oos"].get("profit_factor_net"),
          "passes_bar": r["bar"]["passes_bar"],
          "bonferroni_p": r["significance"].get("p_one_sided"),
          "bonferroni_pass": r["significance"].get("bonferroni_pass"),
          "deflated_sharpe": r["significance"].get("deflated_sharpe"),
          "pf_2x_costs": (r.get("sensitivity_2x_costs") or {}).get(
              "profit_factor_net"),
          "verdict": r["verdict"]} for r in all_rows),
        key=lambda x: (x["expectancy_net"] is not None,
                       x["expectancy_net"] or -9), reverse=True)
    (OUT / "synthesis.json").write_text(json.dumps(
        {"task": "TASK-STR-RD-007",
         "prior_global_trials": PRIOR_GLOBAL_TRIALS,
         "rd7_fixed_cells": len(rows), "rd7_wf_procedures": len(wf_rows),
         "rd7_trials": RD7_TRIALS, "n_global_lower_bound": N_GLOBAL,
         "bonferroni_alpha_at_1602": 0.05 / N_GLOBAL,
         "bonferroni_alpha_at_2000_reference": 0.05 / 2000,
         "sr_std_across_cells": sr_std,
         "promotable": [x for x in ranked if x["verdict"] == "PROMOTABLE"],
         "watchlist": [x for x in ranked if x["verdict"] == "WATCHLIST"],
         "ranked_table": ranked}, indent=1, default=str))
    (OUT / "sanity_checks.json").write_text(json.dumps(sanity, indent=1))
    print(f"[done] rows={len(all_rows)} promotable="
          f"{sum(1 for r in all_rows if r['verdict'] == 'PROMOTABLE')} "
          f"watchlist={sum(1 for r in all_rows if r['verdict'] == 'WATCHLIST')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
