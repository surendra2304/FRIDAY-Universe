# TASK-REL-103 — Fleet-layout exit-134 flaky gate: live re-probe on current main (evidence)

- **Task:** Reliability: fleet-layout exit-134 flaky gate — live re-probe on current main.
- **Owner:** Muse 4. **Claim:** hub #1483 comment 7203017473, 2026-11-27 ~02:14 IST.
- **Board verified:** AVAILABLE, owner muse_4, P2, on live main `cd94db08` (board blob read via git blob API before editing). Note: the board record's evidence line mistakenly names the output `TASK-REL-102-EVIDENCE.md`; the record's own files list says `TASK-REL-103-EVIDENCE.md` — filed here as REL-103, as flagged in the claim post.
- **Branch:** `muse4/task-rel-103-fleet-layout-exit-134-flaky-gate-reprobe` from main `cd94db08` (verified via API).
- **Gate identity:** `.github/workflows/validate-monorepo.yml` ("Monorepo Structure and Safety CI"), job `Validate fleet layout and mirror safety`, step `Run regression tests` (`scripts/ci_gate_test_runner.py`, the REL-081 wrapper around `python -m pytest -q tests`). That step is where the REL-070 SIGABRT landed. The sibling `friday-universe-ci.yml` `test` job runs per-agent tier-1 suites, not the root suite; it was probed too (see §3) — no exit-134 there. `fleet-live-validation.yml` runs no pytest and is out of scope.
- **Scope:** read-only live probe. No env flip, no deploy, no live-state change (none needed, none made; no coordinator clearance exists for this task). No code changed in this PR — evidence doc only, plus a fix *proposal* in §7. No board hunk: board flips are coordinator-only per WATCH182 §3.

## Verdict

**REPRODUCED.** The SIGABRT is still alive on current main: **5 of the 10 failed fleet-layout-gate runs in the probe window aborted with the exact REL-070 signature** — all tests passed first, then `Fatal Python error: _enter_buffered_busy ... at interpreter shutdown, possibly due to daemon threads` from a Stratex supervision refresh thread logging to stderr at finalization. The REL-070 fix (PR #1452, merged 2026-11-23T04:59:48Z, merge commit `27b7d4e2`) cut the occurrence rate from ~5/day in the Nov 21/22 window (10 occurrences) to ~1.4/day in this window (5 in 3.65 days), but did not eliminate it, because it stops only the supervision module object still in `sys.modules` — and the suite's own `purge_ambiguous_modules()` orphans the keeper by dropping `api.friday_supervision` from `sys.modules` mid-session (§5). The orphan keeper survives `pytest_sessionfinish` and aborts the interpreter whenever its refresh thread happens to be mid-emit at finalization (~0.5% of runs). The smallest safe fix is proposed in §7; it is a proposal only — not applied here.

## §1 — Probe method

All reads via the GitHub API (`~/workspace/custom-connectors/custom.github/bin/github_api.py`, read-only):

1. Listed every `validate-monorepo.yml` and `friday-universe-ci.yml` run created `>= 2026-11-23T05:00:00Z` (just after the REL-070 merge). The runs endpoint caps at 1,000 results per query, so the window was fetched in two slices (main + a `created=start..end` gap slice) and de-duplicated by run id: **1,605 unique runs per workflow**, 2026-11-23T05:01:05Z → 2026-11-26T20:45:08Z, plus a tail check to 21:04:16Z (5 more validate runs, 0 failures).
2. For every failed run (10 validate + 29 CI), listed its jobs, took the failed job(s), downloaded the job log text (the logs endpoint 302-redirects to a pre-signed blob; the blob is plain text, not a zip — the first pass assumed zip and failed on all 39; corrected to text), sliced the failed step by its `started_at`/`completed_at` timestamps, and classified it: REL-070 signature markers (6), pytest summary line, REL-081 exit code, step exit code, named failing tests.
3. Audited all 12 re-run runs (`run_attempt > 1`) via `jobs?attempt=1` to check whether an attempt-1 failure was masked by a later green attempt.
4. Verified current-main gate state from the check-runs of `cd94db08` (re-read 2026-11-27 ~02:36 IST).
5. Local mechanism probe (`~/workspace/muse4-runs/rel103_orphan_probe.py`) reproducing the orphan on the exact PR-base code (§5), and the REL-070 regression tests (§8).

## §2 — Window totals

| Workflow | Unique runs | Success | Failure | Cancelled | In progress | Decided |
|---|---|---|---|---|---|---|
| `validate-monorepo.yml` (fleet-layout gate) | 1,605 | 1,069 | **10** | 525 | 1 | 1,079 |
| `friday-universe-ci.yml` (CI/CD `test` + voice) | 1,605 | 1,569 | **29** | 0 | 7 | 1,598 |

The 525 cancelled validate runs are the workflow's `cancel-in-progress: true` concurrency (a newer push cancels the older run on the same ref) — not failures. No failed run was hidden by a re-run (§4).

## §3 — The five recurrences (SIGABRT, exact REL-070 signature)

Every one of these shows the pytest summary line first (**all tests passed**), then the abort at interpreter shutdown. No failing test in any of them.

| Run | When (UTC) | Head | Branch / event | Pytest summary | Runner exit | Step exit | Markers |
|---|---|---|---|---|---|---|---|
| 45118801855 | 2026-11-23 05:36:08 | `b3b9373c49bb` | muse1/task-rel-080-cortex-tier1-ci (PR) | 3737 passed, 72 skipped, 249 warnings, 8 subtests passed in 109.35s | — (pre-runner) | **134** | 6/6 incl. `(core dumped)` |
| 45157161309 | 2026-11-23 10:33:20 | `e570ad5c1dcd` | main (merge #1478 — the REL-081 runner PR itself) | 3764 passed, 72 skipped, 265 warnings, 8 subtests passed in 104.62s | −6 | **250** | 5/6 |
| 45505142262 | 2026-11-24 22:53:50 | `8aea427516b9` | main (merge #1733) | 3857 passed, 72 skipped, 257 warnings, 8 subtests passed in 104.32s | −6 | **250** | 5/6 |
| 45514408464 | 2026-11-24 23:58:52 | `d5bed2622dda` | musetp5/task-vyr-064-pd-whitelist (PR) | 3857 passed, 72 skipped, 257 warnings, 8 subtests passed in 105.73s | −6 | **250** | 5/6 |
| 45756595864 | 2026-11-26 04:39:28 | `bd60c787bc95` | musetp5/task-db-007-vyralx-filestore-backup (PR) | 3912 passed, 72 skipped, 330 warnings, 8 subtests passed in 106.28s | −6 | **250** | 5/6 |

Rate: **5 SIGABRT in 1,079 decided gate runs (0.46%)**, and 5 of the 10 gate failures (50%). Pre-fix baseline (REL-070 doc): 10 of 12 failed runs in the 2026-11-21/22 window were exit-134 — about 5 occurrences/day then vs ~1.4/day now. The fix reduced the occurrence rate roughly 3–4×; it did not reach zero. VAL-014's 5/5 (6/6) board-only first-try passes are consistent with this rate — at 0.46% per run, five consecutive passes are expected ~97.7% of the time — so that watch could not have detected a residual this small.

Why the step exit is 250, not 134, in the four runner-era recurrences: the REL-081 runner runs pytest as a subprocess; a SIGABRT death surfaces as `returncode == -6`, which the runner returns from `main()` and `sys.exit(-6)` reports to the shell as 250 (−6 mod 256). The pre-runner run (45118801855) executed `python -m pytest` directly in bash, so bash reported 134 = 128 + 6, with the shell's `Aborted (core dumped)` line. Same abort, different reporting path.

The signature in run 45756595864 (job 139696546259), verbatim from the step log — identical causal chain to REL-070 run 45082613824, including the dual `__file__` spellings that betray two module objects (see §5):

```
File ".../Stratex/api/friday_supervision.py", line 442, in _refresh_market_analysis
  _run_market_analysis({"symbols": symbols, "timeframes": timeframes})
File ".../Stratex/api/friday_supervision.py", line 348, in _run_market_analysis
  sig = engine.evaluate_symbol_timeframe(symbol, tf) if engine is not None else None
File ".../tests/../Stratex/autonomy/mt5_autonomous_engine.py", line 628, in evaluate_symbol_timeframe
  ml_result = ml_ensemble_get_signal(df, regime=...)
File ".../Stratex/strategies/ml_ensemble.py", line 226, in get_signal
  logger.info(f"ML ensemble signal: {side} confidence={confidence:.2f}")
ValueError: I/O operation on closed file.
Fatal Python error: _enter_buffered_busy: could not acquire lock for
<_io.BufferedWriter name='<stderr>'> at interpreter shutdown, possibly due to daemon threads
Python runtime state: finalizing
REL-081: test step FAILED (exit -6) — failure summary:
```

Note the REL-081 `EXIT-134 RECURRENCE` banner did **not** fire in any of the four runner-era recurrences: `summary_lines()` only banners when `exit_code == 134`, but the runner's exit code for a signal death is −6, so the banner branch is dead code for the real SIGABRT shape. The diagnosis info is still in the log (the tail re-print contains the fatal error), but the gate fails as unexplained exit 250 unless the reader knows to look for −6. See §7 item 3.

## §4 — The other failures are genuine (not the flake)

**Fleet-layout gate, genuine test failures (5):**

| Run | When (UTC) | Head | Branch / event | Failing tests | Step exit |
|---|---|---|---|---|---|
| 45156075974 | 2026-11-23 10:26:08 | `363c6df522da` | muse1/task-sen-022-telegram-self-check-manifest (PR) | `tests/test_sen022_telegram_self_check.py::test_both_present_via_env_file` (Telegram creds absent — the known exit-1 failure REL-070 lists as unrelated) | 1 |
| 45160054974 | 2026-11-23 10:52:44 | `e0378fc56748` | same branch (PR) | SEN-022 self-check tests + `Sentinel/test_real_deep_layer3b.py::TestNeuralNetwork::test_training_linear_data` (pytest summary line not recovered from this step slice) | 1 |
| 45178622984 | 2026-11-23 12:53:51 | `4d7eb6e6706c` | muse8/task-obs-014 (PR) | `tests/test_fleet_alert_notify.py` (2 tests) | 1 |
| 45188405754 | 2026-11-23 13:53:26 | `3d22d58e1fed` | muse8/task-obs-014 (PR) | same OBS-014 fleet-alert tests | 1 |
| 45471117198 | 2026-11-24 19:31:30 | `ce3c817fbcde` | main (merge #1705) | `tests/test_real_deep_layer3b.py::TestNeuralNetwork::test_training_linear_data` | 1 |

Zero REL-070 markers in all five; all fail with named tests and exit 1.

**CI/CD failures (29):** all genuine test failures, zero REL-070 markers in any step slice. Grouped: REL-080 Cortex tier-1 ×5 (`test_f3_peer_transport_exponential_backoff`), REL-088 Forge tier-1 ×2 / Futuris tier-1 ×1 (step exits 4 / 2; no failing test name captured by the probe's regex for these two steps), VOI-032 voice ×3, VOI-043 voice ×2, FRIDAY tier-1 (FRD-044 ×1, FRD-058 ×5, FRD-059 ×1, FRD-060 ×1), MEM-030 Memora tier-1 ×4, STR-082 Stratex tier-1 ×2 (`test_debt_enabling_parameter_rejected`), VYR-082 VyralX tier-1 ×2. The two Stratex tier-1 failures are genuine assertion failures, not the shutdown race. Attempt 1 of re-run 45302872946 (REL-088) also failed genuinely (Forge tier-1, exit 4).

**Re-run audit (12 runs with `run_attempt > 1`):** 11 had attempt 1 = success (re-run for other reasons; nothing masked). The one exception, 45302872946, failed on both attempts with the same genuine Forge tier-1 failure. **No failure was masked by a re-run.**

## §5 — Why the REL-070 fix did not hold: the purge orphans the keeper

The REL-070 fix is present and correct on current main — `stop_status_summary_keeper()` in `Stratex/api/friday_supervision.py`, the `pytest_sessionfinish` hook in `tests/conftest.py`, and `tests/test_rel070_shutdown_threads.py` (4 tests, passing — §8). The hole is in what the hook can reach.

**The causal chain, verified against code on main `cd94db08` and the failing run logs:**

1. `tests/test_e2e_real_repo_integration.py::TestStratexE2E` imports the Stratex dashboard (`from Stratex.dashboard import app`). `Stratex/dashboard.py` (module level) runs its blueprint loop — `importlib.import_module("api.friday_supervision")` — then `from api.friday_supervision import start_status_summary_keeper; start_status_summary_keeper()`. Keeper #1 starts on module object #1 (`api.friday_supervision`, file `…/Stratex/api/friday_supervision.py`), with its own stop event and keeper thread.
2. The same file's later e2e classes — `TestVyralXE2E`, `TestCortexE2E`, `TestMemoraE2E`, `TestForgeE2E` — each call `purge_ambiguous_modules()` in `setup_class` (lines 186, 334, 447, 538; plus `tests/test_graceful_degradation.py:19`). `tests/repo_isolation.py::purge_ambiguous_modules()` drops **every** module whose first dotted segment is in `AMBIGUOUS_TOP_LEVEL_NAMES` — which includes `"api"` — so it drops `api.friday_supervision` (and the `api` package) from `sys.modules`. The first post-Stratex purge orphans keeper #1: its thread is still alive, holding a reference to module #1's globals, but no `sys.modules` entry points at module #1 any more, so no stop call can ever reach its stop event. The keeper keeps looping (30 s cadence) and spawning `stratex-market-analysis-refresh` threads for the rest of the session.
3. If `api.friday_supervision` is re-imported afterwards (e.g. as `Stratex.api.friday_supervision`, resolved via the un-normalised `tests/..` sys.path entry that `tests/test_cross_agent_integration.py:12` / `tests/test_deep_modules.py:11` insert), a second module object #2 is created with a fresh stop event and a second keeper. The CI log proves this happened in the failing runs: the same process's tracebacks show both `…/Stratex/api/friday_supervision.py` and `…/tests/../Stratex/api/friday_supervision.py` as the module file.
4. At session end, `pytest_sessionfinish` looks up `api.friday_supervision` then `Stratex.api.friday_supervision`, stops the **first one it finds, and returns**. It stops object #2 (or finds nothing, if no re-import happened) and returns True, printing nothing — which is why every recurrence log shows **zero** `TASK-REL-070` hook lines. Keeper #1 and its refresh threads are never stopped.
5. At interpreter finalization, an orphaned refresh thread emits a log record to the already-closed stderr → `ValueError: I/O operation on closed file` → the next emit tries to acquire the stderr buffered-writer lock while finalizing → `Fatal Python error: _enter_buffered_busy … possibly due to daemon threads` → `abort()` → SIGABRT. It lands only when a refresh thread happens to be mid-emit at the exact finalization moment — timing, not the diff — hence ~0.5% of runs and green on re-run every time.

**Local reproduction** (`~/workspace/muse4-runs/rel103_orphan_probe.py`, run against the worktree at `cd94db08`, Python 3.12.3, pytest 9.2.0 venv; per-pass refresh patched to a no-op so the probe measures keeper lifecycle only):

```
sup1: api.friday_supervision file: .../Stratex/api/friday_supervision.py
keeper1 started: True alive: True
after purge: api.friday_supervision in sys.modules: False
sup2: Stratex.api.friday_supervision file: .../tests/../Stratex/api/friday_supervision.py
sup1 is sup2: False
keeper2 started: True alive: True
hook stopped module: Stratex.api.friday_supervision -> True
supervision threads STILL ALIVE after hook: ['stratex-status-summary-keeper']
keeper1 (orphan) alive: True
keeper2 alive: False
VERDICT: ORPHAN REPRODUCED — hook stopped one module object, the pre-purge keeper survives
after cleanup, supervision threads alive: []
```

The probe reproduces the exact `__file__` spelling pair seen in the CI logs. The full SIGABRT itself is timing-dependent and was not forced locally (REL-070 likewise reproduced only the first half locally); the recurrence is established by the five CI runs above.

## §6 — Gate state on current main

Main `cd94db08` (merge of PR #2016, STR-094), check-runs re-read 2026-11-27 ~02:36 IST: **12/12 completed — 9 success, 3 skipped, 0 failed.** `Validate fleet layout and mirror safety` is **success**; `test` is **success**. The gate is green on current main, and the 5 validate runs after the probe window (to 21:04 UTC) are 3 success / 2 in progress / 0 failures. The gate is healthy but still flaky at ~0.5% per run: at the current push rate (~440 gate runs/day) that is roughly 1–2 SIGABRT failures per day, each costing a re-run and a diagnosis cycle on a passing suite — most often on board-only diffs, exactly as in the REL-070 window.

## §7 — Smallest safe fix proposal (proposal only — NOT applied in this PR)

1. **Primary — stop before purge** (`tests/repo_isolation.py::purge_ambiguous_modules`): before popping any `api.*` name from `sys.modules`, if `api.friday_supervision` is loaded, call its `stop_status_summary_keeper()` best-effort (try/except, never raise), then purge. This kills the orphan at its creation point — the keeper is joined while its module object is still reachable — and covers every purge call site (e2e ×5, graceful-degradation ×1) with one change. Test-only file; production never calls purge; `stop_*` is idempotent. Cost: a purge that lands while a refresh is in flight waits for the join (bounded by the 180 s default; the keeper loop itself exits immediately on the event, only an in-flight refresh is waited out).
2. **Secondary — stop every loaded instance in the hook** (`tests/conftest.py::pytest_sessionfinish`): iterate both names and stop each loaded module instead of returning after the first. Cheap belt-and-braces for the (currently theoretical) case where both module objects are loaded simultaneously.
3. **Tertiary — runner signal mapping** (`scripts/ci_gate_test_runner.py`): treat subprocess `returncode == -6` (SIGABRT) as exit 134 in `summary_lines()` (banner + 6-marker signature check) and as the runner's own exit code, so the next recurrence fails as the canonical 134 with the `EXIT-134 RECURRENCE` banner instead of an unexplained 250. The gate still fails; only the diagnosis improves.

Alternatives considered and rejected: retrying the pytest step on 134 in the workflow (masks the race, burns ~110 s per flake); making the refresh thread non-daemon (hangs the process with no shutdown coordination); removing the keeper (reintroduces the FRD-013/VOI-006 63 s status-read latency); reaching into the orphaned thread's `__globals__` from the hook to set its stop event (fragile internals-reaching; the purge-side fix removes the need). Acceptance for the fix should be a re-probe over a larger run sample, not five PRs: at a 0.46% per-run rate, five consecutive passes are expected even with the bug present (§3).

## §8 — Local tests

- `tests/test_rel070_shutdown_threads.py` — **4/4 passed locally** (2.50 s, pytest 9.2.0, Python 3.12.3, `~/workspace/muse4/vyr035-venv`) on the exact PR-base code (`cd94db08`). No test file changed in this task.
- Orphan mechanism probe — reproduced (§5). Probe script: `~/workspace/muse4-runs/rel103_orphan_probe.py`.
- Full root suite not run locally (this VM has no CI deps installed — same limitation REL-070 recorded); the work PR's own `validate-monorepo.yml` run is the full-suite verification for this evidence-only change.

## Files changed

- `docs/collaboration/TASK-REL-103-EVIDENCE.md` — this doc.
- No code changed, no board hunk (coordinator-only flips per WATCH182 §3).

## States

- **implemented:** YES — live re-probe complete with run-level evidence (1,605 + 1,605 runs enumerated, all 39 failed runs log-classified, current-main gate state verified, orphan mechanism reproduced locally). No code change required for the probe itself; the fix is proposed in §7, not applied.
- **tested:** YES — 4/4 REL-070 regression tests pass locally on the PR-base code; orphan probe reproduces the mechanism; CI re-verification follows from the work PR's gate run.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — no code changed; nothing to deploy. The gate runs in GitHub Actions, not on the fleet.
- **production-verified:** YES for the verdict — the SIGABRT recurrence is established by five live CI runs on current main with the exact REL-070 signature, and the gate state on current main is verified green (9 success / 3 skipped / 0 failed). Paired verification (owner order rule 3) is owed — no verifier was named for this task; Muse to name one.

— Muse 4
