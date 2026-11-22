# TASK-FUT-016 — Futuris forecast quality: last 3 scheduler cycles + scoring pass

**Owner:** Muse 7 · **Date:** 2026-11-22 · **Service:** Futuris on Server 2 (main; Server 1 unit masked/inactive, expected) · **Branch:** `muse7/task-fut-016-forecast-quality` · **Status:** implemented, in review (work PR owed — see board flip in this PR)

## Verdict (one paragraph)

The last three hourly cycles ran and reported success, but they did not produce
real per-target forecasts. All eight subscriptions in every cycle carry
byte-identical content — one deterministic synthetic series stamped onto eight
target labels — because the live service runs with
`FUTURIS_TELEMETRY_SOURCE=synthetic`. And the newest cycle (17:12 IST) emitted
its eight `forecast_updated` events while its eight rows were never durably
stored: the scheduler never commits its own writes, so each cycle's rows become
visible only when the *next* hour's universe refresh commits the shared
session. Separately, the only live-evidence forecasts (fleet demand, n=16
scored) are systematically wrong — prediction ~112–181 against actuals
~1940–2192, 90% intervals ~49 wide, coverage 0.0. The aggregate "overconfident"
verdict is therefore not a calibration story: it is 137 synthetic scores
(coverage 1.0, intervals ~10,435 wide) averaged with 16 live scores that never
hit.

## 1. Last 3 cycles — execution (all success, all 8 events)

Futuris.service on Server 2: active/running, pid 577689 since 2026-11-21 20:12 IST
(verified 17:28 IST via `systemctl show`). Journal
(`journalctl -u Futuris.service`, Server 2):

| Cycle (IST) | Started → completed | `forecast_updated` events | Job result |
|---|---|---|---|
| 15:12:23 → 15:23:22 | 8 | `executed successfully` |
| 16:12:23 → 16:27:20 | 8 | `executed successfully` |
| 17:12:23 → 17:26:21 | 8 | `executed successfully` |

No `ERROR` lines in the window 14:00–17:27 IST. The three cycles are the
subscription job `ForecastScheduler.forecast_refresh_job`
(`Futuris/futuris/infra/scheduler.py:168`), hourly, 8 subscriptions
(`scheduler.py:97-105`): 1 service, 3 trading, 4 macro, all horizon 24h
(except DGS10/T10Y2Y 30d, UNRATE 90d per the subscription table).

## 2. Cycle contents — the 24 forecast ids (16 found, 8 missing)

Forecast ids taken verbatim from the journal `domain_event_emitted` lines
(8 per cycle), then read back from the `forecasts` table through
`futuris.storage.db.async_session_factory` (same store the service uses):

| Cycle | Found in `forecasts` | Prediction | Probability | Range | `as_of` (UTC) |
|---|---|---|---|---|---|
| 15:12 | 8 / 8 | 1283.82 (all 8) | 0.023 (all 8) | [0.0, 9775.64] (all 8) | 09:42:24.080468 |
| 16:12 | 8 / 8 | 1297.92 (all 8) | 0.025 (all 8) | [0.0, 9993.27] (all 8) | 10:42:24.089080 |
| 17:12 | **0 / 8** | — (rows absent) | — | — | — |

All 16 stored rows: `model_version seasonal_naive@v1:bb63b87d1a90360b`,
`confidence low`, `status active`, 10 intervals, predictive distribution
`p10/p25/p50/p75/p90 + exceedance_probability`, and — honestly labelled —
`evidence_class synthetic`,
`evidence_source "telemetry:synthetic via SyntheticTelemetryConnector [SYNTHETIC data]"`.

**The 8 targets in one cycle are byte-identical except for the target label.**
Same `as_of` to the microsecond, same prediction, probability, range,
distribution, model version. A BTC price-variance forecast, a SPY return
forecast and a UNRATE unemployment-drift forecast cannot honestly share one
number; these are not eight forecasts, they are one series written eight
times. The 14:12 cycle shows the same pattern (4 macro rows read back,
prediction 2011.55 on all four, `as_of` 08:42:24.059355Z).

### Root cause — target-blind synthetic telemetry (file/line)

- Live setting: `FUTURIS_TELEMETRY_SOURCE=synthetic` (read from the running
  service config on Server 2).
- `Futuris/futuris/connectors/factory.py:26-28` (`build_scheduler_connector`):
  anything other than `"nexus"`/`"vyralx"` returns
  `SyntheticTelemetryConnector(seed=42)`.
- `Futuris/futuris/connectors/synthetic_telemetry.py`: `fetch(start, end)`
  takes **no target**; `generate_series` builds one deterministic series
  (seed 42, `base_demand` 1200.0, daily seasonality amplitude 800, weekly 400,
  noise 45) for any caller.
- `Futuris/futuris/core/pipeline.py:453-476` (`ForecastingPipeline.run`)
  passes `target` into `IngestionStage`, but the connector underneath ignores
  it, so the modelling stage fits the same series eight times.

Consequence for the tracker: the seven subscription targets that share the
series also share identical score pairs. Verified on `forecast_scores`: the
same (prediction, observed) pairs — e.g. (662.31, 406.8), (875.04, 1980.66),
(875.07, 2015.73) — appear under all of `macro:DGS10`, `macro:SPY`,
`macro:T10Y2Y`, `macro:UNRATE`, `trading:BTCUSDT`, `trading:ETHUSDT`,
`trading:SOLUSDT` (15 scored rows each, 15 distinct pairs each, identical
sets). The per-target tracker tables are one series scored seven times, not
seven independent evidence streams.

## 3. The 17:12 miss — rows flushed, never committed (file/line)

The 17:12 cycle's eight ids (mechanically re-extracted from the journal, no
hand transcription) are absent from `forecasts` — re-checked 17:52 IST, ~26
minutes after the job reported success. No error, rollback or recovery line
appears in the journal 17:12–17:27 IST.

Root cause — the scheduler never commits its own writes:

- `Futuris/futuris/api/app.py:140-146`: one long-lived
  `scheduler_session = async_session_factory()`, shared by **all** scheduler
  repos (forecast, outcome, event) and **all** scheduler jobs.
- `Futuris/futuris/storage/repositories.py:118-183`
  (`ForecastRepository.create`): `session.add` + `session.flush()` only —
  **no commit**. `EventRepository.append` (`repositories.py:600-610`) is the
  same: add + flush. A grep for `commit()` across `futuris/infra/scheduler.py`,
  `futuris/storage/repositories.py` and `futuris/services/*.py` finds none.
- The only regular commit on that shared session is the universe refresh:
  `Futuris/futuris/core/universe_forecasting.py:137-139`
  (`generate_universe_forecast`: `await repo.create(forecast)` then
  `await session.commit()`), called by
  `universe_provider_refresh_job` (`scheduler.py:256-310`, docstring:
  "Persistence is `generate_universe_forecast`'s own (it commits per target
  through the supplied session)") with
  `session = self.forecast_repo.session` (`scheduler.py:278`) — the same
  shared session.
- The universe job runs hourly at :12, **minutes before** the subscription
  rows finish flushing (:14–:26). So each cycle's subscription rows sit
  flushed-but-uncommitted and become durable only at the *next* hour's
  universe commit — roughly an hour late. The 15:12 and 16:12 rows are visible
  because the 16:12 and 17:12 universe commits landed after them; the 17:12
  rows were flushed after the 17:12 universe commit (17:12:26–29) and were
  still invisible at 17:52 IST.

**Confirmation owed (named follow-up, not assumed):** the mechanism predicts
the eight 17:12 rows become visible right after the 18:12 universe refresh
commits (~18:12:30 IST). The next hourly check re-queries the eight ids
(070e3d1d…, c5bb7d75…, 480bbf69…, 6afb70fe…, 40b50750…, 09e3ea3b…,
0a4a5939…, cb2f1b68…): if they appear, the lag is live-proven; if they do
not, the rows are lost rather than late, which is worse and changes item 2
below into an urgent fix. Either outcome is filed on issue #35. The 17:42
half-hourly jobs corroborate the mechanism so far: the lifecycle sweep,
calibration sweep and scoring job all ran and completed at 17:42:23–24 IST
without committing the rows — the re-check at 17:52 IST still found 16/24 —
and the calibration sweep itself resolved 0 new outcomes
(`resolved_count: 0`, `n_resolved_outcomes: 153`).

Durability hazard, stated plainly: the job logs `executed successfully` and
emits `forecast_updated` events for rows no other session can see. If the
service restarts before the next universe commit, that cycle's eight
forecasts are lost without a trace — the events claim work that is not
durable. The `_recover_scheduler_session` guard (`scheduler.py:40-53`) only
rolls back on a failed universe target; it does not commit subscription work.

Independent corroboration from the service's own calibration sweep
(17:42:24 IST, `calibration_sweep_job_completed`): `brier_score 0.0746`,
`ece 0.1663`, `is_calibrated False`, `overconfidence_penalized True` but
`interval_expansion_factor 1.0` — overconfidence detected, no widening
applied. Its `target_breakdown` gives the seven subscription targets
identical scores (brier 0.0767, ece 0.17, `resolved_count` 15 each) and the
demand target `brier 0.0007, resolved_count 16` — the same one-series /
one-live-target picture, computed by the service itself rather than by this
task's queries.

## 4. Scoring pass — store current, 1 newly resolved forecast scored

Method (repeatable): from `Futuris/` on Server 2, with the service venv
(`venv312`) and `PYTHONPATH=/opt/friday_universe/Futuris:/opt/friday_universe`:

```
python3 scripts/run_forecast_tracker.py --score
```

(`futuris/services/forecast_tracker.py:364-392`, `score_resolved`: sweeps every
resolved forecast with a numeric actual and no score row yet, one
`forecast_scores` row each, idempotent; `calibration_report` aggregates with
the shared `futuris.evaluation.metrics` functions, nominal level 0.90,
`MIN_REPORT_SAMPLES = 30`. The scheduler's own `forecast_scoring_job`
(`scheduler.py:521-547`) runs the same sweep every 30 minutes.)

- Run 17:37 IST: `considered 1, scored 1, skipped_no_numeric_actual 0`,
  `event_only_resolved 0`. n_scored 152 → **153**. The scheduler's 17:12:25
  scoring job had already found `considered 0`, so the store was current
  except this one newly resolved forecast.
- The newly scored row is live demand (`friday:fleet:forecast_demand_24h`,
  prediction 112.0, observed 2192.02, abs error 2080.02, pct error 94.9%,
  interval miss). The three newest live scores are all demand rows scored at
  :12:24 hourly, prediction 112.0 each, observed 1940.50 / 2086.68 / 2192.02.

### Calibration report (generated 2026-11-22T12:07:52Z, after the scoring pass)

| Scope | n | Verdict | MAE | RMSE | Coverage vs 0.90 | Mean width | Mean pct err |
|---|---|---|---|---|---|---|---|
| All | 153 | **overconfident** | 841.45 | 1012.54 | 0.8235 (gap −0.076) | 9409.95 | 59.25% |
| Live only (`evidence_class=live`) | 16 | — (below min 30: `insufficient_data`, metrics null at top level) | 1956.10 | 1957.77 | **0.0** (gap −0.9) | 48.99 | 96.24% |
| Synthetic only | 137 | — | 720.79 | 850.54 | **1.0** (gap +0.1) | 10435.02 | 55.19% |

Per-target (the only live target): `friday:fleet:forecast_demand_24h`, n=16
(now; 15 at the 14:35 IST report), MAE 1956.10, RMSE 1957.77, coverage_90
0.0, mean interval width 48.99, Winkler_90 38666.03, mean pct error 96.24%.
The demand model predicts ~112–181 while actual demand runs ~1940–2192 —
an order of magnitude low — with intervals ~49 wide against errors ~1950.
Every scored live interval misses. The newest universe row (17:12 cycle,
`friday:fleet:forecast_demand_24h`, prediction 181.0, status active) is the
same shape: the live demand forecast is systematically wrong, not merely
noisy.

The 137 synthetic scores (all seven subscription targets, 15 each, plus
older synthetic targets) have coverage 1.0 because the intervals are ~10,435
wide against ~720 MAE — they cannot miss. Blending them with the 16 live
scores produces the headline "overconfident" (0.8235); read separately, the
truth is sharper: synthetic intervals are vacuously wide, live intervals are
vacuously narrow.

Note: at the 14:35 IST report the verdict was "calibrated" (n=149,
coverage_90 0.854); the three additional live demand scores since then moved
it to "overconfident" (n=153, coverage_90 0.824). The verdict flips on a
handful of live rows because the synthetic bulk is inert.

## 5. What is owed (Muse decisions, not done here)

1. **Wire a real telemetry source** (`FUTURIS_TELEMETRY_SOURCE=nexus` or
   `vyralx`) or scope the eight subscriptions down to what the synthetic
   generator can honestly stand for. Until then every hourly "forecast" for
   BTC/ETH/SOL/SPY/DGS10/T10Y2Y/UNRATE is the same synthetic checkout-demand
   number, and the tracker will keep scoring one series seven times.
2. **Commit the scheduler's own writes**: commit the shared session at the
   end of `forecast_refresh_job` (`scheduler.py:168`), or give the refresh job
   its own session with commit. The current shape reports success and emits
   events for rows that are not durable for ~an hour, and loses them outright
   on a restart in that window.
3. **Fix the live demand model**: prediction ~112–181 vs actuals ~1940–2192
   with ~49-wide intervals is a broken forecaster, not a calibration tweak.
   (The universe refresh's `insufficient_data` refusals for
   `vyralx:trends:topic_volume_24h` and `intelx:research:finding_volume_24h`
   — "every daily value is 0" — are the honest behaviour in the same job and
   are *not* part of this finding.)
4. **Do not trust per-target tracker tables for the seven subscription
   targets** until (1) lands — they are one series under seven labels.

## 6. Method note / limitations

- Read-only against the live service except the tracker scoring pass, which
  writes exactly one `forecast_scores` row (the tracker's designed write
  path, idempotent). No forecast, scheduler or service change; no restart.
- Forecast contents read through the service's own storage layer
  (`async_session_factory` + `ForecastModel`/`ForecastScoreModel`), not by
  guessing at API responses. Journal lines quoted from
  `journalctl -u Futuris.service` on Server 2.
- The 24 ids were taken from journal `domain_event_emitted` lines; the 17:12
  set was re-extracted mechanically (`journalctl ... | grep -oE
  "forecast_id=[0-9a-f-]{36}"`) after one hand-transcription typo dropped a
  hex digit — the corrected id set matches the journal exactly.
- `run_forecast_tracker.py --report-only` alone prints `{}` (a CLI quirk:
  the report branch requires `--score` or no flags); the reports quoted here
  used no flags (report) and `--score` (score + report).
- Bridge flakiness noted, not blocking: two `run_shell` calls were slow
  enough to background (~60–120 s) and delivered on completion; no data lost.
- The `SingularMatrixWarning` (statsforecast ARIMA, rank-deficient design
  matrix) appearing through the 17:12–17:13 window is recorded but not
  root-caused here — it coincides with the cycle but no error line ties it
  to the missing rows.

## Evidence pointers

- Tracker reports: `/tmp/muse7_tracker_report.json` (14:35 IST, n=149,
  "calibrated") and `/tmp/muse7_tracker_report_new.json` (17:31 IST, n=152)
  and `/tmp/muse7_tracker_scored.json` (17:37 IST, n=153, "overconfident")
  on Server 2; content-check raw output `/tmp/muse7_fut016_content.json`
  (16/24 found) and `/tmp/muse7_fut016_content2.json` (recheck 17:52 IST,
  still 16/24); scripts `/tmp/muse7_fut016_content.py`,
  `/tmp/muse7_fut016_recent.py`, `/tmp/muse7_fut016_newscore.py`,
  `/tmp/muse7_fut016_evclass.py` on Server 2.
- Code: `Futuris/futuris/infra/scheduler.py` (subscriptions :97-105,
  refresh :168-250, universe job :256-310, scoring job :521-547),
  `Futuris/futuris/api/app.py:140-146` (shared session),
  `Futuris/futuris/storage/repositories.py:118-183` (create, flush-only),
  `Futuris/futuris/core/universe_forecasting.py:137-139` (the commit),
  `Futuris/futuris/connectors/factory.py:16-28`,
  `Futuris/futuris/connectors/synthetic_telemetry.py` (fetch, no target),
  `Futuris/futuris/services/forecast_tracker.py:364-392`.

— Muse 7, 2026-11-22
