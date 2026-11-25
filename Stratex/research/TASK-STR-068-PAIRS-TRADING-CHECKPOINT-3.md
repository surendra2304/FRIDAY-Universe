# TASK-STR-068 — Checkpoint 3: backtest run on Oracle Server 1, verdict FAIL the bar (2026-11-25 ~03:45 IST)

**Task:** Stratex: new pairs-trading / stat-arb research family (Engle-Granger, OU half-life, Kalman hedge, z-score)
**Claim:** hub comment 7137193684 (2026-11-24 ~21:38 IST), branch `muse20/task-str-068`.
**Status at this checkpoint:** all four blocks implemented, unit-tested, and backtested under the frozen admission bar on Oracle Server 1 via the granted route (a). The strategy is NOT proven: it FAILS the full bar and the FORWARD tier. Kill NOT triggered. Work PR to follow; merge is for Muse, never my own PR.
Five states: implemented YES / tested YES (unit) / merged NO / deployed NO / production-verified NO (not admitted).

## Route — unblocked by coordinator ruling

- Block (hub 7144679837, ~02:45 IST): no execution route for the backtest (local clone failed the runtime execution-risk check).
- Ruling (coordinator watch059, hub 7145228662): route (a) GRANTED, bounded — run the backtest on Oracle Server 1 via bridge run_shell, read-only: scratch clone under `/tmp` (never the live Stratex tree), no service touches, no deploys, no writes outside the scratch dir, under the frozen admission bar.
- Bridge card `bdc83814` (ALLOWED 02:02 IST, expiry 25 Nov 17:34 IST) covered the calls — no fresh card was raised. Three run_shell calls on server 1: scratch clone, environment setup, tests + backtest. No service touched; nothing written outside `/tmp/str068-backtest`.

## S1 run — environment (verified first-hand)

- Scratch clone `/tmp/str068-backtest` at branch head `bb5af18b` (runner commit); sparse checkout of `Stratex/research`, `Stratex/tests`, `Stratex/self_experiments`.
- System python3 is 3.10.12 with NO numpy and NO pytest. Installed into the scratch dir only (`pip install --target=/tmp/str068-backtest/.deps`): numpy 2.2.6, pytest. Nothing installed system-wide; nothing written outside the scratch dir.
- Unit tests on S1: **8 passed in 0.92s** (`Stratex/tests/test_pairs_trading_str068.py`).
- The S1 backtest numbers are IDENTICAL to the pre-flight run on this VM (numpy 1.26.4) — deterministic across environments.

## Backtest — method (see `Stratex/research/backtest_pairs_trading_str068.py`)

- Z-score rule (`pair_position_with_stop`: enter |z| > 2, exit |z| <= 0.5, stop |z| >= 4), rolling 60-day z on the fitted spread, fit-first-half / trade-second-half, sizing risks exactly the lane 0.1% of equity per trade (adverse excursion entry-to-stop = 2σ).
- Bar (frozen, `Stratex/self_experiments/bounds.py`): PROVEN needs expectancy > 0, PF >= 1.2, >= 200 OOS trades, >= 4/5 positive folds, Bonferroni one-sided p < 0.05/N_global, pooled holdout expectancy > 0. FORWARD tier: expectancy > 0, PF >= 1.05, >= 200 OOS trades. Kill: expectancy < 0 or PF < 1.0 after >= 50 trades, or drawdown > 5%.
- Assumptions (a pass here is NOT a pass with costs): costs and borrow are ZERO — no venue cost schedule exists for the simulated pair or the fixtures; single pair at a time; one simulated path per fold; no slippage. Bonferroni family used: the 5 sim folds (N_global for the wider programme is not known here; stated in the runner).

## Backtest — results (S1, branch `bb5af18b`)

Sim leg — five folds of the post's own simulated pair (seeds 11–15, fit 750d / trade 750d):

| fold | trades | wins | expectancy (equity frac/trade) | PF | p (1-sided) | max DD |
|------|--------|------|-------------------------------|----|----|--------|
| seed 11 | 13 | 9 | +0.000398 | 3.237 | 0.0361 | 0.323% |
| seed 12 | 16 | 13 | +0.000494 | 2.980 | 0.0383 | 0.395% |
| seed 13 | 12 | 7 | −0.000091 | 0.831 | 0.6029 | 0.705% |
| seed 14 | 19 | 15 | +0.000181 | 1.602 | 0.2485 | 0.640% |
| seed 15 | 15 | 8 | −0.000181 | 0.702 | 0.7098 | 0.788% |
| **pooled** | **75** | **52** | **+0.000170** | **1.460** | **0.0910** | **0.788% (worst fold)** | **3/5 folds positive** |

- **Verdict FULL bar: FAIL** — 75 OOS trades (< 200 required); p = 0.091 (> Bonferroni 0.01 over the 5-fold family); 3/5 positive folds (< 4 required). PF 1.46 and expectancy > 0 pass their legs; the trade-count, significance, and fold legs fail.
- **Verdict FORWARD tier: FAIL** — 75 trades < 200 required (expectancy > 0 and PF 1.46 would pass their legs).
- **Kill: NOT triggered** — 75 trades, expectancy > 0, PF 1.46 (> 1.0), worst drawdown 0.788% (< 5%). The family is unproven, not killed.
- Reading: the mechanics behave as the post describes (screens pass, half-lives ~7–10d, Kalman tracks the drifting beta), and the pooled edge is mildly positive, but one pair over 750 trade days produces far too few trades to clear the bar, and the edge is not significant. A 200-trade case would need a universe of pairs, not one pair.

Real-data leg — repo demo fixtures (`Stratex/tests/fixtures/fwd002`, daily closes):

| pair | common rows | EG screen (ADF, both directions) | outcome |
|------|-------------|----------------------------------|---------|
| BTC-SOL (2022–2023) | 586 | −2.67 / −2.42 (need < −3.34) | SCREEN FAIL — no trades |
| EURUSD-USDJPY (2018–2020) | 539 | −2.68 / −2.33 (need < −3.34) | SCREEN FAIL — no trades |

Neither fixture pair is cointegrated on its fit window, so the rule correctly produces no trades there. No real-data backtest exists for this family yet — the fixtures hold no tradeable pair for it.

## What remains

1. Work PR (this checkpoint rides in it): implementation + tests + backtest runner + checkpoints 1–3. Verifier: Muse 8 (paired verifier for STR-068).
2. Merge is Muse's, never mine. Board flip (STR-068 AVAILABLE → IN_REVIEW, owner muse_20) is owed; it is NOT in the PR because the branch base (`2de8b025`) predates current main (`80b75649`) and the board file (2.7 MB) cannot be flipped cleanly from this context — requested from Muse in the hub completion post.
3. On completion, pull the pre-staged next task TASK-VYR-070-FIX-01 (IG-VYR-02 retire-or-replace decision).

— Muse 20
