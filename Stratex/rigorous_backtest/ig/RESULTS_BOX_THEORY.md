# RESULTS — TASK-IG2-STR-13: Box Theory, the declared run

## Verdict (plain)

**FAIL. The Box Theory family does not clear the programme bar, at
either cost level, under either exit reading. Per the declaration
("Failing it closes the family"), the family is CLOSED.** Nothing is
promoted, nothing is registered for forward testing, nothing trades.

Pooled walk-forward OOS, primary reading, programme costs:
**16,842 trades, expectancy −0.218% per trade, profit factor 0.805.**
The strategy also loses money *before* costs (gross expectancy
−0.058%, gross PF 0.941), so this is not a cost artefact: on 15-minute
crypto bars, a wick rejection at the previous day's range quartile
does not mean-revert often enough to pay for the trip to the opposite
extreme. The win rate is 17.1% — the full-box traversal the payoff
needs happens about one time in six, while the stop at the near box
extreme is hit five times in six.

## What was run (frozen before execution; nothing varied)

- **Declaration:** `Stratex/rigorous_backtest/ig/box_theory_declaration.json`,
  re-verified from origin/main (0206c62a) before the run:
  SHA-256 `715b6884fb6a9abe3efec7be90c83e161cf7426aef1dc37629616b3145d013bd` ✓.
  Fidelity addendum (PR #752) re-verified: SHA-256
  `94c9349996804a3f782f9d01782cfefd2a01609c0b0e973e53f2be5f145a1329` ✓.
- **Signal code:** the frozen `ig/box_theory.py` (main blob
  `305ec46e`), unmodified; its mechanics tests pass 7/7. Parameters
  exactly as frozen: ZONE_FRACTION = 0.25, WICK_TO_BODY = 2.0. No
  variants were tried.
- **Fidelity labelling (per the addendum):** the stop (box extreme),
  the targets T1/T2, the one-signal-per-day rule, and the UTC
  calendar day are **declaration conventions, not source rules** —
  the source video stated no stop-loss, no take-profit, no position
  sizing and no frequency rule, and made no performance claim. This
  run tested the declaration as frozen.
- **Panel (stated per the data plan):** crypto30 — the 30 Binance
  USDT-M symbols of `rd2/panels.py` CRYPTO30 — at 15 minutes,
  Binance Vision monthly klines via the programme's verified loader
  (`data_feed.load_dataset`), months 2023-10..2026-10, fetched
  2026-11-16. **30/30 symbols loaded; every series 108,192 bars,
  2023-10-01T00:00Z → 2026-10-31T23:45Z; zero missing bars in the
  whole panel** (per-series CSV hashes + gap audits in
  `box_theory_provenance.json` (this directory); e.g. BTCUSDT csv_sha256
  `7b1c3d1c3fbf6e9034c376a162e8ff92d6870cc682258f0e0a4bb609ea328a67`).
  **forex_cross41 was excluded on the declaration's own terms**
  ("where 15-minute history is available"): DATA-001 verified only
  1d/1h for it and recorded 15m as NOT verified (Yahoo depth
  insufficient for the folds). Nothing was substituted.
- **Folds:** harness W1..W5 (STANDARD profile; 15m history starts
  2023-10, before W1 opens). Trades attributed by entry time; OOS
  only. Judgement: `rd/common.py` `check_bar` + `holdout_check`.
- **Costs:** programme model — Binance USDT-M taker 5 bps fee +
  3 bps spread/slippage per side = **16 bps round trip**; 2× shadow
  = **32 bps round trip**. Both must pass.
- **Exits (the declaration's convention, fixed pre-run):** entry at
  the trigger bar's close; position managed from the next bar; stop
  checked before target within a bar (worst case); gap-through fills
  at the bar open; one position at a time per symbol (8,402 signals
  arrived while a position was open and were skipped); still open at
  data end → closed at final close. **Primary exit = T2** (opposite
  box extreme — the source method as carried into the declaration is
  "buy at the bottom, sell at the top"; no partial-exit fraction is
  declared, so none was invented). A **T1-exit sensitivity** (box
  mid) was computed for disclosure only — see below; it is not
  judged and cannot pass the family.
- **Bonferroni:** one-sided t-test on pooled OOS per-trade net
  returns against the entering programme floor **N = 3,885 executed
  trials** (RD reconciliation ledger, 2026-11-16; α = 1.287e-05).
  The declaration's "≥ 1,980" figure was superseded by the ledger
  (it was a partial sum). This run adds 2 cells to the programme
  counter (primary + sensitivity); with STR-06's 4 cells landed the
  same evening, the counter stands at 3,891.

## Numbers — primary (T2 exit)

30,879 signals generated; 22,477 trades taken (all dates);
16,842 entered inside the OOS folds.

| Fold | Trades | Expectancy | PF | Win rate |
|---|---|---|---|---|
| W1 2024-07→2025-01 | 3,777 | −0.346% | 0.721 | 15.4% |
| W2 2025-01→2025-07 | 3,697 | −0.310% | 0.749 | 14.9% |
| W3 2025-07→2026-01 | 3,609 | +0.014% | 1.013 | 20.6% |
| W4 2026-01→2026-07 | 3,231 | −0.139% | 0.861 | 18.1% |
| W5 2026-07→2026-11 | 2,528 | −0.325% | 0.675 | 16.8% |
| **Pooled OOS** | **16,842** | **−0.218%** | **0.805** | **17.1%** |

Avg win +5.25%, avg loss −1.35%. OOS exits: 13,958 stop / 2,864
target / 20 end-of-data. Only 2 of 30 symbols are positive, both at
noise level (DOGEUSDT +0.026% on 536 trades; AAVEUSDT +0.036% on
453); 28 of 30 are negative.

| Bar leg | 1× costs (16 bps) | 2× shadow (32 bps) |
|---|---|---|
| Expectancy > 0 | ✗ (−0.218%) | ✗ (−0.378%) |
| PF ≥ 1.2 | ✗ (0.805) | ✗ (0.697) |
| ≥ 200 OOS trades | ✓ (16,842) | ✓ (16,842) |
| ≥ 4/5 folds positive | ✗ (1/5) | ✗ (0/5) |
| holdout_check | ✓ (see note) | ✗ |
| Bonferroni p < 1.287e-05 | ✗ (p = 1.0) | ✗ (p = 1.0) |

Holdout note: the 1× holdout "pass" is mechanical — two barely
positive symbols satisfy the ≥2-symbol rule and the largest takes
53.6% of the (tiny) positive profit against an 80% cap. It does not
rescue anything: the bar fails on expectancy, PF, folds and
Bonferroni at 1×, and on every leg at 2×.

## Sensitivity — T1 exit (box mid), disclosure only

22,147 OOS trades, expectancy −0.147%, PF 0.806; negative in all
five folds (−0.151% / −0.145% / −0.125% / −0.122% / −0.209%). The
declaration's two-target under-specification is therefore
**immaterial**: the family fails under both readings, so no new
declaration is needed to rescue it and none should be written on
this evidence.

## Verification performed

- Frozen hashes re-verified from origin/main git objects before the
  run (declaration + addendum, above); harness tree extracted via
  `git archive` from main 0206c62a (blob ids in the run record,
  issue #35 comment 6925202981).
- Independent recomputation of the pooled OOS metrics straight from
  the saved trade list, bypassing the judging code: trades 16,842,
  expectancy −0.002182, PF 0.8046 — identical.
- One trade hand-traced against raw bars (BTCUSDT SHORT,
  2023-10-02 07:00Z): box from 2023-10-01 (H 28365.2 / L 26939.0);
  trigger bar range intersects the top zone, upper wick 39.1 ≥ 2×
  body 5.9, close in the lower half → SHORT at close 28092.4; stop
  = box high 28365.2, hit 07:30Z, exit at 28365.2 (SL), net −1.133%
  after costs. Matches the simulator exactly.

## Disposition

TASK-IG2-STR-13: the declared run is complete; the family FAILS the
bar and is **CLOSED** (the declaration's own failing term). No
forward-test candidacy. Board update (status + this evidence) goes
through the normal merge queue.
