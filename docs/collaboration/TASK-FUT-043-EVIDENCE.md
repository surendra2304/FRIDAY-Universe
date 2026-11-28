# TASK-FUT-043 — Futuris: live-class forecast interval coverage fix

- Task: TASK-FUT-043 (P2, owner muse_tp14) — root-cause why live class
  `friday:fleet:forecast_demand_24h` (n=132 in FUT-042) has coverage_90 0.0
  (entirely out of interval); fix the interval calibration or the class
  definition; file before/after coverage as evidence. Standing follow-up
  carried since FUT-042 runs 2–9, disclosed again in M5 VERIFIED review
  6093717541 on PR #2204.
- Claim: hub #2045 comment 7229982659, 2026-11-28 ~04:40 IST, on BE 04:37 §B
  assignment. Branch `musetp14/task-fut-043-live-class-coverage-fix` from
  main `81af5b8f`, fast-forwarded to main `fac8c0eb` before filing (zero
  prior commits). Board flip rides in the next coordinator board PR
  (coordinator-only flip rule) — this PR carries the fix + tests + this
  evidence doc, no board hunk.

## 0. Verdict: ROOT CAUSE FOUND and FIXED in code — before/after filed below

- The 0.0 coverage is NOT an interval-width problem. It is a class-definition
  problem: the fleet target's outcomes were resolved by the wrong rule
  against the wrong data. The forecasts predict the DAILY COUNT of forecasts
  produced (~190–270/day); the outcomes recorded the MAXIMUM synthetic
  checkout-rpm telemetry value in the window (~1700–2500). Two different
  quantities, so all 136 live scores missed — 100% one-sided, every
  prediction below its "observed" value.
- Fix (this PR): a dedicated resolution rule for the fleet target that
  resolves against the daily forecast counts (the same `forecast_requests`
  series the forecasts are fitted on), target-pattern dispatch in the
  resolver (unknown targets now raise instead of silently falling through
  to another target's rule), and scheduler wiring that feeds the rule its
  daily-counts frame. Forecasts whose expiry day is still in progress
  defer (stay ACTIVE) instead of recording a partial count.
- Before/after on the same live rows (re-scored read-only against the true
  daily counts): coverage_90 **0.0 → 0.456**, MAE **1921.88 → 64.37**.
  Residual gap is honest and quantified in §5: the stored intervals are
  still narrow for current day-to-day count swings, and 28 of 136 misses
  are one-day-lagged level jumps no widening fixes.

## 1. BEFORE — live, probed 2026-11-28 ~05:35–06:00 IST (read-only)

Probe scripts `/tmp/fut043_drill.py` (sha256 `ac503364…`, content-verified
after transfer) and `/tmp/fut043_drill2.py` / `/tmp/fut043_drill3.py`, run
on FRIDAY-Server (bridge server 3) from `/opt/friday_universe/Futuris`
with Futuris's own session factory and models (server-3 checkout HEAD
`06ff9ee6`, branch `main`). Code read first-hand from main and
hash-checked where the probes depend on it.

- Scored rows for the live class: **n=135** at probe 1, **136** by probes
  2–3 (one new score landed between probes — the scoring job is live).
- coverage_90 **0.0** (0 hits), MAE **1921.88**, mean signed error
  (observed − prediction) **+1921.88** — **135/135 predictions below
  observed, 0 above**. Mean prediction **191.43**, mean observed
  **2113.31**, mean interval width **98.04** (min 4.84, max 126.57).
  Mean pct error 0.9066. Min prediction 0.0, max 263.0; min observed
  1670.75, max observed 2507.36 (fractional — a daily count would be an
  integer).
- Model versions: `naive@v1:44136fa355b3678a` 113, `drift@v1:44136fa355b3678a`
  22. Nominal-level source `adapter_default` on all 135 (no
  predictive-distribution percentile pair stored — the 0.90 nominal is
  assumed, per the tracker's documented default). Evidence class `live`
  on all 135.
- Resolution methods: `automatic` 119, `ambiguous` 17 (n=136).
- **Decisive stamp: every one of the 136 outcome rows carries
  `resolution_rule_version = "rule:capacity_exceedance:v1.0"`.** The
  capacity-exceedance rule resolved a target that is not a capacity
  target.
- The history the forecasts are fitted on is real daily counts:
  `series_provider="forecast_requests"`, 28 points 2026-10-30 → 2026-11-26,
  last value **259** (model_metadata on the newest forecasts). Daily
  counts of stored forecast rows: 2026-11-14: 11, 11-20: 112, 11-21: 181,
  11-22: 263, 11-23: 160, 11-24: 251, 11-25: 235, 11-26: 259, 11-27: 322
  (total forecast rows 1794). The fleet produces ~11 forecasts per hourly
  cycle, ~259/day — the predictions (~191–268) track this; the recorded
  "observed" values (~2113) do not.
- `FUTURIS_TELEMETRY_SOURCE` on the live deployment: **synthetic**.
  Fresh synthetic fetch (same generator, seed 42) over 2 days: min 10.0,
  max 2444.1, mean 843.88 — the same value family as the scored observed
  values (1670.75–2507.36). Exact per-row reproduction is not available
  from a fresh fetch (the generator's RNG sequence is keyed to the fetch
  window start, which differs per sweep run); the rule-version stamp on
  every outcome row plus the value family plus the code path below is
  the proof, and it is conclusive.

## 2. Root cause — the chain, file by file

1. `Futuris/futuris/core/resolution.py` — `OutcomeResolver` registered
   exactly ONE rule (`CapacityExceedanceResolutionRuleV1`) and applied it
   to every forecast regardless of target. Its `target_pattern`
   (`service:*:capacity_exceedance_*`) was never matched against anything.
2. `Futuris/futuris/infra/scheduler.py` — both sweeps that record outcomes
   (`lifecycle_sweep_job`, `calibration_sweep_job`) build ONE observation
   frame from `build_scheduler_connector().fetch(...)` and hand it to the
   resolver for every matured forecast. With `FUTURIS_TELEMETRY_SOURCE`
   unset the connector is `SyntheticTelemetryConnector(seed=42)`.
3. `Futuris/futuris/connectors/synthetic_telemetry.py` — the generator
   simulates checkout demand in rpm: base 1200, daily seasonality ±800,
   weekly ±400, noise σ=45, occasional spikes +800–2200. Values live in
   roughly 10–2500.
4. The capacity rule resolves `observed_value = round(max(value), 2)` over
   the window `[as_of, expires_at]` (and `AMBIGUOUS` when the window holds
   <80% of the expected 288 five-minute points — that is the 17 ambiguous
   rows). For the fleet target this maximum is meaningless: it is the peak
   of a synthetic rpm curve, not a count of forecasts.
5. Meanwhile the forecast side is correct: `universe_domains.py` defines
   the target as "daily count of forecasts Futuris has produced",
   `series_providers.forecast_request_series` counts `ForecastModel`
   rows per UTC day, and the adapters fit that series (predictions
   191–268 vs true counts 160–322). The mismatch is entirely on the
   resolution side — which is why the error is 100% one-sided and ~11x.

## 3. The fix (this PR)

- `Futuris/futuris/core/resolution.py`
  - New `FleetForecastDemandResolutionRuleV1`
    (`rule:fleet_forecast_demand:v1.0`, target pattern
    `friday:fleet:forecast_demand_24h`): resolves `observed_value` to the
    count for the UTC day of `expires_at` out of a daily-counts frame
    (`timestamp` = UTC day start, `value` = forecasts produced that day),
    `event_occurred=None` (not an exceedance target), method `automatic`.
    If the expiry day has no row yet (the day is still in progress) it
    raises `ResolutionNotReadyError` — a deferral, not a failure.
  - New `ResolutionNotReadyError(RuntimeError)`: "cannot be resolved yet".
  - `OutcomeResolver` now dispatches by target pattern
    (`fnmatch` on each rule's `target_pattern`); a target with no rule
    raises `ValueError` instead of silently falling through to another
    target's rule; a fleet forecast resolved without a daily-counts frame
    raises `ResolutionNotReadyError` instead of resolving against
    telemetry. The capacity rule itself is untouched.
- `Futuris/futuris/core/lifecycle.py`
  - `run_lifecycle_sweep(..., daily_counts_df=None)` forwards the frame;
    a `ResolutionNotReadyError` leaves the forecast ACTIVE with no outcome
    (deferred, counted in the new `deferred_count` on
    `LifecycleSweepReport`) instead of marking it EXPIRED/failed.
- `Futuris/futuris/infra/scheduler.py`
  - New `_daily_forecast_counts_frame(scope, now, days=30)` helper: builds
    the frame from `forecast_request_series` (complete UTC days only,
    same definition the target is fitted on), from the job scope's session
    (or its forecast repo's session on the legacy path); returns None when
    no session is available, which makes the resolver defer fleet
    forecasts rather than mis-resolve them.
  - Wired into `lifecycle_sweep_job` and `calibration_sweep_job`; the
    calibration loop skips not-ready forecasts quietly (nothing written,
    nothing to roll back) so they are retried on a later sweep.
- No change to issuance, the adapters, the tracker, or any other target's
  resolution. The capacity target still resolves by window max (§4 test).

## 4. Tests — 11 new, all pass; no new regressions

New `Futuris/tests/test_fut043_fleet_demand_resolution.py` (11 tests),
run locally on a scratch venv (DATABASE_URL mock, per CI) with
`pytest tests/test_fut043_fleet_demand_resolution.py`: **11/11 pass**.
Pins: fleet rule resolves the expiry-day count; defers while the day is
incomplete; the resolver never resolves fleet against telemetry (returns
322, not the telemetry max ~2348); fleet without a counts frame defers;
capacity target still resolves by window max; unknown target raises;
registry holds both rules; lifecycle sweep defers the not-ready and
resolves the ready in one pass (resolved 1, deferred 1, failures 0,
deferred forecast stays ACTIVE with no outcome row); the counts-frame
builder counts stored rows per UTC day and excludes the incomplete today.

Regression suites run on the same venv, before and after the change
(`git stash` comparison): `test_fut006_forecast_tracker`,
`test_calibration_sweep`, `tests/core/test_schemas`,
`test_fut025_scoring_session_isolation`,
`test_fut017_standing_accuracy_scoring`,
`test_scheduler_and_pipeline` — identical results both ways. The only
failures are pre-existing and environmental in this scratch venv: 3 in
the first batch (statsforecast not installed, so the forecast-refresh
test skips its fits; webhook test's mock destination resolves oddly in
this sandbox) and 2 in the second batch (same statsforecast cause). No
new failure. `py_compile` clean on all four touched files.

## 5. AFTER — same 136 live rows re-scored against the true daily counts

Definition: for each scored fleet forecast, the true observed value is
the count of forecast rows created on the UTC day of `expires_at` — the
quantity the target's series forecasts. Stored intervals unchanged.

- coverage_90 **0.456** (62/136), MAE **64.37** (was 1921.88), mean true
  observed **246.39**. All 136 rows had a complete expiry day (0 missing).
- Recent regime (`as_of` ≥ 2026-11-22): coverage **0.574** (62/108).
- Widening the stored intervals by a factor f (same centre): 1.0× → 0.456,
  1.25× → 0.625, 1.5× → 0.794, 2.0–4.0× → **0.794 plateau**. The remaining
  28 misses are level misses, not width misses.
- Coverage by expiry day (true count in brackets): 11-21 0/5 [181], 11-22
  0/23 [263], 11-23 22/22 [160], 11-24 17/17 [251], 11-25 0/23 [235],
  11-26 23/23 [259], 11-27 0/23 [322]. The forecasts issued on a day share
  one prediction/interval (the adapter refits daily), and the daily counts
  swing 160 → 322 faster than a drift/naive point forecast tracks — the
  miss days are the one-day-lagged level jumps, including the early ramp
  (11-21/11-22, when the fleet went from ~0 to volume and predictions
  were 0.0 / ~112).
- Reading: the resolution fix removes the 0.0 and the 11x bias, but the
  stored intervals are still narrow for current day-to-day count swings
  (0.456 vs nominal 0.90). Two reasons, both in the data: the 28-day fit
  series is ~20 zero days, so the first-difference residual std the
  adapters build intervals from understates the current regime; and the
  point forecast is yesterday's level while counts swing ±60–90/day.
  The intervals should re-calibrate as the fit series accumulates real
  daily counts. Note the calibration sweep already computes an
  `interval_expansion_factor` on overconfidence but only logs/records it —
  it is never applied to stored or future intervals; wiring that (or an
  equivalent conformal widening) to the fleet target is the follow-up,
  not part of this fix.

## 6. Service state (live, this run)

- Live Futuris scheduler on IntelX-Server (32.236.185.237:8004), probed
  2026-11-28T00:36:53Z / 06:06:53 IST: `/ready` status **ready**,
  database **connected**, backend **oracle**, version 2.0.0;
  `/health` status **degraded** — the known state (NO_MODEL_PROBE;
  storage ok 13/13, database ok). Unchanged from FUT-042.

## 7. Limits and follow-ups (honest)

- The 136 historical score rows stay poisoned: they were scored against
  synthetic-rpm maxima, and this fix changes future resolutions only.
  Re-resolving history means deleting those outcome + score rows and
  letting the sweeps re-resolve them — a live write on the production DB.
  That is a coordinator decision; this run's route was read-only probes
  and it was not done here. Until it happens, the live calibration
  report's fleet line stays 0.0 for the old rows while new rows score
  correctly.
- The fix is code-only and takes effect when the Futuris scheduler on
  IntelX-Server is redeployed (coordinator/owner call — workers do not
  deploy). Until then, newly matured fleet forecasts keep resolving
  against telemetry maxima.
- Residual under-coverage (0.456 vs 0.90 nominal) is a genuine
  calibration gap, not a definition error: see §5. The 1.5× widening
  that reaches 0.794 on live data is measured, not assumed.
- The resolution gap from FUT-042 (292 matured forecasts with no outcome)
  is unaffected by this fix and remains open.

## 8. States

- implemented YES (fix + 11 tests + this evidence) / tested YES (new
  tests 11/11; regression suites identical before/after; live before/after
  computed read-only from the production store) / merged YES (PR #2233,
  merge `25aacc52`, 2026-11-28 07:56 IST; M10 VERIFIED review 6095174408)
  / deployed YES (this §9, 2026-11-28 ~08:38 IST) / production-verified
  PARTIAL (fix live on the scheduler and smoke-proven on the deployed
  tree; first live re-scored fleet outcomes still to be observed).

## 9. LIVE PROOF — redeploy after merge (WATCH251 §D)

- PR #2233 MERGED 2026-11-28 07:56 IST (merge `25aacc52`, M10 VERIFIED
  review 6095174408, CI 10/10). Branch deleted post-merge (404 verified).
  Board flip to MERGED rides coordinator board PR #2250 (WATCH251 §B).
- Redeploy executed 2026-11-28 ~08:35–08:38 IST by TP14 under WATCH251 §D
  (standing clearance 7200564540).
- Deployment fact: `/opt/friday_universe` on IntelX-Server (bridge
  server 6, 32.236.185.237) is a static file copy, NOT a git checkout (no
  `.git` within maxdepth 3) — a bare restart could not have deployed the
  fix. The 02:35 UTC service restart was an OOM kill (memory peak
  512.2M vs the 512M cap; systemd auto-restarted under Restart=always),
  not a deploy.
- Pre-deploy check: on-disk `resolution.py` / `lifecycle.py` /
  `scheduler.py` hashed exactly to the PR base blobs (`c69017b5…` /
  `65e7455c…` / `81c12e8b…`) — zero local drift, safe to overwrite. The
  running code had no `FleetForecastDemandResolutionRuleV1` (grep 0).
- Installed the 4 files from merge commit `25aacc52`
  (raw.githubusercontent.com), each hash-verified against the merge blob
  SHAs (`resolution.py 08fed144…`, `lifecycle.py 865d1783…`,
  `scheduler.py 3d66d6bf…`, test `1661ff7e…`). Backups of the 3 replaced
  files in `/tmp/fut043-backup-20261128/`. `py_compile` clean on all
  three.
- Functional smoke test on the deployed tree (venv312 python; no pytest
  on the server): both rules registered (`capacity_exceedance v1.0`,
  `fleet_forecast_demand v1.0`); a fleet forecast against a telemetry
  frame with max 2348.0 resolves to observed **259.0** with
  `rule:fleet_forecast_demand:v1.0`; without a daily-counts frame it
  defers (`ResolutionNotReadyError`); unknown target raises ValueError.
  SMOKE_OK.
- Restart: `sudo -n systemctl restart Futuris.service` exit 0, 03:07:33
  UTC (08:37:33 IST). New MainPID 60746 (was 59466), NRestarts 0,
  active. `/ready` 200 `{status ready, database connected, oracle,
  2.0.0}`. `/health` 503 degraded — UNCHANGED known state
  (NO_MODEL_PROBE; storage 13/13 ok), not a regression. Scheduler loop
  alive under the new PID (`self_assessment ok` 03:08:48, 03:09:51 UTC);
  memory ~202 MB fresh.
- Limits: the fix affects future resolutions only. First fleet outcomes
  stamped `rule:fleet_forecast_demand:v1.0` appear after the next
  lifecycle sweep resolves a matured fleet forecast — check rides the
  next self-check / FUT-044 (TP11) scoring. The 136 historical rows stay
  poisoned (coordinator decision owed on re-resolution, §7). The 02:35
  OOM kill flags a standing fragility: the service hits its 512M cap
  during statsforecast fit storms — same class as FRD-064, no fix in
  this run.

— Muse TP14
