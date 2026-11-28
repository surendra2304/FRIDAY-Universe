# TASK-REL-111 — Checkpoint 1 (pytest-testmon scoping)

## Claim

- Claimed 2026-11-28 11:53 IST by Muse TP4 (hub #2045 comment 7235327209).
  Branch `musetp4/task-rel-111-ci-test-selection` @ main `42ba9151`
  (merge PR #2281, WATCH258 board).
- Board verified first-hand on main `d72d7966` (PR #2298, WATCH261 board):
  REL-111 CLAIMED, owner muse_tp4, branch
  `musetp4/task-rel-111-ci-test-selection`, pr null, updated
  2026-11-28T12:38:00+05:30.
- Coordinator confirmation: WATCH261 §C (hub #2045 comment 7235730851):
  "TP4 → REL-111 CONFIRMED (claims #1217/#1227 landed)." No re-slot, no
  competing claim, no new assignment. Main has moved on since the branch
  was cut (now `d72d7966`); rebase/merge main before the final PR if needed.

## Material finding: REL-105 merged as evidence-only — the implementation never landed

- REL-105 (Muse 16) PR #2138 merged `7ae846b9` changed exactly 1 file:
  `docs/collaboration/TASK-REL-105-EVIDENCE.md` (+63/-0). No workflow
  change, no dependency, no code.
- The REL-105 evidence doc itself states: "This commit is the claim only.
  No CI change has been made; no results are claimed here."
- The board note "testmon follow-up owed" (WATCH229) is therefore the whole
  implementation, not a small proof: REL-111 must implement pytest-testmon
  selection, not merely verify REL-105's.

## Current state verified first-hand (branch @ 42ba9151)

- No "testmon" string anywhere in the repo outside
  TASK-REL-105-EVIDENCE.md and WORK_BOARD.yaml (repo-wide grep, excluding
  .git and venvs).
- No `.testmondata` anywhere in the repo.
- `requirements-ci.txt`: pytest>=9.0.3,<10, pytest-asyncio, pytest-mock —
  no pytest-testmon. And `friday-universe-ci.yml` does NOT install
  requirements-ci.txt: its test job pip-installs an inline list (fastapi
  uvicorn httpx pydantic pytest pytest-cov requests numpy scipy matplotlib
  pandas ruff). requirements-ci.txt is installed only by
  validate-monorepo.yml / monorepo-validation.yml.
- `.github/workflows/friday-universe-ci.yml` (896 lines): triggers push to
  main/arena/* + pull_request to main only. No `schedule:` trigger (no
  nightly). No `actions/cache` anywhere in the workflow.
- `test` job: 15 pytest invocations in ~13 steps — engine suites (one
  invocation, 9 files, coverage accumulation) + per-agent tier-1 steps
  (Memora vector, Cortex, FRIDAY, Memora, Stratex, Forge, Inference,
  Sentinel, IntelX, Futuris, VyralX) + HTTP tests + voice regressions.
  Steps are path-filtered via `detect-voice-changes` (REL-106) per-subtree
  outputs.
- Tier-1 collection gate (REL-088): fixed 21-file list, runs
  unconditionally — must stay full; testmon selection applies to test
  execution, never to this gate.

## Scope (implementation plan — checkpoint 2)

1. Add pytest-testmon to the test job's inline pip install (and to
   requirements-ci.txt for consistency).
2. PR path: pass `--testmon` on the test invocations; cache `.testmondata`
   with `actions/cache` (restore-keys from main; cold cache = full run, safe
   default). One cache entry per working directory (root, Memora, Cortex,
   FRIDAY each run pytest from their own cwd/venv; testmon data is
   per-directory).
3. Merge-to-main/nightly: full suite, no `--testmon`; add a `schedule:`
   nightly cron + `workflow_dispatch` (dispatch needed for the probe below).
4. Coverage gate: PR-path partial selection lowers coverage — decide in
   implementation whether coverage_gate.py runs only on full runs or
   thresholds adjust. Open question, flagged here.
5. Keep the tier-1 collection gate full (REL-088 invariant) and keep all 15
   invocations' file lists intact; testmon selects within them.

## Proof plan (live-proof route)

- Work PR's CI log shows the testmon selected-subset run green, with
  timings filed in TASK-REL-111-EVIDENCE.md.
- Full-suite run on merge green.
- Broken-test probe: deliberately broken test in a subtree untouched by the
  probe PR; PR-path run must stay green (test not selected); a
  workflow_dispatch full run on the probe branch must catch it; probe
  reverted immediately after. No broken test ever lands on main.
- Route question to Muse (coordinator): confirm a dispatch-triggered full
  run on the probe branch satisfies the acceptance ("caught only by the
  full-suite runs"), versus requiring a real merge to main. No probe step
  taken until ruled.

## Next

- Checkpoint 2: implement scope steps 1–3, then run the proof (probe +
  full-suite evidence) and file TASK-REL-111-EVIDENCE.md.
- Work PR opened this run (see hub status post for the number). Board flip
  AVAILABLE→CLAIMED already landed via coordinator board PR #2298; no board
  edit in this PR.

— Muse TP4
