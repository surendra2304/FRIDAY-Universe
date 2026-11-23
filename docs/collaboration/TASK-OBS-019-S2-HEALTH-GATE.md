# TASK-OBS-019 — Fleet CD S2 post-deploy health gate: pre-existing Futuris/IntelX 503s no longer fail the S2 job

- **Task:** TASK-OBS-019 (P1), owner muse_4
- **Assigned:** Muse (coordinator) in watch 7094281062 (2026-11-23 ~12:53 IST), queue tail (STR-EXP-007 → STR-EXP-008\* → OBS-019\*)
- **Claimed:** issue #35 comment 7094618855 (~13:12 IST); claim PR #1472 MERGED (merge f174deae, main HEAD at implementation time)
- **Branch:** `muse4/task-obs-019-cd-s2-health-gate`
- **Implemented:** 2026-11-23 ~13:24–13:40 IST, this run

## The defect

Fleet CD run 45122467146 (workflow_dispatch, head 136533e5) re-syncing the fleet after the OBS-013 G4 repair: S1 job success, S2 job failure at "Update Changed Agents on Server 2". Same failure recurred on push CD run 45124516836. Probable cause (NOT proven from the job log — see the open question below): the S2 post-deploy health gate fails on pre-existing Futuris + IntelX `/health` 503s.

Root cause in code (`.github/workflows/deploy-monorepo.yml`, S2 job, TASK-OBS-001 gate): after the restart loop, the gate curls every S2 agent's `/health` (Futuris :8004, IntelX :8005, Cortex :8009, VyralX :8010; masked/not-found units skipped per TASK-OBS-006) with a 12×5s retry plus a second-chance sweep, and any agent still non-2xx lands in `FAILED_HEALTH`, which fails the whole job (`exit 1`). The gate never asks whether the agent was already unhealthy *before* the deploy — so a healthy deploy is failed by a pre-existing outage it did not cause.

Premise re-verified live this run (S2 bridge probe, 2026-11-23T08:03:34Z / 13:33:34 IST): `:8004 Futuris → 503`, `:8005 IntelX → 503`, `:8009 Cortex → 200`, `:8010 VyralX → 000` (connection refused — VyralX is masked on S2 since it moved to AWS U2; the gate already skips it). The 503s are still pre-existing at implementation time.

## The fix (S2 job only; S1 gate untouched)

Two marked blocks in `.github/workflows/deploy-monorepo.yml`, both confined to the `deploy-server2` job:

1. **Pre-deploy health baseline** (`BEGIN/END PRE-DEPLOY HEALTH BASELINE (TASK-OBS-019)`), inserted between the `SERVER2_AGENTS` definition and the restart loop: before any restart, probe each S2 agent's `/health` (3 attempts × 5s, so a transient blip cannot misclassify a healthy agent as degraded) and record `HEALTHY_BEFORE` plus `BASELINE_TAKEN=yes`. Masked/not-found units are skipped, mirroring the gate.
2. **Pre-existing-degradation filter** (`BEGIN/END PRE-EXISTING DEGRADATION FILTER (TASK-OBS-019)`), inserted after the second-chance sweep and before the final failure block: a `FAILED_HEALTH` agent that was already unhealthy before this deploy is a loud `::warning::` (the degradation stays visible), not a job failure. Only a healthy→unhealthy **regression** still fails the job. Fail-closed: if the baseline never ran (`BASELINE_TAKEN` empty), nothing is downgraded.

Design choice, stated plainly: the degraded set is **measured fresh on every run**, not a hard-coded Futuris/IntelX list. A hard-coded list would bake today's outage into the workflow and stop failing even if a fixed agent regressed; the baseline re-arms the gate automatically the moment an agent is healthy again. The 503s themselves are NOT changed — out of scope, per the assignment.

## S2 `.git/objects` preventive repair (authorised inside this task)

Same narrow scope as the S1 G4 repair (coordinator watch 7094281062), executed live on S2 via the bridge this run: `sudo chown -R ubuntu:ubuntu /opt/friday_universe/.git/objects` — rc=0; non-ubuntu entries **13 → 0** (including the same pack-1716efea from the 04:28 IST OBS-009 drill window); non-ubuntu group entries 0; `git fetch origin main` rc=0 (origin/main now f174deae); `git fsck` rc=0. S2 checkout HEAD remains ca2c586f (behind main, as expected — the next CD run fast-forwards it; the fetch path it needs is now clear).

## Tests

New `tests/test_fleet_cd_s2_health_gate.py` (12 tests), following the established `tests/test_fleet_cd_branch_guard.py` pattern: the marked blocks are extracted from the workflow file and **executed under bash** with fake `curl` / `systemctl` / `sleep` on PATH, so what is tested is what deploys.

- Baseline records healthy agents only (`HEALTHY_BEFORE=[ VyralX Cortex]`, `BASELINE_TAKEN=yes`); failing agents retried 3× (curl log: 8004×3, 8005×3, 8009×1, 8010×1); masked units skipped and never probed.
- Filter downgrades pre-existing 503s to `::warning::` (job passes); keeps a healthy→unhealthy regression (job fails); mixed set warns one / keeps one; fails closed when the baseline never ran; empty `FAILED_HEALTH` is a no-op.
- Combined sequence reproducing run 45122467146's shape (baseline with Futuris/IntelX 503 → gate fails both → filter) exits 0; the regression twin exits 1.

Run locally this run (scratch tree, pytest 9.2.0 venv): **19 passed** — 12 new OBS-019 tests + 7 existing branch-guard tests, no regressions. Both job scripts pass `bash -n`.

## Files

- `.github/workflows/deploy-monorepo.yml` — S2 job only: +42-line baseline block, +22-line filter block (no S1 change, no guard/second-chance change)
- `tests/test_fleet_cd_s2_health_gate.py` — new, 12 tests
- `docs/collaboration/TASK-OBS-019-S2-HEALTH-GATE.md` — this evidence
- `docs/collaboration/WORK_BOARD.yaml` — OBS-019 record: CLAIMED → IN_REVIEW, pr set, evidence + next_action

## States

- **implemented:** YES (this run)
- **tested:** YES — 19/19 local pytest; CI on the work PR to be verified on its final head (Muse merges only)
- **merged:** NO — work PR open, awaiting Muse
- **deployed:** NO — the fix reaches the fleet via Fleet CD after merge
- **production-verified:** NO — proof requires a CD run whose S2 job succeeds while Futuris/IntelX remain 503; that run can only happen after the merge (a push triggers CD). The proof run is the acceptance criterion, not this PR.

## Open / owed

1. **IntelX 12:00:36 IST restart — still NOT confirmable.** The CD job log is unread: approval `9fcd7226` (read `productionresultssa14.blob.core.windows.net`) is **still pending** — verified this run via the permissions list (approval_id `9fcd7226-8fbb-44a6-8038-050a411b5d28`, requested 2026-11-23T06:18:17Z, scope "Muse4 Work Request"). Surendra was asked to decide 12:12 IST. Not guessing: the question stays open until the log is read. The OBS-019 probable-cause statement above therefore stays "probable, NOT proven" — the fix is correct on the live-measured premise (503s pre-existing, gate fails on any non-2xx) regardless of the log.
2. **Post-merge CD proof run** — after Muse merges, the next push-triggered CD run is the proof: S2 job must succeed while Futuris :8004 / IntelX :8005 remain 503. To be watched and filed by the hourly self-check / work-request loop.
3. **S1 gate note (not changed):** Server 1's gate has the same unconditional shape; its agents are currently healthy, so it is out of scope. If a pre-existing S1 503 ever appears, the same baseline+filter treatment applies there.
4. **Work-request schedule:** NOT cancelled this run. Body step 2 says cancel while mid-task, but the settled rule (MEMORY.md) is DO NOT cancel while the OBS-013 live leg awaits fresh clearance — the loop is the watcher for that clearance, and the main agent re-armed it at 13:14 IST after the OBS-019 claim. The OBS-013 live leg still awaits fresh clearance (not granted). Main agent to decide if this changes.

— Muse 4
