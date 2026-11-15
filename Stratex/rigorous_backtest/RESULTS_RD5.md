# TASK-STR-RD-005 — Session / Time-of-Day Effects: Results

**Mandate (owner wave-4 order, 2026-11-15 ~12:33 IST):** ten more
Stratex research crews; this crew's track is a NEW family — **session /
time-of-day effects**: entries conditioned on session opens
(Asia/London/New York) and hour-of-day windows, momentum-continuation
and reversal variants, on crypto30 (24/7 session effects) AND forex
majors (EURUSD, GBPUSD, USDJPY), 15m/1h. Avoid RD-003's forex-native
mean-reversion track (this is session-timing, not MR).

**Verdict, plainly: ZERO candidates, ZERO watchlist. All 162
configurations have negative out-of-sample expectancy net of costs.**
The family is a null result on every panel. Nothing here is wired
anywhere; nothing in production references this family, so there is
nothing to remove either. The counter still grows by 162 — that is
the honest price of having asked the question properly.

## Pre-declaration (frozen before any cell ran)

`results_rd5/declaration.json`, SHA-256
`4b640f87ab6921d517503ff4e87a9e7aef0a9f03899e0b02c98aa411ad6ec658`,
frozen 2026-11-15 and posted publicly in the claim on issue #35
(comment 6891055743) **before the first RD-005 cell executed**. No
variant, threshold, cell or exit spec changed after that. The runner
(`rd5/run_rd5.py`) implements the declaration exactly; an independent
re-computation (`rd5/check_btc.py`, different mechanics) reproduces
the runner's BTCUSDT expectancy for the best row to <1e-12
(−0.0014068014828270 over 853 OOS trades).

**Sub-family A — Session-Open Impulse (SOI), 32 configs/panel.**
Anchors: TOKYO 09:00 Asia/Tokyo, LONDON 08:00 Europe/London,
NEWYORK 09:30 America/New_York (local times via the tz database).
Prior move = close ratio over the last L ∈ {1h, 4h} before the entry
bar; MOM follows its sign, REV fades it; entry at the open of the
first bar at/after the anchor; pure time exit at +2h/+4h (clock-based);
session choice ∈ {TOKYO, LONDON, NEWYORK, ALL}.

**Sub-family B — Hour-Window (HOD), 20 configs/panel.** Entries at
fixed UTC hours {0, 8, 13, 16, 21}; direction from the move over the
preceding W ∈ {1h, 3h} (MOM/REV); hold = W.

Plus **6 walk-forward-select procedures** (one per sub-family ×
panel): per fold, pick the family's best in-sample variant (≥ 50
in-sample trades), judge its next fold. **Total: 156 cells + 6
procedures = 162 trials.**

**Panels.** crypto30 @1h (STANDARD folds W1–W5, OOS 2024-07-01 →
2026-11-01); crypto13 @15m (STANDARD; the 13 symbols with RD-002
15m caches); forex3 @1h (LATE folds W2–W5, OOS from 2025-01-01).
One open position per symbol; entries while busy are skipped;
prior move == 0 is no trade; crypto lookback windows must be
contiguous (an archive hole falsifies the prior move — trade
skipped); forex windows may span closures (causal, disclosed).

**Costs (round trip, per trade):** crypto 16 bps (the harness
standard), forex majors 6 bps (the programme's OANDA-modelled cost).
Exits are time-based, so the 2×-cost sensitivity is an exact
recomputation from stored entry/exit prices.

## Data (provenance first)

Only RD-002's provenanced caches were used; the runner verifies
every file's SHA-256 against its sidecar manifest before loading
(any mismatch aborts the panel). Per-file records:
`results_rd5/coverage_<panel>.json`.

| Panel | Source | Series | Range |
|---|---|---|---|
| crypto30 1h | Binance Vision public archives (per-zip SHA-256) | 30 @ 1h | 2022-01 → 2026-10 |
| crypto13 15m | Binance Vision public archives | 13 @ 15m | 2023-10 → 2026-10 |
| forex3 1h | Yahoo Finance chart API (sidecar manifests) | EURUSD, GBPUSD, USDJPY @ 1h | 2024-11-15 → 2026-11-13 |

**On "OANDA-sourced" forex data, stated plainly:** the OANDA price
API is not reachable from the research sandbox (no venue credentials
in this environment — the same disclosed basis RD-003 Stage 2B used
for its OANDA families). The historical series are RD-002's
provenanced Yahoo FX series; OANDA is the intended forward venue
and the cost model is the programme's OANDA-modelled majors cost.
No synthetic data anywhere.

**UNCOVERED:** forex 15m — Yahoo 15m depth (~60 days) cannot
support walk-forward folds. Not tested, not estimated.

## The bar (unchanged Anti-Overfit Law)

Expectancy > 0 AND PF ≥ 1.2 AND ≥ 200 OOS trades AND ≥ 80% of folds
positive AND untouched-holdout pass (alphabetical every-3rd-symbol
subset, pooled expectancy > 0 on ≥ 30 trades; forex3 holdout =
USDJPY alone, declared small-panel rule) AND breadth (≥ 50% of
symbols positive, no symbol > 50% of total positive profit) AND
2×-cost sensitivity AND Bonferroni one-sided p < 0.05/N_global
(one-sided t-test on pooled OOS per-trade net returns; DSR reported
for near-bar rows — none came near the bar, so no DSR is load-bearing
here). The ≥ 80% fold rule is applied literally: LATE panels
(4 folds) therefore need 4/4.

**Global counter:** 1,557 (RD-002 final) + 207 (RD-003 declared:
152 + 34 + 21) = **1,764 before RD-005**; RD-005 adds **162** →
gate floor **N = 1,926**, with a stability check at N = 3,000 for
any would-be candidate (wave-4 siblings RD-004/006–013 add trials in
parallel). No RD-005 verdict is anywhere near a boundary — every
row's expectancy is negative — so no verdict in this document can
flip at any final N.

## Sanity checks (before any number was trusted)

- **S1** — zero-cost SOI trades on BTCUSDT 1h: the first 5 trades'
  returns recomputed independently from raw bars match the runner
  exactly.
- **S2** — cost monotonicity: doubling costs never raises any
  trade's net return.
- **S3** — fold partition: pooled OOS trade count equals the sum of
  per-fold counts; all OOS entries fall inside the fold era.
- **Independent cross-check** — `rd5/check_btc.py` recomputes
  SOI_TOKYO_MOM_L4h_H4h on BTCUSDT with pandas asof mechanics (a
  different code path from the runner's event loop): 853 OOS trades,
  expectancy −0.0014068014828270 — identical to the runner's saved
  per-symbol figure.

## Results

### Panel summary

| Panel | Rows | Positive-expectancy rows | Mean expectancy | Best row | Best exp. | Best PF |
|---|---|---|---|---|---|---|
| crypto30 @1h | 54 | **0** | −0.161% | SOI_TOKYO_MOM_L4h_H4h | −0.077% | 0.885 |
| crypto13 @15m | 54 | **0** | −0.159% | SOI_TOKYO_MOM_L4h_H4h | −0.070% | 0.878 |
| forex3 @1h | 54 | **0** | −0.060% | SOI_NEWYORK_REV_L4h_H4h | −0.046% | 0.568 |

Full per-row evidence (pooled + per-fold metrics, breadth,
per-symbol expectancy, holdout, exact Bonferroni p):
`results_rd5/rows_<panel>.json` and `results_rd5/synthesis.json`.
Across the 162 rows the programme evaluated ≈ 2.64M OOS trades
(counted per row, so overlapping configurations recount shared
trades — the figure measures work done, not independent bets).

### Texture of the null

- **Both directions lose, everywhere.** MOM and REV are both
  negative on all three panels. That is the signature of a gross
  effect of ≈ zero paying a fixed toll: mean net expectancy is
  −0.161% on crypto against a 0.16% round-trip cost (implied gross
  ≈ −0.001%), and −0.060% on forex against a 0.06% cost (implied
  gross ≈ 0.000%). There is no session effect at these horizons to
  harvest in either direction.
- **The least-bad cell is the same on both crypto panels** —
  Tokyo-open momentum, 4h lookback, 4h hold (−0.077% @1h, −0.070%
  @15m; PF 0.885/0.878 on 25,440 / 11,037 trades). Adding back the
  16 bps cost implies a gross continuation of ≈ +0.08%/trade —
  real enough to notice, half the cost wall, and nowhere near the
  bar (it fails the first gate, expectancy > 0, outright). It is
  **not** a watchlist entry: the watchlist is for configurations
  that pass the mechanical bar and fail significance, and this one
  passes nothing. Recorded here so a future crew does not re-spend
  trials rediscovering it; any revisit would need a mechanism that
  changes the cost equation (e.g. maker execution), pre-declared
  as a new family.
- **Forex is worse than flat.** PFs run 0.12–0.57: at 1–3h holds,
  majors move so little that the 6 bps cost consumes the entire
  distribution; the 21:00 UTC hour (New York close) is the single
  worst window on the panel (PF ≈ 0.12 for W1h both directions).
- **Folds agree.** folds-positive fraction is 0.0 on 156 of 162
  rows and never above 0.2 — the null is era-consistent across
  W1–W5 / W2–W5, not one bad regime.
- **The wf-select procedures manufacture nothing** (crypto30 SOI
  procedure: −0.235%, PF 0.650; forex procedures ≈ −0.06%): given
  every advantage of in-sample selection, the factory procedure
  still loses — the same control result RD-002 found.

### Boundaries vs sibling tracks (as declared)

Not RD-002's `session_breakout` (no range-breakout condition
anywhere in RD-005) and not its `dow_effect` (no day-of-week rule).
Not RD-003's `overnight_drift` (no fixed overnight hold) or
`london_drive` (no Asia-range condition, no ATR brackets; the
London anchor is 08:00 local, not a 07:00 UTC range break). Not
RD-003's forex-native mean-reversion: RD-005 REV variants reverse
only the prior session/window move at fixed clock times.

## What this means for Stratex

Session/time-of-day timing at 15m/1h with 2–4h holds is **closed**
as a direction-picking family on crypto and the forex majors: the
effect, if any exists intraday, is smaller than the cost of
trading it. This does not touch the two RD-002 forward entrants
(daily/4h trend mechanisms, already in forward measurement under
TASK-STR-FWD-002), and it removes one more region of the search
space from contention — which is what the counter is for.

**Global trial count after RD-005: ≥ 1,926** (1,764 + 162; the
final figure rises further as RD-003 Stage 3 and the other wave-4
crews report). Research only: no production, governance, priors or
engine changes were made by this task; no live trading.
