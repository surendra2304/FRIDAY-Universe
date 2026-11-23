# TASK-REL-070 — Fleet-layout exit-134 (SIGABRT) flaky gate: root cause + fix

**Worker:** Muse 9. **Branch:** `muse9/task-rel-070`. **Base:** main `ed94c3d9`.
**Assignment:** coordinator watch 7091286076 (2026-11-23 09:41 IST). **Claim:** issue #35
comment 7091373834.

## Verdict

Root cause **identified to log + runner evidence and fixed**. The abort is not in the
code under test and not in the validator: it is a CPython interpreter-shutdown race
between the main thread finalizing and Stratex supervision **daemon threads that are
still logging**, started at import time by the root test suite. All tests pass first;
the process then aborts. The fix joins those threads before the interpreter
finalizes, so the gate outcome now reflects the test result.

## The failure signature (identical in every occurrence)

From run 45082613824 (merge #1435, main `84739a0`, 2026-11-22 23:22 UTC):

```
3728 passed, 72 skipped, 261 warnings, 8 subtests passed in 109.51s (0:01:49)
Traceback (most recent call last):
  File ".../logging/__init__.py", line 1164, in emit
    self.flush()
  ...
ValueError: I/O operation on closed file.
Call stack:
  File ".../threading.py", line 1012, in run
  File ".../Stratex/api/friday_supervision.py", line 442, in _refresh_market_analysis
  File ".../Stratex/api/friday_supervision.py", line 348, in _run_market_analysis
  File ".../Stratex/autonomy/mt5_autonomous_engine.py", line 628, in evaluate_symbol_timeframe
  File ".../Stratex/strategies/ml_ensemble.py", line 226, in get_signal
    logger.info(f"ML ensemble signal: {side} confidence={confidence:.2f}")
Fatal Python error: _enter_buffered_busy: could not acquire lock for
<_io.BufferedWriter name='<stderr>'> at interpreter shutdown, possibly due to daemon threads
Python runtime state: finalizing
/home/runner/work/_temp/...sh: line 1:  2501 Aborted  (core dumped) python -m pytest -q tests
##[error]Process completed with exit code 134.
```

Key facts: the `pytest -q tests` step **passed** (3728 passed) and the abort happens
**after** the summary, at interpreter shutdown. Exit 134 = 128 + SIGABRT (6).

## Measured incidence

All failed `validate-monorepo.yml` runs in the 2026-11-21/22 window were pulled
(`github_list_runs`, status=failure) and their job-log tails scanned:

| Run | When (UTC) | Branch / event | Exit |
|-----|-----------|----------------|------|
| 44874617299 | Nov 21 06:14 | main, merge #1170 | **134** |
| 44875277858 | Nov 21 06:22 | main, merge #1174 | **134** |
| 44894544460 | Nov 21 10:28 | muse1/task-vyr-032 | **134** |
| 44934353024 | Nov 21 18:13 | main, merge #1245 | **134** |
| 44967481885 | Nov 22 00:36 | main, merge #1279 | **134** |
| 44994834215 | Nov 22 06:41 | muse4/task-orch-012 | **134** |
| 45008909833 | Nov 22 09:43 | main, merge #1355 | **134** |
| 45048755358 | Nov 22 17:19 | main, merge #1393 | **134** |
| 45052231024 | Nov 22 17:56 | muse8/task-rel-067 | **134** |
| 45082613824 | Nov 22 23:19 | main, merge #1435 | **134** |
| 45025212684 | Nov 22 13:00 | muse1/task-sen-022 | 1 (real test failure, see below) |
| 45089046032 | Nov 23 00:29 | muse1/task-sen-022 | 1 (same real test failure) |

**10 of the 12 failed runs in the window are exit 134 with the identical signature**
(the 10 listed above; the two exit-1 runs are the same genuine failure —
`test_sen022_telegram_self_check.py::test_both_present_via_env_file`, Telegram
credentials absent — unrelated to this task). Every 134 run shows
`3723-3728 passed` first, then the `friday_supervision.py` daemon-thread
frames, then the fatal error. The six PRs
named in the assignment (#1186, #1240, #1263, #1330, #1348, #1350) all merged
after a green re-run of the same gate — consistent with this race.

Correction to an earlier note: on PR #1330 (TASK-ORCH-011) I recorded the gate
failure as a "proxy-env artifact". That was wrong — the base failure was this
same exit-134 shutdown race, not a proxy/environment issue. No proxy variable
is involved anywhere in the chain below.

## Causal chain (verified step by step)

1. **The suite imports the Stratex dashboard.** `tests/test_e2e_real_repo_integration.py::
   TestStratexE2E` does `from Stratex.dashboard import app`.
2. **Import starts the keeper.** `Stratex/dashboard.py` (module level) registers the
   `friday_supervision_bp` blueprint and calls `start_status_summary_keeper()`
   (TASK-FRD-013). The keeper is an **infinite-loop daemon thread**
   (`stratex-status-summary-keeper`, 30 s cadence) that calls
   `_refresh_status_summary()` → `_compute_engine_status_summary()` →
   `_ensure_market_analysis()`.
3. **Each keeper pass spawns a refresh thread.** `_ensure_market_analysis()`
   starts one single-shot **daemon thread** (`stratex-market-analysis-refresh`)
   that runs `_refresh_market_analysis()` → `_run_market_analysis()` →
   `engine.evaluate_symbol_timeframe()` → `ml_ensemble.get_signal()` →
   `logger.info(...)`. One refresh evaluates up to 5 symbols and measured
   24.5 s cold / 69 s under load on Server 1, so with a 30 s keeper cadence a
   refresh thread is live at session end most runs.
4. **The Stratex logger writes to stderr.** `Stratex/logger/__init__.py`
   `get_logger()` attaches a `RotatingFileHandler` **and** a console
   `StreamHandler()` (stderr). The refresh thread therefore writes to stderr
   while it runs.
5. **Shutdown race.** pytest prints the summary and the main thread starts
   finalizing: streams are closed, `logging.shutdown()` closes handlers. The
   still-running daemon thread emits → `ValueError: I/O operation on closed
   file` (logging `handleError` prints the traceback to stderr) → a thread
   then tries to acquire the stderr buffered-writer lock while the
   interpreter is finalizing → CPython raises `Fatal Python error:
   _enter_buffered_busy ... at interpreter shutdown, possibly due to daemon
   threads` and calls `abort()` → SIGABRT → exit 134 → the whole job fails
   although every test passed.

**Why it is flaky:** the abort lands only when a refresh thread happens to be
mid-emit at the exact moment of finalization. Whether that happens depends on
when the last keeper pass fired relative to the ~110 s session end — timing,
not the diff. Hence "green on re-run every time", and hence board-only diffs
burning a full diagnosis cycle per occurrence.

## The fix (this PR)

**`Stratex/api/friday_supervision.py`** — shutdown half, production behaviour unchanged:
- New module-level `_STATUS_SUMMARY_KEEPER_STOP: threading.Event()`.
- `_status_summary_keeper_loop()` now exits on the event and waits on it
  (`event.wait(interval)`) instead of `time.sleep()`, so a stop wakes the loop
  immediately. Behaviour identical while running.
- New `stop_status_summary_keeper(timeout=180.0) -> bool`: sets the event,
  joins the keeper thread, then joins any live `stratex-market-analysis-refresh`
  / `stratex-status-summary-refresh` threads, and returns True only when none
  is alive afterwards. The 180 s bound exceeds the documented 69 s worst-case
  refresh. `start_status_summary_keeper()` clears the event, so a stopped
  keeper can be restarted (dashboard re-init, tests).
- `_ensure_market_analysis()` returns early once the stop event is set, so no
  new background work can start after a stop request. Production never calls
  `stop_status_summary_keeper()` — the keeper still lives for the process
  lifetime there; only the test harness calls it.

**`tests/conftest.py`** — `pytest_sessionfinish` hook: if the supervision module
was imported by the suite, call `stop_status_summary_keeper()` so no
supervision thread is alive when the interpreter finalizes. Never fails the
session from teardown; prints a warning if a thread is still alive after the
join (timeout path).

**`tests/test_rel070_shutdown_threads.py`** (new, 4 tests): keeper stops and its
thread dies; stop-then-start restarts the keeper; a slow in-flight refresh
thread is actually waited out (join proven by elapsed time ≥ 1 s); no refresh
is spawned after a stop.

Alternatives considered and rejected:
- **Retry the pytest step on 134 in the workflow** (rerun-safe step): masks the
  race, burns ~110 s of runner time per flake, and leaves the abort in every
  other job that imports the dashboard. The root cause is fixed instead.
- **Making the refresh thread non-daemon:** would hang the pytest process
  until the refresh finishes (up to ~69 s) with no shutdown coordination —
  same wait, less control.
- **Removing the keeper / making the refresh synchronous:** reintroduces the
  FRD-013 / VOI-006 latency the keeper was built to fix (63 s status reads).

## Verification done

- New regression tests: **4/4 pass locally** (venv, Python 3.12, pytest 9.2):
  `tests/test_rel070_shutdown_threads.py`, 2.18 s.
- Mechanism reproduced locally with the real module under pytest capture: a
  refresh thread left alive at session end emits `ValueError: I/O operation
  on closed file` logging errors at shutdown — the first half of the CI
  signature. The fatal second half is the narrower race; it lands in CI
  (10/12 failed runs in the window) because of the much larger session
  teardown there.
- Syntax-checked: `py_compile` clean on all three touched files.
- **Not yet run:** the full root suite locally (this VM has no CI deps
  installed); the work PR's own `validate-monorepo.yml` run is the full-suite
  verification — it must pass first-try, and it exercises the new
  `pytest_sessionfinish` hook on the real ~110 s session.

## Acceptance

- [x] Failure mode identified to root cause, with log + runner evidence
      (9+ runs, identical signature, causal chain traced to source lines).
- [x] Fixed at the cause (stop + join before interpreter finalization),
      not masked with a retry.
- [ ] Five consecutive board-only PRs pass the gate first-try — **post-merge
      observation**: this can only be measured after the fix lands. The
      coordinator's watch should track the next five board-only PRs; if any
      of them fails the gate with exit 134, this task reopens. The work PR's
      own first-try green run is data point one.
- [ ] No rollback needed: the change is additive (one new function, one event,
      one hook); production never calls the stop path, and the keeper loop's
      running behaviour is unchanged.

## Files changed

- `Stratex/api/friday_supervision.py` — stop event, keeper loop wait, `start`
  clears the event, new `stop_status_summary_keeper()`, spawn guard in
  `_ensure_market_analysis()`.
- `tests/conftest.py` — `pytest_sessionfinish` hook.
- `tests/test_rel070_shutdown_threads.py` — new regression tests.
- `docs/collaboration/TASK-REL-070-EXIT-134-ROOT-CAUSE.md` — this file.
