# TASK-FUT-037 — Futuris: forecast accuracy scoring run 7

- Task: TASK-FUT-037 (P2, owner muse_tp12) — score the next unscored forecast
  cohort against outcomes and file the accuracy evidence. Sequel to FUT-034
  (run 6, MERGED) and FUT-036 (run 8). Pool-floor feedstock.
- Claim: hub #1483 comment 7200350235, 2026-11-26 ~23:51 IST, on coordinator
  assignment in WATCH177 (hub 7200280447). Branch
  `musetp12/task-fut-037-forecast-scoring-run-7`, fast-forwarded to main
  `50c870af` before filing (zero unique commits at rebase; branch created
  from main `b74efa00`); board flip rides in the work PR.
- Live leg cleared by coordinator ruling WATCH183 §2a (hub 7203117194,
  2026-11-27 ~02:20 IST): the "no live legs until ruled" hold (hub
  7202446201) is answered on the hub, the authorized channel — grant
  settled (owner approval 2026-11-26 18:25:56 IST; rulings 7192682851,
  7193378286, 7197725825, 7200414167; standing clearance 7200564540).
  Run 7 measured live under that clearance.
- **Status of this doc: LIVE PROBES RUN — run 7 measured fresh on
  2026-11-27 ~02:46 IST (21:16–21:17 UTC). All numbers in §2–§4 are
  first-hand live measurements from the shared Oracle store.**

## 1. Method verified on main `50c870af` (first-hand, repo-side)

- Scoring code read from live main, byte-for-byte the files runs 6/8 used
  (identical sha256 to the run-8 verification on main `0c89b38b` — the
  scoring code is unchanged):
  - `Futuris/futuris/services/forecast_tracker.py` (21,842 bytes,
    sha256 `2b429615cbcfcfe0200d89ef476ee23b246e5459cd912bc0c4626a29f59ea3c2`)
  - `Futuris/futuris/storage/db.py` (8,014 bytes,
    sha256 `4d945dcd24e5d2befc115756a1f35cd2390e112f44e2cdadac72bed286e75b2a`)
  - `Futuris/futuris/storage/models.py` (18,727 bytes,
    sha256 `16794c0f7b2d38aacee6d8bf593c9fb6f0f9818bbefca5f5328a6766d72d57b3`)
  - `Futuris/futuris/storage/score_repository.py` (4,791 bytes,
    sha256 `39ed9216a37a3f585729486efa4e9d9389d43c430a3ef7a4d9dc9af9f62e3af5`)
- Entry points (same FUT-028/033 method as runs 5–8):
  - `ForecastScoreRepository.list_unscored_resolved(limit=500)` —
    resolved forecast/outcome pairs with no score row, oldest first,
    numeric `observed_value` only (`score_repository.py:37`).
  - `ForecastTracker.score_resolved(limit=500)` — idempotent, one insert
    per forecast inside its own savepoint (FUT-025 fix); the sweep's
    `scored` count is only the rows this run inserted
    (`forecast_tracker.py:445`).
  - `ForecastScoreRepository.count_event_only_resolved()` — resolved
    outcomes with no numeric actual, never numerically scorable
    (`score_repository.py:70`).
  - `ForecastTracker.calibration_report()` and `rolling_hit_rate()` —
    calibration + 30-day hit-rate over scored rows
    (`forecast_tracker.py:490` and rolling-hit-rate method).
- Live route actually used (run 7, 2026-11-26 21:16–21:17 UTC): first-hand
  live reads on the shared Oracle store via FRIDAY-Server (bridge server 3,
  `run_shell`) using Futuris's own session factory and tracker code.
  The four files above were sha256-verified byte-identical on the
  server-3 checkout (`/opt/friday_universe/Futuris`) before any probe
  ran — all four hashes match main `50c870af` exactly. Probes ran as
  `/opt/friday_universe/venv312/bin/python` with
  `PYTHONPATH=/opt/friday_universe/Futuris` from the Futuris checkout
  (the service venv; `DATABASE_URL` comes from the checkout `.env` via
  the settings class — no credential read or printed). No service
  restarted, no deploy, no fleet mutation. Probe script
  `/tmp/fut036_probe.py` on server 3 (sha256
  `d017df1ba8fd0de8d0af251440e87b2b7b4126685c8d82a862bc56f79bbd4654`,
  verified identical to the workspace copy before the run).
  Server-3 checkout at probe time: HEAD `5b245ffd`, branch `main`, with
  uncommitted `FRIDAY/ui/out/*` modifications belonging to another agent
  — left untouched; probes read only.

## 2. Run 7 measurements — FRESH (2026-11-26 21:16 UTC)

- Unscored cohort: `list_unscored_resolved(limit=500)` returned **0 rows**.
  The sweep was armed but did NOT run (per plan: empty queue means no
  sweep). The standing 30-minute `forecast_scoring_job` (FUT-017) has
  already scored everything resolved so far.
- Store totals: forecasts **1439** (run 8: 1406), outcomes **952**,
  scores **952**, `count_event_only_resolved` **0**. Last scoring
  batch (max `scored_at`): **2026-11-26 21:03:32.189981+00:00**.
- Fresh calibration report (`generated_at_utc` 2026-11-26T21:16:29Z,
  status `measured`, verdict `underconfident`): n_scored **952**,
  MAE **912.623782**, RMSE **1041.745587**, nominal level 0.8,
  coverage_80 **1.0**, coverage gap vs nominal 0.2, mean interval width
  8719.714968, Winkler-80 9746.494407, mean pct error 46.678458.
  Rolling 30-day hit-rate **0.883403** (window 2026-10-27T21:03:32Z to
  2026-11-26T21:03:32Z, n_in_window 952). By nominal level: 0.80 n=717
  coverage_80 1.0; 0.90 n=235 coverage_90 0.52766.
- Run 8 comparison (same method, carried only for the delta): n_scored
  896 → 916 (run 8) → **952** (+36 scored by the standing job since run 8),
  MAE 909.21 → 912.62, RMSE 1042.72 → 1041.75, rolling hit-rate
  0.883188 → 0.883403. Coverage_80 still 1.0; verdict still underconfident.
- By-target (fresh, n / MAE / RMSE / coverage): BTCUSDT 8 / 635.33 /
  655.33 / 1.0; ETHUSDT 7 / 686.06 / 705.95 / 1.0; NIFTY 8 / 650.22 /
  675.31 / 1.0; fleet:api:request_rate 1 / 299.31 / 299.31 / 1.0;
  friday:fleet:forecast_demand_24h 111 / 2018.37 / 2031.51 / coverage_90
  0.0; macro:DGS10:yield_shift_30d 94 / 794.90 / 846.17 / 1.0;
  macro:SPY:return_exceedance_24h 99 / 778.51 / 832.85 / 1.0;
  macro:T10Y2Y:curve_inversion_30d 94 / 794.90 / 846.17 / 1.0;
  macro:UNRATE:unemployment_drift_90d 94 / 794.90 / 846.17 / 1.0;
  my portfolio 4 / 1692.04 / 1693.91 / 1.0;
  service:checkout:capacity_exceedance_24h 116 / 717.86 / 786.48 / 1.0;
  trading:BTCUSDT:price_variance_24h 110 / 734.80 / 800.35 / 1.0;
  trading:ETHUSDT:price_variance_24h 103 / 759.09 / 819.09 / 1.0;
  trading:SOLUSDT:price_variance_24h 102 / 760.89 / 821.12 / 1.0;
  "what should i watch in indian markets" 1 / 1493.77 / 1493.77 / 1.0.
- Live evidence class (`evidence_class="live"`, fresh): n_scored **111**,
  status `measured`, verdict `overconfident`, MAE **2018.371982**, RMSE
  **2031.513234**, nominal level 0.9, coverage_90 **0.0**, coverage gap
  vs nominal −0.9, mean interval width 91.89009, Winkler-90
  39538.248649, mean pct error 91.711543. This is the live class
  `friday:fleet:forecast_demand_24h` (n=107 in run 8 → 111 now);
  intervals remain ~22x narrower than errors.

## 3. Resolution gap — FRESH (2026-11-26 21:16 UTC)

- Forecasts with no outcome row: **487** total; **239 matured**
  (run 8: 231 matured). Matured = `as_of + horizon` already passed.
- By target (matured): `vyralx:trends:topic_volume_24h` 109,
  `intelx:research:finding_volume_24h` 111,
  `service:checkout:capacity_exceedance_24h` 2, and 17 targets with 1 each
  (cortex:execution:sla_breach_probability_24h,
  forge:deployment:regression_risk_24h,
  cortex:subagent:concurrency_thrashing_risk_24h,
  memora:storage:capacity_exhaustion_days,
  memora:vector_index:retrieval_latency_spike_24h,
  forge:ci_cd:pipeline_failure_risk_24h,
  inference:gpu:vram_oom_probability_24h,
  friday:orchestration:system_health_24h,
  sentinel:security:threat_anomaly_risk_24h,
  friday:eventbus:message_backlog_24h,
  sentinel:ratelimit:api_saturation_risk_24h,
  market:crypto:BTCUSDT:volatility_24h,
  intelx:research:topic_velocity_surge_24h,
  intelx:source:rate_limit_depletion_24h,
  market:crypto:ETHUSDT:volatility_24h,
  market:crypto:portfolio:drawdown_risk_24h,
  inference:queue:token_starvation_risk_24h).
  The two hourly recurring targets still dominate (220 of 239).
- Oldest matured row: `1140e21f-8bab-4584-afa4-eacd5157f5a8`,
  `service:checkout:capacity_exceedance_24h`,
  as_of 2026-11-20T18:48:01.997576+00:00 — the same oldest row as runs 7/8,
  still unresolved.
- Resolution gap, not a scoring gap — the scoring job is healthy
  (unscored cohort empty, last batch 21:03 UTC); the outcome-recording
  sweep is not keeping up (FUT-025: lifecycle sweep not wired on main).
- Data-quality check: outcomes with `resolved_at` in the future: **0**.

## 4. Service state — FRESH (2026-11-26 21:17 UTC)

- Futuris on bridge server 6, `GET /health`: HTTP **503**,
  status `degraded`, version 2.0.0, observed 2026-11-26T21:17:22Z.
- Storage: ok (live schema inspection, 13/13 required tables present).
  Database: ok (live round-trip + all required tables present).
- Forecasting capability: `unknown` (`NO_MODEL_PROBE` — no
  forecasting-model probe exists; storage readiness is not forecasting
  ability). The 503 is the missing model probe, not a storage failure.
- Service process: `uvicorn futuris.api.app` on port 8004, PID 35287,
  started 06:32 UTC — same process as run 8.
- The scoring job itself runs on the scheduler and the store is healthy;
  the service being `degraded` does not change the run-7 measurements.

## 5. Notes and follow-ups

- The `--report-only` flag of `scripts/run_forecast_tracker.py` returns
  `{}` by construction (its guard only prints the report when scoring
  ran or the flag is absent); the plain no-flag invocation prints the
  report. Run 7 used the probe script (same as run 8).
- System python3 on server 3 cannot import the Futuris package; the
  probes must run under `/opt/friday_universe/venv312/bin/python` with
  `PYTHONPATH=/opt/friday_universe/Futuris` from the Futuris checkout.
- Roster PR #1999 is MERGED (head `ccd86d6c`); `muse_tp12` is on main's
  `TEAM_ROSTER.yaml` — the roster-validator block that held PR #2000 is
  gone. PR #2000 rebase onto current main is owed separately (WATCH183
  §2a) and is not part of this PR.

## 6. States (run 7 complete)

- implemented COMPLETE (method verified on main, probes run live,
  fresh numbers filed) / tested COMPLETE (live probes, fresh
  measurements, no sweep needed — cohort empty) / merged NO (work PR
  open, awaiting Muse; paired verification requested) /
  deployed N/A (no code change; no live change made) /
  production-verified YES (live store measured first-hand 2026-11-26
  21:16–21:17 UTC; evidence is the measurement itself, filed in this
  doc; merge pending).

— Muse TP12
