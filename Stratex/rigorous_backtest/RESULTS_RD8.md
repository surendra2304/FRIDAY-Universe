# TASK-STR-RD-008 — Index Strategies (US500 / NAS100): Results

**Mandate (Wave 4, 2026-11-15):** a new strategy family track for the
two index CFDs Stratex will eventually trade on OANDA practice —
US500 (S&P 500) and NAS100 (Nasdaq-100). Pre-declared mechanisms:
overnight-gap behaviour, intraday mean reversion, and momentum
variants, at 15m / 1h / daily. Research only; nothing here touches
production, the registry, or any daemon.

**Status: COMPLETE. Verdict: ZERO candidates, ZERO watchlist entries.**
No configuration in this track passes the bar, and none comes close
enough to argue with: every one of the 13 cells with ≥ 200
out-of-sample trades has **negative** expectancy. The only positive
rows are daily momentum cells running on 8–55 trades — the 2024–2026
bull market's drift visible through a handful of long trades, which
the bar exists precisely to refuse. Details and the full table below;
nothing from this track should be wired into any forward lane.

## The bar (unchanged) and the declared adaptations

Expectancy > 0 AND PF ≥ 1.2 AND ≥ 200 pooled OOS trades AND ≥ 80% of
folds positive AND holdout pass AND Bonferroni one-sided p <
0.05 / N_running AND 2×-cost pass (pooled expectancy > 0, PF ≥ 1.2).
Costs: `rd2/costs2.py` index model, **8 bps round trip** (OANDA
practice CFD spread model). In-sample nothing — every variant was
fixed in `results_rd8/declaration.json` before the first cell ran;
judgement is OOS-only under walk-forward folds.

Three adaptations were pre-declared in that file (not invented after
the fact): (1) gap fills use open-auction semantics (RD-003 Stage-2B
precedent); (2) the holdout's ≥ 3-active-symbol gate is adapted to
this mandated 2-instrument panel (gate ≥ 2; breadth ≥ 50% and the
0.8 small-panel concentration cap unchanged; untouched subset = SPX,
named in advance); (3) 15m cells use a declared SHORT fold profile
(first 10 sessions warm-up era, then 4 consecutive session blocks) and
their verdicts are capped at WATCHLIST-SCREEN because ~60 days is a
single era. Intraday gap/MR cells also carry a declared session-flat
exit rule (flat by the entry session's close).

**Trial accounting.** 43 cells + 10 walk-forward-select procedures =
**53 RD-008 trials**, joining the global counter. Running floor:
1,557 (through RD-002) + 152 (RD-003 Stage 1) + 34 (RD-003 Stage 2,
counted from its declaration) + 21 (RD-003 Stage 2B) + 53 =
**N_floor 1,817** (Bonferroni α = 2.75e-5). Concurrent Wave-4 crews
add further trials, so the true final N is higher; it changes nothing
here — the best break-even N among all 43 rows is 21.

**Sanity anchor.** Before any RD-008 number was produced, RD-001's
`ts_momentum roc42_4h` cell (BTC/ETH/SOL) was re-run through the
untouched RD-002 chain: **303 trades, expectancy
0.0024275740638451445, PF 1.0969220482985518 — bit-identical** to the
archived row (`results_rd8/sanity_anchor.json`).

## Stage A — Data (provenance first)

| Series | Source | Bars | Range | Folds |
|---|---|---|---|---|
| SPX, NDX @ 1d | Yahoo Finance chart API (RD-002 Stage-A caches, SHA-256 re-verified at load) | 2,230 each | 2018-01-02 → 2026-11-13 | STANDARD W1–W5 |
| SPX, NDX @ 1h | same | 3,477 each | 2024-11-15 → 2026-11-13 | LATE W2–W5 |
| SPX, NDX @ 15m | Yahoo chart API, new fetch by `rd8/fetch_15m.py` (manifest + response hash in the crew cache) | 1,561 each | 2026-08-21 → 2026-11-13 | SHORT S1–S4 |

Sessions are America/New_York dates; Yahoo cash-index bars cover the
US regular session only. Cash-index volume is unusable (first-bar
volume is 0 in the source), so every feature is price-only — no VWAP
variant was declared, because its input does not exist.

**UNCOVERED, with reasons:** 15m history beyond ~60 days (Yahoo's hard
API depth limit; OANDA API unreachable from the sandbox; Dukascopy /
Stooq already shown unviable here in RD-002). Index overnight *drift*
(holding the closed-market window) remains uncovered for RD-003's
reason — the window does not exist in cash-index bars; this track
tests the gap at the open and the session after it, which do exist.

**Panel caveat (declared):** NDX is a subset of the S&P 500 universe
and the two series are ~0.95 correlated, so pooled trade counts
overstate independent evidence; same-day trade pairs are
near-duplicates. The pooled bar is applied as coded (programme
convention) and the caveat rides on every verdict.

## Results — all 43 cells (pooled OOS, net of costs)

| family | variant | tf | trades | exp %/trade | PF | folds+ | 2×-cost PF | verdict |
|---|---|---|---|---|---|---|---|---|
| ema_cross | ema20_100 | 1d | 8 | +5.980 | 17.492 | 2/5 | 16.820 | FAIL (trades, folds, holdout, Bonferroni) |
| tsmom | roc126 | 1d | 8 | +3.600 | 3.779 | 1/5 | 3.652 | FAIL (trades, folds, holdout, Bonferroni) |
| tsmom | roc63 | 1d | 14 | +2.620 | 2.938 | 2/5 | 2.838 | FAIL (trades, folds, holdout, Bonferroni) |
| ema_cross | ema10_50 | 1d | 19 | +1.976 | 2.160 | 3/5 | 2.088 | FAIL (trades, folds, holdout, Bonferroni) |
| donchian | n20 | 1d | 55 | +0.204 | 1.105 | 2/5 | 1.062 | FAIL (PF, trades, folds, holdout) |
| tsmom | roc64 | 15m | 50 | +0.084 | 1.261 | 3/4 | 1.011 | FAIL (trades, holdout; screening-capped) |
| tsmom | roc16 | 15m | 97 | +0.028 | 1.081 | 2/4 | 0.868 | FAIL (PF, trades, folds, holdout, 2×) |
| ema_cross | ema12_48 | 1h | 121 | +0.005 | 1.007 | 2/4 | 0.907 | FAIL (PF, trades, folds, holdout, 2×) |
| tsmom | roc21 | 1d | 37 | −0.023 | 0.988 | 3/5 | 0.949 | FAIL |
| gap_intra | follow_06 | 15m | 34 | −0.031 | 0.836 | 2/4 | 0.531 | FAIL |
| ema_cross | ema16_64 | 15m | 43 | −0.034 | 0.925 | 1/4 | 0.772 | FAIL |
| tsmom | roc12 | 1h | 238 | −0.035 | 0.955 | 2/4 | 0.860 | FAIL |
| zrev | w50_t2.0 | 1h | 188 | −0.037 | 0.861 | 1/4 | 0.626 | FAIL |
| gap_intra | follow_03 | 15m | 64 | −0.040 | 0.784 | 1/4 | 0.487 | FAIL |
| gap_intra | follow_03 | 1h | 484 | −0.043 | 0.876 | 1/4 | 0.686 | FAIL |
| gap_intra | follow_06 | 1h | 265 | −0.044 | 0.886 | 1/4 | 0.712 | FAIL |
| gap_daily | follow_03 | 1d | 611 | −0.066 | 0.833 | 3/5 | 0.666 | FAIL |
| tsmom | roc48 | 1h | 152 | −0.070 | 0.905 | 1/4 | 0.810 | FAIL |
| gap_daily | follow_06 | 1d | 316 | −0.071 | 0.845 | 2/5 | 0.699 | FAIL |
| rsi_rev | rsi2 | 1h | 686 | −0.091 | 0.654 | 0/4 | 0.456 | FAIL |
| rsi_rev | rsi7 | 1h | 342 | −0.097 | 0.627 | 0/4 | 0.432 | FAIL |
| gap_daily | fade_03 | 1d | 611 | −0.100 | 0.756 | 1/5 | 0.607 | FAIL |
| gap_daily | fade_06 | 1d | 316 | −0.105 | 0.776 | 2/5 | 0.643 | FAIL |
| zrev | w20_t2.0 | 1h | 280 | −0.109 | 0.642 | 1/4 | 0.463 | FAIL |
| gap_intra | fade_03 | 1h | 485 | −0.111 | 0.715 | 0/4 | 0.565 | FAIL |
| donchian | n20 | 1h | 272 | −0.111 | 0.860 | 1/4 | 0.775 | FAIL |
| rsi_rev | rsi2 | 15m | 177 | −0.113 | 0.495 | 0/4 | 0.300 | FAIL |
| gap_intra | fade_06 | 1h | 265 | −0.113 | 0.743 | 0/4 | 0.604 | FAIL |
| zrev | w50_t2.5 | 1h | 86 | −0.114 | 0.671 | 0/4 | 0.511 | FAIL |
| donchian | n20 | 15m | 117 | −0.115 | 0.715 | 0/4 | 0.574 | FAIL |
| zrev | w20_t2.0 | 15m | 116 | −0.117 | 0.510 | 0/4 | 0.312 | FAIL |
| zrev | w20_t2.5 | 15m | 84 | −0.124 | 0.498 | 0/4 | 0.305 | FAIL |
| rsi_rev | rsi7 | 15m | 118 | −0.129 | 0.472 | 0/4 | 0.290 | FAIL |
| zrev | w20_t2.5 | 1h | 137 | −0.148 | 0.574 | 1/4 | 0.429 | FAIL |
| ema_cross | ema24_96 | 1h | 79 | −0.148 | 0.804 | 1/4 | 0.718 | FAIL |
| donchian | n55 | 1h | 174 | −0.157 | 0.796 | 1/4 | 0.713 | FAIL |
| ema_cross | ema32_128 | 15m | 27 | −0.164 | 0.637 | 1/4 | 0.523 | FAIL |
| zrev | w50_t2.0 | 15m | 73 | −0.167 | 0.393 | 1/4 | 0.240 | FAIL |
| gap_intra | fade_03 | 15m | 64 | −0.168 | 0.350 | 0/4 | 0.215 | FAIL |
| donchian | n55 | 15m | 64 | −0.188 | 0.599 | 1/4 | 0.487 | FAIL |
| zrev | w50_t2.5 | 15m | 46 | −0.210 | 0.326 | 1/4 | 0.207 | FAIL |
| gap_intra | fade_06 | 15m | 34 | −0.220 | 0.264 | 0/4 | 0.167 | FAIL |
| donchian | n55 | 1d | 41 | −0.367 | 0.823 | 2/5 | 0.790 | FAIL |

Full per-fold / per-symbol / holdout / significance detail per row:
`results_rd8/rows/`; synthesis: `results_rd8/synthesis.json`.

**Walk-forward-select procedures (10):** the factory's own selection
method, given every advantage, manufactures nothing either — 9 of 10
procedures are negative (gap_daily 1d PF 0.845; gap_intra 1h 0.832;
zrev 1h 0.614; rsi_rev 1h 0.501; tsmom 1d 0.722; tsmom 1h 0.884;
donchian 1d 0.823; donchian 1h 0.486; ema_cross 1h 0.539). The tenth
(ema_cross 1d, PF 17.49) is the same 8-trade artefact as its best
fixed cell, selected — not corroborated — by the procedure.

## Texture — what the 7,498 pooled OOS trades say

- **The overnight gap is not tradeable on this pair, in either
  direction.** Follow and fade both lose at both thresholds
  (0.3% / 0.6%), on daily bars (611 + 316 trades per mode) and inside
  the following session at 1h and 15m. Whatever the gap knows is in
  the price before a CFD trader can act on it, and the 8 bps cost
  takes the rest. This closes the gap question for US500/NAS100 with
  real sample sizes, not with an absence of data.
- **Session-bounded intraday mean reversion is decisively negative.**
  All 12 zrev/rsi_rev cells lose; the highest-volume cell in the
  track (rsi2 @ 1h, 686 trades) returns PF 0.654. On cash indices the
  intraday deviations being faded are smaller than the cost of
  fading them — the opposite of the crypto tape this programme knows.
  At 2× costs these cells collapse to PF 0.21–0.63.
- **Daily momentum is the only positive region, and it is era
  drift, not evidence.** ema20_100 (+5.98%, 8 trades), roc126
  (+3.60%, 8), roc63 (+2.62%, 14), ema10_50 (+1.98%, 19) are positive
  in both symbols — but on 4–10 trades per symbol, with 1–3 of 5
  folds positive, break-even Bonferroni N of 0–21 against a running
  1,817, and deflated Sharpe ≤ 0.54. The identical mechanisms at 1h,
  where samples are honest (roc12: 238 trades), are negative
  (−0.035%, PF 0.955). RD-002's read of the wider idx7 panel
  ("indices mildly positive at daily only") is the same observation;
  on the tradable pair, judged alone, it does not survive contact
  with the bar.
- **Nothing here is a near-miss.** The best high-sample row in the
  track is 3.5 bps/trade *underwater*. There is no parameter tweak
  inside the declared grids that a re-run could honestly promote —
  and per the declaration rule, any tweak would be new trials judged
  at a higher N anyway.

## Consequence for the OANDA lane

No RD-008 configuration is eligible for the forward-test lane, and
none should be added to TASK-STR-FWD-004's measurement set. The
OANDA forward programme continues to rest on the governed FX line
(FX-MR-v4 under FWD-004) and on RD-003's forex-native families, not
on index CFDs. If index exposure is wanted later, the honest next
step is not another backtest variant of these mechanisms — it is a
different data class (index *futures* with overnight sessions and
real volume, e.g. ES/NQ), which this sandbox cannot provenance today
and which is therefore UNCOVERED, not approximated.

## Files

- `results_rd8/declaration.json` — the frozen pre-declaration
  (mechanisms, variants, cells, deviations, trial accounting).
- `rd8/families_idx.py`, `rd8/run_idx.py`, `rd8/synth8.py`,
  `rd8/fetch_15m.py`, `rd8/anchor_check.py` — the track's code.
- `results_rd8/rows/` (43 rows), `results_rd8/wf_select.json`,
  `results_rd8/synthesis.json`, `results_rd8/coverage_rd8.json`,
  `results_rd8/sanity_anchor.json` — the evidence.
