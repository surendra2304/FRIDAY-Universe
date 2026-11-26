# TASK-FUT-035 — Futuris: forecast accuracy scoring run 7

- Task: TASK-FUT-035 (P2, owner muse_13) — score the next unscored forecast
  cohort against outcomes and file the accuracy evidence. Sequel to FUT-034
  (run 6) and FUT-033 (run 5).
- Claim: hub #1483 comment 7193010620, 2026-11-26 ~18:42 IST, on coordinator
  assignment in WATCH160 (hub 7191807363, ~17:55 IST), effective head.
  Branch `muse13/task-fut-035-forecast-scoring-run-7` from main `4a9b0a57`;
  board flip rides in the work PR.
- **Cohort boundary (WATCH160 step 1):** FUT-034's evidence is NOT filed yet
  — no `TASK-FUT-034-EVIDENCE.md` on main, Muse 4 branch null, pr null —
  so per WATCH160 this run scored the oldest unscored cohort per the
  FUT-028 method and names the boundary here: **the oldest unscored cohort
  is empty** — every resolved forecast in the store already has a score
  row. FUT-033 (run 5) likewise has no evidence filed on main.
- Method: all numbers below are first-hand live reads on the shared Oracle
  store via FRIDAY-Server (bridge server 3, `run_shell`) using Futuris's
  own session factory and tracker code — byte-identical to main `4a9b0a57`
  (sha256-verified for `Futuris/futuris/storage/{db,score_repository,
  models}.py` and `Futuris/futuris/services/forecast_tracker.py`).
  Server-3 checkout HEAD `5b245ffd` is stale, but those four files are
  unchanged vs main and the working tree is clean for `Futuris/futuris`.
  No credential read or printed, no service restarted, no deploy, no fleet
  mutation. Probes run 2026-11-26 ~18:48–18:51 IST (13:18–13:21 UTC).
  The `run_shell` route itself was granted by the owner ruling hub
  7192682851 (2026-11-26 18:25 IST, closes approval 7113152293) — the
  grant landed after WATCH160, so no live-service re-slot was needed.
  The scoring sweep (`score_resolved`, idempotent, savepoint-isolated
  per the FUT-025 fix) was armed but did NOT run: the queue was empty.

## 1. Verdict: the unscored cohort is EMPTY — nothing left to score

- `list_unscored_resolved(limit=500)`: **0 rows**. Every resolved forecast
  with a numeric outcome already has a score row.
- Store totals (live, ~18:48 IST): forecasts **1351**, outcomes **896**,
  scores **896**. 896/896 resolved forecasts scored.
- `count_event_only_resolved`: **0**.
- Last scoring batch: **13:03:17 UTC today** (18:33 IST) — the five newest
  score rows all carry 13:03:15–13:03:17 UTC, the prior batch 12:03 UTC,
  so the standing 30-minute `forecast_scoring_job` (FUT-017) is running
  and scoring on schedule.
- No scoring pass ran and no live writes were made: there was nothing to
  score, and the run makes no live change. The deliverable is this
  accuracy evidence.

## 2. Accuracy evidence (calibration report, generated 2026-11-26 13:18:05 UTC)

- n_scored **896**, status **measured** (min_samples 30 met).
- MAE **912.45**, RMSE **1046.53**, nominal level 0.80, coverage_80 **1.0**
  (gap +0.2 vs nominal), mean interval width **8758.19**, Winkler_80
  **9768.92**, mean pct error **46.28%**. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.885045** (n_in_window 896, window
  2026-10-27 → 2026-11-26).
- By nominal level: 0.80 → n=669, coverage 1.0; 0.90 → n=227,
  coverage_90 0.546256 (gap −0.354).
- By evidence class: **synthetic n=793** (coverage_80 1.0); **live n=103**
  (coverage_90 0.0 — see §3).
- By target (n): `service:checkout:capacity_exceedance_24h` 110,
  `trading:BTCUSDT:price_variance_24h` 104,
  `friday:fleet:forecast_demand_24h` 103,
  `trading:ETHUSDT:price_variance_24h` 97,
  `trading:SOLUSDT:price_variance_24h` 96, `macro:SPY` 93,
  `macro:DGS10` 88, `macro:T10Y2Y` 88, `macro:UNRATE` 88, `BTCUSDT` 8,
  `ETHUSDT` 7, `NIFTY` 8, `my portfolio` 4,
  `fleet:api:request_rate` 1, `what should i watch in indian markets` 1.
  Total 896.
- Change since run 3 (Nov 25 ~06:36 IST): +362 forecasts (989→1351),
  +254 outcomes/scores (642→896); MAE 968.70→912.45,
  RMSE 1104.32→1046.53, hit-rate 0.88474→0.885045.

## 3. Headline finding: the only live-scored target is entirely out of interval

- The live class is a single target: `friday:fleet:forecast_demand_24h`
  (n=103, was 53 in run 2, 74 in run 3, nominal 0.90): coverage_90 **0.0**,
  MAE **2059.76**, RMSE 2067.88, mean interval width **89.26**,
  Winkler_90 **40389.60**, mean pct error **92.19%**.
- Its 90% intervals (~89 wide) are ~23x narrower than its errors
  (~2060) — all 103 live scores missed. The aggregate 0.885 hit-rate is
  carried by the 793 synthetic scores; the live leg is miscalibrated on
  its only target. Follow-up for the coordinator (carried from runs 2–3,
  still open): widen / recalibrate the `friday:fleet:forecast_demand_24h`
  intervals, or confirm the target's actuals feed is sane.

## 4. Resolution gap: 223 matured forecasts have no outcome at all (was 165)

- **455** forecasts have no outcome row (was 347); of those **223 are
  matured** (expires_at already passed) but unresolved — oldest
  2026-11-21 18:48 UTC (`service:checkout:capacity_exceedance_24h`,
  forecast `1140e21f-8bab-4584-afa4-eacd5157f5a8`) — the same oldest row
  as run 3, so the backlog is growing, not resolving.
- By target: `intelx:research:finding_volume_24h` **103**,
  `vyralx:trends:topic_volume_24h` **101** (the two hourly recurring jobs
  are 204 of 223), `service:checkout:capacity_exceedance_24h` 2, plus 9
  singletons across other targets.
- These can never enter the scoring queue until the outcome-recording
  sweep records their outcomes. This is a resolution gap, not a scoring
  gap — the scoring job is healthy; the sweep that records outcomes for
  these recurring targets is not keeping up. (FUT-025 already filed that
  the lifecycle sweep is not wired on main; this run quantifies the
  backlog: 223, +58 since run 3.) Follow-up, not fixed here — no code
  change in this task.

## 5. Service state (live, ~18:50 IST)

- Futuris lives on bridge server 6 (AWS `ip-172-26-4-138`): `uvicorn
  futuris.api.app` on port 8004, PID 35287, started 06:32 UTC today.
- `/health`: status `degraded` — storage ok (13/13 required tables
  present); forecasting `unknown` (no forecasting-model probe exists).
  Honest degradation per the OBS-016 verdict, not a failure.
- The future-`resolved_at` anomaly from run 2 stays gone: max
  `OutcomeModel.resolved_at` is 2026-11-26 13:03:11 UTC, 0 rows in the
  future at probe time (13:20:55 UTC).
- FUT-032 note: its scoring leg was blocked on S2 `Futuris/.env`
  missing / no DATABASE_URL. This run's route (FRIDAY-Server, server 3:
  `Futuris/.env` present, tracker code byte-identical to main) works;
  the S2 route remains untested.

## 6. States

- implemented YES (evidence filed in this doc) / tested YES (all numbers
  first-hand live reads, plus the conditional sweep armed and correctly
  not fired) / merged NO (work PR open, awaiting Muse) / deployed N/A
  (no code change; no live change made) / production-verified N/A (the
  scoring job is already running on server 6; verified by fresh rows,
  not by this task).

— Muse 13
