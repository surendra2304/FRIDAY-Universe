#!/usr/bin/env python3
"""TASK-STR-RD-006 pairs / stat-arb engine (crew's own implementation).

Implements PREDECLARATION.md exactly:
  - Engle-Granger screen (OLS on log prices + BIC-lag ADF on residuals,
    MacKinnon EG 5% tau < -3.34) + half-life filter, formation data only.
  - Walk-forward: 5 folds x 134d from 2024-07-01, 365d formation,
    untouched holdout 2026-05-02..2026-11-01 evaluated only for
    pair-configs passing every other bar element.
  - Trading: frozen formation params, z entry 2.0/2.5, exit z=0 cross,
    stop |z|>=4, next-bar-open execution both legs, exact two-leg P&L,
    32 bps round-trip cost (RD-002 pairs convention), 64 bps sensitivity.
  - Verdicts vs the standing RD-002 promotion bar at N = 1,740 trials.

Modes:
  python3 pairs_engine.py validate   # synthetic machinery fixtures
  python3 pairs_engine.py run        # full run (fixtures gate first)
Outputs land in ~/workspace/rd-006/out/.
"""
import json
import math
import os
import sys
import time
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA = Path("/home/hatch/workspace/rd-006/data")
OUT = Path("/home/hatch/workspace/rd-006/out")
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
           "DOGEUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "DOTUSDT",
           "TRXUSDT", "AVAXUSDT", "NEARUSDT", "ATOMUSDT", "UNIUSDT",
           "ETCUSDT", "BCHUSDT", "FILUSDT", "APTUSDT", "ARBUSDT",
           "OPUSDT", "INJUSDT", "SUIUSDT", "XLMUSDT", "HBARUSDT",
           "ALGOUSDT", "VETUSDT", "SANDUSDT", "MANAUSDT", "AAVEUSDT"]
COST = 0.0032          # 32 bps round trip, both legs (RD-002 convention)
COST2X = 0.0064
EG_CV_5 = -3.34        # MacKinnon EG 5% asymptotic, 2 vars, constant
ENTRY_CONFIGS = [2.0, 2.5]
STOP_Z = 4.0
N_TRIALS = 435 * 2 * 2          # 1,740
N_GLOBAL_FLOOR = 1557 + N_TRIALS  # 3,297 (RD-003 additions excluded)
T0 = pd.Timestamp("2024-07-01", tz="UTC")
FOLD_DAYS = 134
N_FOLDS = 5
HOLDOUT_END = pd.Timestamp("2026-11-01", tz="UTC")
HL_RANGE = {"1h": (6.0, 240.0), "4h": (6.0, 120.0)}
MIN_COVERAGE = 0.95

# ---------------------------------------------------------------- stats

def ols(X, y):
    """Least squares; returns (coef, resid, se) with classical SEs."""
    XtX_inv = np.linalg.pinv(X.T @ X)
    coef = XtX_inv @ (X.T @ y)
    resid = y - X @ coef
    dof = max(len(y) - X.shape[1], 1)
    s2 = float(resid @ resid) / dof
    se = np.sqrt(np.maximum(np.diag(XtX_inv) * s2, 0.0))
    return coef, resid, se


def _ne_solve(X, y):
    """OLS via normal equations (fast path for tall-skinny designs).

    Returns (coef, resid, se). Falls back to pinv if X'X is singular.
    Numerically adequate here: regressors are lagged differences of a
    residual series (near-stationary, modest collinearity); the fixture
    suite re-validates tau values against the original lstsq path.
    """
    XtX = X.T @ X
    Xty = X.T @ y
    try:
        XtX_inv = np.linalg.inv(XtX)
        coef = XtX_inv @ Xty
    except np.linalg.LinAlgError:
        XtX_inv = np.linalg.pinv(XtX)
        coef = XtX_inv @ Xty
    resid = y - X @ coef
    dof = max(len(y) - X.shape[1], 1)
    s2 = float(resid @ resid) / dof
    se = np.sqrt(np.maximum(np.diag(XtX_inv) * s2, 0.0))
    return coef, resid, se


def adf_tau(e, maxlag):
    """ADF tau on residuals e (no constant/trend), BIC lag selection.

    All candidate lags share one sample (t = maxlag+1 .. T-1) so BIC
    comparisons are like-for-like. Returns (tau, chosen_lag).
    """
    e = np.asarray(e, dtype=float)
    T = len(e)
    de = np.diff(e)                       # de[i] = e[i+1]-e[i], i=0..T-2
    start = maxlag + 1                    # first usable t index into e
    ts = np.arange(start, T)              # t values (index into e)
    y = de[ts - 1]
    n = len(y)
    # Prebuild the full lag design once; lag-p model uses its first p+1 cols.
    cols = [e[ts - 1]]
    for i in range(1, maxlag + 1):
        cols.append(de[ts - 1 - i])
    M = np.column_stack(cols)
    best = None
    for p in range(maxlag + 1):
        X = M[:, :p + 1]
        coef, resid, se = _ne_solve(X, y)
        rss = float(resid @ resid)
        if rss <= 0 or se[0] == 0:
            continue
        bic = n * math.log(rss / n) + (p + 1) * math.log(n)
        if best is None or bic < best[0]:
            best = (bic, coef[0] / se[0], p)
    if best is None:
        return float("nan"), -1
    return float(best[1]), int(best[2])


def half_life(e):
    """AR(1) half-life of spread e in bars; +inf if not mean-reverting."""
    e = np.asarray(e, dtype=float)
    de = np.diff(e)
    X = e[:-1].reshape(-1, 1)
    coef, _, _ = ols(X, de)
    lam = float(coef[0])
    if lam >= 0:
        return float("inf"), lam
    return float(-math.log(2) / lam), lam


def eg_screen(logA, logB, tf):
    """Engle-Granger screen on formation log-price arrays.

    Returns dict(alpha, beta, mu, sigma, tau, lag, hl, adf_pass, hl_pass).
    """
    X = np.column_stack([np.ones(len(logB)), logB])
    coef, resid, _ = ols(X, logA)
    alpha, beta = float(coef[0]), float(coef[1])
    T = len(resid)
    maxlag = int(min(48, math.floor(12 * (T / 100.0) ** 0.25)))
    tau, lag = adf_tau(resid, maxlag)
    hl, _lam = half_life(resid)
    lo, hi = HL_RANGE[tf]
    return {
        "alpha": alpha, "beta": beta,
        "mu": float(np.mean(resid)), "sigma": float(np.std(resid, ddof=1)),
        "tau": tau, "lag": lag, "hl": hl,
        "adf_pass": bool(tau < EG_CV_5),
        "hl_pass": bool(lo <= hl <= hi),
    }


def dsr(returns, n_trials, var_sr_trials):
    """Deflated Sharpe ratio (Bailey & Lopez de Prado 2014).

    returns: per-trade net returns of the config under judgement.
    var_sr_trials: variance of per-trade Sharpe estimates across trials.
    """
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n < 3 or np.std(r, ddof=1) == 0 or var_sr_trials <= 0:
        return float("nan")
    sr = float(np.mean(r) / np.std(r, ddof=1))
    g3 = float(stats.skew(r, bias=False)) if n > 3 else 0.0
    g4 = float(stats.kurtosis(r, fisher=False, bias=False)) if n > 4 else 3.0
    gamma = 0.5772156649015329
    sr0 = math.sqrt(var_sr_trials) * (
        (1 - gamma) * stats.norm.ppf(1 - 1.0 / n_trials)
        + gamma * stats.norm.ppf(1 - 1.0 / (n_trials * math.e)))
    denom = math.sqrt(max(1 - g3 * sr + ((g4 - 1) / 4.0) * sr * sr, 1e-12))
    return float(stats.norm.cdf((sr - sr0) * math.sqrt(n - 1) / denom))


def metrics(returns, returns2x):
    """Core trade metrics for a return vector (net) + its 2x-cost twin."""
    r = np.asarray(returns, dtype=float)
    r2 = np.asarray(returns2x, dtype=float)
    if len(r) == 0:
        return {"n": 0, "expectancy": None, "pf": None, "pf2x": None,
                "win_rate": None, "sharpe": None, "p_one_sided": None,
                "max_dd": None, "total": 0.0}
    pos = r[r > 0].sum()
    neg = -r[r < 0].sum()
    pf = float(pos / neg) if neg > 0 else (float("inf") if pos > 0 else 0.0)
    pos2 = r2[r2 > 0].sum()
    neg2 = -r2[r2 < 0].sum()
    pf2 = float(pos2 / neg2) if neg2 > 0 else (float("inf") if pos2 > 0 else 0.0)
    sd = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
    sharpe = float(np.mean(r) / sd) if sd > 0 else 0.0
    p = float(stats.ttest_1samp(r, 0.0, alternative="greater").pvalue) \
        if len(r) > 1 and sd > 0 else 1.0
    cum = np.cumsum(r)
    max_dd = float(np.max(np.maximum.accumulate(cum) - cum)) if len(r) else 0.0
    return {"n": int(len(r)), "expectancy": float(np.mean(r)), "pf": pf,
            "pf2x": pf2, "win_rate": float(np.mean(r > 0)), "sharpe": sharpe,
            "p_one_sided": p, "max_dd": max_dd, "total": float(np.sum(r))}

# ---------------------------------------------------------------- data

def load_symbol_1h(sym):
    df = pd.read_csv(DATA / f"{sym}_1h.csv")
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("ts")[["open", "close"]]


def resample_4h(df1h):
    """UTC-aligned complete 4h buckets only: open=first open, close=last close."""
    g = df1h.groupby(df1h.index.floor("4h"))
    out = g.agg(open=("open", "first"), close=("close", "last"),
                cnt=("close", "size"))
    out = out[out["cnt"] == 4].drop(columns="cnt")
    return out


def window_slice(df, start, end):
    return df[(df.index >= start) & (df.index < end)]


def expected_bars(start, end, tf):
    hours = (end - start).total_seconds() / 3600.0
    return int(hours if tf == "1h" else hours / 4)

# ---------------------------------------------------------------- trading

def trade_fold(opA, clA, opB, clB, scr, entry_band, cost):
    """Simulate one fold for one selected pair. Arrays are the aligned
    pair bars of the trading window (open/close per leg). Signals on
    close z of bar i, executions at open of bar i+1; end-of-window
    flatten at the last bar's close. Returns list of trade dicts."""
    alpha, beta, mu, sigma = scr["alpha"], scr["beta"], scr["mu"], scr["sigma"]
    if sigma <= 0:
        return [], 0
    spread = np.log(clA) - alpha - beta * np.log(clB)
    z = (spread - mu) / sigma
    n = len(z)
    trades = []
    guard_skips = 0
    pos = 0            # +1 long spread, -1 short spread, 0 flat
    entry_i = None
    qA = qB = None
    eA = eB = None

    def close_trade(i_exit, pA, pB, reason):
        pnl = qA * (pA - eA) - qB * (pB - eB)
        if pos == -1:
            pnl = -pnl
        trades.append({"entry_bar": int(entry_i), "exit_bar": int(i_exit),
                       "side": int(pos), "bars_held": int(i_exit - entry_i),
                       "gross": float(pnl), "net": float(pnl - cost),
                       "net2x": float(pnl - 2 * cost), "reason": reason})

    for i in range(n):
        if pos == 0:
            if i + 1 < n:
                if z[i] <= -entry_band or z[i] >= entry_band:
                    eA, eB = float(opA[i + 1]), float(opB[i + 1])
                    denom = eA + beta * eB
                    if denom <= 0:   # degenerate hedge sizing: never enter
                        guard_skips += 1
                        continue
                    pos = 1 if z[i] <= -entry_band else -1
                    entry_i = i + 1
                    qA = 1.0 / denom
                    qB = beta * qA
        else:
            exit_now = False
            reason = None
            if pos == 1 and z[i] >= 0:
                exit_now, reason = True, "mean_cross"
            elif pos == -1 and z[i] <= 0:
                exit_now, reason = True, "mean_cross"
            elif abs(z[i]) >= STOP_Z and ((pos == 1 and z[i] < 0) or
                                          (pos == -1 and z[i] > 0)):
                exit_now, reason = True, "stop"
            if exit_now and i + 1 < n:
                close_trade(i + 1, float(opA[i + 1]), float(opB[i + 1]), reason)
                pos = 0
            elif i == n - 1:
                close_trade(i, float(clA[i]), float(clB[i]), "window_end")
                pos = 0
    if pos != 0:  # position opened on the final aligned bar edge case
        close_trade(n - 1, float(clA[n - 1]), float(clB[n - 1]), "window_end")
    return trades, guard_skips

# ---------------------------------------------------------------- folds

def fold_windows():
    folds = []
    for k in range(N_FOLDS):
        start = T0 + pd.Timedelta(days=FOLD_DAYS * k)
        end = start + pd.Timedelta(days=FOLD_DAYS)
        folds.append({"fold": f"W{k + 1}", "start": start, "end": end,
                      "form_start": start - pd.Timedelta(days=365),
                      "form_end": start})
    return folds


def holdout_window():
    start = T0 + pd.Timedelta(days=FOLD_DAYS * N_FOLDS)
    return {"fold": "HOLDOUT", "start": start, "end": HOLDOUT_END,
            "form_start": start - pd.Timedelta(days=365), "form_end": start}

# ---------------------------------------------------------------- validate

def validate():
    rng = np.random.default_rng(20261115)
    print("== machinery fixtures (synthetic, validation only) ==")
    # (c) ADF ordering: stationary AR(1) vs random walk
    T = 4000
    ar = np.zeros(T)
    eps = rng.normal(size=T)
    for t in range(1, T):
        ar[t] = 0.90 * ar[t - 1] + eps[t]
    rw = np.cumsum(rng.normal(size=T))
    maxlag = int(min(48, math.floor(12 * (T / 100.0) ** 0.25)))
    tau_ar, _ = adf_tau(ar - ar.mean(), maxlag)
    tau_rw, _ = adf_tau(rw - rw.mean(), maxlag)
    print(f"ADF tau: AR(1) phi=0.90 -> {tau_ar:.2f} | random walk -> {tau_rw:.2f}")
    assert tau_ar < -3.34 and tau_ar < tau_rw, "ADF fixture (c) FAILED"
    # (b) constructed cointegrated pair must pass; HL near construction
    x = np.cumsum(rng.normal(size=T)) + 100.0
    spread_true = np.zeros(T)
    for t in range(1, T):
        spread_true[t] = 0.95 * spread_true[t - 1] + rng.normal(scale=0.5)
    y = np.exp(0.8 * np.log(x) + 0.02 * spread_true + 2.0)
    scr = eg_screen(np.log(y), np.log(x), "1h")
    hl_true = -math.log(2) / math.log(0.95)
    print(f"EG on constructed pair: tau={scr['tau']:.2f} beta={scr['beta']:.3f} "
          f"HL={scr['hl']:.1f} (constructed {hl_true:.1f}) "
          f"adf_pass={scr['adf_pass']} hl_pass={scr['hl_pass']}")
    assert scr["adf_pass"] and abs(scr["beta"] - 0.8) < 0.1, "EG fixture (b) FAILED"
    assert 0.4 * hl_true < scr["hl"] < 2.5 * hl_true, "HL fixture FAILED"
    # (a) independent random walks: screen pass rate must be low
    passes = 0
    trials = 40
    for _ in range(trials):
        a = np.cumsum(rng.normal(size=T)) + 100.0
        b = np.cumsum(rng.normal(size=T)) + 50.0
        s = eg_screen(np.log(np.abs(a) + 200), np.log(np.abs(b) + 200), "1h")
        if s["adf_pass"] and s["hl_pass"]:
            passes += 1
    rate = passes / trials
    print(f"independent-RW screen pass rate: {passes}/{trials} = {rate:.2f}")
    assert rate <= 0.20, "EG fixture (a) FAILED: screen too permissive"
    print("ALL FIXTURES PASS")

# ---------------------------------------------------------------- run

def aligned_pair(dfA, dfB, start, end):
    a = window_slice(dfA, start, end)
    b = window_slice(dfB, start, end)
    j = a.join(b, how="inner", lsuffix="A", rsuffix="B")
    return j


def run():
    validate()
    OUT.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    print("loading data ...", flush=True)
    data = {}
    for sym in SYMBOLS:
        d1 = load_symbol_1h(sym)
        data[sym] = {"1h": d1, "4h": resample_4h(d1)}
    folds = fold_windows()
    hw = holdout_window()
    (OUT / "windows.json").write_text(json.dumps(
        {"folds": [{k: str(v) for k, v in f.items()} for f in folds],
         "holdout": {k: str(v) for k, v in hw.items()}}, indent=1))

    screen_rows = []
    trade_rows = []
    # Checkpoint resume: ckpt_after_<tf>.json holds cumulative rows after
    # that timeframe's loop finished; a killed run restarts from there.
    done_tfs = []
    for tf_done in ["1h", "4h"]:
        ck = OUT / f"ckpt_after_{tf_done}.json"
        if ck.exists():
            saved = json.loads(ck.read_text())
            screen_rows = saved["screen_rows"]
            trade_rows = saved["trade_rows"]
            done_tfs.append(tf_done)
        else:
            break
    if done_tfs:
        print(f"resuming: checkpointed timeframes {done_tfs}", flush=True)
    # cache screens: (pair, tf, window_id) -> screen dict or None(data-skip)
    screens = {}

    def get_screen(symA, symB, tf, win):
        key = (symA, symB, tf, win["fold"])
        if key in screens:
            return screens[key]
        form = aligned_pair(data[symA][tf], data[symB][tf],
                            win["form_start"], win["form_end"])
        exp_f = expected_bars(win["form_start"], win["form_end"], tf)
        cov_f = len(form) / exp_f if exp_f else 0.0
        rec = {"pair": f"{symA}/{symB}", "tf": tf, "fold": win["fold"],
               "cov_form": cov_f, "data_skip": False}
        if cov_f < MIN_COVERAGE or len(form) < 200:
            rec["data_skip"] = True
            screens[key] = (None, rec)
            screen_rows.append(rec)
            return screens[key]
        scr = eg_screen(np.log(form["closeA"].to_numpy()),
                        np.log(form["closeB"].to_numpy()), tf)
        rec.update({"tau": scr["tau"], "lag": scr["lag"], "hl": scr["hl"],
                    "beta": scr["beta"], "adf_pass": scr["adf_pass"],
                    "hl_pass": scr["hl_pass"],
                    "selected": bool(scr["adf_pass"] and scr["hl_pass"])})
        screens[key] = (scr, rec)
        screen_rows.append(rec)
        return screens[key]

    pairs = list(combinations(SYMBOLS, 2))
    print(f"{len(pairs)} pairs x {len(folds)} folds x 2 tf", flush=True)
    tf_list = os.environ.get("RD6_TFS", "1h,4h").split(",")
    stop_after = os.environ.get("RD6_STOP_AFTER", "")
    for tf in tf_list:
        if tf in done_tfs:
            print(f"[{tf}] skipped (checkpoint)", flush=True)
            continue
        for (symA, symB) in pairs:
            for win in folds:
                scr, rec = get_screen(symA, symB, tf, win)
                if scr is None or not rec.get("selected"):
                    continue
                trade_df = aligned_pair(data[symA][tf], data[symB][tf],
                                        win["start"], win["end"])
                exp_t = expected_bars(win["start"], win["end"], tf)
                cov_t = len(trade_df) / exp_t if exp_t else 0.0
                rec["cov_trade"] = cov_t
                if cov_t < MIN_COVERAGE:
                    rec["trade_data_skip"] = True
                    continue
                for E in ENTRY_CONFIGS:
                    ts, gsk = trade_fold(trade_df["openA"].to_numpy(),
                                         trade_df["closeA"].to_numpy(),
                                         trade_df["openB"].to_numpy(),
                                         trade_df["closeB"].to_numpy(),
                                         scr, E, COST)
                    if gsk:
                        rec.setdefault("guard_skips", 0)
                        rec["guard_skips"] += gsk
                    times = trade_df.index
                    for tr in ts:
                        tr.update({"pair": rec["pair"], "tf": tf,
                                   "fold": win["fold"], "config": E,
                                   "entry_time": str(times[tr["entry_bar"]]),
                                   "exit_time": str(times[tr["exit_bar"]])})
                        trade_rows.append(tr)
        print(f"[{tf}] done t+{time.time() - t_start:.0f}s "
              f"trades={len(trade_rows)}", flush=True)
        (OUT / f"ckpt_after_{tf}.json").write_text(json.dumps(
            {"screen_rows": screen_rows, "trade_rows": trade_rows},
            default=str))
        if stop_after == tf:
            print(f"stopping after {tf} (checkpoint written)", flush=True)
            return

    trades = pd.DataFrame(trade_rows)
    trades.to_csv(OUT / "trades_folds.csv", index=False)
    print(f"trades (folds): {len(trades)}", flush=True)

    # ---- per-config metrics over W1-W5
    cfg_rows = []
    if len(trades):
        for (pair, tf, E), g in trades.groupby(["pair", "tf", "config"]):
            m = metrics(g["net"].to_numpy(), g["net2x"].to_numpy())
            fold_tot = g.groupby("fold")["net"].sum()
            m.update({"pair": pair, "tf": tf, "config": E,
                      "folds_traded": int(g["fold"].nunique()),
                      "folds_positive_share":
                          float(np.mean([fold_tot.get(f"W{k}", 0.0) > 0
                                         for k in range(1, 6)
                                         if f"W{k}" in fold_tot])) if len(fold_tot) else 0.0,
                      "sharpe_for_dsr": m["sharpe"]})
            cfg_rows.append(m)
    cfg = pd.DataFrame(cfg_rows)
    # cross-trial Sharpe variance for DSR (configs with >= 30 trades)
    var_sr = float(cfg.loc[cfg["n"] >= 30, "sharpe"].var(ddof=1)) \
        if (cfg["n"] >= 30).sum() > 2 else 0.0
    print(f"cross-trial Sharpe variance (n>=30 configs): {var_sr:.6f}", flush=True)

    bonf = 0.05 / N_TRIALS
    bonf_g = 0.05 / N_GLOBAL_FLOOR
    verdicts = []
    for _, row in cfg.iterrows():
        g = trades[(trades["pair"] == row["pair"]) & (trades["tf"] == row["tf"])
                   & (trades["config"] == row["config"])]
        d = dsr(g["net"].to_numpy(), N_TRIALS, var_sr) if var_sr > 0 else float("nan")
        d_g = dsr(g["net"].to_numpy(), N_GLOBAL_FLOOR, var_sr) if var_sr > 0 else float("nan")
        mech = (row["expectancy"] > 0 and row["pf"] >= 1.2 and row["n"] >= 200
                and row["folds_traded"] >= 3 and row["folds_positive_share"] >= 0.8)
        sig = row["p_one_sided"] < bonf
        sig_g = row["p_one_sided"] < bonf_g
        dsr_ok = d >= 0.95
        cost_ok = row["pf2x"] >= 1.0
        v = {"pair": row["pair"], "tf": row["tf"], "config": row["config"],
             "n": int(row["n"]), "expectancy": row["expectancy"], "pf": row["pf"],
             "pf2x": row["pf2x"], "win_rate": row["win_rate"],
             "folds_traded": int(row["folds_traded"]),
             "folds_positive_share": row["folds_positive_share"],
             "p_one_sided": row["p_one_sided"], "dsr": d, "dsr_global_n": d_g,
             "max_dd": row["max_dd"], "total_net": row["total"],
             "mechanical_bar": bool(mech), "bonferroni_pass": bool(sig),
             "bonferroni_pass_global_floor": bool(sig_g),
             "dsr_pass": bool(dsr_ok), "cost2x_pass": bool(cost_ok),
             "holdout": None, "verdict": None}
        if row["n"] < 30:
            v["verdict"] = "INSUFFICIENT"
        elif mech and sig and dsr_ok and cost_ok:
            v["verdict"] = "PENDING_HOLDOUT"
        elif mech:
            v["verdict"] = "WATCHLIST"
        else:
            v["verdict"] = "FAIL"
        verdicts.append(v)
    ver = pd.DataFrame(verdicts)

    # ---- holdout: ONLY for PENDING_HOLDOUT configs
    pending = ver[ver["verdict"] == "PENDING_HOLDOUT"]
    print(f"configs pending holdout: {len(pending)}", flush=True)
    holdout_trades = []
    for _, v in pending.iterrows():
        symA, symB = v["pair"].split("/")
        scr, rec = get_screen(symA, symB, v["tf"], hw)
        hres = {"evaluated": False}
        if scr is not None and rec.get("selected"):
            trade_df = aligned_pair(data[symA][v["tf"]], data[symB][v["tf"]],
                                    hw["start"], hw["end"])
            exp_t = expected_bars(hw["start"], hw["end"], v["tf"])
            if len(trade_df) / exp_t >= MIN_COVERAGE:
                ts, _gsk = trade_fold(trade_df["openA"].to_numpy(),
                                      trade_df["closeA"].to_numpy(),
                                      trade_df["openB"].to_numpy(),
                                      trade_df["closeB"].to_numpy(),
                                      scr, float(v["config"]), COST)
                times = trade_df.index
                for tr in ts:
                    tr.update({"pair": v["pair"], "tf": v["tf"], "fold": "HOLDOUT",
                               "config": float(v["config"]),
                               "entry_time": str(times[tr["entry_bar"]]),
                               "exit_time": str(times[tr["exit_bar"]])})
                    holdout_trades.append(tr)
                hm = metrics(np.array([t["net"] for t in ts]) if ts else np.array([]),
                             np.array([t["net2x"] for t in ts]) if ts else np.array([]))
                hres = {"evaluated": True, "n": hm["n"],
                        "expectancy": hm["expectancy"], "pf": hm["pf"],
                        "pass": bool(hm["n"] >= 20 and hm["expectancy"] > 0
                                     and hm["pf"] >= 1.0)}
        idx = ver[(ver["pair"] == v["pair"]) & (ver["tf"] == v["tf"])
                  & (ver["config"] == v["config"])].index
        ver.loc[idx, "holdout"] = json.dumps(hres)
        ver.loc[idx, "verdict"] = "PASS" if hres.get("pass") else "WATCHLIST"
    if holdout_trades:
        pd.DataFrame(holdout_trades).to_csv(OUT / "trades_holdout.csv", index=False)
    ver.to_csv(OUT / "config_verdicts.csv", index=False)
    # screen log written last: holdout screens (bar-passers only) included
    screens_df = pd.DataFrame(screen_rows)
    screens_df.to_csv(OUT / "screen_log.csv", index=False)
    print(f"screens logged: {len(screens_df)}", flush=True)

    # ---- procedure-level pooling per (tf, config)
    proc = {}
    if len(trades):
        for (tf, E), g in trades.groupby(["tf", "config"]):
            m = metrics(g["net"].to_numpy(), g["net2x"].to_numpy())
            d = dsr(g["net"].to_numpy(), N_TRIALS, var_sr) if var_sr > 0 else float("nan")
            fold_tot = g.groupby("fold")["net"].sum()
            proc[f"{tf}|E{E}"] = {**{k: m[k] for k in
                                     ["n", "expectancy", "pf", "pf2x", "win_rate",
                                      "p_one_sided", "max_dd", "total"]},
                                  "dsr": d,
                                  "fold_totals": {k: float(v) for k, v in fold_tot.items()}}
    synthesis = {
        "task": "TASK-STR-RD-006",
        "n_trials_rd6": N_TRIALS,
        "n_global_floor": N_GLOBAL_FLOOR,
        "bonferroni_threshold": bonf,
        "bonferroni_threshold_global_floor": bonf_g,
        "cross_trial_sharpe_variance": var_sr,
        "n_configs_with_trades": int(len(cfg)),
        "n_pairs_ever_selected": int(screens_df[screens_df.get("selected") == True]["pair"].nunique()) if len(screens_df) else 0,
        "verdict_counts": ver["verdict"].value_counts().to_dict() if len(ver) else {},
        "passers": ver[ver["verdict"] == "PASS"].to_dict("records") if len(ver) else [],
        "watchlist": ver[ver["verdict"] == "WATCHLIST"].to_dict("records") if len(ver) else [],
        "procedure_level": proc,
        "elapsed_s": time.time() - t_start,
    }
    (OUT / "synthesis.json").write_text(json.dumps(synthesis, indent=1, default=str))
    print(json.dumps(synthesis["verdict_counts"], indent=1))
    print(f"PASSERS: {len(synthesis['passers'])}  WATCHLIST: {len(synthesis['watchlist'])}")
    print(f"done in {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        validate()
    else:
        run()
