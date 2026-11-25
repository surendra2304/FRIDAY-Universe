"""Backtest runner for TASK-STR-068 — z-score pairs rule under the frozen bar.

Runs the four-block rule from Stratex/research/pairs_trading.py as a
tradeable strategy and judges it against the frozen admission bar in
Stratex/self_experiments/bounds.py (values copied here, never edited):

  PROVEN (full bar): expectancy > 0, PF >= 1.2, >= 200 OOS trades,
    >= 4/5 positive folds, Bonferroni one-sided p < 0.05 / N_global,
    pooled holdout expectancy > 0.
  FORWARD_TEST tier: expectancy > 0, PF >= 1.05, >= 200 OOS trades.
  Lane terms: 0.1% risk per trade, 2% heat cap.
  Kill: expectancy < 0 or PF < 1.0 after >= 50 trades, or drawdown > 5%.

Two legs, both out-of-sample:
  1. SIM: five folds of the post's own simulated pair (seeds 11-15; seed 11
     is the post's setup). Fit on the first 750 days, trade the last 750.
  2. REAL: repo demo fixtures (Stratex/tests/fixtures/fwd002) — BTC/SOL and
     EURUSD/USDJPY daily closes, first half fit / second half trade. A pair
     that fails the Engle-Granger screen in either direction is reported as
     SCREEN FAIL and produces no trades.

Method (stated so the numbers can be reproduced and challenged):
  - Spread = ly - a - beta*lx with (a, beta) from OLS on the fit window.
  - Z-score = rolling 60-day mean/std of the spread, computed on past data
    only (no lookahead); trading starts after a 60-day OOS warm-up.
  - Rule = pair_position_with_stop (enter |z| > 2, exit at |z| <= 0.5,
    stop at |z| >= 4), exactly as transcribed from the post.
  - Sizing: each trade risks exactly the lane 0.1% of equity. The adverse
    excursion from entry (|z| = 2) to stop (|z| = 4) is 2 * sigma_entry, so
    size = 0.001 / (2 * sigma_entry) spread-units per unit of equity.
    One pair is traded at a time, so heat is 0.1% (under the 2% cap).
  - A trade closes when the position returns to 0 (exit, stop, or the end
    of the OOS window, marked forced-close). PnL is in equity-fraction
    units (1.0 = 100% of venue equity at the start).
  - Bonferroni family: the 5 sim folds (N_global for the wider programme is
    not known here, so the correction uses the fold family and says so).

Assumptions / limits (a pass here is NOT a pass with costs):
  - Costs and borrow are ZERO — no venue cost schedule exists for the
    simulated pair or the fixtures, so the result is gross of costs.
  - Single pair per leg; one simulated path per fold; no slippage.
  - The creator's simulated numbers remain unproven claims; this runner
    measures the transcribed mechanics only.

Writes nothing; prints one JSON verdict object to stdout. Demo only.
No live trading.
"""

import csv
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from research.pairs_trading import (  # noqa: E402
    EG_CRITICAL_5PCT,
    engle_granger,
    kalman_beta,
    ou_halflife,
    pair_position_with_stop,
)

# Frozen bar (Stratex/self_experiments/bounds.py) — copied values, read-only.
FULL_BAR_PF = 1.2
FORWARD_PF = 1.05
MIN_OOS_TRADES = 200
MIN_POS_FOLDS = 4
FOLDS_TOTAL = 5
LANE_RISK = 0.001  # 0.1% of equity per trade
KILL_DD = 0.05     # 5% of venue equity
BONFERRONI_ALPHA = 0.05

ROLL = 60
Z_IN, Z_OUT, Z_STOP = 2.0, 0.5, 4.0

N_TRAIN = 750
N_TOTAL = 1500
TRUE_BETA = 1.5
TRUE_HALFLIFE = 10.0
SIM_SEEDS = [11, 12, 13, 14, 15]


# ---------------------------------------------------------------------------
# One-sided t-test p-value (mean > 0) via the regularised incomplete beta.
# stdlib only — no scipy dependency.
# ---------------------------------------------------------------------------
def _betacf(a, b, x):
    maxit, eps, fpmin = 200, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log(1 - x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_pvalue_one_sided(trades):
    """One-sided p-value for H1: mean(trade PnL) > 0. NaN when n < 2."""
    n = len(trades)
    if n < 2:
        return float("nan")
    mean = float(np.mean(trades))
    sd = float(np.std(trades, ddof=1))
    if sd == 0:
        return 0.0 if mean > 0 else 1.0
    t = mean / (sd / math.sqrt(n))
    df = n - 1
    x = df / (df + t * t)
    ib = _betai(df / 2.0, 0.5, x)
    return 0.5 * ib if t > 0 else 1.0 - 0.5 * ib


# ---------------------------------------------------------------------------
# Simulated pair (identical construction to the unit tests).
# ---------------------------------------------------------------------------
def sim_pair(seed):
    rng = np.random.default_rng(seed)
    phi = 2.0 ** (-1.0 / TRUE_HALFLIFE)
    sigma_spread = 0.02
    sigma_e = sigma_spread * math.sqrt(1 - phi**2)
    x = np.cumsum(rng.normal(0, 0.03, N_TOTAL))
    s = np.zeros(N_TOTAL)
    for t in range(1, N_TOTAL):
        s[t] = phi * s[t - 1] + rng.normal(0, sigma_e)
    beta = np.full(N_TOTAL, TRUE_BETA)
    beta[N_TRAIN:] = TRUE_BETA + 0.4 * np.linspace(0, 1, N_TOTAL - N_TRAIN)
    y = 0.1 + beta * x + s
    return x, y


# ---------------------------------------------------------------------------
# Real-pair loader: repo demo fixtures, ts,open,high,low,close,volume.
# ---------------------------------------------------------------------------
def load_closes(path):
    closes, stamps = [], []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            closes.append(float(row["close"]))
            stamps.append(row["ts"])
    return np.asarray(closes), stamps


def aligned_log_pair(path_a, path_b):
    ca, sa = load_closes(path_a)
    cb, sb = load_closes(path_b)
    idx_b = {s: i for i, s in enumerate(sb)}
    common = [(i, idx_b[s]) for i, s in enumerate(sa) if s in idx_b]
    if len(common) < 100:
        return None, None, len(common)
    ia = np.array([i for i, _ in common])
    ib = np.array([j for _, j in common])
    return np.log(ca[ia]), np.log(cb[ib]), len(common)


# ---------------------------------------------------------------------------
# One fit/trade run of the rule.
# Returns (diag, trades, equity_curve). trades are per-trade PnL in equity
# fraction; equity_curve starts at 1.0 and is marked daily.
# ---------------------------------------------------------------------------
def run_rule(lx, ly, n_train, label):
    lx = np.asarray(lx, dtype=float)
    ly = np.asarray(ly, dtype=float)
    diag = {"label": label, "n_total": int(lx.size), "n_train": int(n_train)}
    beta_hat, adf_xy = engle_granger(lx[:n_train], ly[:n_train])
    _, adf_yx = engle_granger(ly[:n_train], lx[:n_train])
    a_fit = float(np.mean(ly[:n_train] - beta_hat * lx[:n_train]))
    spread_train = ly[:n_train] - a_fit - beta_hat * lx[:n_train]
    hl = ou_halflife(spread_train)
    resid_train = ly[:n_train] - 0.1 - beta_hat * lx[:n_train]
    r_var = float(np.var(resid_train))
    q_var = (0.4**2 / max(1, lx.size - n_train)) if lx.size > n_train else 0.0
    th = kalman_beta(lx, ly, q_var, r_var)
    diag.update({
        "beta_hat": round(float(beta_hat), 4),
        "adf_xy": round(float(adf_xy), 2),
        "adf_yx": round(float(adf_yx), 2),
        "eg_screen_pass": bool(adf_xy < EG_CRITICAL_5PCT and adf_yx < EG_CRITICAL_5PCT),
        "half_life": None if (hl is None or math.isnan(hl)) else round(float(hl), 2),
        "kalman_beta_end": round(float(th[1]), 4),
    })
    if not diag["eg_screen_pass"]:
        diag["outcome"] = "SCREEN FAIL — no trades"
        return diag, [], [1.0]
    if hl is None or math.isnan(hl):
        diag["outcome"] = "NO HALF-LIFE — no trades"
        return diag, [], [1.0]

    spread = ly - a_fit - beta_hat * lx
    oos = spread[n_train:]
    trades = []
    equity = [1.0]
    pos = 0
    size = 0.0
    trade_pnl = 0.0
    forced_closes = 0
    for i in range(1, len(oos)):
        window = oos[max(0, i - ROLL):i]
        if len(window) < ROLL:
            equity.append(equity[-1])
            continue
        mu = float(np.mean(window))
        sigma = float(np.std(window))
        if sigma <= 0:
            equity.append(equity[-1])
            continue
        z = (oos[i] - mu) / sigma
        d = oos[i] - oos[i - 1]
        daily = pos * d * size  # position held into today, sized at entry
        equity.append(equity[-1] + daily)
        if pos != 0:
            trade_pnl += daily
        new_pos = pair_position_with_stop(z, pos, z_in=Z_IN, z_out=Z_OUT, z_stop=Z_STOP)
        if pos != 0 and new_pos == 0:
            trades.append(trade_pnl)
            trade_pnl = 0.0
            size = 0.0
        elif pos == 0 and new_pos != 0:
            size = LANE_RISK / ((Z_STOP - Z_IN) * sigma)
        pos = new_pos
    if pos != 0:
        trades.append(trade_pnl)
        forced_closes += 1
    diag["outcome"] = "TRADED"
    diag["forced_closes"] = forced_closes
    return diag, trades, equity


def max_dd_pct(equity_curve):
    peak = equity_curve[0]
    worst = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return round(worst * 100, 3)


def summarise(trades, equity_curve):
    trades = [float(t) for t in trades]
    n = len(trades)
    if n == 0:
        return {"n_trades": 0, "wins": 0, "losses": 0, "expectancy": None,
                "pf": None, "p_one_sided": None,
                "max_dd_pct": max_dd_pct(equity_curve)}
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    if gross_loss == 0 and gross_win > 0:
        pf = "inf"
    elif gross_loss > 0:
        pf = round(gross_win / gross_loss, 3)
    else:
        pf = None
    p = t_pvalue_one_sided(trades)
    return {
        "n_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "expectancy": round(float(np.mean(trades)), 6),
        "pf": pf,
        "p_one_sided": None if math.isnan(p) else round(float(p), 4),
        "max_dd_pct": max_dd_pct(equity_curve),
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.join(here, "..", ".."))
    fixtures = os.path.join(repo_root, "Stratex", "tests", "fixtures", "fwd002")

    result = {
        "task": "TASK-STR-068",
        "bar": {"full_pf": FULL_BAR_PF, "forward_pf": FORWARD_PF,
                "min_oos_trades": MIN_OOS_TRADES,
                "min_positive_folds": MIN_POS_FOLDS, "folds_total": FOLDS_TOTAL,
                "bonferroni_alpha_over_folds": BONFERRONI_ALPHA / FOLDS_TOTAL,
                "lane_risk_pct": LANE_RISK * 100, "kill_dd_pct": KILL_DD * 100},
        "assumptions": ["costs_and_borrow_ZERO_no_venue_schedule",
                        "rolling_z_window_60d", "single_pair_at_a_time",
                        "size_risks_lane_0.1pct_entry_to_stop"],
        "sim": {"folds": []},
        "real": {"pairs": []},
    }

    # ---- Leg 1: simulated pair, 5 folds -----------------------------------
    all_trades = []
    worst_dd = 0.0
    for seed in SIM_SEEDS:
        lx, ly = sim_pair(seed)
        diag, trades, equity = run_rule(lx, ly, N_TRAIN, f"sim-seed-{seed}")
        summary = summarise(trades, equity)
        diag["summary"] = summary
        result["sim"]["folds"].append(diag)
        all_trades.extend(trades)
        worst_dd = max(worst_dd, summary["max_dd_pct"] or 0.0)
    pooled = summarise(all_trades, [1.0])
    pooled["max_dd_pct"] = worst_dd  # worst fold drawdown, not a pooled curve
    pos_folds = sum(1 for f in result["sim"]["folds"]
                    if f["summary"]["expectancy"] is not None
                    and f["summary"]["expectancy"] > 0)
    pooled["positive_folds"] = pos_folds
    result["sim"]["pooled"] = pooled
    pf_ok = pooled["pf"] not in (None, "inf") and pooled["pf"] >= FULL_BAR_PF
    full = (
        pooled["n_trades"] >= MIN_OOS_TRADES
        and pooled["expectancy"] is not None and pooled["expectancy"] > 0
        and pf_ok
        and pos_folds >= MIN_POS_FOLDS
        and pooled["p_one_sided"] is not None
        and pooled["p_one_sided"] < BONFERRONI_ALPHA / FOLDS_TOTAL
        and worst_dd < KILL_DD * 100
    )
    forward = (
        pooled["n_trades"] >= MIN_OOS_TRADES
        and pooled["expectancy"] is not None and pooled["expectancy"] > 0
        and pooled["pf"] is not None
        and (pooled["pf"] == "inf" or pooled["pf"] >= FORWARD_PF)
        and worst_dd < KILL_DD * 100
    )
    killed = (
        (pooled["n_trades"] >= 50 and pooled["expectancy"] is not None
         and (pooled["expectancy"] < 0
              or (pooled["pf"] not in (None, "inf") and pooled["pf"] < 1.0)))
        or worst_dd >= KILL_DD * 100
    )
    result["sim"]["verdict_full_bar"] = "PASS" if full else "FAIL"
    result["sim"]["verdict_forward_tier"] = "PASS" if forward else "FAIL"
    result["sim"]["kill_triggered"] = bool(killed)

    # ---- Leg 2: real demo fixtures ----------------------------------------
    for name_a, name_b, label in [
        ("BTCUSDT_1d.csv", "SOLUSDT_1d.csv", "BTC-SOL"),
        ("FX_EURUSD_1d.csv", "FX_USDJPY_1d.csv", "EURUSD-USDJPY"),
    ]:
        pa = os.path.join(fixtures, name_a)
        pb = os.path.join(fixtures, name_b)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            result["real"]["pairs"].append(
                {"label": label, "outcome": "FIXTURES ABSENT — no trades"})
            continue
        lx, ly, n_common = aligned_log_pair(pa, pb)
        if lx is None:
            result["real"]["pairs"].append(
                {"label": label, "outcome": "TOO FEW COMMON ROWS",
                 "n_common": n_common})
            continue
        n_train = len(lx) // 2
        diag, trades, equity = run_rule(lx, ly, n_train, label)
        diag["summary"] = summarise(trades, equity)
        diag["n_common"] = int(n_common)
        result["real"]["pairs"].append(diag)

    print(json.dumps(result, indent=1, default=str))


if __name__ == "__main__":
    main()
