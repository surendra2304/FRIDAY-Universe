# RESULTS — TASK-STR-RD-012: order-flow proxy families (OHLCV only)

**Status: IN PROGRESS — declaration revision.** Owner directive
2026-11-15 (Wave 4): strategy finding never stops; any configuration
that passes the full bar is added to demo trading by the coordinator.
This round tests a NEW family class RD-001/002/003 never touched:
order-flow *proxies*. No L2 / trade-level data exists in this
programme, so every flow quantity is an OHLCV-derived proxy, declared
as such — nothing here is true delta, and the document never calls
it that.

**Claim:** issue #35 comment 6890924249. Workspace
`~/workspace/rd-012/` (own clone). Declaration base commit
`337a1e3f` (main at declaration time).

## The bar (unchanged from RD-001/RD-002/RD-003)

Expectancy > 0 AND PF ≥ 1.2 AND ≥ 200 OOS trades AND ≥ 80% of folds
positive AND untouched-holdout pass (`rd2.stats2.holdout2`: breadth
≥ 50% of active symbols, no symbol > 50% of profit, untouched
every-3rd-symbol subset positive on ≥ 30 trades) AND Bonferroni
one-sided p < 0.05 / N_global AND 2×-cost sensitivity pass.
In-sample selection only; OOS judgement (harness folds W1–W5,
STANDARD profile, OOS era 2024-07-01 → 2026-11-01, trades attributed
by entry time); costs per `rd2/costs2.py` (crypto 16 bps round trip);
unobtainable data = UNCOVERED, never synthetic.

**Trial counting.** The global counter continues from RD-002's final
**1,557** + RD-003's declared **207** (152 Stage-1 + 34 Stage-2 +
21 Stage-2B) = **1,764** before this round. RD-012 adds **28 trials**
(20 cells + 8 wf-select procedures) → judgement at **N = 1,792**,
Bonferroni α ≈ 2.79e-5. Parallel Wave-4 rounds (RD-004..RD-011,
RD-013) add trials as they land; raw per-row p-values are published
in the synthesis so any verdict can be re-derived at the final N,
and any passer must be re-checked at that N by the coordinator.
Deflated Sharpe ratios are computed and reported for near-bar rows
for the record (RD-002's stated practice: DSR reported, Bonferroni
is the operative significance gate).

## Pre-declared features (frozen)

Bar t; O/H/L/C/V = open/high/low/close/base-volume; all causal.

- **CLV(t)** = (2C − H − L)/(H − L) if H > L else 0 — close location.
- **SV1(t)** = sign(C − O)·V, sign(0) = 0 — directional volume.
- **SV2(t)** = V·CLV(t) — CLV-weighted volume.
- **CVD_L(t)** = rolling sum of SV over the L bars ending at t (full
  window required). Windowed by construction: an infinite-history
  CVD cannot be reproduced by the live daemon and is never used.
- **zV_m(t)** = (V(t) − mean_m(V))/std_m(V), ddof=1, full window;
  0 when the window std is 0.
- **ROC_n(t)** = C(t)/C(t−n) − 1. **ATR** = harness `rd.common.atr` (14).

Entries are (signal bar, side) for `rd.fastsim.simulate_entries`
(harness MODULE convention: signal on close of bar t → enter at open
of t+1, entry-bar exit-checked, stop-before-target, gaps at the
open, one position at a time). Warmup 260 bars everywhere.

## Pre-declared families (frozen — `rd12/families_rd12.py`)

1. **cvd_momentum** — windowed-CVD slope agrees with price momentum;
   CROSS form (joint condition turning true fires): LONG iff
   CVD_L(t) − CVD_L(t−s) > 0 and ROC_s(t) > 0; SHORT mirrored.
   Variants: `ofm_a` SV2 L48 s12 · `ofm_b` SV2 L96 s24 ·
   `ofm_c` SV1 L48 s12. Exit: bracket SL 2.0 / TP 3.0 ATR.
2. **vol_confirmed_momentum** — Donchian breakout gated by volume
   surge (state form, the families2 donchian convention): LONG iff
   C(t) > max(H, prior n) and zV_m(t) ≥ z*; SHORT mirrored.
   Variants: `vcm_a` n20 m48 z1.0 · `vcm_b` n40 m96 z1.5 ·
   `vcm_c` n20 m48 z0.5. Exit: bracket 2.0 / 3.0 ATR.
3. **cvd_divergence** — exhaustion reversal on flow non-confirmation
   (proxy fixed to SV2; state form): SHORT iff H(t) exceeds the
   prior-n high while CVD_L(t) is below the prior-n CVD peak; LONG
   mirrored at lows. Variants: `div_a` n20 L48 · `div_b` n40 L96.
   Exit: bracket_time SL 1.5 / TP 2.0 ATR, max 24 bars @15m, 12 @1h.
4. **vol_climax_reversal** — volume-climax rejection (state form):
   LONG iff ROC_s(t) < 0, zV_m(t) ≥ z*, CLV(t) ≥ +0.5; SHORT iff
   ROC_s(t) > 0, zV_m(t) ≥ z*, CLV(t) ≤ −0.5. Variants:
   `vcl_a` m48 z2.0 s12 · `vcl_b` m96 z2.5 s24. Exit: bracket_time
   SL 1.5 / TP 2.5 ATR, max 24 bars @15m, 12 @1h.

**Cells:** every variant × {crypto30 @ 15m, crypto30 @ 1h} =
20 cells. Plus one wf-select procedure per family × cell (the
factory-procedure control, `rd.common.wf_select_judge`) = 8.
**Total 28 trials.** Machine-readable declaration:
`results_rd12/declaration.json`, shipped in the declaration PR
*before the first cell runs*. No variant, threshold, cell or exit
spec may change after that PR; any change needs a new declaration
and a new count.

## Data (provenance first)

Binance Vision public archives (futures/um monthly klines) through
the harness `data_feed` contract — per-zip SHA-256, canonical CSV
SHA-256, gap audit; gaps reported, never filled. crypto30 @ 1h from
the RD-002 verified cache (2022-01..2026-10). crypto30 @ 15m
(2023-10..2026-10, the programme's 15m range): the 13 symbols RD-002
cached are reused hash-verified; the other 17 are fetched fresh
into the RD-012 crew cache under the identical contract.
_Per-series coverage table: filled in at synthesis._

## Mappability (daemon-identical computability)

The live daemon's feed (`Stratex/autonomy/async_pipeline.py`,
`AsyncMarketDataEngine.get_klines`) parses Binance fapi klines into
exactly open_time/open/high/low/close/volume/close_time — OHLCV base
volume, any interval incl. 15m/1h. Every grid config is a pure
function of OHLCV history with max lookback 260 bars → **mappable**
(wiring note for whoever wires a passer: request `limit ≥ 300`
bars; a call parameter, not a formula change).

**Unmappable — excluded from the grid by construction, named here:**
true trade-level cumulative delta (no such feed exists); taker-buy
volume / quote-volume CVD (kline fields beyond index 6 are not
parsed by the daemon's `get_klines`); infinite-history CVD (not
reproducible from a finite kline window).

## Sanity anchor (before any RD-012 number is trusted)

RD-001's published `ts_momentum` roc42_4h cell (BTC/ETH/SOL, RD-001
cache) reproduced through the untouched harness chain — required
bit-identical: 303 trades, expectancy 0.0024275740638451445,
PF 1.0969220482985518. _Result: filled in at synthesis._

## Results

_Filled in at synthesis: one row per cell with per-config PASS/FAIL
against the full bar, wf-select procedure rows, 2×-cost rows for
near-bar cells, and the passer list (or "zero passers" stated
plainly). Machine-readable: `results_rd12/synthesis.json`._
