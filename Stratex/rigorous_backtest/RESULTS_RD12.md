# RESULTS — TASK-STR-RD-012: order-flow proxy families (OHLCV only)

**Status: COMPLETE — zero passers.** Owner directive 2026-11-15
(Wave 4): strategy finding never stops; any configuration that passes
the full bar is added to demo trading by the coordinator. This round
tested a NEW family class RD-001/002/003 never touched: order-flow
*proxies*. No L2 / trade-level data exists in this programme, so every
flow quantity is an OHLCV-derived proxy, declared as such — nothing
here is true delta, and the document never calls it that.

**Bottom line, plainly: all 28 trials (20 cells + 8 wf-select
procedures) FAIL the bar. Not one cell reaches PF 1.0 — the best is
0.9952 (`vcm_b` @1h, statistically indistinguishable from breakeven,
p = 0.59). OHLCV order-flow proxies are systematically
anti-predictive after costs at 15m/1h on crypto30 in this era. No
configuration from this round goes to forward demo trading.**

**Claim:** issue #35 comment 6890924249. Workspace
`~/workspace/rd-012/` (own clone). Declaration PR #287 (branch
`claude/task-str-rd-012-declaration`, base main `337a1e3f`) was OPEN
before the first cell ran; declaration timestamp
2026-11-15T07:23:51Z. No variant, threshold, cell or exit spec changed
after that PR.

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
in the row files and the synthesis so any verdict can be re-derived
at the final N, and any passer must be re-checked at that N by the
coordinator. (No re-derivation can rescue this round: every p-value
is ≈ 1.0 except `vcm_b` @1h at 0.5897 and `vcl_b` @1h at 0.7191.)

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
20 cells. Plus one wf-select procedure per family × timeframe (the
factory-procedure control, `rd.common.wf_select_judge`) = 8.
**Total 28 trials.** Machine-readable declaration:
`results_rd12/declaration.json`, shipped in declaration PR #287
*before the first cell ran*.

## Data (provenance first)

Binance Vision public archives (futures/um monthly klines) through
the harness `data_feed` contract — per-zip SHA-256, canonical CSV
SHA-256, gap audit; gaps reported, never filled. Full per-series
manifest: `results_rd12/coverage.json`.

**crypto30 @ 1h** (RD-002 verified cache, 2022-01..2026-10): 19
symbols complete at 42,360 rows, 0 missing bars. 11 symbols
(SOL, XRP, LTC, TRX, NEAR, FIL, XLM, HBAR, VET, SAND, MANA) carry
the known shared 120-bar archive hole (42,240 rows) already
manifested by RD-002. Later listings are shorter by listing date:
APT 35,374 · OP 38,722 · INJ 36,886 · SUI 30,656 · ARB 31,641 rows,
0 missing bars within their spans.

**crypto30 @ 15m** (2023-10..2026-10): all 30 series complete at
108,192 rows, **0 missing bars**. 13 series reused hash-verified
from the RD-002 cache, 13 from the RD-012 crew cache fetched under
the identical contract, and 4 (VET, SAND, MANA, AAVE) fetched in
memory — see the environment disclosure below. The two independent
15m evaluation runs loaded the panel separately and produced
**byte-identical CSV SHA-256 for all 30 series** (cross-checked
2026-11-15), so the in-memory series are pinned by two independent
hash observations, recorded in `coverage.json` with their per-zip
SHA-256 manifests.

## Mappability (daemon-identical computability)

The live daemon's feed (`Stratex/autonomy/async_pipeline.py`,
`AsyncMarketDataEngine.get_klines`) parses Binance fapi klines into
exactly open_time/open/high/low/close/volume/close_time — OHLCV base
volume, any interval incl. 15m/1h. Every grid config is a pure
function of OHLCV history with max lookback 260 bars → **mappable**
(wiring note for whoever wires a passer: request `limit ≥ 300`
bars; a call parameter, not a formula change). Mappability is moot
for deployment this round — nothing passed — but the verdicts are
not contaminated by unmappable constructions.

**Unmappable — excluded from the grid by construction, named here:**
true trade-level cumulative delta (no such feed exists); taker-buy
volume / quote-volume CVD (kline fields beyond index 6 are not
parsed by the daemon's `get_klines`); infinite-history CVD (not
reproducible from a finite kline window).

## Sanity anchor (before any RD-012 number is trusted)

RD-001's published `ts_momentum` roc42_4h cell (BTC/ETH/SOL, RD-001
cache) reproduced through the untouched harness chain — **PASSED
bit-identical**: 303 trades, expectancy 0.0024275740638451445,
PF 1.0969220482985518, exact float match on all three figures
(`~/workspace/rd-012/anchor_result.json`, crew workspace).

## Results — all 20 cells EVALUATED, zero passers

Expectancy is net per-trade %; PF is net profit factor; folds = W1–W5
positive count; breadth = share of active symbols with positive OOS
expectancy; untouched = holdout subset expectancy %; every cell was
judged at Bonferroni α ≈ 2.79e-5 (N = 1,792). Full per-fold and
per-symbol detail: `results_rd12/rows/*.json`. Synthesis:
`results_rd12/synthesis.json`.

### crypto30 @ 1h

| cell | trades | exp % | PF | folds | breadth | untouched % | p | verdict |
|---|---|---|---|---|---|---|---|---|
| cvd_momentum/ofm_a | 23,654 | −0.1272 | 0.9250 | 1/5 | 0.200 | −0.1243 | ≈1.0 | FAIL |
| cvd_momentum/ofm_b | 20,688 | −0.1521 | 0.9094 | 0/5 | 0.167 | −0.1534 | ≈1.0 | FAIL |
| cvd_momentum/ofm_c | 23,093 | −0.1369 | 0.9190 | 1/5 | 0.100 | −0.1160 | ≈1.0 | FAIL |
| vol_confirmed_momentum/vcm_a | 18,217 | −0.0966 | 0.9430 | 2/5 | 0.167 | −0.1123 | 0.9998 | FAIL |
| vol_confirmed_momentum/vcm_b | 11,498 | −0.0084 | 0.9952 | 2/5 | 0.467 | −0.0598 | 0.5897 | FAIL |
| vol_confirmed_momentum/vcm_c | 20,964 | −0.0914 | 0.9455 | 1/5 | 0.133 | −0.0931 | 0.9998 | FAIL |
| cvd_divergence/div_a | 49,785 | −0.1818 | 0.8241 | 0/5 | 0.000 | −0.1893 | 1.0 | FAIL |
| cvd_divergence/div_b | 35,578 | −0.1987 | 0.8140 | 0/5 | 0.000 | −0.2091 | 1.0 | FAIL |
| vol_climax_reversal/vcl_a | 5,071 | −0.0572 | 0.9516 | 3/5 | 0.400 | −0.0809 | 0.9247 | FAIL |
| vol_climax_reversal/vcl_b | 3,503 | −0.0319 | 0.9758 | 4/5 | 0.533 | −0.0312 | 0.7191 | FAIL |

`vcl_b` @1h is the only cell passing the folds check (4/5) and the
only one with breadth above 50% — it still fails expectancy, PF and
the untouched holdout. `vcm_b` @1h is the closest to breakeven
(PF 0.9952) and is still negative-expectancy. Neither is a near-bar
passer in any operative sense: the bar requires PF ≥ 1.2, not PF ≈ 1.

### crypto30 @ 15m

| cell | trades | exp % | PF | folds | breadth | untouched % | p | verdict |
|---|---|---|---|---|---|---|---|---|
| cvd_momentum/ofm_a | 92,118 | −0.1581 | 0.8232 | 0/5 | 0.000 | −0.1501 | 1.0 | FAIL |
| cvd_momentum/ofm_b | 81,959 | −0.1532 | 0.8244 | 0/5 | 0.000 | −0.1585 | 1.0 | FAIL |
| cvd_momentum/ofm_c | 90,979 | −0.1473 | 0.8339 | 0/5 | 0.000 | −0.1373 | 1.0 | FAIL |
| vol_confirmed_momentum/vcm_a | 72,940 | −0.1412 | 0.8399 | 0/5 | 0.000 | −0.1204 | 1.0 | FAIL |
| vol_confirmed_momentum/vcm_b | 45,641 | −0.1216 | 0.8680 | 0/5 | 0.000 | −0.0954 | 1.0 | FAIL |
| vol_confirmed_momentum/vcm_c | 82,626 | −0.1436 | 0.8365 | 0/5 | 0.000 | −0.1327 | 1.0 | FAIL |
| cvd_divergence/div_a | 186,295 | −0.1695 | 0.7210 | 0/5 | 0.000 | −0.1733 | 1.0 | FAIL |
| cvd_divergence/div_b | 136,027 | −0.1659 | 0.7316 | 0/5 | 0.000 | −0.1746 | 1.0 | FAIL |
| vol_climax_reversal/vcl_a | 22,693 | −0.1701 | 0.7597 | 0/5 | 0.000 | −0.1741 | 1.0 | FAIL |
| vol_climax_reversal/vcl_b | 14,368 | −0.1855 | 0.7621 | 0/5 | 0.000 | −0.2270 | 1.0 | FAIL |

At 15m the failure is total: in the six momentum cells **not one of
the 30 symbols is positive in any cell** (breadth 0.000 across the
board), and the reversal cells are worse than the momentum cells.

### Walk-forward selection procedures (factory-procedure control)

| procedure | trades | exp % | PF | verdict |
|---|---|---|---|---|
| cvd_momentum @1h (picks ofm_a ×5) | 23,654 | −0.1272 | 0.9250 | FAIL |
| vol_confirmed_momentum @1h (picks vcm_b ×5) | 11,498 | −0.0084 | 0.9952 | FAIL |
| cvd_divergence @1h (picks div_b ×5) | 35,578 | −0.1987 | 0.8140 | FAIL |
| vol_climax_reversal @1h (picks vcl_b ×5) | 3,503 | −0.0319 | 0.9758 | FAIL |
| cvd_momentum @15m (ofm_b ×4, ofm_c ×1) | 82,964 | −0.1521 | 0.8258 | FAIL |
| vol_confirmed_momentum @15m (vcm_c ×2, vcm_b ×3) | 62,089 | −0.1341 | 0.8537 | FAIL |
| cvd_divergence @15m (picks div_b ×5) | 136,027 | −0.1659 | 0.7316 | FAIL |
| vol_climax_reversal @15m (picks vcl_b ×5) | 14,368 | −0.1855 | 0.7621 | FAIL |

In-sample selection manufactures nothing: each procedure reproduces
(approximately) its family's best variant and inherits its failure.
Full pick detail: `results_rd12/wf_select.json`.

### 2×-cost sensitivity — not triggered, by the stated rule

The declaration's near-bar rule re-runs at 2× costs any cell that is
within reach of the bar. The operative near-bar set is empty: **no
cell reaches pooled PF 1.0** (best 0.9952), and doubling a
strictly-adverse cost can only lower expectancy and PF, so no FAIL
verdict in this round can flip at 2× costs — and no PASS exists to
stress. The 2×-cost gate is therefore recorded as NOT TRIGGERED for
all 28 trials rather than silently skipped; if the coordinator
prefers mechanical re-runs regardless, the driver
(`rd12/run_families.py`, `--double-costs`) reproduces them from the
frozen grid and manifested data.

## Reading of the result (texture, not a new claim)

- CVD-proxy momentum loses at both timeframes (PF 0.82–0.93): the
  CLV/sign-weighted volume slope adds no predictive content beyond
  price momentum at 15m/1h, and what little signal exists is smaller
  than the 16 bps round-trip cost.
- Volume-gating Donchian breakouts does not rescue them; the
  strictest gate (`vcm_b`, z ≥ 1.5 on a 96-bar window) merely trades
  less and loses least @1h (PF 0.9952).
- Fading extremes is the worst direction tested (divergence PF
  0.72–0.82, climax reversal 0.76–0.98): in this era intraday crypto
  moves continue more often than OHLCV-flow exhaustion predicts.
- Consistent with RD-002's texture: the programme's verified edge
  concentrates at 4h/1d trend, not intraday flow. This round closes
  the OHLCV order-flow-proxy direction at 15m/1h for the declared
  constructions; it says nothing about true trade-level delta,
  which this programme cannot measure (no such data exists).

## Disclosures

1. **Sandbox file-write fault (environment).** During this round the
   crew sandbox's exec file-creation intermittently failed with
   EPERM (writes silently produced 0-byte files). It destroyed 4 of
   the 17 freshly fetched 15m cache CSVs (AAVE, MANA, SAND = 0-byte;
   VET absent) — `data_feed`'s cache write is best-effort and did
   not surface the loss; the crew caught it on hash verification.
   Those 4 series were therefore loaded via in-memory fetch from the
   same Binance Vision source under the same provenance contract;
   their canonical CSV SHA-256 and full per-zip SHA-256 manifests are
   recorded in `results_rd12/coverage.json`, and both independent
   15m runs observed byte-identical hashes for all 30 series. No
   number in this document rests on unverified data.
2. **Shipped row files are reduced.** `results_rd12/rows/*.json`
   carry the full fold/pooled/holdout/bar/trade-stats payloads with
   `per_symbol_oos` reduced to trades / win_rate / expectancy_net /
   profit_factor_net per symbol (a note inside each file says so).
   Full per-symbol metrics are reproducible from the frozen code
   (`rd12/`) and the manifested data.
3. **Production untouched.** Research only: no daemon, config,
   server or live-demo state was modified by this round.

## Verdict

**Zero passers out of 28 trials.** Nothing from TASK-STR-RD-012 is
forwarded to forward demo trading. The global trial counter stands
at **1,792** after this round (before parallel Wave-4 rounds'
additions). The order-flow-proxy track is closed at 15m/1h for the
declared constructions.
