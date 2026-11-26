# TASK-REL-102 — Fleet CD repair route: diagnosis + smallest safe repair

- **Task:** TASK-REL-102 — Fleet CD repair route: diagnose the broken CD path
  end-to-end and file the smallest safe repair.
- **Owner:** Muse 4. **Assigned:** coordinator WATCH135 (hub #1483 comment
  7181402891, 2026-11-26 ~08:36 IST). **Claimed:** hub #1483 comment
  7181480891 (2026-11-26 ~08:45 IST). Board verified AVAILABLE / owner null
  on main `f53ce7f5` before the claim; no competing claim, branch or PR.
- **Branch:** `muse4/task-rel-102-fleet-cd-repair-route` (from main `f06de330`,
  the current main after PR #1949 merged).
- **Acceptance:** diagnose the deploy-monorepo CD path (workflow + health
  gates + rollback) end-to-end from current main; file the root cause + the
  smallest safe repair with staged proof. **No production deploy until
  coordinator hub clearance.**
- **Five states:** implemented YES (diagnosis + repair runbook + staged-proof
  tests) / tested YES (6/6 new tests local, 37/37 with neighbours) /
  merged NO / deployed N/A / production-verified NO (live leg = the runbook
  below executed + a green deploy, gated on coordinator clearance).

## 1. Verdict in one paragraph

The CD workflow is behaving correctly — the break is fleet-side checkout
hygiene, not workflow logic. In the last 30 `deploy-monorepo` runs, **zero**
deploys succeeded: 25 runs skipped both deploy jobs (board-only merges) and
the 5 runs that actually triggered a deploy all failed — 4 of them in
**both** jobs at the single SSH step, and 1 (PR #1929, Sentinel-only, so
only the S1 filter matched) in the S1 job alone. Each server trips a *different* SAFE CHECKOUT guard,
and each guard is refusing to deploy rather than deploying over a bad
checkout: **Server 1 has tracked modifications** (2 modified + 1 deleted
file) and trips the dirty-tree guard; **Server 2's checkout is parked on
Muse 10's VOI-044 branch** and trips the TASK-OBS-005 branch guard. No
workflow code change is needed to fix the 5 failures. The repair is two
small fleet-side state corrections (runbook in §4), plus a watchdog so the
failure mode — which has now recurred after the D9 recurrences of
2026-11-16/17 — is caught before the next deploy instead of by it.

## 2. The CD path as it exists on main `f06de330`

Verified first-hand from `.github/workflows/deploy-monorepo.yml`,
`rollback-deploy.yml`, `scripts/rollback_deploy.sh` (read) and
`deploy/deploy_fleet.sh` (read).

| Step | Where | What happens |
|---|---|---|
| Trigger | `deploy-monorepo.yml` | `push` to `main` + `workflow_dispatch`. `detect-changes` (dorny/paths-filter v4) sets `server1` / `server2` booleans. |
| S1 deploy | `deploy-server1` job | SSH (appleboy/ssh-action v1.2.5, secrets `SERVER1_HOST` + `ORACLE_SSH_KEY`) into `/opt/friday_universe`: SAFE CHECKOUT (branch guard TASK-OBS-005 → dirty-tree guard → fetch → ancestor check → `--ff-only` merge) → MEM-009 Memora migration gate → restart Memora / Forge / Sentinel (only if `LoadState=loaded`) → STR-044 timer install → health gate (OBS-001 + OBS-005 second-chance sweep) → MEM-009 memory-path smoke probe. REL-098 EXIT-trap recovery guard throughout. |
| S2 deploy | `deploy-server2` job | Same SAFE CHECKOUT → restart VyralX / Cortex / IntelX / Futuris (+ VyralX-Daemon) → health gate with OBS-019 pre-deploy baseline + pre-existing-degradation filter. |
| Rollback | `rollback-deploy.yml` (manual, confirmation-gated) | SSH both servers → `scripts/rollback_deploy.sh <target-sha>` (refuses any target that is not an ancestor of the deployed HEAD) → public-gateway `/health` check of all 10 agents. Last run 2026-11-22, success (manual). |
| Not CD | `deploy/deploy_fleet.sh` | Legacy 17-line Docker Compose script (`docker compose build/up`). Docker is not running on the fleet (verified 2026-10-26: `docker ps` empty, Swarm inactive). Dead code path — not the CD route. |

Health-gate and restart behaviour was already verified by REL-098
(PR #1668, IN_REVIEW): S1 agent map `(Memora Forge Sentinel)`, masked /
not-found units skipped (OBS-006), moved/sleeping units never revived by
the recovery guard.

## 3. Evidence

### 3.1 The last 30 deploy runs: 0 deploys, 5 failures, 25 vacuous passes

Read first-hand from the GitHub API
(`/actions/workflows/deploy-monorepo.yml/runs` + per-run `/jobs`), 2026-11-26.

- **Both-deployed-OK: 0. Both-skipped: 25. Any-deploy-failed: 5. Mixed: 0.**
- The 5 failures (all 2026-11-26; `detect-changes` succeeded in each):
  runs 45728251043, 45728272752, 45737375597 and 45740553832 failed in
  **both** deploy jobs at the single SSH step; run 45737535632 (PR #1929,
  Sentinel-only change, so only the S1 filter matched) failed the S1 job
  with S2 skipped:
  - Run 45728251043 — merge PR #1916 (REL-099), 00:22:19 UTC
  - Run 45728272752 — merge PR #1918 (LAP-004), 00:22:30 UTC
  - Run 45737375597 — merge PR #1917 (INT-037), 01:40:48 UTC
  - Run 45737535632 — merge PR #1929 (SEN-027, Muse 4), 01:42:14 UTC
  - Run 45740553832 — merge PR #1933 (LAP-003), 02:09:44 UTC
- The 25 "success" runs are vacuous: both deploy jobs `skipped`
  (board-only merges match neither paths-filter). Every merge that
  touches agent code has failed to deploy since at least 05:52 IST
  2026-11-26; nothing has deployed in the 30-run window.
- Cross-check: `fleet-backup.yml` last 30 runs are 13 success / 10 failure /
  7 cancelled — the backup lane has its own failures (REL-099's lane, not
  CD), but the deploy failures above are not a GitHub-side outage: the
  same runners, secrets and SSH action succeed on other workflows.

### 3.2 Server 1 root cause: dirty tracked tree → dirty-tree guard

Read first-hand via the bridge (read-only `run_shell`, server 1),
2026-11-26 ~10:35 IST. No state changed.

```
$ git -C /opt/friday_universe branch --show-current   -> main
$ git -C /opt/friday_universe rev-parse --short HEAD  -> b51ef05f
$ git -C /opt/friday_universe status --porcelain=v1 --untracked-files=no
 M Futuris/futuris/integrations/memora_cloud_fallback.py
 M Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py
 D VyralX/tests/test_vyr057_pool.py
$ git -C /opt/friday_universe rev-parse origin/main  -> cc66b42d (at read time)
```

- The branch guard **passes** (on `main`). The dirty-tree guard
  **fails**: `git diff --quiet` is non-zero, so the job prints
  `::error::Tracked collaborator changes present; refusing deployment
  without modifying them.` and exits 1 — before any fetch, restart or
  health gate. Every S1 deploy fails at this line until the three
  tracked changes are reconciled (committed through a reviewed PR or
  reverted). S1 is also behind main (`b51ef05f` vs `cc66b42d` at read
  time; main has since moved to `f06de330`), which the ff-only merge
  will repair once the tree is clean.

### 3.3 Server 2 root cause: checkout parked on a task branch → branch guard

Read first-hand via the bridge (read-only `get_system_info` + `git_status`,
server 2, two reads), 2026-11-26 ~10:30–10:50 IST. No state changed.

```
On branch: muse10/task-voi-044-acceptance-run-27
Status: (untracked files only — venv dirs, bridge scratch files, tmp/, var/)
```

- The TASK-OBS-005 branch guard **fails**: `git branch --show-current`
  is `muse10/task-voi-044-acceptance-run-27`, not `main`, so the job
  prints the `TASK-OBS-005 branch guard` error naming the branch and
  exits 1 — before any fetch. The dirty-tree guard would pass (clean
  tracked tree); the branch guard is the sole trip.
- **No stranded work:** S2 HEAD `73b2ec2e` is exactly the pushed tip of
  `muse10/task-voi-044-acceptance-run-27` on origin (refs API, verified
  2026-11-26). Returning S2 to `main` loses nothing — but it must be
  coordinated with Muse 10: the VOI-044 acceptance run is live on S2
  right now (the checkout advanced `256ae701` → `73b2ec2e` between my
  reads), so restoring `main` mid-run would disrupt it.
- **TP8's carried note is not reproduced:** "S2 clone origin/main stuck
  at `ce061d9e` (fetch permission issue)" — `origin/main` on S2 read
  `02b86511`, the then-current main, at ~10:45 IST. The fetch path
  works; the branch guard exits before `git fetch` ever runs, so
  `origin/main` simply stops advancing while the checkout is parked.
- The parking predates the first failure (05:52 IST): the guard was
  built for exactly this defect class (D9, three recurrences
  2026-11-16/17) and is doing its job.

### 3.4 What is NOT broken

- The SSH path itself: both servers report ONLINE via the bridge, and
  the same secrets/action succeed on the rollback workflow (last run
  2026-11-22) and on `reconcile-server1-state.yml` snapshots. The
  failures are guard exits inside the remote script, not connection
  failures.
- The health gates, restart loops and recovery guard: untouched by this
  diagnosis; REL-098 already verified them, and no deploy has reached
  them since 05:52 IST.
- The rollback path: `rollback-deploy.yml` + `scripts/rollback_deploy.sh`
  are intact. One doc drift found: the rollback workflow's header comment
  still says the deploy moves servers forward with
  `git reset --hard origin/main` — the deploy has used safe ff-only merge
  since the OBS-005 work. Comment-only drift, not a break; flagged for a
  follow-up touch, not fixed in this PR (see §5).

### 3.5 Structural gap found (not the cause of the 5 failures — follow-up)

Since the 2026-11-24 fleet move, `deploy-monorepo.yml` covers **only
Oracle Server 1 + 2**. There is no deploy job for FRIDAY-Server,
Stratex-Server, VyralX-Server or IntelX-Server, and the paths-filter
covers **neither** `FRIDAY/**`, `Inference/**` nor `Stratex/**` — so a
merge touching only those trees triggers **no** deploy job at all, silently.
`VyralX/**`, `IntelX/**`, `Futuris/**` *do* trigger the S2 job, but S2's
units for them are masked/sleeping backups (they live on AWS now): the S2
job pulls the code and skips the restart, so the live AWS hosts never
receive it. This is a real coverage hole that the 5 failures mask (nothing
deploys anywhere right now), but fixing it means building AWS deploy jobs
— a scoped follow-up task, not part of the smallest safe repair.

## 4. Smallest safe repair (runbook — needs coordinator hub clearance)

No production deploy by the worker; each step is a fleet-side state
change for the coordinator (or a worker acting on the coordinator's
explicit direction on the hub).

1. **Server 2 — return the checkout to `main`** (only after Muse 10's
   VOI-044 acceptance run ends, or on Muse 10's confirmation on the hub):
   on S2, `git checkout main`, then `git fetch --no-tags origin` and
   `git merge --ff-only origin/main` (the deploy's own safe-checkout
   steps, by hand). Verify: `git branch --show-current` → `main`,
   `git status --porcelain --untracked-files=no` empty,
   `git rev-parse HEAD` == current main. Nothing is lost: the VOI-044
   tip is pushed on origin.
2. **Server 1 — reconcile the three tracked changes:** the coordinator
   reviews `git diff` on S1 for
   `Futuris/futuris/integrations/memora_cloud_fallback.py`,
   `Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py`
   and the deleted `VyralX/tests/test_vyr057_pool.py`; either commit them
   through a reviewed PR (if they are wanted work) or revert them
   (`git checkout -- <paths>` + restore the deleted test). Verify: clean
   tracked tree on `main`.
3. **Prove it:** re-run `deploy-monorepo` via `workflow_dispatch` (or
   wait for the next merge that touches agent paths). Both deploy jobs
   must conclude **success with real restarts and health gates**, not
   skips. Record the run id + job conclusions on the hub as the live
   evidence; that closes the production-verification leg of this task.
4. **Prevention (proposed, not built here):** a scheduled checkout-state
   watchdog — extend `reconcile-server1-state.yml` to Server 2 and put
   it on a schedule (it is manual-only today, S1-only), or a new
   workflow that alerts when either deploy checkout leaves `main` or
   gains tracked modifications. D9 has now recurred after its November
   16/17 occurrences because nothing watches the state between deploys.

## 5. What this PR changes

- `docs/collaboration/TASK-REL-102-FLEET-CD-REPAIR-ROUTE.md` (this file).
- `tests/test_fleet_cd_rel102_checkout_guards.py` — 6 staged-proof tests
  (see §6).
- `.github/workflows/deploy-monorepo.yml` — **comment-only**: `BEGIN/END
  DIRTY-TREE GUARD (TASK-REL-102)` markers around the existing dirty-tree
  guard in both jobs, so the tests execute the exact block that deploys
  (same pattern as the TASK-OBS-005 / TASK-REL-098 markers). No behaviour
  change.
- `docs/collaboration/WORK_BOARD.yaml` — REL-102 AVAILABLE → IN_REVIEW,
  owner `muse_4`, branch + PR set.

**Merge note:** merging this PR touches `tests/**` and
`.github/workflows/**`, both of which are in the deploy paths-filter — so
the merge itself will trigger `deploy-monorepo`, and both deploy jobs
will fail until the §4 runbook is executed. That failure is expected and
is itself the before-evidence; it does not block this PR (CI is separate
from CD).

## 6. Staged proof

`tests/test_fleet_cd_rel102_checkout_guards.py` extracts the exact guard
blocks from the workflow and executes them under bash in scratch git
repos reproducing the observed server states:

- S2 state (parked on `muse10/task-voi-044-acceptance-run-27`, clean tree):
  branch guard exits 1 naming the branch; dirty-tree guard exits 0.
- S1 state (on `main`, the exact tracked M/M/D set): branch guard exits 0;
  dirty-tree guard exits 1 with "Tracked collaborator changes present"
  (the porcelain output is asserted file-for-file).
- Clean `main` checkout: both guards exit 0.
- Staged-only modification also trips the dirty-tree guard (the guard
  checks the index too).
- Structural pins: exactly two dirty-tree guard blocks, byte-identical,
  each after its job's branch guard and before its ff-only merge.

Local results (rel101-venv, pytest 9.2.0):
`tests/test_fleet_cd_rel102_checkout_guards.py` — **6/6 passed**;
with neighbours (`test_fleet_cd_branch_guard.py`,
`test_fleet_cd_rel098_recovery_guard.py`, `test_fleet_cd_s2_health_gate.py`)
— **37/37 passed**. Workflow YAML parses; `py_compile` clean.

## 7. Notes / open items

- **Log-download approval 417e6487** (requested 2026-11-26 08:45:50 IST,
  to fetch the failed deploy job logs from GitHub's log storage): still
  awaiting the user's decision, but **no longer needed for this
  diagnosis** — the failing guard on each server was proven by direct
  read-only bridge reads + the API job metadata instead. It can lapse.
- **REL-101** (queue head ahead of REL-102) merged as PR #1949
  (`f06de330`) while this run was in flight; REL-102 is now the queue
  head. The next pool pull is named in the completion post on #1483.
- The S1 dirty files' provenance (who edited them on S1, and whether
  they are wanted work) is for the coordinator to determine from the
  on-server diff at runbook step 2 — it does not change the diagnosis.
- Subagent mapping of the CD path (workflows + `deploy/` + docs) was
  commissioned in this run; its report, if it adds anything beyond §2,
  will be folded in by a follow-up commit.
