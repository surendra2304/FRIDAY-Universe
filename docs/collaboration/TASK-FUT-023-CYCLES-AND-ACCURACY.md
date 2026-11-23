# TASK-FUT-023 — Futuris: last-3-cycles verification + accuracy evidence

- Task: TASK-FUT-023 (P1, owner muse_9)
- Branch: `muse9/task-fut-023`, from main `958cc13`
- Claim: issue #1483 comment 7099202361 (2026-11-23 ~16:41 IST), on assignment
  in coordinator watch 7098354619 (~16:12 IST) + nudge 7098694215 (~16:25 IST)
- Assignment: verify the last 3 scheduler cycles produced real forecasts and
  score the oldest unscored forecasts, file accuracy evidence.
- Live target: Futuris.service on Oracle Server 2 (10.0.0.120), MainPID 609831
  since restart 2026-11-23 16:15:17 IST. All live evidence below was read
  first-hand this run via the bridge (`run_shell`, server 2) and the public
  gateway — journal lines, service state, and read-only store queries through
  the service's own repository layer (SELECTs only; no writes, no restarts,
  no credential ever left Server 2).

## 0. Live service state at verification time

- `Futuris.service`: active, running, MainPID 609831, started 16:15:17 IST.
  Previous process (PID 605930) ran 12:00:36–16:15:16 IST.
- S2 checkout is on branch `muse10/task-fut-022-401-storm` @ `da4541b4`
  (work PR #1491, OPEN, mergeable clean, base `e570ad5c`) — i.e. the live
  service runs Muse 10's unmerged FUT-022 (401-storm) fix. Noted, not mine
  to merge. FUT-017 standing-scoring code IS in this checkout
  (`_score_matured_forecasts` present in `futuris/infra/scheduler.py`).
- Public gateway: `GET /futuris/health` → HTTP 503, status `degraded`:
  storage ok (13/13 tables present, DB round-trip ok), forecasting
  `unknown` / `NO_MODEL_PROBE` (OBS-016 by-design honest degradation).
  `GET /futuris/v1/self/status` → HTTP 403 (requires minimum role `viewer`)
  from outside — the accuracy surface is not publicly readable.
- Bridge transport: `gh` calls timed out twice ~16:39–16:40 IST (read
  timeout to friday-universe.duckdns.org); recovered ~16:43 IST
  (`tools` list in 2.2 s). GitHub reads/writes in this run went through
  `gh_api.py` (custom.github PAT) instead.

## 1. Last 3 scheduler cycles (at claim time ~16:41 IST: 14:01, 15:01, 16:01)

The hourly cycle is two jobs at :01: `forecast_refresh_job` (telemetry,
8 subscriptions) and `universe_provider_refresh_job` (3 provider targets).

### 1.1 Cycles 14:01 and 15:01 — produced real stored forecasts

- Telemetry refresh executed successfully: 14:01:18 → 14:14:36,
  15:01:18 → 15:13:23 (APScheduler "executed successfully").
- Provider refresh completed both cycles: `generated=3 active=1` at
  14:01:30 and 15:01:23. The ACTIVE forecast each cycle:
  `friday:fleet:forecast_demand_24h`, prediction 263.0,
  model `naive@v1:44136fa355b3678a`. The other two provider targets are
  honest `INSUFFICIENT_DATA` refusals every cycle (see §1.4).
- Store (read-only query, forecasts `created_at` in last 5 h): 8 telemetry
  targets × 3 rows each (cycles 13:01, 14:01, 15:01), latest `as_of`
  09:31:18 UTC (15:01 IST); provider targets × 4 rows each (13:01–16:01).
  Telemetry rows are real stored forecasts from a real model fit
  (`seasonal_naive@v1:bb63b87d1a90360b`) — see the caveat in §3, which
  qualifies what "real" means here.

### 1.2 Cycle 16:01 — telemetry refresh KILLED by the service restart (GAP)

- Provider refresh completed normally at 16:01:24 (`generated=3 active=1`,
  same ACTIVE forecast, prediction 263.0).
- Telemetry refresh started 16:01:18 and ran ~14 minutes, then at 16:15:16
  raised `concurrent.futures.process.BrokenProcessPool: A process in the
  process pool was terminated abruptly` (`scheduler.py:194` →
  `pipeline.py:541` → `core/pipeline.py:191` → `infra/cpu.py:426`
  `run_cpu_process`), followed immediately by `scheduler_shutdown_requested`
  / `Scheduler has been shut down` — the service restarted at 16:15:17 IST
  (new PID 609831), terminating the CPU worker pool mid-fit. The restart,
  not a model or data error, killed the cycle.
- Store confirms zero telemetry forecasts from 16:01: latest telemetry
  `as_of` is 09:31:18 UTC (15:01 IST); provider rows reach 10:31:24 UTC
  (16:01 IST). The restart also skipped the 16:31 lifecycle/scoring jobs;
  the first post-restart 30-minute jobs fired 16:45:33 / 16:45:55 and
  completed (see §2).
- Likely restart cause: the S2 checkout is Muse 10's FUT-022 branch and
  the restart coincides with that deploy (PR #1491 open). Actor not
  verified — recorded as the likely cause, not asserted.
- **Gap filed:** the 16:01 telemetry cycle produced no forecasts. No
  re-run was attempted by this task (re-running a scheduler cycle is a
  live write outside a verification task's scope).

### 1.3 Cycle 17:15 — partial, still running at probe time

- After the 16:15 restart the hourly jobs re-anchored to process start,
  so this cycle fired at 17:15:33, not 17:01:18 (APScheduler interval
  jobs anchor to start; the 30-minute jobs likewise moved to :15/:45).
- Provider refresh completed 17:15:44: `generated=2 active=1` — NOT 3.
  The ACTIVE forecast is again `friday:fleet:forecast_demand_24h`
  (prediction 263.0). The missing count is the vyralx target, which
  FAILED with `Session is already flushing` (17:15:35) yet still left
  its `INSUFFICIENT_DATA` row in the store — persisted but uncounted
  (see §2.1). The intelx target refused as usual
  (`INSUFFICIENT_DATA`). Store confirms 3 new provider rows at
  11:45:33–43 UTC (17:15 IST).
- Telemetry refresh started 17:15:33 and was still running at probe
  time (~17:16–17:19 IST; it normally takes ~12–14 minutes) — outcome
  unknown, to be verified on the next check. No new telemetry rows yet
  at probe time (latest telemetry `as_of` still 09:31:18 UTC).

### 1.4 The two INSUFFICIENT_DATA provider targets (by design, not a failure)

- Every cycle (13:01–16:01): `vyralx:trends:topic_volume_24h` and
  `intelx:research:finding_volume_24h` refuse with
  "stored series contains no observed events in the 28-day window (every
  daily value is 0); refusing to present an unmeasured intake as a
  measured zero-volume forecast". Honest refusals, recorded as
  `INSUFFICIENT_DATA` rows (prediction 0.0) — the loop refuses to invent
  data. No action for this task.

## 2. Scoring — the standing loop works, backlog is zero

FUT-017 per-cycle scoring is live and scoring (journal
`forecast_scoring_job_completed`, all under the pre-restart PID except
the last):

- 14:31:19 — considered 9, scored 9 → `n_scored_total` 338 → 347,
  rolling 30d hit-rate 0.893372.
- 15:31:19 — considered 9, scored 9 → 347 → 356, hit-rate 0.893258.
- 16:01:20 — considered 0, scored 0 → 356, hit-rate 0.893258.
- 16:45:55 (new process) — considered 9, scored 9 → 356 → 365,
  hit-rate 0.893151, `report_status: measured`.
- No `cycle_scoring_failed` / `forecast_scoring_job_failed` lines in 4 h.
- Store (read-only): `list_unscored_resolved` returned **0 rows** at the
  first probe (through the 16:01 cycle) — no resolved forecast lacked a
  score row then; `count_scores()` = 356 (365 after the 16:45 run per
  the journal); `event_only_resolved` = 0. The 9+9+9 scored that
  afternoon were the newly matured ones, scored in-cycle.
- **Backlog at final probe (~17:16–17:19 IST): 8 unscored-resolved.**
  Eight forecasts (all `as_of` 2026-11-22 11:42 UTC) were resolved by
  the lifecycle sweep at 17:15:43 IST and await the next scoring pass
  (~17:45). One more score landed in the same minute (UNRATE,
  scored 17:15:43.95, `TOTAL_SCORES` 366). This is a fresh
  resolution batch, not a stale backlog — the loop drains it every
  30 minutes; no manual scoring was attempted (a manual score run
  would write to the live store outside a verification task's scope).

### 2.1 NEW live failure — shared-session contention at 17:15:43

- `calibration_sweep_job` raised an exception at 17:15:43 in
  `outcome_repo.list_resolved_with_forecasts` (`scheduler.py:445` →
  `repositories.py:495` → SQLAlchemy session error while acquiring a
  connection). The same minute, the universe job's vyralx target
  failed with `Session is already flushing`.
- Cause (from the evidence, not yet proven in code): after the
  restart the 30-minute jobs (lifecycle, calibration, scoring) and
  the hourly jobs all fire together at :15/:45 and share the
  scheduler's single session — concurrent jobs collide on it. The
  calibration sweep died for the cycle; its next run is 17:45:33.
  Filed here as a follow-up for the coordinator's pool, not fixed
  in this task.

## 3. Accuracy evidence — filed WITH a caveat

- Rolling 30-day hit-rate (measured, from the store): **0.893151** over
  365 scored forecasts, all in-window, `min_samples` 30 met,
  `report_status: measured` (16:45:55 run).
- **Caveat — the telemetry forecasts are not target-specific.** In the
  15:01 cycle all 8 telemetry subscriptions stored the IDENTICAL
  forecast: prediction 1544.89, range [0.0, 10087.87], model
  `seasonal_naive@v1:bb63b87d1a90360b` — BTC/ETH/SOL price variance, SPY
  return, DGS10 yield, T10Y2Y curve, UNRATE drift and checkout capacity
  all carry the same numbers. Mechanism, verified in code:
  - Ingestion is target-blind: `BaseConnector.fetch(start, end)` takes
    no target (`futuris/connectors/base.py:80`); the pipeline ingests
    the same observation list for every subscription.
  - The live connector is the deterministic synthetic generator,
    confirmed three ways: `FUTURIS_TELEMETRY_SOURCE` defaults to
    `"synthetic"` (`infra/config.py:142`); the key is unset in the
    S2 `.env` (and `NEXUS_URL` is unset too); AND the live process
    environ (`/proc/<MainPID>/environ`, MainPID 609831) contains NO
    `FUTURIS_TELEMETRY_SOURCE` — so the default applies at runtime.
    The store agrees: every telemetry forecast row carries
    `evidence_class` SYNTHETIC with source
    `telemetry:synthetic via SyntheticTelemetryConnector [SYNTHETIC
    data]`, while the `friday:fleet` rows carry class LIVE, source
    `stored_series:forecast_requests`.
  - Outcomes resolve the same way: `lifecycle_sweep_job` fetches ONE
    observation frame and `run_lifecycle_sweep` resolves every active
    forecast against it — the 15:31 batch of 9 scores shares observed
    value 2316.24 across 8 targets (the 9th, `friday:fleet`, scored
    pred 181.0 / obs 2316.24, hit False).
  - Store-wide: only **45 distinct predictions / 56 distinct observed
    values across all 356 score rows**.
- What this means: the 0.893 hit-rate is real arithmetic over stored
  scores, but it measures ONE synthetic series' wide-interval coverage
  repeated 8×, not 8 independent targets' accuracy — and the intervals
  ([0.0, 10087.87]) are so wide that hits are near-guaranteed. The
  telemetry forecasts are real stored rows from a real model fit, but
  their input series is generated (seed 42), not measured. The
  `friday:fleet` provider forecast is the one series with its own
  provider data (naive, pred 263.0).
- No code fix was attempted here: pointing Futuris at a measured source
  (NEXUS / per-target series) is a follow-up for the coordinator's pool,
  not a silent change inside a verification task.

## 4. Verdict

- Acceptance, first half ("last 3 cycles verified to have produced real
  forecasts, or the gap filed"): **PARTIALLY MET, gap filed** — 14:01
  and 15:01 produced real stored forecasts (with the §3 caveat); the
  16:01 telemetry cycle produced none (restart kill, §1.2).
- Acceptance, second half ("oldest unscored forecasts scored, accuracy
  evidence filed"): **MET WITH A TAIL** — the standing loop scored
  everything resolvable through 16:45 (9+9+9 = 27 this afternoon, zero
  backlog at the first probe); 8 resolutions from 17:15:43 await the
  ~17:45 pass (the next scheduled scoring run drains them — to be
  confirmed on the next check, not forced here). Accuracy evidence
  (hit-rate 0.893151 over 365, total scores 366 at final probe, with
  the §3 caveat) is filed in this document.
- Follow-ups for the coordinator's pool (not taken here): (a) point the
  live scheduler at a measured telemetry source or per-target series —
  the current synthetic default makes per-target forecasts
  indistinguishable; (b) the 16:01 kill shows a deploy/restart during
  a running hourly cycle discards that cycle silently (no
  completed/failed summary is written for the telemetry refresh job —
  it has no completion log line, unlike the provider job); (c) the
  scheduler's jobs share one session and collide after the restart
  re-anchored them to the same :15/:45 marks — calibration sweep
  exception + vyralx "Session is already flushing" at 17:15:43
  (§2.1); the jobs need session isolation or serialization.
- **Correction from the 17:38–17:48 IST follow-up verification (§6):
  the second half is NOT met.** The 17:45 scoring pass logged
  considered 8 / scored 8 / `n_scored_total` 374, but the store still
  shows 366 scores and the same 8 forecasts unscored — the drain did
  not persist. And the 17:15 telemetry cycle produced zero stored
  telemetry forecasts despite reporting success. See §6.

## 6. Follow-up verification — hourly self-check 2026-11-23 17:38–17:48 IST

Verified first-hand this run (bridge `run_shell`, Server 2; read-only
store queries through the service's own repository layer, SELECTs only).
Service still MainPID 609831, active, no restart since 16:15:17 IST.

### 6.1 Cycle 17:15 telemetry — completed with success, stored ZERO rows (NEW GAP)

- `forecast_refresh_job` started 17:15:33, `executed successfully`
  17:27:38 IST (~12 min; CPU worker PID 610988 fitted ARIMA models,
  repeated `SingularMatrixWarning: The design matrix is rank-deficient`
  from statsforecast).
- Store (read-only, probed ~17:47 IST): **zero telemetry forecasts
  created from the 17:15 cycle.** All 8 telemetry targets' latest
  `as_of` is still 09:31:18 UTC (15:01 IST cycle); only 3 forecasts
  created since 11:15 UTC — the provider rows at 11:45:33–43 UTC
  (17:15 cycle). `created_at >= 11:15 UTC` count = 3, all provider.
- One `domain_event_emitted event_type=forecast_updated` fired at
  17:26:11 for forecast_id `823e8307-978a-42d7-87d8-c26ff8e34d2e` —
  **that forecast_id does not exist in the `forecasts` table**
  (SELECT by id returns NONE). The refresh emitted a forecast-updated
  event for a forecast that was never persisted.
- Verdict: the 17:15 telemetry cycle is a **silent zero** — worse than
  the 16:01 kill, which at least raised a visible exception. Two
  consecutive telemetry cycles (16:01, 17:15) produced no telemetry
  forecasts. Root cause not proven in this task; the emitted-but-
  unstored forecast points at the persist step of the telemetry
  refresh (or the shared-session contention in §2.1) rather than at
  the model fit, which ran. Follow-up for the coordinator's pool.

### 6.2 The 17:45 scoring pass — logged success, did NOT persist (DRAIN FAILED)

- 17:45:33 jobs all fired: lifecycle sweep executed successfully;
  calibration sweep **completed** 17:45:37 (recovered from its 17:15
  exception; brier 0.0648, ece 0.161, `n_resolved_outcomes` 374,
  `is_calibrated: False`).
- Scoring job: `forecast_scoring_job_completed` 17:45:37 with
  `considered: 8, scored: 8, n_scored_total: 374, hit_rate: 0.893048`,
  and APScheduler `executed successfully` — no exception, no error,
  no rollback line anywhere in the journal 17:45:33–17:48:00.
- **Store disagrees (probed twice, ~17:46:51 and ~17:47:23 IST):**
  `count_scores()` still **366**; `list_unscored_resolved()` still
  **8 rows** — the SAME 8 forecasts resolved 17:15:43 (as_of
  2026-11-22 11:42 UTC; ids `c5bb7d75…`, `480bbf69…`, `6afb70fe…`,
  `5d08464f…`, `070e3d1d…`, `40b50750…`, `09e3ea3b…`, `0a4a5939…`,
  the same 8 that failed calibration resolution at 17:15:43 with
  `Session is already flushing`); latest score row is still the
  UNRATE score of 17:15:43.95. **The 8 scores the job claims do not
  exist in the store.**
- The journal's `n_scored_total: 374` is therefore in-memory arithmetic
  from a session whose writes never landed (or were rolled back by a
  concurrent job on the shared session) — the scoring loop's own
  metrics can no longer be trusted at face value; only the store
  counts. The 17:15:43 first scoring run (considered 0, scored 0,
  n=365) matched the store then, so the store is the ground truth
  and the 17:45 run is the one that diverged.
- Verdict: **the 8-score tail was NOT drained.** Acceptance second
  half is NOT MET as of 17:47 IST. The next scoring pass is 18:15:33
  (jobs re-anchor to :15/:45 after the restart; the 18:15 hourly
  cycle follows). Do not force a manual score run — that is a live
  write outside a verification task's scope. Follow-up for the
  coordinator's pool: scoring persistence / session isolation (same
  root-cause family as §2.1).
- Minor, noted: `stratex_risk_regime_broadcast_failed error=All
  connection attempts failed` at 17:45:37 (unrelated to scoring).

### 6.3 Updated accuracy evidence

- Rolling 30-day hit-rate from the **store**: **0.893151 over 366
  scored forecasts** (latest score 17:15:43.95 UTC). The journal's
  0.893048 / 374 at 17:45:37 is NOT backed by the store and must not
  be cited as the measured rate.
- The §3 caveat stands unchanged (one synthetic series, wide
  intervals, 45 distinct predictions).

## 7. Files changed

- `docs/collaboration/TASK-FUT-023-CYCLES-AND-ACCURACY.md` (this file)
- `docs/collaboration/WORK_BOARD.yaml` (FUT-023: branch set, claim
  evidence, status CLAIMED → IN_REVIEW)
