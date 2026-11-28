# TASK-REL-125 — CI path filters per agent subtree + per-job duration reporting

Worker: Muse 7. Hub: issue #2045 (claim comment 7237473574).
Branch: `muse7/task-rel-125-ci-jobs-per-subtree`.
Assignment: WATCH267 §C (hub 7237371867), after the PR #2327 verdict
(VERIFIED, review 6096994384).

## Gap closed

TASK-REL-106 delivered per-subtree change detection with step-level
gating inside one `test` job. REL-125's acceptance requires
path-filtered CI **jobs** per agent subtree. This change splits the
agent tier-1 steps out of the `test` job into ten per-agent jobs,
gated at job level by the same `detect-voice-changes` outputs.

## What changed

Only `.github/workflows/friday-universe-ci.yml` (plus this evidence doc).

1. **Ten per-agent jobs** — `test-friday`, `test-memora`,
   `test-cortex`, `test-stratex`, `test-forge`, `test-inference`,
   `test-sentinel`, `test-intelx`, `test-futuris`, `test-vyralx`.
   Each has `needs: detect-voice-changes` and a job-level
   `if: shared == 'true' || <agent> == 'true'`, so a PR touching one
   agent subtree runs only that agent's job (plus the cross-agent
   `test` job); a board/docs-only PR skips all ten.
2. **Step bodies moved verbatim.** Every agent tier-1 step (and the
   Memora vector regressions, VyralX ffmpeg install) moved with its
   run body unchanged; only the now-redundant step-level `if:` was
   removed and the REL-086 failure-summary `--job`/`--check` labels
   updated to the new job id. Verified: all 15 pytest invocations in
   the workflow are byte-identical before/after.
3. **`test` job preserved.** Same job id (required-check name
   unchanged), keeping the REL-088 tier-1 collection gate
   (unconditional), both lints, engine suites + coverage gate, HTTP
   tests, and test-results upload.
4. **Per-job duration reporting on every job.** Each new job records
   a start epoch after checkout and ends with the same `always()`
   `Job duration: Ns` step REL-106 added; all 14 jobs in the
   workflow now report durations. The per-job duration report from
   this PR's CI run is filed in the PR body / hub completion post.

## Guards preserved

- **REL-068 collection guard** (owner-workflows contracts job):
  untouched; every pytest invocation stays in the workflow text, so
  a shipped test file is still collected whenever its subtree (or a
  shared path) changes.
- **REL-088 tier-1 collection gate**: still unconditional in `test`.
- **Non-PR events**: `detect-voice-changes` forces every output true
  off-PR (REL-120 nightly), so push/schedule runs execute all jobs.
- Skipped per-agent jobs report as skipped, never pending, so
  board-only PRs still go green fast.

## Live proof

This PR touches the workflow file (`shared`), so its own CI run is a
full run: all ten per-agent jobs execute and report durations. The
run id, per-job durations, and check list are cited in the PR body
and hub completion post. Single-agent and board-only filtering can
only be observed on PRs opened after merge (paths-filter evaluates
the whole PR diff); the paired verifier confirms on the next
single-agent PR (only that agent's job runs) and the next board-only
PR (all ten skipped, `test` green fast).

## Five states

- implemented: YES (workflow change + this doc)
- tested: YES for the shared/full-run path via this PR's CI
  (evidence in PR body); single-agent/board-only filtering verified
  by job-level `if` + detect outputs, live confirmation post-merge
- merged: NO (awaiting coordinator merge)
- deployed: N/A (CI config takes effect on merge)
- production-verified: NO until a post-merge single-agent PR shows
  only that agent's job running

— Muse 7
