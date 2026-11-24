# TASK-STR-047 — Scope: wire the 7 RD-025 PROVEN ensembles to demo trading

**Checkpoint 1 — scope (read-only; no live change, no S1 write).**
Branch `muse8/task-str-047`. Base: main `90ad8c3e` (verified first-hand
2026-11-24 ~16:40 IST). Scope check: `Stratex/tests/test_str047_scope_admission.py`
(30 tests, green locally against main; CI verdict owed on the work PR).

## The 7 books

RD-025 trials 3905, 3906, 3927, 3928, 3929, 3933, 3978. Canonical
definitions: `Stratex/strategies/ensemble_books.py` (BOOKS); registry:
`Stratex/config_strategy.py` PRODUCTION_STRATEGY_REGISTRY; daemon-facing
modules: `Stratex/strategy_ensemble_book_39xx.py`. Book 3900 (loop
first-light, source LOOP) is explicitly OUT of scope — it is not an
RD-025 book and records no Bonferroni/holdout pass.

| Book | Members | Trades | Expect. | PF | Win | Folds | max_stop_pct |
|------|---------|--------|---------|----|-----|-------|--------------|
| 3905 | SHK k1.5 + DON n55_b26 (crypto30 1d) | 784 | +1.9383% | 1.4548 | 0.3839 | 4/5 | 0.50 |
| 3906 | SHK k1.5 + TSM roc72 (crypto30 1d) | 820 | +1.7244% | 1.4333 | 0.4122 | 4/5 | 0.50 |
| 3927 | VA ema12_26 + SHK k1.5 + STO k14_raw fx28 | 1150 | +0.9665% | 1.4639 | 0.4096 | 4/5 | 0.60 |
| 3928 | DON + SHK k1.5 + STO k14_raw fx28 | 1149 | +0.9120% | 1.4440 | 0.3847 | 4/5 | 0.50 |
| 3929 | TSM + SHK k1.5 + STO k14_raw fx28 | 1185 | +0.8249% | 1.4235 | 0.4042 | 4/5 | 0.50 |
| 3933 | VA + SHK k1.5 + XSL lv20_r10 | 1295 | +0.9253% | 1.4072 | 0.4672 | 4/5 | 0.60 |
| 3978 | DUAL roc90 + SHW k1.0 1w + ZSC w50 + HA1d + XSL | 1698 | +0.4728% | 1.3262 | 0.4441 | 4/5 | 0.90 |

## Admission check vs the frozen PROVEN bar

Bar (`Stratex/self_experiments/bounds.py`): expectancy > 0, PF >= 1.2,
>= 200 OOS trades, >= 4/5 positive folds, Bonferroni one-sided
p < 0.05 / N_global, pooled holdout expectancy > 0.

- **Checkable legs — all 7 PASS** on the recorded figures (lowest PF
  1.3262, lowest trades 784, all 4/5 folds, all expectancy > 0).
- **Statistical legs — RECORDED, not recomputed here.** Every book's
  registry `reason` text states "Bonferroni pass at round N=3,979,
  holdout pass". The full RD-002 trade lists do not ship in the repo,
  so the p-value/holdout legs are carried from the RD-025 verdict
  (same boundary as `test_exp002_ensemble_book.py` §8).
- **Registry — all 7 admitted as FORWARD_TEST entries:** status
  FORWARD_TEST, `forward_protocol` True, `forward_lane` FORWARD_TEST,
  `lane_assets` set (CRYPTO30), risk 0.1% per trade / 2% heat cap,
  `max_stop_pct` overrides stamped (0.50 / 0.60 / 0.90), figures agree
  with the BOOKS dict. Pinned by the scope test.
- **Member modules — all 12 present on main `90ad8c3e`** (verified via
  the git tree, then by the test's `find_spec`): vol_adaptive_trend,
  donchian_turtle, ts_momentum, shock_breakout_k15, shock_breakout,
  stoch_reversion, stoch_reversion_crypto, tsmom2_dual_crypto_1d,
  shock_breakout_1wk, zscore_reversion, ha_trend, xs_lowvol.

## Findings (scope-level, not blockers unless stated)

1. **Stale "PENDING_WAVE_PR_MERGE" stamps.** `ensemble_books.py`,
   the book-module docstrings, and the registry `execution` fields
   still say 3905/3906/3927/3928/3929 wait on wave-2 PRs #983 / #987 /
   #991 / #994 / #996 — but all five PRs have landed: every member
   module is on main. The stamps are stale and need a doc-only
   correction (follow-up in the wiring leg, not this checkpoint).
2. **Title correction.** The task title says every book "contains
   shock_breakout k1.5". Six do. **3978's shock leg is k1.0 @ 1w**
   (`strategy_shock_breakout_1wk`), not k1.5. Pinned by the scope test.
3. **3978 "1wk" vs "1w" — already resolved.** `run_daemon.py`
   (TASK-STR-FWD-035) normalizes the legacy `1wk` label to `1w`
   (`_LEGACY_TIMEFRAME_LABELS`); the book's venue label `1w` matches.
   Verified in code on main; no fix owed.
4. **xs legs abstain safely.** 3933/3978's xs_lowvol leg resolves via
   persisted panel membership (`panel_signal_service.py`); with no
   membership persisted yet it abstains and the book nets the members
   that did signal. Not a blocker — but the first panel ranking must
   have run on S1 before the xs legs can contribute.
5. **Stop-cap overrides are stamped, not yet proven applied.** The
   registry carries per-book `max_stop_pct` (0.50/0.60/0.90) against
   the 0.15 env cap. The wiring leg must verify the daemon actually
   applies the per-book override at runtime (FWD-012 method) on the
   live copy before first fills.

## Remaining gates to live demo trading (wiring leg)

1. **S1 `STRATEX_STRATEGY_ALLOWLIST` append** for the 7 book modules
   (`strategy_ensemble_book_3905/3906/3927/3928/3929/3933/3978`) —
   deploy step on the live copy. **Needs coordinator clearance first;
   no live change in this checkpoint.**
2. Per-book `max_stop_pct` runtime application — verify on the live
   copy (finding 5).
3. Panel ranking run on S1 so the xs legs can contribute (finding 4);
   first-scan evidence (fills, or no-fill with reasons) filed after.
4. Stale-stamp correction (finding 1) + title correction (finding 2)
   recorded for the board / coordinator.

## Out of scope

- Book 3900 (LOOP first-light). Live trading of any kind (demo only
  per standing rule; this task wires demo). Any change to the frozen
  bars, lane terms, or judged figures.
