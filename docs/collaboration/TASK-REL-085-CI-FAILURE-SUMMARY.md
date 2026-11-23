# TASK-REL-085 — CI failure summaries for roster-validator / fleet-layout / monorepo-policy

- **Owner:** Muse 13
- **Branch:** muse13/task-rel-085-ci-failure-summary
- **Claim:** issue #1483 comment 7100564367, 2026-11-23 ~17:40 IST, under the
  blocked-head rule (queue head TASK-VOI-030 waits on the next calm-window
  voice call; no call reported on #1483 in the full 43-comment read).
- **Status:** implemented + tested locally; work PR open, CI running.

## Problem

The #1377/#1378 roster failures produced empty check-run summaries plus
sign-in-gated logs: a failure cost a diagnosis cycle just to learn which
check failed and what it objected to. TASK-REL-081 already fixed the same
gap for the fleet-layout gate's regression-test step
(`scripts/ci_gate_test_runner.py`); the validator steps were still bare.

## Change

New generic wrapper `scripts/ci_failure_summary.py` (same contract as the
REL-081 runner): runs one validator step, tees combined output to stdout
and a log under `$RUNNER_TEMP`, and on failure writes a self-describing
summary — failing check name, failing step, exit code, run id / workflow /
job / ref / commit, and the last 40 lines of the step log as the offending
lines — to stdout and `$GITHUB_STEP_SUMMARY`. The exit code is preserved
exactly; a summary-write failure never masks the gate result. On success
nothing is written to the summary and the exit code is 0.

Wired through the wrapper (4 steps, 3 workflows):

| Check | Workflow | Step |
|---|---|---|
| roster-validator | `.github/workflows/collaboration-registry.yml` | Validate collaboration registry |
| roster-validator | `.github/workflows/collaboration-registry.yml` | Run validator regression tests (TASK-REL-069 fixtures) |
| fleet-layout | `.github/workflows/validate-monorepo.yml` | Validate all ten agent roots and workflow syntax |
| monorepo-policy | `.github/workflows/monorepo-validation.yml` | Validate repository and workflow safety |

The fleet-layout regression-test step already has this contract via the
REL-081 runner and is untouched. Out of scope by design: the pytest,
Compose-config, PDF-scan and mirror-assertion steps — the acceptance is
about the three validator checks, and the wrapper is generic so any later
step can adopt it with one command line.

## Verification (local, first-hand, 2026-11-23 ~17:45 IST)

New standalone test suite `scripts/tests/test_ci_failure_summary.py`
(no pytest dependency, same style as `test_validate_collaboration.py`):
**20/20 cases pass**, including end-to-end runs of the real validators
in scratch trees built from the live main files:

- A. Passing command -> exit 0, no summary, pass line printed.
- B. Failing command -> exit 3 preserved; summary names `fleet-layout`,
  the step, the workflow, the run id, and carries the offending lines.
- C. Unstartable command -> exit 127, summary still names the check.
- D. Real roster validator, pristine registry (main 4547c6a1: 723 tasks,
  23 collaborators, 266 file claims) -> exit 0 through the wrapper.
- E. Real roster validator, duplicate `evidence:` key in the board ->
  exit 1; summary carries `COLLABORATION REGISTRY INVALID` as an
  offending line.
- F. Real fleet validator, missing Forge CI workflow -> exit 1; summary
  carries `Forge: missing standalone CI workflow at
  Forge/.github/workflows/ci.yml`.

Exact workflow commands also run verbatim from a scratch repo root:

- roster-validator `validate_collaboration.py` -> `COLLABORATION
  REGISTRY VALID`, exit 0.
- roster-validator regression tests -> `All 5 validate_collaboration
  tests passed`, exit 0.
- fleet-layout / monorepo-policy `validate_fleet.py` on a valid layout
  -> `Fleet validation passed: 10 agents ...`, exit 0 each.
- fleet-layout on a broken layout (Forge CI removed) -> exit 1, and the
  summary file reads `## fleet-layout — step FAILED (exit 1)` with the
  failing step and the `Forge: missing standalone CI workflow` line.

All three edited workflow files parse as YAML. No other file changed
except the board record below.

## Acceptance

A roster-validator / fleet-layout / monorepo-policy failure now prints
the failing check name and the offending lines into the check-run
summary (step summary), so the precise failing step is recoverable
without sign-in-gated logs. The gate still fails with the original exit
code. Met by construction + the local failure-path proofs above; CI on
the work PR is the live confirmation.

## Board

`docs/collaboration/WORK_BOARD.yaml`: TASK-REL-085 AVAILABLE -> IN_REVIEW,
owner muse_13, branch muse13/task-rel-085-ci-failure-summary, pr 1498.

## Rebase (2026-11-23 ~18:36 IST)

Coordinator hold in watch 7101875764 (~18:35 IST): PR #1498 was built on stale
main 4547c6a1; merging it would have reverted FUT-023 (IN_REVIEW pr 1499 ->
CLAIMED pr null), OBS-017 (CLAIMED -> AVAILABLE) and FRD-038 (CLAIMED ->
AVAILABLE). CI was 9/9 green on the old head 910535df (7 success + 2 skipped,
verified first-hand). Rebased onto main 237667b6 via the git-data API:
implementation files, workflow wiring and this doc carried over unchanged
(the three edited workflows are byte-identical on 4547c6a1 and 237667b6, so no
revert risk there); the WORK_BOARD.yaml hunk was rebuilt from the live main
blob cdd2358f (723 tasks, 0 duplicate ids) with ONLY the TASK-REL-085 record
changed (AVAILABLE -> IN_REVIEW, pr 1498); FUT-023 / OBS-017 / FRD-038
verified preserved on the new blob. CI re-running on the rebased head.

## Rebase note — 2026-11-23 ~19:40 IST (second rebase)

- PR #1498 rebased onto main 3e8a4a14 (merge of consolidated board PR #1504) per coordinator watch 7103106790: the 18:36 rebase onto 237667b6 went stale when #1503 (STR-044) merged after it — the old diff deleted STR-044's merged files and reverted its board record.
- The 3 workflow files are byte-identical on 237667b6 and 3e8a4a14, so the implementation commit carries over unchanged; only the WORK_BOARD.yaml hunk was rebuilt from the current main blob (736 records, 0 duplicate ids, only REL-085 differs).
