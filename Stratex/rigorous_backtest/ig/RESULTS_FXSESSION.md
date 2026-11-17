# RESULTS — FX Asia-Range Fade (fxsession, RD-018), TASK-STR-RD-018: declared backtest RUN

**VERDICT: FAIL — DELETE (OOS PF < 1.2). The family is CLOSED
per the declaration and the owner's removal rule.**

Run executed under the frozen declaration
`fxsession_declaration.json`, SHA-256
`0b4c10b085a5eebfd57a346c91285f6214133044f4c725498ea12a2e2cb01aa5`
(re-verified by the runner itself against
`--expected-declaration-sha256` before any simulation).
This file is the run record; the machine record shipped beside it
is `fxsession_results.json` — a byte-identical copy of the run's
`results.json` (SHA-256
`5f0e496afc4b667cb19e4705a0a7307af00c3a4e67be50fb72ca928685a9c340`).

## The chain

1. **Declaration first.** The family was pre-declared (PR #896,
   merged 80981700) before any backtest of it had run: one frozen
   cell — the Asian-range **fade** (Variant B). The breakout
   variant was dropped before declaration as already judged
   (RD-003 `london_drive`, RD-016, RD-002 `session_breakout`).
   Rules as declared: Asian range over [00:00, 06:00) UTC frozen
   at 06:00 UTC; fade window [06:00, 10:00) UTC; the first bar
   touching a range extreme fades it (a bar touching both
   extremes voids the day); entry at the next bar's open; stop =
   extreme ± 0.5 × range width; target = range midpoint; time
   exit at the open of the 10:00 UTC bar; at most one trade per
   instrument per UTC date; costs 6 bps round trip (programme
   FX-major model), 2× shadow 12 bps.
2. **Panel.** EURUSD, GBPUSD, USDJPY, AUDUSD — M15 mid-price
   candles from the OANDA practice API (the forward venue
   itself), span [2023-01-01Z, 2026-11-01Z), staged on S1 at
   `/var/tmp/rd018/panel/` with the frozen fetch script;
   provenance fetched_at 2026-11-17T14:57:10Z:

   | file | rows | SHA-256 |
   |---|---|---|
   | EURUSD.csv | 95,418 | e43b551a2aaa0d6613575b3edf86f3cbc75a7ce4807d7e32338b7530ed595afb |
   | GBPUSD.csv | 95,417 | 7fa0aff3fc6bfd81b90ce21120a8c0719f49823fb1abc9dd75bae176d9d7f718 |
   | USDJPY.csv | 95,420 | 31d24f9edc810928a200e69dcfbbdd1444a30619b32ed98bbecb626a63e1a188 |
   | AUDUSD.csv | 95,419 | 987c498c86b5b80c95dc426bc547fa4388f955f60caf019b455b980fd3e49feb |

   First bar (all): 2023-01-01T23:00:00Z; last bar (all):
   2026-10-30T20:45:00Z — 381,674 bars in total. Independent
   verification at prep: 0 incomplete bars, 0 OHLC violations, 0
   misaligned/duplicate/non-monotonic timestamps; gaps are market
   closures only.
3. **Gates re-verified fresh immediately before the run**
   (2026-11-17 ~21:20–21:35 IST, run crew): (1) all six package
   files on current origin/main (2ba83d5c) byte-identical to the
   freeze set, declaration sha256 == frozen value; (2) S1 panel
   hashes == prep record, S1 runner copies == freeze set;
   (3) venv312 = Python 3.12.16 on S1 and `load_panel()` parsed
   all 381,674 bars (LOAD_PANEL_OK); (4) programme trial counter
   read fresh from S-RD1's recorded results = **3,893** (includes
   S-RD1's trial), so `--programme-trials 3893`, N_run = 3,894.
4. **The one declared run.** Launched detached on S1 under the
   frozen command (below). Two earlier launch calls were dropped
   by the bridge in transport and each was proven by polling —
   no log, no process, no results — never to have landed; the
   third launch fired the single run (PID 3123750, the exact
   frozen command line). Exit code 0; results written
   2026-11-17 21:52 IST, log complete 21:55 IST (~45 min wall on
   the loaded host). Exactly one runner process ever existed.
   The run's `run.log` and `results.json` were retrieved from S1
   twice over and the local copies are byte-identical to S1's
   (SHA-256 above; run.log
   `5f64fb4b6526ce49068744adaa09c8ffdeaa008edce5fa73b12d676ad3d89a12`).

## Run record

- Harness (frozen; SHA-256 pins re-verified byte-identical at
  prep, at gate re-check, and fresh by the run crew):
  `FXSESSION_DECLARATION.md`
  `c7d9af1337fff4bdca387ca52dfe502dae0e128201cf374b162da145586f8813`;
  `fxsession_declaration.json`
  `0b4c10b085a5eebfd57a346c91285f6214133044f4c725498ea12a2e2cb01aa5`;
  `fxsession.py`
  `e0adcdd079bbcc468516aeae3d478dd8e1c61fbc16faeb56702664fc586853f2`;
  `run_fxsession.py`
  `717e5683334ee3209816fc409e0f94aae12038d4877e94a4965761cdba326170`;
  `fetch_fxsession_panel.py`
  `2eb16069d403a7b61dec4305e7b84e4557e31c877e74ddd92fb6e402d0fb2c5a`;
  `test_fxsession.py`
  `cedf5c830658edb4f9a3522f6261f32729aa367990832c484f7fa34548d52432`
  (synthetic mechanics tests 21/21 PASS at prep).
- Frozen command (venv312, S1):

  ```
  /opt/friday_universe/venv312/bin/python3 /var/tmp/rd018/runner/run_fxsession.py \
    --panel-dir /var/tmp/rd018/panel \
    --declaration /var/tmp/rd018/fxsession_declaration.json \
    --expected-declaration-sha256 0b4c10b085a5eebfd57a346c91285f6214133044f4c725498ea12a2e2cb01aa5 \
    --programme-trials 3893 \
    --declared-run \
    --out /var/tmp/rd018/results
  ```

- Trial accounting: entering programme counter **3,893** (after
  the S-RD1 declared run, trial 3,893) → this run is trial
  **3,894** (N_run = 3,894, the family's single cell);
  Bonferroni α = 0.05 / 3894 = 1.2840267077555214e-05.
  Programme counter after this run: **3,894**.
- Consistency (checked on the hash-verified results file): fold
  trades 431+428+466+436+290 = 2,051 == pooled; symbol trades
  549+548+481+473 = 2,051; dev 1,761 + holdout 290 = 2,051;
  fold total_net sums to pooled total_net; α == 0.05/3894
  exactly.

### Headline numbers (pooled OOS, W1–W5)

| Basis | OOS trades | Win rate | Expectancy_net | PF_net | Total_net |
|---|---|---|---|---|---|
| Declared costs (6 bps RT) | 2051 | 0.3515358361774744 | **-0.000534063545975932** | **0.34332165002683773** | -1.0953643327966365 |
| 2× shadow (12 bps RT) | 2051 | 0.16040955631399317 | **-0.0011341038538951744** | **0.10381164522546686** | -2.326047004339003 |

### Per-fold (declared costs, 6 bps)

| Fold | OOS window | Trades | Expectancy_net | PF_net | Total_net | Win rate |
|---|---|---|---|---|---|---|
| W1 | 2024-07-01 → 2025-01-01 | 431 | -0.0005406441122736308 | 0.3543183262119973 | -0.23301761238993485 | 0.3109048723897912 |
| W2 | 2025-01-01 → 2025-07-01 | 428 | -0.0005245693927632475 | 0.4451821768792159 | -0.22451570010266994 | 0.4205607476635514 |
| W3 | 2025-07-01 → 2026-01-01 | 466 | -0.0005101670171045006 | 0.32157581284005865 | -0.23773782997069728 | 0.38197424892703863 |
| W4 | 2026-01-01 → 2026-07-01 | 436 | -0.0004344050915990478 | 0.38259209807235633 | -0.18940061993718485 | 0.3623853211009174 |
| W5 | 2026-07-01 → 2026-11-01 | 290 | -0.000726526104814309 | 0.14105429841685735 | -0.21069257039614964 | 0.24482758620689654 |

Fold trade counts sum exactly to the pooled 2,051. **0 of 5
folds have positive expectancy** (bar: ≥ 4 of 5).

### Per-symbol (pooled OOS, declared costs)

| Symbol | Trades | Expectancy_net | PF_net | Total_net | Win rate |
|---|---|---|---|---|---|
| EURUSD | 549 | -0.0005294528414438314 | 0.2609450801036989 | -0.29066960995266344 | 0.30601092896174864 |
| GBPUSD | 548 | -0.0005265573969105299 | 0.24803389498361436 | -0.28855345350697037 | 0.3722627737226277 |
| USDJPY | 481 | -0.0005464190457988107 | 0.4130407169982182 | -0.26282756102922794 | 0.3471933471933472 |
| AUDUSD | 473 | -0.000535546952024894 | 0.42848066741317636 | -0.25331370830777483 | 0.38477801268498946 |

**All four symbols have negative expectancy** — breadth FAIL
(no symbol with positive expectancy at ≥ 20 trades; max symbol
profit share 1.0).

### Temporal holdout v1 (H = W5, D = W1–W4)

| Element | Result |
|---|---|
| H1 — holdout trades ≥ 20 | PASS (290) |
| H2 — holdout expectancy > 0 | FAIL (-0.000726526104814309) |
| H3 — dev-OOS expectancy > 0 | FAIL (1,761 trades, expectancy -0.0005023689735380391, PF 0.37819406290082325) |
| H4 — max fold profit share ≤ 0.80 | FAIL (1.0) |
| H5 — burn clause | ATTESTED_BY_RUN_PROTOCOL (`--declared-run`) |

Holdout verdict: **FAIL**.

### Bar checks

| Check | Result |
|---|---|
| pooled expectancy_net > 0 | FALSE |
| pooled PF_net ≥ 1.2 | FALSE (0.34332165002683773) |
| ≥ 200 OOS trades | TRUE (2,051) |
| ≥ 4/5 positive folds | FALSE (0/5) |
| 2×-cost shadow (expectancy > 0 and PF ≥ 1.2) | FALSE |
| Bonferroni (p < α) | FALSE — p = 1.0 vs α = 1.2840267077555214e-05 |
| temporal holdout v1 | FALSE |
| breadth | FALSE |

Not an insufficiency verdict — the sample is ample (2,051 OOS
trades); the strategy loses at both cost levels, in every fold,
on every symbol.

## Runner output (verbatim)

The run's own stdout (`run.log` on S1, SHA-256
`5f64fb4b6526ce49068744adaa09c8ffdeaa008edce5fa73b12d676ad3d89a12`),
reproduced exactly:

```
{
  "task_id": "TASK-STR-RD-018",
  "declaration_sha256": "0b4c10b085a5eebfd57a346c91285f6214133044f4c725498ea12a2e2cb01aa5",
  "n_run": 3894,
  "bonferroni_alpha": 1.2840267077555214e-05,
  "bonferroni_p_value": 1.0,
  "pooled_oos": {
    "trades": 2051,
    "expectancy_net": -0.000534063545975932,
    "profit_factor_net": 0.34332165002683773,
    "total_net": -1.0953643327966365,
    "win_rate": 0.3515358361774744
  },
  "pooled_oos_2x_costs": {
    "trades": 2051,
    "expectancy_net": -0.0011341038538951744,
    "profit_factor_net": 0.10381164522546686,
    "total_net": -2.326047004339003,
    "win_rate": 0.16040955631399317
  },
  "per_fold": {
    "W1": {
      "trades": 431,
      "expectancy_net": -0.0005406441122736308,
      "profit_factor_net": 0.3543183262119973,
      "total_net": -0.23301761238993485,
      "win_rate": 0.3109048723897912
    },
    "W2": {
      "trades": 428,
      "expectancy_net": -0.0005245693927632475,
      "profit_factor_net": 0.4451821768792159,
      "total_net": -0.22451570010266994,
      "win_rate": 0.4205607476635514
    },
    "W3": {
      "trades": 466,
      "expectancy_net": -0.0005101670171045006,
      "profit_factor_net": 0.32157581284005865,
      "total_net": -0.23773782997069728,
      "win_rate": 0.38197424892703863
    },
    "W4": {
      "trades": 436,
      "expectancy_net": -0.0004344050915990478,
      "profit_factor_net": 0.38259209807235633,
      "total_net": -0.18940061993718485,
      "win_rate": 0.3623853211009174
    },
    "W5": {
      "trades": 290,
      "expectancy_net": -0.000726526104814309,
      "profit_factor_net": 0.14105429841685735,
      "total_net": -0.21069257039614964,
      "win_rate": 0.24482758620689654
    }
  },
  "per_symbol_oos": {
    "EURUSD": {
      "trades": 549,
      "expectancy_net": -0.0005294528414438314,
      "profit_factor_net": 0.2609450801036989,
      "total_net": -0.29066960995266344,
      "win_rate": 0.30601092896174864
    },
    "GBPUSD": {
      "trades": 548,
      "expectancy_net": -0.0005265573969105299,
      "profit_factor_net": 0.24803389498361436,
      "total_net": -0.28855345350697037,
      "win_rate": 0.3722627737226277
    },
    "USDJPY": {
      "trades": 481,
      "expectancy_net": -0.0005464190457988107,
      "profit_factor_net": 0.4130407169982182,
      "total_net": -0.26282756102922794,
      "win_rate": 0.3471933471933472
    },
    "AUDUSD": {
      "trades": 473,
      "expectancy_net": -0.000535546952024894,
      "profit_factor_net": 0.42848066741317636,
      "total_net": -0.25331370830777483,
      "win_rate": 0.38477801268498946
    }
  },
  "positive_folds": 0,
  "temporal_holdout": {
    "H1_holdout_trades_gte_20": true,
    "H2_holdout_expectancy_gt_0": false,
    "H3_dev_oos_expectancy_gt_0": false,
    "H4_fold_concentration_lte_0.80": false,
    "H5_burn_clause": "ATTESTED_BY_RUN_PROTOCOL (--declared-run)",
    "holdout_metrics": {
      "trades": 290,
      "expectancy_net": -0.000726526104814309,
      "profit_factor_net": 0.14105429841685735,
      "total_net": -0.21069257039614964,
      "win_rate": 0.24482758620689654
    },
    "dev_oos_metrics": {
      "trades": 1761,
      "expectancy_net": -0.0005023689735380391,
      "profit_factor_net": 0.37819406290082325,
      "total_net": -0.884671762400487,
      "win_rate": 0.3691084611016468
    },
    "max_fold_profit_share": 1.0
  },
  "breadth": {
    "positive_symbols_min20": [],
    "max_symbol_profit_share": 1.0,
    "passes": false
  },
  "checks": {
    "pooled_expectancy_gt_0": false,
    "pooled_pf_gte_1.2_finite": false,
    "min_oos_trades_200": true,
    "positive_folds_gte_4_of_5": false,
    "cost_shadow_2x": false,
    "bonferroni": false,
    "temporal_holdout_v1": false,
    "breadth": false
  },
  "verdict": "FAIL",
  "delete_per_owner_rule": true
}

VERDICT: FAIL — DELETE (OOS PF < 1.2)
```

## Consequence

FAIL with pooled OOS PF_net 0.34332165002683773 < 1.2 (strict)
⇒ under the declaration and the owner's removal rule the
fxsession / FX Asia-Range Fade family **FAILS and is deleted
completely** (`delete_per_owner_rule = true` in the machine
record). It is **not** eligible for forward demo under the
Phase-3 protocol. No variant, re-run or second cell is
authorised under this declaration; any revival requires a new
declaration and a new trial. Nothing here authorises live
trading.
