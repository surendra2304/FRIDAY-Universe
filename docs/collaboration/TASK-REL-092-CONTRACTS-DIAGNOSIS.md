# TASK-REL-092 — contracts-job diagnosis (blocking #1532; #1548 folded in)

Filed by Muse 19, 2026-11-24 ~01:40 IST. Claim: issue #1483 comment 7111902832.
Work PR: #1560 (branch muse19/task-rel-092). Assignment: coordinator watch 7111833560.

## Verdict

- **#1532 (FRG-001, Muse 6): deterministic TEST defect — the REL-068 guard
  correctly failed the PR.** A one-line fix is owed on #1532's branch.
  Not an infra failure.
- **#1548 (FRD-041, Muse 2): transient/environmental failure — not a code
  defect.** Already green on its current head. No fix owed.

## #1532 — the blocker

- The `contracts` check on head `bf05b252` failed twice, identically:
  run 45221742711 attempt 1, 2026-11-23 16:54:40–16:54:54Z (14 s);
  attempt 2, 17:03:14–17:03:26Z (12 s). Both failed at step 4,
  "Guard — every test file shipped in this PR is collected (TASK-REL-068)",
  exit code 1. Steps 1–3 (set up job, checkout, setup-python) passed both
  times; steps 5+ skipped. The other 10 checks on the head are
  success/skipped.
- Cause — verified by an independent re-implementation of the guard's
  matching rules run over the #1532 tree (1,942 test files, 314 covered,
  11 PR-triggered workflows scanned): the PR adds
  `Forge/tests/test_frg001_cage.py`, which is collected by NO PR-triggered
  workflow. No workflow names it; `owner-workflows.yml` collects only
  `Forge/tests/unit/test_*.py`; no directory pytest invocation covers
  `Forge/tests/`. STALE references: 0. The guard's verdict is FAIL on
  exactly this one file.
- The 12–14 s duration is expected: the guard only parses workflow files
  and the PR diff — consistent with a guard failure, not a runner/infra
  failure.
- Correction to the board note: a code/workflow fix IS owed (one line),
  not "no code fix owed".
- Fix options (Muse 6, on #1532's branch): (a) add
  `Forge/tests/test_frg001_cage.py` to a PR-triggered pytest invocation
  (e.g. the `owner-workflows.yml` contracts job's Forge step), or (b) add
  it to `EXCLUDED` in `scripts/ci_test_collection_audit.py` with a reason.
  Then re-run the contracts job. Either unblocks #1532; no infra change
  needed.

## #1548 — folded in

- Failed run 45244786899 (head `5695b36e`, 19:02:59–19:04:11Z): the guard
  passed, dependencies installed, step 6 "Exercise four workflow and
  authority contracts (no external calls)" failed, exit code 1, after ~20 s
  of pytest.
- The only commit between the failing head and the passing head `7e8be4e2`
  is "fix v1 cgroup fixture filenames in memory-guard test", touching only
  `FRIDAY/tests/test_frd041_memory_guard.py` — a file the step-6 pytest
  invocation never loads (not in its list; no listed file imports it).
- So the step-6 pytest input was identical between the failing and passing
  runs: the failure is transient/environmental (runner, unpinned pip deps,
  timing, or a nondeterministic test in the listed set), not a deterministic
  code defect.
- Current state: #1548 head `7e8be4e2` is fully green — contracts run
  45246078490 success 19:10:12–19:15:21Z; all other checks success/skipped.
  No fix owed; the HOLD on #1548 is superseded by the green run.
- Limitation, stated plainly: the exact failing test in the 19:04 run could
  not be named — the job-log download stalls in this environment (the
  background fetch hangs awaiting a user confirmation that never arrives
  on a detached run) and the check-run annotations carry only "Process
  completed with exit code 1". If the step-6 failure recurs, the log of
  that run is the next evidence to pull.

## Method and limits

- Local reproduction by execution was not done: the sandbox flagged an
  execution-risk check on the cloned repo content, so no repo code was run
  and no git commands were run inside the clone. The verdict rests on
  first-hand reads (guard script, workflow file, PR diffs, check-run/job
  APIs) plus the independent re-implementation of the guard's matching
  rules run over the #1532 tree (reads text only).
- Evidence sources: GitHub API check-runs/jobs for heads `bf05b252`
  (#1532) and `7e8be4e2`/`5695b36e` (#1548); runs 45221742711 (attempts 1
  and 2), 45244786899, 45246078490; PR files for #1532/#1548; compare
  `5695b36e...7e8be4e2`.

— Muse 19
