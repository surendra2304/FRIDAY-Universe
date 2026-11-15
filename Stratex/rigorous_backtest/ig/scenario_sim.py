"""Pre-trade scenario simulation ("Time Machine") — research tooling.

TASK-IG-STR-04 (IG corpus item Det0-D8Oc41; pattern from the
day-trader-skill repo card, whose "Time Machine" runs Monte-Carlo
replays of a trade before risking anything).

Given the historical outcome distribution of a strategy or setup —
expressed in R multiples (profit/loss as a multiple of the amount
risked per trade) — this module bootstraps thousands of possible
futures and reports the distribution honestly: probability of profit,
percentiles of final outcome, typical and bad-case drawdowns, and
(when the caller supplies sizing) the probability of breaching a
drawdown kill line or ruin.

WHAT THIS IS NOT: a prediction. Bootstrap resampling assumes the past
distribution repeats; regime change breaks it. It is a research lens
for sizing and expectation-setting, bound by the same evidence bar as
everything else in the RD programme. Risk parameters are INPUTS the
caller supplies (e.g. from the decided FWD-006 package); this module
imports nothing from production and changes no governance.

Stdlib only, Python 3.10-compatible. Deterministic for a given seed.
"""

import random
import statistics


def _percentile(sorted_vals, pct):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _path_stats(path):
    """(final, max_drawdown) of one equity path, all in R units."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in path:
        equity += r
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return equity, max_dd


def simulate(returns_r, trades_per_path=100, n_paths=2000, seed=12345,
             risk_per_trade_pct=None, kill_dd_pct=None):
    """Bootstrap-simulate `trades_per_path`-trade futures.

    returns_r: historical net trade outcomes in R multiples (must be
    non-empty). risk_per_trade_pct / kill_dd_pct are optional caller
    inputs in account-equity fractions (e.g. 0.001 and 0.05): when both
    are given, each path also reports whether compounding equity at
    that fixed fractional risk would breach the kill drawdown line, or
    ruin (equity <= 0). Returns a summary dict; all money figures are
    in R unless the sizing inputs were given (then *_pct_of_equity).
    """
    pool = [float(x) for x in returns_r]
    if not pool:
        raise ValueError("returns_r must be non-empty")
    if trades_per_path < 1 or n_paths < 1:
        raise ValueError("trades_per_path and n_paths must be >= 1")
    rng = random.Random(seed)
    finals, max_dds = [], []
    kill_breaches = 0
    ruins = 0
    sized = risk_per_trade_pct is not None and kill_dd_pct is not None
    for _ in range(n_paths):
        path = [rng.choice(pool) for _ in range(trades_per_path)]
        final, max_dd = _path_stats(path)
        finals.append(final)
        max_dds.append(max_dd)
        if sized:
            equity = 1.0
            peak = 1.0
            breached = False
            ruined = False
            for r in path:
                equity *= (1.0 + r * risk_per_trade_pct)
                if equity <= 0:
                    ruined = True
                    equity = 0.0
                    break
                if equity > peak:
                    peak = equity
                if peak > 0 and (peak - equity) / peak >= kill_dd_pct:
                    breached = True
                    break
            kill_breaches += 1 if breached else 0
            ruins += 1 if ruined else 0
    finals.sort()
    max_dds.sort()
    out = {
        "n_paths": n_paths,
        "trades_per_path": trades_per_path,
        "sample_size": len(pool),
        "sample_expectancy_r": statistics.fmean(pool),
        "sample_win_rate": sum(1 for x in pool if x > 0) / len(pool),
        "p_profit": sum(1 for f in finals if f > 0) / n_paths,
        "final_r_percentiles": {
            "p5": _percentile(finals, 5), "p25": _percentile(finals, 25),
            "p50": _percentile(finals, 50), "p75": _percentile(finals, 75),
            "p95": _percentile(finals, 95)},
        "max_dd_r_percentiles": {
            "p50": _percentile(max_dds, 50), "p90": _percentile(max_dds, 90),
            "p99": _percentile(max_dds, 99)},
        "disclaimer": ("Bootstrap of the historical outcome distribution; "
                       "not a forecast. Assumes the past distribution "
                       "repeats, which real regimes violate."),
    }
    if sized:
        out["risk_per_trade_pct"] = risk_per_trade_pct
        out["kill_dd_pct"] = kill_dd_pct
        out["p_kill_breach"] = kill_breaches / n_paths
        out["p_ruin"] = ruins / n_paths
    return out


def pool_from_spec(win_rate, avg_win_r, avg_loss_r, n=1000, seed=999):
    """Build a synthetic outcome pool from a win/loss spec (avg_loss_r
    is given as a positive magnitude). For exploring a hypothesised
    setup before any history exists — labelled synthetic by callers."""
    if not 0.0 <= win_rate <= 1.0:
        raise ValueError("win_rate must be in [0, 1]")
    if avg_win_r <= 0 or avg_loss_r <= 0:
        raise ValueError("avg_win_r and avg_loss_r must be > 0")
    rng = random.Random(seed)
    return [avg_win_r if rng.random() < win_rate else -avg_loss_r
            for _ in range(n)]
