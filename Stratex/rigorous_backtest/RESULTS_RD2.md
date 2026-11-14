# TASK-STR-RD-002 — Stratex Mega-Grid R&D: Results

**Mandate (owner, 2026-11-15 ~02:22 IST, expanded ~02:43 IST):** RD-001's
search was too narrow. Research every asset class and timeframe where
honest data exists, create more strategies (batch-2, then batch-3 under
the expansion order), backtest everything properly, and test
combinations. Goal: find what is *genuinely* profitable for Stratex.

**Status at this revision:** Stage A (data) COMPLETE. Stage B in
progress. Stages C/D pending. This document is extended stage by stage;
the final synthesis (Stage D) replaces the interim sections.

## The Anti-Overfit Law — extended (binding on every number below)

- **Global trial counter.** Every configuration evaluated anywhere in
  RD-002 — grid cells, governed/discovery module cells, wf-select
  procedures, combinations, ensembles — is counted and added to
  RD-001's 116. The promotion bar rises with the counter.
- **Promotion bar.** Expectancy > 0 AND profit factor ≥ 1.2 AND ≥ 200
  out-of-sample trades AND ≥ 80% of walk-forward folds positive AND a
  per-asset-class untouched-holdout pass (breadth: ≥ 50% of active
  symbols positive, no symbol carrying > 50% of profit on panels with
  ≥ 5 symbols, and a never-tuned alphabetical subset of symbols
  positive on ≥ 30 trades) AND significance at the final global N:
  deflated Sharpe ratio ≥ 0.95 AND Bonferroni one-sided
  p < 0.05 / N_global. Near-bar results additionally face a 2×-cost
  sensitivity.
- Parameters are selected in-sample only; judgement is OOS-only.
  Walk-forward folds W1–W5 (OOS era 2024-07-01 → 2026-11-01) where the
  series allow; panels built from shorter history use the disclosed
  LATE profile (W2–W5, OOS from 2025-01-01).
- Combinations are judged on compounded equity + max drawdown, never
  per-trade averages alone.
- No production/governance/priors/engine changes; research area only;
  no live trading; **no synthetic data** — an unobtainable series is
  marked UNCOVERED with the reason.

## Stage A — Data (provenance first)

Full per-series table (bars, range, missing bars, per-file SHA-256 of
every source archive/response): `results_rd2/coverage.json` +
per-series sidecar manifests beside the cached series. 128 base series
files; derived timeframes (4h, 1d, 1wk) are resampled from base series
with complete-buckets-only rules.

| Class | Source | Series | Timeframes (base) | Range |
|---|---|---|---|---|
| Crypto (30 USDT-M pairs) | Binance Vision public archives (monthly klines, per-zip SHA-256) | 30 @ 1h; 12 @ 15m; 6 @ 5m | 1h / 15m / 5m (+ derived 4h/1d/1wk) | 1h: 2022-01 → 2026-10 (later for post-2022 listings: APT 2022-10, ARB 2023-03, OP/SUI/INJ per listing) |
| Forex (28 pairs: majors, minors, crosses) | Yahoo Finance chart API (real broker-quote aggregated series; per-series manifests) | 28 @ 1d; 28 @ 1h | 1d from 2018; 1h from 2024-11-15 (API depth limit ~730 days) | 1d: 2018 → 2026-11; 1h: 2024-11 → 2026-11 |
| Commodities (7 futures) | Yahoo Finance chart API | GOLD, SILVER, WTI, BRENT, NATGAS, COPPER, PLATINUM @ 1d + 1h | as forex | as forex |
| Indices (7) | Yahoo Finance chart API | SPX, NDX, DJI, RUT, FTSE, NIKKEI, DAX @ 1d; NDX/DJI/SPX @ 1h | as forex | as forex |

Gap accounting (audited, never interpolated): several crypto 1h series
share one identical 120-bar gap block (an archive-side hole, present
in the exchange's own monthly files); XRPUSDT 1h also 120. Yahoo 1h
"missing" counts are dominated by market closures (nights/weekends)
under the >2h-gap audit and are reported per series in coverage.json.
Yahoo rows with null OHLC are dropped and counted, never filled.

**Fold consequence:** panels derived from Yahoo 1h (forex/comm/idx at
4h/1h) start 2024-11-15, so their OOS folds are the LATE profile
(W2–W5). Everything else uses STANDARD W1–W5. Recorded per result row.

### UNCOVERED / UNTESTABLE — with reasons

- **Spot XAUUSD / XAGUSD via Yahoo** — the spot tickers returned 404.
  Metals are covered via COMEX futures (GC=F / SI=F) instead.
- **Dukascopy (forex tick/minute)** — not viable from the research
  sandbox: the datafeed answered 503 (rate-limit/bot protection) on
  essentially every request across repeated paced probes (one success
  in dozens of attempts). Not used; forex provenance rests on Yahoo.
- **Stooq** — served a bot-challenge page from this sandbox. Not used.
- **Forex carry family** — UNTESTABLE: no provenance-honest
  rate-differential series is obtainable from the available sources,
  and inventing one would violate the no-synthetic-data rule.
- **OANDA server-side pull** — not needed once Yahoo coverage proved
  complete for all 28 pairs; no server credentials were touched.

### Costs (disclosed, round-trip, applied per trade)

Crypto 16 bps (harness standard, as BT-001/RD-001). Forex majors
6 bps, minors/crosses 10 bps. GOLD 10, SILVER 14, WTI/BRENT 12,
NATGAS 20, COPPER 12, PLATINUM 14 bps. Indices 8 bps. Pairs trades
carry doubled two-leg costs. Exact per-symbol figures ship in
`rd2/costs2.py` and in every result row.

### Faithfulness anchor

Before any new result was trusted, the batch-2 signal code was run
against RD-001's own published cell (ts_momentum roc42, 4h,
BTC/ETH/SOL): 303 trades, expectancy 0.0024275740638451445, PF
1.0969220482985518 — **bit-identical** to RD-001's stage-3 table
(`results_rd2/sanity_checks.json`).

## Stage B — The Grid (in progress at this revision)

Batches: (1) RD-001's 28 variants generalized across classes/timeframes
+ batch-2 families (47 configs: cross-sectional momentum, dual
time-series momentum, turtle-2, volatility-targeted trend, filtered
forex mean-reversion, day-of-week, pairs stat-arb); (2) governed
modules as coded (bb_reversion, supertrend, adx_ema bare + production
config, factory_winner_1..5) and all 58 discovery modules, per class;
(3) **batch-3 (owner expansion order): 18 new families, 36 configs,
pre-declared in `results_rd2/batch3_declaration.json` before first
execution** — keltner_breakout, bollinger_trend, macd_trend,
psar_trend, rsi_momentum, stoch_reversion, ichimoku_trend, ha_trend,
linreg_trend, shock_breakout, bar_patterns, gap_daily,
turn_of_month (window redefined causally after a truncation test
proved the textbook form look-ahead), xs_reversal, xs_lowvol, pairs3,
session_breakout, vol_compression. Batch-3 runs no 15m/5m cells
(declared compute deferral; 4h/1d prioritised).

Every family's honest walk-forward selection procedure (pick the best
variant per fold on data before the fold, judge the next fold) is run
as the factory-procedure control alongside the fixed cells.

## Stages C/D

Pending — combinations (signal ensembles + portfolio weighting of the
best streams, judged on compounded equity and drawdown) and the final
computed synthesis with the global trial count, significance at the
final N, candidates or an explicit NONE, and forward-protocol entrant
recommendations.
