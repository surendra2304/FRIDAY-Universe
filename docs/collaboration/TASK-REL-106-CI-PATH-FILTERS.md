# TASK-REL-106 — CI path filters per agent subtree + per-job duration reporting

Worker: Muse 7. Hub: issue #2045 (claim comment 7214096586).
Branch: `muse7/task-rel-106-ci-path-filters`.

## What changed

Only `.github/workflows/friday-universe-ci.yml` (plus this evidence doc).

1. **Per-subtree change detection.** The existing `detect-voice-changes`
   job (dorny/paths-filter, same base logic as the voice filter) now also
   emits: `shared`, `any_code`, `siblings`, and one output per agent
   subtree (`friday`, `memora`, `cortex`, `stratex`, `forge`,
   `inference`, `sentinel`, `intelx`, `futuris`, `vyralx`).
   - `shared` = the CI workflow itself, `scripts/**`, root `tests/**`,
     and root config (`pyproject.toml`, `setup.cfg`,
     `requirements*.txt`, `Dockerfile`, `docker-compose*.yml|yaml`).
     Any `shared` hit runs the full suite.
   - `any_code` = `shared` plus every agent subtree.
   - `siblings` = the eight sibling trees the F821 lint covers.
2. **Step gating in the `test` job** (now `needs: detect-voice-changes`):
   - Tier-1 collection gate (REL-088): always runs — it is cheap and is
     the fixed-list unwiring guard.
   - Install dependencies, engine suites + coverage gate, HTTP tests:
     `any_code` (cross-agent suites; any agent change can break them).
   - FRIDAY lint: `shared || friday`. Sibling F821 lint:
     `shared || siblings`.
   - Each agent tier-1 step (and Memora vector regressions, VyralX
     ffmpeg install): `shared || <that agent>`.
   - Board/docs-only PRs match no filter: every agent suite is skipped,
     the `test` job still runs and reports green in seconds — no
     required check is left pending.
3. **Per-job duration reporting.** Every job (`test`,
   `detect-voice-changes`, `voice-regressions`, `docker`) records a
   start epoch right after checkout and ends with an `always()` step
   that prints `Job duration: Ns` to the log and the step summary.

## Guards preserved

- **REL-068 collection guard** lives in `owner-workflows.yml`
  (contracts job) and is untouched. Every pytest invocation stays in
  the workflow text, so a test file shipped in a PR is still collected
  whenever its subtree (or a shared path) changes.
- **REL-088 tier-1 collection gate** still runs unconditionally.
- Required check names are unchanged (`test` job kept; gating is at
  step level), so board-only and docs-only PRs still report green.

## Live proof

- This PR touches the workflow file (`shared`), so its own CI run is a
  full-suite run: detect outputs show `shared=true`, all agent steps
  execute, and every job log ends with a `Job duration:` line. The
  run/check evidence is cited in the PR body and hub status.
- Board-only and single-agent filter behaviour can only be observed on
  PRs opened after this change merges (paths-filter evaluates the
  whole PR diff). The paired verifier confirms on the next board-only
  PR (agent steps skipped, `test` green fast) and the next
  single-agent PR (only that agent's tier-1 step plus the cross-agent
  engine suites run).

## Five states

- implemented: YES (workflow change + this doc)
- tested: YES for the shared/full-run path via this PR's CI;
  board-only/single-agent filtering verified by design + detect
  outputs, live confirmation post-merge by the paired verifier
- merged: NO (awaiting coordinator merge)
- deployed: N/A (CI config takes effect on merge)
- production-verified: NO until a post-merge board-only PR shows the
  filtered run

— Muse 7
