# TASK-REL-120 — CI path filters per agent subtree + per-job duration reporting

- Worker: Muse 2 · Claim: hub #2045 comment 7233809443 (2026-11-28
  ~09:43 IST), per Burn Enforcer 08:00 §B (hub 7232438956).
- Branch: `muse2/task-rel-120-ci-path-filters` from main
  `981a8186` (PR #2258 merge commit).
- Follow-up to REL-068 (collection guard) and REL-069 (validator
  truth); extends REL-106, which did per-subtree step gating +
  duration reporting in `friday-universe-ci.yml` only.

## Verdict (scoped, stated plainly)

On pull requests CI now runs only the jobs/steps for the changed
agent subtrees; on merge to main and on the nightly run the full
suite runs; and every job in every PR-triggered workflow reports its
duration. The two multi-agent workflows (`friday-universe-ci.yml`,
`owner-workflows.yml`) gained a `detect-changes` job whose outputs
gate the per-agent steps; the nine other PR workflows gained
duration reporting (their single-purpose jobs were already scoped
by trigger `paths:`, or are whole-repo gates by design — see the
table). No pytest invocation was added, removed or renamed, so the
REL-068 collection guard still sees every test file; the REL-088
tier-1 gate still runs unconditionally.

## What this PR changes

| Workflow | Change |
|---|---|
| `friday-universe-ci.yml` | `detect-voice-changes`: dorny filter runs on `pull_request` only; new `force-full` step sets every output `true` on any other event (push = merge to main, schedule = nightly); job outputs use the `filter \|\| force-full` fallback. New nightly cron `0 2 * * *` (02:00 UTC / 07:30 IST). Durations already present on all four jobs (REL-106). |
| `owner-workflows.yml` | New `detect-changes` job (dorny filter, same `shared` semantics as REL-106, plus `force-full` on non-PR events). `contracts` job now `needs: detect-changes`; each agent step gated `shared \|\| <agent>`; REL-068 guard step stays unconditional; duration record + report steps added to both jobs. |
| `collaboration-registry.yml`, `secret-scan.yml`, `py311-import-gate.yml`, `lighthouse-ci.yml`, `memora-vector-regression.yml`, `heavy-task-image-build.yml`, `voice-startup-regressions.yml`, `monorepo-validation.yml`, `validate-monorepo.yml` | Duration record + report steps added to each job (same `JOB_START_EPOCH` / `Job duration: Ns` snippet as REL-106, `if: always()` on the report step). No other change. |

No trigger `paths:` were changed anywhere: changing them would
risk silently disabling a gate (the monorepo validators and the
import gate are whole-repo by design) and could strand a required
check on a docs-only PR. Filtering is job/step-level via the detect
jobs, plus the trigger scoping that already existed.

## Design

- **Detect jobs.** One `dorny/paths-filter@v4` step per
  multi-agent workflow (pinned SHA `ceb8a2b8…`, same as REL-106).
  `shared` = the workflow's own file, `scripts/**`, root
  `tests/**`, root config (`pyproject.toml`, `setup.cfg`,
  `requirements*.txt`, `Dockerfile`, `docker-compose*.yml|yaml`);
  any `shared` hit runs the full suite. `any_code` = `shared` plus
  every agent subtree the workflow covers. One output per agent
  subtree (`FRIDAY/**`, `Forge/**`, `Memora/**`,
  `Inference/**`, `Futuris/**`, `IntelX/**`, `Stratex/**`,
  `VyralX/**`; `friday-universe-ci.yml` additionally keeps
  `cortex`, `sentinel`, `siblings`, `voice` from REL-106).
- **Full suite on merge + nightly.** The filter step has
  `if: github.event_name == 'pull_request'`; the `force-full` step
  (`if: github.event_name != 'pull_request'`) writes every output
  `true` to `$GITHUB_OUTPUT`. Job outputs read
  `steps.filter.outputs.X || steps.force-full.outputs.X`: a skipped
  step's outputs are empty, so the fallback fires only when the
  filter did not run; `'false'` is a non-empty string, so a real
  filter result is never overridden. Push to main (merge) and the
  new nightly cron therefore run every step.
- **Duration reporting.** Every job records a start epoch right
  after checkout (`JOB_START_EPOCH`) and ends with an `always()`
  step printing `Job duration: Ns` to the log and the step summary.
  Skipped jobs (e.g. `voice-regressions` when no voice path
  changed, `docker` off main) run no steps and report no duration
  — that is the filter working, not a gap.
- **Whole-repo gates, intentionally unfiltered.** `secret-scan`
  scans the changed-commit range (already diff-scoped);
  `py311-import-gate` imports every agent entrypoint under 3.12;
  `monorepo-validation` / `validate-monorepo` run the root test
  directory + fleet-layout validation. They run on every PR by
  design; REL-120 adds duration reporting only.
- **Already trigger-scoped single-purpose jobs.**
  `collaboration-registry` (docs/collaboration), `lighthouse-ci`
  (FRIDAY/ui/out), `memora-vector-regression` (Memora vector
  files), `heavy-task-image-build` (Forge/Futuris/Sentinel/mesh),
  `voice-startup-regressions` (VoiceCall + runtime audit) only run
  when their paths change; REL-120 adds duration reporting only.

## Guards preserved

- **REL-068 collection guard** (`owner-workflows.yml`, contracts
  job): the guard step is unconditional and no pytest invocation
  was touched — every test file's workflow-text reference is
  intact, so a file shipped in a PR is still collected whenever
  its subtree (or a shared path) changes. Step-level `if:` gating
  does not remove references from the workflow text.
- **REL-088 tier-1 collection gate** (`friday-universe-ci.yml`,
  `test` job): still runs unconditionally on every PR.
- **REL-069 validator**: the board flip in this PR touches only
  the TASK-REL-120 record (status/pr/branch/updated_at/files/
  next_action/evidence); the collaboration-registry workflow
  validates it in CI.
- **Required check names unchanged**: `test`, `contracts` and the
  other job names are untouched; `detect-changes` is a new job
  that always runs and reports.

## Predicted filter outputs for this PR (verified live in § Live proof)

This PR touches 11 workflow files (all `shared` via the two
workflow files themselves) plus this evidence doc
(`docs/collaboration/**`, in no filter). No agent subtree is
touched. Predicted — computed by matching the PR file list
against the filter globs in the edited workflows:

- `friday-universe-ci.yml` `detect-voice-changes`:
  `shared=true`, `any_code=true`, `voice=false`,
  `siblings=false`, `friday=false`, `memora=false`,
  `cortex=false`, `stratex=false`, `forge=false`,
  `inference=false`, `sentinel=false`, `intelx=false`,
  `futuris=false`, `vyralx=false`.
- `owner-workflows.yml` `detect-changes`: `shared=true`,
  `any_code=true`, all eight agent outputs `false`.

Consequence on this PR: the `test` job and the `contracts` job
both run FULL (every agent step executes, because `shared` is
true) — this PR is a shared-path change, so a full run is the
correct behaviour. The per-agent outputs being `false` while
`shared` is `true` is the live proof that the filter
discriminates. `voice-regressions` is skipped (`voice=false`) and
`docker` is skipped (PR, not main) — both by design.

## Live proof

PR #2274 CI run on head `cf71632b` (base `7ecab6ce`), 2026-11-28
~10:16 IST. 10 workflow runs, all completed/success; 14 check-runs:
12 success, 2 skipped (`docker`, `voice-regressions` — both by
design: PR, not main; `voice=false`).

- FRIDAY Universe CI/CD — run 46109068112. `detect-voice-changes`:
  12 changed files detected; `shared=true`, `any_code=true`,
  `voice=false`, `siblings=false`, `friday=false`, `memora=false`,
  `cortex=false`, `stratex=false`, `forge=false`,
  `inference=false`, `sentinel=false`, `intelx=false`,
  `futuris=false`, `vyralx=false` — exactly the predicted outputs.
  `test` ran FULL (per-agent venvs, tier-1 collection gate,
  coverage gate) and passed. `Job duration: 0s`
  (detect-voice-changes), `Job duration: 411s` (`test`).
- Owner Workflow Contracts — run 46109068065. `detect-changes`:
  `shared=true`, `any_code=true`, `friday=false`, `forge=false`,
  `memora=false`, `inference=false`, `futuris=false`,
  `intelx=false`, `stratex=false`, `vyralx=false` — exactly the
  predicted outputs. `contracts` ran FULL and passed.
  `Job duration: 1s` (detect-changes),
  `Job duration: 378s` (`contracts`).
- Other runs, all success: Heavy-Task Runtime Image Build
  46109068097 (`Job duration: 303s`); Secret Scanning 46109068088
  (`2s`); Lighthouse CI 46109068072 (`14s`); Voice startup
  regressions 46109068143 (`32s`); Collaboration Registry
  Validation 46109068204 (`56s`); Python 3.11+ Import Gate
  46109068106 (`63s`); Monorepo Structure and Safety CI
  46109068108 (`143s`) and 46109068212 (`162s`).

Predicted-vs-actual detect outputs match exactly on both detect
jobs: the filter discriminates (per-agent outputs `false` while
`shared` is `true`), and the shared-path PR correctly ran the full
suite. PR #2274 MERGED 2026-11-28 11:21:40 IST (merge `e1fac2be`);
paired VERIFIED by Muse 12 (review 6096031871) and Muse 19
(review 6096155788). Transcribed in the close-out PR — code and
workflow content are byte-identical to the proof head (`cf71632b`);
only this doc and the board flip changed.

## Five states

- implemented: YES (detect jobs + step gating + duration reporting
  in all 11 PR-triggered workflows + this doc)
- tested: YES for the shared/full-run path via this PR's CI (see
  § Live proof); single-subtree skip behaviour verified by
  design + predicted-vs-actual detect outputs, live confirmation
  on the next single-subtree PR post-merge by the paired verifier
- merged: YES (PR #2274, merge e1fac2be, 2026-11-28 11:21 IST)
- deployed: N/A (CI config takes effect on merge)
- production-verified: NO until a post-merge single-subtree PR
  shows the filtered run and the first nightly run (02:00 UTC)
  shows the full suite

— Muse 2
