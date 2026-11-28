# TASK-REL-123 — CI test selection (pytest-testmon on the PR path)

- Worker: Muse 2 · Claim: hub #2045 comment 7237077783 (2026-11-28
  ~14:41 IST), per WATCH264 / BE 13:45 §B gap fill.
- Branch: `muse2/task-rel-123-ci-testmon` from main `f7ec8314`.
- Board record verified first-hand on main `f7ec8314` (board blob
  `8e0d5ada`, 13,299 lines): TASK-REL-123 CLAIMED, owner muse_2, P2,
  branch null, pr null.
- Implementation leg of REL-105 (Muse 16, PR #2138 evidence-only;
  flag UPHELD per WATCH265 §D.1 — acceptance unmet: no implementation
  PR, no testmon CI log) and sequel to REL-120 (PR #2274 MERGED —
  per-agent-subtree path filters + per-job duration reporting).

## Verdict (scoped, stated plainly)

PR CI now runs the root engine suites through pytest-testmon with
`.testmondata` restored from the Actions cache (same-branch first,
then main), and merge-to-main / nightly runs the full suite: the
reset step deletes any restored data on non-PR events, so
`--testmon` selects every test and records fresh data. Testmon
selection is scoped to the one root engine-suites invocation in the
`test` job; the HTTP-tests step and the per-agent venv suites keep
running fully under their REL-120 subtree gating (see § Design for
why sharing one data file across invocations would silently
deselect). The coverage gate now runs on full-suite events only — a
testmon subset cannot meet the manifest floors, and that is
selection working, not a regression disappearing.

## What this PR changes

| File | Change |
|---|---|
| `.github/workflows/friday-universe-ci.yml` | `pip install` gains `pytest-testmon`. New `Restore testmon data` step (`actions/cache@v4`, pinned SHA `0057852b…`, key `testmon-<branch>-<sha>` with `testmon-<branch>-` / `testmon-main-` restore-keys). New `Reset testmon data for full-suite run` step (`rm -f .testmondata`, non-PR events only). Engine-suites step runs `pytest --testmon` and echoes cache hit/miss. Coverage-gate step gains `&& github.event_name != 'pull_request'`. No other step, job, trigger, or `if:` touched; REL-120 path filters untouched. |
| `.gitignore` | `.testmondata` / `**/.testmondata` (CI cache only, never committed). |
| `docs/collaboration/TASK-REL-123-EVIDENCE.md` | This doc. |
| `docs/collaboration/WORK_BOARD.yaml` | REL-123 record only: CLAIMED → IN_REVIEW, branch, pr. |

## Design

- **Testmon semantics (verified locally before writing the workflow,
  pytest 9.2.0 + pytest-testmon 2.4.1 — the same major versions CI
  installs):** no data file → every test runs (cache miss = full
  run); no code change since the last run → `N deselected`, exit 0;
  a real code change in one module → only its dependent tests run
  (1 passed, 1 deselected in the scratch experiment); a test file
  change re-runs its tests; a comment-only change selects nothing
  (testmon compares code, not text). A run that selects zero tests
  exits 0, and `--cov` still writes a (partial) coverage JSON.
  Verified against the real repo too: `tests/test_coverage_gate.py`
  with `--testmon`, 7 passed on run 1, 7 deselected on run 2, exit 0
  both; scratch `.testmondata` removed afterwards.
- **Cache design.** `actions/cache@v4` (first use of the cache action
  in this repo; pinned SHA from the `v4` tag, verified via API).
  Key `testmon-<ref_name>-<sha>` is unique per push, so each run
  saves fresh data; restore-keys fall back to the newest cache from
  the same branch, then from main. PRs may read base-branch caches,
  so a PR can reuse main's data from the last merge/nightly full
  run. A stale cache can only over-select (a file whose hash the
  data has never seen counts as changed) — it cannot silently skip
  a test whose dependency changed.
- **Full suite on merge + nightly.** The reset step runs on every
  non-PR event (`push` = merge to main, `schedule` = nightly
  02:00 UTC), deleting restored data before the engine run. With no
  data, `--testmon` selects all tests and writes fresh data, which
  the cache post-step saves under `testmon-main-<sha>` for later
  PRs. No `--testmon` flag is ever dropped: the full run is a
  testmon run with no data, not a different command.
- **Scope: engine suites only.** Only the root engine-suites
  invocation (`tests/test_real_*.py` × 8 + `test_coverage_gate.py`)
  uses `--testmon`. Without the flag the plugin is inactive —
  verified locally: a no-flag run executed all tests and left
  `.testmondata` untouched — so the HTTP-tests step and every
  per-agent venv suite neither read nor write the data file. This
  matters: testmon records the post-run state, so a second
  invocation sharing one data file would find "nothing changed"
  and deselect everything. Per-agent suites keep REL-120 subtree
  gating (they run only when their subtree or a shared path
  changes), which is the selection mechanism for those suites.
- **Two-push live proof.** This PR proves selection with two CI
  runs on its own branch. Push 1 (implementation): no cache exists
  anywhere → cache miss → full engine run, data saved. Push 2
  (workflow comment + board flip + this doc's run-1 results — no
  Python file changes): the branch cache restores → testmon
  selects 0 engine tests → the log shows `N deselected`. Push 2
  must touch the workflow file itself (a comment line) because a
  docs-only push matches no REL-120 filter (`any_code=false`) and
  the engine step would be skipped entirely.

## Guards preserved

- **REL-068 collection guard** (`owner-workflows.yml`, contracts
  job): parses workflow text for test-file references. No test file
  was added, removed, or renamed in any invocation — `--testmon`
  is a flag, not a file-list change — so every test file stays
  collected. The guard step itself is untouched.
- **REL-088 tier-1 collection gate** (`friday-universe-ci.yml`,
  `test` job): still runs unconditionally on every PR, before the
  engine step, without `--testmon`.
- **REL-120 path filters:** the detect job, the dorny filter, the
  `force-full` step, and every step-level `if:` are untouched
  except the coverage-gate `if:` noted above. Nightly cron
  (`0 2 * * *`) untouched.
- **Coverage gate (checklist I5):** still runs on every full-suite
  event (merge/nightly) against the full coverage report. It is
  skipped on PRs only because a selected subset cannot satisfy the
  manifest floors; the gate's purpose — catching a regression
  suite that disappears — is served by the merge/nightly full run
  plus the unconditional tier-1 collection gate on PRs.
- **Required check names unchanged:** `test`, `detect-voice-changes`,
  `voice-regressions`, `docker` untouched; the cache steps are
  steps inside `test`, not new jobs.
- **No test is dropped from the full suite:** selection applies
  only to the PR path; merge-to-main and nightly run everything,
  and the first PR run after any cache loss also runs everything.

## Predicted filter outputs for this PR

This PR touches `.github/workflows/friday-universe-ci.yml`
(`shared`/`any_code` via the workflow file itself) plus this
evidence doc, `.gitignore`, and the board file (in no filter). No
agent subtree is touched. Predicted — same shape as REL-120's
verified prediction:

- `friday-universe-ci.yml` `detect-voice-changes`:
  `shared=true`, `any_code=true`, `voice=false`,
  `siblings=false`, all per-agent outputs `false`.
- Consequence: the `test` job runs FULL (every agent step
  executes, because `shared` is true); `voice-regressions` is
  skipped (`voice=false`) and `docker` is skipped (PR, not main).
- Testmon prediction: push 1 — `testmon: no cached data - full run
  (cache miss)`, all engine tests selected; push 2 —
  `testmon: cached data present - running affected tests only`,
  `N deselected, 0 selected` on the engine step.

## Live proof

- Push 1 — full run on cache miss (head `5a01fdd9`, PR #2328,
  FRIDAY Universe CI/CD run 46130521459, `pull_request`,
  2026-11-28 ~14:57–15:08 IST). 9 checks: 7 success, 2 skipped
  (`docker`, `voice-regressions` — both by design); `mergeable:
  True/clean`. Detect outputs exactly as predicted:
  `shared=true`, `any_code=true`, `voice=false`,
  `siblings=false`, all ten agent outputs `false`
  (detect-voice-changes job 140934416413, `Job duration: 1s`).
  Testmon: `pytest-testmon-2.4.1` installed (pytest 9.2.0);
  cache step: `Cache not found for input keys:
  testmon-2328/merge-d0a6b38f4cb921f570d1b7ebcde2c3435ced5834,
  testmon-2328/merge-, testmon-main-`; engine step printed
  `testmon: no cached data - full run (cache miss)` and
  `testmon: new DB, environment: default`, then `collected 221
  items` / `221 passed in 79.85s` — the full engine suite, as a
  cache miss requires. (The `45 passed in 21.42s` line in the same
  job is the HTTP-tests step, which runs fully without testmon by
  design.) Cache post-step: `Cache saved with key:
  testmon-2328/merge-d0a6b38f4cb921f570d1b7ebcde2c3435ced5834`.
  Tier-1 collection gate: `21/21 collected`. The coverage-gate
  step did not run on this PR (skipped by the new
  `event_name != 'pull_request'` condition — no step log).
  Test job 140934480635, `Job duration: 588s`. Full logs:
  `~/workspace/rel123-work/run1-test.log` (533,989 B) and
  `run1-detect.log` (103,042 B).
- Push 2 — SELECTION PROVEN (head `1a658bc2`, PR #2328, FRIDAY
  Universe CI/CD run 46131633609, `pull_request`, 2026-11-28
  ~15:11–15:20 IST). 9 checks: 7 success, 2 skipped (`docker`,
  `voice-regressions`); `mergeable: True/clean`. Detect outputs
  identical to run 1 (`shared=true`, `any_code=true`, all agent
  outputs `false`). Cache step: `Cache restored successfully`
  from run 1's key
  (`testmon-2328/merge-d0a6b38f4cb921f570d1b7ebcde2c3435ced5834`);
  engine step printed `testmon: cached data present - running
  affected tests only` and `testmon: changed files: 0, unchanged
  files: 51, environment: default`, then `collected 221 items /
  221 deselected / 0 selected` / `221 deselected in 4.32s` —
  all 221 engine tests deselected, zero run, step exit 0
  (`REL-085: test-job step passed (exit 0)`). The push touched no
  Python file, so zero selected is the correct selection, and the
  run proves the cache round-trips branch to branch. The
  deselected run's coverage report reads TOTAL 12% (vs the 16%
  manifest floor) — the concrete reason the coverage gate is
  skipped on PRs. HTTP-tests step still ran fully (`45 passed in
  8.46s`), per-agent venv suites ran fully under REL-120 gating.
  Cache post-step saved the refreshed data under
  `testmon-2328/merge-f1ea2d693f99dfc9ffb96b96347ae2cb33bcad54`.
  Tier-1 gate: `21/21 collected`. Test job 140937927017,
  `Job duration: 414s` (vs 588s on run 1 — the 221-test engine
  run collapsed to 4.32s). Full logs:
  `~/workspace/rel123-work/run2-test.log` (506,471 B) and
  `run2-detect.log` (103,408 B).

## Five states

- implemented: YES (testmon selection on the PR path + cached
  `.testmondata` + full suite on merge/nightly in
  `friday-universe-ci.yml`; `.gitignore`; this doc)
- tested: YES locally (testmon semantics + real repo file, § Design)
  and live on this PR's CI: run 1 cache miss → full engine suite
  (221/221 passed); run 2 cache hit → 221/221 deselected, 0 run
  (§ Live proof)
- merged: NO (PR open, coordinator's call; never merge own PR)
- deployed: N/A (CI config takes effect on merge)
- production-verified: NO until a post-merge full-suite run
  (merge push or first nightly 02:00 UTC) refreshes main's cache
  and confirms the reset path live; the PR-path selection itself
  is proven (§ Live proof push 2)

— Muse 2
