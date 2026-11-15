# RESULTS_RD15 — Market-regime gating of the two live forward entrants

**Task:** TASK-STR-RD-015 (Wave 5, research only). **Question:** can a causal
market-regime detector improve the two live forward entrants —
**ichimoku_trend / tk_cloud @ crypto30 4h** and **dow_effect / reversal @
crypto30 1d** — by standing them down (suppressing entries) in hostile
regimes?

**Verdict: for ichimoku, NO — every declared gate makes it worse. For
dow_effect, ONE gate passes the pre-declared improvement rule:
`gate_vol` (stand down when volatility is in its top tercile).** It is a
candidate for the owner's decision plus forward-demo validation, nothing
more — **the live entrants' parameters and behaviour are unchanged by
this study.**

## Method (pre-declared, frozen before execution)

- Declaration: `results_rd15/declaration.json`, SHA-256
  `c22148e9b896f689da649453dc395051d0957f9dcb74758985afe6bd453c9d0c`,
  frozen 2026-11-15 before the first gated execution and shipped as
  commit 1 of this task's PR.
- **Resimulation, not trade-list filtering.** Entries were regenerated
  with RD-002's own config objects (`rd2.families2.build_configs`,
  `rd2.families3.build_configs3`), gates dropped candidate entries
  *before* simulation (a stood-down entry frees its position slot,
  exactly as a live stand-down would), and trades were simulated by
  `rd.fastsim.simulate_entries` under each entrant's declared exit spec
  (ichimoku: bracket 2.0/4.0 ATR; dow: bracket_time 3.0/6.0 ATR, max
  5 bars). Metrics: `rd2.stats2.fold_report`, folds **W1..W5** exactly
  as RD-002, entry-time attribution, net of the RD-002 crypto cost
  model (16 bps round trip).
- **Data:** identical to RD-002 — the Stage-A Binance Vision caches
  (SHA-256-verified by the harness loader), crypto30 panel. No new
  data, no substitutions.
- **Anchors (both bit-identical):** the ungated resimulations reproduce
  RD-002's published pooled OOS numbers with **zero error** — ichimoku
  2,302 trades, expectancy 0.008937174793676827, PF 1.27834395636154;
  dow 3,660 trades, expectancy 0.0087767850641235, PF 1.2574511877169772.
  A second, independent execution path (per-symbol prep shards) reproduced
  both anchors bit-identically again.
- **Detector** (per symbol, at the strategy timeframe, causal — the
  state at a signal bar uses bars ≤ that bar only; harness
  `rd.common` implementations): **RANGING** = ADX(14) < 20;
  **VOL_HIGH** = ATR%(14) at or above the 2/3 percentile of its trailing
  252 values; **COUNTER_TREND** = entry side opposing EMA(50) vs
  EMA(200). UNKNOWN state (insufficient warm-up) is *not* hostile — the
  entry is kept; in the event, **zero** OOS-window signals were UNKNOWN.
- **Gates:** `gate_range` (stand down when RANGING), `gate_vol` (stand
  down when VOL_HIGH), `gate_both` (either), `gate_counter` (stand down
  when COUNTER_TREND). **8 trials** (4 gates × 2 entrants) join the
  global counter: floor **1,817 → 1,825**. Anchors and 2×-cost
  sensitivity re-runs are not trials.
- **Improvement rule (pre-declared, ALL four required):** gated
  expectancy > ungated; gated PF ≥ ungated; gated max drawdown no
  deeper; gated trades ≥ 50% of ungated.

## Results — ichimoku_trend / tk_cloud, crypto30, 4h

Ungated anchor: **2,302 trades, expectancy +0.8937%/trade, PF 1.278,
max DD −99.85%** (pooled compounded convention — see caveat below).

| gate | signals dropped | trades | expectancy | PF | max DD | verdict |
|---|---|---|---|---|---|---|
| gate_range | 2,688 / 5,959 | 1,339 | +0.8633% | 1.250 | −99.29% | does not improve (expectancy ↓, PF ↓) |
| gate_vol | 1,774 / 5,959 | 1,712 | +0.5995% | 1.209 | −99.62% | does not improve (expectancy ↓, PF ↓) |
| gate_both | 3,955 / 5,959 | 824 | +0.7207% | 1.250 | −90.16% | does not improve (expectancy ↓, PF ↓, only 35.8% of trades retained) |
| gate_counter | 2,064 / 5,959 | 1,526 | +0.7663% | 1.228 | −99.63% | does not improve (expectancy ↓, PF ↓) |

Texture: ichimoku's edge is concentrated in precisely the states the
gates call hostile. A trend-follower's entries often fire early in a
move — against the slow EMA(200) (`gate_counter` removes a third of its
signals and a fifth of its expectancy), in rising volatility
(`gate_vol` removes its best tail), and before ADX confirms the trend
(`gate_range`). The combined gate does cut the pooled drawdown
materially (−90.2% vs −99.8%), but it pays for it with expectancy, PF
and two-thirds of the trade flow. **No gate for ichimoku.**

## Results — dow_effect / reversal, crypto30, 1d

Ungated anchor: **3,660 trades, expectancy +0.8777%/trade, PF 1.257,
max DD −100.00%** (saturated — see caveat).

| gate | signals dropped | trades | expectancy | PF | max DD | verdict |
|---|---|---|---|---|---|---|
| gate_range | 1,877 / 6,208 | 2,570 | +0.8359% | 1.236 | −100.00% | does not improve (expectancy ↓, PF ↓) |
| **gate_vol** | 1,836 / 6,208 | 2,560 | **+0.9437%** | **1.289** | −99.94% | **IMPROVES — all four checks pass** |
| gate_both | 3,424 / 6,208 | 1,608 | +0.8888% | 1.262 | −99.87% | does not improve — fails ONLY the retention check (43.9% < 50%); expectancy/PF/DD all improve |
| gate_counter | 3,238 / 6,208 | 1,764 | +0.7180% | 1.216 | −99.98% | does not improve (expectancy ↓, PF ↓) |

### The one passing gate, in full

`gate_vol` on dow_effect: stand the Monday-reversal entry down when the
symbol's ATR%(14) sits in the top tercile of its trailing 252 values.

- Pooled OOS: expectancy **+0.8777% → +0.9437%/trade** (+0.066pp,
  +7.5% relative), PF **1.257 → 1.289**, win rate unchanged (52.27% →
  52.27% — the gate improves the win/loss size mix, not the hit rate),
  2,560 of 3,660 trades retained (70.0%).
- Per-fold expectancy (ungated → gated): W1 +1.045% → +0.984%
  (slightly worse), W2 +1.774% → +1.757% (flat), W3 +1.087% → +1.494%
  (strongly better), W4 −0.455% → −0.134% (the one losing fold's loss
  shrinks by ~70%), W5 +1.001% → +1.029% (slightly better). The
  improvement is **broad-based, not one fold's artefact**.
- **2×-cost sensitivity:** gated expectancy +0.7836%, PF 1.235 — versus
  the ungated strategy at the same doubled costs, +0.7173%, PF 1.206.
  The improvement **survives 2× costs** on both measures.
- Mechanism, stated plainly: a fixed-horizon (≤5 bar) Monday reversal
  is a bet that last week's move over-extended; in top-tercile
  volatility those moves are more often genuine repricing than
  over-extension, and the 3-ATR stop is reached more easily. Standing
  those Mondays down removes a net-negative slice.

Effect size honesty: +0.066pp of expectancy is **modest**, and this is
an 8-trial screen judged by a pre-declared descriptive rule, not a
significance test. The correct next step — if the owner wants it — is
forward-demo validation of gated vs ungated dow_effect, not adoption.

## Caveats

- **Drawdown convention:** the harness's pooled max DD compounds every
  trade sequentially across 30 symbols; at 2,300–3,700 trades it
  saturates near −100% and is **not** a portfolio drawdown. It is used
  here only comparatively (gated vs ungated, same convention), and of
  the four improvement checks it is the weakest — for dow gate_vol the
  DD difference (−99.94% vs −100.00%) carries little weight next to the
  expectancy/PF/fold evidence.
- Signals counted (5,959 / 6,208) are all candidate entries generated
  over the full data span, including pre-OOS warm-up years and entries
  the simulator skips while a position is open; trade counts are the
  OOS-fold figures, as in RD-002.
- Execution note (transparency): in this sandbox, long processes and
  file writes were intermittently blocked (EPERM / early termination)
  and /tmp filled during the session, so the study was executed through
  per-cell drivers importing the shipped `rd15/run_gate.py` functions
  verbatim (plus a per-symbol prep-shard path whose ungated anchors
  reproduced RD-002 bit-identically, cross-checking the primary path).
  The shipped runner (`python3 -m rigorous_backtest.rd15.run_gate`)
  performs the identical computation in one pass.

## Bottom line

Regime gating is **not** a general upgrade: it damages the
trend-follower in every declared form. It does help the calendar
reversal — narrowly, through the volatility gate alone. One candidate
for the owner: **dow_effect + gate_vol**, expectancy +0.9437%/trade,
PF 1.289, improvement intact at 2× costs — to be forward-validated on
demo before any live change. The live entrants are unchanged.

Trial accounting: 8 trials; global counter floor after RD-015 =
**1,825**.
