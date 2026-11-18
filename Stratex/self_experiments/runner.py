"""Combination runner — pooled metrics over stored OOS trade streams.

Pure arithmetic on the stream store's recorded per-trade net returns:
no market data, no re-backtesting, no invented series. The pooled
metrics are exactly the metrics the research programme computed for a
single stream, computed over the union of the members' trade lists:

- expectancy = mean of pooled net returns
- PF = gross profit / gross loss over the pooled list
- folds = per-fold expectancy over the pooled per-fold lists; a fold
  is positive when its pooled expectancy > 0
- holdout = trade-weighted pooled untouched expectancy; available
  only when EVERY member carries holdout data (fail-closed for the
  full bar)
- significance = one-sided p from the t-stat of the pooled returns
  (sample stdev, normal-approximation p) — the construction the
  RD-002 records themselves carry (verified: it reproduces
  bollinger_trend p50_sd2.0's recorded t 3.1823 / p 0.0007305 to
  five significant figures from its stored trades).
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Iterable

from .store import StreamRecord


@dataclass
class PooledMetrics:
    members: tuple[str, ...]
    trades: int
    wins: int
    expectancy: float
    pf: float
    gross_profit: float
    gross_loss: float
    per_fold: dict[str, dict[str, float]]  # fold -> {trades, expectancy}
    positive_folds: int
    folds_with_trades: int
    holdout_trades: int | None
    holdout_expectancy: float | None
    t_stat: float
    p_one_sided: float

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    def to_dict(self) -> dict:
        return {
            "members": list(self.members),
            "trades": self.trades,
            "wins": self.wins,
            "win_rate": round(self.win_rate, 6),
            "expectancy": self.expectancy,
            "pf": self.pf,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "per_fold": self.per_fold,
            "positive_folds": self.positive_folds,
            "folds_with_trades": self.folds_with_trades,
            "holdout_trades": self.holdout_trades,
            "holdout_expectancy": self.holdout_expectancy,
            "t_stat": self.t_stat,
            "p_one_sided": self.p_one_sided,
        }


def _metrics_for_returns(
    members: tuple[str, ...],
    returns: list[float],
    per_fold_returns: dict[str, list[float]],
    holdout_trades: int | None,
    holdout_expectancy: float | None,
) -> PooledMetrics:
    trades = len(returns)
    wins = sum(1 for r in returns if r > 0)
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = -sum(r for r in returns if r < 0)
    expectancy = statistics.fmean(returns) if returns else 0.0
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    else:
        pf = float("inf") if gross_profit > 0 else 0.0
    per_fold: dict[str, dict[str, float]] = {}
    positive = 0
    with_trades = 0
    for fold in sorted(per_fold_returns):
        fold_returns = per_fold_returns[fold]
        if not fold_returns:
            continue
        with_trades += 1
        fold_exp = statistics.fmean(fold_returns)
        per_fold[fold] = {"trades": len(fold_returns), "expectancy": fold_exp}
        if fold_exp > 0:
            positive += 1
    if trades >= 2:
        sd = statistics.stdev(returns)
        t_stat = expectancy / (sd / math.sqrt(trades)) if sd > 0 else 0.0
    else:
        t_stat = 0.0
    p_one_sided = 0.5 * math.erfc(t_stat / math.sqrt(2.0))
    return PooledMetrics(
        members=members,
        trades=trades,
        wins=wins,
        expectancy=expectancy,
        pf=pf,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        per_fold=per_fold,
        positive_folds=positive,
        folds_with_trades=with_trades,
        holdout_trades=holdout_trades,
        holdout_expectancy=holdout_expectancy,
        t_stat=t_stat,
        p_one_sided=p_one_sided,
    )


def pooled_metrics(records: Iterable[StreamRecord]) -> PooledMetrics:
    """Judge the equal-standing union of the members' OOS trades."""
    records = list(records)
    members = tuple(r.stream_id for r in records)
    per_fold_returns: dict[str, list[float]] = {}
    returns: list[float] = []
    for record in records:
        for fold, fold_returns in record.folds.items():
            per_fold_returns.setdefault(fold, []).extend(fold_returns)
            returns.extend(fold_returns)
    if all(
        r.holdout_trades is not None and r.holdout_expectancy is not None
        for r in records
    ):
        holdout_trades = sum(int(r.holdout_trades) for r in records)
        holdout_expectancy = (
            sum(float(r.holdout_expectancy) * int(r.holdout_trades) for r in records)
            / holdout_trades
            if holdout_trades
            else None
        )
    else:
        holdout_trades = None
        holdout_expectancy = None
    return _metrics_for_returns(
        members, returns, per_fold_returns, holdout_trades, holdout_expectancy
    )
