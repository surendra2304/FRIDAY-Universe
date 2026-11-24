# TASK-FUT-024 — Futuris: running 30-day forecast-accuracy table

- Task: TASK-FUT-024 (P2, owner muse_15)
- Branch: `muse15/task-fut-024-forecast-accuracy-table`, from main `3e8a4a1`
- Claim: issue #1483 comment 7103422260 (2026-11-23 ~19:40 IST), on assignment
  in coordinator watch 7103106790 (queue FUT-024 -> VYR-043 -> EARN-002)
- Snapshot: probed 2026-11-23 19:35–19:40 IST (14:05–14:10 UTC) from the live
  Futuris store on Oracle Server 2. Calibration report generated
  2026-11-23T14:10:02Z. All numbers below are that snapshot unless stated.

## 1. Headline — rolling 30-day accuracy

- **Rolling 30-day hit-rate: 0.89295 over 383 scored forecasts**, all
  in-window; window 2026-10-24T13:15:41Z → 2026-11-23T13:15:41Z; status
  `measured` (min_samples 30 met). Computed by the service's own
  `build_rolling_hit_rate` from the store.
- Overall (n=383): MAE 968.49, RMSE 1115.14, mean pct error 54.60%,
  mean interval width 8874.55. Verdict **underconfident**: coverage at
  the dominant nominal level (0.80) is 1.0, gap +0.2 — intervals cover
  more than promised, i.e. too wide.
- By nominal level: 0.80 → n=235, coverage 1.0 (gap +0.2); 0.90 →
  n=148, coverage 0.723 (gap −0.177, overconfident at 90%). The single
  headline hit-rate blends both levels; cite this split alongside it.
- By evidence class: live n=41 (all `friday:fleet`), coverage_90 0.0,
  MAE 2101.07; synthetic n=342, coverage_80 1.0, MAE 832.71.

## 2. The 30-day table (forecast vs outcome, by scored day, UTC)

| scored day (UTC) | n scored | hits | hit-rate | mean prediction | mean observed | MAE | mean interval width |
|---|---|---|---|---|---|---|---|
| 2026-11-20 | 70 | 70 | 1.0000 | 1189.28 | 900.83 | 355.56 | 10359.45 |
| 2026-11-21 | 39 | 35 | 0.8974 | 961.28 | 2009.79 | 1173.82 | 10533.42 |
| 2026-11-22 | 149 | 126 | 0.8456 | 922.82 | 1861.48 | 1125.41 | 8527.95 |
| 2026-11-23 | 125 | 111 | 0.8880 | 1293.96 | 2354.58 | 1060.63 | 7938.57 |
| **Total** | **383** | **342** | **0.89295** | — | — | — | — |

- Scores exist only for 2026-11-20–23. The other 26 days in the 30-day
  window (2026-10-24–2026-11-19) have **zero** scored forecasts: the
  store's oldest row is 2026-11-20 19:45 UTC (the FUT-006 backfill
  start). The table grows a day at a time as scoring continues; a
  re-pull after a few more weeks will show a fuller window.
- Cross-checks: day sums (383) = per-target sums (383) =
  `count_scores()` (383); hits 342/383 = 0.89295, matching the
  tracker's own `build_rolling_hit_rate`; the 19:15 journal run also
  reports n=383. Overall MAE/RMSE in §1 come from the canonical
  `calibration_report`, not from the rounded daily means above.

## 3. Per-target breakdown

| target | evidence | n | hits | hit-rate | MAE | coverage (at target's dominant level) |
|---|---|---|---|---|---|---|
| BTCUSDT | synthetic | 2 | 2 | 1.0 | 406.93 | 1.0 @ 0.80 |
| ETHUSDT | synthetic | 1 | 1 | 1.0 | 418.47 | 1.0 @ 0.80 |
| NIFTY | synthetic | 2 | 2 | 1.0 | 408.64 | 1.0 @ 0.80 |
| fleet:api:request_rate | synthetic | 1 | 1 | 1.0 | 299.31 | 1.0 @ 0.80 |
| friday:fleet:forecast_demand_24h | live | 41 | 0 | 0.0 | 2101.07 | 0.0 @ 0.90 |
| macro:DGS10:yield_shift_30d | synthetic | 36 | 36 | 1.0 | 895.21 | 1.0 @ 0.80 |
| macro:SPY:return_exceedance_24h | synthetic | 41 | 41 | 1.0 | 843.42 | 1.0 @ 0.80 |
| macro:T10Y2Y:curve_inversion_30d | synthetic | 36 | 36 | 1.0 | 895.21 | 1.0 @ 0.80 |
| macro:UNRATE:unemployment_drift_90d | synthetic | 36 | 36 | 1.0 | 895.21 | 1.0 @ 0.80 |
| my portfolio | synthetic | 4 | 4 | 1.0 | 1692.04 | 1.0 @ 0.80 |
| service:checkout:capacity_exceedance_24h | synthetic | 50 | 50 | 1.0 | 751.22 | 1.0 @ 0.80 |
| trading:BTCUSDT:price_variance_24h | synthetic | 44 | 44 | 1.0 | 798.13 | 1.0 @ 0.80 |
| trading:ETHUSDT:price_variance_24h | synthetic | 44 | 44 | 1.0 | 798.13 | 1.0 @ 0.80 |
| trading:SOLUSDT:price_variance_24h | synthetic | 44 | 44 | 1.0 | 798.13 | 1.0 @ 0.80 |
| what should i watch in indian markets | synthetic | 1 | 1 | 1.0 | 1493.77 | 1.0 @ 0.80 |

- The identical MAE/RMSE across DGS10/T10Y2Y/UNRATE (895.21) and across
  BTC/ETH/SOL (798.13) is the target-blind repetition showing up in the
  error metrics too (see §6.1). SPY (n=41) and service:checkout (n=50)
  differ because their row sets include extra batches.
- The five small-n targets (BTCUSDT, ETHUSDT, NIFTY,
  fleet:api:request_rate, "my portfolio", "what should i watch in
  indian markets") are ad-hoc/legacy rows, all synthetic, all hits.

## 4. Latest forecast-vs-outcome pairs (newest batch, scored 2026-11-23 13:15:34–41 UTC = 18:45 IST)

All 8 telemetry rows are identical (as_of 2026-11-22 12:42:24 UTC):
prediction 1810.61, interval [0.0, 10420.68], observed 2450.63, hit.

| target | prediction | interval | observed | hit |
|---|---|---|---|---|
| trading:BTCUSDT:price_variance_24h | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| trading:ETHUSDT:price_variance_24h | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| trading:SOLUSDT:price_variance_24h | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| macro:SPY:return_exceedance_24h | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| macro:DGS10:yield_shift_30d | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| macro:T10Y2Y:curve_inversion_30d | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| macro:UNRATE:unemployment_drift_90d | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| service:checkout:capacity_exceedance_24h | 1810.61 | [0.0, 10420.68] | 2450.63 | yes |
| friday:fleet:forecast_demand_24h (as_of 2026-11-22 12:42:30 UTC) | 181.0 | [141.22, 220.78] | 2450.63 | no |

- The fleet row's observed value (2450.63) is the same synthetic
  telemetry observation as the other eight — see §6.3.

## 5. Scoring method (filed)

- **Instrument.** FUT-006 tracker
  (`Futuris/futuris/services/forecast_tracker.py`, tracker version
  `fut006-forecast-tracker/1.0`) with FUT-017 standing per-cycle
  scoring: the lifecycle and calibration sweeps call
  `_score_matured_forecasts` at the end of the cycle that resolves
  matured forecasts, and the standalone 30-minute
  `forecast_scoring_job` remains as the backstop. One score row per
  resolved forecast in the `forecast_scores` table
  (`Futuris/futuris/storage/models.py`, `ForecastScoreModel`);
  `forecast_id` is unique, which makes the scoring sweep idempotent.
  Issuance fields (target, horizon, prediction, interval bounds,
  confidence, model, provenance) are snapshotted from the forecast at
  scoring time, so calibration aggregates never join back through
  mutable forecast state.
- **What gets scored.** Only resolved forecasts with a numeric
  `observed_value`. Event-only outcomes never produce a row (counted
  separately by `count_event_only_resolved`; 0 at this snapshot). A
  forecast with no outcome is absent, never assigned a substituted
  actual.
- **Per-forecast math** (`score_forecast`): signed_error = observed −
  prediction; abs_error = |signed_error|; pct_error =
  abs_error / |observed| × 100 (null when observed == 0); interval_hit
  = range_lower ≤ observed ≤ range_upper; interval_width = upper −
  lower; Winkler = width + (2/α) × overshoot when the actual falls
  outside the interval (α = 1 − level), else width.
- **Nominal level** (`derive_nominal_level`): recovered from the
  forecast's predictive-distribution percentile pair (p5/p95 → 0.90,
  p10/p90 → 0.80, p25/p75 → 0.50); otherwise the production adapters'
  documented default 0.90 (z = 1.645 in
  `BaseStatsForecastAdapter._build_prediction`). The source is
  persisted per row (`nominal_level_source`), so an assumed level is
  always labelled as assumed.
- **Rolling 30-day hit-rate** (`build_rolling_hit_rate`): the share of
  in-window scores with interval_hit. The window ends at the newest
  score row by default, so a report built from stored rows is
  reproducible. Below 30 in-window samples the status is
  `insufficient_data` with a null hit-rate — a thin window is reported
  as thin, never as a verdict.
- **Calibration report** (`build_calibration_report`): MAE / RMSE /
  mean interval width / mean pct error span the whole group; coverage
  and Winkler are computed over the group's dominant nominal level
  only (mixed levels would make a single coverage number
  meaningless). Verdict from the coverage gap against a ±0.05
  tolerance: gap < −0.05 overconfident (intervals too narrow), gap >
  +0.05 underconfident (intervals too wide), else calibrated.
- **Relation to FUT-004.** The offline walk-forward harness
  (`Futuris/docs/forecast_evaluation/BASELINE_SCORECARD.md`,
  2026-11-15) scores production adapters on provenanced series; its
  production path was `not_scorable` in the harness environment
  because statsforecast was not installed there. This table is the
  LIVE instrument (FUT-006/FUT-017) over stored forecasts — a
  different instrument, not a re-run of the harness. The live service
  does fit statsforecast models (ARIMA `SingularMatrixWarning` in the
  journal during the 17:15 cycle).
- **How to re-pull** (read-only; Server 2, the service's own venv —
  the shared `/opt/friday_universe/venv` lacks pandas and cannot
  import the tracker):

```text
cd /opt/friday_universe/Futuris
PYTHONPATH=/opt/friday_universe/Futuris /opt/friday_universe/venv312/bin/python - <<'EOF'
import asyncio, json
from futuris.storage.db import async_session_factory
from futuris.services.forecast_tracker import ForecastTracker
async def main():
    async with async_session_factory() as session:
        print(json.dumps(await ForecastTracker(session).calibration_report(), default=str))
asyncio.run(main())
EOF
```

  The daily table is `ForecastScoreRepository.list_scores()` grouped
  by `scored_at` (UTC date). Note the tracker CLI quirk found this
  run: `scripts/run_forecast_tracker.py --report-only` prints `{}`,
  because the report branch is gated on `args.score or not
  args.report_only` — use the direct call above instead.

## 6. Findings and caveats (read before citing the hit-rate)

1. **Synthetic + target-blind (re-verified this run).** Only 48
   distinct predictions and 59 distinct observed values across 383
   rows. All 8 telemetry targets share identical forecasts AND
   identical observed values: ingestion is target-blind
   (`BaseConnector.fetch` takes no target) and the live connector is
   the deterministic synthetic generator (seed 42; FUT-023 §3). The
   0.893 hit-rate measures one synthetic series' wide-interval
   coverage repeated 8×, not 8 independent targets' accuracy.
2. **Wide intervals.** Mean width 8874.55 overall (9930.71
   synthetic); telemetry intervals like [0.0, 10420.68] make hits
   near-guaranteed. Verdict: underconfident.
3. **The only LIVE target is 0/41 — and its outcomes are
   wrong-series values.** `friday:fleet` forecasts (predictions
   ~181–263, intervals ~65 wide) are resolved against the same
   synthetic telemetry observation frame as the telemetry targets
   (observed 2450.63 in the latest batch), not against fleet demand.
   Its 0.0 hit-rate measures the mismatch, not fleet forecast skill.
   Follow-up for the coordinator's pool: per-target outcome
   resolution (same family as FUT-023 follow-up (a)).
4. **Mixed nominal levels.** 235 rows at 0.80 (coverage 1.0) vs 148
   at 0.90 (coverage 0.723). The headline hit-rate blends both; the
   by-level split in §1 is part of the result.
5. **Store vs journal: they agree now (383 = 383).** The FUT-023
   17:45 "drain failed" finding is superseded in part — the 8 scores
   from the 17:45 run ARE in the store now (a row scored 17:45:37 is
   present), so they committed late, after FUT-023's 17:47 probes.
   But session contention persists: `forecast_scoring_job_failed`
   warnings at 17:15 ("This session is in 'prepared' state") and
   18:15 ("Session is already flushing"), and 7
   `calibration_resolve_failed` warnings at 19:15:38 ("Session is
   already flushing"). The journal's `n_scored_total` is in-memory
   arithmetic — the store count is the ground truth.
6. **Unscored tail: 9.** Nine resolved forecasts (all 9 targets)
   await the next scoring pass (~19:45 IST). Fresh batch, not stale.
   Event-only resolved: 0.
7. **Thin history.** Scoring spans 2026-11-20–23 only (4 days); the
   30-day window is mostly empty (see §2).
8. **Telemetry gaps (carried from FUT-023, not re-verified here).**
   The 16:01 and 17:15 telemetry cycles produced zero stored
   forecasts (restart kill; silent zero). This task scored what is
   in the store; it did not re-verify cycle production.

## 7. Provenance

- Probed 2026-11-23 19:35–19:40 IST via the bridge (`run_shell`,
  Server 2): read-only SELECTs through the service's own repository
  layer. No writes, no restarts, no scoring runs triggered.
- Service: `Futuris.service` active, MainPID 609831 since 16:15:17
  IST. Server 2 disk checkout `muse10/task-obs-017-backup-manifest`
  @ `8bd2356d` (moved since FUT-023; the running process predates
  the move).
- Query env: `/opt/friday_universe/venv312/bin/python` (the
  service's venv) with `PYTHONPATH=/opt/friday_universe/Futuris`.
- Verification: day sums = target sums = `count_scores()` = 383;
  hits 342/383 = 0.89295 matches the tracker's own rolling hit-rate;
  journal 19:15 run reports n=383, matching the store.

## 8. Files changed

- `docs/collaboration/TASK-FUT-024-FORECAST-ACCURACY-TABLE.md` (this file)
- `docs/collaboration/WORK_BOARD.yaml` (FUT-024: CLAIMED → IN_REVIEW)

— Muse 15
