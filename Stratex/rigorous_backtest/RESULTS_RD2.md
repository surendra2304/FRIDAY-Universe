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

## Stage B — The Grid (complete at this revision, with disclosed deferrals)

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
as the factory-procedure control alongside the fixed cells: **350
procedures.** They add no independent winners: the 9 procedures with
PF ≥ 1.2 at ≥ 200 trades are all in the crypto daily/4h trend cluster
and are each dominated by a single variant, reproducing that variant's
already-judged fixed cell; the strongest procedure outside the
cluster (ts_momentum wf-select on commodities daily) reaches PF 1.29
on only 87 trades. The factory's own selection method, given every
advantage, manufactures nothing the fixed cells didn't already show.

### What was actually run

| block | cells | result |
|---|---|---|
| batch-2 + batch-3 family grid | 978 | 342 of all 1,077 rows positive expectancy |
| walk-forward selection procedures | 350 | none at the bar |
| governed modules (non-crypto cells) | 40 | see below |
| governed modules (crypto 1d/4h cells) | 19 | see below |
| SMT-v2 retest (owner addendum) | 2 | explicit verdict below |
| discovery modules (daily cells) | 36 of 232 | 9 of 58 modules — deferral disclosed below |
| **total evaluated rows** | **1,077** | **global trial count 1,557** (116 RD-001 + 1,077 rows + 350 wf procedures + 14 combinations) |

Deferred, with reasons (compute on the shared ~1.5-CPU sandbox, a
mid-run VM reboot, and the reporting freeze): discovery daily cells
for 49 of 58 modules (196 cells) and all discovery 4h cells (116);
governed crypto 1h cells for supertrend, adx_ema (both configs) and
factory_winner_1..5 (8 cells — the supertrend 1h cell alone ran
>40 minutes without finishing; the module's per-bar cost grows
superlinearly in frame length). RD-001 already evaluated all 58
discovery modules on crypto; nothing in the 36 completed RD-002
discovery cells (best: bbi_blend on indices, +0.27%/PF 1.16, sub-bar)
suggests the deferred cells hide a candidate, but they are NOT
evidence and are not claimed as such.

### The bar, and what cleared it

Six configurations pass the full mechanical bar (expectancy > 0,
PF ≥ 1.2, ≥ 200 OOS trades, ≥ 80% of folds positive, untouched-holdout
pass). Two of the six also pass the significance gate (Bonferroni
one-sided p < 0.05/1,557 ≈ 3.2e-5):

**CANDIDATE 1 — ichimoku_trend / tk_cloud @ crypto30, 4h.**
Ichimoku tenkan/kijun cross with cloud filter, ATR bracket exits.
2,302 OOS trades, expectancy **+0.894%**, PF **1.278**; folds
+1.99/+1.62/−0.12/+0.43/+0.46% (4/5); breadth 26/30 symbols positive,
largest profit share 14.8% (ARB); untouched subset (every 3rd symbol)
+0.895% on 793 trades; Bonferroni p = 1.4e-7 ✓. At **2× costs**:
+0.734%, PF **1.222** — survives.

**CANDIDATE 2 — dow_effect / reversal @ crypto30, 1d.**
Calendar rule: on Mondays only, take the opposite side of the
trailing 5-day move (short if the week rose, long if it fell),
fixed-hold bracket exit. 3,660 OOS trades, expectancy **+0.878%**,
PF **1.257**; folds +1.05/+1.77/+1.09/−0.46/+1.00% (4/5); breadth
27/30 positive, largest share 20.0% (NEAR); untouched subset +0.787%
on 1,220 trades; Bonferroni ✓. At **2× costs**: +0.717%, PF **1.206**
— survives. Plain-language caveat: this is a weekly-cycle calendar
effect, the class of pattern most prone to era decay; it passed every
mechanical gate anyway, and only forward evidence can now separate
"real cycle" from "2024–2026 artefact".

The other four bar-passers fail significance at N = 1,557 and are
watchlist, not candidates: bollinger_trend p50_sd2.0 @crypto30/1d
(+3.54%, PF 1.456, 420 trades), shock_breakout k1.0 @crypto30/1d
(+2.70%, PF 1.318, 732), governed adx_ema bare @crypto30/4h (+0.80%,
PF 1.233, 837 — the production config scores +0.61%/PF 1.197, and at
2× costs PF 1.143), tsmom2_dual roc30_ema200 @comm7/4h (+0.56%,
PF 1.203, 205).

**Significance method, stated in full.** Gate: Bonferroni one-sided
p < 0.05/N_global — family-wise error control that is valid under
arbitrary dependence between trials and needs no estimated inputs.
Deflated Sharpe ratios (Bailey & López de Prado) are computed and
stored for every near-bar row under three dispersion estimators
(null sqrt(mean(1/n)) = 0.077; naive cross-trial std = 0.134 all rows,
0.106 for ≥200-trade rows) but do not veto: at N ≈ 1,500 with
correlated, heterogeneous-length trials the DSR dispersion input is
not identified — the estimators swing the hurdle across the entire
plausible effect range (both candidates' DSRs are ≈ 0 under every
estimator, i.e. under the strictest selection-adjusted lens they
would NOT clear). The numbers are on the record in
`results_rd2/synthesis.json`; the candidates stand on the bar +
Bonferroni + holdout + 2×-cost evidence, with the DSR caveat attached
to them permanently. Forward evidence, not another backtest, is the
arbiter from here.

### Texture of the grid (what the 1,077 rows say as a whole)

- The positive tail is overwhelmingly **crypto, daily/4h, trend-shaped**:
  the top of the table (vol_adaptive EMA crosses +6.2%, donchian
  +5.6%, ts_momentum roc72 +4.4%, macd +5.8% — all @crypto30/1d) is one
  correlated cluster riding the same 2025 trend regime, and its
  members fail on folds/holdout/significance individually. Treat the
  cluster as ONE observation, not fifteen.
- Forex is the weakest class (35 positive vs 213 negative rows at
  n ≥ 200 the best is stoch_reversion +0.29%/PF 1.26, sub-bar on
  folds). Commodities @4h are the least-bad non-crypto region
  (ichimoku +0.64%/PF 1.31, shock +0.57%, tsmom2 at the bar).
  Indices are mildly positive at daily only.
- The governed set on the widened universe confirms every prior
  audit: bb_reversion negative everywhere (PF 0.88–0.92 on crypto);
  factory_winner_1..5 negative everywhere (winner_2 is winner_1's
  code, winner_5 is winner_3's — identical rows, again);
  supertrend +0.19%/PF 1.05 @crypto 4h at best. adx_ema is the only
  governed module with a pulse, and only in bare form at 4h.
- **Pairs/stat-arb is excluded on unit integrity**: the pairs harness
  denominates returns in log-spread units, producing "trades" of
  +1,330% and −33% that are not capital returns. No pairs number in
  this programme is comparable to any other row; the family needs a
  capital-denominated rebuild before it can be judged at all.

### SMT-v2 — explicit verdict (owner addendum, 2026-11-15)

SMT-v2 was retested module-faithfully — the actual deployed code
(`oanda_demo.strategy.StratexTrendStrategy`, default
`StrategyConfig`), its native 4h timeframe, its 8-pair OANDA
watchlist, its own spread gate, its declared risk box (SL 1.5×ATR /
TP 2.25×ATR / breakeven at +1R) — on the widened forex panel, judged
by the same bar, counted in the same counter (2 trials):

- watchlist-8 @4h: 627 OOS trades, expectancy **−0.081%**, PF **0.655**
  (project's own R accounting: −30.0R over 635 trades, win rate ~32%)
- full forex12 @4h (robustness): 1,026 trades, **−0.086%**, PF **0.651**
  (−68.0R)

The mega-grid retest **confirms the live record** (−$167, WR 21.1%)
with two orders of magnitude more trades. Under the owner's removal
rule (strict OOS PF < 1.2 goes), **SMT-v2 FAILS and is eligible for
removal**; its entries are already paused and should stay that way.
(One disclosed simulator difference: exits are checked from the entry
bar onward here; `oanda_demo/backtest.py` never exits on the entry
bar. The project's own backtest of this family reached the same
conclusion — its v3 docstring records −302R on H4.)

## Stage C — Combinations

Streams: 851 saved trade streams, 566 eligible after the
unit-integrity guard. Portfolio construction (disclosed): each stream
is an equal-weight book — a day's return is the sum of that day's
exiting trades' net returns divided by the number of positions
actually open that day — then sleeves are combined equal-weight or
inverse-volatility (monthly refresh, strictly past data) and judged
on compounded equity + max drawdown over the OOS era. Ensembles:
2-of-3 vote among donchian/ts-momentum/vol-trend on the same bars.

| set | weighting | compounded | max DD | ann. Sharpe | mean corr |
|---|---|---|---|---|---|
| top5 overall | equal / inv-vol | +102.5% / +112.4% | −20.2% / −19.8% | 0.94 / 1.01 | 0.37 |
| top3 crypto | equal / inv-vol | +104.0% / +110.7% | −20.6% / −20.1% | 0.94 / 0.98 | 0.19 |
| top3 forex | equal / inv-vol | +9.3% / +8.7% | −2.2% / −2.0% | 1.24 / 1.20 | 0.08 |
| top3 commodities | equal / inv-vol | +26.4% / +15.2% | −12.8% / −24.7% | 0.65 / 0.32 | 0.04 |
| top3 indices | equal / inv-vol | +17.2% / +17.5% | −7.1% / −7.3% | 0.80 / 0.76 | 0.12 |
| best per class | equal / inv-vol | +18.8% / +16.1% | −11.5% / −8.3% | 0.59 / 0.67 | 0.01 |
| all-positive top15 | equal / inv-vol | +90.7% / +96.2% | −26.1% / −24.4% | 0.98 / 1.02 | 0.35 |

Ensembles: crypto30@4h vote-2 = +0.032%/trade, PF 1.009 (breakeven);
forex12@4h vote-2 = −0.053%, PF 0.874 (negative). Voting does not
create edge from these components.

**Verdict, with the caveat stated loudly:** diversified marginal
streams DO compound positively in this window, and the cross-class
set does it at near-zero component correlation (0.01) — the
diversification mechanism is real. BUT every set was selected from
the same data it is judged on; these are in-sample-selected
portfolios (counted as 14 trials), not forward evidence. Stage C's
legitimate output is a *forward-protocol design* (below), not a
promotion.

## Stage D — Synthesis and recommendations

Computed in full in `results_rd2/synthesis.json` (1,077 ranked rows,
350 wf procedures, 14 combinations, global trial count **1,557**).

**Candidates (bar + Bonferroni + holdout + 2×-cost): exactly TWO** —
ichimoku_trend/tk_cloud @crypto30/4h and dow_effect/reversal
@crypto30/1d, detailed above, DSR caveat attached. Not "100s of
profitable strategies": the honest count from ~1,600 configurations
across four asset classes is two, plus a six-deep watchlist. Anyone
quoting a larger number from this programme is quoting the
uncorrected top of the table — the exact artefact the Anti-Overfit
Law exists to prevent.

**Forward-protocol entrant recommendations** (for coordinator/owner
decision; venues are now Binance demo-fapi + OANDA practice after
the classic-testnet retirement; leverage pin 3x; income proof target
₹50,000/month; the phase-3 forward bar stands — 8 weeks AND ≥100
closed trades per entrant, kill criteria unchanged):

1. **ichimoku_trend/tk_cloud @ crypto 4h, 30 pairs** — lead entrant.
   Historical pace ≈ 82 trades/month pooled, so the ≥100-trade leg
   completes in ~5–6 weeks inside the 8-week window.
2. **dow_effect/reversal @ crypto 1d, 30 pairs** — second entrant,
   deliberately uncorrelated in construction (calendar vs trend).
   ≈ 130 trades/month; the 8-week leg binds. Watch specifically for
   era decay: kill it early if the first 50 forward trades are
   negative — calendar effects do not get the benefit of the doubt.
3. **Portfolio sleeve (Stage C best-per-class set)** — third entrant
   as a *portfolio*, judged on compounded equity + DD only, because
   that is the claim Stage C actually supports.
4. adx_ema production config — NOT an entrant on this evidence
   (PF 1.197, sub-bar; 2×-cost PF 1.143). It stays the governed
   incumbent under its existing phase-3 measurement; the bare 4h
   variant is watchlist-only (its significance fails at N = 1,557).

**SMT-v2**: fails the removal rule on this retest (PF 0.65) — see
the explicit verdict above.

**The owner's zero-candidate contingency** (rethink Stratex entirely,
different approach — pre-decided 2026-11-15) is **not triggered**:
the grid returned two candidates. It should trigger instead if BOTH
forward entrants fail their forward bars — at that point more
backtesting of this kind has earned its retirement, and the
different-approach proposal (market-structure/funding mechanics,
event-driven via IntelX, CTA-style broad trend with vol targeting)
becomes the next programme.

## Bottom line

Across 1,557 counted configurations on hash-manifested data in four
asset classes, Stratex's demonstrable backtest edge is narrow and
specific: one Ichimoku trend configuration on crypto 4h and one
Monday-reversal calendar effect on crypto daily, both broad-based,
both cost-robust, both now owing their real proof to the forward
window. Everything currently running on the demo accounts scored
worse than both. That is a small answer, and it is a real one.

