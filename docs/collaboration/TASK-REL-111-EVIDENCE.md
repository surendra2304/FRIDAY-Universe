# TASK-REL-111 — Evidence (pytest-testmon CI test selection)

## Live-proof route

Per the board (SPEED ROUND 2 order 7203732206 task (c)) and the
coordinator ruling WATCH262 §C: CI on a real PR — affected-tests-only
run green + full-suite run on merge green, timings filed here. The
broken-test proof runs on the probe branch (this branch), never on
main; a `workflow_dispatch` full run on the probe branch is the
full-suite leg for the probe.

## Run 1 — implementation PR, cold-cache full run: GREEN

- Work PR: **#2323** (head `a94accb6`, branch
  `musetp4/task-rel-111-implementation`, base main `1bc92551` at
  creation), 3 commits, +216/-29, 3 files, mergeable True.
- Workflow run: **46128595016**, event `pull_request`, status
  completed, conclusion **success**. Created 2026-11-28T09:02:41Z,
  updated 09:13:50Z — wall time **669 s (~11.2 min)**.
- Check-runs (8/8): test **success**, voice-regressions **skipped**
  (correct — no voice files touched), detect-voice-changes success,
  secrets success, 4 validation jobs success. 7 success + 1 skipped,
  0 failed.
- Test job: **success, 648 s (~10.8 min)**. detect-voice-changes:
  success, 16 s.
- Step-level (test job, 26 steps): all success except the designed
  skip — `Coverage gate` **skipped** on this PR event, exactly as
  checkpoint 2 decided (PR-path subsets lower coverage by design;
  the gate enforces on push / schedule / dispatch full runs).
  `Restore testmon data cache` (step 3) success — cold cache, nothing
  to restore, full run as designed. `Post Restore testmon data cache`
  (step 51) success — the `.testmondata` from this full run was saved
  under the branch key, priming the cache for run 2 (the probe leg).
  All 11 agent tier-1 steps, the engine suites and the HTTP tests:
  success.
- What run 1 proves: the testmon wiring installs and runs in every
  venv (root + 11 agent venvs), the workflow parses and the PR path
  executes end to end, and the cold-cache default is the full suite
  (no test silently skipped on the first run).

## Compatibility proof (pre-implementation, S2 first-hand)

- `pytest-testmon 2.2.0` installs alongside `pytest 9.2.0`.
- Smoke test (2 modules + 2 tests): cold cache → full run, 2 passed;
  comment-only change → 0 tests ran; real behaviour change → only
  the dependent test ran (failed as designed), unrelated skipped;
  brand-new test file → ran. See checkpoint 2 for detail.

## Probe leg (next — not yet run)

- Design (checkpoint 2): a cross-subtree dependency break — change
  behaviour in subtree A so a test in subtree B fails, while A's own
  tests stay green. The probe commit touches A only, so
  `detect-voice-changes` skips B's step and the PR-path run stays
  green; a `workflow_dispatch` full run on the probe branch then
  catches it; the probe is reverted immediately after.
- Investigation so far (S2 first-hand, 2026-11-28 ~15:25 IST): the
  agent tier-1 suites are hermetic — no tier-1 test file imports
  another agent's package, and no invoked test imports `mesh/*`.
  The remaining candidate surface is the `voice-regressions` job:
  it runs only when voice files change, so a break in a non-voice
  FRIDAY module asserted only by a voice test would be skipped in
  the PR run and caught by the full run. The exact pair (module →
  voice test) is picked first-hand during the probe leg; nothing on
  main is touched. `mesh/` is ruled out (no invoked test imports it).
- Run 2 (probe commit) and the dispatch full run: timings and
  deselection counts to be filed here when they land.

## Merge leg (owed)

- Full suite on merge-to-main (push event) green, with the coverage
  gate enforced; nightly schedule (02:00 UTC) repeats it daily.
  Paired verdict + merge are the coordinator's call (verdict for
  #2323 not yet assigned at filing time).

— Muse TP4
