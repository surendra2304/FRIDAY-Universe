# TASK-REL-093 — CI test-collection canary proof run 2

**Worker:** Muse 13 · **Claim:** hub #1483 comment 7116630870 (2026-11-24 ~04:40 IST),
on assignment in coordinator watch 7115749789 (~03:55 IST) ·
**Branch:** `muse13/task-rel-093-canary-proof-run-2` (from main `cae99f6c`) ·
**Claim PR:** #1584 (MERGED by coordinator 2026-11-24 05:17:16 IST, merge `944d4bd6`) ·
**Work PR:** filed this run; number in the board record ·
**Date:** 2026-11-24 ~04:40–05:10 IST (proof); work filed this run

## Verdict: PASS — the canary still catches an uncollected shipped test file

A deliberately uncollected test file was caught by CI (contracts job guard step
fails, all later steps skipped) and by the guard run locally on the same diff
(exit 1, file named). No gap to name.

## What the canary is (REL-068 lineage)

- Guard: `scripts/ci_test_collection_audit.py` — diff-scoped. In CI it runs as
  the first step of the contracts job in `.github/workflows/owner-workflows.yml`
  (`--base <base-sha>`) and fails exit 1 when a PR adds/modifies a test file
  that no PR-triggered workflow collects. It also fails on stale workflow
  references to test files that no longer exist.
- Canary: `tests/test_rel068_collection_canary.py` — listed in the contracts
  job pytest invocation (owner-workflows.yml line 96) and self-checking: its
  first test asserts its own filename appears in that workflow file.
- REL-068 (Muse 11, PR #1384, merged): guard + canary landed; local proof
  then was guard exit 1 on an unwired probe, exit 0 once wired; full-repo
  audit on main 3dd7cfba: 269/1,899 test files collected by PR CI.
- REL-072 (Muse 1, PR #1425, merged): the three 2026-11-14 wave files
  verified collected and green on main; no wiring gap.

## Proof leg 1 — local (clone of main `cae99f6c`, /tmp/FRIDAY-Universe)

1. **Full-repo audit on main:** `python3 scripts/ci_test_collection_audit.py --full`
   → 1,945 test files in repo, **317 covered (16.3%)** by a PR-triggered
   workflow, 11 PR-triggered workflows scanned; 1,627 uncollected.
   That is pre-existing debt the guard reports but does not fail on
   (diff-scoped by design, per its docstring); up from the REL-068 baseline
   of 269/1,899 — coverage grew, debt did not shrink. Not a REL-093 gap:
   the task is the canary, not the backlog.
2. **Canary still runs and self-checks:** `pytest tests/test_rel068_collection_canary.py`
   (pytest 9.2.0, venv) → **2 passed**. Still listed in owner-workflows.yml
   (line 96, 1 hit).
3. **Probe diff:** added `FRIDAY/tests/test_rel093_canary_probe.py` (trivial
   passing test, listed in NO workflow pytest invocation) on a local branch
   over main; guard `--base cae99f6c5a76faf4df7f0fb06d3cfa01f3f9161b` →
   **exit 1, FAIL: 1 test file shipped, `UNCOLLECTED: FRIDAY/tests/test_rel093_canary_probe.py`**,
   no stale references. 1,946 test files, 317 covered.
4. **Negative control:** same guard with `--base <probe HEAD>` (empty diff) →
   **exit 0, PASS: no test files in scope to check** — the guard is not
   failing spuriously.

## Proof leg 2 — CI (the literal acceptance: "caught by CI")

- **Probe PR #1585** (`muse13/task-rel-093-probe-uncollected`, head
  `2d82ca7a`, base main `cae99f6c`): diff verified first-hand via the API —
  exactly one file added, `FRIDAY/tests/test_rel093_canary_probe.py` (+11).
  Title marked `[PROBE — DO NOT MERGE]`.
- **Contracts job failed:** workflow run 45287430804, job 138087275712
  (`contracts`, https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45287430804/job/138087275712):
  step 4 `Guard — every test file shipped in this PR is collected (TASK-REL-068)`
  → **failure**; steps 5–16 skipped (fail-fast). All other checks on the probe
  head: secrets scan success, detect-voice-changes success, entrypoints
  success, voice-regressions skipped; fleet-layout / monorepo-policy / test
  still in progress at read time and irrelevant to the verdict — the guard
  step is the canary.
- **Probe PR closed unmerged** (state closed, merged false) immediately after
  the verdict. Nothing from the probe touched main.

## Related state (verified first-hand this run)

- **REL-089** PR #1539: MERGED 2026-11-24 ~04:54 IST (head `84a0fc1e`).
- **FRG-020** claim PR #1549: MERGED 2026-11-24 ~04:58 IST (head `0dc6bc3f`); work PR follows its merge.
- **VOI-030:** still CLAIMED / blocked — no calm-window voice call reported
  on #1483 through the latest read.
- **REL-093 claim PR #1584:** MERGED by coordinator 2026-11-24 05:17:16 IST
  (merge `944d4bd6`); board flip AVAILABLE → CLAIMED on main.
- **Board on main `693e7406`** (blob `477a27b9`, 18,237 lines, 789 records):
  REL-093 CLAIMED owner muse_13; SEN-024 AVAILABLE owner muse_13 (queue
  next: VOI-030 blocked -> REL-093 -> SEN-024, coordinator watch ~05:20 IST,
  board PR watch006 #1588); REL-091 now in Muse 4's queue; VOI-030 CLAIMED
  muse_13. Coordinator board PR watch007 NOT shipped (ship.py tree-POST
  truncation) — its MERGED flips (incl. REL-093) and top-ups (incl.
  VOI-035→Muse 13) are NOT in force; claim only from the board on main.
- **Usage:** 21% of free weekly limit (subscription-status, this run; reset
  Nov 29 6:09 PM IST). Not nearly gone — no wrap-up.
- **Schedules:** hourly self-check + weekly reset armed; work-request absent —
  correct while mid-task (claim workflow: re-created only when idle
  with no assignment).

## Files

- This doc: `docs/collaboration/TASK-REL-093-CANARY-PROOF-RUN-2.md` (filed
  in the work PR after #1584 merged).
- Local working copy: `~/workspace/muse13/rel093/TASK-REL-093-CANARY-PROOF-RUN-2.md`.
