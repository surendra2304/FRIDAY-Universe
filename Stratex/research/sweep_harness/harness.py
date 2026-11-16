"""Offline vectorized parameter-sweep harness (TASK-IG2-STR-01).

Pattern adapted from vectorbt (community edition, Apache-2.0 + Commons
Clause — pattern only, no vectorbt code copied and vectorbt is NOT a fleet
dependency): pack every parameter combination into NumPy arrays and evaluate
the whole grid in vectorized operations instead of looping backtests one at
a time. FRIDAY-native implementation on NumPy only (already a Stratex
dependency); no numba, no pandas requirement, Python 3.10.

RESEARCH ONLY. This module never routes orders and never touches a venue.
It exists for Stratex's RD programme: sweep offline / off-fleet, shortlist,
then validate any survivor through the canonical rigorous_backtest engine
and the forward scorecard before it can influence demo trading. Fleet RAM
is ~956MB per VM, so the grid is hard-capped by an explicit memory estimate
— an oversized sweep raises instead of OOM-killing a server.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

# One float64 per (combo, bar) per working array; we hold ~4 arrays live.
_BYTES_PER_CELL = 8 * 4
DEFAULT_MAX_GRID_BYTES = 256 * 1024 * 1024  # 256MB working-set ceiling


class GridTooLargeError(ValueError):
    """Raised when a sweep grid would exceed the RAM ceiling."""


@dataclass(frozen=True)
class SweepGrid:
    """Cartesian parameter grid with a hard size/RAM guard."""

    parameters: dict[str, tuple]
    max_combos: int = 4096

    def combos(self) -> list[dict]:
        names = list(self.parameters)
        out = [dict(zip(names, vals)) for vals in
               itertools.product(*(self.parameters[n] for n in names))]
        if len(out) > self.max_combos:
            raise GridTooLargeError(
                f"grid has {len(out)} combos > cap {self.max_combos}; "
                "narrow the ranges — fleet RAM is not sweep RAM")
        return out

    def estimated_bytes(self, n_bars: int) -> int:
        n = 1
        for vals in self.parameters.values():
            n *= len(vals)
        return n * int(n_bars) * _BYTES_PER_CELL

    def check_ram(self, n_bars: int, cap: int = DEFAULT_MAX_GRID_BYTES) -> None:
        est = self.estimated_bytes(n_bars)
        if est > cap:
            raise GridTooLargeError(
                f"grid needs ~{est/1e6:.0f}MB working set > cap "
                f"{cap/1e6:.0f}MB; run off-fleet or shrink the grid")


def sma(values: np.ndarray, window: int) -> np.ndarray:
    """Simple moving average with NaN warm-up, vectorized via cumsum."""
    if window < 1:
        raise ValueError("window must be >= 1")
    out = np.full(values.shape, np.nan, dtype=float)
    if len(values) < window:
        return out
    csum = np.concatenate(([0.0], np.cumsum(values)))
    out[window - 1:] = (csum[window:] - csum[:-window]) / window
    return out


@dataclass
class SweepResult:
    parameters: dict
    metrics: dict[str, float]
    n_trades: int = 0


@dataclass
class SweepReport:
    results: list[SweepResult] = field(default_factory=list)
    n_bars: int = 0
    fee_bps: float = 0.0

    def ranked(self, min_trades: int = 5) -> list[SweepResult]:
        eligible = [r for r in self.results if r.n_trades >= min_trades]
        return sorted(eligible,
                      key=lambda r: (r.metrics.get("sharpe", -9e9),
                                     r.metrics.get("net_return", -9e9)),
                      reverse=True)

    def best(self, min_trades: int = 5) -> SweepResult | None:
        r = self.ranked(min_trades)
        return r[0] if r else None


def equity_metrics(strategy_returns: np.ndarray, positions: np.ndarray,
                   periods_per_year: int = 365) -> tuple[dict[str, float], int]:
    """Vectorized portfolio metrics for one combo (vectorbt-style stats)."""
    r = np.asarray(strategy_returns, dtype=float)
    equity = np.cumprod(1.0 + r)
    total = float(equity[-1] - 1.0) if len(equity) else 0.0
    mean, std = float(r.mean()) if len(r) else 0.0, float(r.std()) if len(r) else 0.0
    downside = r[r < 0]
    dstd = float(downside.std()) if len(downside) else 0.0
    sharpe = mean / std * math.sqrt(periods_per_year) if std > 0 else 0.0
    sortino = mean / dstd * math.sqrt(periods_per_year) if dstd > 0 else 0.0
    peak = np.maximum.accumulate(equity) if len(equity) else equity
    dd = (equity / peak - 1.0) if len(equity) else np.array([])
    max_dd = float(dd.min()) if len(dd) else 0.0
    gains = float(r[r > 0].sum()); losses = float(-r[r < 0].sum())
    pf = gains / losses if losses > 0 else (float("inf") if gains > 0 else 0.0)
    calmar = (total / abs(max_dd)) if max_dd < 0 else 0.0
    entries = int(np.sum(np.diff(np.concatenate(([0.0], positions))) > 0))
    return ({"net_return": total, "sharpe": sharpe, "sortino": sortino,
             "max_drawdown": max_dd, "profit_factor": pf, "calmar": calmar},
            entries)


def sweep_ma_crossover(close: np.ndarray, grid: SweepGrid,
                       fee_bps: float = 5.0,
                       max_grid_bytes: int = DEFAULT_MAX_GRID_BYTES) -> SweepReport:
    """Vectorized fast/slow SMA-crossover sweep over the whole grid.

    Grid must carry ``fast`` and ``slow`` windows (fast < slow enforced per
    combo; invalid combos are skipped, not silently traded). Positions are
    long-only 0/1 — Stratex research convention; no leverage, no shorts.
    """
    close = np.asarray(close, dtype=float)
    if close.ndim != 1 or len(close) < 30:
        raise ValueError("need a 1-D close series of >= 30 bars")
    grid.check_ram(len(close), max_grid_bytes)
    combos = grid.combos()
    windows = sorted({int(p[k]) for p in combos for k in ("fast", "slow")})
    smas = {w: sma(close, w) for w in windows}
    bar_ret = np.zeros_like(close)
    bar_ret[1:] = close[1:] / close[:-1] - 1.0
    fee = fee_bps / 10_000.0
    report = SweepReport(n_bars=len(close), fee_bps=fee_bps)
    for p in combos:
        fast, slow = int(p["fast"]), int(p["slow"])
        if fast >= slow:
            continue
        pos = (smas[fast] > smas[slow]).astype(float)
        pos[:slow] = 0.0
        pos = np.nan_to_num(pos)
        turnover = np.abs(np.diff(np.concatenate(([0.0], pos))))
        strat_ret = pos * bar_ret - turnover * fee
        metrics, n_trades = equity_metrics(strat_ret, pos)
        report.results.append(SweepResult(dict(p), metrics, n_trades))
    return report


@dataclass
class WalkForwardFold:
    train_bars: tuple[int, int]
    test_bars: tuple[int, int]
    best_train_params: dict | None
    train_metrics: dict[str, float]
    test_metrics: dict[str, float]


def walk_forward(close: np.ndarray, grid: SweepGrid, n_folds: int = 4,
                 fee_bps: float = 5.0) -> list[WalkForwardFold]:
    """Expanding-window walk-forward: sweep on train, score winner on test.

    The train/test Sharpe gap is the overfit signal the RD programme reads;
    a combo that only wins in-sample is reported, never promoted by this code.
    """
    close = np.asarray(close, dtype=float)
    if n_folds < 2:
        raise ValueError("n_folds must be >= 2")
    fold_len = len(close) // (n_folds + 1)
    if fold_len < 30:
        raise ValueError("series too short for that many folds")
    folds: list[WalkForwardFold] = []
    for i in range(n_folds):
        train_end = fold_len * (i + 1)
        test_end = min(train_end + fold_len, len(close))
        train = sweep_ma_crossover(close[:train_end], grid, fee_bps)
        best = train.best()
        test_metrics: dict[str, float] = {}
        if best is not None:
            seg = close[train_end:test_end]
            one = SweepGrid({"fast": (best.parameters["fast"],),
                             "slow": (best.parameters["slow"],)})
            rep = sweep_ma_crossover(
                np.concatenate((close[max(0, train_end - int(best.parameters["slow"])):train_end], seg)),
                one, fee_bps)
            if rep.results:
                test_metrics = rep.results[0].metrics
        folds.append(WalkForwardFold(
            (0, train_end), (train_end, test_end),
            dict(best.parameters) if best else None,
            dict(best.metrics) if best else {}, test_metrics))
    return folds
