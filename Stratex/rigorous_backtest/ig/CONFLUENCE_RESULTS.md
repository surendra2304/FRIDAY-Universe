# RESULTS — TASK-IG-STR-06: Fib/BOS confluence family (fib_bos_confluence), declared run

## Verdict (plain)

**ZERO of the 4 pre-declared cells pass the programme bar. The family
is CLOSED** — the declaration's own terms ("Failing it closes the
family, like RD-004/006/012/014/016 before it") apply. Nothing is
promoted, nothing is registered, nothing trades; no forward-test
candidate comes out of this run.

Trials added to the global counter: **4** (one per panel × timeframe
cell), taking it from 3,885 to **3,889**. The Bonferroni gate at the
corrected final floor is α = 0.05 / 3,889 = **1.2857e-05**; no cell
came near it (best one-sided p = 0.230, crypto30 @4h). The closest
cell — crypto30 @4h, expectancy +0.0694%, PF 1.041 — fails on PF
(1.041 < 1.2), folds (3/5, needs 4), the holdout2 untouched subset
(−0.117%) and the 2×-cost shadow (expectancy flips to −0.0900%);
it is a miss, not a near-miss under the bar.

## What was run (pre-declared, frozen before execution)

Declaration: `declaration.json` in this directory, declared
2026-11-15 before any backtest of this family, sha256
`43c025e1ce4dffd16d21d7cbd1218dc11006bdc85c77a933d66785cbdc280300`
(re-verified from origin/main immediately before the run; the
declaration governs). Signal code `confluence.py` executed
byte-identical to main (hash-manifested extraction; the
declaration's own tests pass, 5/5). Frozen parameters: FIB zone
(0.500, 0.618), extensions (1.272, 1.618), swing window 2 (fractal,
strict), one signal per leg, entry at the BOS confirmation close,
stop = leg origin, invalidation = close beyond leg origin before
confirmation. No variant, threshold or exit spec was altered after
the freeze. Corpus scope note: the Stratex supervisor ruled corpus
item S-24 is this same family/source (DYeU6nSBl9K), so no separate
S-24 test exists or is added.

- Cells (judgement unit = panel × timeframe, RD-002 practice):
  crypto30 @1h, crypto30 @4h, forex_cross41 @1h, forex_cross41 @4h.
- Folds: crypto30 STANDARD W1–W5; forex_cross41 LATE W2–W5
  (panels16 convention: Yahoo 1h history starts 2024-11-18, after
  W1 opens). Trades attributed to folds by entry time.
- Execution conventions: entry at the confirmation close; exits
  managed from the next bar; within a bar the STOP is assumed hit
  before any target (worst case); a bar gapping through a level
  fills at the bar open; one position at a time per symbol (signals
  arriving while a trade is open are skipped: 76,174 / 20,260 /
  30,242 / 7,276 per cell).
- Costs: programme model (rd2/costs2) — crypto30 **16 bps round
  trip**; forex_cross41 all crosses **10 bps round trip**. The
  2×-cost shadow is recomputed exactly from the saved trade legs
  (exits are price-level based; costs enter only via net returns)
  and must pass the same bar.
- Judgement: the programme's own rd2.stats2 `check_bar2` +
  `holdout2`, plus `rd.common.holdout_check` as the declaration
  names it. Bar per cell (ALL must hold): expectancy_net > 0;
  PF_net ≥ 1.2; ≥ 200 pooled OOS trades; positive folds per
  check_bar2 (≥ 80% of profile folds positive, trades in
  ≥ profile−1 folds); holdout2 passes; rd.common holdout_check
  passes; 2× shadow passes the same checks; Bonferroni one-sided
  p < 0.05 / N_final on pooled OOS trades.

### Run-level freeze (disclosed — NOT a declaration fact)

The declaration names two targets (T1 = 1.272R, T2 = 1.618R) with
no exit split. Before any execution, the ambiguity was resolved at
run level, in the manner of Box Theory's declared ambiguity
resolutions: **50/50 scale-out** — 50% of the position exits at T1,
the remaining 50% at T2; the stop (leg origin) covers the whole
position until T1 and the remainder after it; **no stop movement**
(none is declared). 50/50 is the only split introducing no tunable
number. One signal = one trade; trade net = mean of the two legs'
nets, each leg costed in price space. A stop hit before T1 exits
the whole trade at the stop; end of data closes any remainder at
the final close. This resolution is recorded here and on issue #35
as a run-level freeze, not a declaration fact.

### Trial floor (coordinator correction applied)

The run design started from the declaration-era floor (1,980,
giving N_final = 1,996). The coordinator's reconciliation ledger
(`~/workspace/rd-reconcile/TRIAL_LEDGER.md`) fixes the true
entering floor at **N = 3,885 executed trials**, superseding every
earlier drifting figure. The Bonferroni step was recomputed
exactly from the saved OOS trade lists at N_final = 3,885 + 4 =
**3,889** (α = 1.2857e-05). **No verdict changes** — every cell
fails Bonferroni at either floor.

### Verification before any number was trusted

The scale-out simulator was hand-verified on 6 synthetic paths
before the run (TP1→TP2 scale-out; stop-before-target same-bar
worst case; gap-through-stop fill at open; TP1-then-stop
remainder; zero-cost net = +0.15 exact on the T1/T2 fixture; short
mirror) — all pass. The declaration's own test suite
(`ig/tests/test_confluence.py`) passes 5/5 on the extracted copy.

## Data provenance (stated before results, per programme practice)

- **crypto30**: Binance Vision USDT-M futures monthly klines via
  the harness data_feed cache contract (cache `~/workspace/str-rd2/
  cache2`; 1h, months 2022-01..2026-10; per-file SHA-256 +
  canonical CSV SHA-256 sidecars re-verified on every load by
  load_dataset; 4h derived by resample_dataset, complete UTC
  buckets only, parent hash recorded). All 30 symbols loaded,
  **UNCOVERED = none**; 30,656–42,360 1h bars per symbol spanning
  2022-01-01 → 2026-10-31; **1,320 gap-audited missing bars in
  total, reported and never filled**.
- **forex_cross41**: Yahoo Finance chart-API 1h series fetched
  under TASK-STR-DATA-001's expansion contract (cache
  `~/workspace/rd-016/cache16`), admitted ONLY where the series'
  status in `data_verification.json` is FULL_MATCH or
  TRUNCATED_MATCH (panels16 rule; unverified series are excluded,
  never substituted). **All 41 series verified and loaded,
  UNCOVERED = none**; 12,054–12,361 1h bars per symbol spanning
  2024-11-18 → 2026-11-13; 4h resampled from the verified 1h.
  The gap audit counts FX non-trading hours against the 24/7 grid,
  as in prior rounds (hence the large raw missing-bar totals:
  210,391 at 1h / 56,079 at 4h — these are market-closed hours,
  not data holes). One cosmetic artefact: the harness resample
  manifest mislabels the forex 4h source string as Binance; the
  parent-hash chain points at the Yahoo 1h series.

## Results — every cell (pooled walk-forward OOS, programme costs)

| Cell | OOS trades | Win rate | Expectancy | PF | Pos folds | 2× shadow (exp / PF) | Bonferroni p (N=3,889) | Verdict |
|---|---|---|---|---|---|---|---|---|
| crypto30 @1h | 18,466 | 61.8% | −0.1641% | 0.818 | 0/5 | −0.3240% / 0.666 | ≈1.0 | FAIL |
| crypto30 @4h | 3,923 | 66.7% | +0.0694% | 1.041 | 3/5 | −0.0900% / 0.949 | 0.230 | FAIL |
| forex_cross41 @1h | 14,047 | 37.7% | −0.1105% | 0.318 | 0/4 | −0.2105% / 0.106 | 1.0 | FAIL |
| forex_cross41 @4h | 3,868 | 53.6% | −0.0994% | 0.572 | 0/4 | −0.1994% / 0.305 | 1.0 | FAIL |

Per-fold expectancy (programme costs):

- **crypto30 @1h** — W1 −0.1267% (4,707 trades) · W2 −0.0920%
  (4,050) · W3 −0.2073% (4,383) · W4 −0.1878% (3,490) · W5
  −0.2710% (1,836). Negative in all five folds; holdout2 breadth
  1/30 symbols (untouched-subset expectancy −0.2050% over 5,779
  trades); rd.common holdout_check FAIL; t = −7.94. The ≥200-trades
  leg is the only bar leg met.
- **crypto30 @4h** — W1 +0.0194% (1,227) · W2 +0.1953% (747) ·
  W3 +0.2819% (974) · W4 −0.2468% (634) · W5 −0.0457% (341). The
  closest cell: expectancy positive and rd.common holdout_check
  PASSES (the only gate passed anywhere in the run), but PF
  1.041 < 1.2, folds 3/5 < the required 4, holdout2 fails
  (untouched-subset expectancy −0.1168% over 1,285 trades), the 2×
  shadow flips expectancy negative, and Bonferroni p = 0.230 is
  four orders of magnitude from α.
- **forex_cross41 @1h** — W2 −0.1063% (4,024) · W3 −0.1083%
  (3,727) · W4 −0.1173% (3,716) · W5 −0.1107% (2,580). Uniformly
  negative, t = −39.8, holdout breadth 0/41.
- **forex_cross41 @4h** — W2 −0.1001% (1,065) · W3 −0.1006%
  (1,070) · W4 −0.1114% (1,012) · W5 −0.0799% (721). Uniformly
  negative, t = −11.0, breadth 0/41.

Full per-fold tables, holdout internals and per-symbol figures are
in `confluence_results.json` alongside this file; every trade leg
is in the run's saved cell outputs (see Delivery note).

Reading of the mechanism, on these universes (descriptive, not a
new test): on crypto the model wins often (62–67%) but loses money
— the scale-out banks the small first extension while losses run
the full leg back to the origin, and that payoff asymmetry does
not survive programme costs. On forex crosses at 1h it loses on
win rate and payoff alike. The SK-System Fib/BOS confluence
hypothesis does not clear the pre-declared bar on either declared
panel at either declared timeframe.

## Significance / DSR disclosure

Gate = Bonferroni one-sided p < 1.2857e-05 at N = 3,889 — no cell
passes (best p = 0.230). Deflated Sharpe is **non-computable
in-round** per RD-016 practice (the cross-trial Sharpe dispersion
estimator is not available for a single 4-cell round) and is
reported as such, not estimated; Bonferroni is the declared gate.

## What this round establishes

1. The fib_bos_confluence family is judged and **CLOSED** under
   its pre-declaration; it joins RD-004/006/012/014/016 as a
   family the programme has honestly eliminated. No retune is
   authorised by this record — variants would require a new
   declaration and would raise the trial count.
2. Global trial counter: **3,889**. No candidate is forwarded to
   the forward-test lane from this round.
3. The run consumed fully provenance-verified panels only
   (crypto30 hash-sidecar caches; forex_cross41 admitted solely
   on FULL_MATCH / TRUNCATED_MATCH verification), with zero
   uncovered symbols in any cell.

## Delivery note

Run executed 2026-11-16 by the STR-06 backtest crew (research
only; the repo and all live code untouched). Full results —
results table, per-fold figures, provenance, floor statement —
posted to issue #35 as comment **6924993040**. Run artefacts (full
trade legs per cell): `~/workspace/str06-backtest/results/`
(`results.json`, `bonferroni_corrected.json`, `cell_*.json`),
with the run's STATE.md alongside. This record + the board closure
land in a separate follow-up PR, per the TASK-IG-STR-06 board
entry's declared next step. Status of the run itself: **complete —
verdict FAIL, family CLOSED**.

## Files

- `Stratex/rigorous_backtest/ig/CONFLUENCE_DECLARATION.md` +
  `declaration.json` — the frozen pre-declaration (2026-11-15).
- `Stratex/rigorous_backtest/ig/confluence.py` — the signal code,
  executed byte-identical to main.
- This file: `Stratex/rigorous_backtest/ig/CONFLUENCE_RESULTS.md`
- `Stratex/rigorous_backtest/ig/confluence_results.json` —
  machine-readable per-cell summary (pooled + per-fold + 2×
  shadow + holdout + corrected Bonferroni + provenance summary).
