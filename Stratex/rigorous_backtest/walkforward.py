"""Walk-forward fold structure and out-of-sample-only aggregation.

Folds are fixed calendar windows. For fold k the in-sample segment is every
bar strictly before the fold's start (expanding/anchored window); the fold
itself is the out-of-sample segment. Trades are attributed to a segment by
ENTRY time. A strategy's headline numbers are computed ONLY from trades
entered inside out-of-sample folds — in-sample numbers are reported
separately and labelled, never blended into the headline.
"""
from __future__ import annotations

import pandas as pd

from .simulator import Trade, trade_metrics

# (fold_id, oos_start, oos_end) — end exclusive. Data before 2024-07-01 is
# warm-up / early in-sample only; no out-of-sample claim is made on it.
FOLDS: list[tuple[str, str, str]] = [
    ("W1", "2024-07-01", "2025-01-01"),
    ("W2", "2025-01-01", "2025-07-01"),
    ("W3", "2025-07-01", "2026-01-01"),
    ("W4", "2026-01-01", "2026-07-01"),
    ("W5", "2026-07-01", "2026-11-01"),
]


def fold_bounds() -> list[dict]:
    return [{"fold": fid, "oos_start": s, "oos_end": e} for fid, s, e in FOLDS]


def trades_in_window(trades: list[Trade], start: str | None, end: str | None) -> list[Trade]:
    out = []
    s = pd.Timestamp(start, tz="UTC") if start else None
    e = pd.Timestamp(end, tz="UTC") if end else None
    for t in trades:
        if s is not None and t.entry_time < s:
            continue
        if e is not None and t.entry_time >= e:
            continue
        out.append(t)
    return out


def oos_report(trades: list[Trade]) -> dict:
    """Per-fold and pooled out-of-sample metrics for a fixed trade list."""
    per_fold = {}
    pooled: list[Trade] = []
    for fid, s, e in FOLDS:
        ft = trades_in_window(trades, s, e)
        per_fold[fid] = {"oos_start": s, "oos_end": e, **trade_metrics(ft)}
        pooled.extend(ft)
    return {"per_fold": per_fold, "pooled_oos": trade_metrics(pooled)}


def in_sample_report(trades: list[Trade], before: str) -> dict:
    """Metrics for trades entered before a timestamp (an in-sample segment)."""
    return trade_metrics(trades_in_window(trades, None, before))
