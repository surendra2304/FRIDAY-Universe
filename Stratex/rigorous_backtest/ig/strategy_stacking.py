"""Strategy stacking/weighting — research-side composition.

TASK-IG-STR-12, code part (IG corpus item DcJyszBG6VF — a no-code
marketplace pattern: pick strategies, stack them with weights,
auto-rebalance).

What is implemented here is the RESEARCH half of that pattern:
compose the per-period fractional returns of several strategies into
one weighted stack (rebalanced every period by construction), and
score the stack with descriptive statistics (compounded return, max
drawdown, per-strategy contribution). What is deliberately NOT here:
the marketplace's broker-API auto-trading. A stack is a strategy for
evidence purposes — it faces the same RD programme bar (on trade-level
outcomes through the programme harness) and the same Phase-3 forward
protocol as any single strategy before it may trade, even on demo.
Stacking unproven strategies produces an unproven stack with better
marketing; the statistics below exist to measure, not to promote.

Series must be aligned (equal length, same periods) — the composer
raises on misalignment instead of silently truncating someone's
history. Stdlib only, Python 3.10-compatible.
"""

import math


def normalise_weights(weights):
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("weights must sum to a positive value")
    if any(w < 0 for w in weights.values()):
        raise ValueError("negative weights are not supported")
    return {k: w / total for k, w in weights.items()}


def compose(series_by_strategy, weights):
    """Weighted per-period returns of the stack.

    series_by_strategy: {name: [fractional return per period]} — all
    series must have equal length. weights need not sum to 1 (they
    are normalised). Returns the combined series."""
    if not series_by_strategy:
        raise ValueError("no strategies given")
    missing = [k for k in weights if k not in series_by_strategy]
    if missing:
        raise ValueError("weights name unknown strategies: %s" % missing)
    lengths = {len(v) for v in series_by_strategy.values()}
    if len(lengths) != 1:
        raise ValueError("series are misaligned: lengths %s"
                         % sorted(lengths))
    w = normalise_weights({k: weights.get(k, 0.0)
                           for k in series_by_strategy})
    n = lengths.pop()
    return [sum(w[name] * series_by_strategy[name][i]
                for name in series_by_strategy)
            for i in range(n)]


def stack_stats(combined, series_by_strategy=None, weights=None):
    """Descriptive statistics for a combined return series."""
    if not combined:
        raise ValueError("empty series")
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in combined:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    mean = sum(combined) / len(combined)
    var = sum((r - mean) ** 2 for r in combined) / len(combined)
    out = {
        "periods": len(combined),
        "total_return": equity - 1.0,
        "mean_period_return": mean,
        "period_volatility": math.sqrt(var),
        "max_drawdown": max_dd,
        "note": ("Descriptive only. Promotion of any stack requires the "
                 "RD programme bar on trade-level outcomes plus the "
                 "Phase-3 forward protocol — not these statistics."),
    }
    if series_by_strategy is not None and weights is not None:
        w = normalise_weights({k: weights.get(k, 0.0)
                               for k in series_by_strategy})
        out["contribution"] = {
            name: w[name] * sum(series)
            for name, series in series_by_strategy.items()}
    return out
