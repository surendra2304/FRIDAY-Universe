# TASK-STR-RD-006 — Pairs / Statistical Arbitrage: Pre-Declaration

Locked 2026-11-15 (IST), BEFORE any backtest execution. Claim: issue #35
comment 6890997830. Any deviation discovered necessary during the run is
disclosed in RESULTS_RD6.md as a deviation, never silently absorbed.

## Family

Pairs trading / statistical arbitrage on crypto: cointegration-screened
pairs, formation-frozen hedge ratio and spread moments, z-score
entry/exit, traded walk-forward. This is a NEW dedicated family for
Stratex research (RD-002 touched pairs only as small grid cells —
`pairs` in batch-2 and `pairs3` in batch-3; RD-006 is the full
cointegration treatment and is counted independently).

## Universe and data

- Symbols: CRYPTO30 exactly as in `rd2/panels.py` (BTC, ETH, SOL, BNB,
  XRP, DOGE, ADA, LTC, LINK, DOT, TRX, AVAX, NEAR, ATOM, UNI, ETC, BCH,
  FIL, APT, ARB, OP, INJ, SUI, XLM, HBAR, ALGO, VET, SAND, MANA, AAVE —
  all USDT-M perpetuals).
- Source: Binance Vision public archives, futures/um monthly klines,
  1h, 2022-01 through 2026-10 (the RD-002 source and era). Per-zip
  SHA-256 recorded in a manifest; hashes cross-checked against the
  RD-002 cache sidecars for every overlapping archive.
- Pairs: all C(30,2) = 435 unordered pairs. Orientation: log P_A is
  regressed on log P_B where A precedes B in the CRYPTO30 list order.
  Trading is two-sided in z, so orientation changes only the hedge
  parametrisation, not the opportunity set.
- 4h series: resampled from the 1h series, UTC-aligned complete buckets
  only (4 consecutive hourly bars), per RD-002 convention.
- Gaps: counted, never interpolated or filled. A pair/fold is
  DATA-SKIP (counted in the failure accounting) if either leg covers
  < 95% of expected bars in the formation window or the trading window.
  Pair series are built on the intersection of the two legs' timestamps.

## Walk-forward structure

- Judged era: 2024-07-01 → 2026-05-02, five equal folds of 134 days:
  W1 2024-07-01→2024-11-12, W2 2024-11-12→2025-03-26,
  W3 2025-03-26→2025-08-07, W4 2025-08-07→2025-12-19,
  W5 2025-12-19→2026-05-02 (exact boundaries computed and printed by
  the engine; the rule — 5 × 134d from 2024-07-01 — is what is locked).
- Formation window: the 365 days immediately preceding each fold start,
  same for both timeframes.
- Untouched holdout: 2026-05-02 → 2026-11-01, formation 2025-05-02 →
  2026-05-02. The holdout is evaluated ONCE, at the very end, and only
  for pair-configs that pass every other bar element. No screening,
  tuning, or selection decision ever touches holdout data.

## Screen (formation window only, per pair / timeframe / fold)

1. Engle–Granger step 1: OLS of log P_A on a constant and log P_B over
   the formation window → α, β, residuals e_t.
2. Engle–Granger step 2: ADF test on e_t — no-constant, no-trend
   regression Δe_t = ρ e_{t−1} + Σ_{i=1..p} γ_i Δe_{t−i} + ε_t, lag p
   chosen by BIC over p ∈ [0, p_max], p_max = min(48, ⌊12·(T/100)^¼⌋).
   Screen passes iff the ADF τ statistic < **−3.34** (MacKinnon
   Engle–Granger 5% asymptotic critical value, 2 variables, constant
   in the cointegrating regression; finite-sample adjustment at
   T ≥ 2,190 is < 0.01 and is ignored, disclosed here).
3. Half-life filter: AR(1) on the spread e_t, Δe_t = λ e_{t−1} + ε_t,
   HL = −ln 2 / λ bars; require λ < 0 and 6 ≤ HL ≤ 240 bars at 1h
   (6 h – 10 d), 6 ≤ HL ≤ 120 bars at 4h (1 d – 20 d).

A pair trades in a fold iff it passes BOTH screen steps in that fold's
formation window. Screen outcomes for every pair/fold are recorded —
pairs that pass early and break later are failure-accounting results.

## Trading rule (per selected pair / fold; α, β, μ = mean(e), σ = sd(e) frozen from formation)

- spread_t = log P_A,t − α − β·log P_B,t; z_t = (spread_t − μ)/σ,
  computed on bar close t. All executions at bar t+1 OPEN prices of
  both legs (no same-bar fills, no lookahead).
- Entry configs (the ONLY two variants): E ∈ {2.0, 2.5}.
  z_t ≤ −E → long spread; z_t ≥ +E → short spread.
- Exit: z crosses 0 against the position (long spread exits when
  z ≥ 0; short when z ≤ 0); stop: |z| ≥ 4.0 adverse (long: z ≤ −4;
  short: z ≥ +4); fold end → flat. One open position per pair-config;
  re-entry only after flat, on a fresh entry signal.
- Position/P&L (exact two-leg, no log approximation): quantities
  q_A = 1/(P_A + β·P_B), q_B = β·q_A at entry execution prices
  (gross notional = 1.0). Long-spread P&L = q_A·ΔP_A − q_B·ΔP_B
  between execution bars; short-spread negated. Trade return = P&L / 1.0.
- Costs: **32 bps round trip per trade**, subtracted from every trade
  return (RD-002 harness convention: crypto 16 bps × two legs).
  2×-cost sensitivity: every metric also computed at 64 bps.

## Trial count

N_RD6 = 435 pairs × 2 timeframes × 2 entry configs = **1,740 trials**.
Every pair-config the screen could have selected counts, whether or
not it ever traded — the screen is part of the strategy, and reporting
only traded pairs would understate the search. Context: the global
counter stood at 1,557 after RD-002; RD-003 is running concurrently
and adds its own trials. Verdicts are computed at N = 1,740 and
additionally checked at the conservative global floor
N = 1,557 + 1,740 = 3,297 (RD-003 additions excluded — disclosed).

## The bar (standing RD-002 promotion bar, operationalised for pairs)

A pair-config is PASS iff ALL hold on folds W1–W5 (net of 32 bps):
- expectancy > 0 AND profit factor ≥ 1.2 AND ≥ 200 OOS trades;
- traded in ≥ 3 of 5 folds AND ≥ 80% of traded folds net-positive;
- one-sided t-test on per-trade net returns: Bonferroni p < 0.05/N at
  N = 1,740 (a passer that fails at N = 3,297 is flagged as such);
- deflated Sharpe ratio ≥ 0.95 at N = 1,740 (Bailey & López de Prado;
  cross-trial Sharpe variance estimated over all pair-configs with
  ≥ 30 trades — disclosed approximation);
- 2×-cost profit factor ≥ 1.0;
- holdout (single final pass): expectancy > 0 AND PF ≥ 1.0 AND
  ≥ 20 trades.

WATCHLIST: expectancy > 0, PF ≥ 1.2, ≥ 200 trades, fold conditions met,
but significance, DSR, 2×-cost, or holdout fails (RD-002 usage).
FAIL: any other judged config (≥ 30 trades). INSUFFICIENT: < 30 trades.
Procedure-level verdicts: all screen-selected trades pooled per
(timeframe, config) and judged with the same metrics, reported
alongside the per-pair verdicts.

## Failure accounting (required output)

Per fold/timeframe: pairs screened, ADF passes, half-life passes,
DATA-SKIPs, pairs traded. Persistence distribution (in how many folds
each pair was selected). Breakdown list: pairs selected in ≥ 1 fold
whose screen later fails, and pairs whose traded folds turn negative
after positive ones. Aggregate pooled result of the whole procedure —
the honest "does pairs stat-arb work at all here" number.

## Machinery validation (before any market number is trusted)

The ADF/Engle–Granger implementation (hand-written, numpy/scipy —
statsmodels is not installable in this sandbox) is validated on
synthetic series used ONLY as test fixtures: (a) two independent
random walks must rarely pass the screen; (b) a constructed
cointegrated pair must pass with τ ≪ −3.34 and a recovered half-life
near the constructed value; (c) ADF on a stationary AR(1) must reject
strongly, on a pure random walk must not. Fixture results are reported
in RESULTS_RD6.md. Synthetic data is never used as market evidence.

## Scope

Research only. No production code, strategy registry, config, or
daemon changes. Passers, if any, are handed to the coordinator for the
forward-demo decision under the owner's standing rule; nothing here
authorises live trading.
