# TASK-STR-RD-014 — Volatility-Targeted Trend with a Drawdown Brake: Results

**Verdict: ZERO of 96 pre-declared configurations pass the standing bar. No candidate, no watchlist, no forward entrant, no production change.**

Claim + hashed pre-declaration (posted BEFORE first execution): https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6891611635 — declaration SHA-256 `55007e3b4a742f2ba42b9a690e053646dcd27de0e55b7f1ce3ae779180684022` (`results_rd14/declaration.json`).

## What was tested

The mechanism TASK-STR-RD-013's rotation failure pointed to. RD-013 died on drawdown alone (0/48 inside its 20% DD limit; best −21.0%, median −36.7%) and its completion note named the missing ingredient: a risk mechanism. This family tests exactly that mechanism on plain trend signals, as a new pre-declared family — not a retune of RD-013 (different universe, judgement unit and signal class):

- **Universe / data:** crypto30 (RD-002 list), RD-002 Stage-A hash-verified Binance Vision caches; coverage 30/30 symbols at both timeframes. Timeframes **4h, 1d**; folds W1–W5; OOS = episodes entered in [2024-07-01, 2026-11-01).
- **Signals** (long/short symmetric, close-decided, held next bar): tsmom42, tsmom126, ema10_50, ema20_100.
- **Vol-target sizing:** w = sign × min(1, σ\*/σ_t), σ_t = trailing 42-bar realized vol; **σ\* ∈ {15%, 30%, 60%}**; cap 1.0, no leverage.
- **Drawdown brake** (driven causally by the same configuration's UNBRAKED shadow equity per symbol): **none** (control) / **flat_05** (flat at −5% DD, release at −2.5%) / **flat_10** (flat at −10%, release at −5%) / **half_10** (half size at −10%, release at −5%).
- **Judgement unit:** position episodes (maximal constant-sign non-zero runs), judged with the untouched rd2 machinery (fold_report / holdout2 / check_bar2). Costs: 8 bps per unit of |Δposition| turnover (harness crypto standard); every cell also re-run at 2× costs.
- **Grid: 4 × 3 × 4 × 2 = 96 trials.** Bonferroni gate at the declared global counter N = 1,913 (floor 1,817 at declaration + 96). Break-even N per row in `results_rd14/synthesis.json`.

**Sanity anchor (before any RD-014 number was trusted):** RD-001's roc42_4h cell reproduced bit-identically through the rd2 chain — 303 trades, expectancy 0.0024275740638451445, PF 1.0969220482985518 (`results_rd14/sanity_anchor.json`). Engine verification: an independent episode re-implementation reproduced episode counts exactly with max per-episode deviation < 5e-5, and the brake mechanics audit found 0 position mismatches across the panel (`results_rd14/verification.json`, `rd14/verify14.py`).

## How the family died — gate by gate (of 96)

| gate | survivors |
|---|---|
| ≥ 200 OOS episodes | 69 |
| pooled expectancy > 0 | 38 |
| holdout2 (breadth / concentration / untouched subset) | 16 |
| PF ≥ 1.2 | 6 |
| ≥ 80% of folds positive | 6 |
| Bonferroni at N = 1,913 (and identically at the 1,987 current-floor reference) | 2 |
| 2×-cost gate | 4 |
| **full bar (all gates)** | **0** |

No cell is close on all axes at once. The failures are structural, not marginal:

**1. The positive expectancy is era drift, again.** The best cells earn everything in W1/W3 and give it back in W2/W4. Best cell overall, **ema20_100_vt30_none @1d** (+0.936%/episode, PF 1.237, 273 episodes): W1 +3.56% (PF 1.97), W2 −3.04% (PF 0.45), W3 +3.80% (PF 2.14), W4 −2.74% (PF 0.37), W5 −0.14% — 2/5 folds positive, p = 6.0e-2 against a 2.6e-5 threshold. **tsmom42_vt60_none @1d** (1,708 episodes, PF 1.237) passes the holdout cleanly (breadth 21/30, max symbol share 0.09, untouched subset +0.203% on 583 episodes) and still fails: 3/5 folds, p = 2.6e-2, and 2×-cost PF 1.107. Same disease as RD-008's daily momentum and RD-013's rotation: a real but regime-bound drift that the fold and significance gates exist to reject.

**2. The two statistically significant cells are economically trivial.** ema20_100_vt15_none and vt30_none @4h pass Bonferroni (p = 1.8e-5 and 2.4e-5; break-even N 2,704 and 2,046) — on expectancy of +0.025% and +0.046% per episode with PF 1.025 / 1.024. With 2,086 episodes the standard error shrinks around a near-zero mean; the PF ≥ 1.2 effect-size gate and the 2×-cost gate (PF → ~0.98) kill them. DSR is 0.00 for every row in the family. This is why the bar carries both kinds of gate.

**3. The brake works as a risk cap and fails as a profit mechanism.** Post-hoc portfolio lens (equal-weight per-symbol bar equity, OOS window; `results_rd14/portfolio_lens.json`, not part of the declared bar): **flat_05 cuts the portfolio max drawdown in 24 of 24 groups** — worst case −12.2%, against unbraked drawdowns of −8.9% to −53.4% (e.g. tsmom126 vt30 @4h: −26.6% → −3.3%; tsmom126 vt60 @1d: −53.4% → −3.9%). The mechanism does the one job it was built for. But it pays for it with the return itself: flat_05's compounded portfolio return is positive in **1 of 24** groups (unbraked: 19 of 24), and at the episode level the flat brakes are a massacre — among ≥200-episode rows, brake=none has 21/24 positive expectancy (median PF 1.077), flat_05 has **0/8** (median PF 0.739), flat_10 has 1/13 (median PF 0.715), half_10 has 15/24 (median PF 1.016 — still below its unbraked control in nearly every group). The reason is in the declared release rule: the brake parks the book in cash after the loss, and re-entry waits for the *unbraked shadow* equity to recover halfway — by construction the braked book sits out the sharpest part of the trend resumption, which is where trend expectancy lives. A drawdown brake of this design converts drawdown into opportunity cost at roughly 1:1 or worse.

**4. Vol targeting alone does not rescue the signal.** The unbraked cells are the family's best (median PF 1.077 among big rows; tsmom42 @1d portfolio lens +11.9% / +22.0% / +30.2% compounded for vt15/30/60 — the only group to beat BTC buy-and-hold's +23.3% over the same window, at vt60) — and they still fail folds, holdout or significance everywhere. Sizing cannot manufacture an edge the signal does not have; it can only rescale the one that is there, and what is there is era drift (point 1).

## Consequence

Nothing from this track enters any forward lane; no sleeve, registry or production state changes. The 96 trials join the global counter: **floor after RD-014 = 1,913** on the declared accounting (1,817 + 96); later Wave-4/5 crews' additions only raise it, and no verdict in this family flips at the 1,987 reference (the Bonferroni survivor set is identical).

One mechanism note for any future family (a new pre-declared family, never a retune of this one): if a drawdown brake is revisited, the release rule is the suspect part — release on the *braked* book's own recovery or on fresh signal entry, not on shadow-equity recovery. The DD compression itself (24/24 groups) is real and may be worth having as a pure risk overlay on an already-proven strategy; it is not a source of expectancy.

## Full results — 4h (48 cells)

| variant | episodes | exp %/ep | PF | folds+ | p (1-sided) | verdict |
|---|---|---|---|---|---|---|
| ema10_50_vt15_none | 4248 | +0.019 | 1.028 | 2/5 | 2.3e-04 | FAIL |
| ema10_50_vt15_flat_05 | 786 | -0.167 | 0.768 | 1/5 | 7.4e-01 | FAIL |
| ema10_50_vt15_flat_10 | 1519 | +0.001 | 1.001 | 1/5 | 2.4e-02 | FAIL |
| ema10_50_vt15_half_10 | 4248 | +0.009 | 1.020 | 1/5 | 9.2e-04 | FAIL |
| ema10_50_vt30_none | 4248 | +0.037 | 1.027 | 2/5 | 3.3e-04 | FAIL |
| ema10_50_vt30_flat_05 | 324 | -0.828 | 0.529 | 1/5 | 9.6e-01 | FAIL |
| ema10_50_vt30_flat_10 | 731 | -0.417 | 0.715 | 1/5 | 8.0e-01 | FAIL |
| ema10_50_vt30_half_10 | 4248 | -0.020 | 0.974 | 2/5 | 1.1e-02 | FAIL |
| ema10_50_vt60_none | 4248 | +0.068 | 1.027 | 2/5 | 8.9e-04 | FAIL |
| ema10_50_vt60_flat_05 | 202 | -0.335 | 0.881 | 1/5 | 5.2e-01 | FAIL |
| ema10_50_vt60_flat_10 | 257 | -1.567 | 0.549 | 0/5 | 9.3e-01 | FAIL |
| ema10_50_vt60_half_10 | 4248 | -0.014 | 0.990 | 2/5 | 1.3e-02 | FAIL |
| ema20_100_vt15_none | 2086 | +0.025 | 1.025 | 3/5 | 1.8e-05 | FAIL |
| ema20_100_vt15_flat_05 | 367 | -0.647 | 0.470 | 0/5 | 9.3e-01 | FAIL |
| ema20_100_vt15_flat_10 | 777 | -0.238 | 0.767 | 0/5 | 6.8e-02 | FAIL |
| ema20_100_vt15_half_10 | 2086 | -0.030 | 0.955 | 2/5 | 4.6e-04 | FAIL |
| ema20_100_vt30_none | 2086 | +0.046 | 1.024 | 3/5 | 2.4e-05 | FAIL |
| ema20_100_vt30_flat_05 | 179 | -1.175 | 0.487 | 0/5 | 5.1e-01 | FAIL |
| ema20_100_vt30_flat_10 | 305 | -1.242 | 0.474 | 0/5 | 8.8e-01 | FAIL |
| ema20_100_vt30_half_10 | 2086 | -0.069 | 0.936 | 2/5 | 3.3e-03 | FAIL |
| ema20_100_vt60_none | 2086 | +0.085 | 1.024 | 3/5 | 8.3e-05 | FAIL |
| ema20_100_vt60_flat_05 | 119 | -0.505 | 0.811 | 1/5 | 4.3e-01 | FAIL |
| ema20_100_vt60_flat_10 | 123 | -2.980 | 0.382 | 0/5 | 4.8e-01 | FAIL |
| ema20_100_vt60_half_10 | 2086 | -0.037 | 0.979 | 3/5 | 4.3e-04 | FAIL |
| tsmom126_vt15_none | 5961 | +0.028 | 1.064 | 3/5 | 1.2e-02 | FAIL |
| tsmom126_vt15_flat_05 | 522 | -0.176 | 0.710 | 1/5 | 9.9e-01 | FAIL |
| tsmom126_vt15_flat_10 | 1452 | -0.092 | 0.807 | 1/5 | 9.1e-01 | FAIL |
| tsmom126_vt15_half_10 | 5961 | +0.003 | 1.010 | 3/5 | 1.5e-01 | FAIL |
| tsmom126_vt30_none | 5961 | +0.055 | 1.064 | 3/5 | 1.3e-02 | FAIL |
| tsmom126_vt30_flat_05 | 149 | -0.141 | 0.904 | 2/5 | 8.3e-01 | FAIL |
| tsmom126_vt30_flat_10 | 348 | -0.383 | 0.698 | 1/5 | 9.6e-01 | FAIL |
| tsmom126_vt30_half_10 | 5961 | +0.017 | 1.038 | 3/5 | 9.2e-02 | FAIL |
| tsmom126_vt60_none | 5961 | +0.112 | 1.073 | 3/5 | 9.8e-03 | FAIL |
| tsmom126_vt60_flat_05 | 94 | -0.058 | 0.978 | 2/5 | 9.2e-01 | FAIL |
| tsmom126_vt60_flat_10 | 91 | -1.050 | 0.677 | 1/5 | 9.8e-01 | FAIL |
| tsmom126_vt60_half_10 | 5961 | +0.053 | 1.069 | 3/5 | 4.1e-02 | FAIL |
| tsmom42_vt15_none | 10474 | +0.029 | 1.080 | 3/5 | 7.0e-04 | FAIL |
| tsmom42_vt15_flat_05 | 1423 | -0.085 | 0.790 | 0/5 | 8.3e-01 | FAIL |
| tsmom42_vt15_flat_10 | 3510 | -0.057 | 0.854 | 1/5 | 5.1e-01 | FAIL |
| tsmom42_vt15_half_10 | 10474 | +0.005 | 1.019 | 3/5 | 1.6e-02 | FAIL |
| tsmom42_vt30_none | 10474 | +0.058 | 1.081 | 3/5 | 6.5e-04 | FAIL |
| tsmom42_vt30_flat_05 | 509 | -0.397 | 0.607 | 1/5 | 4.9e-01 | FAIL |
| tsmom42_vt30_flat_10 | 1253 | -0.196 | 0.757 | 0/5 | 8.0e-01 | FAIL |
| tsmom42_vt30_half_10 | 10474 | +0.017 | 1.042 | 3/5 | 1.3e-02 | FAIL |
| tsmom42_vt60_none | 10474 | +0.117 | 1.091 | 4/5 | 4.9e-04 | FAIL |
| tsmom42_vt60_flat_05 | 179 | -0.603 | 0.717 | 1/5 | 8.3e-01 | FAIL |
| tsmom42_vt60_flat_10 | 385 | -0.577 | 0.681 | 1/5 | 4.7e-01 | FAIL |
| tsmom42_vt60_half_10 | 10474 | +0.046 | 1.069 | 4/5 | 2.0e-03 | FAIL |

## Full results — 1d (48 cells)

| variant | episodes | exp %/ep | PF | folds+ | p (1-sided) | verdict |
|---|---|---|---|---|---|---|
| ema10_50_vt15_none | 643 | +0.255 | 1.151 | 4/5 | 4.6e-03 | FAIL |
| ema10_50_vt15_flat_05 | 113 | -1.052 | 0.458 | 0/5 | 9.6e-01 | FAIL |
| ema10_50_vt15_flat_10 | 206 | -0.742 | 0.573 | 1/5 | 7.2e-01 | FAIL |
| ema10_50_vt15_half_10 | 643 | +0.014 | 1.013 | 4/5 | 4.9e-02 | FAIL |
| ema10_50_vt30_none | 643 | +0.475 | 1.140 | 4/5 | 7.5e-03 | FAIL |
| ema10_50_vt30_flat_05 | 121 | -2.537 | 0.241 | 0/5 | 1.0e+00 | FAIL |
| ema10_50_vt30_flat_10 | 90 | -3.091 | 0.238 | 0/5 | 9.9e-01 | FAIL |
| ema10_50_vt30_half_10 | 643 | +0.054 | 1.030 | 3/5 | 8.3e-02 | FAIL |
| ema10_50_vt60_none | 643 | +0.566 | 1.089 | 3/5 | 3.5e-02 | FAIL |
| ema10_50_vt60_flat_05 | 74 | -3.963 | 0.105 | 0/5 | 9.6e-01 | FAIL |
| ema10_50_vt60_flat_10 | 66 | -6.161 | 0.136 | 0/5 | 9.9e-01 | FAIL |
| ema10_50_vt60_half_10 | 643 | +0.127 | 1.039 | 4/5 | 1.3e-01 | FAIL |
| ema20_100_vt15_none | 273 | +0.588 | 1.300 | 2/5 | 3.2e-02 | FAIL |
| ema20_100_vt15_flat_05 | 102 | -1.896 | 0.303 | 0/5 | 9.9e-01 | FAIL |
| ema20_100_vt15_flat_10 | 85 | -2.280 | 0.343 | 0/5 | 9.8e-01 | FAIL |
| ema20_100_vt15_half_10 | 273 | -0.065 | 0.946 | 2/5 | 2.5e-01 | FAIL |
| ema20_100_vt30_none | 273 | +0.936 | 1.237 | 2/5 | 6.0e-02 | FAIL |
| ema20_100_vt30_flat_05 | 97 | -1.735 | 0.499 | 1/5 | 8.3e-01 | FAIL |
| ema20_100_vt30_flat_10 | 85 | -4.597 | 0.254 | 0/5 | 1.0e+00 | FAIL |
| ema20_100_vt30_half_10 | 273 | +0.027 | 1.012 | 2/5 | 2.6e-01 | FAIL |
| ema20_100_vt60_none | 273 | +0.659 | 1.085 | 3/5 | 2.0e-01 | FAIL |
| ema20_100_vt60_flat_05 | 66 | -3.269 | 0.304 | 1/5 | 9.6e-01 | FAIL |
| ema20_100_vt60_flat_10 | 57 | -5.587 | 0.246 | 0/5 | 9.6e-01 | FAIL |
| ema20_100_vt60_half_10 | 273 | +0.545 | 1.142 | 3/5 | 2.1e-01 | FAIL |
| tsmom126_vt15_none | 698 | -0.144 | 0.880 | 3/5 | 3.7e-01 | FAIL |
| tsmom126_vt15_flat_05 | 74 | -1.300 | 0.471 | 0/5 | 4.2e-01 | FAIL |
| tsmom126_vt15_flat_10 | 129 | -1.001 | 0.524 | 1/5 | 8.2e-01 | FAIL |
| tsmom126_vt15_half_10 | 698 | -0.130 | 0.816 | 1/5 | 5.5e-01 | FAIL |
| tsmom126_vt30_none | 698 | -0.403 | 0.835 | 2/5 | 4.7e-01 | FAIL |
| tsmom126_vt30_flat_05 | 62 | -1.015 | 0.663 | 1/5 | 2.5e-01 | FAIL |
| tsmom126_vt30_flat_10 | 59 | -2.170 | 0.515 | 0/5 | 3.3e-01 | FAIL |
| tsmom126_vt30_half_10 | 698 | -0.196 | 0.842 | 1/5 | 3.5e-01 | FAIL |
| tsmom126_vt60_none | 698 | -1.388 | 0.710 | 2/5 | 7.8e-01 | FAIL |
| tsmom126_vt60_flat_05 | 35 | +1.297 | 1.344 | 1/4 | 4.7e-02 | FAIL |
| tsmom126_vt60_flat_10 | 30 | -0.399 | 0.937 | 1/4 | 1.3e-01 | FAIL |
| tsmom126_vt60_half_10 | 698 | -0.453 | 0.803 | 2/5 | 4.4e-01 | FAIL |
| tsmom42_vt15_none | 1708 | +0.208 | 1.247 | 3/5 | 5.6e-03 | FAIL |
| tsmom42_vt15_flat_05 | 306 | -0.216 | 0.794 | 2/5 | 8.7e-01 | FAIL |
| tsmom42_vt15_flat_10 | 649 | -0.051 | 0.946 | 2/5 | 5.6e-01 | FAIL |
| tsmom42_vt15_half_10 | 1708 | +0.094 | 1.165 | 2/5 | 4.7e-02 | FAIL |
| tsmom42_vt30_none | 1708 | +0.421 | 1.250 | 3/5 | 6.8e-03 | FAIL |
| tsmom42_vt30_flat_05 | 180 | -1.049 | 0.598 | 0/5 | 1.0e+00 | FAIL |
| tsmom42_vt30_flat_10 | 279 | -0.748 | 0.664 | 1/5 | 9.7e-01 | FAIL |
| tsmom42_vt30_half_10 | 1708 | +0.147 | 1.154 | 3/5 | 9.7e-02 | FAIL |
| tsmom42_vt60_none | 1708 | +0.741 | 1.237 | 3/5 | 2.6e-02 | FAIL |
| tsmom42_vt60_flat_05 | 139 | -2.693 | 0.328 | 0/5 | 1.0e+00 | FAIL |
| tsmom42_vt60_flat_10 | 115 | -2.601 | 0.499 | 0/5 | 9.9e-01 | FAIL |
| tsmom42_vt60_half_10 | 1708 | +0.281 | 1.176 | 3/5 | 1.1e-01 | FAIL |

Notes on the tables: expectancy is per position episode, net of the declared turnover costs. `max_drawdown_net` in synthesis.json is the harness's sequential episode-compounding field and is not the family's portfolio drawdown — the portfolio-lens drawdowns in `results_rd14/portfolio_lens.json` are the drawdown numbers this family should be read by. Slow signals at 1d (ema20_100: 273 episodes over 30 symbols) leave no symbol with ≥ 20 episodes, so holdout2's breadth leg fails structurally for those cells — recorded on their rows, not hidden.

Files: `rd14/` (family14 engine, run14 runner, synth14 synthesis, anchor14 anchor, verify14 verification, portfolio14 diagnostic), `results_rd14/declaration.json` (frozen, hashed), `results_rd14/synthesis.json` (every row: folds, per-symbol, holdout, p, break-even N, DSR, 2×-cost), `results_rd14/sanity_anchor.json`, `results_rd14/verification.json`, `results_rd14/portfolio_lens.json`.
