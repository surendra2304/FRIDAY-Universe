# TASK-REL-072 — CI test collection: the three 2026-11-14 wave files

- Task: TASK-REL-072 (P1). Claim: issue #35 comment 7085410728; claim PR #1422 (board-only).
- Verified against: main `a8c6fea2` (live tree + all 26 workflow files, fetched via API 2026-11-23 ~02:20 IST).
- Verdict: **all three named files are collected by CI and execute green on main. No wiring gap — no workflow change was needed, so none was made.**

## Per-file verdict

| File (as named in acceptance) | Tests | Collected by (workflow / job / step) | Green run on main |
|---|---|---|---|
| `Forge/tests/unit/test_task_forge_002_developer_retry.py` | 5 `def test_` | `owner-workflows.yml` / `contracts` / "Generated-code ingestion and saved verification status" | Run 45064060744, head `3f9cec0c`, 2026-11-22 20:01:44Z push, conclusion `success`; contracts job 137336159463 `success`, step `success` |
| `Forge/tests/unit/test_task_forge_002_recovery_escalation.py` | 2 | same as above | same run/job/step |
| `Forge/tests/unit/test_task_forge_002_routing.py` | 8 | same as above | same run/job/step |
| `Forge/tests/unit/test_task_forge_002_truthful_completion.py` | 4 | same as above | same run/job/step |
| `Memora/tests/test_viking_context_durability.py` (PR #90) | 9 | `friday-universe-ci.yml` / `test` / "Run Memora vector tenant and transaction regressions" (standalone pytest invocation; workflow comment cites TASK-REL-001) | Run 45067289998, main head `a8c6fea2`, 2026-11-22 20:35:25Z push, conclusion `success`; test job 137346168990 `success`, step `success` |
| `FRIDAY/tests/test_intent_classifier_tier.py` (PR #92) | 14 | `owner-workflows.yml` / `contracts` / "Exercise four workflow and authority contracts (no external calls)" | Run 45064060744 (same as Forge rows) |

Note on the Forge glob: acceptance names `Forge/tests/unit/test_task_forge_002_*.py` — that glob matches exactly the four files above on main; all four are listed explicitly in the contracts job.

Run links:
- https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45064060744 (Owner Workflow Contracts, contracts job)
- https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45067289998 (FRIDAY Universe CI/CD, test job, main head)

## Guard check (REL-068, live)

The REL-068 guard (`scripts/ci_test_collection_audit.py`, PR #1384 merged) was run in its own
`--full` logic against the live main tree and all 26 workflow files: the guard's own
`parse_workflows` / `covers` functions were imported and executed, with the test-file list taken
from the live main tree (`git/trees/a8c6fea2`, 1,923 test files) and directory references resolved
against a directory skeleton built from the same tree (no repo clone is available in this worker VM).

- All six files above: **COVERED** (Forge ×4 and intent via `owner-workflows.yml`; viking via `friday-universe-ci.yml` with working-directory `Memora`).
- Whole repo: 279 / 1,923 test files covered by a PR-triggered workflow (REL-068 measured 269 / 1,899 on 2026-11-22 — the count moved with the repo, not with this task).
- Stale workflow references to test files that no longer exist: **0**.
- PR-triggered workflows scanned: 11 of 26.
- The guard step itself ran `success` inside the green contracts job 137336159463.

## Why the contracts run is on head 3f9cec0c, not a8c6fea2

`owner-workflows.yml` is path-filtered on push, so it does not run on every main push. The
compare `3f9cec0c...a8c6fea2` (8 commits) touches **0 workflow files**, so the green contracts run
at `3f9cec0c` executed byte-identical workflow content to current main — the listing and the
green result both apply to main as it stands.

## Before / after

- Before (REL-001, open since 2026-11-14): the three wave files ran in no workflow.
- After (this verification): each file is named explicitly in a PR-triggered workflow's pytest
  invocation and has a green run on main. The wiring predates this task (present on main;
  this task changed no workflow, test, or source file). The acceptance's "wire any still
  missing" branch did not trigger: nothing was still missing.
- Change set of this task: this evidence doc + the board record flip (CLAIMED → IN_REVIEW).
  No code, workflow, or test-list change.

## Method and limits

- No local pytest: this worker VM has no repo clone (clone blocked, as in prior runs); CI is the
  test arbiter. A green job whose pytest invocation names a file explicitly is the execution
  proof — `pytest -q` fails the job on any failure or collection error in a listed file.
- Step-level conclusions were read from the Jobs API for both runs (all steps `success` in the
  two jobs cited); full text logs were not downloaded.
- Check-runs on main head `a8c6fea2` (12 total): `test` `success`, all validation checks
  `success`, `docker` `success`. One unrelated observation, not in this task's scope and not
  touched: "Deploy Specialist Fleet (Server 2)" shows `failure` on that head — a deploy job,
  not a test-collection job; flagged here for Muse.

## Sequencing note

Claim PR #1422 (board-only) CI went green 9/9 (7 success, 2 skipped, 0 failed) on head
`e12523f9` and was merged by Muse 2026-11-23 ~02:30 IST (merge commit `6360fb06`, main head).
This evidence doc and the board flip ride in the work PR on the same branch, rebased onto
main `6360fb06` after the claim merge.

— Muse 1
