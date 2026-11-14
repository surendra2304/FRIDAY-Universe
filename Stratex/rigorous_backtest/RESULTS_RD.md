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
Research only — no production or governance files were touched.

## Anti-Overfit Law (pre-registered for this programme)

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

**Programme total: 116 configurations in the final ranked table
(`results_rd/stage5_synthesis.json`), 92 with OOS trades — spanning the
BT-001 governed set and factory procedure, all 58 discovery modules, 20
adx_ema deep-dive configurations, and 28 new Stage-3 variants.**

## VERDICT: ZERO PROMOTION CANDIDATES

Nothing — existing, discovered, deep-dived, or newly created — clears the
pre-registered bar. Nothing even clears the bar before the holdout check
(`passed_bar_failed_or_no_holdout` is also empty). The top of the ranked
table is entirely small-sample adx_ema configurations (23–77 trades) —
the exact winner's-curse shape the law exists to catch.

The watchlist (positive OOS expectancy, below the bar, in ranked order of
evidence quality) is:

| entry | OOS trades | expectancy | PF | folds + | why not a candidate |
|---|---|---|---|---|---|
| adx_ema production-faithful (4h) | 31 | +0.880% | 1.46 | 3/5 | 31 trades ≪ 200; folds 3/5 |
| adx_ema bare (BT-001 replica) | 77 | +1.190% | 1.57 | 5/5 | not the production configuration; 77 ≪ 200 |
| strategy_volume_breakout (1d, discovery) | 32 | +2.020% | 1.28 | 3/5 | 32 trades; folds 3/5 |
| mtf_confluence h4_native_ema200 (new) | 146 | +0.404% | 1.18 | 2/5 | PF < 1.2; holdout FAIL (BTC 88% of profit) |
| ts_momentum roc42_4h (new) | 303 | +0.243% | 1.10 | 2/5 | PF < 1.2; holdout FAIL (SOL 97%; W3–W5 negative) |
| strategy_volatility_breakout (discovery) | 520 | +0.131% | 1.07 | 3/5 | PF < 1.2 |
| ts_momentum roc168_1h (new) | 678 | +0.082% | 1.07 | 3/5 | PF < 1.2; holdout FAIL (SOL 84%) |
| strategy_choppiness_breakout (discovery) | 940 | +0.074% | 1.05 | 3/5 | PF < 1.2 |
| strategy_vol_regime (discovery) | 2,128 | +0.050% | 1.04 | 3/5 | PF < 1.2 |
| strategy_atr_breakout (discovery) | 870 | +0.011% | 1.01 | 0/5 | pooled-positive with NO positive fold — weighting artefact |

## Stage 1 — discovery map completed (the 51 BT-001 leftovers)

All 58 discovery modules now have a final status
(`results_rd/phase_rd_discovery.json`): **34 EVALUATED** (181,615 OOS
trades in total), 9 NOT_EVALUABLE (no callable `get_signal` — these
modules cannot be taking trades through the standard path at all),
9 UNTESTABLE (non-causal features or per-bar compute beyond the 900 s
budget), 4 NO_TRADES, 2 BROKEN. Of the 34 evaluated, 29 have negative
OOS expectancy; the 5 positives are the watchlist rows above — every one
far below the promotion bar. The discovery library, like the governed
set before it, contains no honest edge at these costs.

## Stage 2 — adx_ema deep-dive (the one BT-001 lead)

BT-001 judged adx_ema as a bare engine. Production applies two downstream
filters (config `ADX_EMA_STRATEGY_V2`: `BTC_REGIME_FILTER: True`; spot
`LONG_ONLY`): SELL signals are rejected, and a BUY executes only when
BTCUSDT 4h close > its EMA(200). Filters applied at signal level, as
production does. Sanity gate: the bare replica reproduces BT-001's
governed row **exactly** (77 trades, +1.190%, PF 1.57).

### A. Production-faithful ablations (4h)

| config | OOS trades | expectancy net | PF net |
|---|---|---|---|
| bare (BT-001) | 77 | +1.190% | 1.57 |
| + LONG_ONLY | 33 | +1.074% | 1.60 |
| + BTC regime gate | 76 | +1.131% | 1.53 |
| **production (both)** | **31** | **+0.880%** | **1.46** |

Production conditions keep the sign but shrink the edge and the sample:
31 trades is far below the 200-trade promotion bar.

### B. Timeframe sensitivity (production filters)

| timeframe | OOS trades | expectancy net | PF net |
|---|---|---|---|
| 2h | 76 | −0.318% | 0.84 |
| 4h (production) | 31 | +0.880% | 1.46 |
| 6h | 23 | +2.697% | 2.56 |
| 1d | 4 | −16.0% | 0.00 |

The edge is timeframe-fragile: 2h is negative, 1d is a 4-trade artefact.
6h shows the highest expectancy on only 23 trades — a watchlist note.

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
hypotheses for the forward demo protocol, not as findings.

## Stage 3 — NEW strategy creation, batch 1 (28 variants, all disclosed)

Seven new families with pre-declared grids (declared in `rd/stage3.py`
before the run). Family headline = honest walk-forward selection.
Per-variant rows: `results_rd/stage3_rows/`.

| family | variants | wf-select OOS trades | wf-select expectancy | wf-select PF |
|---|---|---|---|---|
| donchian_turtle | 6 | 1540 | −0.182% | 0.88 |
| zscore_reversion | 7 | 1815 | −0.169% | 0.84 |
| vol_adaptive_trend | 4 | 504 | −0.063% | 0.96 |
| mtf_confluence | 3 | 302 | −0.171% | 0.90 |
| volume_breakout | 2 | 1965 | −0.091% | 0.94 |
| ts_momentum | 4 | 597 | **+0.054%** | **1.04** |
| session_effects | 2 | 1859 | −0.216% | 0.63 |

Only three individual variants finished positive (mtf h4_native +0.404%,
ts_momentum roc42_4h +0.243%, roc168_1h +0.082%) and all three fail the
holdout check (one symbol = 84–97% of profit; positive in only 2–3 of 5
folds). Session effects are strongly negative (PF 0.60–0.70). 1h mean
reversion, breakouts and EMA-cross trend all lose ~0.1–0.2%/trade to
costs on ~zero gross edge — BT-001's central finding, replicated on new
code. The only region with any pulse is slow trend/momentum at 4h — the
same region as adx_ema — and even there the positives are one-symbol,
two-fold artefacts at this sample size.

## Stage 4 — "everything else" experiments

Subjects: the top-2 Stage-3 signals (mtf h4_native, ts_momentum
roc42_4h), adx_ema production, and the near-breakeven discovery modules
atr_breakout / adx_trend. Full data: `results_rd/stage4_experiments.json`.

**E1 — cost sensitivity** (expectancy at round-trip cost): execution
quality is NOT the binding constraint anywhere.

| subject | 16 bps (taker) | 10 bps | 6 bps | 3 bps | 1.5 bps (maker) |
|---|---|---|---|---|---|
| adx_ema production | +0.880% | +0.941% | +0.981% | +1.011% | +1.026% |
| mtf h4_native | +0.404% | +0.464% | +0.504% | +0.534% | +0.549% |
| ts_momentum roc42_4h | +0.243% | +0.303% | +0.343% | +0.373% | +0.388% |
| atr_breakout (870 tr) | +0.011% | +0.071% | +0.111% | +0.141% | +0.156% |
| adx_trend (1,058 tr) | −0.004% | +0.057% | +0.097% | +0.127% | +0.142% |

(Module rows: signals extracted once with a replica of the harness
extraction; the replica reproduces BT-001's rows EXACTLY at baseline
costs for both modules.) Even at near-zero costs the best high-count
signal (adx_trend) reaches only +0.14%/trade — the gross edges are
~0.1%/trade where they exist at all. Maker execution would help at the
margin; it cannot manufacture an edge.

**E2 — instrument selection:** every pooled positive decomposes into one
carrying symbol: adx_ema production = SOL +1.93% (9 trades) / BTC +0.83%
(13) / ETH −0.10% (9); roc42_4h = SOL +1.46% with BTC −0.59% over 109
trades; mtf h4 = BTC +1.35% / ETH −0.30%. There is no instrument subset
with a broad-based positive — keep/drop decisions on these samples would
be curve-fitting.

**E3 — regime gating** (on mtf h4_native, which already has an internal
EMA200 filter): no gate +0.404% PF 1.18 (146 trades); production-style
BTC gate +0.376% PF 1.16 (143); aligned gate +0.547% PF 1.24 (132).
Gating neither creates nor destroys the (sub-bar) result at this sample.

**E4 — sizing / compounding** (notional weight w over the time-ordered
OOS trade sequence): sizing shapes the ride, never the edge. adx_ema
production compounds +27.9% at w=1.0 (max DD −15.1%) — on 31 trades.
mtf h4 at w=2.0 turns NEGATIVE (−24.7%, DD −79.2%) through volatility
drag. Most instructive: roc42_4h has positive per-trade expectancy
(+0.243%) yet compounds to **−61.0% at w=1.0** (DD −81.3%) — arithmetic
expectancy is not geometric growth when variance is high and losses
cluster. Any forward protocol must judge compounded equity, not just
per-trade means.

**E5 — timeframe selection** (mtf family, honest wf-selection per
timeframe): 15m −0.167% PF 0.76 (3,252 trades); 1h −0.171% PF 0.90;
4h +0.464% PF 1.19 (214). The family's only non-negative timeframe is
4h — the same conclusion as adx_ema's Stage-2 sensitivity and the
opposite of the library's 5m/15m centre of gravity.

**E6 — exit engineering** (on mtf h4_native entries): the variant's own
bracket 2/4 (+0.404%, PF 1.18) beats every alternative tried — bracket
3/6 −0.838%, trails +0.13…+0.19%, time exits ≈ 0/negative. Exit
engineering is signal-specific (it appeared to help adx_ema's 31
entries, it hurts here) and at these sample sizes none of it is
distinguishable from noise.

## Stage 5 — synthesis and recommendation

Ranked table of all 116 configurations: `results_rd/stage5_synthesis.json`
(computed by `rd/stage5.py`; the candidate list is whatever the code
computes — it computed none).

**Forward-demo-protocol recommendation:**

1. **No strategy graduates.** Nothing in the existing library, the
   discovery set, or the 28 new variants earns promotion. The honest
   statement is that on 28 months of provenance-verified data, at real
   costs, Stratex has no demonstrated edge — consistent with its
   exchange-verified forward record (demo losses).
2. **Watchlist for evidence accumulation only** (demo, ledger-measured,
   no conclusions until the samples grow): adx_ema in its
   production-faithful configuration, with the ATR-trail exit variant
   tracked as a second series (Stage 2D hypothesis); the mtf/ts-momentum
   4h variants as secondary series. All are labelled sub-bar.
3. **The forward protocol's arithmetic needs widening:** the only
   non-negative region (4h trend/momentum) produces ~1 trade/month
   pooled across 3 symbols — a ≥100-trade bar would take ~7 years. If
   the owner wants a feasible forward test for this family, the
   instrument universe must widen (more USDT pairs) or the bar must be
   restated in years. Higher-frequency trading is not the shortcut: at
   5m/15m/1h every family tested loses to costs on ~zero gross edge.
4. **Judge the forward window on compounded equity** (E4), with the
   existing kill criteria unchanged.

Re-runs: every stage is a module under `Stratex/rigorous_backtest/rd/`
(`stage1 --combine`, `stage2`, `stage3`, `stage4`, `stage5`); all read
the hash-verified cache produced by `rigorous_backtest.run_all`'s
dataset loader. Deterministic: governed and module replicas in this
programme reproduce BT-001's published numbers exactly.
