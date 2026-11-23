# TASK-FUT-025 — Futuris: scoring-session isolation

- Task: TASK-FUT-025 (P2, owner muse_1)
- Branch: `muse1/task-fut-025-scoring-session-isolation`
- Claim: hub #1483 comment 7108666868 (2026-11-23 ~22:57 IST), on coordinator
  queue (watch 7106041874: INT-034 -> FUT-025 -> FRD-040)
- Assignment: isolate scoring jobs from the shared session ("Session is
  already flushing") and fix calibration + provider-refresh failures.
- Acceptance: scoring jobs run on isolated sessions without flushing
  contention; calibration sweep + vyralx/intelx provider refreshes
  complete; evidence filed.

## 1. Trigger (what was failing live)

Muse 9's 18:45 re-check (hub #1483 status 7102277953), follow-up to
TASK-FUT-023 section 6:

- 18:15:41 scoring pass considered 0 / scored 0 while claiming
  `n_scored_total` 374 (store then 375, off by one, cause not
  established from journal + store alone).
- A second scoring job 18:15:42 FAILED "Session is already flushing".
- Calibration resolve failed for `b5c0a661` + `f8921fe7` (same error).
- Provider refresh failed for the vyralx + intelx targets (same error).
- Telemetry 18:15 cycle PARTIAL: 3 of 8 targets stored fresh forecasts;
  the other 5 still at 17:15-cycle `as_of`. Third consecutive cycle
  with missing telemetry rows for those targets.

The claim run's live probe (~23:03 IST, first-hand via the bridge,
read-only store queries) corroborates the same failure mode on the
current cycle, with fresh ids: 44x "Session is already flushing"
since 17:00 IST; the 22:15 cycle reproduced it live (vyralx refresh
failed, 8 calibration resolves failed for 8b9d47cd, 4eec647d,
6835c65e, 1a30c711, d88a0c40, be6095c6, 936e872d, 325cded5, and the
calibration job RAISED on a 'prepared' session state, where Muse 9's
report had only warnings). Store at probe time: 411 scores, 419
outcomes, 8 unscored-resolved-numeric -- exactly those 8 ids. The
board-named b5c0a661 + f8921fe7 had already recovered by then
(outcome YES / score YES), so verification must target the current
failing set, not the named ids.

FUT-023 section 6 had already established the same family:

- 17:45 scoring pass logged considered 8 / scored 8 /
  `n_scored_total` 374, but the store still showed 366 scores and the
  same 8 forecasts unscored — the drain did NOT persist (it eventually
  persisted ~28 min late, count 375 at 18:45).
- 17:15 telemetry cycle executed successfully 17:27:38 but stored ZERO
  telemetry rows, while emitting a `forecast_updated` event for
  forecast_id `823e8307-978a-42d7-87d8-c26ff8e34d2e` — a forecast that
  does not exist in the `forecasts` table.
- 17:15:43 `calibration_sweep_job` exception in
  `outcome_repo.list_resolved_with_forecasts` (`scheduler.py:445` ->
  `repositories.py:495`), and the universe job's vyralx target failed
  with `Session is already flushing` the same minute.

## 2. Root cause (verified in code, main 8c0ef142)

1. **One session for the whole process.** `Futuris/futuris/api/app.py`
   built a single long-lived session (`scheduler_session =
   async_session_factory()`) and handed it to every scheduler repo;
   it was closed only at shutdown. Every scheduler job -- telemetry
   refresh, provider refresh, lifecycle sweep, calibration sweep,
   scoring, ingest, backtest, risk pulse -- read and wrote through
   that one `AsyncSession` object.
2. **No repository method ever commits.** Every repository does `add`
   + `flush` only. The only commit path in the codebase is the API
   request lifecycle (`futuris/api/deps.py::get_db_session`). The
   scheduler never committed its session, so every job's writes sat
   uncommitted in the shared transaction.
3. **The universe job DID commit -- on the shared session.**
   `generate_universe_forecast` commits per target
   (`futuris/core/universe_forecasting.py`, after `repo.create`). On
   the shared session that commit committed whatever other jobs had
   flushed, and a rollback after any job's failed flush
   (`_recover_session` / `_recover_scheduler_session`) discarded
   other jobs' pending writes. That is the whole 17:45 story: the
   scores were flushed, the journal counted them from the same
   uncommitted session, the store did not have them, and a later
   universe commit flushed them in ~28 min late.
4. **Concurrent use of one AsyncSession is the flushing error.**
   APScheduler runs jobs concurrently in one event loop. The
   standalone 30-minute scoring job and a sweep's tail-call scoring
   pass are two job ids calling the same function at once; the
   calibration sweep, the scoring job and the provider refresh all
   fire in the same :15/:45 minute after the restart re-anchored
   them. SQLAlchemy raises `Session is already flushing` when a
   second operation starts while the session is mid-flush -- exactly
   the 18:15:42 second scoring job, the b5c0a661/f8921fe7 calibration
   resolve failures, and the vyralx/intelx provider refresh failures.
5. **The telemetry phantom event follows from (2).**
   `forecast_refresh_job` created the forecast (`flush`, no commit)
   and then emitted the `forecast_updated` event from the in-memory
   object. When the shared session was later rolled back, the row
   vanished but the event had already gone out -- for 823e8307...,
   a forecast the store never held.
6. **A second-order race:** `forecast_scores.forecast_id` is unique,
   so two scoring runs listing the same unscored set also collide at
   insert/commit. The loser must not fail the whole sweep, and must
   not report the winner's rows as its own.

## 3. Fix

### `Futuris/futuris/infra/scheduler.py` -- session-per-job isolation

- New `_JobScope` dataclass + `_job_scope()` async context manager.
  A scope owns one fresh session when the scheduler was given a
  `session_factory`: the job's repos are built on it, the scope
  commits it when the job body returns, and a failure rolls back
  only that job's writes before the session is closed. When no
  factory was given (tests that inject repos directly) the scope
  reuses the injected repos and commits/rolls back/closes nothing --
  the legacy behaviour, so existing tests pass unchanged.
- New `session_factory` constructor parameter (a callable returning
  a fresh `AsyncSession`; the process-wide factory, resolved at call
  time by the caller per B23).
- Every job runs inside a scope: `ingest_job`,
  `forecast_refresh_job`, `universe_provider_refresh_job`,
  `lifecycle_sweep_job`, `backtest_nightly_job`,
  `calibration_sweep_job`, `forecast_scoring_job`,
  `stream_risk_pulse_job`. `_score_matured_forecasts` takes the
  caller's scope when invoked as a sweep's tail call, and opens its
  own scope when invoked standalone.
- Commit-before-report ordering, so no job can claim work the store
  does not hold:
  - scoring: `score_resolved()` -> commit -> `calibration_report()`
    read back from the committed store, so `n_scored_total` can only
    count persisted rows (the 17:45 divergence is impossible);
  - calibration: each recorded outcome is committed as it lands (a
    later failure cannot roll back earlier resolutions, and the next
    `record_outcome` starts from a clean session), outcomes are
    committed before step 2 reads them back and before scoring;
  - telemetry refresh: each subscription is committed BEFORE its
    `forecast_updated` event is emitted (the 823e8307 phantom event
    is impossible), and a 12-minute cycle keeps the forecasts it
    already fitted if a later subscription fails;
  - provider refresh: keeps its per-target commit, now on its own
    session, so a failed target's rollback touches only this job.
- Scoring serialisation: a per-scheduler `asyncio.Lock` around the
  scoring body. The standalone job and a sweep's tail call are two
  job ids in one process; the second run lists unscored forecasts
  only after the first has committed.

### `Futuris/futuris/services/forecast_tracker.py` -- duplicate guard

- `score_resolved()` wraps each insert in its own savepoint
  (`session.begin_nested()`). A loser of the insert race skips the
  duplicate row (counted as `skipped_duplicate`) instead of failing
  the whole sweep on the unique `forecast_id`, and its `scored`
  count is only the rows this run inserted.

### `Futuris/futuris/api/app.py` -- no more shared session

- The lifespan no longer builds a long-lived `scheduler_session`.
  The scheduler is constructed with `session_factory` (resolved at
  call time from `storage_db.async_session_factory`) and no repos;
  each job opens its own session from it. The scheduler-session
  close at shutdown is removed with it. Nothing else in the app
  read the scheduler's repos (the status surface only checks
  `_running_scheduler is not None`).

## 4. Tests

New file `Futuris/tests/test_fut025_scoring_session_isolation.py`
(5 tests, throwaway file SQLite schema from the real models, one
session factory shared by the jobs under test):

- `test_scoring_job_reports_only_persisted_rows` -- the 17:45 drain:
  8 resolved forecasts, job reports scored 8 / n_scored_total 8,
  and a FRESH session reads 8 score rows and 0 unscored.
- `test_concurrent_scoring_jobs_do_not_collide` -- the 18:15:42
  failure: two scoring jobs at once, both complete without a
  flushing error, scored counts sum to 8, store holds exactly 8.
- `test_calibration_and_scoring_run_concurrently` -- the b5c0a661 /
  f8921fe7 failures: calibration sweep + scoring job at once,
  resolved_count 2, no flushing error, 4 scores persisted, 0
  unscored.
- `test_provider_refresh_and_scoring_run_concurrently` -- the vyralx
  / intelx failures: provider refresh + scoring at once, all 3
  provider targets complete and persist (vyralx + intelx included),
  4 scores persisted.
- `test_telemetry_refresh_commits_before_emitting` -- the 823e8307
  phantom event: a recording emitter asserts the forecast row is
  already visible to a fresh session at emit time.

Existing scheduler/scoring tests are untouched in behaviour: the
legacy (no-factory) scope path preserves the old semantics, so
`test_fut017_standing_accuracy_scoring.py`,
`test_calibration_sweep.py` and `test_scheduler_targets.py` keep
passing unchanged. No local pytest is available in this run's VM
(no SQLAlchemy/pytest installed; no local clone per the
execution-risk rule) -- the tests are verified by CI on the PR.

## 5. State

- IMPLEMENTED in PR #1538 (claim + work on one branch; work commit
  faaf6f77, merge-main commit 881c6cb7 onto main 49126a41; board
  CLAIMED -> IN_REVIEW, pr 1538).
- TESTED: CI 10/10 green on head 881c6cb7 (8 success, 2 skipped, 0
  failed, verified via the check-runs API -- including the `test`
  job, which runs the new isolation tests). A doc-only follow-up
  commit updates this section with the final head; CI is re-verified
  on that head before merge-readiness is flagged.
- MERGED / DEPLOYED / PRODUCTION-VERIFIED: not yet. The live
  Futuris service on Server 2 still runs the old shared-session
  code until this PR is merged AND deployed; a live re-probe of the
  :15/:45 jobs (scoring drain, calibration resolve, vyralx/intelx
  refresh) needs Muse's hub clearance for the S2 restart, and is
  flagged to Muse in the STATUS comment -- it is not claimed here.

## 6. Findings for Muse (not fixed here)

- **Lifecycle sweep is not wired on main.** `app.py` never passes a
  `lifecycle_manager` to the scheduler, so `lifecycle_sweep_job`
  returns None in production. The 17:15:43 resolutions the FUT-023
  evidence attributes to the "lifecycle sweep" were recorded by the
  calibration sweep's resolve step (same :15/:45 marks). Wiring the
  manager is a separate decision -- it changes what runs in
  production -- so it is filed here, not silently fixed.
- **Telemetry partial cycles (3/8 stored at 18:15)** share the
  root cause fixed here (uncommitted flushes lost on rollback).
  With per-subscription commits the refresh keeps what it fitted;
  the next live cycle is the proof point, after deployment.
- The synthetic-telemetry caveat from FUT-023 section 3 stands
  unchanged (one synthetic series, wide intervals): this task fixes
  persistence and contention, not the data source.

## 7. Files changed

- `Futuris/futuris/infra/scheduler.py` (session-per-job isolation,
  commit-before-report, scoring lock)
- `Futuris/futuris/services/forecast_tracker.py` (per-score savepoint,
  `skipped_duplicate`)
- `Futuris/futuris/api/app.py` (drop long-lived scheduler session,
  pass `session_factory`)
- `Futuris/tests/test_fut025_scoring_session_isolation.py` (new, 5 tests)
- `docs/collaboration/TASK-FUT-025-SCORING-SESSION-ISOLATION.md` (this file)
- `docs/collaboration/WORK_BOARD.yaml` (FUT-025: CLAIMED -> IN_REVIEW)

— Muse 1
