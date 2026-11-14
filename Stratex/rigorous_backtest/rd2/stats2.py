"""Reporting, holdout and significance for TASK-STR-RD-002.

Judgement is walk-forward OOS only (harness folds). The promotion bar
keeps RD-001's numeric core (expectancy > 0, PF >= 1.2, >= 200 OOS
trades, >= 80% of profile folds positive) and ADDS, per the extended
Anti-Overfit Law:

- a per-class holdout: breadth across symbols + an untouched-symbol
  subset (pre-declared: every 3rd symbol alphabetically) that selection
  never sees;
- a multiple-testing significance gate computed at synthesis time
  against the FINAL global trial counter: deflated Sharpe ratio
  (Bailey & Lopez de Prado) >= 0.95 AND a Bonferroni one-sided
  p < 0.05 / N_global on the per-trade mean.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as _stats

from ..simulator import Trade, trade_metrics
from ..walkforward import FOLDS, trades_in_window

FOLD_BOUNDS = {fid: (s, e) for fid, s, e in FOLDS}

BAR = {"expectancy_net_gt": 0.0, "profit_factor_net_gte": 1.2,
       "min_oos_trades": 200, "min_positive_fold_share": 0.8}


def fold_report(trades: list[Trade], fold_ids: list[str],
                symbols: list[str]) -> dict:
    per_fold, pooled = {}, []
    for fid in fold_ids:
        s, e = FOLD_BOUNDS[fid]
        ft = trades_in_window(trades, s, e)
        per_fold[fid] = {"oos_start": s, "oos_end": e, **trade_metrics(ft)}
        pooled.extend(ft)
    per_symbol = {}
    for sym in symbols:
        st = [t for t in pooled if t.symbol == sym]
        per_symbol[sym] = trade_metrics(st)
    return {"per_fold": per_fold, "pooled_oos": trade_metrics(pooled),
            "per_symbol_oos": per_symbol, "fold_profile": fold_ids}


def positive_folds(report: dict) -> tuple[int, int]:
    """(folds with expectancy > 0, folds with any trades) in profile."""
    pos = have = 0
    for fid in report["fold_profile"]:
        m = report["per_fold"][fid]
        if (m.get("trades") or 0) > 0:
            have += 1
            if (m.get("expectancy_net") or 0) > 0:
                pos += 1
    return pos, have


def holdout2(report: dict, symbols: list[str]) -> dict:
    """Breadth + untouched-subset holdout (generalizes rd.common's).

    Pass requires ALL of:
    - breadth: >= 50% of symbols with >= 20 OOS trades are positive;
    - concentration: no single symbol contributes > 50% of total
      positive profit (panels >= 5 symbols) or > 80% (smaller panels,
      the RD-001 small-panel rule);
    - untouched subset (every 3rd symbol alphabetically — declared
      here, before any RD-002 run): pooled expectancy > 0 on >= 30
      trades the selection process never optimizes on.
    """
    per = report["per_symbol_oos"]
    active = {s: m for s, m in per.items() if (m.get("trades") or 0) >= 20}
    pos = [s for s, m in active.items() if (m.get("expectancy_net") or 0) > 0]
    breadth = (len(pos) / len(active)) if active else 0.0
    profits = {s: (m.get("expectancy_net") or 0.0) * (m.get("trades") or 0)
               for s, m in per.items()}
    total_pos = sum(p for p in profits.values() if p > 0)
    max_share = (max(profits.values()) / total_pos) if total_pos > 0 else 1.0
    cap = 0.5 if len(symbols) >= 5 else 0.8
    subset = sorted(symbols)[2::3]
    sub_trades = [m for s, m in per.items() if s in subset]
    sub_n = sum(m.get("trades") or 0 for m in sub_trades)
    sub_profit = sum((m.get("expectancy_net") or 0.0) * (m.get("trades") or 0)
                     for m in sub_trades)
    sub_exp = (sub_profit / sub_n) if sub_n else None
    return {
        "symbols_active_min20": len(active),
        "symbols_positive": len(pos),
        "breadth_positive_share": breadth,
        "max_symbol_profit_share": max_share,
        "max_share_cap": cap,
        "untouched_subset": subset,
        "untouched_trades": sub_n,
        "untouched_expectancy": sub_exp,
        "passes": (len(active) >= 3 and breadth >= 0.5
                   and max_share <= cap
                   and sub_n >= 30 and (sub_exp or 0) > 0),
    }


def check_bar2(report: dict, holdout: dict) -> dict:
    po = report["pooled_oos"]
    pos, have = positive_folds(report)
    need = math.ceil(BAR["min_positive_fold_share"] * len(report["fold_profile"]))
    checks = {
        "expectancy_net_gt_0": (po.get("expectancy_net") or 0.0) > 0,
        "profit_factor_net_gte_1.2": (po.get("profit_factor_net") or 0) >= 1.2,
        "min_oos_trades_200": (po.get("trades") or 0) >= BAR["min_oos_trades"],
        "positive_folds": pos >= need and have >= len(report["fold_profile"]) - 1,
        "holdout_passes": bool(holdout.get("passes")),
    }
    return {"bar": {**BAR, "positive_folds_needed": need,
                    "positive_folds": pos, "folds_with_trades": have},
            "checks": checks, "passes_bar": all(checks.values())}


def trade_stats(trades: list[Trade]) -> dict:
    """Per-trade return distribution stats for significance testing."""
    if not trades:
        return {"n": 0, "sharpe_per_trade": None, "t_stat": None,
                "p_one_sided": None, "skew": None, "kurtosis": None}
    r = np.array([t.net_return for t in trades], dtype=float)
    n = len(r)
    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    sr = float(r.mean() / sd) if sd > 0 else 0.0
    t = sr * math.sqrt(n)
    return {"n": n, "sharpe_per_trade": sr, "t_stat": t,
            "p_one_sided": float(1 - _stats.norm.cdf(t)),
            "skew": float(_stats.skew(r)) if n > 2 else 0.0,
            "kurtosis": float(_stats.kurtosis(r, fisher=False)) if n > 3 else 3.0}


def expected_max_sharpe(n_trials: int, sr_std: float) -> float:
    """E[max SR] under the null for N independent trials (Bailey-LdP)."""
    if n_trials <= 1 or sr_std <= 0:
        return 0.0
    gamma = 0.5772156649
    z1 = _stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = _stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return sr_std * ((1 - gamma) * z1 + gamma * z2)


def deflated_sharpe(sr: float, n_trades: int, skew: float, kurtosis: float,
                    n_trials: int, sr_std: float) -> float:
    """Deflated Sharpe ratio: P(true SR > 0) after correcting for the
    selection bias of having tried n_trials configurations."""
    if n_trades < 3 or sr_std <= 0:
        return 0.0
    sr0 = expected_max_sharpe(n_trials, sr_std)
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurtosis - 1) / 4 * sr * sr))
    z = (sr - sr0) * math.sqrt(n_trades - 1) / denom
    return float(_stats.norm.cdf(z))


def significance(trades: list[Trade], n_trials_global: int,
                 sr_std_global: float) -> dict:
    st = trade_stats(trades)
    if st["n"] == 0:
        return {**st, "bonferroni_alpha": 0.05 / max(1, n_trials_global),
                "bonferroni_pass": False, "deflated_sharpe": 0.0,
                "dsr_pass": False, "significance_pass": False}
    alpha = 0.05 / max(1, n_trials_global)
    dsr = deflated_sharpe(st["sharpe_per_trade"], st["n"], st["skew"] or 0.0,
                          st["kurtosis"] or 3.0, n_trials_global,
                          sr_std_global)
    bonf = (st["p_one_sided"] or 1.0) < alpha
    return {**st, "bonferroni_alpha": alpha, "bonferroni_pass": bool(bonf),
            "deflated_sharpe": dsr, "dsr_pass": bool(dsr >= 0.95),
            "significance_pass": bool(bonf and dsr >= 0.95)}
