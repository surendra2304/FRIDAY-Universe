# TASK-REL-116 — Evidence: Fleet CD deploy failure on triggered runs

- **Task:** TASK-REL-116 (diagnosis only; repair is TASK-REL-118, assigned to Muse 13)
- **Author:** Muse 4 — diagnosis, 2026-11-27 ~19:30 IST (continuation of the 17:24 run; the
  17:24 parent run timed out 18:26:43 IST and its diagnosis subagent timed out 18:25:03 IST)
- **Claim:** hub #2045 comment 7217683270 (17:24 IST) · Board (main `7ae846b9`): REL-116 CLAIMED / owner muse_4
- **Branch:** `muse4/task-rel-116-cd-deploy-failure-diagnosis` (base: current main `7ae846b9`)
- **Scope:** diagnose only. No workflow edit, no server change, no restart, no deploy, no merge,
  no hub post. The fix proposal in §6 is a proposal only; it was not applied.

## 1. Root-cause verdict

**Verdict: UNPROVEN at the sub-block level — the exact failing command inside the SSH step
could not be read, because both failed job logs are unfetchable from this VM (see §5).
What the API evidence does prove, and what it rules out, is stated below; the residual
uncertainty is exactly one item: which sub-block of the SSH script exits non-zero.**

Best-supported hypothesis (from step timings + the all-runs pattern, NOT from log text):
the failure is at SSH-transport / early safe-checkout stage, common to both servers —
either the SSH connection itself never establishes (host/key/auth) or the script dies in
the first seconds on-server (branch guard, dirty-tree guard, or `git fetch`), before any
agent restart or health probing. The evidence for this, and what it excludes:

- **Proven:** on every triggered run, BOTH deploy jobs fail at the same single step,
  "Update Changed Agents on Server N" (`appleboy/ssh-action` v1.2.5), and nothing else
  fails. The detect-changes job always succeeds. No deploy job has concluded `success`
  in the whole 30-run window (§4).
- **Proven by timing:** the health gate did NOT fail these runs. Server 2's SSH step dies
  in 3–5 s on every failed run; Server 1's in 10–27 s. A health-gate failure needs at
  minimum a 60 s first-pass probe loop plus a 60 s settle plus a second pass, and a
  restart loop before that — minutes, not seconds. The Memora migration gate, the
  restart loops, the health gate, the second-chance sweep and the Memora smoke probe
  are all ruled out as the failing block by duration alone.
- **Proven by symmetry:** Server 1 and Server 2 fail independently on every triggered
  run with the same signature. That points at a cause shared by both jobs — the SSH
  action invocation and its shared inputs (`secrets.SERVER1_HOST` / `SERVER2_HOST`,
  `secrets.ORACLE_SSH_KEY`, `appleboy/ssh-action@0ff4204d`) or a shared on-server
  precondition — not per-agent code, not one server being down, and not a single
  agent's restart.
- **NOT proven:** whether Server 2 dies at SSH connect/auth (most consistent with a
  3–5 s step) or in the first on-server guard, and whether Server 1 gets further
  (fetch/merge, most consistent with 10–27 s) or just connects more slowly and dies
  at the same place. The two servers may even fail at different sub-blocks. Only the
  job logs close this; they stayed unfetchable (§5).
- **Trigger cause proven:** the target run's head merge (PR #2096, TASK-INT-879) touched
  `.github/workflows/friday-universe-ci.yml`, which matches the `.github/workflows/**`
  glob in BOTH servers' paths-filter, plus `IntelX/**` (Server 2). That is why both
  deploy jobs triggered on a merge whose deployable content was otherwise small.

## 2. Failing run under diagnosis — run 45969056089

- Workflow: "FRIDAY Universe Fleet Continuous Deployment"
  (`.github/workflows/deploy-monorepo.yml`, workflow id 393276861)
- Run: https://github.com/surendra2304/FRIDAY-Universe/actions/runs/45969056089
- Event `push`, head `7175b9b0` (merge PR #2096, TASK-INT-879, merged 2026-11-27T08:52:23Z),
  created 2026-11-27T08:52:26Z, conclusion `failure`, run number 1943.
- PR #2096 files (5): `.github/workflows/friday-universe-ci.yml` (modified),
  `IntelX/docs/STANDING_WATCHES.md`, `IntelX/intelx/watches/engine.py`,
  `IntelX/tests/test_standing_watches.py`, `docs/collaboration/TASK-INT-879-EVIDENCE.md`.
  Trigger: the CI workflow file matches `.github/workflows/**` in both filters; `IntelX/**`
  matches Server 2's filter.

| Job | Job ID | Conclusion | Step that failed | Step window (UTC) | Step secs |
|---|---|---|---|---|---|
| Analyze Changed Agents | 140404702064 | success | — (all steps success) | 08:52:28–08:52:42 | 14 |
| Deploy Core Fleet (Server 1) | 140404815165 | failure | 2 "Update Changed Agents on Server 1" | 08:52:45–08:53:08 | 23 |
| Deploy Specialist Fleet (Server 2) | 140404815222 | failure | 2 "Update Changed Agents on Server 2" | 08:52:45–08:52:48 | 3 |

Source: `run_45969056089.json`, `run_45969056089_jobs.json` (Actions API, saved
`~/workspace/muse4-runs/rel116/`). Both deploy jobs contain exactly one step besides
setup/complete, and that step is the failing one — there is no other step in which the
failure could hide.

## 3. How the SSH step is constructed (workflow as on main)

Workflow file verified byte-identical to main: saved copy's git blob SHA
`a1b11654623c4aedff32e8ed4b1f36b06013528c` matches the blob served for
`.github/workflows/deploy-monorepo.yml` at main `7ae846b9`.

- Trigger: `push` to `main` + `workflow_dispatch`. Concurrency group
  `deploy-monorepo-${{ github.ref }}`, `cancel-in-progress: false`.
- `detect-changes` ("Analyze Changed Agents"): `actions/checkout@v7` +
  `dorny/paths-filter@v4`. Server 1 filter: `Memora/**`, `Forge/**`, `Sentinel/**`,
  `mesh/**`, `deploy/**`, `scripts/**`, `tests/**`, `.github/workflows/**`. Server 2
  filter: `VyralX/**`, `Cortex/**`, `IntelX/**`, `Futuris/**`, plus the same shared
  `mesh/**`, `deploy/**`, `scripts/**`, `tests/**`, `.github/workflows/**`.
- Each deploy job runs only if its filter output is `true` (or on `workflow_dispatch`),
  on `ubuntu-latest`, and consists of ONE action step:
  `appleboy/ssh-action@0ff4204d` (v1.2.5) with `host: ${{ secrets.SERVER1_HOST }}`
  / `SERVER2_HOST`, `username: ubuntu`, `key: ${{ secrets.ORACLE_SSH_KEY }}`,
  and a long inline `script:` executed on the server in `/opt/friday_universe`.
- The script's sub-blocks, in order (Server 1; Server 2 is the same except where noted):
  1. Banner echo; `cd /opt/friday_universe`; `set -euo pipefail` (any later
     non-zero exit aborts the script immediately — this is the failure surface:
     the step reports only the action's exit code, not which line failed).
  2. `DEPLOY_REV="${{ github.sha }}"` + 40-hex validation.
  3. Main-branch guard (TASK-OBS-005): `git branch --show-current` must be `main`.
  4. Dirty-tree guard (TASK-REL-102): `git diff --quiet` + `git diff --cached --quiet`.
  5. `git fetch --no-tags origin "$DEPLOY_REV"`; `git cat-file -e "$DEPLOY_REV^{commit}"`;
     `git merge-base --is-ancestor "$OLD_REV" "$DEPLOY_REV"`; `git merge --ff-only`;
     HEAD-equals-`$DEPLOY_REV` check.
  6. `CHANGED_AGENTS` from `git diff --name-only $OLD_REV HEAD`.
  7. Server 1 only: Memora pre-restart migration gate (TASK-MEM-009).
  8. REL-098 recovery guard: `trap rel098_recover EXIT` (recovery runs only if a
     restart was attempted — with the observed 3–27 s durations no restart was
     reached, so the trap is a no-op here).
  9. Restart loop over Server 1 `Memora, Forge, Sentinel` / Server 2
     `VyralX, Cortex, IntelX, Futuris` (+ `VyralX-Daemon` on Server 2).
  10. Server 2 only: pre-deploy health baseline (TASK-OBS-019) before the restart loop.
  11. Post-deploy health gate (TASK-OBS-001) + 60 s settle + second-chance sweep
      (TASK-OBS-005) + Server 2 pre-existing-degradation filter (TASK-OBS-019).
  12. Server 1 only: Stratex reconciliation timer install (TASK-STR-044) and the
      Memora memory-path smoke probe (TASK-MEM-009).
- Failure surface: with `set -euo pipefail` and a single SSH step, any failing
  sub-block aborts the whole step with no per-block marker in the API record —
  only the job log names the line. That is why the logs are the missing evidence.

## 4. Recent-run breakdown — skip-vs-fail validation

Full 30-run window swept 2026-11-27 ~19:20 IST (`run_breakdowns_full30.json`):
runs 1950–1979 of the workflow (most recent first in the source file), plus the
target run 45969056089 (run 1943, just outside the window).

Tally over the 30 runs:

| Run conclusion | Server 1 deploy job | Server 2 deploy job | Count |
|---|---|---|---|
| success | skipped | skipped | 24 |
| failure | failure | failure | 5 |
| cancelled | (no jobs returned) | (no jobs returned) | 1 |

- **No deploy job concluded `success` in the entire window.** Zero of 30 runs.
- The 5 failed runs in-window: 45996819905 (head `e013e581`, 12:13 UTC),
  45987412916 (`94e6ee48`, 11:04 UTC), 45986179911 (`a284c307`, 10:55 UTC),
  45981981651 (`3b5e6d9a`, 10:25 UTC), 45977028100 (`e9b91a9f`, 09:50 UTC).
  In every one, "Analyze Changed Agents" succeeded and BOTH deploy jobs failed at
  step 2, "Update Changed Agents on Server N" — the identical signature to the
  target run. Step durations across the five: Server 1 SSH step 10–27 s
  (10, 21, 11, 13, 27); Server 2 SSH step 3–5 s (5, 5, 3, 5, 5).
- The 24 successful runs all have BOTH deploy jobs `skipped` — the paths-filter
  passed nothing deployable, so no deploy was attempted and the run succeeded.
- The 1 cancelled run (45981999406, head `ff08b859`, 10:25 UTC) returned an empty
  jobs list from the API; it is excluded from the tally, not counted as a skip.
- With the target run included: **6 consecutive triggered runs failed identically,
  0 triggered deploys succeeded.**

**WATCH215/216 claim — VALIDATED:** "CD skips by paths-filter when nothing deployable
changed and fails when it triggers; no CD deploy has succeeded on any recent main head."
Every success in the window is a skip; every trigger is a failure; no deploy job
succeeded. The claim holds over the full 30-run window, not just a sample.

## 5. The missing evidence — job logs unfetchable (exact gap)

**Logs NOT obtained.** Both failed job logs stayed unfetchable after the bounded retries
prescribed for this task; no further download attempts were made.

What is established:

- The logs endpoint for each failed job is
  `https://api.github.com/repos/surendra2304/FRIDAY-Universe/actions/jobs/<job-id>/logs`
  (jobs 140404815165, 140404815222). It 302-redirects to a temporary download URL.
- Two earlier download attempts (60 s read timeout, `dl_logs.py`, `dl_status.txt`
  13:36–13:38 UTC) both failed with `TimeoutError('The read operation timed out')`
  after ~60 s, having received no bytes.
- This run retried with timeout 300 s, streaming chunked to disk, max 2 attempts per
  job (`dl_logs_retry2.py`, `dl_status_retry2.txt`, 13:45–14:05 UTC). All four attempts
  failed identically with `TimeoutError('The read operation timed out')` at the 300 s
  read timeout, zero bytes received:
  - Server 1 (job 140404815165): attempt 1 13:45:22–13:50:24, attempt 2 13:50:29–13:55:31.
  - Server 2 (job 140404815222): attempt 1 13:55:36–14:00:37, attempt 2 14:00:42–14:05:44.
  No further retries were made, per the task bound.
- A no-follow probe of the same endpoint (same auth, 30 s timeout) returns the 302 in
  ~1.5 s for both jobs, with `Location` host
  `productionresultssa2.blob.core.windows.net`. The GitHub API side is healthy and
  authenticated; **the stall is on the Azure blob host: the redirect target never
  sends data from this VM, even with a 300 s read timeout.**
- No signed download URL was printed or saved anywhere in this task's outputs.

**Exact gap:** the text of the two failed SSH steps — the failing sub-block/command
and the server-side error line — is unknown. Nothing in this document quotes log
lines, because no log lines were obtained. REL-118 (repair) must obtain one failing
job's log from a network path that can reach the blob host (or re-run the deploy with
debug output) before editing the workflow; editing blind risks fixing the wrong block.

## 6. Smallest safe fix — PROPOSAL ONLY (not applied; for REL-118)

1. **Get the log first.** From a host that can reach
   `productionresultssa2.blob.core.windows.net`, download one failed job's log
   (either job; Server 2's 3–5 s failure is the sharpest signal) and name the exact
   failing sub-block. Do not edit the workflow until the block is named.
2. **Then the minimal change, scoped to the named block:**
   - If SSH connect/auth: verify `ORACLE_SSH_KEY` / `SERVER1_HOST` / `SERVER2_HOST`
     secrets and host reachability from a runner; no workflow-logic change needed.
   - If an early guard (branch/dirty-tree/fetch): fix the on-server precondition
     the guard names (checkout branch, dirty tree, fetch) — or, if the guard itself
     misfires, correct that guard only.
   - Add per-sub-block echo markers (e.g. `echo "REL-116: <block> OK"`) so the next
     failure names its block in the log without changing any guard's semantics.
3. **Explicitly out of scope:** changing guard semantics, weakening `set -euo pipefail`,
   removing the health gate, any force-push/reset/stash on the servers, any change to
   the paths-filter globs. Workflow edits ride a coordinator-reviewed PR.

## 7. Sources

- `~/workspace/muse4-runs/rel116/run_45969056089.json` — target run record (API).
- `~/workspace/muse4-runs/rel116/run_45969056089_jobs.json` — target job/step record.
- `~/workspace/muse4-runs/rel116/workflow_runs_recent30.json` — 30 most recent CD runs.
- `~/workspace/muse4-runs/rel116/run_breakdowns_retry2.json` — 5 failed + 4 success
  job breakdowns (sample, before the full sweep).
- `~/workspace/muse4-runs/rel116/run_breakdowns_full30.json` — all-30 job breakdowns.
- `~/workspace/muse4-runs/rel116/sweep_full30.py` — the sweep script.
- `~/workspace/muse4-runs/rel116/deploy-monorepo.yml` — workflow file, verified
  byte-identical to main (`a1b11654623c4aedff32e8ed4b1f36b06013528c`).
- `~/workspace/muse4-runs/rel116/pr2096_files.json` — PR #2096 changed files (trigger proof).
- `~/workspace/muse4-runs/rel116/dl_logs.py`, `dl_status.txt` — first log attempts (60 s).
- `~/workspace/muse4-runs/rel116/dl_logs_retry2.py`, `dl_status_retry2.txt`,
  `dl_logs_retry2.out` — this run's log retries (300 s, max 2 per job).

— Muse 4
