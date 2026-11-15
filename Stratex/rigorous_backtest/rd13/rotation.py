"""TASK-STR-RD-013 — Cross-asset momentum rotation (research only).

Rules-based rotation over a fixed 7-asset cross-asset universe, judged
under the programme's Anti-Overfit Law: walk-forward folds W1-W5 as
RD-002, OOS-only judgement, net of turnover costs, variants disclosed,
every configuration counted.

Pre-declared on issue #35 (comment 6890930042) BEFORE first execution:
  universe  BTCUSDT ETHUSDT SOLUSDT BNBUSDT (Binance Vision USDT-M 1h,
            resampled to daily, complete 24-bar buckets only),
            GOLD (GC=F), SPX (^GSPC), NDX (^NDX) via Yahoo daily.
  rule      score = trailing L-calendar-day return (last close <= t vs
            last close <= t-L; each endpoint's bar must be within 3
            calendar days of its target date; asset needs >= L+30 days
            of history). Hold top-K at equal weight 1/K.
            long_only: always invested. long_flat: a selected asset
            with score <= 0 is held as cash (weight NOT redistributed).
            If fewer than K assets are eligible, the unfilled weight
            stays in cash in both modes.
  grid      L in {21,63,126,252} x K in {1,2,3} x cadence in
            {weekly(Mon), daily} x mode in {long_only, long_flat}
            = 48 configurations = 48 trials.
  window    rebalancing starts 2023-01-02 for every config; periods are
            attributed to folds by period START date; OOS = starts in
            [2024-07-01, 2026-11-01). Earlier periods are in-sample
            context only.
  costs     round-trip bps by asset (crypto 16, GOLD 10, SPX/NDX 8 —
            the RD-002 table). At each rebalance the traded notional
            sum_i |w_new,i - w_drifted,i| is charged RT_i/2 per asset
            leg (one side), deducted from the new period's return.
            Initial build from cash is charged. Cash earns 0.
  metrics   compounded equity, max drawdown (period granularity),
            per-period profit factor, one-sided t-test on OOS period
            returns, per-asset P&L contribution shares, turnover.
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

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "GOLD", "SPX", "NDX"]
RT_BPS = {"BTCUSDT": 16.0, "ETHUSDT": 16.0, "SOLUSDT": 16.0, "BNBUSDT": 16.0,
          "GOLD": 10.0, "SPX": 8.0, "NDX": 8.0}
START = pd.Timestamp("2023-01-02")
OOS_START = pd.Timestamp("2024-07-01")
END = pd.Timestamp("2026-11-01")
FOLDS = [("W1", "2024-07-01", "2025-01-01"), ("W2", "2025-01-01", "2025-07-01"),
         ("W3", "2025-07-01", "2026-01-01"), ("W4", "2026-01-01", "2026-07-01"),
         ("W5", "2026-07-01", "2026-11-01")]
LOOKBACKS = [21, 63, 126, 252]
KS = [1, 2, 3]
CADENCES = ["weekly", "daily"]
MODES = ["long_only", "long_flat"]
STALE_DAYS = 3


def _verify(path: Path) -> dict:
    sidecar = path.with_suffix(path.suffix + ".json")
    meta = json.loads(sidecar.read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != meta.get("csv_sha256"):
        raise RuntimeError(f"hash mismatch for {path}; refusing unverified data")
    return meta


def load_closes(cache: Path) -> tuple[dict[str, pd.Series], dict]:
    """Daily close series per asset, indexed by UTC calendar date."""
    closes: dict[str, pd.Series] = {}
    provenance = {}
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
        f = cache / f"{sym}_1h_2022-01_2026-10.csv"
        meta = _verify(f)
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        daily = df["close"].resample("1D", origin="start_day").agg(["last", "count"])
        dropped = int((daily["count"] != 24).sum())
        s = daily.loc[daily["count"] == 24, "last"]
        s.index = s.index.tz_localize(None).normalize()
        closes[sym] = s
        provenance[sym] = {"source": meta["source"], "csv_sha256": meta["csv_sha256"],
                           "base_rows": meta["rows"], "daily_bars": int(len(s)),
                           "incomplete_days_dropped": dropped}
    for sym, yf in [("GOLD", "GOLD"), ("SPX", "SPX"), ("NDX", "NDX")]:
        f = cache / f"YH_{yf}_1d.csv"
        meta = _verify(f)
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
        s = df["close"].copy()
        s.index = s.index.normalize()
        s = s[~s.index.duplicated(keep="last")].sort_index()
        closes[sym] = s
        provenance[sym] = {"source": meta["source"], "csv_sha256": meta["csv_sha256"],
                           "base_rows": meta["rows"], "daily_bars": int(len(s)),
                           "incomplete_days_dropped": 0}
    return closes, provenance


def close_at(series: pd.Series, target: pd.Timestamp):
    """(close, staleness_days) of the last bar <= target, or None."""
    idx = series.index.searchsorted(target, side="right") - 1
    if idx < 0:
        return None
    bar_date = series.index[idx]
    return float(series.iloc[idx]), (target - bar_date).days


def rebalance_dates(cadence: str) -> list[pd.Timestamp]:
    if cadence == "weekly":
        days = pd.date_range(START, END, freq="W-MON")
    else:
        days = pd.date_range(START, END, freq="D")
    return list(days)


def run_config(closes, lookback, k, cadence, mode, cost_mult=1.0):
    dates = rebalance_dates(cadence)
    periods = []  # (start, net_return, gross_return, turnover_cost, {asset: contrib})
    weights = {a: 0.0 for a in ASSETS}  # start all cash
    for j, t in enumerate(dates):
        t_next = dates[j + 1] if j + 1 < len(dates) else END
        if t_next <= t:
            continue
        # --- selection at t (uses only bars <= t) ---
        scored = []
        for a in ASSETS:
            s = closes[a]
            if (t - s.index[0]).days < lookback + 30:
                continue
            now = close_at(s, t)
            past = close_at(s, t - pd.Timedelta(days=lookback))
            if now is None or past is None:
                continue
            if now[1] > STALE_DAYS or past[1] > STALE_DAYS:
                continue
            scored.append((a, now[0] / past[0] - 1.0))
        scored.sort(key=lambda x: (-x[1], x[0]))
        new_w = {a: 0.0 for a in ASSETS}
        for a, score in scored[:k]:
            if mode == "long_flat" and score <= 0:
                new_w[a] = 0.0
            else:
                new_w[a] = 1.0 / k
        # --- turnover cost vs current (drifted) weights ---
        cost = 0.0
        for a in ASSETS:
            dw = abs(new_w[a] - weights[a])
            if dw > 0:
                cost += dw * (RT_BPS[a] * cost_mult / 10000.0) / 2.0
        # --- period returns with weights new_w over (t, t_next] ---
        gross = 0.0
        contrib = {}
        for a in ASSETS:
            if new_w[a] == 0.0:
                continue
            c0 = close_at(closes[a], t)
            c1 = close_at(closes[a], t_next)
            if c0 is None or c1 is None:
                contrib[a] = 0.0
                continue
            r = c1[0] / c0[0] - 1.0
            contrib[a] = new_w[a] * r
            gross += contrib[a]
        net = gross - cost
        periods.append({"start": t, "net": net, "gross": gross,
                        "cost": cost, "contrib": contrib})
        # --- drift weights to t_next for the next turnover charge ---
        # drifted w_i = w_i * (1 + r_i) / (1 + gross); the residual is cash.
        denom = 1.0 + gross
        weights = {}
        for a in ASSETS:
            if new_w[a]:
                r_i = contrib.get(a, 0.0) / new_w[a]
                weights[a] = new_w[a] * (1.0 + r_i) / denom
            else:
                weights[a] = 0.0
    return periods


def summarise(periods):
    oos = [p for p in periods if OOS_START <= p["start"] < END]
    is_p = [p for p in periods if p["start"] < OOS_START]
    rets = np.array([p["net"] for p in oos], dtype=float)
    eq = np.cumprod(1.0 + rets)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    dd = float(np.min(eq / peak - 1.0)) if len(eq) else 0.0
    pos = float(rets[rets > 0].sum())
    neg = float(-rets[rets < 0].sum())
    pf = (pos / neg) if neg > 0 else (float("inf") if pos > 0 else 0.0)
    t_p = float(stats.ttest_1samp(rets, 0.0, alternative="greater").pvalue) if len(rets) > 2 else 1.0
    folds = {}
    for fid, s, e in FOLDS:
        fr = np.array([p["net"] for p in oos
                       if pd.Timestamp(s) <= p["start"] < pd.Timestamp(e)])
        folds[fid] = {"periods": int(len(fr)),
                      "compounded": float(np.prod(1.0 + fr) - 1.0) if len(fr) else 0.0}
    contrib_tot = {a: 0.0 for a in ASSETS}
    for p in oos:
        for a, c in p["contrib"].items():
            contrib_tot[a] += c
    pos_contrib = {a: c for a, c in contrib_tot.items() if c > 0}
    tot_pos = sum(pos_contrib.values())
    max_share = (max(pos_contrib.values()) / tot_pos) if tot_pos > 0 else 1.0
    is_rets = np.array([p["net"] for p in is_p], dtype=float)
    return {
        "oos_periods": int(len(rets)),
        "oos_compounded": float(np.prod(1.0 + rets) - 1.0) if len(rets) else 0.0,
        "oos_max_drawdown": dd,
        "oos_period_pf": pf,
        "oos_mean_period_return": float(rets.mean()) if len(rets) else 0.0,
        "t_stat_one_sided_p": t_p,
        "folds": folds,
        "folds_positive": int(sum(1 for f in folds.values() if f["compounded"] > 0)),
        "total_turnover_cost_frac": float(sum(p["cost"] for p in oos)),
        "contrib_by_asset": {a: float(c) for a, c in contrib_tot.items()},
        "max_asset_profit_share": float(max_share),
        "is_compounded": float(np.prod(1.0 + is_rets) - 1.0) if len(is_rets) else 0.0,
        "is_periods": int(len(is_rets)),
    }


def buy_hold(closes, asset, cost_mult=1.0):
    s = closes[asset]
    c0 = close_at(s, OOS_START)
    c1 = close_at(s, END)
    window = s[(s.index >= OOS_START) & (s.index <= END)]
    eq = window / window.iloc[0]
    dd = float((eq / eq.cummax() - 1.0).min())
    gross = c1[0] / c0[0] - 1.0
    net = (1.0 + gross) * (1.0 - RT_BPS[asset] * cost_mult / 10000.0) - 1.0
    return {"compounded_net": float(net), "max_drawdown_daily": dd}


def main():
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "workspace/str-rd2/cache2"
    closes, provenance = load_closes(cache)
    rows = []
    for L in LOOKBACKS:
        for k in KS:
            for cad in CADENCES:
                for mode in MODES:
                    periods = run_config(closes, L, k, cad, mode)
                    row = {"lookback_days": L, "top_k": k, "cadence": cad,
                           "mode": mode, **summarise(periods)}
                    rows.append((row, periods))
    out_rows = []
    for row, periods in rows:
        mech = (row["oos_compounded"] > 0 and row["oos_period_pf"] >= 1.2
                and row["folds_positive"] >= 4 and row["oos_max_drawdown"] >= -0.20
                and row["max_asset_profit_share"] <= 0.50)
        entry = {kk: vv for kk, vv in row.items()}
        entry["mechanical_bar"] = bool(mech)
        if mech:
            p2 = run_config(closes, row["lookback_days"], row["top_k"],
                            row["cadence"], row["mode"], cost_mult=2.0)
            s2 = summarise(p2)
            entry["x2_cost"] = {"oos_compounded": s2["oos_compounded"],
                                "oos_period_pf": s2["oos_period_pf"]}
        out_rows.append(entry)
    benchmarks = {a: buy_hold(closes, a) for a in ["BTCUSDT", "GOLD", "SPX"]}
    ew = {}
    for a in ASSETS:
        ew[a] = buy_hold(closes, a)
    ew_comp = float(np.mean([v["compounded_net"] for v in ew.values()]))
    benchmarks["EQUAL_WEIGHT_ALL7"] = {"compounded_net_mean_of_legs": ew_comp,
                                       "note": "mean of the 7 single-asset net buy-hold legs; drift ignored, context only"}
    print(json.dumps({"provenance": provenance, "rows": out_rows,
                      "benchmarks_oos": benchmarks}, indent=1))


if __name__ == "__main__":
    main()
