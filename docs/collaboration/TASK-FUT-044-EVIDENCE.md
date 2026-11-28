# TASK-FUT-044 — Futuris forecast quality: oldest unscored forecasts scored (checkpoint 1)

- Task: TASK-FUT-044 (P1, owner muse_tp6) — score the oldest unscored forecasts
  against outcomes; accuracy evidence filed; last 3 scheduler cycles verified
  producing real forecasts. Standing backlog POOL 7(vi) follow-up.
- Claim: hub #2045 comment 7235177877, 2026-11-28 ~11:47 IST (pool pull, P1,
  AVAILABLE owner-null on main 42ba9151; WATCH259 correction leaves it in the
  pool; verdict column 4 awaiting, below cap). Branch
  `musetp6/task-fut-044-forecast-quality-scoring` from main `42ba9151`.
- Service: Futuris on IntelX-Server (bridge server 6, 32.236.185.237:8004,
  PID 63602, port 8004). Probed 2026-11-28 ~06:14–06:35 UTC / 11:44–12:05 IST.
- Method: `scripts/run_forecast_tracker.py` (report, no flags) on IntelX-Server
  via the service's own venv312 + EnvironmentFile, and read-only drill scripts
  through Futuris's own session factory (same route as FUT-043/FUT-045).
  No service change, no restart by this task.

## 0. Verdict

- **Unscored queue is 0** — the scheduler's own 30-minute scoring job keeps it
  drained, as in FUT-045. There is no unscored oldest batch to score; the
  "oldest batch" is therefore the oldest scheduler-scored batch, reported
  below (FUT-045 precedent: "both tasks report on scheduler-scored batches").
- **Oldest batch (oldest 100 scored rows): MAE 597.53, hit rate 0.97** — but
  the shape is the known split: non-fleet rows hit 1.0 (vacuously wide
  intervals), fleet rows hit 0.0. Live report: n_scored 1269, MAE 875.87,
  verdict "underconfident".
- **The FUT-043 fix has not yet scored a single live fleet row.** All 139
  fleet outcomes still carry `rule:capacity_exceedance:v1.0`; zero carry
  `rule:fleet_forecast_demand:v1.0`. Newest fleet score resolved 03:06 UTC,
  before the 03:07:44 UTC redeploy. Three fleet forecasts matured 03:33 /
  04:33 / 05:33 UTC and sit ACTIVE (deferred by design — the expiry day is
  still in progress); they resolve after Nov 29 00:00 UTC.
- **Unresolved backlog grew: 328 matured forecasts with no outcome row**
  (was 292 per FUT-042/FUT-043 §7). Post-redeploy, 8 targets stopped
  resolving entirely — the FUT-043 "refuse rather than mis-resolve" change
  means trading/macro targets now fail every sweep with "No resolution rule".
- **Last 3 scheduler cycles: PASS with one OOM noted.** Scoring cycles
  05:10 / 05:40 / 06:10 UTC all executed successfully; refresh cycles
  produced real forecasts (newest forecast 06:16:12 UTC). The 05:10 cycle
  was interrupted by a second Futuris OOM kill today (05:10:33 UTC);
  systemd auto-restarted in 6 s (new PID 63602, healthy since).

## 1. Scoring sweep (this run)

Census (`list_unscored_resolved`, oldest-first) 06:20 UTC:

- **Unscored: 0. Event-only resolved: 0.** No `--score` sweep needed (a sweep
  would consider 0, as the 06:10:58 UTC scheduler run did — see §3).
- Live calibration report (generated 2026-11-28T06:20:16Z, service's own
  tracker): n_scored **1269** (FUT-045 had 1266 at ~08:50 IST — +3 since,
  all `service:checkout:capacity_exceedance_24h`, resolved 03:37 / 04:40 /
  05:41 UTC, all interval hits), MAE 875.87, RMSE 995.19, coverage_80 1.0,
  mean pct error 50.71%, verdict **"underconfident"**, rolling 30d hit rate
  0.890465 (n 1269, measured).
- Live fleet line `friday:fleet:forecast_demand_24h`: n **139**, MAE 1909.31,
  RMSE 1932.67, coverage_90 **0.0**, mean pct error 90.50%, mean interval
  width 98.87. Unchanged from FUT-045 — the stored score rows are the old
  poisoned ones (FUT-043 §7), and no post-redeploy fleet row exists yet.

## 2. Oldest batch accuracy (oldest 100 scored rows, by scored_at)

Oldest scored rows start 2026-11-20 19:45 UTC (the tracker's first backfill).
Oldest 10 rows: all interval hits — NIFTY/BTCUSDT/ETHUSDT predictions
~1899–1921 vs observed 2318.0; synthetic rows prediction 875.12 vs observed
699.99. Aggregates over the oldest 100:

| Scope | n | MAE | Interval hit rate | Mean pct error |
|---|---|---|---|---|
| All | 100 | 597.53 | 0.97 | 56.25% |
| Live fleet (`friday:fleet:forecast_demand_24h`) | 3 | 2006.44 | **0.0** | 100% (predictions 0.0 on the early ramp, FUT-043 §5) |
| Other (synthetic + capacity) | 97 | 553.96 | 1.0 | 54.90% |

Same shape as FUT-016/FUT-045: synthetic rows hit 1.0 on ~9500-wide
intervals; live fleet rows miss 0.0. The oldest batch adds no new signal
beyond confirming the pattern holds back to the first scored rows.

## 3. Fleet rule: zero rows under the new rule (the FUT-043 live-effect check)

- Fleet outcome rule census (all 139 fleet outcomes):
  `rule:capacity_exceedance:v1.0`: **139**; `rule:fleet_forecast_demand:v1.0`: **0**.
- Newest 8 fleet scores: all capacity-rule, predictions 243.70 / 268.59 vs
  observed 1701.61–1770.95, all misses; newest resolved 03:06:04 UTC,
  scored 03:06:11 UTC — minutes BEFORE the 03:07:44 UTC redeploy.
- Fleet status census: active 27, resolved 139. Expired fleet forecasts:
  142 total = 139 resolved + **3 matured with no outcome** (as_of 03:33 /
  04:33 / 05:33 UTC Nov 27, expires 03:33 / 04:33 / 05:33 UTC Nov 28,
  prediction 268.59, status `active`). These are the FUT-043 deferral
  working as designed: the fleet rule raises `ResolutionNotReadyError`
  while the expiry day (Nov 28) is incomplete, so the forecasts stay
  ACTIVE and resolve after Nov 29 00:00 UTC, when the Nov 28 daily count
  is complete. First honestly-scored fleet rows land Nov 29 at the
  earliest — re-probe then; do not claim the fix is live in scoring yet.

## 4. Unresolved backlog: 328 matured forecasts with no outcome (+36)

Matured (`expires_at` < now) forecasts with no outcome row, by target/status
(drill 06:30 UTC; FUT-042/FUT-043 §7 had 292):

- `intelx:research:finding_volume_24h`: 142, status `insufficient_data`.
- `vyralx:trends:topic_volume_24h`: 140, status `insufficient_data`.
- 8 hourly targets × 3, status `active`: macro:SPY, macro:DGS10,
  macro:UNRATE, macro:T10Y2Y, trading:BTCUSDT, trading:ETHUSDT,
  trading:SOLUSDT, `friday:fleet:forecast_demand_24h` (the 3 fleet rows
  from §3) — 24 total.
- `service:checkout:capacity_exceedance_24h`: 2, status `draft`.
- 20 singletons, status `insufficient_data` (forge/memora/cortex/sentinel/
  inference/friday/market/intelx targets, 1 each).
- **Total: 328.**

The 24 `active` rows are the post-redeploy effect: the 06:11:03 UTC
calibration sweep logged `calibration_resolve_failed` for exactly these
targets — "No resolution rule for target '...': refusing to resolve
against another target's rule (see TASK-FUT-043)". The FUT-043 fix
stopped mis-resolution, but it also stopped ALL resolution for every
target without a rule (everything except fleet + capacity). Those
targets' matured forecasts now pile up ~1/hour/target unresolved, and
the live calibration lines for them are frozen at pre-03:07 UTC data.
Named follow-up for the coordinator: either write resolution rules for
the trading/macro targets or rule the backlog acceptable — the pile
grows ~8/hour while the sweeps keep refusing.

## 5. Last 3 scheduler cycles — real forecasts produced (PASS with OOM noted)

Journal (`journalctl -u Futuris.service`, PID 63602 unless noted):

- **05:10 UTC cycle:** forecast_refresh_job started 05:10:04 (PID 62662);
  forecast_scoring_job completed 05:10:10 (considered 0, scored 0,
  n_scored_total 1268); universe_provider_refresh completed 05:10:28
  (generated=3, active=1). **05:10:33 — Futuris.service killed by the
  OOM killer** (main process exited, code=killed, status=9/KILL, result
  `oom-kill`, 197.8M memory peak per systemd); auto-restarted 05:10:39,
  new PID 63602, application startup complete 05:10:52. Second Futuris
  OOM today (first 02:35 UTC at 512.2M peak, FUT-045 §3). Flagged for
  FUT-047 (fit-cost cap check) — the cap has not yet been shown to bind
  before the backstop.
- **05:40 UTC cycle:** forecast_scoring_job completed 05:40:59
  (considered 0, scored 0, n 1268) and 05:41:08 (considered 1, scored 1,
  n 1269 — the 05:41 capacity row). Clean under the new process.
- **06:10 UTC cycle:** lifecycle_sweep_job + calibration_sweep_job +
  forecast_scoring_job started 06:10:52, all executed successfully;
  forecast_scoring_job completed 06:10:58 (considered 0, scored 0,
  n_scored_total 1269, rolling hit rate 0.890465 — matches this run's
  live report exactly); ingest_job completed 06:10:54 (points=289);
  forecast_refresh_job started 06:10:52, universe_provider_refresh
  completed 06:11:13 (generated=3, active=1), refresh executed
  successfully 06:16:13.
- Forecast production (store counts): 2026-11-23: 160, 11-24: 251,
  11-25: 235, 11-26: 259, 11-27: 322, 11-28: 49 (partial day, by 06:20
  UTC); newest forecast created **06:16:12 UTC**; total forecasts 1843
  (was 1794 in FUT-043). Real forecasts are being produced in all three
  cycles.

## 6. Service state (live, this run)

- `/ready` 200: status `ready`, database `connected`, backend `oracle`,
  version 2.0.0 (observed 2026-11-28T06:14:17Z / 11:44:17 IST, and again
  via run_shell on IntelX-Server).
- `/health`: status `degraded` — the known state (NO_MODEL_PROBE;
  storage ok 13/13, database ok). Unchanged from FUT-042/FUT-043.
- Bridge route verified first-hand this run: run_shell server 6
  (IntelX-Server, ip-172-26-4-138) + server 3 (FRIDAY-Server checkout
  main 06ff9ee6) both OK; Futuris.service active running.

## 7. States

implemented N/A (evidence task) / tested YES (census + report + drills +
journal run first-hand) / merged NO (work PR open, awaiting Muse) /
deployed N/A / production-verified YES for the scoring-state, oldest-batch
and last-3-cycles claims above (live store read through the service's own
storage layer; no service change, no restart by this task).

## 8. Follow-ups (honest, not this task's scope)

- Re-probe Nov 29: first fleet rows under `rule:fleet_forecast_demand:v1.0`
  (the 3 deferred rows + newly maturing); the live fleet coverage_90
  should move off 0.0 then — or the deferral is itself stuck.
- Coordinator call: resolution rules for the 8 trading/macro targets, or
  accept the ~8/hour unresolved pile (§4).
- FUT-047 (fit-cost cap): second OOM today (05:10 UTC) is its evidence —
  the cap still has not been shown to bind before the backstop.

— Muse TP6, 2026-11-28 ~12:05 IST
