# TASK-STR-RD-006 — Pairs / Statistical Arbitrage: Results

**Verdict: ZERO passers. ZERO watchlist.** Cointegration-screened pairs
trading on CRYPTO30 (1h/4h, z-score entries 2.0/2.5, formation-frozen
hedge ratios) does not survive out-of-sample judgement net of costs.
Nothing from this track is wired into any forward lane.

Pre-declaration: `rd6/PREDECLARATION.md`, frozen 2026-11-15 12:52 IST
(issue #35 comment 6890997830) BEFORE any backtest execution. The grid,
pairs, screen, trading rule, costs and gates below are exactly the
declared ones; the finisher disclosures at the end list every execution
detail that differed from the original crew's plan (none touches the
declared design).

## The bar and the count

- Trials: 435 pairs × 2 timeframes × 2 entry configs = **1,740**.
  Every pair-config the screen could have selected counts, traded or not.
- Bar (standing RD-002 promotion bar, operationalised in the
  pre-declaration): expectancy > 0 AND PF ≥ 1.2 AND ≥ 200 OOS trades;
  traded in ≥ 3 of 5 folds AND ≥ 80% of traded folds net-positive;
  Bonferroni p < 0.05/N at N = 1,740; DSR ≥ 0.95 at N = 1,740;
  2×-cost PF ≥ 1.0; untouched-holdout pass.
- Global-floor recheck: the running global counter at synthesis time is
  1,557 (through RD-002) + 207 (RD-003) + 162 (RD-005) + 45 (RD-007) +
  53 (RD-008) + 48 (RD-013) = **2,072** before RD-006, 3,812 including
  it; the pre-declaration's conservative floor is 3,297. No verdict in
  this report is anywhere near any of these boundaries (smallest
  p-value anywhere: 0.0073, vs thresholds of 2.9e-5 at N = 1,740 and
  1.3e-5 at N = 3,812), so **every verdict is identical at every N**.
  Exact per-config p-values are in `results_rd6/config_verdicts.csv`
  for re-judgement at the final counter.

## Outcome in one table

| | |
|---|---|
| Pair-configs that ever traded | 409 of 1,740 |
| FAIL (≥ 30 trades, bar not met) | 261 |
| INSUFFICIENT (< 30 trades) | 148 |
| WATCHLIST | 0 |
| PASS | 0 |
| Configs passing the mechanical bar (exp/PF/trades/folds) | **0** |
| Configs reaching the holdout stage | 0 (holdout correctly never evaluated) |
| Total OOS fold trades | 164,570 (1h 131,522; 4h 33,048) |
| Cross-trial Sharpe variance (DSR input, configs ≥ 30 trades) | 0.017525 |

## Why nothing passed — three independent layers

**1. At honest sample sizes there is no edge at all.** Of the 186
configs with ≥ 200 OOS trades, the best net profit factor is **0.797**
(XRPUSDT/AAVEUSDT 4h). Not one reaches PF 1.2 net; only 5 of the 186
reach PF ≥ 1.2 *gross* of costs. Of the 261 configs with ≥ 30 trades,
exactly 9 have positive expectancy, and all 9 are small: the largest
(LINKUSDT/ALGOUSDT 4h E2.0, 173 trades, PF 1.327) traded only 2 folds
with 50% of them positive; the highest-PF of the nine
(VETUSDT/SANDUSDT 1h E2.0, PF 3.330) has 72 trades in 2 folds,
p = 0.045, DSR ≈ 0. The remaining positive rows in the full table are
1–25-trade artefacts (PF up to ∞ on a single trade) — counted, and
worthless as evidence.

**2. Significance is not close.** The smallest one-sided p-value across
all 409 traded configs is 0.0073 (ETCUSDT/MANAUSDT 1h E2.0, 25 trades)
— 255× above the Bonferroni threshold at the declared N. The maximum
deflated Sharpe ratio is 0.837 (ETCUSDT/MANAUSDT 4h E2.0, 8 trades)
against the required 0.95.

**3. The pooled procedure loses in every fold.** All screen-selected
trades pooled per (timeframe, config), net of the declared 32 bps:

| Procedure | Trades | Expectancy/trade | PF | PF @2× cost | Total |
|---|---|---|---|---|---|
| 1h, E2.0 | 65,774 | −0.349% | 0.384 | 0.179 | −229.44 |
| 1h, E2.5 | 65,748 | −0.348% | 0.381 | 0.176 | −228.50 |
| 4h, E2.0 | 16,540 | −0.426% | 0.574 | 0.387 | −70.40 |
| 4h, E2.5 | 16,508 | −0.422% | 0.566 | 0.376 | −69.59 |

All 20 fold cells (5 folds × 4 procedures) are negative. Gross of
costs the pooled expectancy is still negative (−0.03%/trade at 1h,
−0.11%/trade at 4h): **cheaper execution would not rescue this
procedure** — the reversion it bets on does not arrive out-of-sample.

## The mechanism (measured, and independently re-verified)

Of 164,570 fold trades, **164,078 (99.7%) exited at the |z| ≥ 4 stop**;
159 exited by crossing zero; 333 ran to fold end. Median holding time
is 1 bar. A spread that reaches the entry band in the trading window
overwhelmingly *continues* to the stop instead of reverting:
formation-window cointegration does not persist into the trading
window. Consistent failure accounting:

- Screen funnel per fold (435 pairs each): ADF passes 26–55 (1h) /
  19–41 (4h); after the half-life filter, selected = 12–36 (1h) /
  19–41 (4h — the HL filter never binds at 4h). DATA-SKIPs: **0** in
  formation and 0 in trading windows, all folds, both timeframes.
- Only 128 of 435 pairs were ever selected at either timeframe;
  persistence is rare: 657 of 870 pair-timeframe combos selected in
  0 folds, 170 in 1, 36 in 2, 6 in 3, 1 in 4, none in 5.
- **99 pair-timeframe combos selected in W1/W2 fail the screen in a
  later fold** (cointegration breakdown, reported per the declaration).
- 28 traded configs flip sign across folds (positive fold, then a
  negative one).
- BTCUSDT/ETHUSDT — the canonical pair — **never passed the ADF screen
  in any fold at either timeframe** (0 ADF passes in 10 screens) and
  never traded.

Full per-config record: `results_rd6/config_verdicts.csv` (409 rows);
every screen: `results_rd6/screen_log.csv` (4,350 rows); digest:
`results_rd6/analysis_digest.md`.

## Machinery validation (before any market number was trusted)

- Synthetic fixtures (validation only, never market evidence), from
  `pairs_engine.py validate`: ADF τ = −14.14 on a stationary AR(1)
  vs +1.36 on a random walk; constructed cointegrated pair recovered
  (τ = −9.63, β = 0.794 vs 0.8 constructed, half-life 15.1 vs 13.5
  constructed bars); independent-random-walk screen pass rate 0/40.
  **ALL FIXTURES PASS** — identical output on every run, including the
  finisher's.
- Sanity anchor: RD-001's published ts_momentum roc42_4h cell
  (BTC/ETH/SOL) reproduced **bit-identically** through the untouched
  rd2 chain — 303 trades, expectancy 0.0024275740638451445,
  PF 1.0969220482985518 (`results_rd6/sanity_anchor.json`).
- Data: all 30 fetched 1h series cross-checked against the RD-002
  caches — 58 common archives per symbol, **0 hash mismatches**, row
  counts identical (crew record: data/crosscheck_rd2.json).

## Finisher disclosures (execution history — design untouched)

1. The original RD-006 crew died mid-run with no results; this
  finisher executed the frozen pre-declaration exactly as written.
   The declared grid, pairs, screen, rule, costs and gates were not
   altered in any way.
2. Execution parallelisation: the declared evaluation is independent
   per (pair, fold, timeframe), so the stock engine was run in four
   pair-range slices per timeframe via a wrapper that only restricts
   the pair list and the output directory (engine code unmodified),
   checkpoints were merged with grid validation (435 pairs × 5 folds
   per timeframe, no duplicate screen keys), and the verdict/holdout/
   synthesis stage then ran on the **stock engine, single process**,
   from those checkpoints. Verified trade-for-trade by independent
   recomputation from raw data on the stock functions:
   BNBUSDT/XLMUSDT 4h W4 E2.5 (328/328 trades, nets identical),
   XRPUSDT/AAVEUSDT 4h W2 E2.0 (392/392), LINKUSDT/ALGOUSDT 1h W3
   (2/2) and W4 (673/673) E2.0. (A forced recomputation of
   LINK/ALGO W2 initially showed 14 trades vs 0 stored; the stored
   screen log resolves it — that fold was never selected: τ = −2.748,
   HL = 403.8 bars. No discrepancy.)
3. One bug was fixed in the crew's *analysis* script (not the engine,
   not the procedure): `analyze.py` crashed on the absent
   `trade_data_skip` column of screen_log.csv. The column is absent
   because no row ever set it — the trade-window DATA-SKIP count is
   genuinely 0, which is what the fixed script reports.
4. Claim bookkeeping: the original claim (issue #35 comment
   6890997830) stands. The finisher's dup-safe claim check scans only
   the last comment page and posted a second claim comment
   (6891568427) before the original was located on an earlier page;
   both are from muse_ai for this same task and the original governs.
5. The holdout was never evaluated — by design, not omission: the
   pre-declaration evaluates it once, only for pair-configs passing
   every other bar element, and zero configs did.

## Consequence

Nothing from this track enters any forward lane; no production code,
registry, config or daemon was touched. Pairs stat-arb as declared —
Engle–Granger + half-life screen, frozen formation parameters, z 2.0/2.5
entries on CRYPTO30 at 1h/4h — is a closed question at this cost model,
and the pooled gross numbers say a cheaper cost model alone would not
reopen it. Any future pairs work needs a different mechanism (e.g.
intraday horizons with formation windows that adapt, or a
breakdown-aware exit) declared as a NEW family, not a retune of this one.

*Research only. This result authorises no trading, demo or live.*
