# RESULTS — EMA 5/11 crossover bracket (S-RD1), TASK-IG2-STR-19: declared backtest RUN

**VERDICT: FAIL — the family is CLOSED per the declaration.**

Run executed under the frozen declaration
`ema511_declaration.json`, SHA-256
`671a1426555c1c969e7364cf6de009a39a485e613b5c8f0bcbb8e335db635b2e`
(re-verified by the runner itself before any simulation).
This file is the run record; the machine record shipped beside it
is `ema511_results.json` — a byte-identical copy of the run's
`results.json` (SHA-256
`5e6bc45e2bc1e0f37c195bd0a4bf5a7fa45d2461f4f6458376795e99ac8e5b7f`).

## The chain (stated wherever the verdict is reported)

1. **Declaration first.** The family was pre-declared (PR #880)
   before any backtest of it had run: one frozen cell —
   EMA_FAST=5, EMA_SLOW=11, RR_TARGET=3.0, BE_TRIGGER_R=1.5 on the
   crypto30 15-minute panel. The data gate passed before
   declaration: the identical panel the Box Theory run used,
   hash-pinned in a frozen provenance manifest.
2. **Attempt 1 — executed, verdict lost, never observed.** The run
   executed end-to-end (all 30 symbols simulated and judged in
   memory), but the final `results.json` write failed with a
   sandbox write denial (EPERM, 2026-11-17 19:51 IST) before the
   verdict was printed, written or observed by anyone. No trial
   was consumed by an observed execution; the coordinator
   authorised one re-execution of the byte-identical command
   because the deterministic verdict had never been observed, so
   no selection surface exists.
3. **Attempt 2 — transport stop, zero symbols loaded.** Three
   launches of the identical command each aborted on the first
   data fetch. Root cause proven by controlled probes: the
   sandbox egress path truncates response bodies for
   browser-User-Agent requests, and the pinned loader
   (`data_feed.py`, hash-verified programme code) sends
   `User-Agent: Mozilla/5.0`. The same URL fetched with a
   non-browser agent arrived complete. An environment condition,
   not a data or code defect; the loader was not patched — a
   changed loader would be a new, undeclared instrument.
4. **Observed run — pre-staged panel, zero fetches.** The panel
   was pre-staged into the runner's panel directory from
   hash-verified local caches only: every staged CSV's SHA-256
   equals the frozen provenance manifest for all 30 symbols, so
   the loader served every symbol from its cache branch and made
   zero network fetches. The declared command ran byte-identical
   (`--trial-floor 3893`), completed in ~215 s with exit code 0,
   and wrote `results.json` + `RESULTS.md`. That execution is
   trial **3,893**, and its verdict is the verdict recorded here.

## Run record

- Harness (frozen at run-prep, pins re-verified byte-identical
  before the observed run): `ema511.py` SHA-256
  `f1ae7f78c2305ce7747b4b7e82c39d06caf85feb32f3b151f5e5c23c80843f61`;
  `run_ema511.py` SHA-256
  `a7aa2a1683b8614d597668ce6d14ff6a3b031c4f61b76d47e7348ed31ca28e6d`;
  `test_ema511.py` SHA-256
  `a6c2e14b38342f4f5039818b9578000e886bf31a217a9d08e9ab5ca319a30244`
  (synthetic mechanics tests 21/21 PASS). Judgement via the
  programme's own `rd.common.check_bar` / `holdout_check`, folds
  W1..W5, entry-time attribution.
- Panel: crypto30 (30 Binance USDT-M symbols), 15-minute bars,
  Binance Vision monthly klines via the programme's verified
  loader (`data_feed.load_dataset`), months 2023-10..2026-10,
  **108,192 bars per symbol, zero missing bars**. The results
  record's panel block matches the frozen provenance manifest
  (`panel_provenance.json` SHA-256
  `1eeea5cdad831cc0338c41f4cb7aaf684cf9d80fecbd6fa19f645652bb464517`)
  on rows / missing bars / csv_sha256 for all 30 symbols.
- Rules as declared: completed EMA(5)/EMA(11) crossover on bar
  *i* enters at bar *i*'s close; stop at the trigger candle's
  extreme (long: low, short: high, zero buffer); target =
  entry ± 3.0 × initial risk; stop moves to breakeven when price
  reaches +1.5R (applies from the next bar); one position at a
  time per symbol; opposite crossovers do not close a position.
- Trial accounting: entering N = **3,892** (programme counter
  after the SRS declared run, trial 3,892) → this run is trial
  **3,893**; Bonferroni α = 0.05 / 3893 =
  1.2843565373747753e-05. Programme counter after this run:
  **3,893**.

### Headline numbers (pooled OOS, W1–W5)

| Basis | OOS trades | Win rate | Expectancy_net | PF_net |
|---|---|---|---|---|
| Programme costs (16 bps RT) | 150079 | 0.19367133309790177 | **-0.0016642525839553953** | **0.642959470251625** |
| 2× shadow (32 bps RT) | 150079 | 0.18406972327907303 | **-0.0032640243120639167** | **0.4521808752418005** |

### Per-fold (programme costs, 16 bps)

| Fold | OOS window | Trades | Expectancy_net | PF_net |
|---|---|---|---|---|
| W1 | 2024-07-01 → 2025-01-01 | 33681 | -0.001559742004072416 | 0.6885330590769247 |
| W2 | 2025-01-01 → 2025-07-01 | 31640 | -0.00135152950263472 | 0.7241471639866977 |
| W3 | 2025-07-01 → 2026-01-01 | 32368 | -0.0017947891343041698 | 0.6056106400278426 |
| W4 | 2026-01-01 → 2026-07-01 | 31774 | -0.0019088825139699438 | 0.5721687835785361 |
| W5 | 2026-07-01 → 2026-11-01 | 20616 | -0.00173296138663552 | 0.5884105968929758 |

Fold trade counts sum exactly to the pooled 150,079. **0 of 5
folds have positive expectancy** at either cost level (bar:
≥ 4 of 5).

### Bar checks (both cost levels, identical outcomes)

| Check | Result |
|---|---|
| expectancy_net > 0 | FALSE |
| profit_factor_net ≥ 1.2 | FALSE |
| ≥ 200 OOS trades | TRUE (150,079) |
| ≥ 4/5 positive folds | FALSE (0/5) |
| holdout (`rd.common.holdout_check`) | FALSE |
| Bonferroni (p < α) | FALSE — p = 1.0 at both levels (t = -55.415912588473084 at 16 bps; t = -108.69395220354788 at 32 bps) vs α = 1.2843565373747753e-05 |

Not an insufficiency verdict — the sample is ample (150,079 OOS
trades); the strategy loses at both cost levels, in every fold,
on every symbol judged.

## Runner output (verbatim)

The observed run's own `RESULTS.md`, reproduced exactly:

```
# RESULTS — TASK-IG2-STR-19 declared run

**Verdict: FAIL — the family closes, per the declaration**

Declaration SHA-256 re-verified: 671a1426555c1c969e7364cf6de009a39a485e613b5c8f0bcbb8e335db635b2e
Trial floor stated: N = 3893 (Bonferroni alpha = 0.05/N)

## costs_16bps

OOS trades: 150079, expectancy_net: -0.0016642525839553953, PF_net: 0.642959470251625

Checks: {"expectancy_net_gt_0": false, "profit_factor_net_gte_1.2": false, "min_oos_trades_200": true, "positive_folds_gte_4_of_5": false, "holdout": false, "bonferroni": false}

## costs_32bps_shadow

OOS trades: 150079, expectancy_net: -0.0032640243120639167, PF_net: 0.4521808752418005

Checks: {"expectancy_net_gt_0": false, "profit_factor_net_gte_1.2": false, "min_oos_trades_200": true, "positive_folds_gte_4_of_5": false, "holdout": false, "bonferroni": false}
```

## Consequence

FAIL ⇒ **not** eligible for forward demo under the Phase-3
protocol. Per the declaration the EMA 5/11 crossover bracket
family is closed: no variant, re-run or second exit rule is
authorised under this declaration; any revival requires a new
declaration and a new trial. Nothing here authorises live
trading.
