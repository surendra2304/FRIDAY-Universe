# RESULTS — TASK-STR-RD-003: strategy discovery, round 3

**Status: IN PROGRESS.** Owner directive 2026-11-15: strategy finding
never stops; any configuration that passes the full bar is wired into
demo trading by the coordinator (TASK-STR-FWD-002 line). This document
is the round-3 record: Stage 1 finishes RD-002's disclosed deferrals,
Stage 2 judges new pre-declared families, Stage 3 synthesises.

**The bar (unchanged from RD-001/RD-002):** expectancy > 0 AND
PF ≥ 1.2 AND ≥ 200 OOS trades AND ≥ 80% of folds positive AND
untouched-holdout pass AND Bonferroni significance at the RUNNING
global trial count AND 2×-cost sensitivity pass AND breadth (no
single-symbol-carried candidates; per-symbol profit shares reported).
In-sample selection only; OOS judgement; costs per `rd2/costs2.py`;
unobtainable data = UNCOVERED, never synthetic. The global trial
counter continues from RD-002's final **1,557**.

**Sanity anchor (harness fidelity):** RD-001's `ts_momentum/roc42_4h`
cell (BTC/ETH/SOL, RD-001 cache) re-run through the untouched RD-002
chain before any RD-003 number was produced: **303 trades, expectancy
0.0024275740638451445, PF 1.0969220482985518 — bit-identical** to
RD-001's archived row.

---

## Stage 1 — RD-002's deferrals, completed or closed with cause

RD-002 disclosed three deferral classes. Their true state on current
main (after TASK-STR-CLEANUP-001/002 executed the owner's rule):

* **Runnable and RUN here (152 trials):** the 25 discovery modules
  that survive on main × RD-002's 6 discovery cells (crypto30 1d,
  forex28 1d, comm7 1d, idx7 1d, crypto12 4h, forex12 4h) = 150 cells,
  plus governed `adx_ema` (the only surviving governed module) at
  crypto30 1h in its bare and production configurations = 2 cells.
  Survivors: arb_scanner, bollinger_rsi_reversion, breakout_momentum,
  ensemble_strategy, grid_trading, ml_ensemble, options_pricing,
  pair_trading, prediction_enhanced, quantitative_engine,
  regime_detector, scalping_microstructure, sentiment_strategy,
  statistical_arbitrage, strategy_donchian_observe_only,
  strategy_ehlers_hma, strategy_hybrid, strategy_mean_reversion_scalper,
  strategy_ml, strategy_rsi_divergence_scalper,
  strategy_scalping_breakout, strategy_supertrend_atr,
  strategy_volume_breakout, strategy_vwap_scalper,
  vwap_volume_profile.
* **Closed by deletion — never run, never resurrected (168 cells):**
  the other 33 discovery modules were deleted by CLEANUP-001 (their
  code no longer exists; RD-002's assignment predates the cleanup):
  27 with zero RD-002 cells, plus 6 whose daily cells RD-002 did run
  (bollinger_bands_strategy, crypto_trading_strategy,
  dynamic_position_sizing, forex_scalping_strategy,
  strategy_mean_reversion, trend_following) whose 4h cells are closed
  with them — 162 discovery cells in total. Governed 1h cells for
  supertrend, factory_winner_1..5 (6 configs) are likewise closed:
  the modules are deleted under the owner's PF < 1.2 rule. (The
  superlinear-1h question that deferred supertrend's cell is moot —
  the code is gone by owner order, which supersedes the deferral.)
* **adx_ema's other governed cells** (forex12 1d/4h, comm7 1d/4h,
  idx7 1d) were already completed by RD-002; only its crypto30 1h
  cells were deferred, and they run here.

_Stage-1 results table: filled in at synthesis (Stage 3)._

---

## Stage 2 — new families, PRE-DECLARED before execution

Declared 2026-11-15 in `results_rd3/stage2_declaration.json` (machine-
readable), in `rd3/families_rd3.py` (code) and here, all shipped in a
dedicated PR merged **before the first Stage-2 cell ran**. No variant,
threshold, cell or exit spec may change after that merge. Four
families, none a re-skin of the judged crypto daily-trend cluster:

1. **funding_extremes** (crypto30 @ 4h, 1d; 8 cells) — perpetual
   funding prints as a positioning gauge (new data source for the
   programme: Binance Vision fundingRate archives, every zip SHA-256
   verified against its published checksum). FADE variants fade
   extreme prints (≥ 90th / ≥ 95th trailing-540-print percentile)
   when price is extended the same way vs EMA50; CARRY variants take
   the funding-receiving side above ±1bp / ±3bp prints. Judgement is
   price-only — funding cashflows are NOT added to returns (declared;
   conservative for the carry claim). Gates: ≥ 160 days of print
   history, print age ≤ 24h.
2. **overnight_drift** (forex12, comm7 @ 1h; 4 cells) — hold the
   21:00→07:00 UTC window outright (drift_long) or fade its previous
   completed window (drift_fade); exit is time at the 07:00 close
   (bracket_time 3.0/6.0 ATR, 11 bars). Indices are **UNCOVERED** for
   this mechanism: Yahoo cash-index 1h bars exist only 13:00–21:00
   UTC, so the window does not exist in the data.
3. **btc_leadlag** (crypto12, crypto30 @ 1h; 4 cells) — BTC's
   trailing 4-bar / 12-bar move, scaled by BTC ATR%(14) (θ 1.0 /
   1.5), predicts alt entries over the next k bars. BTC itself is
   never traded (that would be ts_momentum, already judged).
4. **vol_regime_switch** (crypto30 4h/1d, comm7 1d, forex28 1d;
   8 cells) — the claim is the switch: donchian-20 breakouts only
   when ATR% trailing-200 percentile rank ≤ 0.35 (switch_b: 0.25),
   z-score(20, 2.0) reversion only when rank ≥ 0.65 (switch_b:
   0.75), flat between. Two sleeves simulated independently and
   pooled (declared simplification, as in RD-002 Stage C).

Counting: 24 cells + 10 wf-select procedures (one per family × panel
× timeframe with ≥ 2 variants) = **34 Stage-2 trials**.

_Stage-2 results: filled in at synthesis (Stage 3)._

---

## Stage 2B — forex-native families (owner scope extension, 2026-11-15)

Added by owner directive ~12:19 IST: *"Stratex should also take
trades in OANDA and it should create strategies using that also."*
Declared in `results_rd3/stage2b_declaration.json`, in
`rd3/families_fx.py` and here, shipped in a dedicated PR merged
**before the first Stage-2B cell ran**. Venue design is OANDA
(instruments, session structure, RD-002's OANDA-modelled costs:
majors 6 bps RT, minors 10, GOLD 10). Data is RD-002's provenanced
Yahoo FX/commodity series — the OANDA practice price API is not
reachable from the research sandbox (no venue credentials in this
environment), stated plainly; TASK-STR-FWD-004's forward lane
supplies live OANDA evidence for any survivor. SMT-v2 (deleted) and
FX-MR-v4 (incumbent, under FWD-004 measurement) are NOT re-tested.

1. **london_drive** (forex12, comm7 @ 1h; 4 cells) — Asia-range →
   London expansion: a 07:00 UTC close outside the 00:00–07:00 Asia
   range, held to 17:00 (bracket_time 2.0/4.0, 9 bars). `drive_narrow`
   additionally requires Asia width < 1.0×ATR(14).
2. **monday_gap_fade** (forex28, comm7 @ 1d; 4 cells) — fade
   Friday→Monday gaps beyond 0.5× / 1.0× ATR% over ≤ 3 days
   (bracket_time 2.0/3.0). **Declared deviation:** entries are
   decided at Monday's open from the gap itself and filled at that
   open (open-auction semantics) — the only family in the programme
   using open-known information.
3. **trend_pullback** (forex28 1d, forex12 4h, comm7 1d; 6 cells) —
   retracement entries no judged family uses: inside an EMA100/200
   trend (10-bar slope), buy the first EMA20 touch-and-reclaim bar;
   exit trail 2.0/3.0 ATR.

Counting: 14 cells + 7 wf-select procedures = **21 Stage-2B trials**,
joining the same global counter and final-N Bonferroni gate.

_Stage-2B results: filled in at synthesis (Stage 3)._

---

## Stage 3 — synthesis

_Filled in when all stages complete: one ranked table at the final
running N, explicit PASS/FAIL per configuration, passer evidence
packs, and the RD-002 candidates re-checked at the new N._
