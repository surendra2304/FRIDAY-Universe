# TASK-STR-RD-007 — Gold & Commodities Intraday: Results

**Mandate (owner Wave-4 order, 2026-11-15 ~12:33 IST):** a new research
track for Stratex — GOLD & COMMODITIES INTRADAY. XAUUSD first, then
XAGUSD and WTI; OANDA practice is the eventual venue. Distinct from
TASK-STR-RD-003's forex-pairs track. Research only; production
untouched.

**Claim:** issue #35 comment 6890936016. **Pre-declaration:** PR #290
(`results_rd7/declaration.json` + `rd7/families7.py` + `rd7/run_rd7.py`)
opened BEFORE the first cell was executed; nothing declared there was
altered afterwards.

## Verdict — stated plainly

**ZERO candidates. All 45 judged rows FAIL the bar, and not narrowly:
every one of the 30 fixed cells and all 15 walk-forward-select
procedures has NEGATIVE out-of-sample expectancy net of costs.** No
row reached the near-bar band (expectancy > 0, PF ≥ 1.15, ≥ 200
trades), so no 2×-cost sensitivity runs were triggered and there is
nothing to wire into any forward lane from this track. The least-bad
rows are still losers (best PF 0.979). Intraday breakout and
mean-reversion at 1h on gold, silver and WTI, under these declared
mechanisms, did not pay their execution costs anywhere in the
2025-01-01 → 2026-11-01 out-of-sample era.

## Data (provenance first)

| Instrument | Venue proxy for | Source series | Bars | Range (UTC) | SHA-256 |
|---|---|---|---|---|---|
| GOLD | XAUUSD (OANDA) | Yahoo GC=F via RD-002 Stage-A cache `YH_GOLD_1h.csv` | 11,438 | 2024-11-15 → 2026-11-13 | `244f8e08…abe60c` (re-verified by this crew) |
| SILVER | XAGUSD (OANDA) | Yahoo SI=F, `YH_SILVER_1h.csv` | 11,434 | 2024-11-15 → 2026-11-13 | sidecar-verified at runtime |
| WTI | WTI (OANDA) | Yahoo CL=F, `YH_WTI_1h.csv` | 11,311 | 2024-11-15 → 2026-11-13 | sidecar-verified at runtime |

- Spot XAUUSD/XAGUSD history is **not obtainable from a provenanced
  source in this sandbox**: Yahoo spot tickers 404 (RD-002 Stage A);
  Dukascopy returned HTTP 503 again on this crew's 2026-11-15 probe;
  the OANDA price API requires server-side venue credentials, which
  research crews do not pull (RD-003 Stage-2B finding). COMEX/NYMEX
  futures are the equivalently-provenanced history, exactly as RD-002
  judged comm7. Disclosed proxy caveats: Yahoo continuous futures
  embed contract-roll steps; futures basis ≠ OANDA spot/CFD pricing.
- **15m is UNCOVERED — no judged cells.** Measured 2026-11-15: Yahoo
  provenanced 15m depth for GC=F/SI=F/CL=F is 5,545 bars spanning only
  2026-09-08 → 2026-11-13 (~67 days), which cannot populate the
  walk-forward folds. No synthetic or substituted series was used.
- Folds: LATE profile (W2–W5, OOS from 2025-01-01), as every
  Yahoo-1h panel in RD-002. Costs (round trip, OANDA-practice model,
  `rd2/costs2.py`): GOLD 10 bps, SILVER 14, WTI 12.

## Method (as declared, unchanged)

Five families × two variants, per-instrument judgement at 1h:
`orb_breakout` (NY 13:00–14:59 UTC opening range, first break
15:00–18:00), `prevday_breakout` (prior-trading-day range, 08:00–18:00),
`vwap_reversion` (session-VWAP stretch fade, k = 1.5 / 2.0 ATR),
`bb_rsi_reversion` (Bollinger(20,2) + RSI extremes, ± ADX<25 filter),
`donchian_intra` (Donchian(20) break, 08:00–18:00, ± EMA200 filter).
Harness MODULE simulation (`rd/fastsim`): signal on close → entry at
next open, entry-anchored ATR brackets, stop-before-target, one
position at a time. **Every position is flat by 21:00 UTC** — enforced
by simulating each entry on its own session slice, so no position can
cross a session end, weekend or data gap by construction. Plus 15
wf-select procedures (per family × instrument; variant chosen per fold
on pre-fold data only, per the declared rule).

**Bar (unchanged):** expectancy > 0 AND PF ≥ 1.2 AND ≥ 200 OOS trades
AND ≥ 80% folds positive (via `rd2/stats2.check_bar2`) AND holdout AND
Bonferroni p < 0.05/N. Single-instrument holdout (declared substitute
for cross-symbol breadth): W5 expectancy > 0 on ≥ 30 trades. DSR
reported, not gating (RD-002 synthesis practice).

**Trial accounting:** 30 cells + 15 procedures = **45 RD-007 trials**.
Global counter: 1,557 (RD-001+RD-002) + 45 = **1,602** — a declared
LOWER bound (sibling Wave-4 crews raise the true final N; with zero
passers there is nothing to re-gate). Bonferroni α at 1,602 =
3.12e-05. Cross-cell Sharpe dispersion (DSR input): 0.0593.

**Sanity:** SHA-256 of all three series re-verified against RD-002
sidecars; 5 sampled trades from the first cell re-derived by an
independent brute-force bar scan — exit time, exit price and net
return identical in all 5 (`results_rd7/sanity_checks.json`).

## Full results — all 45 rows (pooled LATE-fold OOS, net of costs)

| # | Kind | Family / Variant | Inst | OOS trades | Expectancy/trade | PF | +Folds | W5 trades | W5 exp | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cell | prevday_breakout / pd_ema | SILVER | 278 | -0.014% | 0.979 | 1/4 | 50 | -0.010% | FAIL |
| 2 | cell | donchian_intra / dc_ema | GOLD | 272 | -0.019% | 0.938 | 2/4 | 49 | +0.002% | FAIL |
| 3 | wf | donchian_intra / wf_select | GOLD | 296 | -0.032% | 0.893 | 2/4 | 49 | +0.002% | FAIL |
| 4 | wf | prevday_breakout / wf_select | SILVER | 315 | -0.034% | 0.948 | 1/4 | 50 | -0.010% | FAIL |
| 5 | cell | bb_rsi_reversion / bbr_adx | SILVER | 80 | -0.040% | 0.925 | 3/4 | 11 | +0.260% | FAIL |
| 6 | cell | prevday_breakout / pd_plain | SILVER | 322 | -0.048% | 0.928 | 1/4 | 57 | -0.090% | FAIL |
| 7 | cell | orb_breakout / orb_narrow | SILVER | 66 | -0.049% | 0.881 | 2/4 | 12 | -0.271% | FAIL |
| 8 | cell | donchian_intra / dc_plain | GOLD | 349 | -0.055% | 0.830 | 0/4 | 63 | -0.033% | FAIL |
| 9 | cell | prevday_breakout / pd_ema | GOLD | 276 | -0.068% | 0.801 | 0/4 | 50 | -0.020% | FAIL |
| 10 | cell | vwap_reversion / vwap_20 | SILVER | 185 | -0.073% | 0.852 | 1/4 | 38 | -0.240% | FAIL |
| 11 | wf | prevday_breakout / wf_select | GOLD | 287 | -0.075% | 0.783 | 0/4 | 50 | -0.020% | FAIL |
| 12 | cell | bb_rsi_reversion / bbr_pure | GOLD | 178 | -0.078% | 0.746 | 0/4 | 31 | -0.150% | FAIL |
| 13 | wf | bb_rsi_reversion / wf_select | GOLD | 129 | -0.081% | 0.714 | 0/4 | 10 | -0.481% | FAIL |
| 14 | cell | prevday_breakout / pd_plain | GOLD | 314 | -0.092% | 0.744 | 0/4 | 60 | -0.077% | FAIL |
| 15 | cell | donchian_intra / dc_ema | WTI | 333 | -0.095% | 0.844 | 0/4 | 58 | -0.114% | FAIL |
| 16 | wf | bb_rsi_reversion / wf_select | SILVER | 155 | -0.099% | 0.804 | 1/4 | 11 | +0.260% | FAIL |
| 17 | cell | vwap_reversion / vwap_20 | GOLD | 192 | -0.101% | 0.655 | 0/4 | 38 | -0.085% | FAIL |
| 18 | cell | vwap_reversion / vwap_20 | WTI | 162 | -0.105% | 0.812 | 2/4 | 30 | +0.106% | FAIL |
| 19 | cell | donchian_intra / dc_plain | WTI | 414 | -0.106% | 0.827 | 0/4 | 74 | -0.224% | FAIL |
| 20 | wf | donchian_intra / wf_select | WTI | 414 | -0.106% | 0.827 | 0/4 | 74 | -0.224% | FAIL |
| 21 | cell | vwap_reversion / vwap_15 | WTI | 429 | -0.106% | 0.792 | 1/4 | 71 | +0.087% | FAIL |
| 22 | wf | vwap_reversion / wf_select | WTI | 429 | -0.106% | 0.792 | 1/4 | 71 | +0.087% | FAIL |
| 23 | cell | orb_breakout / orb_narrow | GOLD | 82 | -0.110% | 0.604 | 0/4 | 11 | -0.198% | FAIL |
| 24 | cell | vwap_reversion / vwap_15 | GOLD | 379 | -0.111% | 0.624 | 0/4 | 76 | -0.067% | FAIL |
| 25 | wf | orb_breakout / wf_select | SILVER | 169 | -0.112% | 0.676 | 1/4 | 12 | -0.271% | FAIL |
| 26 | cell | bb_rsi_reversion / bbr_pure | SILVER | 199 | -0.117% | 0.792 | 0/4 | 30 | -0.166% | FAIL |
| 27 | wf | vwap_reversion / wf_select | GOLD | 286 | -0.119% | 0.610 | 0/4 | 38 | -0.085% | FAIL |
| 28 | cell | orb_breakout / orb_plain | WTI | 335 | -0.120% | 0.747 | 0/4 | 68 | -0.221% | FAIL |
| 29 | wf | vwap_reversion / wf_select | SILVER | 293 | -0.120% | 0.755 | 1/4 | 38 | -0.240% | FAIL |
| 30 | wf | orb_breakout / wf_select | GOLD | 180 | -0.120% | 0.500 | 0/4 | 11 | -0.198% | FAIL |
| 31 | cell | orb_breakout / orb_plain | GOLD | 274 | -0.121% | 0.500 | 0/4 | 51 | -0.107% | FAIL |
| 32 | cell | bb_rsi_reversion / bbr_adx | GOLD | 56 | -0.126% | 0.600 | 0/4 | 10 | -0.481% | FAIL |
| 33 | wf | orb_breakout / wf_select | WTI | 209 | -0.145% | 0.676 | 0/4 | 68 | -0.221% | FAIL |
| 34 | cell | donchian_intra / dc_ema | SILVER | 296 | -0.162% | 0.740 | 0/4 | 54 | -0.062% | FAIL |
| 35 | cell | vwap_reversion / vwap_15 | SILVER | 379 | -0.163% | 0.704 | 0/4 | 79 | -0.138% | FAIL |
| 36 | cell | bb_rsi_reversion / bbr_adx | WTI | 77 | -0.163% | 0.679 | 1/4 | 14 | -0.379% | FAIL |
| 37 | cell | bb_rsi_reversion / bbr_pure | WTI | 242 | -0.168% | 0.711 | 0/4 | 44 | -0.091% | FAIL |
| 38 | cell | orb_breakout / orb_plain | SILVER | 249 | -0.169% | 0.608 | 0/4 | 49 | -0.275% | FAIL |
| 39 | cell | orb_breakout / orb_narrow | WTI | 101 | -0.175% | 0.635 | 0/4 | 25 | -0.244% | FAIL |
| 40 | cell | prevday_breakout / pd_plain | WTI | 320 | -0.177% | 0.753 | 0/4 | 58 | -0.215% | FAIL |
| 41 | wf | prevday_breakout / wf_select | WTI | 320 | -0.177% | 0.753 | 0/4 | 58 | -0.215% | FAIL |
| 42 | wf | donchian_intra / wf_select | SILVER | 361 | -0.178% | 0.716 | 0/4 | 54 | -0.062% | FAIL |
| 43 | wf | bb_rsi_reversion / wf_select | WTI | 172 | -0.185% | 0.604 | 0/4 | 14 | -0.379% | FAIL |
| 44 | cell | donchian_intra / dc_plain | SILVER | 376 | -0.192% | 0.696 | 0/4 | 69 | -0.163% | FAIL |
| 45 | cell | prevday_breakout / pd_ema | WTI | 293 | -0.193% | 0.728 | 0/4 | 52 | -0.083% | FAIL |

## Reading the wreckage (diagnostics, labelled as such)

The failure is uniform, not marginal — but it is not uniform noise
either. The least-bad rows cluster just below breakeven NET, which
means their gross-of-cost edges are slightly positive and simply too
small to pay 10–14 bps round-trip costs at 1h frequency:

- prevday_breakout/pd_ema SILVER: net -0.014%/trade, PF 0.979; labelled approximation of gross-of-cost expectancy ≈ +0.126%/trade (net + the round-trip cost) — a real but tiny gross edge, roughly an order of magnitude below what PF ≥ 1.2 net requires at these win/loss shapes.
- donchian_intra/dc_ema GOLD: net -0.019%/trade, PF 0.938; labelled approximation of gross-of-cost expectancy ≈ +0.081%/trade (net + the round-trip cost) — a real but tiny gross edge, roughly an order of magnitude below what PF ≥ 1.2 net requires at these win/loss shapes.
- donchian_intra/wf_select GOLD: net -0.032%/trade, PF 0.893; labelled approximation of gross-of-cost expectancy ≈ +0.068%/trade (net + the round-trip cost) — a real but tiny gross edge, roughly an order of magnitude below what PF ≥ 1.2 net requires at these win/loss shapes.
- prevday_breakout/wf_select SILVER: net -0.034%/trade, PF 0.948; labelled approximation of gross-of-cost expectancy ≈ +0.106%/trade (net + the round-trip cost) — a real but tiny gross edge, roughly an order of magnitude below what PF ≥ 1.2 net requires at these win/loss shapes.
- bb_rsi_reversion/bbr_adx SILVER: net -0.040%/trade, PF 0.925; labelled approximation of gross-of-cost expectancy ≈ +0.100%/trade (net + the round-trip cost) — a real but tiny gross edge, roughly an order of magnitude below what PF ≥ 1.2 net requires at these win/loss shapes.

That is a statement about magnitude, not a near-miss: PF ≥ 1.2 net
would require several times these gross edges. Nothing in this table
justifies a parameter re-tune — re-tuning on the same data is exactly
what the trial counter exists to prevent; any future attempt at these
mechanisms belongs in a new pre-declared round (e.g. with 15m data if
a provenanced long series ever becomes obtainable, or on genuinely
different mechanisms), and its trials would add to the counter.

## Consequences

- Nothing is wired, registered or forwarded. The forward lane
  (TASK-STR-FWD-002/003/004) is unaffected.
- The owner's removal rule is not triggered: these were never
  production strategies — they are research configurations that failed
  at the gate, which is the gate working as designed.
- Full per-fold metrics, per-row significance and provenance records:
  `results_rd7/rows.json`; ranked synthesis: `results_rd7/synthesis.json`.
