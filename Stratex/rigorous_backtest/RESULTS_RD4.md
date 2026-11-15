# RESULTS — TASK-STR-RD-004: volatility-regime trend following

**Status: COMPLETE (research) — verdicts below; coordinator verifies and
merges.** Owner standing rule 2026-11-15: strategy finding never stops;
any configuration passing the full bar is wired into demo trading by the
coordinator. This round tests ONE new pre-declared family:
**volatility-regime trend following** on CRYPTO30 at 15m and 2h —
timeframes RD-002/RD-003 did not judge for trend families.

**Pre-declaration (binding, posted before any data fetch or run):**
claim — issue #35 comment
[6890957904](https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6890957904);
declaration — comment
[6890972056](https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6890972056);
machine-readable copy in `results_rd4/declaration.json`. Nothing in the
grid changed after the declaration.

**The bar (unchanged from RD-001/RD-002/RD-003):** expectancy > 0 AND
PF ≥ 1.2 AND ≥ 200 OOS trades AND ≥ 80% of folds positive AND
untouched-holdout pass AND Bonferroni significance at the RUNNING
global trial count AND 2×-cost sensitivity pass AND breadth.
RD-004's declared significance element is the strict form
(Bonferroni p < 0.05/N **and** deflated Sharpe ≥ 0.95) and its
declared 2×-cost element is PF ≥ 1.2 with expectancy > 0 — the
standard RD-002's two live winners actually met.
*Disclosure:* RD-002's synthesis applied the Bonferroni gate with DSR
reported as a caveat (its winners' DSR ≈ 0). RD-004 keeps its own
stricter declared gate; per-config p-values and DSRs are published in
`results_rd4/synthesis.json` so the coordinator can re-judge any row
under either convention.

**Trial accounting.** RD-004 = 32 cells + 2 wf-select procedures =
**34 trials**. Judged at **N = 1,798** = 1,557 (RD-001/RD-002 final) +
207 (RD-003 declared on main: 152 + 34 + 21) + 34. Sibling Wave-4
crews add trials concurrently (the coordinator's floor was already
≥ 1,812 from RD-013's 48 before RD-004's own 34; RD-007's crew
computed 1,891 including later completions). **No RD-004 verdict is
N-sensitive:** every positive-expectancy row also fails at least one
N-independent element (PF, fold consistency, or 2×-cost), and the best
row's p-value (0.0142) fails the Bonferroni gate even at N = 34
(α = 0.00147). The verdicts below are identical at any reconciled
global N ≥ 34.

**Sanity anchor (harness fidelity).** RD-001's `ts_momentum` roc42_4h
cell (BTC/ETH/SOL, 1h 2023-10..2026-10 resampled to 4h, untouched
RD-002 chain) reproduced **bit-identically** before any RD-004 number
was produced: **303 OOS trades, expectancy 0.0024275740638451445,
PF 1.0969220482985518**. (First assembly pooled full-period trades —
372 — because RD-001's rows are OOS rows; corrected to the OOS basis
and re-verified. Recorded in `results_rd4/synthesis.json`.)
Additionally, RD-004's per-entry scale engine was asserted
trade-identical to `fastsim.simulate_entries` at scale factor 1
(3,934 trades, BTCUSDT 15m don20 base — `engine_consistency.json`),
re-verified inside the staged judged run. After the run, two cells
(2h ema24_96_gate_lo, 15m don20_base) were independently recomputed
from the shipped trade CSVs and matched their rows bit-identically,
and fragment row counts matched merged trade counts exactly.

---

## The family, as declared

- **Signals (events only, causal, warmup 260 bars):** `don20`/`don55`
  Donchian channel crosses; `ema12_48`/`ema24_96` EMA crosses.
- **Regime state (causal, daily):** bar ATR%(14); daily vol V(d) =
  mean bar ATR% over the UTC day; R(d) = rank of V(d−1) among the
  prior 180 daily values. All bars of day d use R(d).
- **Modes:** `base` (ungated control), `gate_hi` (R ≥ 0.50 only),
  `gate_lo` (R < 0.50 only), `scale` (bracket multiples ×
  (0.75 + 0.5·R)).
- **Exits:** bracket SL 2.0× / TP 4.0× ATR(14) at the signal bar,
  fastsim entry-price anchor, MODULE convention.
- **Costs:** harness crypto standard — 16 bps round trip
  (5 fee + 3 spread/slippage per side); 2× = 32 bps.
- **Adjacency disclosed:** RD-003's `vol_regime_switch` (donchian /
  z-score switch, 4h/1d) is a different mechanism on different
  timeframes; RD-004 is pure trend and adds the SCALE mode.

## Data

Binance Vision USDT-M futures monthly klines, 15m, 2023-01..2026-10
(per-symbol first archive month for ARB 2023-03 / SUI 2023-05), via
the harness `data_feed` cache contract (per-zip SHA-256, canonical
CSV SHA-256, gap audit). **All 30 CRYPTO30 series covered; zero
missing bars across the whole panel** (4.0M bars). 2h derived from
the verified 15m series (complete 8-bar buckets only, parent hash
recorded; rd4-local resample implementing the harness rule — the
harness `_TF_MINUTES` table has no 2h entry). Full provenance:
`results_rd4/coverage.json`. Fold profile STANDARD (W1–W5, OOS
2024-07-01..2026-11-01) for every cell.

## Results

**Headline: ZERO PASSERS. ZERO WATCHLIST. All 32 cells and both
wf-select procedures FAIL the declared bar.** No configuration is
promoted, and nothing in this family is wired to forward demo trading.
The result is not a uniform zero, though — the texture below is the
measured content of this round.

### Per-config table (pooled OOS, W1–W5)

| TF | Variant | OOS trades | Expectancy | PF | Folds + | Holdout | PF @2x | p (1-sided) | DSR | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 2h | ema24_96_gate_lo | 2286 | +0.202% | 1.107 | 2/5 | pass | 1.022 | 0.014222580545783181 | 0.568 | FAIL |
| 2h | don20_gate_lo | 6313 | +0.148% | 1.074 | 3/5 | pass | 0.994 | 0.005394345457189864 | 0.205 | FAIL |
| 2h | ema12_48_gate_lo | 3471 | +0.107% | 1.055 | 2/5 | pass | 0.975 | 0.07883260864919817 | 0.138 | FAIL |
| 2h | don55_gate_lo | 4138 | +0.079% | 1.038 | 2/5 | pass | 0.963 | 0.14155220864875362 | 0.049 | FAIL |
| 2h | ema12_48_scale | 5146 | +0.069% | 1.029 | 2/5 | pass | 0.963 | 0.19279214982238158 | 0.015 | FAIL |
| 2h | don20_scale | 9474 | +0.051% | 1.021 | 3/5 | pass | 0.957 | 0.20558218255669425 | 0.000 | FAIL |
| 2h | ema12_48_base | 5250 | +0.049% | 1.020 | 2/5 | pass | 0.956 | 0.26123041699585636 | 0.007 | FAIL |
| 2h | don55_scale | 6621 | +0.035% | 1.014 | 2/5 | pass | 0.952 | 0.3178731018658354 | 0.001 | FAIL |
| 2h | don20_base | 9566 | +0.030% | 1.012 | 3/5 | FAIL | 0.951 | 0.31081953991104894 | 0.000 | FAIL |
| 2h | don55_base | 6497 | +0.012% | 1.005 | 2/5 | FAIL | 0.945 | 0.4341965378385245 | 0.001 | FAIL |
| 2h | ema24_96_base | 3558 | -0.042% | 0.982 | 2/5 | pass | 0.919 | 0.6810182576831594 | 0.001 | FAIL |
| 15m | don55_gate_lo | 28938 | -0.090% | 0.885 | 0/5 | FAIL | 0.718 | 1.0 | 0.000 | FAIL |
| 2h | ema24_96_scale | 3548 | -0.093% | 0.960 | 2/5 | FAIL | 0.896 | 0.8443551199975414 | 0.000 | FAIL |
| 15m | don20_gate_lo | 43586 | -0.096% | 0.874 | 0/5 | FAIL | 0.705 | 1.0 | 0.000 | FAIL |
| 15m | ema12_48_gate_lo | 23031 | -0.107% | 0.859 | 0/5 | FAIL | 0.689 | 1.0 | 0.000 | FAIL |
| 15m | ema24_96_gate_lo | 14816 | -0.110% | 0.852 | 0/5 | FAIL | 0.682 | 1.0 | 0.000 | FAIL |
| 15m | ema12_48_base | 40434 | -0.131% | 0.861 | 0/5 | FAIL | 0.722 | 1.0 | 0.000 | FAIL |
| 15m | ema12_48_scale | 40262 | -0.133% | 0.855 | 0/5 | FAIL | 0.713 | 1.0 | 0.000 | FAIL |
| 2h | don55_gate_hi | 2764 | -0.133% | 0.960 | 2/5 | FAIL | 0.914 | 0.8337141167017057 | 0.001 | FAIL |
| 15m | don20_base | 75231 | -0.136% | 0.859 | 0/5 | FAIL | 0.724 | 1.0 | 0.000 | FAIL |
| 15m | don20_scale | 76380 | -0.144% | 0.845 | 0/5 | FAIL | 0.706 | 1.0 | 0.000 | FAIL |
| 15m | don55_base | 51081 | -0.144% | 0.854 | 0/5 | FAIL | 0.721 | 1.0 | 0.000 | FAIL |
| 15m | don55_scale | 51740 | -0.153% | 0.842 | 0/5 | FAIL | 0.708 | 1.0 | 0.000 | FAIL |
| 15m | ema24_96_base | 26997 | -0.159% | 0.831 | 0/5 | FAIL | 0.695 | 1.0 | 0.000 | FAIL |
| 15m | ema12_48_gate_hi | 19167 | -0.160% | 0.861 | 1/5 | FAIL | 0.745 | 1.0 | 0.000 | FAIL |
| 15m | ema24_96_scale | 26504 | -0.172% | 0.817 | 0/5 | FAIL | 0.683 | 1.0 | 0.000 | FAIL |
| 15m | don20_gate_hi | 35374 | -0.188% | 0.843 | 0/5 | FAIL | 0.733 | 1.0 | 0.000 | FAIL |
| 15m | don55_gate_hi | 23437 | -0.206% | 0.831 | 0/5 | FAIL | 0.725 | 1.0 | 0.000 | FAIL |
| 15m | ema24_96_gate_hi | 12651 | -0.214% | 0.814 | 0/5 | FAIL | 0.703 | 1.0 | 0.000 | FAIL |
| 2h | ema12_48_gate_hi | 2283 | -0.224% | 0.928 | 2/5 | FAIL | 0.880 | 0.9462452712128938 | 0.000 | FAIL |
| 2h | don20_gate_hi | 4465 | -0.248% | 0.924 | 2/5 | FAIL | 0.879 | 0.9908925206904086 | 0.000 | FAIL |
| 2h | ema24_96_gate_hi | 1366 | -0.445% | 0.859 | 1/5 | FAIL | 0.815 | 0.9940391685792157 | 0.000 | FAIL |

### Walk-forward selection procedures (counted trials)

| Procedure | OOS trades | Expectancy | PF | PF @2x | p | DSR | Verdict | Per-fold picks |
|---|---|---|---|---|---|---|---|---|
| wf_select[15m] | 23685 | -0.161% | 0.844 | 0.718 | 1.0 | 0.000 | FAIL | W1: ema12_48_base, W2–W4: ema12_48_gate_hi, W5: ema12_48_gate_lo |
| wf_select[2h] | 2286 | +0.202% | 1.107 | 1.022 | 0.0142 | 0.568 | FAIL | ema24_96_gate_lo in all five folds |

### Reading of the result

1. **15m is uniformly dead for this family.** All 16 cells have
   negative expectancy (PF 0.81–0.89, zero positive folds almost
   everywhere). At a 16 bps round-trip cost, short-horizon bracket
   trend trades on CRYPTO30 do not carry their friction; no regime
   mode rescues the timeframe.
2. **The declared regime intuition is inverted at 2h.** The design
   bet was that high-volatility regimes favour trend following.
   Measured: `gate_lo` (low-vol entries only) is the best mode for
   **all four signals** at 2h, and `gate_hi` is the worst mode for
   **all four signals at both timeframes** (every gate_hi cell has
   negative expectancy). What little positive expectancy exists at 2h
   sits in quiet-regime entries.
3. **Even the best cell is far from the bar.** ema24_96_gate_lo@2h
   (PF 1.107, +0.202%/trade, 2,286 trades) fails four independent
   elements: PF < 1.2, folds 2/5 positive, significance (p = 0.0142
   vs Bonferroni α = 2.78e-5 at N = 1,798; DSR 0.568 < 0.95), and
   2×-cost (PF falls to 1.022). It is a sub-bar texture, not a
   near-miss on one element.
4. **The 2h gate_lo effect decays over time.** wf-select picked
   ema24_96_gate_lo in every fold; its per-fold OOS PF runs
   W1 1.459 → W2 1.318 → W3 0.925 → W4 0.956 → W5 0.914 — positive in
   the 2024-07..2025-07 folds, negative from 2025-07 onward, with
   per-fold max drawdowns of −64% to −90% on the summed-return
   convention. This is a fading regime effect, not a stable edge.
5. **Bracket scaling by vol rank adds nothing.** `scale` sits between
   `base` and `gate_lo` at 2h and below `base` at 15m; the one novel
   mechanism in this family does not earn its complexity.

## What this means for Stratex

The volatility-regime trend family is **closed at the declared bar**:
no passer, no watchlist entry, nothing to wire into the forward demo
lane. The gate_lo@2h cluster is recorded above as measured sub-bar
texture — explicitly **not** a watchlist (under the declared rules,
WATCHLIST requires passing the mechanical bar, which no cell did).
If a future round wants to pursue low-vol-regime entries at 2h with
different exits or risk geometry, that is a NEW family requiring its
own pre-declaration and its own counted trials; RD-004's bar does not
bend retroactively. The programme's forward lane continues to rest on
the RD-002 winners and the RD-003 additions already registered there.

## Execution incidents (disclosed in full)

The numbers above come from a difficult execution environment; every
incident is recorded here because each one shaped the run, and none
of them changed a declared parameter.

1. **Cache sidecar loss (data fetch).** Six symbols (ATOM, AVAX, INJ,
   NEAR, OP, UNI) silently lost their provenance sidecars when the
   harness cache writer's writes were swallowed during an OS-level
   write-block episode (below). The cache contract correctly REFUSED
   the sidecar-less CSVs; all six series were re-fetched and their
   canonical CSV hashes are byte-identical to the first fetch. The
   final panel was re-verified end-to-end before judging: 30/30
   sidecars present, every `csv_sha256` matching, zero missing bars.
2. **Write-block episodes (EPERM).** This sandbox intermittently
   returns `EPERM (Operation not permitted)` on file writes from
   compute processes for minutes-to-hours at a time (a security-layer
   behaviour under the ~80-crew parallel load; reads and network
   calls were unaffected). It killed: the first judged monolithic run
   (crashed on the AVAX sidecar refusal — the integrity system
   working as designed, no rows written), the second monolithic run
   (all 30 symbols computed, then the first row write was blocked),
   and several worker attempts.
3. **Staged, checkpointed execution.** The judged run was therefore
   executed in stages — `rd4/run_symbol.py` (one symbol × timeframe
   per process, trade fragments on disk) → `rd4/assemble.py` (one
   config per process, judged rows + merged trade CSVs) → `rd4/wf.py`
   (procedure rows) → `rd4/synth4.py` (verdicts) — with
   retry-hardened writers throughout. The stages call the identical
   functions in the identical accumulation order as the monolithic
   reference implementation (`rd4/run_rd4.py`, kept in tree), so the
   numbers are the monolithic numbers; the engine probe
   (fastsim-identity at scale 1) re-ran inside the staged BTC worker.
   A discarded 3-symbol smoke run validated the pipeline end-to-end
   before the judged run; its numbers were never reported or counted.
   The staged driver ultimately completed all stages in ~15 minutes
   once a sandbox restart cleared the write-block; a delegated
   runner session confirmed the block was environment-wide, not
   session-specific.

## Reproduce

```bash
cd Stratex
# stage 1: per-symbol fragments (60 units: 30 symbols x {15m,2h})
python3 -m rigorous_backtest.rd4.run_symbol --tf 15m --symbol BTCUSDT \
    --cache-dir <rd-004 15m cache> --coverage <coverage.json> \
    --frag-dir results_rd4/frag --out-dir results_rd4   # x60
# stage 2: per-config rows (32 units)
python3 -m rigorous_backtest.rd4.assemble --tf 15m --signal don20 \
    --mode base --frag-dir results_rd4/frag \
    --out-dir results_rd4                               # x32
# stage 3: wf-select procedure rows (2 units)
python3 -m rigorous_backtest.rd4.wf --tf 15m --out-dir results_rd4
python3 -m rigorous_backtest.rd4.wf --tf 2h  --out-dir results_rd4
# stage 4: synthesis / verdicts
python3 -m rigorous_backtest.rd4.synth4 --out-dir results_rd4 \
    --anchor-json <anchor_result.json> --coverage <coverage.json>
```

(`rd4/run_rd4.py` remains as the monolithic reference implementation
of the same computation.) Data regenerates from the public Binance
Vision archive; every series hash is in `results_rd4/coverage.json`,
every trade of every cell in `results_rd4/rows/trades/`.

## Scope statement

Research only. No production code, registry, daemon, configuration
or priors were changed. Any PASS row would have been a *candidate for
the forward demo protocol* (8 weeks AND ≥ 100 closed trades, phase-3
kill criteria) — a backtest pass is not proof of profit, and nothing
here authorises live trading. This round produced no such candidate.
