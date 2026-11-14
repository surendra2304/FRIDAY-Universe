# TASK-STR-RD-001 — Stratex strategy R&D programme results

Owner mandate (2026-11-14): do not only backtest the existing strategies —
create new strategies, backtest each and every one, keep the most
profitable, and test EVERYTHING (exits, sizing, instruments, regime gates,
timeframes, execution) so Stratex takes the most profitable trades.

Method (identical discipline to TASK-STR-BT-001): walk-forward folds
W1–W5, judgement on out-of-sample trades only (entries 2024-07-01 →
2026-11-01), pooled BTC/ETH/SOL unless stated, Binance USDT-M taker costs
16 bps round trip, provenance-verified Binance mainnet data (hashes match
TASK-STR-BT-001's `data_provenance.json` exactly; 0 missing bars).

## Anti-Overfit Law (pre-registered, this programme)

Generating many strategies guarantees lucky-noise "winners" — that is
exactly how the factory manufactured its five. Therefore:

- every variant tried is **counted and disclosed** (per family, per stage);
- parameters are selected on **in-sample folds only**; judgement is OOS;
- **PROMOTION CANDIDATE** requires ALL of: OOS expectancy > 0, PF ≥ 1.2,
  ≥ 200 OOS trades, positive expectancy in ≥ 4 of 5 folds — **plus** a
  holdout check (expectancy > 0 on ≥ 2 of 3 symbols with ≥ 20 trades each,
  and no single symbol contributing > 80% of net profit);
- family headlines use honest walk-forward selection (per fold, rank the
  family's variants on in-sample trades only, judge the top-1 on the
  fold's OOS trades);
- anything below the bar is reported as **noise / watchlist** with its
  numbers, never dressed up.

## Stage 2 — adx_ema deep-dive (the one BT-001 lead)

BT-001 judged adx_ema as a bare engine. Production applies two downstream
filters (config `ADX_EMA_STRATEGY_V2`: `BTC_REGIME_FILTER: True`; spot
`LONG_ONLY`): SELL signals are rejected, and a BUY executes only when
BTCUSDT 4h close > its EMA(200). Filters applied at signal level, as
production does. Sanity gate: the bare replica reproduces BT-001's
governed row **exactly** (77 trades, +1.190%, PF 1.57).

### A. Production-faithful ablations (4h)

| config | OOS trades | WR | expectancy net | PF net |
|---|---|---|---|---|
| bare (BT-001) | 77 | 59.7% | +1.190% | 1.57 |
| + LONG_ONLY | 33 | — | +1.074% | 1.60 |
| + BTC regime gate | 76 | — | +1.131% | 1.53 |
| **production (both)** | **31** | — | **+0.880%** | **1.46** |

Production conditions keep the sign but shrink the edge and the sample:
31 trades is far below the 200-trade promotion bar. adx_ema remains a
**watchlist lead, not a candidate**.

### B. Timeframe sensitivity (production filters)

| timeframe | OOS trades | expectancy net | PF net |
|---|---|---|---|
| 2h | 76 | −0.318% | 0.84 |
| 4h (production) | 31 | +0.880% | 1.46 |
| 6h | 23 | +2.697% | 2.56 |
| 1d | 4 | −16.0% | 0.00 |

The edge is timeframe-fragile: 2h is negative, 1d is a 4-trade artefact.
6h shows the highest expectancy on only 23 trades — a watchlist note, not
evidence.

### C. ADX-threshold sensitivity (4h, production filters)

| threshold | OOS trades | expectancy net | PF net |
|---|---|---|---|
| > 15 | 52 | +0.641% | 1.30 |
| > 20 (production) | 31 | +0.880% | 1.46 |
| > 25 | 12 | +1.083% | 1.51 |
| > 30 | 2 | −0.475% | 0.87 |

No threshold rescues the sample size; stricter thresholds just trade less.

### D. Exit engineering on the same 31 production entries

| exit spec | expectancy net | PF net |
|---|---|---|
| bracket 3/3 (production; close-anchored) | +0.880% | 1.46 |
| bracket 2/2 | +0.625% | 1.50 |
| bracket 2/4 | +1.422% | 1.86 |
| bracket 3/6 | +1.464% | 1.54 |
| bracket 4/8 | +0.960% | 1.24 |
| ATR trail 3/3 | +2.225% | 2.59 |
| bracket 3/6 + trail 2 (arm 1) | +1.797% | 2.81 |
| bracket 3/3 + 30-bar time exit | +0.908% | 1.53 |
| bracket 3/3 + 60-bar time exit | +0.803% | 1.42 |

Trailing stops and wider targets roughly double expectancy **on the same
31 trades** — with n=31 these differences are within noise. Recorded as
hypotheses for the forward demo protocol (test trailing exits there), not
as findings.

## Stage 1 — discovery completion

In progress — see `results_rd/phase_rd_discovery.json` when complete.

## Stages 3–5

Pending; this file is updated per stage, one PR per stage.
