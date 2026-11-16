"""TASK-IG2-STR-01: vectorized sweep harness tests (research only)."""
import numpy as np
import pytest

from Stratex.research.sweep_harness import (GridTooLargeError, SweepGrid,
                                            sma, sweep_ma_crossover,
                                            walk_forward)


def _trend(n=400, seed=7):
    rng = np.random.default_rng(seed)
    return 100.0 * np.exp(np.cumsum(rng.normal(0.0012, 0.01, n)))


def test_sma_matches_manual():
    x = np.arange(10, dtype=float)
    out = sma(x, 3)
    assert np.isnan(out[0]) and abs(out[2] - 1.0) < 1e-12 and abs(out[9] - 8.0) < 1e-12


def test_grid_cap_enforced():
    g = SweepGrid({"fast": tuple(range(2, 200)), "slow": tuple(range(201, 400))},
                  max_combos=100)
    with pytest.raises(GridTooLargeError):
        g.combos()


def test_ram_guard_enforced():
    g = SweepGrid({"fast": (5, 10), "slow": (30, 50)})
    with pytest.raises(GridTooLargeError):
        sweep_ma_crossover(_trend(), g, max_grid_bytes=1024)


def test_sweep_runs_and_ranks():
    rep = sweep_ma_crossover(_trend(), SweepGrid({"fast": (5, 10, 20), "slow": (30, 50, 100)}))
    assert len(rep.results) == 9
    best = rep.best(min_trades=1)
    assert best is not None and "sharpe" in best.metrics
    assert all(np.isfinite(v) or v == float("inf") for r in rep.results for v in r.metrics.values())


def test_invalid_fast_ge_slow_skipped():
    rep = sweep_ma_crossover(_trend(), SweepGrid({"fast": (50,), "slow": (30,)}))
    assert rep.results == []


def test_walk_forward_shape():
    folds = walk_forward(_trend(600), SweepGrid({"fast": (5, 10), "slow": (30, 50)}), n_folds=3)
    assert len(folds) == 3
    for f in folds:
        assert f.test_bars[0] == f.train_bars[1]
        assert f.best_train_params is None or set(f.best_train_params) == {"fast", "slow"}


def test_short_series_rejected():
    with pytest.raises(ValueError):
        sweep_ma_crossover(np.arange(10, dtype=float), SweepGrid({"fast": (2,), "slow": (5,)}))
