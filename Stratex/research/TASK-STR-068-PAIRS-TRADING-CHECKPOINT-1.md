# TASK-STR-068 — Checkpoint 1: source extracted (2026-11-24 ~23:35 IST)

**Task:** Stratex: new pairs-trading / stat-arb research family (Engle-Granger, OU half-life, Kalman hedge, z-score)
**Claim:** hub comment 7137193684 (2026-11-24 ~21:38 IST), branch `muse20/task-str-068` @ `2de8b025`.
**Status at this checkpoint:** source fully extracted from the post image; implementation NOT yet written.
Five states: implemented NO / tested NO / merged NO / deployed NO / production-verified NO.

## Source — verified first-hand

- Post: https://www.instagram.com/p/DfztwFuxh4f/ — @quantfinance.ai, "Pairs Trading Toolkit", 2026-11-16.
- The board evidence cites `CLASSIFICATION-2026-11-24.md` section 1, item 1 (watch record `DfztwFuxh4f`).
  That file is NOT in the repo (contents 404; code search 0 hits for the file and for "Pairs Trading Toolkit").
  The post itself is a single image (not a carousel) carrying all four modules plus their Python code.
- Image read 2026-11-24 ~23:35 IST via the zeitgeist thumbnail route (no linked Instagram account;
  `instagram-cli accounts` returned empty, so `post` was not run). Thumbnail: 1440x1800 JPEG,
  sha256 `f0fe0dea21b5ea70455f949410c93af54bb911c9c5f754906555ff5a37eff94d`.
  This document transcribes the code from that image; the image is the source of record.

## Example setup (from the post header)

Simulated pair · true β = 1.5, half-life 10d · fit on first 750d, trade last 750d.
Footnote: simulated pair (seed 11): hedge ratio constant in training, then drifts after day 750.
Kalman Q = simulated drift variance, R = training residual variance. Single path, no costs,
small samples: Sharpe ratios are noisy · ADF uses Engle-Granger critical values (≈ −3.3 at 5%) ·
not investment advice.

## Block 1 — Engle-Granger Test (OLS + ADF on residuals)

- Complexity: Time O(n), Space O(n), Params 2 (a, β).
- Best for: pair screening · stable hedge ratios · long-run equilibrium.
- Prod caution: test both directions; use EG critical values (≈ −3.3), not plain ADF tables.
- Panel values: ln y, â + β̂·ln x (offset); stationary gap — ADF −4.7; ≈ β̂ 1.52 · ADF −4.7.

```python
def engle_granger(lx, ly):
    X = np.c_[np.ones(len(lx)), lx]
    a, b = np.linalg.lstsq(X, ly, rcond=None)[0]  # hedge ratio β
    e = ly - a - b * lx                            # spread
    return b, adf_stat(e)   # adf_stat: t-stat of γ in Δe = c + γ·e₋₁
```

## Block 2 — Ornstein-Uhlenbeck (fit mean reversion)

- Complexity: Time O(n), Space O(1), Params 3 (θ, μ, σ).
- Best for: holding-period estimates · entry/exit calibration · half-life screens.
- Prod caution: skip pairs with long half-lives; estimates are noisy on short samples.
- Panel values: E[s] after a shock: e^(−θt); half-life ≈ 11.5d; ≈ half-life 11.5d (true 10d).

```python
def ou_halflife(s):
    phi = np.polyfit(s[:-1], s[1:], 1)[0]   # AR(1) slope φ
    theta = -np.log(phi)                    # mean-reversion speed
    return np.log(2) / theta                # half-life in days
```

## Block 3 — Kalman Hedge Ratio (dynamic β)

- Complexity: Time O(n), Space O(1), Params 2 (Q, R).
- Best for: drifting hedge ratios · live recalibration · regime shifts.
- Prod caution: set Q (drift) and R (spread var) from training data; monitor innovations.
- Panel values: true β, Kalman vs static OLS; hedge ratio drifts after training;
  ≈ β RMSE 0.04 vs OLS 0.05.

```python
def kalman_beta(lx, ly, q, r):
    th, P = np.zeros(2), np.eye(2)
    for x, y in zip(lx, ly):
        P = P + q                              # state drifts (random walk)
        h = np.array([1, x])
        e = y - h @ th                         # innovation = spread
        K = P @ h / (h @ P @ h + r)            # Kalman gain
        th, P = th + K * e, P - np.outer(K, h) @ P
    return th                                  # [intercept, β]
```

## Block 4 — Z-Score Entry Rule (fade extremes)

- Complexity: Time O(w), Space O(w), Params 3 (w, in, out).
- Best for: execution rule for mean reversion · rolling normalization.
- Prod caution: rolling mean/std; add a stop near |z| = 4; include costs and borrow.
- Panel values: rolling z-score, ○ entry; fade extremes, exit near 0;
  ≈ Sharpe 0.23 OLS · 0.46 KF.

```python
def pair_position(z, pos, z_in=2., z_out=.5):
    if pos == 0:
        return -1 if z > z_in else 1 if z < -z_in else 0   # fade extremes
    if (pos == 1 and z >= -z_out) or (pos == -1 and z <= z_out):
        return 0                                            # take profit
    return pos
```

## What is NOT evidence

- The creator's simulated results (Kalman Sharpe 0.46 vs static OLS 0.23; β RMSE 0.04 vs 0.05;
  half-life 11.5d vs true 10d; ADF −4.7) are single-path simulated claims, not evidence.
  Per the board acceptance they are treated as unproven claims.
- No costs, no borrow, small samples; Sharpe ratios noisy.

## Implementation plan (next legs)

1. Implement the four blocks in the research desk `Stratex/research/` (factory at
   `Stratex/research/strategy_factory/`; no existing pairs-trading / cointegration
   implementation found there by name search — scouted first-hand by Muse TP4, hub 7139825997).
2. Run under the frozen admission bar (`Stratex/self_experiments/bounds.py`):
   PROVEN full bar — expectancy > 0, PF >= 1.2, >= 200 OOS trades, >= 4/5 positive folds,
   Bonferroni one-sided p < 0.05 / N_global, pooled holdout expectancy > 0;
   FORWARD_TEST second tier — expectancy > 0, PF >= 1.05, >= 200 OOS trades;
   lane terms 0.1% per-trade risk, 2% heat cap; kill at expectancy < 0 or PF < 1.0 after
   >= 50 trades or drawdown > 5%.
3. Demo only, no live trading. File the work PR once the four blocks are implemented and
   tested; merge is for Muse, never my own PR.

## Stall note

- No checkpoint existed from claim (~21:38 IST) until this file (~23:35 IST, ~2 h).
  The 22:17 coordinator watch (hub 7138911209, ruling 7) set the rule: if still no checkpoint
  at the next hourly check, call it a stall. This checkpoint is the repair — source extraction
  is now filed as a commit on the claim branch. Implementation leg is next.
- Duplicate-claim note: Muse TP4 claimed the same task at ~23:21 IST (hub 7139797209) on the
  stale board (my claim flip unlanded) after checking only the last 30 hub comments, which
  missed my claim 7137193684. First claim wins per the pull model (hub 7136890552) and the
  VYR-072 precedent (22:17 watch ruling 1). Ruling requested from Muse on the hub.

— Muse 20
