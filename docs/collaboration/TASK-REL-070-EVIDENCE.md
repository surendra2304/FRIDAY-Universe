# TASK-REL-070 — Fleet-layout exit-134 (SIGABRT) flaky gate: root cause + complete fix (follow-up)

**Worker:** Muse 4. **Branch:** `muse4/task-rel-070-fleet-layout-sigabrt-flaky-gate`.
**Base:** main `330de772`. **Assignment:** coordinator WATCH214 §4 top-up (queued for
muse_4); **claim:** hub #2045 comment 7223881892 (2026-11-27 ~22:40 IST).
**Prior work:** Muse 9, PR #1452 (merged 2026-11-23 10:29 IST), root-cause doc
`docs/collaboration/TASK-REL-070-EXIT-134-ROOT-CAUSE.md`; REL-081 runner, PR #1478.

## Verdict

The Nov 23 fix identified the right race but is **incomplete: the gate kept aborting
with the fix in the tree**. Root cause of the recurrence is a second, unaddressed
half — the suite's own `repo_isolation` purges orphan the keeper thread, so the
session-end stop cannot reach it. This PR fixes that half at the cause (three
layers) and makes the REL-081 runner recognise the recurrence's real exit-code
shape, which it previously missed. No quarantine entry is needed: the race is
fixed, not masked (see Acceptance).

## The recurrence evidence (post-fix window, verified first-hand)

All failed `validate-monorepo.yml` runs since the fix merged (2026-11-23 10:29 IST)
were pulled (`status=failure`) and their job logs read in full (job-logs endpoint,
redirect captured, blob fetched unauthenticated — the endpoint works from this VM;
the REL-116 "logs unfetchable" note does not reproduce here). 15 failures:

| Run | When (UTC) | Event / head | Exit | Finding |
|-----|-----------|--------------|------|---------|
| 45113131348 | Nov 23 04:39 | PR | 1 | `test_rel070_shutdown_threads::test_keeper_stops_and_thread_dies` — Muse 9's own PR #1452 run, pre-merge |
| 45118801855 | Nov 23 05:36 | PR `b3b9373c` | **134** | All 6 signature markers, `Aborted (core dumped)`, 3737 passed first. Fix in tested tree (head descends from `c98ed395`, compare API merge-base `c98ed395`) |
| 45156075974 | Nov 23 10:26 | PR | 1 | `test_sen022_telegram_self_check::test_both_present_via_env_file` (genuine) |
| 45157161309 | Nov 23 10:33 | push `e570ad5c` (#1478, the REL-081 runner's own merge) | **250** | 5/6 markers, 3764 passed first. Fix in tree (main commit) |
| 45160054974 | Nov 23 10:52 | PR | 1 | `test_real_deep_layer3b`, SEN-022 tests (genuine) |
| 45178622984 | Nov 23 12:53 | PR | 1 | `test_fleet_alert_notify` x2 (genuine) |
| 45188405754 | Nov 23 13:53 | PR | 1 | `test_fleet_alert_notify` x2 (genuine) |
| 45471117198 | Nov 24 19:31 | push | 1 | `test_real_deep_layer3b::test_training_linear_data` (genuine) |
| 45505142262 | Nov 24 22:53 | push `8aea4275` | **250** | 5/6 markers, 3857 passed first. Fix in tree (main commit) |
| 45514408464 | Nov 24 23:58 | PR `d5bed262` | **250** | 5/6 markers, 3857 passed first. Fix in tree (head descends from `c98ed395`) |
| 45756595864 | Nov 26 04:39 | PR `bd60c787` | **250** | 5/6 markers, 3912 passed first. Fix in tree (head descends from `c98ed395`) |
| 45942135457 | Nov 27 04:49 | push | 1 | `test_real_deep_layer3b::test_training_linear_data` (genuine) |
| 46015835460 | Nov 27 14:25 | PR | 1 | `test_fleet_cd_rel118_stale_lock` (genuine) |
| 46033304482 | Nov 27 16:24 | PR | 1 | `test_real_deep_layer11::test_search_and_authorise` + U+FEFF SyntaxError (genuine) |
| 46035081517 | Nov 27 16:36 | PR | 1 | `test_real_deep_layer11::test_search_and_authorise` (genuine) |

**5 of the 15 failures are the race, all with the fix in the tested tree.**
Exit 250 is the race's shape under the REL-081 runner: pytest dies of SIGABRT
(subprocess returncode -6), the runner's `sys.exit(-6)` surfaces as shell exit
250 — e.g. run 45756595864 log: `REL-081: test step FAILED (exit -6)`, fatal
`_enter_buffered_busy ... at interpreter shutdown, possibly due to daemon
threads` with the `friday_supervision.py:442 _refresh_market_analysis` /
`:348 _run_market_analysis` frames, 3912 passed first. The 5th marker missing
in the 250-runs is `(core dumped)` — the shell prints that only when it runs
the dying process directly; under the runner there is no shell message.
No race recurrence since Nov 26 04:39 UTC (the last ~36 h show only genuine
exit-1 failures), but the race is rare (~5 in ~4 days), so the clean window
is supporting evidence only — the mechanism fix below is the proof.

## Causal chain of the recurrence (the missing half)

1. **The suite imports the Stratex dashboard.** `tests/test_e2e_real_repo_integration.py::
   TestStratexE2E` does `from Stratex.dashboard import app`; `Stratex/dashboard.py`
   (module level) imports `api.friday_supervision` and calls
   `start_status_summary_keeper()` — keeper thread #1 starts on module object M1.
2. **The suite purges `api.*` mid-session.** `TestVyralXE2E.setup_class` (and the
   Cortex/Memora/Forge classes after it) call `purge_ambiguous_modules()`, which
   drops every `sys.modules` entry whose first segment is in
   `AMBIGUOUS_TOP_LEVEL_NAMES` — `"api"` is in that set. M1 is dropped from
   `sys.modules`, but keeper #1 keeps running: the live thread holds M1 alive
   through its frame globals, the loop keeps firing every 30 s, and each pass
   spawns `stratex-market-analysis-refresh` threads. M1's stop event is never set.
3. **Session end cannot stop the orphan.** `pytest_sessionfinish` looks up
   `sys.modules.get("api.friday_supervision")` — it finds nothing (or a second
   module object M2 created by a later re-import, whose keeper was never started)
   — stops that, returns. Keeper #1 and its refresh threads are still alive.
4. **Shutdown abort.** A refresh thread emits to stderr while CPython finalizes
   → `ValueError: I/O operation on closed file` → `Fatal Python error:
   _enter_buffered_busy ... at interpreter shutdown, possibly due to daemon
   threads` → `abort()` → SIGABRT → the gate fails although every test passed.

The Nov 23 regression test's own docstring warns about exactly this shape
("a purge + re-import would create a second module object whose keeper thread
no stop call could reach"), but the test avoids the pattern while the E2E test
performs it on every run. The hook's failure is silent: on the success path it
prints nothing, and the four recurrence logs contain zero `TASK-REL-070` lines
— no WARNING was ever printed, so the stop either never ran (module not found)
or stopped the wrong object.

## The fix (this PR)

**Layer 1 — the keeper does not start under pytest** (`Stratex/dashboard.py`):
the dashboard import now starts the keeper only when `"pytest" not in sys.modules`.
The keeper is a production warming optimisation (FRD-013); under pytest the read
path computes synchronously when cold, so no test depends on it, and a keeper
started at import time in a test process is pure liability. Production
(uvicorn) never has pytest loaded, so production behaviour is unchanged.
Tests that need the keeper call `start_status_summary_keeper()` directly.

**Layer 2 — a purge cannot orphan the keeper** (`tests/repo_isolation.py`):
`purge_ambiguous_modules()` now stops the supervision keeper (both spellings)
*before* dropping `api.*` from `sys.modules`, best-effort with a 90 s bound
(covers the documented 69 s worst-case refresh). The purge is the orphaning
operation, so the purge must clean up thread-owning modules first. This also
protects any future test path that starts a keeper deliberately.

**Layer 3 — the hook stops every module object** (`tests/conftest.py`):
`pytest_sessionfinish` now stops both `api.friday_supervision` and
`Stratex.api.friday_supervision` instead of returning after the first found —
the suite can hold the module under both spellings as two distinct objects.

**Runner recognition** (`scripts/ci_gate_test_runner.py`): the recurrence banner
and signature check now key on both abort forms — exit 134 and returncode -6
(SIGABRT under the runner, shell exit 250). The old code keyed on 134 only, so
none of the four post-fix recurrences was recognised as one (the Nov 26 log
shows the generic `test step FAILED (exit -6)` header with no banner and no
signature check, even though all markers are in the log).

## Verification done

- **Failing probe first (TEST FIRST):** new test
  `TestRel070PurgeOrphan::test_purge_does_not_orphan_supervision_keeper`
  FAILED pre-fix with exactly the orphan assertion (`purge orphaned the
  supervision keeper: the keeper thread is still alive but
  api.friday_supervision is gone from sys.modules ...`), and passes post-fix.
- **New tests, 8 total:** the purge-orphan test + `test_dashboard_import_under_pytest_starts_no_keeper`
  (in `tests/test_rel070_shutdown_threads.py`), and the -6 unit + integration
  tests (in `tests/test_rel081_gate_failure_summary.py`, fake pytest killed by
  `os.abort()` → runner exit 250 + banner + all 6 markers).
- **Focused suites locally** (venv `sen026-ci-venv`, pytest 9.2.0, mock
  `DATABASE_URL` as the gate sets it): `tests/test_rel070_shutdown_threads.py`
  + `tests/test_rel081_gate_failure_summary.py` — **18 passed**.
- **Full root suite locally** via the REL-081 runner
  (`python scripts/ci_gate_test_runner.py`, same command as the gate):
  **52 failed, 3884 passed, 72 skipped, 8 subtests passed in 613.46 s**
  (runner exit 1). The 52 failures are NOT a regression: the identical 52
  tests (same names, same 10 files — workflow/dispatch integration tests)
  fail on the pristine base `330de772` run with the same venv/env (52 failed,
  249 passed on those 10 files alone; `diff` of the failing-test lists is
  empty), while the CI run on `330de772` (46036410525) is green — the local
  VM lacks something the CI runners have (live-agent dispatch surface), and
  none of the 10 files imports the dashboard or the supervision module. The
  focused suites (REL-070 + REL-081) pass 18/18 locally.
- **CI on this PR:** the work PR's own `validate-monorepo.yml` run is the
  full-suite verification — it must pass first-try; it exercises the dashboard
  gate and the purge-stop on the real ~110 s session.

## Verification not yet done

- This PR's CI gate run (first-try green is data point one).
- Post-merge observation (carried from Muse 9's doc, still open): five
  consecutive board-only PRs pass the gate first-try with no exit-134/-6
  recurrence; if one occurs, this task reopens. The coordinator's watch
  should track it — the recurrence is rare enough that one green run proves
  the mechanism, not the rate.

## Acceptance

- [x] Root cause of the recurrence identified from CI evidence (5 recurrences,
      log + runner evidence, causal chain traced to source lines).
- [x] Fixed at the cause (no keeper under pytest; purge cannot orphan it;
      hook covers both spellings), not masked with a retry.
- [x] Runner recognises the recurrence's real shape (-6/250) as well as 134.
- [ ] Gate passes reliably on main — post-merge observation (see above).
- [ ] No rollback needed: additive + gating changes only; production never
      loads pytest, so the keeper still starts at dashboard import there;
      the purge-stop is test-only and best-effort.

Quarantine note (REL-108, TP11): no quarantine entry is filed for this flake —
the acceptance allows "fixed or quarantined", and the fix removes the
mechanism, so there is nothing left to quarantine. If a recurrence is ever
observed post-merge, the REL-108 list is the fallback route (owner muse_4,
expiry 2026-12-31).

## Files changed

- `Stratex/dashboard.py` — keeper starts only outside pytest.
- `tests/repo_isolation.py` — purge stops the keeper before dropping `api.*`.
- `tests/conftest.py` — sessionfinish hook stops both module spellings.
- `scripts/ci_gate_test_runner.py` — -6 recognised as the SIGABRT recurrence.
- `tests/test_rel070_shutdown_threads.py` — 2 new tests (purge-orphan, dashboard gate).
- `tests/test_rel081_gate_failure_summary.py` — 2 new tests (-6 unit + integration).
- `docs/collaboration/TASK-REL-070-EVIDENCE.md` — this file.
