"""Tests for TASK-IG2-STR-12 bayesian_uncertainty (stdlib-only, offline).

Deterministic synthetic fill lists only — mechanics/evidence-shape
evidence, never strategy-performance evidence.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.bayesian_uncertainty import (  # noqa: E402
    InsufficientDataError, posterior_from_fills,
)

# 60% winners averaging +1.5R, 40% losers at -1.0R: true expectancy
# 0.6*1.5 - 0.4*1.0 = +0.5R, true PF = 0.9/0.4 = 2.25.
STRONG = [1.5] * 60 + [-1.0] * 40
# Mirror image: expectancy -0.5R, PF ~0.44.
WEAK = [-1.5] * 60 + [1.0] * 40
FAST = dict(n_iter=3000, burn=1000)


def test_strong_fills_support_promotion_evidence():
    summary = posterior_from_fills(STRONG, **FAST)
    assert summary.p_expectancy_positive > 0.95
    assert summary.p_profit_factor_at_bar > 0.9
    assert summary.expectancy_ci90[0] > 0
    assert summary.gate_evidence()["supports_promotion"] is True


def test_weak_fills_do_not_support_promotion():
    summary = posterior_from_fills(WEAK, **FAST)
    assert summary.p_expectancy_positive < 0.05
    assert summary.gate_evidence()["supports_promotion"] is False


def test_deterministic_for_same_seed():
    a = posterior_from_fills(STRONG, seed=42, **FAST)
    b = posterior_from_fills(STRONG, seed=42, **FAST)
    assert a.as_dict() == b.as_dict()


def test_posterior_tracks_observed_point_estimates():
    summary = posterior_from_fills(STRONG, **FAST)
    assert summary.observed_expectancy_r == pytest.approx(0.5)
    assert summary.observed_profit_factor == pytest.approx(2.25)
    assert summary.expectancy_ci90[0] < summary.expectancy_median \
        < summary.expectancy_ci90[1]
    assert summary.draws_retained > 0
    # Degenerate identical magnitudes make the posterior a narrow ridge
    # (acceptance is low); the operative check is that both chains agree.
    assert all(0.01 < r < 0.99 for r in summary.acceptance_rates)
    assert summary.split_chain_expectancy_diff < 0.1


def test_varied_fills_mix_healthily():
    import random
    rng = random.Random(3)
    fills = [rng.uniform(1.1, 1.9) for _ in range(60)] + \
        [-rng.uniform(0.8, 1.2) for _ in range(40)]
    summary = posterior_from_fills(fills, **FAST)
    assert all(0.05 < r < 0.95 for r in summary.acceptance_rates)
    assert summary.p_expectancy_positive > 0.95


def test_insufficient_or_one_sided_data_is_refused():
    with pytest.raises(InsufficientDataError):
        posterior_from_fills([1.0] * 8 + [-1.0] * 1, **FAST)
    with pytest.raises(InsufficientDataError):
        posterior_from_fills([2.0] * 30, **FAST)  # no losses at all


def test_scratch_trades_dropped_and_counted():
    summary = posterior_from_fills(STRONG + [0.0] * 5, **FAST)
    assert summary.n_scratch_dropped == 5
    assert summary.n_trades == 100


def test_gate_evidence_shape():
    evidence = posterior_from_fills(STRONG, **FAST).gate_evidence()
    assert evidence["profit_factor_bar"] == 1.2
    assert evidence["n_forward_trades"] == 100
    assert "still apply in full" in evidence["standard"]
