"""TASK-IG2-STR-03: Vibe-Trading research-layer pattern tests."""
import numpy as np
import pytest

from Stratex.research.vibe_layer import (ResearchCommittee, ProposalEvidence,
                                         compute_factor,
                                         information_coefficient, parse_spec)


def _series(n=300, seed=3, drift=0.001):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    volume = rng.uniform(1e5, 2e5, n)
    return close, volume


def test_factor_shapes_and_warmup():
    close, volume = _series()
    for name in ("momentum", "reversal", "volatility", "bollinger_z", "rsi_factor"):
        f = compute_factor(name, close)
        assert f.shape == close.shape and np.all(f[:5] == 0.0)
    assert compute_factor("volume_surge", close, volume).shape == close.shape
    assert compute_factor("amihud_illiquidity", close, volume).shape == close.shape
    with pytest.raises(ValueError):
        compute_factor("nope", close)
    with pytest.raises(ValueError):
        compute_factor("volume_surge", close)  # needs volume


def test_ic_detects_momentum_in_trending_series():
    close, _ = _series(drift=0.002)
    ic = information_coefficient(compute_factor("momentum", close, window=10), close, horizon=5)
    assert ic > 0.05  # trending series: momentum must rank-predict forward returns


def test_ic_zero_on_constant_factor():
    close, _ = _series()
    assert information_coefficient(np.zeros_like(close), close) == 0.0


def test_committee_verdicts():
    c = ResearchCommittee()
    good = c.review(ProposalEvidence("momentum", ic=0.05, sharpe=1.4,
                                     max_drawdown=-0.08, n_trades=250, oos_sharpe=1.0))
    assert good.verdict == "adopt"
    bad_dd = c.review(ProposalEvidence("x", ic=0.05, sharpe=1.4,
                                       max_drawdown=-0.30, n_trades=250, oos_sharpe=1.0))
    assert bad_dd.verdict == "reject"
    thin = c.review(ProposalEvidence("y", ic=0.005, sharpe=0.4,
                                     max_drawdown=-0.05, n_trades=10))
    assert thin.verdict == "reject"
    overfit = c.review(ProposalEvidence("z", ic=0.05, sharpe=2.0,
                                        max_drawdown=-0.05, n_trades=250, oos_sharpe=-0.5))
    assert overfit.verdict in ("watch", "reject") and overfit.lens_votes["robustness"] == "reject"


def test_parse_spec_ok_and_grid():
    plan = parse_spec("backtest ma_crossover on BTC/USDT with fast=10 slow=50 lookback 365 fee 5bps")
    assert plan.strategy == "ma_crossover" and plan.symbol == "BTC/USDT"
    assert plan.sweep_grid() == {"fast": (10,), "slow": (50,)}
    assert plan.params["fee_bps"] == 5.0


def test_parse_spec_rejects_garbage():
    for bad in ("please trade something", "backtest ma_crossover on BTC/USDT fast=60 slow=50",
                "backtest unknown_strategy on BTC/USDT"):
        with pytest.raises(ValueError):
            parse_spec(bad)
