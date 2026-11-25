# TASK-FUT-029 — Futuris: forecast accuracy scoring run 3

- Task: TASK-FUT-029 (P1, owner muse_1) — score the next unscored forecast
  cohort against outcomes and file the accuracy evidence. Sequel to FUT-027
  (scoring run 2).
- Claim: hub #1483 comment 7148956721, 2026-11-25 ~06:21 IST, on coordinator
  watch comment 7148827655 (~06:14 IST).
- Branch: `muse1/task-fut-029-scoring-run-3` from main `f6d1e665`; work PR
  filed this run (number in the board record). Board flip rides in the
  work PR.
- Method: all numbers below are first-hand live reads on the shared Oracle
  store via FRIDAY-Server (bridge server 3) using Futuris's own session
  factory and tracker code — byte-identical to main `f6d1e665`
  (sha256-verified for `futuris/storage/{db,score_repository,models}.py`
  and `futuris/services/forecast_tracker.py`) — no credentials read or
  printed, no service restarted. Probes run 2026-11-25 ~06:35–06:42 IST.
  The scoring sweep itself (`score_resolved`, idempotent,
  savepoint-isolated per the FUT-025 fix) was run at 06:40:41 IST and
  wrote nothing: the queue is empty.

## 1. Verdict: the unscored cohort is EMPTY — nothing left to score

- `list_unscored_resolved(limit=500)`: **0 rows**. Every resolved forecast
  with a numeric outcome already has a score row.
- Store totals (live, ~06:36 IST): forecasts **989**, outcomes **642**,
  scores **642**. 642/642 resolved forecasts scored.
- `score_resolved()` sweep, 06:40:41 IST: considered **0**, scored **0**,
  skipped_no_numeric_actual **0**, skipped_duplicate **0**,
  event_only_resolved **0**. `count_scores` unchanged at 642; the latest
  score row is unchanged (`33e89a94`, scored 06:32:00 IST).
- Last scoring batch: **06:32:00 IST today** (2026-11-25) — the five
  newest score rows all carry 06:31:58–06:32:00 IST, so the standing
  30-minute `forecast_scoring_job` (FUT-017) is running and scoring on
  schedule.
- `count_event_only_resolved`: **0**.
- No scoring pass wrote anything: there was nothing to score, and the run
  makes no live change. The deliverable is this accuracy evidence.

## 2. Accuracy evidence (calibration report, generated 2026-11-25 01:06:05 UTC)

- n_scored **642**, status **measured** (min_samples 30 met).
- MAE **968.70**, RMSE **1104.32**, nominal level 0.80, coverage_80 **1.0**
  (gap +0.2 vs nominal), mean interval width **8872.01**, Winkler_80
  **9881.47**, mean pct error **49.79%**. Verdict: **underconfident**.
- Rolling 30-day hit-rate: **0.88474** (n_in_window 642, window
  2026-10-26 → 2026-11-25).
- By nominal level: 0.80 → n=444, coverage 1.0; 0.90 → n=198,
  coverage_90 0.6263 (gap −0.274).
- By evidence class: **synthetic n=568** (coverage_80 1.0); **live n=74**
  (coverage_90 0.0 — see §3).
- Change since run 2 (Nov 24 ~15:30 IST): +168 forecasts (821→989),
  +155 outcomes/scores (487→642); MAE 971.64→968.70,
  RMSE 1115.44→1104.32, hit-rate 0.89117→0.88474.

## 3. Headline finding: the only live-scored target is entirely out of interval

- The live class is a single target: `friday:fleet:forecast_demand_24h`
  (n=74, was 53, nominal 0.90): coverage_90 **0.0**, MAE **2139.76**,
  mean interval width **77.37**, Winkler_90 **42095.67**, mean pct error
  **93.00%**. The live-only calibration verdict is **overconfident**,
  30-day hit-rate **0.0**.
- Its 90% intervals (~77 wide) are ~28x narrower than its errors
  (~2140) — all 74 live scores missed. The aggregate 0.885 hit-rate is
  carried by the 568 synthetic scores; the live leg is miscalibrated on
  its only target. Follow-up for the coordinator (carried from run 2,
  still open): widen / recalibrate the `friday:fleet:forecast_demand_24h`
  intervals, or confirm the target's actuals feed is sane.

## 4. Resolution gap: 165 matured forecasts have no outcome at all (was 136)

- **347** forecasts have no outcome row (was 334); of those **165 are
  matured** (expires_at already passed) but unresolved — oldest
  2026-11-22 00:18 IST, 78.4 h old
  (`service:checkout:capacity_exceedance_24h`).
- By target: `intelx:research:finding_volume_24h` **74**,
  `vyralx:trends:topic_volume_24h` **72** (the two hourly recurring jobs
  are 146 of 165), `service:checkout:capacity_exceedance_24h` 2, plus 17
  singletons across other targets.
- These can never enter the scoring queue until the outcome-recording
  sweep records their outcomes. This is a resolution gap, not a scoring
  gap — the scoring job is healthy; the sweep that records outcomes for
  these recurring targets is not keeping up. (FUT-025 already filed that
  the lifecycle sweep is not wired on main; this run quantifies the
  backlog: 165, +29 since run 2.) Follow-up, not fixed here — no code
  change in this task.

## 5. Fleet home found: Futuris lives on bridge server 6 now

- Server 1: `Futuris.service` masked / inactive. Server 2: the Futuris
  directory was deleted from the checkout (uncommitted working-tree
  deletions) and the service has been inactive since Nov 24 19:09 IST
  (Oracle consolidation).
- FRIDAY-Server (bridge server 3): full checkout including Futuris +
  `.env` present, but no Futuris process and port 8004 not listening.
- Bridge server 6 (AWS host `ip-172-26-4-138`): Futuris **RUNNING** —
  `uvicorn futuris.api.app` on port 8004, PID 5261, started Nov 24
  03:57 UTC; `/health` status `degraded`, storage ok (13/13 required
  tables present), forecasting `unknown` (no forecasting-model probe
  exists — the same honest degradation run 2 recorded). The standing
  scoring job runs here: fresh score rows at 06:32 IST today.
- The future-`resolved_at` anomaly from run 2 is gone: max
  `OutcomeModel.resolved_at` is 2026-11-25 06:31:53 IST, 4.1 min
  before the probe.
- Bridge note: concurrent `run_shell` calls on one MCP session get
  crossed — my server-3 sweep call returned the server-6 probe's
  output instead of its own; the sweep was re-run alone and verified
  clean. Server-6 `run_shell` also hangs intermittently (two 100 s+
  timeouts before the clean verify).

## 6. States

- implemented YES (evidence filed in this doc) / tested YES (all numbers
  first-hand live reads, plus the idempotent sweep run through the write
  path) / merged NO (work PR open, awaiting Muse) / deployed N/A (no
  code change; no live change made) / production-verified N/A (the
  scoring job is already running on server 6; verified by fresh rows,
  not by this task).
