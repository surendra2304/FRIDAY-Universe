# TASK-REL-111 — Checkpoint 2 (pytest-testmon implementation)

## Claim

- Head task TASK-REL-111, Muse TP4. Checkpoint 1 filed 2026-11-28 ~13:05 IST
  (branch `musetp4/task-rel-111-ci-test-selection`, commit `608fa7e6`,
  PR #2304).
- **PR #2304 MERGED 2026-11-28 14:17:59 IST** (merge `960cd3fc`,
  head `608fa7e6`, 1 file +92/-0). Paired verdict: Muse 9 VERIFIED,
  review `6096759088` (filed ~13:56 IST, due ~15:00, ~64 min early;
  BE 13:45 §A / WATCH264 §C). The merge train merged it with #2292 /
  #2300 / #2315 / #2295 in the same window. The old branch was deleted
  on merge (standard GitHub behaviour).
- **New branch for this checkpoint:** `musetp4/task-rel-111-implementation`
  @ main `22f869ac` (merge PR #2307, INT-050). Work PR opened this run
  (see hub status post for the number). Board flip IN_REVIEW → MERGED
  for pr 2304, and the new PR number, ride the coordinator board PR.

## Route ruling adopted

- **WATCH262 §C (hub #2045 comment 7236059938): "TP4 → REL-111 route
  question (#1271) — DECIDED: run the broken-test proof on the probe
  branch; do NOT merge a deliberately-broken-test commit to main."**
  The checkpoint-1 route question is answered. No probe step is taken
  on main, ever. The proof runs on the probe branch (this branch) via
  a workflow_dispatch full run — the dispatch trigger is added in this
  checkpoint.

## Implementation (checkpoint-1 scope steps 1–3)

### Compatibility proven first-hand before writing the change

- `pytest-testmon 2.2.0` installs cleanly alongside `pytest 9.2.0`
  (S2 scratch venv, pip, 2026-11-28 ~14:20 IST). The bound used is
  `pytest-testmon>=2.2,<3` (testmon is at 2.x, not 0.6.x).
- Smoke test (S2, two modules + two tests, pytest 9.2.0 / testmon 2.2.0):
  cold cache → full run, 2 passed; comment-only change to a module →
  0 tests ran (testmon ignores comment-only changes); real behaviour
  change → only the dependent test ran (and failed as designed), the
  unrelated test was skipped; a brand-new test file → ran (new tests
  always run). Selection semantics are exactly as the design needs.

### Workflow: `.github/workflows/friday-universe-ci.yml` (932 → 973 lines)

Base is current main `22f869ac` (see §Corrections). Commit `0038d337`,
blob `d2e29cd850e851d342601a9fa4512e71826ae4dc`, verified byte-identical
on the branch first-hand.

1. **Triggers:** `workflow_dispatch:` added (manual full-suite runs —
   the broken-test probe — and ad-hoc re-runs; a dispatch is a non-PR
   event, so it runs the full suite via the existing force-full step).
2. **PR-only selection flag:** job-level `TESTMON` env on both the
   `test` job and the `voice-regressions` job:
   `TESTMON: ${{ github.event_name == 'pull_request' && '--testmon' || '' }}`
   — `--testmon` on pull_request only; empty (full suite) on push,
   schedule and dispatch.
3. **Cache:** `Restore testmon data cache` step (actions/cache@v4) right
   after checkout in the `test` job. One entry holds `.testmondata`
   for all 11 pytest working directories (root + Memora, Cortex,
   FRIDAY, Stratex, Forge, Inference, Sentinel, IntelX, Futuris,
   VyralX). Key `testmon-<os>-<ref>`, restore-keys fall back to main.
   Cold cache (no entry yet, e.g. the first run) means testmon has no
   data and runs the full suite — the safe default.
4. **Installs:** `pytest-testmon` added to every pytest install: the
   root inline list plus all 11 per-agent venv installs (Memora vector
   + tier-1, Cortex, FRIDAY, Stratex, Forge, Inference, Sentinel,
   IntelX, Futuris, VyralX) plus the voice-regressions install —
   13 installs in total.
5. **Selection:** `$TESTMON` appended to all 15 pytest invocations:
   engine suites (1), Memora vector (2), Cortex, FRIDAY, Memora
   tier-1, Stratex, Forge, Inference, Sentinel, IntelX, Futuris,
   VyralX, HTTP tests (1 each), voice-regressions (1). File lists,
   deselects, venvs and step `if:` gates are untouched.
6. **Coverage gate decision (checkpoint-1 open question, decided):**
   the `Coverage gate` step now runs only on full runs
   (`... && github.event_name != 'pull_request'`). A PR-path run
   selects a test subset, which lowers coverage by design; enforcing
   the regression-class floors there would fail every partial run.
   The gate still enforces on push (merge to main), schedule
   (nightly) and dispatch full runs. `--cov` collection on PR runs
   is kept (partial report, harmless).
7. **Untouched by design:** the tier-1 collection gate (REL-088,
   fixed 21-file list, runs unconditionally), the
   `detect-voice-changes` path filters (PR step selection is
   orthogonal to testmon's within-step selection), the `docker` job
   (main-only), and the `Upload test results` step.

### `requirements-ci.txt` (commit `6f7c8edf`, blob `2158ed1f`)

- Added under `# Test tooling`, after `pytest-asyncio`:
  `pytest-testmon>=2.2,<3` with a TASK-REL-111 comment. The file is
  otherwise unchanged from main (verified by md5). It is installed
  only by validate-monorepo.yml / monorepo-validation.yml; those jobs'
  invocations are out of scope and unchanged.

## Corrections to checkpoint 1 (read from the stale S2 clone)

Checkpoint 1 described the workflow from the S2 clone, which was
then on the old FRG-036 branch — not from the REL-111 branch base.
First-hand re-read on the branch and on current main corrects:

- **A `schedule:` trigger DOES exist** (TASK-REL-120: nightly full
  suite, cron `0 2 * * *` / 02:00 UTC). Checkpoint 1's "no schedule /
  no nightly" is wrong. Only `workflow_dispatch` was missing, and
  this checkpoint adds it.
- **The workflow is 923 lines at the branch base** (932 on current
  main), not 896.
- **The `test` job has 14 pytest invocations, not 15** — the 15th is
  in the `voice-regressions` job. All 15 now carry `$TESTMON`.
- **This PR runs every test step anyway:** the `shared` filter
  matches `.github/workflows/friday-universe-ci.yml` and
  `requirements*.txt`, so all agent steps run on this PR; testmon
  selects within each step's file list. The first run is a cold-cache
  full run; subset behaviour is proven by the probe (next leg).

## Proof plan (refined — probe is the next leg)

- **Run 1 (this PR's CI):** cold cache → full run, all steps green,
  cache saved. Timings filed in TASK-REL-111-EVIDENCE.md.
- **Probe (next leg, after run 1 saves the cache):** a cross-subtree
  dependency break — change behaviour in subtree A so that a test in
  subtree B fails, while A's own tests stay green. The probe PR
  touches A only, so `detect-voice-changes` skips B's step and the
  PR-path run stays green (the B test is never selected); a
  `workflow_dispatch` full run on the probe branch then catches it;
  the probe is reverted immediately after. This is the only design
  consistent with the acceptance: a new broken test file in B would
  be selected (new tests always run) and would fail the PR run.
  The dependency pair (A module → B test) is picked first-hand
  during the probe leg; nothing on main is touched.
- **Full suite on merge:** the merge-to-main push runs the full
  suite with the coverage gate enforced; the nightly schedule does
  the same daily.

## Next

- Work PR CI run 1 (cold-cache full run) → file timings in
  TASK-REL-111-EVIDENCE.md → run the probe leg → file the evidence
  doc → paired verdict + merge (coordinator's call).
- Board flip for pr 2304 → MERGED and the new work PR ride the
  coordinator board PR (no board hunk in this PR).

— Muse TP4
