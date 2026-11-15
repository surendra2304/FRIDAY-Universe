#!/usr/bin/env python3
"""TASK-STR-RD-009 — delta-neutral funding-carry simulator.

Implements EXACTLY the frozen declaration (results_rd9/declaration.json,
SHA-256 c5bb1d91f5cf349846f96a76f21d7aca3914f05d6de494ab6744fec8b242479c,
posted on issue #35 in comment 6891895567 before this code ran):

- crypto30 panel; funding prints (RD-003 verified cache), perp 1h klines
  (RD-002 verified cache), spot 1d klines (RD-009 fetch, checksum-verified).
- Daily 00:00 UTC decision grid; F72 = trailing-72h funding sum.
- Coin-quantity hedge; episode PnL in % of entry spot notional:
    dir * ( ((S_x-S_e)-(P_x-P_e))/S_e + SUM_{prints in (t_e,t_x]} rate*P_print/S_e ) * 100
    - fees - slippage - borrow(NEG only)
- 8 declared cells; standard folds W1..W5; RD-002 bar with episodes in
  place of trades; 2x-cost sensitivity; Bonferroni at N=1934.

Outputs (into results_rd9/): synthesis.json, rows_rd9.json,
episodes_rd9.csv, descriptive.json, spot_manifest.json.
Research only — no orders, no production contact.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

WS = Path("/home/hatch/workspace/rd-009-redo")
FUND_DIR = WS / "data" / "funding"
SPOT_DIR = WS / "data" / "spot"
PERP_DIR = Path("/home/hatch/workspace/str-rd2/cache2")
OUT = WS / "results_rd9"

PANEL = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
         "DOGEUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT",
         "TRXUSDT", "AVAXUSDT", "NEARUSDT", "ATOMUSDT", "UNIUSDT",
         "ETCUSDT", "BCHUSDT", "FILUSDT", "APTUSDT", "ARBUSDT",
         "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT", "HBARUSDT",
         "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT"]

FOLDS = [("W1", "2024-07-01", "2025-01-01"), ("W2", "2025-01-01", "2025-07-01"),
         ("W3", "2025-07-01", "2026-01-01"), ("W4", "2026-01-01", "2026-07-01"),
         ("W5", "2026-07-01", "2026-11-01")]
ERA_START, ERA_END = "2024-07-01", "2026-11-01"

FEE_SPOT, FEE_PERP, SLIP = 0.10, 0.05, 0.02       # % per side / per leg-side
FEES_RT = 2 * (FEE_SPOT + FEE_PERP)               # 0.30 %
SLIP_RT = 4 * SLIP                                # 0.08 %
BORROW_DAY = 0.02                                 # % per day, NEG only
BONF_N = 1934
BONF_ALPHA = 0.05 / BONF_N

CELLS = [
    {"id": "always_pos", "dir": 1, "kind": "always"},
    {"id": "always_neg", "dir": -1, "kind": "always"},
    {"id": "thr_pos_015", "dir": 1, "kind": "thr", "theta": 0.15},
    {"id": "thr_pos_030", "dir": 1, "kind": "thr", "theta": 0.30},
    {"id": "thr_pos_060", "dir": 1, "kind": "thr", "theta": 0.60},
    {"id": "thr_neg_015", "dir": -1, "kind": "thr", "theta": 0.15},
    {"id": "thr_neg_030", "dir": -1, "kind": "thr", "theta": 0.30},
    {"id": "thr_neg_060", "dir": -1, "kind": "thr", "theta": 0.60},
]


# ---------------------------------------------------------------- data load
class SymbolData:
    def __init__(self, sym: str):
        self.sym = sym
        fund = pd.read_csv(FUND_DIR / f"FUND_{sym}.csv")
        fund["ts"] = pd.to_datetime(fund["timestamp"], utc=True)
        fund = fund.sort_values("ts")
        self.print_ts = fund["ts"]
        self.print_ns = fund["ts"].astype("int64").to_numpy()
        self.print_rate = fund["funding_rate"].to_numpy(dtype=float)

        perp = pd.read_csv(PERP_DIR / f"{sym}_1h_2022-01_2026-10.csv")
        perp["ts"] = pd.to_datetime(perp["ts"], utc=True)
        perp = perp.sort_values("ts")
        self.perp = perp
        # perp close of the 1h bar ENDING at t  == bar starting t-1h
        self.perp_close_at = dict(zip(perp["ts"], perp["close"]))
        self.perp_high_at = dict(zip(perp["ts"], perp["high"]))
        self.perp_low_at = dict(zip(perp["ts"], perp["low"]))
        # funding cashflow per print: rate * perp price at print
        p_print = np.array([self.perp_close_at.get(t - pd.Timedelta(hours=1), np.nan)
                            for t in fund["ts"]])
        self.print_p = p_print
        self.print_cash = self.print_rate * p_print      # per unit coin, USDT
        self.cash_prefix = np.concatenate([[0.0], np.nancumsum(self.print_cash)])
        self.rate_prefix = np.concatenate([[0.0], np.nancumsum(self.print_rate)])

        # daily boundary prices: price at 00:00 of day d == close of day d-1
        daily = perp.set_index("ts")["close"].resample("1D").last()
        counts = perp.set_index("ts")["close"].resample("1D").count()
        daily = daily[counts == 24]                       # complete days only
        self.perp_day_close = daily                       # index = day open
        spot = pd.read_csv(SPOT_DIR / f"SPOT_{sym}_1d.csv")
        spot["ts"] = pd.to_datetime(spot["ts"], utc=True)
        spot = spot.sort_values("ts")
        self.spot_day_close = spot.set_index("ts")["close"]

    def price_at(self, t: pd.Timestamp):
        """(spot, perp) at boundary t = close of day t-1; None if missing."""
        day = (t - pd.Timedelta(days=1)).normalize()
        try:
            s = float(self.spot_day_close.loc[day])
            p = float(self.perp_day_close.loc[day])
        except KeyError:
            return None
        if math.isnan(s) or math.isnan(p):
            return None
        return s, p

    def f72(self, t: pd.Timestamp) -> float:
        """Trailing-72h funding sum (fraction) from prints in (t-72h, t]."""
        lo = np.searchsorted(self.print_ns, (t - pd.Timedelta(hours=72)).value, side="right")
        hi = np.searchsorted(self.print_ns, t.value, side="right")
        return float(self.rate_prefix[hi] - self.rate_prefix[lo])

    def funding_cash(self, te: pd.Timestamp, tx: pd.Timestamp) -> float:
        """SUM rate*P_print over prints in (te, tx], per unit coin (USDT)."""
        lo = np.searchsorted(self.print_ns, te.value, side="right")
        hi = np.searchsorted(self.print_ns, tx.value, side="right")
        return float(self.cash_prefix[hi] - self.cash_prefix[lo])

    def max_adverse(self, te, tx, direction) -> float:
        """Worst intra-episode perp move against the perp leg, % of entry."""
        bars = self.perp[(self.perp["ts"] >= te) & (self.perp["ts"] < tx)]
        if len(bars) == 0:
            return 0.0
        pe = self.price_at(te)
        if pe is None:
            return 0.0
        p_entry = pe[1]
        if direction == 1:   # short perp: rising price hurts
            return float((bars["high"].max() / p_entry - 1) * 100)
        return float((1 - bars["low"].min() / p_entry) * 100)


def episode_pnl(sd: SymbolData, te, tx, direction, cost_mult=1.0):
    """Declared episode PnL decomposition, % of entry spot notional."""
    pe = sd.price_at(te)
    px = sd.price_at(tx)
    if pe is None or px is None:
        return None
    s_e, p_e = pe
    s_x, p_x = px
    days = (tx - te).days
    funding = direction * sd.funding_cash(te, tx) / s_e * 100
    basis = direction * (((s_x - s_e) - (p_x - p_e)) / s_e) * 100
    fees = FEES_RT * cost_mult
    slip = SLIP_RT * cost_mult
    borrow = BORROW_DAY * days * cost_mult if direction < 0 else 0.0
    total = funding + basis - fees - slip - borrow
    return {"funding": funding, "basis": basis, "fees": fees, "slip": slip,
            "borrow": borrow, "total": total, "days": days,
            "s_e": s_e, "p_e": p_e, "s_x": s_x, "p_x": p_x}


def fold_active(sd: SymbolData, fold) -> bool:
    """Declared activation rule: every daily boundary of the fold must
    have both leg prices, and funding prints must exist in the fold."""
    _, fs, fe = fold
    t0, t1 = pd.Timestamp(fs, tz="UTC"), pd.Timestamp(fe, tz="UTC")
    for t in pd.date_range(t0, t1, freq="1D"):
        if sd.price_at(t) is None:
            return False
    lo = np.searchsorted(sd.print_ns, t0.value, side="right")
    hi = np.searchsorted(sd.print_ns, t1.value, side="right")
    return hi > lo


def run_cell(sd: SymbolData, cell, fold) -> list[dict]:
    """Episodes for one symbol in one fold under one cell.
    Caller guarantees fold_active(sd, fold); emit() asserts pricing."""
    fid, fs, fe = fold
    t0, t1 = pd.Timestamp(fs, tz="UTC"), pd.Timestamp(fe, tz="UTC")
    out = []
    days = pd.date_range(t0, t1, freq="1D")

    def emit(te, tx):
        r = episode_pnl(sd, te, tx, cell["dir"], 1.0)
        r2 = episode_pnl(sd, te, tx, cell["dir"], 2.0)
        assert r is not None and r2 is not None, \
            f"unpriced episode {sd.sym} {te} {tx} in an active fold"
        out.append({"symbol": sd.sym, "fold": fid, "cell": cell["id"],
                    "dir": cell["dir"], "entry": te.isoformat(), "exit": tx.isoformat(),
                    "days": r["days"], "funding_pct": r["funding"], "basis_pct": r["basis"],
                    "fees_pct": r["fees"], "slip_pct": r["slip"], "borrow_pct": r["borrow"],
                    "pnl_pct": r["total"], "pnl2x_pct": r2["total"],
                    "max_adverse_pct": sd.max_adverse(te, tx, cell["dir"])})

    if cell["kind"] == "always":
        emit(t0, t1)
        return out
    theta = cell["theta"] / 100.0        # % -> fraction
    d = cell["dir"]
    in_pos, te = False, None
    for t in days:
        f = sd.f72(t)
        if in_pos:
            held = (t - te).days
            exit_now = (f < theta / 3) if d == 1 else (f > -theta / 3)
            if exit_now or held >= 45 or t == t1:
                emit(te, t)
                in_pos = False
        if not in_pos and t != t1:
            if (d == 1 and f >= theta) or (d == -1 and f <= -theta):
                in_pos, te = True, t
    if in_pos:
        emit(te, t1)
    return out


def trade_metrics(pnls: np.ndarray) -> dict:
    if len(pnls) == 0:
        return {"trades": 0, "expectancy_pct": None, "pf": None}
    pos = pnls[pnls > 0].sum()
    neg = -pnls[pnls < 0].sum()
    pf = float(pos / neg) if neg > 0 else (float("inf") if pos > 0 else None)
    return {"trades": int(len(pnls)), "expectancy_pct": float(pnls.mean()), "pf": pf}


def judge(episodes: list[dict]) -> dict:
    pnls = np.array([e["pnl_pct"] for e in episodes])
    pnls2 = np.array([e["pnl2x_pct"] for e in episodes])
    m = trade_metrics(pnls)
    m2 = trade_metrics(pnls2)
    folds = {}
    for fid, _, _ in FOLDS:
        fp = np.array([e["pnl_pct"] for e in episodes if e["fold"] == fid])
        folds[fid] = {"episodes": int(len(fp)),
                      "pnl_sum_pct": float(fp.sum()) if len(fp) else 0.0,
                      **trade_metrics(fp)}
    folds_pos = sum(1 for f in folds.values() if f["pnl_sum_pct"] > 0)
    sym_tot = {}
    for e in episodes:
        sym_tot[e["symbol"]] = sym_tot.get(e["symbol"], 0.0) + e["pnl_pct"]
    breadth = (float(np.mean([v > 0 for v in sym_tot.values()]))
               if sym_tot else 0.0)
    if len(pnls) >= 3 and np.std(pnls) > 0:
        p_val = float(stats.ttest_1samp(pnls, 0.0, alternative="greater").pvalue)
    else:
        p_val = None
    checks = {
        "expectancy_gt_0": (m["expectancy_pct"] or -1) > 0,
        "pf_ge_1_2": (m["pf"] or 0) >= 1.2,
        "episodes_ge_200": len(pnls) >= 200,
        "folds_ge_80pct": folds_pos >= 4,
        "holdout_exp_gt_0": (folds["W5"]["expectancy_pct"] or -1) > 0,
        "breadth_ge_50pct": breadth >= 0.5,
        "cost2x_exp_gt_0": (m2["expectancy_pct"] or -1) > 0,
        "bonferroni": (p_val is not None and p_val < BONF_ALPHA),
    }
    return {"pooled": m, "pooled_2x": m2, "folds": folds,
            "folds_positive": folds_pos, "breadth": breadth,
            "symbols_with_episodes": len(sym_tot),
            "p_value_one_sided_t": p_val, "bonferroni_alpha": BONF_ALPHA,
            "checks": checks, "PASS": all(checks.values())}


# ------------------------------------------------------------------- sanity
def sanity(sd_btc: SymbolData) -> dict:
    res = {}
    # S1: synthetic frozen prices, zero costs -> PnL == funding sum exactly
    class Fake(SymbolData):
        def __init__(self):
            idx = pd.date_range("2024-07-01", periods=30, freq="8h", tz="UTC")
            self.print_ts = idx
            self.print_ns = idx.astype("int64").to_numpy()
            self.print_rate = np.full(30, 0.0001)
            self.print_cash = self.print_rate * 100.0
            self.cash_prefix = np.concatenate([[0.0], np.nancumsum(self.print_cash)])
            self.rate_prefix = np.concatenate([[0.0], np.nancumsum(self.print_rate)])
        def price_at(self, t):
            return 100.0, 100.0
    fake = Fake()
    te, tx = pd.Timestamp("2024-07-02", tz="UTC"), pd.Timestamp("2024-07-05", tz="UTC")
    global FEES_RT, SLIP_RT
    saved = (FEES_RT, SLIP_RT)
    FEES_RT = SLIP_RT = 0.0
    r = episode_pnl(fake, te, tx, 1, 1.0)
    FEES_RT, SLIP_RT = saved
    expect = 9 * 0.0001 * 100  # 9 prints in (te, tx] * rate * 100 (pct)
    res["S1"] = {"got": r["total"], "expected": expect, "pass": abs(r["total"] - expect) < 1e-9}
    # S3: BTC always_pos W1 funding via brute force over raw CSVs
    fund = pd.read_csv(FUND_DIR / "FUND_BTCUSDT.csv")
    fund["ts"] = pd.to_datetime(fund["timestamp"], utc=True)
    perp = pd.read_csv(PERP_DIR / "BTCUSDT_1h_2022-01_2026-10.csv")
    perp["ts"] = pd.to_datetime(perp["ts"], utc=True)
    close_at = dict(zip(perp["ts"], perp["close"]))
    t0, t1 = pd.Timestamp("2024-07-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
    brute = 0.0
    for _, row in fund[(fund["ts"] > t0) & (fund["ts"] <= t1)].iterrows():
        brute += row["funding_rate"] * close_at[row["ts"] - pd.Timedelta(hours=1)]
    s_e = sd_btc.price_at(t0)[0]
    brute_pct = brute / s_e * 100
    engine_pct = sd_btc.funding_cash(t0, t1) / s_e * 100
    res["S3"] = {"brute_force_pct": brute_pct, "engine_pct": engine_pct,
                 "pass": abs(brute_pct - engine_pct) < 1e-9}
    return res


# -------------------------------------------------------------- descriptive
def descriptive(sds: dict[str, SymbolData]) -> dict:
    t0, t1 = pd.Timestamp(ERA_START, tz="UTC"), pd.Timestamp(ERA_END, tz="UTC")
    per_symbol, curves = {}, {}
    census_eps = []
    for sym, sd in sds.items():
        row = {"symbol": sym}
        for name, d in (("pos", 1), ("neg", -1)):
            r = episode_pnl(sd, t0, t1, d, 1.0)
            if r is None:
                row[name] = None
                continue
            years = r["days"] / 365.25
            row[name] = {"gross_funding_pct": r["funding"], "basis_pct": r["basis"],
                         "costs_pct": r["fees"] + r["slip"] + r["borrow"],
                         "net_pct": r["total"],
                         "annualised_net_pct": r["total"] / years if years else None}
        per_symbol[sym] = row
        # daily marked curve, continuous POS book
        days = pd.date_range(t0, t1, freq="1D")
        ref = sd.price_at(t0)
        if ref is None:
            continue
        s_ref = ref[0]
        daily_pnl = []
        prev_basis = None
        ok = True
        for i in range(len(days) - 1):
            a, b = days[i], days[i + 1]
            pa, pb = sd.price_at(a), sd.price_at(b)
            if pa is None or pb is None:
                ok = False
                break
            basis_b = pb[1] - pb[0]
            basis_a = pa[1] - pa[0]
            fund = sd.funding_cash(a, b) / s_ref * 100
            daily_pnl.append(fund - (basis_b - basis_a) / s_ref * 100)
        if ok:
            curves[sym] = np.array(daily_pnl)
    # equal-weight portfolio curve for POS; NEG mirrors funding/basis signs
    out = {"per_symbol_always_on_era": per_symbol}
    if curves:
        mat = np.vstack(list(curves.values()))
        port = mat.mean(axis=0)
        curve = np.concatenate([[-(FEES_RT + SLIP_RT)], np.cumsum(port)])
        peak = np.maximum.accumulate(curve)
        dd = float((curve - peak).min())
        out["always_pos_portfolio"] = {
            "symbols_in_curve": len(curves), "days": int(len(port)),
            "final_net_pct_incl_entry_exit_costs": float(curve[-1] - (FEES_RT + SLIP_RT)),
            "max_drawdown_pct_points": dd}
        neg = -port  # funding and basis components flip sign with direction
        curve_n = np.concatenate([[-(FEES_RT + SLIP_RT)], np.cumsum(neg)])
        peak_n = np.maximum.accumulate(curve_n)
        out["always_neg_portfolio_note"] = (
            "NEG curve additionally carries borrow drag not in the mirrored "
            "series; see per-symbol table for NEG nets.")
        out["always_neg_portfolio_mirrored_ex_borrow"] = {
            "max_drawdown_pct_points": float((curve_n - peak_n).min())}
    # failure census: funding print sign stats over the era
    census = {}
    for sym, sd in sds.items():
        mask = (sd.print_ns > t0.value) & (sd.print_ns <= t1.value)
        rates = sd.print_rate[mask]
        neg = rates < 0
        longest = cur = 0
        for v in neg:
            cur = cur + 1 if v else 0
            longest = max(longest, cur)
        census[sym] = {"prints": int(len(rates)),
                       "negative_share": float(neg.mean()) if len(rates) else None,
                       "longest_negative_streak_prints": int(longest),
                       "mean_rate_pct": float(rates.mean() * 100) if len(rates) else None}
    out["funding_print_census"] = census
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sds = {s: SymbolData(s) for s in PANEL}
    san = sanity(sds["BTCUSDT"])
    # data-quality audit: funding prints lacking a perp price (nancumsum
    # would silently treat them as zero cashflow — count them, split by
    # whether they fall inside the judged OOS era)
    era_lo, era_hi = (pd.Timestamp(ERA_START, tz="UTC").value,
                      pd.Timestamp(ERA_END, tz="UTC").value)
    nan_prints = {}
    for s, sd in sds.items():
        isn = np.isnan(sd.print_p)
        in_era = (sd.print_ns > era_lo) & (sd.print_ns <= era_hi)
        nan_prints[s] = {"total": int(isn.sum()),
                         "in_oos_era": int((isn & in_era).sum())}
    # coverage: symbol-fold activation per the declared rule
    coverage = {}
    for s, sd in sds.items():
        coverage[s] = {f[0]: fold_active(sd, f) for f in FOLDS}
    # S2: cost-scaling identity across real episodes (checked in-loop)
    all_eps, rows, s2_ok = [], {}, True
    for cell in CELLS:
        eps = []
        for sd in sds.values():
            for fold in FOLDS:
                if coverage[sd.sym][fold[0]]:
                    eps.extend(run_cell(sd, cell, fold))
        for e in eps:
            ident = (e["pnl2x_pct"] - (e["funding_pct"] + e["basis_pct"]
                     - 2 * (e["fees_pct"] + e["slip_pct"] + e["borrow_pct"])))
            if abs(ident) > 1e-9:
                s2_ok = False
        all_eps.extend(eps)
        rows[cell["id"]] = judge(eps)
        print(cell["id"], rows[cell["id"]]["pooled"], "PASS:", rows[cell["id"]]["PASS"], flush=True)
    san["S2"] = {"cost_scaling_identity_all_episodes": s2_ok, "pass": s2_ok}
    desc = descriptive(sds)
    # worst episodes + worst basis days for the census
    worst = sorted(all_eps, key=lambda e: e["pnl_pct"])[:10]
    desc["worst_episodes"] = [{k: e[k] for k in
        ("cell", "symbol", "fold", "entry", "exit", "days", "funding_pct",
         "basis_pct", "pnl_pct", "max_adverse_pct")} for e in worst]
    adv = [e["max_adverse_pct"] for e in all_eps]
    desc["adverse_excursion_all_episodes"] = {
        "median_pct": float(np.median(adv)), "p95_pct": float(np.percentile(adv, 95)),
        "max_pct": float(np.max(adv))}
    # spot manifest merge
    spot_man = {}
    for s in PANEL:
        spot_man[s] = json.loads((SPOT_DIR / f"SPOT_{s}_1d.csv.json").read_text())
    (OUT / "spot_manifest.json").write_text(json.dumps(spot_man, indent=1))
    pd.DataFrame(all_eps).to_csv(OUT / "episodes_rd9.csv", index=False)
    (OUT / "rows_rd9.json").write_text(json.dumps(rows, indent=1, default=str))
    (OUT / "descriptive.json").write_text(json.dumps(desc, indent=1, default=str))
    synthesis = {
        "task": "TASK-STR-RD-009",
        "declaration_sha256": "c5bb1d91f5cf349846f96a76f21d7aca3914f05d6de494ab6744fec8b242479c",
        "claim_comment": 6891895567,
        "trials": 8, "global_counter_before": 1926, "global_counter_after": 1934,
        "sanity": san,
        "data_quality": {"funding_prints_missing_perp_price": nan_prints,
                         "coverage_symbol_fold_active": coverage},
        "cells": {cid: {"pooled": r["pooled"], "pooled_2x": r["pooled_2x"],
                        "folds_positive": r["folds_positive"], "breadth": r["breadth"],
                        "p_value_one_sided_t": r["p_value_one_sided_t"],
                        "checks": r["checks"], "PASS": r["PASS"]}
                  for cid, r in rows.items()},
        "passers": [cid for cid, r in rows.items() if r["PASS"]],
    }
    (OUT / "synthesis.json").write_text(json.dumps(synthesis, indent=1, default=str))
    print("sanity:", json.dumps(san, default=str))
    print("passers:", synthesis["passers"])


if __name__ == "__main__":
    main()
