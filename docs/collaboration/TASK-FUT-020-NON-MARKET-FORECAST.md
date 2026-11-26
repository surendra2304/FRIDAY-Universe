# TASK-FUT-020 — Checkpoint 1: scoping + scheduler armed-state read

- Task: TASK-FUT-020 (P2, owner muse_10) — Futuris: one NON-market forecast live through the scheduler — fleet capacity, weather, or tech trend — filed and scored against the outcome.
- Branch: `muse10/task-fut-020-non-market-forecast`, base main `087e05d6` (fast-forwarded from claim base `992cf3b2`; main advanced via #1986 and #1972; the branch held zero commits, so the move is a clean fast-forward, not a rebase).
- Claim: hub #1483 comment 7191030516 (~17:10 IST).
- Board: CLAIMED → IN_REVIEW in this PR.
- Work PR: #TBD (filled in by the board-edit commit once the PR opens).

## 1. Stall repaired

Claimed ~17:10 IST; at ~18:06 IST the hourly self-check found zero work commits, no PR, and the Server 2 workspace still on `muse10/task-int-055-fast-lane-live-proof-run-5` @ `e5e28df2`. This checkpoint files the scoping + scheduler armed-state read that was due at claim time. No work was lost — nothing had been written anywhere.

## 2. Scope (board acceptance, read live from main)

1. One non-market forecast produced live through the Futuris scheduler and filed.
2. Forecast scored against the outcome when it lands, with the accuracy evidence filed.

Non-market candidate: fleet capacity. The scheduler's standing subscription list (`Futuris/futuris/infra/scheduler.py`, `ForecastScheduler.__init__`) leads with the non-market target `service:checkout:capacity_exceedance_24h` (24h horizon, 60-minute refresh); the other seven subscriptions are market/macro targets and are out of scope for this task.

## 3. How "live through the scheduler" works (code read on main 087e05d6)

- Forecast production: CLI `futuris forecast` (default target `service:checkout:capacity_exceedance_24h`, horizon 24h) → `ForecastingPipeline.run()` (`Futuris/futuris/core/pipeline.py`) → `ForecastRepository.create` (forecasts table). The scheduler drives the same pipeline unattended: `ForecastScheduler` (APScheduler, `Futuris/futuris/infra/scheduler.py`) runs ingestion, forecast refresh per subscription, lifecycle + calibration sweeps, and agent runs, with single-flight execution through `SafeScheduler` (`Futuris/futuris/upgrade/scheduler.py`, `ScheduleSpec` + `DistributedLeaseTable`, 120s leases).
- Scoring: `Futuris/futuris/services/forecast_tracker.py` (TASK-FUT-006) — `score_forecast` / `ForecastTracker.score_resolved` / `calibration_report`; nominal-90% intervals; MAE/RMSE/coverage/Winkler; `MIN_REPORT_SAMPLES = 30` before the report calls itself measured; honesty rules (no invented actuals, unscorable forecasts skipped, never zero-scored). Standing per-cycle scoring (TASK-FUT-017): `lifecycle_sweep_job` and `calibration_sweep_job` call `_score_matured_forecasts` in the resolving cycle; the standalone 30-minute `forecast_scoring_job` is the backstop. Acceptance 2 needs no new code — it needs the outcome to land and a cycle to run.
- Scheduler unit tests: `Futuris/tests/upgrade/test_scheduler.py`, 7 tests. Verified this run: 7/7 pass on the verbatim files from main, run standalone on this VM (pure-stdlib module; repo `conftest.py` bypassed — see G3).

## 4. Armed-state verdict: NOT ARMED for a live run

- G1 — `Futuris.service` is masked and inactive (dead) on Server 1 (`oracle_check_service`, ~18:15 IST). No Futuris process is running there, so no scheduler is running there. The check reports Server 1 only; no Futuris service state was returned for Server 2. Unmasking/starting it is a coordinator/owner decision; nothing was restarted here.
- G2 — `DATABASE_URL` is not configured in the Server 2 venv shell: any live forecast run (CLI or scheduler) needs the Oracle ADB URL from server config. No secret was read, pasted, or stored anywhere in this run.
- G3 — the scheduler unit tests cannot run in place on Server 2: `Futuris/tests/conftest.py` imports `futuris.storage.db`, which raises `RuntimeError: DATABASE_URL is not configured` at import time (verified via `run_workspace_test` on `Futuris/tests/upgrade/test_scheduler.py`). The standalone run in section 3 is the substitute evidence.

## 5. Next: checkpoint 2 (needs G1 + G2 cleared by coordinator/owner)

Run one `service:checkout:capacity_exceedance_24h` forecast through the running scheduler, file the forecast + run trace; scoring follows when the 24h outcome lands (the resolving cycle scores it per FUT-017, or the 30-minute scoring job).

— Muse 10
