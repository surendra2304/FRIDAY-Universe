# REL-098 guard verification — verdict: COVERED, no gap

Worker: Muse 3. Branch: `muse3/rel-098-guard-verification`, base main `b2374d2a`.
Assignment: coordinator watch 7136585984 (20:57 run, hub #1483) — "verify on main
that merged REL-098's guard covers the S2 deploy-failure step-log diagnosis, and
file the verdict as an evidence doc via PR (no new board record; verdict doc only).
If the guard does NOT cover it, file the gap precisely instead of a pass."
Claim: hub #1483 comment 7136957915, 2026-11-24 ~21:30 IST.
No live deploy, restart, or server touch was performed in this task.

## 1. The diagnosed failure

Fleet CD run 45389036905 (head `8034ab1f`, PR #1663 STR-047 scope, 2026-11-24
17:28 IST), conclusion `failure`. Jobs API, verified first-hand this run:

- Analyze Changed Agents — `success`.
- Deploy Specialist Fleet (Server 2), job 138427617805 — `failure`, at step 2
  "Update Changed Agents on Server 2" (8 s duration).
- Deploy Core Fleet (Server 1) — `success`.

Step-log evidence: the job's raw log requires sign-in on the GitHub UI, so the
log lines below come from the check-run annotations API (job 138427617805),
verified first-hand this run — exactly 2 annotations, quoted verbatim:

- `Process completed with exit code 1.`
- `TASK-OBS-005 branch guard: /opt/friday_universe is checked out on branch
  '<detached HEAD>' instead of 'main' — refusing to fast-forward. Return the
  checkout to the main branch and re-run this deploy.`

Phase of the failure: the main-branch guard at the start of the BEGIN SAFE
CHECKOUT block — before `git fetch` / `git merge --ff-only`, before
changed-agent detection, before the `SERVER2_AGENTS` map, before the
pre-deploy health baseline, before the restart loop, before the VyralX-Daemon
block, and before the post-deploy health gate. No agent service (VyralX,
Cortex, IntelX, Futuris, VyralX-Daemon) was being restarted when it failed,
and no `systemctl restart` had run earlier in the step. The 8 s duration is
consistent with this early exit.

## 2. The guard on main

`.github/workflows/deploy-monorepo.yml` on main (548 lines, sha `bf96c137`;
unchanged by the three board-only commits since `b2374d2a`, verified via the
compare API — only `docs/collaboration/WORK_BOARD.yaml` changed):

- S2 job: branch guard line 339; `SERVER2_AGENTS=("VyralX" "Cortex" "IntelX"
  "Futuris")` line 364; `trap rel098_recover EXIT` line 393; first
  `sudo systemctl restart` line 442; VyralX-Daemon restart line 454.
- S1 job: same guard, trap line 164. The two guard blocks are byte-identical
  (diff verified this run; pinned by test
  `test_guard_blocks_identical_and_placed`).
- `RESTART_ATTEMPTED` is recorded BEFORE every `systemctl restart` in both
  loops and in the VyralX-Daemon block. On a non-zero exit with a non-empty
  attempted set, the trap makes one bounded `reset-failed` + `start` per
  attempted agent found inactive (LoadState `loaded` and not active), then
  exits with the ORIGINAL failure code.
- `scripts/rollback_deploy.sh` on main carries the same guard (trap line 191),
  scoped to the run's affected set, with `SERVER1_SERVICES=(Memora Forge
  Sentinel)` (the REL-098 map fix present).
- Staged S2 coverage in `tests/test_fleet_cd_rel098_recovery_guard.py` on main
  (sha `5de3c2d0`): `test_s2_restart_failure_recovers_intelx` and
  `test_s2_daemon_restart_failure_recovers_daemon` execute the real job script
  under fakes; 12/12 new tests pass per the REL-098 evidence doc.

## 3. Coverage, phase by phase

| Failure phase in the S2 step | Guard behaviour | Covered? |
|---|---|---|
| Main-branch guard / safe checkout (the diagnosed run) | Trap not yet installed; attempted set empty; no restart ever attempted, nothing left stopped — no recovery owed, guard correctly does nothing | Yes — no-op is the correct behaviour |
| Restart loop (`systemctl restart` fails) | Attempted set already holds the agent; trap recovers it if found inactive, exit keeps the original code | Yes |
| VyralX-Daemon block fails | `VyralX-Daemon` already in the attempted set before its restart | Yes |
| Later step fails (health gate, timer install) | Trap fires; starts any attempted agent found inactive, starts nothing healthy | Yes |
| Failure before any restart (dirty checkout, baseline) | Attempted set empty; guard no-ops; nothing stranded | Yes — no-op is correct |

Scope check: the guard only ever touches the attempted set, so moved/sleeping
units are never revived — the S2 job's own comment names VyralX on Server 2,
and the loop only records agents whose LoadState is `loaded`.

## 4. Verdict

**COVERED — no gap filed.** The diagnosed S2 failure left no agent stopped
and needed no recovery; the failure shape that WOULD strand an agent (a
restart-loop or later-step failure after a restart attempt) is covered by the
merged guard in the S2 job, in the S1 job, in the rollback script, and in the
staged tests.

Two notes, neither a gap:

- The diagnosed run's underlying cause — the S2 checkout sitting on a detached
  HEAD — is a separate pre-existing condition, not something the guard
  addresses. It needs the checkout returned to `main` and a re-run, exactly as
  the guard message itself says.
- The guard has still never run on a live host (staged proof only, per the
  REL-098 evidence doc §4). Live proof of the guard on a real CD failure
  remains owed (REL-098 §5) and is outside this verification's scope; it needs
  a Muse ruling under the owner stop order.

## Status

- Implemented: yes (this verdict doc).
- Tested: verification by first-hand API + log evidence; no code changed, no
  tests run — not applicable as a code change.
- Merged: no — verdict PR open, awaiting Muse.
- Deployed: not applicable — documentation only.
- Production-verified: not applicable — the guard's live proof is still owed
  (see §4).

— Muse 3
