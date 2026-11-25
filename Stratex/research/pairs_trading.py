"""
Stratex/research/pairs_trading.py — Pairs Trading Toolkit (TASK-STR-068).

The four blocks of the "Pairs Trading Toolkit": Engle-Granger cointegration
screen, Ornstein-Uhlenbeck half-life, Kalman dynamic hedge ratio, and the
z-score entry rule.

Source: Instagram post https://www.instagram.com/p/DfztwFuxh4f/
(@quantfinance.ai, "Pairs Trading Toolkit", 2026-11-16). The post is a single
image carrying all four modules plus their Python code; the code below is a
transcription of that image (see Stratex/research/
TASK-STR-068-PAIRS-TRADING-CHECKPOINT-1.md). The image is the source of
record — the board evidence cites CLASSIFICATION-2026-11-24.md, which is not
in the repo.

The creator's simulated results (Kalman Sharpe 0.46 vs static OLS 0.23;
beta RMSE 0.04 vs 0.05; half-life 11.5d vs true 10d; ADF -4.7) are single-path
simulated claims, NOT evidence. Per the board acceptance they are treated as
unproven claims. This module implements the mechanics only; any strategy built
on it must pass the frozen admission bar (Stratex/self_experiments/bounds.py)
on demo data before it counts for anything.

Production cautions from the post, honoured here:
- Engle-Granger: test both directions; use Engle-Granger critical values
  (approx -3.34 at 5% for the two-variable case), NOT plain ADF tables.
- OU half-life: skip pairs with long half-lives; estimates are noisy on
  short samples.
- Kalman: set Q (drift) and R (spread variance) from training data; monitor
  innovations.
- Z-score rule: rolling mean/std; add a stop near |z| = 4; include costs
  and borrow.

Demo only. No live trading.
"""

import numpy as np

# Engle-Granger 5% critical value (approx) for the two-variable case.
# Plain ADF tables do NOT apply to residuals of an estimated cointegrating
# regression — the post's prod caution.
EG_CRITICAL_5PCT = -3.34

# Default stop for the z-score rule, per the post's prod caution ("add a stop
# near |z| = 4").
Z_STOP_DEFAULT = 4.0


def _adf_stat(e):
    """t-stat of gamma in the regression  Δe = c + γ·e₋₁.

    This is the ``adf_stat`` helper the post's ``engle_granger`` calls but does
    not define: the Dickey-Fuller t-statistic on the lagged residual, with an
    intercept and no lagged differences. Returns NaN when the series is too
    short to regress.
    """
    e = np.asarray(e, dtype=float)
    if e.size < 4:
        return float("nan")
    de = np.diff(e)
    x = e[:-1]
    X = np.c_[np.ones(x.size), x]
    coef, residuals, _, _ = np.linalg.lstsq(X, de, rcond=None)
    y_hat = X @ coef
    resid = de - y_hat
    dof = x.size - 2
    if dof <= 0:
        return float("nan")
    sigma2 = float(resid @ resid) / dof
    if sigma2 <= 0:
        return float("nan")
    xtx_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(sigma2 * xtx_inv[1, 1])
    if se == 0:
        return float("nan")
    return float(coef[1] / se)


def engle_granger(lx, ly):
    """Engle-Granger test (OLS + ADF on residuals). Block 1 of the post.

    Fits ``ly = a + beta * lx`` by OLS and runs the ADF statistic on the
    spread (residual). Returns ``(beta, adf_stat)``. A pair screens as
    cointegrated when ``adf_stat`` is below the Engle-Granger critical value
    (``EG_CRITICAL_5PCT`` ≈ -3.34 at 5%), tested in BOTH directions — the
    post's prod caution — i.e. call this with (lx, ly) and with (ly, lx).
    """
    lx = np.asarray(lx, dtype=float)
    ly = np.asarray(ly, dtype=float)
    X = np.c_[np.ones(len(lx)), lx]
    a, b = np.linalg.lstsq(X, ly, rcond=None)[0]  # hedge ratio beta
    e = ly - a - b * lx                            # spread
    return float(b), _adf_stat(e)   # adf_stat: t-stat of γ in Δe = c + γ·e₋₁


def ou_halflife(s):
    """Ornstein-Uhlenbeck half-life. Block 2 of the post.

    Fits an AR(1) to the spread and converts the slope to a half-life in the
    same time units as the input (days for daily data). Returns NaN when the
    fitted slope is not in (0, 1), i.e. the series shows no mean reversion
    (phi <= 0) or is explosive (phi >= 1) — such pairs are skipped, per the
    post's prod caution on long/noisy half-lives.
    """
    s = np.asarray(s, dtype=float)
    if s.size < 3 or float(np.std(s)) < 1e-12:
        return float("nan")  # constant series: no AR(1) to fit
    phi = np.polyfit(s[:-1], s[1:], 1)[0]   # AR(1) slope φ
    if phi <= 0 or phi >= 1:
        return float("nan")
    theta = -np.log(phi)                    # mean-reversion speed
    return float(np.log(2) / theta)         # half-life in days


def kalman_beta(lx, ly, q, r):
    """Kalman dynamic hedge ratio. Block 3 of the post.

    Random-walk state [intercept, beta] updated one observation at a time.
    ``q`` is the drift variance and ``r`` the spread (observation) variance —
    both set from training data, per the post's prod caution.

    NOTE (source fidelity): the post's code adds the scalar ``q`` to the whole
    covariance matrix (``P = P + q``), i.e. to every entry including the
    off-diagonals. This transcription keeps that verbatim; the textbook form
    would add ``q`` to the diagonal only (``P + q * I``). The difference is
    small for the small ``q`` the post uses, but a later reviewer may want the
    diagonal form — do not silently "fix" it without noting the change.
    """
    lx = np.asarray(lx, dtype=float)
    ly = np.asarray(ly, dtype=float)
    th, P = np.zeros(2), np.eye(2)
    for x, y in zip(lx, ly):
        P = P + q                              # state drifts (random walk)
        h = np.array([1, x])
        e = y - h @ th                         # innovation = spread
        K = P @ h / (h @ P @ h + r)            # Kalman gain
        th, P = th + K * e, P - np.outer(K, h) @ P
    return th                                  # [intercept, β]


def pair_position(z, pos, z_in=2., z_out=.5):
    """Z-score entry rule (fade extremes). Block 4 of the post, verbatim.

    ``pos`` is the current position (-1, 0, 1); returns the new position.
    Enter when |z| crosses ``z_in`` (fade the extreme), exit near 0 when z
    retraces to ``z_out``. No stop is built into the post's function — see
    ``pair_position_with_stop`` for the post's prod caution (stop near
    |z| = 4).
    """
    if pos == 0:
        return -1 if z > z_in else 1 if z < -z_in else 0   # fade extremes
    if (pos == 1 and z >= -z_out) or (pos == -1 and z <= z_out):
        return 0                                            # take profit
    return pos


def pair_position_with_stop(z, pos, z_in=2., z_out=.5, z_stop=Z_STOP_DEFAULT):
    """Z-score rule with the post's prod-caution stop: exit when |z| >= z_stop.

    Identical to ``pair_position`` except an open position is flattened the
    moment the z-score reaches the stop level — the spread has run away
    instead of reverting, so the mean-reversion premise is broken.
    """
    if pos != 0 and abs(z) >= z_stop:
        return 0
    return pair_position(z, pos, z_in=z_in, z_out=z_out)
