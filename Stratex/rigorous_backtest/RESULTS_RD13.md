# TASK-STR-RD-013 — Cross-Asset Rotation: Results

**Mandate:** a NEW family, distinct from the RD-002 Stage-C sleeve (a
fixed basket of RD-002 members). This task tests a *rules-based
rotation*: a fixed cross-asset universe, momentum-ranked, rebalanced
on a schedule. Research only — no production, governance, registry or
engine changes; no live trading; nothing here is wired anywhere.

**Pre-declaration:** the full grid, universe, costs and bar below were
posted BEFORE the first RD-013 backtest ran — issue #35, comment
6890930042 (2026-11-15). The machine-readable copy is
`results_rd13/declaration.json`. Nothing was retuned after seeing
results; there is no second grid.

## Verdict (stated first, plainly)

**ZERO of the 48 configurations pass the pre-declared bar. Cross-asset
momentum rotation, as specified, is NOT a candidate and NOT a forward
entrant.** Two gates fail universally:

- **Drawdown: 0 of 48 configurations keep OOS max drawdown within the
  20% limit** (best is −21.0%; the median is ≈ −35%; the worst −60.3%).
- **Significance: the best one-sided p-value in the grid is 5.9e-2**
  against a Bonferroni threshold of 2.5e-5 (0.05 / 2,000) — three
  orders of magnitude short. Under the declared fail-closed rule this
  is not close.

The grid's positive tilt (40 of 48 configurations compound positively
OOS) is real arithmetic and changes nothing: it is one correlated
crypto-trend observation wearing 48 sets of clothes, concentrated in
one fold and one asset (dissected below), bought with drawdowns no
portfolio mandate in this programme accepts.

## Universe and provenance

Seven assets, every series SHA-256-verified against the RD-002 cache
sidecars before use (the loader refuses a hash mismatch):

| asset | source | base rows | daily bars used | csv_sha256 (first 12) |
|---|---|---|---|---|
| BTCUSDT | Binance Vision USDT-M monthly klines 1h → daily (complete 24-bar buckets only) | 42,360 | 1,765 | cbd726f60c71 |
| ETHUSDT | same | 42,360 | 1,765 | 5d861191ad4d |
| SOLUSDT | same (5 incomplete days dropped — the known archive gap block) | 42,240 | 1,760 | 281fbff59b20 |
| BNBUSDT | same | 42,360 | 1,765 | 5461c517e9a1 |
| GOLD | COMEX GC=F via Yahoo Finance chart API, daily | 2,232 | 2,232 | 4933b83b0672 |
| SPX | ^GSPC via Yahoo, daily | 2,230 | 2,230 | ab1482ee3b03 |
| NDX | ^NDX via Yahoo, daily | 2,230 | 2,230 | 4dd289321715 |

Full hashes, per-fold numbers, per-asset contributions and every
row's complete metrics: `results_rd13/synthesis.json`. Code:
`rd13/rotation.py` (self-contained; loads only hash-verified series).

## Method (exactly as pre-declared)

- **Score** at rebalance date t: trailing L-calendar-day return —
  last close ≤ t vs last close ≤ t−L; each endpoint's bar must lie
  within 3 calendar days of its target date, and the asset needs
  ≥ L+30 days of history, else it is ineligible at t. **Hold the
  top-K at equal weight 1/K.** `long_only` is always invested;
  `long_flat` holds a selected asset as cash when its score ≤ 0
  (weight NOT redistributed). Unfilled weight (fewer than K eligible)
  stays cash in both modes.
- **Grid:** L ∈ {21, 63, 126, 252} × K ∈ {1, 2, 3} × cadence ∈
  {weekly Mondays, daily} × mode ∈ {long_only, long_flat}
  = **48 configurations = 48 trials**.
- **Window:** rebalancing starts 2023-01-02 for every configuration
  (shared window). Periods are attributed to walk-forward folds by
  period START date; folds W1–W5 exactly as RD-002, OOS era
  2024-07-01 → 2026-11-01 (122 weekly / 853 daily OOS periods).
  2023-01-02 → 2024-07-01 is in-sample context, reported, never judged.
- **Costs:** round-trip bps (crypto 16, GOLD 10, SPX/NDX 8 — the
  RD-002 table). At each rebalance the traded notional
  Σ|w_new − w_drifted| is charged RT/2 per asset leg and deducted
  from the new period's return; the initial build from cash is
  charged; cash earns 0. Turnover is therefore inside every number
  below, including the drawdowns.
- **Judgement (the bar, all seven gates required):** (1) OOS
  compounded > 0 net of costs; (2) per-period profit factor ≥ 1.2;
  (3) ≥ 4/5 folds positive; (4) max drawdown ≤ 20%; (5) largest
  single-asset share of total positive P&L contribution ≤ 50%;
  (6) one-sided t-test on OOS period returns, Bonferroni
  p < 0.05 / N_global at **N_global = 2,000** (floor: 1,557 through
  RD-002 + ≥207 RD-003 trials counted at declaration + 48 RD-013 +
  Wave-4 siblings in flight; a p within 2× of the threshold either
  way counts as FAILED); (7) at 2× costs, compounded > 0 AND
  PF ≥ 1.2. No configuration reached gate 7 — none passed the
  mechanical subset (1)–(5), so no 2×-cost rerun was owed.

**Harness verification:** before any number was trusted, the first
six OOS weekly periods of the L=63/K=1/weekly/long_only configuration
were recomputed through an independent code path (separate selection
and return arithmetic): picks (NDX, NDX, ETHUSDT, NDX, SOLUSDT,
GOLD), gross period returns and the turnover charges (0 when the
holding is unchanged; 0.12% on a full NDX→ETHUSDT switch = 4 bps
index leg + 8 bps crypto leg) reproduce exactly.

## The full grid (OOS, net of costs)

| L | K | cadence | mode | compounded | max DD | period PF | folds+ | p (1-sided) | max asset share |
|---|---|---|---|---|---|---|---|---|---|
| 21 | 1 | daily | long\_flat | -9.8% | -59.5% | 1.03 | 2/5 | 3.9e-01 | 0.51 |
| 21 | 1 | daily | long\_only | +2.1% | -56.5% | 1.05 | 2/5 | 3.3e-01 | 0.43 |
| 21 | 1 | weekly | long\_flat | -20.7% | -60.3% | 1.02 | 1/5 | 4.7e-01 | 0.44 |
| 21 | 1 | weekly | long\_only | -4.0% | -57.6% | 1.09 | 1/5 | 3.7e-01 | 0.66 |
| 21 | 2 | daily | long\_flat | +34.6% | -38.6% | 1.09 | 2/5 | 2.2e-01 | 0.60 |
| 21 | 2 | daily | long\_only | +49.9% | -40.1% | 1.10 | 4/5 | 1.7e-01 | 0.51 |
| 21 | 2 | weekly | long\_flat | +8.9% | -39.2% | 1.14 | 2/5 | 3.3e-01 | 0.51 |
| 21 | 2 | weekly | long\_only | +39.8% | -31.4% | 1.26 | 3/5 | 2.0e-01 | 0.36 |
| 21 | 3 | daily | long\_flat | +22.4% | -31.8% | 1.07 | 3/5 | 2.6e-01 | 0.53 |
| 21 | 3 | daily | long\_only | +30.7% | -31.0% | 1.08 | 4/5 | 2.2e-01 | 0.47 |
| 21 | 3 | weekly | long\_flat | +20.5% | -33.2% | 1.20 | 2/5 | 2.7e-01 | 0.43 |
| 21 | 3 | weekly | long\_only | +34.0% | -28.9% | 1.25 | 4/5 | 2.2e-01 | 0.34 |
| 63 | 1 | daily | long\_flat | +148.0% | -34.8% | 1.20 | 4/5 | 5.9e-02 | 0.57 |
| 63 | 1 | daily | long\_only | +139.7% | -34.8% | 1.19 | 4/5 | 6.4e-02 | 0.59 |
| 63 | 1 | weekly | long\_flat | +72.5% | -40.0% | 1.37 | 2/5 | 1.5e-01 | 0.64 |
| 63 | 1 | weekly | long\_only | +89.3% | -40.0% | 1.41 | 3/5 | 1.3e-01 | 0.60 |
| 63 | 2 | daily | long\_flat | +63.7% | -29.1% | 1.13 | 3/5 | 1.3e-01 | 0.32 |
| 63 | 2 | daily | long\_only | +58.4% | -32.4% | 1.12 | 3/5 | 1.5e-01 | 0.29 |
| 63 | 2 | weekly | long\_flat | +50.5% | -26.7% | 1.33 | 3/5 | 1.7e-01 | 0.40 |
| 63 | 2 | weekly | long\_only | +67.3% | -24.5% | 1.37 | 4/5 | 1.4e-01 | 0.40 |
| 63 | 3 | daily | long\_flat | +54.0% | -27.8% | 1.13 | 3/5 | 1.4e-01 | 0.34 |
| 63 | 3 | daily | long\_only | +53.6% | -33.9% | 1.12 | 3/5 | 1.5e-01 | 0.35 |
| 63 | 3 | weekly | long\_flat | +54.7% | -21.0% | 1.38 | 3/5 | 1.4e-01 | 0.33 |
| 63 | 3 | weekly | long\_only | +53.6% | -27.3% | 1.32 | 3/5 | 1.5e-01 | 0.37 |
| 126 | 1 | daily | long\_flat | +16.8% | -34.5% | 1.07 | 3/5 | 2.8e-01 | 0.50 |
| 126 | 1 | daily | long\_only | +16.8% | -34.5% | 1.07 | 3/5 | 2.8e-01 | 0.50 |
| 126 | 1 | weekly | long\_flat | +16.7% | -33.4% | 1.15 | 3/5 | 2.9e-01 | 0.57 |
| 126 | 1 | weekly | long\_only | +16.7% | -33.4% | 1.15 | 3/5 | 2.9e-01 | 0.57 |
| 126 | 2 | daily | long\_flat | +26.0% | -36.7% | 1.08 | 3/5 | 2.5e-01 | 0.38 |
| 126 | 2 | daily | long\_only | +27.9% | -39.5% | 1.08 | 3/5 | 2.4e-01 | 0.38 |
| 126 | 2 | weekly | long\_flat | +17.9% | -32.6% | 1.17 | 3/5 | 2.9e-01 | 0.42 |
| 126 | 2 | weekly | long\_only | +20.4% | -33.4% | 1.18 | 3/5 | 2.7e-01 | 0.40 |
| 126 | 3 | daily | long\_flat | +4.8% | -39.4% | 1.04 | 3/5 | 3.6e-01 | 0.37 |
| 126 | 3 | daily | long\_only | +10.0% | -42.4% | 1.05 | 4/5 | 3.3e-01 | 0.36 |
| 126 | 3 | weekly | long\_flat | -4.4% | -37.2% | 1.06 | 3/5 | 4.3e-01 | 0.46 |
| 126 | 3 | weekly | long\_only | +3.6% | -39.9% | 1.10 | 3/5 | 3.7e-01 | 0.40 |
| 252 | 1 | daily | long\_flat | +27.2% | -43.5% | 1.08 | 3/5 | 2.4e-01 | 0.53 |
| 252 | 1 | daily | long\_only | +27.2% | -43.5% | 1.08 | 3/5 | 2.4e-01 | 0.53 |
| 252 | 1 | weekly | long\_flat | +29.3% | -45.4% | 1.21 | 2/5 | 2.4e-01 | 0.54 |
| 252 | 1 | weekly | long\_only | +29.3% | -45.4% | 1.21 | 2/5 | 2.4e-01 | 0.54 |
| 252 | 2 | daily | long\_flat | -3.6% | -38.5% | 1.03 | 2/5 | 4.0e-01 | 0.42 |
| 252 | 2 | daily | long\_only | -3.6% | -38.5% | 1.03 | 2/5 | 4.0e-01 | 0.42 |
| 252 | 2 | weekly | long\_flat | +22.9% | -43.0% | 1.19 | 1/5 | 2.6e-01 | 0.34 |
| 252 | 2 | weekly | long\_only | +22.9% | -43.0% | 1.19 | 1/5 | 2.6e-01 | 0.34 |
| 252 | 3 | daily | long\_flat | -9.6% | -37.7% | 1.01 | 3/5 | 4.7e-01 | 0.43 |
| 252 | 3 | daily | long\_only | -5.6% | -37.8% | 1.02 | 3/5 | 4.3e-01 | 0.42 |
| 252 | 3 | weekly | long\_flat | +15.6% | -28.0% | 1.16 | 2/5 | 3.0e-01 | 0.29 |
| 252 | 3 | weekly | long\_only | +18.0% | -28.0% | 1.16 | 2/5 | 2.8e-01 | 0.35 |

Identical long_only/long_flat rows (e.g. L=126/252 at K=1) are not a
copy error: in those configurations the top-ranked asset's score was
positive at (nearly) every OOS rebalance, so the flat filter never
bound. Where trends were choppier (L=21, L=63) the modes separate
clearly.

## Dissection of the best row (why it still fails)

**L=63, K=1, daily, long_flat — +148.0% OOS compounded, PF 1.20,
4/5 folds positive** is the grid's champion, and it fails four gates:

- Max drawdown **−34.8%** (limit 20%).
- Profit concentration: **ETHUSDT alone contributes 57%** of the
  total positive P&L (limit 50%); GOLD adds 27%. The "cross-asset
  rotation" is, in profit terms, mostly an ETH-timing device.
- Fold concentration: W3 (2025-07 → 2026-01) contributes +89.5%
  compounded; W2 is **−10.8%**. One era does the work.
- Significance p = 5.9e-2 vs 2.5e-5 required.
- It also paid **10.3% of equity in turnover costs** across the OOS
  window (853 daily rebalances) to achieve this — the daily cadence's
  cost drag is structural, and it still did not buy drawdown control.

The mechanism behind the drawdowns is visible in the verified spot
check: on 2024-07-29 the rule rotated fully into SOLUSDT on a +7.2%
63-day score — immediately before a **−28.9% week**. Momentum ranking
concentrates into the trailing winner precisely at local tops; with
four of seven assets being correlated crypto majors, the "cross-asset"
basket's variance is crypto variance, and GOLD/SPX/NDX top-rank too
rarely and too briefly to cushion the reversals. `long_flat` barely
helps: the winner's score is usually still positive on the way into
the drop, so the cash gate stays open.

## Benchmarks (context, NOT trials, NOT judged)

OOS window 2024-07-01 → 2026-11-01, net of one round-trip charge,
drawdown on daily closes:

| benchmark | compounded | max DD |
|---|---|---|
| GOLD buy-and-hold | **+66.5%** | −26.7% |
| SPX buy-and-hold | +38.3% | −18.9% |
| BTCUSDT buy-and-hold | +23.1% | −53.0% |
| Equal-weight all-7 (mean of legs) | +17.6% | — |

Plain gold buy-and-hold — zero rotation, zero turnover after entry —
beat 46 of the 48 rotation configurations on compounded return over
the same window. That is the honest context for the grid's positive
tilt: in a window where gold rose two-thirds and crypto trended, most
long-biased rules look clever. The bar exists to separate that from
edge, and nothing here separates.

**In-sample warning, for the record:** the same configurations
compound **+90% to +624%** over the 2023-01 → 2024-07 in-sample
segment. Anyone quoting those numbers as evidence for rotation is
quoting the regime artefact this programme's Anti-Overfit Law exists
to reject.

## Trial accounting and follow-up

- RD-013 adds exactly **48 trials**. Running global count:
  1,557 (through RD-002) + ≥207 (RD-003, counted at declaration)
  + 48 = **≥1,812**, before Wave-4 siblings' additions; significance
  was judged at the conservative N = 2,000.
- **No forward entrant, no sleeve change, no production change.**
  The owner's removal rule does not apply (nothing governed was
  tested; the family was never in production).
- One texture note, explicitly NOT a candidate and NOT a retune
  invitation: L=63 is the least-bad lookback at every K, cadence and
  mode (all twelve L=63 rows compound positively; the grid's best
  drawdown, −21.0%, is L=63/K=3/weekly/long_flat at +54.7%, PF 1.38 —
  still failing drawdown and significance). If rotation is ever
  revisited, the missing ingredient is a risk mechanism (volatility
  targeting or a drawdown brake), which would be a NEW pre-declared
  family judged from scratch — not a continuation of this grid.

## Bottom line

Across 48 pre-declared configurations on hash-verified data in three
asset classes, cross-asset momentum rotation compounds positively in
a friendly window but cannot control drawdown (0/48 within limits),
cannot attribute its profit broadly (champion: 57% from one asset),
and comes nowhere near statistical significance at the programme's
trial count (best p = 5.9e-2 vs 2.5e-5). **The family fails the bar.
Stratex's forward evidence remains where RD-002 put it: the two
promoted candidates and the Stage-C sleeve, now in forward test.**
