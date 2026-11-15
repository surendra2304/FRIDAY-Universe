# RESULTS — TASK-STR-RD-016: RD-003 forex-native families on the forex_cross41 panel

## Verdict (plain)

**ZERO of the 8 pre-declared cells pass the programme bar. Nothing is
promoted, nothing is registered, nothing trades.** There are also **zero
near-misses** under the programme definition (expectancy > 0, PF ≥ 1.15,
≥ 200 OOS trades). Seven of eight cells lose money outright on pooled
walk-forward OOS trades net of costs; the single positive cell
(monday_gap_fade gap_1.0) is a cost artefact — expectancy +0.006%, PF
1.016 on 167 trades, and PF **0.785 at 2× costs**.

Trials added to the global counter: **12** (8 fixed-config cells + 4
wf-select procedures), taking it from 1,934 to **1,946**. The Bonferroni
gate for this round was α = 0.05 / 1,946 = 2.569e-05; no cell came
anywhere near it (best one-sided p = 0.513).

## What was run (pre-declared, frozen before execution)

Declaration: `results_rd16/declaration.json`, frozen
2026-11-15T15:53:21+05:30, sha256
`379b6b7135fef2715f5a10be62cf1a388c18c29a0b5e2d292fdd5de6e8654a64`
(the hash is in the TASK-STR-RD-016 claim comment on issue #35; the
claim post itself was bridge-blocked — see Delivery note — so the
frozen file + hash are the pre-execution record).

- Families: RD-003 Stage-2B's forex-native set, signal code
  `rd3/families_fx.py` byte-identical to main (PR #294) —
  **london_drive** (Asia-range → London breakout, bracket_time
  sl 2.0 / tp 4.0 ATR, max 9 bars), **monday_gap_fade** (weekend-gap
  fade, bracket_time sl 2.0 / tp 3.0, max 3 bars, declared open-auction
  fill), **trend_pullback** (EMA20 touch-and-reclaim inside an
  EMA100/200 trend, trail sl 2.0 / trail 3.0 ATR). RD-003's only
  session family is london_drive; it is in the set. No variant,
  threshold or exit spec was altered after the freeze.
- Panel: **forex_cross41** — TASK-STR-DATA-001's 41 FX
  crosses/minors/exotics, all tradeable on the owner's OANDA practice
  account. Cells: london_drive @1h, monday_gap_fade @1d,
  trend_pullback @1d and @4h (4h resampled from verified 1h, harness
  rule). Folds: 1d STANDARD (W1–W5), 1h/4h LATE (W2–W5; 1h history
  starts 2024-11-18). Warmup 260 bars.
- Costs: rd2/costs2 with panel name `forex_cross41` — every pair is a
  minor/cross/exotic (none in FX_MAJORS), so **10 bps round trip** for
  all 41 symbols.
- Judgement: rd2.stats2 `check_bar2` + `holdout2`, identical to
  RD-002/RD-003 (expectancy > 0, PF ≥ 1.2, ≥ 200 pooled OOS trades,
  ≥ 80% of profile folds positive with trades in ≥ profile−1 folds,
  holdout breadth/concentration/untouched-subset), plus the Bonferroni
  gate at the final N and exact 2×-cost PF ≥ 1.2 from saved trades for
  any candidate. Global counter entering the round: 1,934 (programme
  floor 1,926 through RD-005 + 8 from the most recent completed round
  per coordinator accounting — RD-009's completion entry records
  1,926 → 1,934; the declaration attributed the +8 to RD-015. The
  entering total, and therefore the gate, is identical either way.)

## Sanity anchor — PASSED bit-identically

Before any RD-016 number was produced, the harness copy reproduced
RD-001's published ts_momentum/roc42_4h pooled OOS row **exactly**
(RD-001's own `rd.common.load_timeframe` construction over RD-001's
cache): **303 trades, expectancy_net 0.0024275740638451445,
profit_factor_net 1.0969220482985518** — full float equality, with
wins/win-rate/avg-win/avg-loss/total-return/max-drawdown also matching
the published row. Record: `results_rd16/anchor.json`.

## Data verification — 82/82 series FULL_MATCH, with one disclosed episode

DATA-001's sandbox cache CSVs are 0 bytes (write truncation), so the
panel was re-fetched with DATA-001's own fetcher
(`rd_data1/fetch_expansion.py`) and verified per series against
DATA-001's `manifests.json` (csv_sha256, rows, first/last bar) before
use. Final state: **82/82 series FULL_MATCH** — every series judged is
byte-identical to the file DATA-001 hashed. Full table:
`results_rd16/data_verification.json`.

The episode, disclosed in full: all 41 daily series matched on the
first fetch. The 1h series did not — Yahoo's chart API serves **two
near-identical variants** of its 1h FX history. The non-manifest
variant differs from the manifest variant only in (a) ~0.5% of bars
served as null-OHLC (illiquid hours, concentrated 2026-06/07) and
dropped by the fetcher, and (b) sub-pip-to-~5-pip revisions on ~1% of
common bars (143 of 12,266 bars on AUDCAD; max |Δclose| 0.0005). For
all 41 series the row delta versus the manifest was *exactly* the
null-drop delta, and first/last bars always matched. Rather than judge
on the unverified variant, the crew re-fetched until Yahoo served the
manifest variant for each symbol and kept **only** files whose sha256
equals the DATA-001 manifest (a bounded collection loop; every symbol
was captured). No series was substituted, approximated or excluded:
**UNCOVERED = none** — all 8 cells ran on the full 41-symbol panel.
Declared load rule applied: the in-progress 2026-11-15 daily bar was
dropped at load (28 stub bars across 28 series; the other 13 series
end 2026-11-13).

## Results — every cell (pooled walk-forward OOS, net of 10 bps RT)

| Cell | Trades | Expectancy | PF | Win rate | Total ret | Max DD | Pos folds | Bar | p (1-sided) |
|---|---|---|---|---|---|---|---|---|---|
| london_drive/drive_plain @1h | 5,052 | −0.1115% | 0.423 | 0.331 | −99.7% | −99.7% | 0/4 | FAIL | 1.000 |
| london_drive/drive_narrow @1h | 138 | −0.1785% | 0.242 | 0.268 | −22.0% | −22.2% | 0/4 | FAIL | 1.000 |
| monday_gap_fade/gap_0.5 @1d | 658 | −0.0433% | 0.867 | 0.479 | −26.5% | −51.2% | 1/5 | FAIL | 0.912 |
| monday_gap_fade/gap_1.0 @1d | 167 | **+0.0061%** | 1.016 | 0.503 | +0.2% | −26.4% | 3/5 | FAIL | 0.513 |
| trend_pullback/pb_ema100 @1d | 443 | −0.3157% | 0.668 | 0.298 | −77.6% | −78.7% | 2/5 | FAIL | 0.999 |
| trend_pullback/pb_ema200 @1d | 428 | −0.3088% | 0.671 | 0.304 | −75.7% | −76.2% | 1/5 | FAIL | 0.999 |
| trend_pullback/pb_ema100 @4h | 3,172 | −0.2169% | 0.502 | 0.258 | −99.9% | −99.9% | 0/4 | FAIL | 1.000 |
| trend_pullback/pb_ema200 @4h | 3,018 | −0.1929% | 0.541 | 0.267 | −99.7% | −99.7% | 0/4 | FAIL | 1.000 |

Per-fold detail, holdout internals and per-symbol tables are in
`results_rd16/rows/*.json`; the ranked synthesis is
`results_rd16/synthesis.json`.

Reading of the three mechanisms, on this universe:

- **london_drive is decisively rejected on crosses.** drive_plain is
  negative in every fold and on **0 of 41 symbols** (holdout breadth
  0.000; untouched-subset expectancy −0.096% over 1,702 trades). The
  Asia→London expansion continuation does not survive 10 bps on
  crosses/minors/exotics with a 2/4 ATR bracket. drive_narrow's
  compression filter leaves only 138 trades and loses faster.
- **trend_pullback is decisively rejected at both timeframes.** All
  four cells lose in nearly every fold; 4h breadth is 2–4 positive
  symbols of 41. EMA20 touch-and-reclaim inside an EMA100/200 trend is
  a losing entry on this universe at these costs — consistent with
  RD-003, where the same family also produced no passer on
  forex28/forex12/comm7.
- **monday_gap_fade is the only non-negative mechanism, and it is
  still noise.** gap_1.0 (fade gaps > 1.0 × ATR%) is the round's sole
  watchlist row: +0.0061% expectancy, PF 1.016, 3/5 folds positive,
  untouched-subset expectancy +0.043% (52 trades). It fails the bar on
  PF (1.016 < 1.2), trade count (167 < 200), fold consistency (3 < 4)
  and holdout (0 symbols with ≥ 20 trades — the signal is too rare per
  symbol to establish breadth), its significance is nil (p = 0.513),
  and at 2× costs its PF is **0.785**. gap_0.5 (658 trades) loses
  outright (PF 0.867). The honest statement: large weekend gaps in
  crosses do not exhibit a tradeable fade at 10 bps; the gap_1.0
  residue is indistinguishable from zero.

## wf-select procedures (honesty controls — not promotion candidates)

| Procedure | Trades | Expectancy | PF | Picks |
|---|---|---|---|---|
| london_drive @1h | 5,052 | −0.1115% | 0.423 | drive_plain in W2–W5 |
| monday_gap_fade @1d | 167 | +0.0061% | 1.016 | gap_1.0 in all 5 folds |
| trend_pullback @1d | 428 | −0.3088% | 0.671 | pb_ema200 in all 5 folds |
| trend_pullback @4h | 2,271 | −0.2089% | 0.475 | pb_ema200 in W3–W5 (no in-sample trades before) |

In-sample selection does not rescue any family: the selector picks the
less-bad variant and still loses (monday_gap_fade's procedure merely
reproduces gap_1.0, for the reasons above).

## Significance / DSR disclosure

Gate = Bonferroni one-sided p < 2.569e-05 at N = 1,946 — no cell
passes (best p = 0.513). Deflated Sharpe is **non-computable in-round**
and is reported as such, not estimated: the cross-trial dispersion
estimators require ≥ 10 rows with trade_stats n ≥ 30, and this round
has only 8 cells (all 8 qualify individually, but 8 < 10). This follows
the frozen declaration (DSR disclosed where computable, never gating).

## What this round establishes

1. RD-003's three forex-native mechanisms, tuned for majors/OANDA
   structure, **do not transfer to the 41-cross universe** at realistic
   practice-account costs. Two are strongly negative (not marginal),
   one is zero-within-noise.
2. The forex_cross41 panel itself is now a fully hash-verified,
   reusable research asset (82/82 series byte-identical to DATA-001's
   manifests), and the Yahoo 1h two-variant serving behaviour is
   documented for every future round that touches Yahoo 1h data:
   verify by hash, re-fetch until the manifest variant is served,
   never judge on an unverified variant.
3. Global trial counter: **1,946**. No candidate is forwarded to the
   forward-test lane from this round.

## Delivery note

The Server-2 bridge MCP has been hung since ~15:00 IST 2026-11-15, so
the claim comment, PRs and completion comment could not be posted by
this crew directly. Delivery is packaged as a resumable
check-then-act script, `~/workspace/rd-016/deliver.py` (claim →
code/results PR → board PR from fresh main with full task-id set diff
and read-back → completion comment), for the coordinator's merge
queue. Status at packaging: **implemented + tested locally (anchor
bit-identical, all cells evaluated); NOT merged, NOT deployed**
(research code — nothing to deploy).

## Files

- `Stratex/rigorous_backtest/rd16/` — panels16.py (verified-cache
  loader), run_families16.py, synth16.py, anchor16.py
- `Stratex/rigorous_backtest/results_rd16/` — declaration.json
  (frozen, hashed), synthesis.json, anchor.json,
  data_verification.json, wf_select.json, rows/ (8 cell rows with
  saved trades where the programme screen persisted them — here, all 8)
- This file: `Stratex/rigorous_backtest/RESULTS_RD16.md`
