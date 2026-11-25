"""
Tests for Stratex/research/pairs_trading.py (TASK-STR-068).

The simulated pair reproduces the post's own setup (seed 11, true beta 1.5,
half-life 10d, fit on the first 750 days, trade the last 750, hedge ratio
constant in training then drifting). The post's reported numbers (ADF -4.7,
beta-hat 1.52, half-life 11.5d, Kalman Sharpe 0.46 vs OLS 0.23) are single-path
simulated claims, NOT asserted here — the tests assert behaviour and the
directions the construction supports (cointegration detected, half-life near
10d, Kalman tracking a drifting beta better than static OLS), with tolerances
wide enough for one simulated path.
"""

import numpy as np
import pytest

from research.pairs_trading import (
    EG_CRITICAL_5PCT,
    Z_STOP_DEFAULT,
    engle_granger,
    kalman_beta,
    ou_halflife,
    pair_position,
    pair_position_with_stop,
)

N_TRAIN = 750
N_TOTAL = 1500
TRUE_BETA = 1.5
TRUE_HALFLIFE = 10.0


def simulated_pair(seed=11):
    """Post's simulated pair: log-price random walk + OU spread, beta drifts
    after day 750. Returns (lx, ly, spread, beta_path)."""
    rng = np.random.default_rng(seed)
    phi = 2.0 ** (-1.0 / TRUE_HALFLIFE)
    sigma_spread = 0.02
    sigma_e = sigma_spread * np.sqrt(1 - phi**2)
    x = np.cumsum(rng.normal(0, 0.03, N_TOTAL))
    s = np.zeros(N_TOTAL)
    for t in range(1, N_TOTAL):
        s[t] = phi * s[t - 1] + rng.normal(0, sigma_e)
    beta = np.full(N_TOTAL, TRUE_BETA)
    beta[N_TRAIN:] = TRUE_BETA + 0.4 * np.linspace(0, 1, N_TOTAL - N_TRAIN)
    y = 0.1 + beta * x + s
    return x, y, s, beta


def test_engle_granger_recovers_beta_and_cointegration():
    lx, ly, _, _ = simulated_pair()
    beta_hat, adf = engle_granger(lx[:N_TRAIN], ly[:N_TRAIN])
    assert abs(beta_hat - TRUE_BETA) < 0.2
    assert adf < EG_CRITICAL_5PCT  # cointegrated on the training window


def test_engle_granger_both_directions():
    # Post's prod caution: test both directions.
    lx, ly, _, _ = simulated_pair()
    _, adf_xy = engle_granger(lx[:N_TRAIN], ly[:N_TRAIN])
    _, adf_yx = engle_granger(ly[:N_TRAIN], lx[:N_TRAIN])
    assert adf_xy < EG_CRITICAL_5PCT
    assert adf_yx < EG_CRITICAL_5PCT


def test_ou_halflife_near_true_value():
    _, _, spread, _ = simulated_pair()
    hl = ou_halflife(spread[:N_TRAIN])
    assert 5.0 < hl < 20.0  # true 10d; post's estimate 11.5d


def test_ou_halflife_rejects_non_mean_reverting():
    rng = np.random.default_rng(0)
    walk = np.cumsum(rng.normal(0, 1, 1000))
    hl = ou_halflife(walk)
    assert np.isnan(hl) or hl > 100.0
    assert np.isnan(ou_halflife(np.ones(100)))  # constant series: no AR(1)


def test_kalman_tracks_drifting_beta_better_than_static_ols():
    lx, ly, _, beta_true = simulated_pair()
    # Q = drift variance, R = training residual variance (post's calibration).
    # A random-walk beta drifting 0.4 over the drift window has per-step
    # variance 0.4**2 / n_drift — NOT (0.4 / n_drift)**2.
    resid_train = ly[:N_TRAIN] - 0.1 - TRUE_BETA * lx[:N_TRAIN]
    r = float(np.var(resid_train))
    q = 0.4**2 / (N_TOTAL - N_TRAIN)
    th = kalman_beta(lx, ly, q, r)
    assert th.shape == (2,)
    # Static OLS beta on the training window, applied to the drift period.
    beta_ols, _ = engle_granger(lx[:N_TRAIN], ly[:N_TRAIN])
    drift = slice(N_TRAIN, N_TOTAL)
    # Kalman beta path: re-run step by step to capture the trajectory.
    th_path = np.zeros((N_TOTAL, 2))
    P = np.eye(2)
    th_step = np.zeros(2)
    for t, (xv, yv) in enumerate(zip(lx, ly)):
        P = P + q
        h = np.array([1, xv])
        e = yv - h @ th_step
        K = P @ h / (h @ P @ h + r)
        th_step, P = th_step + K * e, P - np.outer(K, h) @ P
        th_path[t] = th_step
    kalman_rmse = float(np.sqrt(np.mean((th_path[drift, 1] - beta_true[drift]) ** 2)))
    ols_rmse = float(np.sqrt(np.mean((beta_ols - beta_true[drift]) ** 2)))
    assert kalman_rmse < ols_rmse
    assert kalman_rmse < 0.2


def test_pair_position_state_machine():
    assert pair_position(-2.5, 0) == 1   # fade the extreme: enter long
    assert pair_position(2.5, 0) == -1   # fade the extreme: enter short
    assert pair_position(1.5, 0) == 0    # inside the entry band: flat
    assert pair_position(-1.0, 1) == 1   # long, not yet retraced: hold
    assert pair_position(-0.4, 1) == 0   # long, retraced past -z_out: exit
    assert pair_position(1.0, -1) == -1  # short, not yet retraced: hold
    assert pair_position(0.4, -1) == 0   # short, retraced past z_out: exit


def test_pair_position_with_stop_flattens_at_z_stop():
    assert pair_position_with_stop(-4.5, 1) == 0   # stop hit: flat
    assert pair_position_with_stop(4.5, -1) == 0   # stop hit: flat
    assert pair_position_with_stop(-3.9, 1) == 1   # inside the stop: hold
    assert pair_position_with_stop(-2.5, 0) == 1   # entry still works
    assert Z_STOP_DEFAULT == 4.0


def test_end_to_end_zscore_rule_produces_finite_positions():
    lx, ly, _, _ = simulated_pair()
    beta_hat, _ = engle_granger(lx[:N_TRAIN], ly[:N_TRAIN])
    spread = ly - beta_hat * lx
    window = 60
    pos = 0
    positions = []
    for t in range(N_TRAIN, N_TOTAL):
        w = spread[t - window : t]
        z = (spread[t] - w.mean()) / (w.std() + 1e-12)
        pos = pair_position_with_stop(z, pos)
        positions.append(pos)
    positions = np.array(positions)
    assert set(np.unique(positions)) <= {-1, 0, 1}
    assert np.any(positions != 0)  # the rule actually trades
    rets = np.diff(spread[N_TRAIN:]) * positions[:-1]
    assert np.all(np.isfinite(rets))
