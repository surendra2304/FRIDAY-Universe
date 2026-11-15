# RESULTS — TASK-STR-RD-003: strategy discovery, round 3

**Status: COMPLETE with disclosed compute deferrals (Stage 1).**
Owner directive 2026-11-15: strategy finding never stops; any
configuration that passes the full bar is wired into demo trading by
the coordinator (TASK-STR-FWD-002 line). Scope extension ~12:19 IST
added the forex-native Stage 2B and the OANDA forward-test lane.

## Verdict — ZERO new passers

**No configuration in RD-003 passes the full bar.** Across
76 judged rows and 18
wf-select procedures (94 RD-003 trials), zero
rows pass the mechanical bar, so the Bonferroni and 2×-cost gates
were never reached by an RD-003 row. The global trial counter moves
**1,557 → 1,651** (Bonferroni threshold at the final N: 3.028e-05).
RD-002's two passers are re-checked at the new N in §5 — both stand.
The one OANDA-lane forward-test candidate (from RD-002's record,
mechanical bar passed, significance pending) is named with its full
evidence pack in §4.

**The bar (unchanged):** expectancy > 0 AND PF ≥ 1.2 AND ≥ 200 OOS
trades AND ≥ 80% of folds positive AND untouched-holdout pass AND
Bonferroni significance at the RUNNING global N AND 2×-cost
sensitivity pass AND breadth (per-symbol profit shares reported).
In-sample selection only; OOS judgement; costs per `rd2/costs2.py`;
unobtainable data = UNCOVERED, never synthetic.

**Sanity anchor (harness fidelity):** RD-001's `ts_momentum/roc42_4h`
cell re-run through the untouched RD-002 chain before any RD-003
number was produced: **303 trades, expectancy 0.0024275740638451445,
PF 1.0969220482985518 — bit-identical** to RD-001's archived row.
A second bit-identical reproduction (the §4 candidate's RD-002 cell)
is recorded in §4.

---

## 1. Stage 1 — RD-002's deferrals: governed closed, discovery partially compute-bound

### 1a. Governed crypto 1h cells — COMPLETE (2/2)

| config | OOS trades | exp/trade | PF | folds+ | holdout | bar |
|---|---|---|---|---|---|---|
| adx_ema bare @ crypto30 1h | 3,304 | −0.160% | 0.919 | 2/5 | fail | FAIL |
| adx_ema production @ crypto30 1h | 301 | −0.473% | 0.771 | 2/5 | fail | FAIL |

The only surviving governed module fails decisively at 1h in both
configurations. Its wf-select procedure (pooled OOS in §5's table)
is likewise negative. Governed deferrals are fully closed.

### 1b. Discovery-module cells — 36 of 150 computed; 114 compute-deferred

Six modules completed all six cells. The pattern is unambiguous and
matches RD-002's experience with the other nine: the legacy
discovery fleet overwhelmingly does not run (NOT_EVALUABLE — the
adapter cannot serve the module) or does not fire (NO_TRADES) on
these panels; two cells hit the harness's own 300 s projection
screen (UNTESTABLE); the single EVALUATED cell produced 2 trades.

| module | cell | status | OOS trades | exp/trade | PF |
|---|---|---|---|---|---|
| arb_scanner | crypto30/1d | NOT_EVALUABLE | 0 | — | — |
| arb_scanner | forex28/1d | NOT_EVALUABLE | 0 | — | — |
| arb_scanner | comm7/1d | NOT_EVALUABLE | 0 | — | — |
| arb_scanner | idx7/1d | NOT_EVALUABLE | 0 | — | — |
| arb_scanner | crypto12/4h | NOT_EVALUABLE | 0 | — | — |
| arb_scanner | forex12/4h | NOT_EVALUABLE | 0 | — | — |
| bollinger_rsi_reversion | crypto30/1d | NO_TRADES | 0 | — | — |
| bollinger_rsi_reversion | forex28/1d | NO_TRADES | 0 | — | — |
| bollinger_rsi_reversion | comm7/1d | NO_TRADES | 0 | — | — |
| bollinger_rsi_reversion | idx7/1d | NO_TRADES | 0 | — | — |
| bollinger_rsi_reversion | crypto12/4h | UNTESTABLE | 0 | — | — |
| bollinger_rsi_reversion | forex12/4h | EVALUATED | 2 | +0.080% | inf |
| breakout_momentum | crypto30/1d | NOT_EVALUABLE | 0 | — | — |
| breakout_momentum | forex28/1d | NOT_EVALUABLE | 0 | — | — |
| breakout_momentum | comm7/1d | NOT_EVALUABLE | 0 | — | — |
| breakout_momentum | idx7/1d | NOT_EVALUABLE | 0 | — | — |
| breakout_momentum | crypto12/4h | NOT_EVALUABLE | 0 | — | — |
| breakout_momentum | forex12/4h | NOT_EVALUABLE | 0 | — | — |
| ensemble_strategy | crypto30/1d | NO_TRADES | 0 | — | — |
| ensemble_strategy | forex28/1d | NO_TRADES | 0 | — | — |
| ensemble_strategy | comm7/1d | NO_TRADES | 0 | — | — |
| ensemble_strategy | idx7/1d | NO_TRADES | 0 | — | — |
| ensemble_strategy | crypto12/4h | NO_TRADES | 0 | — | — |
| ensemble_strategy | forex12/4h | NO_TRADES | 0 | — | — |
| grid_trading | crypto30/1d | NOT_EVALUABLE | 0 | — | — |
| grid_trading | forex28/1d | NOT_EVALUABLE | 0 | — | — |
| grid_trading | comm7/1d | NOT_EVALUABLE | 0 | — | — |
| grid_trading | idx7/1d | NOT_EVALUABLE | 0 | — | — |
| grid_trading | crypto12/4h | NOT_EVALUABLE | 0 | — | — |
| grid_trading | forex12/4h | NOT_EVALUABLE | 0 | — | — |
| strategy_donchian_observe_only | crypto30/1d | NO_TRADES | 0 | — | — |
| strategy_donchian_observe_only | forex28/1d | NO_TRADES | 0 | — | — |
| strategy_donchian_observe_only | comm7/1d | NO_TRADES | 0 | — | — |
| strategy_donchian_observe_only | idx7/1d | NO_TRADES | 0 | — | — |
| strategy_donchian_observe_only | crypto12/4h | UNTESTABLE | 0 | — | — |
| strategy_donchian_observe_only | forex12/4h | NO_TRADES | 0 | — | — |

**Compute deferrals (NOT trials, NOT failures — uncomputed):** the
remaining 114 cells across 19 modules did not complete in the
research sandbox (1.5 shared vCPUs). These modules' per-bar cost
exceeds what the harness's 300 s projection screen estimates from a
2,000-bar single-symbol probe (the same superlinear failure mode
RD-002 disclosed for supertrend's 1h cell — e.g. strategy_donchian's
crypto12/4h probe itself burned 1,317 s before the screen declared
UNTESTABLE). One service restart also destroyed in-flight cells
(banked rows are checkpointed per cell and were never lost). The
deferred cells remain exactly as RD-002 pre-declared them; their
runners continue to checkpoint in the crew workspace and a follow-up
round can harvest them without any new declaration. Per module:

- ml_ensemble: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- options_pricing: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- pair_trading: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- prediction_enhanced: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- quantitative_engine: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- regime_detector: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- scalping_microstructure: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- sentiment_strategy: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- statistical_arbitrage: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_ehlers_hma: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_hybrid: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_mean_reversion_scalper: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_ml: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_rsi_divergence_scalper: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_scalping_breakout: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_supertrend_atr: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_volume_breakout: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- strategy_vwap_scalper: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h
- vwap_volume_profile: crypto30/1d, forex28/1d, comm7/1d, idx7/1d, crypto12/4h, forex12/4h

### 1c. Closed by deletion — never run, never resurrected (168 cells)

As declared in the Stage-1 accounting (shipped with the claim):
33 discovery modules deleted by TASK-STR-CLEANUP-001/002 under the
owner's PF < 1.2 rule account for 162 discovery cells, and the
governed 1h cells of supertrend + factory_winner_1..5 for 6 more.
The code no longer exists; RD-002's assignment predates the cleanup
and the owner's deletion order supersedes the deferral.

---

## 2. Stage 2 — new pre-declared families: all fail

Declared in `results_rd3/stage2_declaration.json` (PR merged before
the first cell ran). 24 cells + 10 wf-select procedures = 34 trials.
**Zero bar passers.** Per family:

* **funding_extremes** (crypto30 4h/1d) — funding prints as a
  positioning gauge (Binance Vision archives, every zip SHA-256
  verified against its published checksum; PEPE's prints come from
  the 1000PEPEUSDT contract archives, the mapping recorded in its
  manifest; full manifest set in `results_rd3/funding_manifest.json`).
  FADE loses heavily (fade_p95 @ 1d: −2.82%/trade, PF 0.738, 806
  trades — extreme funding persists/trends rather than reverting);
  CARRY loses too (best cell PF 0.922). Price-only judgement as
  declared. The mechanism is refuted on this data at these costs.
* **overnight_drift** (forex12/comm7 1h) — the 21:00→07:00 UTC
  window held outright or faded: PF 0.54–0.86 on 3,163–5,696 trades
  per cell. No overnight premium exists in these series net of
  costs. Indices were UNCOVERED for this mechanism (Yahoo cash-index
  1h has no overnight bars) and were not run.
* **btc_leadlag** (crypto12/crypto30 1h) — BTC's trailing move does
  not predict alts profitably at 1h after 16 bps costs: PF 0.78–0.86
  on up to 46,601 wf-pooled trades. Decisively refuted at this
  horizon.
* **vol_regime_switch** (crypto30 4h/1d, comm7 1d, forex28 1d) —
  the switch does not rescue its components on crypto/forex
  (PF 0.82–0.97). On **comm7 1d both variants are positive**
  (switch_a: +1.173%/trade, PF 1.372, 151 trades; switch_b:
  +0.793%, PF 1.237, 124 trades) but fail the ≥ 200-trade floor —
  watchlist, §5.

## 3. Stage 2B — forex-native families (OANDA venue design): all fail

Declared in `results_rd3/stage2b_declaration.json` (PR merged before
the first cell ran; owner scope extension). 14 cells + 7 wf-select
procedures = 21 trials. **Zero bar passers.** Per family:

* **london_drive** (forex12/comm7 1h) — Asia-range → London
  expansion is refuted: drive_plain @ forex12 PF 0.595 on 1,632
  trades; the narrow-range filter starves the signal (19–24 trades)
  and still loses.
* **monday_gap_fade** (forex28/comm7 1d) — gap fades lose on
  commodities (−0.66 to −0.68%/trade) and on FX at θ=0.5 (PF 0.871);
  θ=1.0 on forex28 is mildly positive (+0.046%, PF 1.127, 103
  trades) — sub-bar on PF and trades.
* **trend_pullback** (forex28 1d, forex12 4h, comm7 1d) —
  retracement entries fail on FX (PF 0.60–0.68) but are **positive
  on comm7 1d**: pb_ema100 +0.766%/trade, PF 1.217 (113 trades);
  pb_ema200 +0.642%, PF 1.182 (109 trades). Both fail the
  ≥ 200-trade floor — watchlist, §5.

Data note (declared): the OANDA practice price API is not reachable
from the research sandbox (no venue credentials in this
environment); families were judged on RD-002's provenanced Yahoo
series with OANDA-modelled costs. TASK-STR-FWD-004's forward lane
supplies live OANDA evidence for anything carried forward.

---

## 4. OANDA forward-test lane — ONE candidate (FORWARD_TEST class)

Mined from RD-002's full record (522 forex/comm rows) plus all
RD-003 forex cells, under the coordinator's criterion — *mechanical
bar passed, significance pending*. Exactly one configuration in the
entire programme's history qualifies:

### tsmom2_dual / roc30_ema200 @ comm7 4h — FORWARD_TEST candidate

Dual time-series momentum (30-bar ROC direction gated by an
EMA200 regime filter; bracket 2.0/4.0 ATR exits; RD-002 batch-2
family, fully specified in `rd2/families2.py`). OANDA relevance:
comm7 = GOLD, SILVER, WTI, BRENT, NATGAS, COPPER, PLATINUM — all
OANDA CFD instruments (XAU/USD etc.).

Evidence pack (RD-002 synthesis record; the cell was RE-RUN
deterministically for this pack and reproduced **bit-identically**:
205 trades, expectancy 0.0055805799369819074, PF 1.2026201995165708):

| element | value |
|---|---|
| OOS trades | 205 |
| expectancy / trade | +0.558% |
| PF (net, RD-002 costs) | 1.203 |
| positive folds | 4/5 |
| mechanical bar | **PASS** (incl. holdout) |
| max symbol profit share | 0.377 (SILVER) — breadth PASS |
| per-symbol shares | GOLD 0.227, WTI 0.192, NATGAS 0.163, BRENT 0.036, PLATINUM 0.005, COPPER 0.000 |
| Bonferroni @ N=1,557 | FAIL (p above 3.2e-5) — significance pending, the FORWARD_TEST rationale |
| **2×-cost PF** | **1.149 — below the 1.2 sensitivity line** (exact recomputation from regenerated trades; stated plainly: this candidate is cost-fragile) |
| DSR (RD-002 record) | gate-estimator tail ≈ 0.0035; naive-estimator tails ~1e-9–1e-11 — reported, not gating, per RD-002's stated method |

Handoff: the coordinator/FWD-004 lane carries this as FORWARD_TEST
(tagged fills, FWD-003 kill criteria). Research crews do not touch
production; nothing here wires it anywhere.

### Near-miss annex (NOT forward-test candidates — bar not passed)

Named so the coordinator sees the whole board; each missed the bar
on the stated element only:

| config | trades | exp | PF | folds | missed on |
|---|---|---|---|---|---|
| zscore_reversion/w50_t2.5_filt @ forex28 1d (RD-002) | 130 | +0.347% | 1.476 | 4/5 | trades (<200) |
| tsmom2_dual/roc90_ema200 @ forex28 1d (RD-002) | 127 | +0.623% | 1.505 | 3/5 | trades, folds |
| ichimoku_trend/tk_cloud @ comm7 4h (RD-002) | 207 | +0.639% | 1.314 | 3/5 | folds |
| stoch_reversion/k14_raw @ forex28 1d (RD-002) | 365 | +0.286% | 1.262 | 4/5 | holdout/breadth |
| vol_regime_switch/switch_a @ comm7 1d (RD-003) | 151 | +1.173% | 1.372 | — | trades |
| trend_pullback/pb_ema100 @ comm7 1d (RD-003) | 113 | +0.766% | 1.217 | — | trades |

(governed supertrend @ comm7 4h, PF 1.236 in RD-002, is excluded
from this annex: its code was deleted by CLEANUP-001 and cannot be
forward-tested.)

---

## 5. Stage 3 — synthesis

Trial accounting: RD-001 116 + RD-002 1,441 = 1,557 prior; RD-003
adds 94 (76 rows + 18
procedures: Stage 1 governed 2 rows + 1 wf, Stage 1 discovery
36 rows, Stage 2 24 rows + 10 wf, Stage 2B 14 rows + 7 wf)
→ **global N = 1,651**.
Significance method unchanged from RD-002 (Bonferroni gate at the
final N; DSR reported, not gating; 2×-cost exact from saved trades
— costs enter this harness only through net returns, exits are
price-level based, so net → 2·net − gross per trade is exact).
Full machine record: `results_rd3/synthesis.json`.

### RD-002 passers re-checked at N = 1,651

The Bonferroni threshold tightens from 3.21e-5 (N=1,557) to
3.028e-05. **ichimoku_trend/tk_cloud @ crypto30 4h stands** (adjusted
p = 1.4e-7 on RD-002's record — two orders inside the new line).
**dow_effect/reversal @ crypto30 1d stands**: its aggregate DSR tail
on RD-002's record is ~9e-29 and it passed Bonferroni at 1,557 with
3,660 trades at +0.878%/trade; a 6% larger N cannot move a p-value
of that magnitude across the line. (Exact p_one_sided values live in
RD-002's unshipped row corpus; the re-check rests on the shipped
synthesis record, stated plainly.) Both remain with FWD-002; RD-003
changes nothing about them.

### Ranked table (all RD-003 rows, by expectancy)

| # | config | panel/tf | status | OOS trades | exp/trade | PF | folds+ | max sym share | bar | sig | 2x-cost PF |
|---|--------|----------|--------|-----------|-----------|-----|--------|---------------|-----|-----|------------|
| 1 | vol_regime_switch/switch_a | comm7/1d | EVALUATED | 151 | +1.173% | 1.372 | 5 | 0.39 | fail | fail | — |
| 2 | vol_regime_switch/switch_b | comm7/1d | EVALUATED | 124 | +0.793% | 1.237 | 5 | 0.32 | fail | fail | — |
| 3 | trend_pullback/pb_ema100 | comm7/1d | EVALUATED | 113 | +0.766% | 1.217 | 3 | 0.41 | fail | fail | — |
| 4 | trend_pullback/pb_ema200 | comm7/1d | EVALUATED | 109 | +0.642% | 1.182 | 3 | 0.37 | fail | fail | — |
| 5 | discovery/bollinger_rsi_reversion | forex12/4h | EVALUATED | 2 | +0.080% | inf | 1 | 1.00 | fail | fail | — |
| 6 | monday_gap_fade/gap_1.0 | forex28/1d | EVALUATED | 103 | +0.046% | 1.127 | 1 | 0.27 | fail | fail | — |
| 7 | london_drive/drive_narrow | forex12/1h | EVALUATED | 19 | -0.009% | 0.922 | 2 | 1.00 | fail | fail | — |
| 8 | monday_gap_fade/gap_0.5 | forex28/1d | EVALUATED | 427 | -0.043% | 0.871 | 2 | 0.30 | fail | fail | — |
| 9 | overnight_drift/drift_long | forex12/1h | EVALUATED | 5696 | -0.050% | 0.612 | 0 | 1.00 | fail | fail | — |
| 10 | london_drive/drive_plain | forex12/1h | EVALUATED | 1632 | -0.058% | 0.595 | 0 | 1.00 | fail | fail | — |
| 11 | vol_regime_switch/switch_a | forex28/1d | EVALUATED | 458 | -0.061% | 0.938 | 2 | 0.27 | fail | fail | — |
| 12 | overnight_drift/drift_fade | forex12/1h | EVALUATED | 5669 | -0.062% | 0.544 | 0 | 1.00 | fail | fail | — |
| 13 | overnight_drift/drift_fade | comm7/1h | EVALUATED | 3163 | -0.087% | 0.861 | 0 | 0.55 | fail | fail | — |
| 14 | vol_regime_switch/switch_a | crypto30/4h | EVALUATED | 4960 | -0.102% | 0.967 | 2 | 0.17 | fail | fail | — |
| 15 | vol_regime_switch/switch_b | crypto30/4h | EVALUATED | 3791 | -0.104% | 0.966 | 2 | 0.21 | fail | fail | — |
| 16 | overnight_drift/drift_long | comm7/1h | EVALUATED | 3169 | -0.115% | 0.819 | 0 | 1.00 | fail | fail | — |
| 17 | trend_pullback/pb_ema200 | forex12/4h | EVALUATED | 1013 | -0.123% | 0.650 | 0 | 1.00 | fail | fail | — |
| 18 | london_drive/drive_plain | comm7/1h | EVALUATED | 842 | -0.130% | 0.822 | 0 | 1.00 | fail | fail | — |
| 19 | btc_leadlag/lag4_t1.0 | crypto12/1h | EVALUATED | 32742 | -0.140% | 0.782 | 0 | 1.00 | fail | fail | — |
| 20 | btc_leadlag/lag4_t1.0 | crypto30/1h | EVALUATED | 86162 | -0.142% | 0.808 | 0 | 1.00 | fail | fail | — |
| 21 | trend_pullback/pb_ema100 | forex12/4h | EVALUATED | 1059 | -0.142% | 0.600 | 0 | 1.00 | fail | fail | — |
| 22 | btc_leadlag/lag12_t1.5 | crypto12/1h | EVALUATED | 17708 | -0.146% | 0.858 | 0 | 1.00 | fail | fail | — |
| 23 | funding_extremes/carry_1bp | crypto30/4h | EVALUATED | 5404 | -0.146% | 0.920 | 2 | 0.48 | fail | fail | — |
| 24 | funding_extremes/carry_3bp | crypto30/4h | EVALUATED | 1258 | -0.159% | 0.922 | 2 | 0.22 | fail | fail | — |
| 25 | governed/strategy_adx_ema:bare | crypto30/1h | EVALUATED | 3304 | -0.160% | 0.919 | 2 | 0.22 | fail | fail | — |
| 26 | vol_regime_switch/switch_b | forex28/1d | EVALUATED | 353 | -0.168% | 0.839 | 1 | 0.43 | fail | fail | — |
| 27 | btc_leadlag/lag12_t1.5 | crypto30/1h | EVALUATED | 46601 | -0.184% | 0.848 | 0 | 1.00 | fail | fail | — |
| 28 | trend_pullback/pb_ema200 | forex28/1d | EVALUATED | 193 | -0.262% | 0.682 | 1 | 0.18 | fail | fail | — |
| 29 | trend_pullback/pb_ema100 | forex28/1d | EVALUATED | 198 | -0.299% | 0.656 | 1 | 0.39 | fail | fail | — |
| 30 | funding_extremes/carry_1bp | crypto30/1d | EVALUATED | 1956 | -0.344% | 0.888 | 1 | 0.30 | fail | fail | — |
| 31 | funding_extremes/fade_p95 | crypto30/4h | EVALUATED | 3652 | -0.423% | 0.894 | 1 | 0.57 | fail | fail | — |
| 32 | funding_extremes/fade_p90 | crypto30/4h | EVALUATED | 4398 | -0.444% | 0.889 | 1 | 0.23 | fail | fail | — |
| 33 | governed/strategy_adx_ema:production | crypto30/1h | EVALUATED | 301 | -0.473% | 0.771 | 2 | 0.22 | fail | fail | — |
| 34 | funding_extremes/carry_3bp | crypto30/1d | EVALUATED | 464 | -0.531% | 0.857 | 1 | 0.26 | fail | fail | — |
| 35 | london_drive/drive_narrow | comm7/1h | EVALUATED | 24 | -0.572% | 0.467 | 1 | 1.00 | fail | fail | — |
| 36 | monday_gap_fade/gap_1.0 | comm7/1d | EVALUATED | 79 | -0.660% | 0.644 | 3 | 1.00 | fail | fail | — |
| 37 | monday_gap_fade/gap_0.5 | comm7/1d | EVALUATED | 202 | -0.685% | 0.667 | 1 | 0.68 | fail | fail | — |
| 38 | vol_regime_switch/switch_a | crypto30/1d | EVALUATED | 864 | -1.486% | 0.828 | 2 | 0.29 | fail | fail | — |
| 39 | vol_regime_switch/switch_b | crypto30/1d | EVALUATED | 712 | -1.599% | 0.818 | 2 | 0.37 | fail | fail | — |
| 40 | funding_extremes/fade_p90 | crypto30/1d | EVALUATED | 872 | -1.734% | 0.837 | 0 | 0.36 | fail | fail | — |
| 41 | funding_extremes/fade_p95 | crypto30/1d | EVALUATED | 806 | -2.819% | 0.738 | 1 | 0.44 | fail | fail | — |
| 42 | discovery/arb_scanner | comm7/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 43 | discovery/arb_scanner | crypto12/4h | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 44 | discovery/arb_scanner | crypto30/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 45 | discovery/arb_scanner | forex12/4h | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 46 | discovery/arb_scanner | forex28/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 47 | discovery/arb_scanner | idx7/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 48 | discovery/bollinger_rsi_reversion | comm7/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 49 | discovery/bollinger_rsi_reversion | crypto12/4h | UNTESTABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 50 | discovery/bollinger_rsi_reversion | crypto30/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 51 | discovery/bollinger_rsi_reversion | forex28/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 52 | discovery/bollinger_rsi_reversion | idx7/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 53 | discovery/breakout_momentum | comm7/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 54 | discovery/breakout_momentum | crypto12/4h | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 55 | discovery/breakout_momentum | crypto30/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 56 | discovery/breakout_momentum | forex12/4h | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 57 | discovery/breakout_momentum | forex28/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 58 | discovery/breakout_momentum | idx7/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 59 | discovery/ensemble_strategy | comm7/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 60 | discovery/ensemble_strategy | crypto12/4h | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 61 | discovery/ensemble_strategy | crypto30/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 62 | discovery/ensemble_strategy | forex12/4h | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 63 | discovery/ensemble_strategy | forex28/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 64 | discovery/ensemble_strategy | idx7/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 65 | discovery/grid_trading | comm7/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 66 | discovery/grid_trading | crypto12/4h | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 67 | discovery/grid_trading | crypto30/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 68 | discovery/grid_trading | forex12/4h | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 69 | discovery/grid_trading | forex28/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 70 | discovery/grid_trading | idx7/1d | NOT_EVALUABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 71 | discovery/strategy_donchian_observe_only | comm7/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 72 | discovery/strategy_donchian_observe_only | crypto12/4h | UNTESTABLE | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 73 | discovery/strategy_donchian_observe_only | crypto30/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 74 | discovery/strategy_donchian_observe_only | forex12/4h | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 75 | discovery/strategy_donchian_observe_only | forex28/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |
| 76 | discovery/strategy_donchian_observe_only | idx7/1d | NO_TRADES | 0 | — | — | 0 | 1.00 | fail | fail | — |

### wf-select procedures (pooled OOS)

- funding_extremes__crypto30__4h: trades=5404 exp=-0.146% pf=0.920
- funding_extremes__crypto30__1d: trades=1956 exp=-0.344% pf=0.888
- overnight_drift__forex12__1h: trades=5696 exp=-0.050% pf=0.612
- overnight_drift__comm7__1h: trades=3165 exp=-0.090% pf=0.857
- btc_leadlag__crypto12__1h: trades=17708 exp=-0.146% pf=0.858
- btc_leadlag__crypto30__1h: trades=46601 exp=-0.184% pf=0.848
- vol_regime_switch__crypto30__4h: trades=4717 exp=-0.118% pf=0.962
- vol_regime_switch__crypto30__1d: trades=864 exp=-1.486% pf=0.828
- vol_regime_switch__comm7__1d: trades=151 exp=+1.173% pf=1.372
- vol_regime_switch__forex28__1d: trades=458 exp=-0.061% pf=0.938
- london_drive__forex12__1h: trades=19 exp=-0.009% pf=0.922
- london_drive__comm7__1h: trades=842 exp=-0.130% pf=0.822
- monday_gap_fade__forex28__1d: trades=103 exp=+0.046% pf=1.127
- monday_gap_fade__comm7__1d: trades=98 exp=-0.714% pf=0.633
- trend_pullback__forex28__1d: trades=198 exp=-0.299% pf=0.656
- trend_pullback__forex12__4h: trades=745 exp=-0.109% pf=0.656
- trend_pullback__comm7__1d: trades=109 exp=+0.642% pf=1.182
- governed__adx_ema__crypto30__1h: trades=3304 exp=-0.160% pf=0.919

### Watchlist (positive expectancy, sub-bar — for the record, not for wiring)

Four of the five strongest RD-003 rows are the same shape:
commodity-panel cells that clear PF ≥ 1.2 but cannot reach 200 OOS
trades inside the fold era (switch_a/switch_b and pb_ema100 on
comm7 1d, 109–151 trades). That is a data-span limit, not a tuning
invitation — minting variants to chase the trade count would be
exactly the overfitting the Anti-Overfit Law forbids. If any of
these is ever settled, it will be by forward evidence (the §4 lane
pattern), not by more backtest combinations.

### Method notes

* Funding data provenance: Binance Vision monthly fundingRate
  archives; 40 series were fetched and verified, of which the 30
  crypto30 panel symbols were used (10 further fetched series were
  not panel members and went unused); every zip SHA-256 verified
  against its published .CHECKSUM; merged manifests in
  `results_rd3/funding_manifest.json`.
* A mid-run sandbox service restart destroyed in-flight cells only;
  every banked row is checkpointed and synthesis reads only banked
  rows. Trial counts count completed cells only, per RD-002's
  convention.
* The repo's `AGENTS.md` turn-completion Telegram protocol applies
  to ZAI agent sessions; this crew reports through the board and
  issue #35 per its tasking.
