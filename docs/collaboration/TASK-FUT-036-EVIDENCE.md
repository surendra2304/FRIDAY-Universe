# TASK-FUT-036 — Futuris: forecast accuracy scoring run 8

- Task: TASK-FUT-036 (P2, owner muse_tp12) — score the next unscored forecast
  cohort against outcomes and file the accuracy evidence. Sequel to FUT-035
  (run 7) and FUT-034 (run 6). New POOL 9 record (WATCH171).
- Claim: hub #1483 comment 7197148698, 2026-11-26 ~21:35 IST, on coordinator
  assignment in WATCH171 (hub 7197061449). Branch
  `musetp12/task-fut-036-forecast-scoring-run-8` from main `0c89b38b`;
  board flip rides in the work PR.
- **Status of this doc: LIVE PROBES RUN — run 8 measured fresh on
  2026-11-26 ~23:22 IST (17:52–17:53 UTC). All numbers in §2–§5 are
  first-hand live measurements from the shared Oracle store. The CARRIED
  values from runs 6/7 in the checkpoint-1 version are replaced below,
  not carried forward.**

## 1. Method verified on main `0c89b38b` (first-hand, repo-side)

- Scoring code read from the live main blob (git blobs API), byte-for-byte
  the files runs 6/7 used:
  - `Futuris/futuris/services/forecast_tracker.py` (21,842 bytes,
    sha256 `2b429615cbcfcfe0200d89ef476ee23b246e5459cd912bc0c4626a29f59ea3c2`)
  - `Futuris/futuris/storage/db.py` (8,014 bytes,
    sha256 `4d945dcd24e5d2befc115756a1f35cd2390e112f44e2cdadac72bed286e75b2a`)
  - `Futuris/futuris/storage/models.py` (18,727 bytes,
    sha256 `16794c0f7b2d38aacee6d8bf593c9fb6f0f9818bbefca5f5328a6766d72d57b3`)
  - `Futuris/futuris/storage/score_repository.py` (4,791 bytes,
    sha256 `39ed9216a37a3f585729486efa4e9d9389d43c430a3ef7a4d9dc9af9f62e3af5`)
- Entry points (same FUT-028/033 method as runs 5–7):
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
- Live route actually used (run 8, 2026-11-26 ~23:22 IST): first-hand live
  reads on the shared Oracle store via FRIDAY-Server (bridge server 3,
  `run_shell`) using Futuris's own session factory and tracker code.
  The four files above were sha256-verified byte-identical on the
  server-3 checkout (`/opt/friday_universe/Futuris`) before any probe
  ran — all four hashes match main `0c89b38b` exactly. Probes ran as
  `/opt/friday_universe/venv312/bin/python` with
  `PYTHONPATH=/opt/friday_universe/Futuris` from the Futuris checkout
  (the service venv; `DATABASE_URL` comes from the checkout `.env` via
  the settings class — no credential read or printed). No service
  restarted, no deploy, no fleet mutation. Probe script kept at
  `/tmp/fut036_probe.py` on server 3 and in the task workspace.

## 2. Run 8 measurements — FRESH (2026-11-26 17:52–17:53 UTC)

- Unscored cohort: `list_unscored_resolved(limit=500)` returned **0 rows**.
  The sweep was armed but did NOT run (per plan: empty queue means no
  sweep). The standing 30-minute `forecast_scoring_job` (FUT-017) has
  already scored everything resolved so far.
- Store totals: forecasts **1406** (run 7: 1351; run 6: 1362), outcomes
  **916**, scores **916**, `count_event_only_resolved` **0**. Last scoring
  batch (max `scored_at`): **2026-11-26 17:03:33.766891+00:00**.
- Fresh calibration report (`generated_at_utc` 2026-11-26T17:52:54Z,
  status `measured`, verdict `underconfident`): n_scored **916**,
  MAE **909.207445**, RMSE **1042.715719**, nominal level 0.8,
  coverage_80 **1.0**, coverage gap vs nominal 0.2, mean interval width
  8750.781932, Winkler-80 9785.820628, mean pct error 46.231647.
  Rolling 30-day hit-rate **0.883188** (window 2026-10-27T17:03:33Z to
  2026-11-26T17:03:33Z, n_in_window 916). By nominal level: 0.80 n=685
  coverage_80 1.0; 0.90 n=231 coverage_90 0.536797.
- Run 7 comparison (same method, carried only for the delta): n_scored
  896 → **916** (+20, scored by the standing job since run 7), MAE
  912.45 → 909.21, RMSE 1046.53 → 1042.72, rolling hit-rate 0.885045 →
  0.883188. Coverage_80 still 1.0; verdict still underconfident.
- By-target (fresh, n / MAE / RMSE / coverage): BTCUSDT 8 / 635.33 /
  655.33 / 1.0; ETHUSDT 7 / 686.06 / 705.95 / 1.0; NIFTY 8 / 650.22 /
  675.31 / 1.0; fleet:api:request_rate 1 / 299.31 / 299.31 / 1.0;
  friday:fleet:forecast_demand_24h 107 / 2038.88 / 2049.52 / coverage_90
  0.0; macro:DGS10:yield_shift_30d 90 / 788.42 / 841.51 / 1.0;
  macro:SPY:return_exceedance_24h 95 / 771.68 / 827.79 / 1.0;
  macro:T10Y2Y:curve_inversion_30d 90 / 788.42 / 841.51 / 1.0;
  macro:UNRATE:unemployment_drift_90d 90 / 788.42 / 841.51 / 1.0;
  my portfolio 4 / 1692.04 / 1693.91 / 1.0;
  service:checkout:capacity_exceedance_24h 112 / 709.90 / 780.22 / 1.0;
  trading:BTCUSDT:price_variance_24h 106 / 727.03 / 794.38 / 1.0;
  trading:ETHUSDT:price_variance_24h 99 / 751.75 / 813.59 / 1.0;
  trading:SOLUSDT:price_variance_24h 98 / 753.54 / 815.66 / 1.0;
  "what should i watch in indian markets" 1 / 1493.77 / 1493.77 / 1.0.
- Live evidence class (`evidence_class="live"`, fresh): n_scored **107**,
  status `measured`, verdict `overconfident`, MAE **2038.87729**, RMSE
  **2049.524971**, nominal level 0.9, coverage_90 **0.0**, coverage gap
  vs nominal −0.9, mean interval width 90.623925, Winkler-90
  39959.668785, mean pct error 91.947007. This is the live class
  `friday:fleet:forecast_demand_24h` (n=103 in run 7 → 107 now);
  intervals remain ~23x narrower than errors.

## 3. Resolution gap — FRESH (2026-11-26 17:52 UTC)

- Forecasts with no outcome row: **490** total; **231 matured**
  (run 7: 223 matured). Matured = `as_of + horizon` already passed.
- By target (matured): `vyralx:trends:topic_volume_24h` 105,
  `intelx:research:finding_volume_24h` 107, and 19 targets with 1 each
  (cortex:execution:sla_breach_probability_24h,
  forge:deployment:regression_risk_24h,
  cortex:subagent:concurrency_thrashing_risk_24h,
  memora:storage:capacity_exhaustion_days,
  memora:vector_index:retrieval_latency_spike_24h,
  forge:ci_cd:pipeline_failure_risk_24h,
  inference:gpu:vram_oom_probability_24h,
  friday:orchestration:system_health_24h,
  sentinel:security:threat_anomaly_risk_24h,
  intelx:research:topic_velocity_surge_24h,
  market:crypto:BTCUSDT:volatility_24h,
  service:checkout:capacity_exceedance_24h (2),
  friday:eventbus:message_backlog_24h,
  intelx:source:rate_limit_depletion_24h,
  sentinel:ratelimit:api_saturation_risk_24h,
  market:crypto:ETHUSDT:volatility_24h,
  inference:queue:token_starvation_risk_24h,
  market:crypto:portfolio:drawdown_risk_24h).
  The two hourly recurring targets still dominate (212 of 231).
- Oldest matured row: `1140e21f-8bab-4584-afa4-eacd5157f5a8`,
  `service:checkout:capacity_exceedance_24h`,
  as_of 2026-11-20T18:48:01.997576+00:00 — the same oldest row as run 7,
  still unresolved.
- Resolution gap, not a scoring gap — the scoring job is healthy
  (unscored cohort empty, last batch 17:03 UTC); the outcome-recording
  sweep is not keeping up (FUT-025: lifecycle sweep not wired on main).
- Data-quality check: outcomes with `resolved_at` in the future: **0**.

## 4. Service state — FRESH (2026-11-26 17:53 UTC)

- Futuris on bridge server 6, `GET /health`: HTTP **503**,
  status `degraded`, version 2.0.0, observed 2026-11-26T17:53:22Z.
- Storage: ok (live schema inspection, 13/13 required tables present).
  Database: ok (live round-trip + all required tables present).
- Forecasting capability: `unknown` (`NO_MODEL_PROBE` — no
  forecasting-model probe exists; storage readiness is not forecasting
  ability). The 503 is the missing model probe, not a storage failure.
- The scoring job itself runs on the scheduler and the store is healthy;
  the service being `degraded` does not change the run-8 measurements.

## 5. Notes and follow-ups

- The `--report-only` flag of `scripts/run_forecast_tracker.py` returns
  `{}` by construction (its guard only prints the report when scoring
  ran or the flag is absent); the plain no-flag invocation prints the
  report. Run 8 used the no-flag invocation plus the probe script.
- System python3 on server 3 cannot import the Futuris package; the
  probes must run under `/opt/friday_universe/venv312/bin/python` with
  `PYTHONPATH=/opt/friday_universe/Futuris` from the Futuris checkout.
- The validator failure on this PR (branch roster lacked `muse_tp12`
  because roster PR #1999 was unmerged) is resolved: #1999 MERGED
  (head `ccd86d6c`); `muse_tp12` is on main's roster. This branch was
  rebased onto main `50c870af` 2026-11-27 ~03:20 IST (WATCH183 §2a); the
  board hunk was dropped in the rebase because the FUT-036 board record
  already rides on main (coordinator WATCH181 flip: IN_REVIEW, pr 2000)
  — board flips ride in board PRs, not work PRs.

## 6. States (run 8 complete)

- implemented COMPLETE (method verified on main, probes run live,
  fresh numbers filed) / tested COMPLETE (live probes, fresh
  measurements, no sweep needed — cohort empty) / merged NO (work PR
  #2000 open, awaiting Muse; paired verification requested) /
  deployed N/A (no code change; no live change made) /
  production-verified YES (live store measured first-hand 2026-11-26
  17:52–17:53 UTC; evidence is the measurement itself, filed in this
  doc; merge pending).

— Muse TP12
