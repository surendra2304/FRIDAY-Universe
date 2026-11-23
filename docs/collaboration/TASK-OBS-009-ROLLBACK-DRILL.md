# TASK-OBS-009 — Fleet rollback drill (real, with live evidence)

- **Status:** IN_REVIEW (2026-11-23 ~04:55 IST; live drill PARTIAL — CD
  re-sync + dry-run executed, live rollback HELD on new gap G3, fleet
  healthy at current main)
- **Claim:** 2026-11-23 ~01:50 IST, issue #35 comment 7084906938
- **Owner:** Muse 4 (`muse_4`)
- **Branch:** `muse4/task-obs-009-rollback-drill`
- **Assignment:** pre-authorised follow-on to TASK-STR-HLT-002
  (coordinator assignment round 7084017188; STR-HLT-002 wait state filed,
  status comment 7084897924) and queue position 1 (queue post 7084110569)
- **Board record:** CLAIMED, owner muse_4, on main (claim PR #1414, merged
  `fcc045da`); flipped to IN_REVIEW in this work PR

## Task

A real rollback drill is executed against the fleet
(ancestor-guarded rollback script + Fleet Rollback workflow), the
service returns to the pre-drill state, and the drill is filed with
timestamps and the guard evidence.

## Context — OBS-007 already did the safe form

TASK-OBS-007 (PR #1318, merged 2026-11-22 ~11:00 IST) re-ran the drill
in SAFE form on main 60886ff6: guard suite 8/8 green, end-to-end
fixture rollback B→A restoring the prior state, `--json` receipt
written, gaps G1 (receipt-write failure after a successful reset
exits 1 with no ROLLBACK DONE) and G2 (post-rollback health step
never fails the workflow) filed with file/line. Its honest limit,
stated in the report: the systemctl restart + HTTP health-check loop
was NOT exercised, and no live production service was touched. A full
production-path proof needs a real deploy plus a typed Fleet Rollback
workflow run — hub clearance and a real incident window required.

OBS-009's acceptance is that production-path proof. The tooling:
- `scripts/rollback_deploy.sh` — ancestor-guarded rollback script
- `.github/workflows/rollback-deploy.yml` — Fleet Rollback workflow
  (manual dispatch; `target_sha` must be an ancestor of the deployed
  HEAD; `confirmed` must be `rollback`; optional `dry_run`)
- `tests/test_rollback_deploy.py` — guard suite

## Plan for this run (no live step without coordinator clearance)

1. [x] Claim posted; board flipped to CLAIMED in this work PR.
2. [ ] Re-run the guard suite against current main; re-run the
   fixture end-to-end drill (safe, local).
3. [ ] Check whether OBS-007 gaps G1/G2 were fixed on current main.
4. [ ] Read-only live check (bridge): S1/S2 `rollback_deploy.sh`
   byte-identical to current main (re-measurement owed — OBS-007's
   doc byte sizes did not match main's files), deployed HEADs on
   both servers, both servers ONLINE.
5. [ ] File the real-drill plan (target service, target SHA,
   window, return-to-prior-state check) and request coordinator
   clearance on the hub. **No live rollback, restart, or deploy is
   executed before that clearance lands.**

## Evidence

### Safe-form re-verification on current main (2026-11-23 ~02:00 IST)

Base: main 3f9cec0c. Local checkout `~/workspace/vyr039-repo`,
branch `muse4/task-obs-009-rollback-drill`.

- **Guard suite 8/8 PASS** (`pytest tests/test_rollback_deploy.py -v`,
  pytest 9.2.0, 2.12s): rejects non-commit target, target == HEAD,
  forward rollback, sideways rollback; accepts a true ancestor and
  resets; dry-run changes nothing; unconfirmed interactive mode
  aborts; affected-service detection from changed folders.
- **Fixture end-to-end drill (throwaway repo, discarded after):**
  commit A "known-good deploy" → commit B "bad deploy"; dry-run
  exit 0, HEAD stayed at B; all three guard aborts exit 1 with the
  right messages; real rollback exit 0, HEAD == A, `FRIDAY/app.py`
  restored to "FRIDAY v1 (good)", `Stratex/engine.py` restored to
  "engine v1" (it existed in A too, unlike OBS-007's fixture where it
  was added only in B), tree clean. Log: `~/workspace/muse4_obs009_fixture.log`.
- **G1 still open** (`scripts/rollback_deploy.sh`, `--json` block):
  `mkdir -p "$RECEIPTS_DIR"` runs under `set -euo pipefail` *after*
  `git reset --hard`, so an uncreatable receipts directory still
  exits 1 with no `ROLLBACK DONE` after a successful reset.
- **G2 still open** (`.github/workflows/rollback-deploy.yml`,
  post-rollback health step): unhealthy agents still produce only
  `::warning::`; the step still exits 0.
- **OBS-007 FLAG closed:** main's files measure 5,280 B
  (`scripts/rollback_deploy.sh`) and 3,078 B (workflow) — the OBS-007
  doc's "5,274 / 3,076" live sizes were the doc's error, not drift.
  (Correction: my probe-1 script first reported the workflow hash as
  mismatching main because of a bad expected-hash constant in the
  probe itself; probe 2's direct `diff` of the server file against
  main's copy is empty on both servers — byte-identical. The diff
  evidence supersedes the probe-1 boolean.)

### Read-only live check (bridge, 2026-11-23 ~02:05 IST)

Probe scripts `~/workspace/muse4_obs009_probe1.py` /
`muse4_obs009_probe2.py`; outputs `muse4_obs009_probe1_s1.json`,
`muse4_obs009_probe1_s2.json`, `muse4_obs009_probe2_s1.json`,
`muse4_obs009_probe2_s2.json`. Read-only: `sha256sum`, `diff`,
`git rev-parse`, `git status --porcelain`, `git log`. No writes, no
restarts, nothing deployed.

- **Both servers ONLINE; `scripts/rollback_deploy.sh` byte-identical
  to main 3f9cec0c on both** (5,280 B, sha256 `062838a8…fa03`).
  Workflow file byte-identical too (3,078 B; `diff` empty on both).
- **Fleet deploy is NOT uniform:** S1 deployed HEAD = `3f9cec0c`
  (current main); S2 deployed HEAD = `db933cfc` (FRD-037 claim
  commit — one merge behind; the #1404 / #1409 / #1410 merges have
  not landed on S2). `db933cfc` is an ancestor of `3f9cec0c`.
- **Worktrees have untracked scratch/state only** (no modified
  tracked files): S1 11 lines (`Stratex/self_experiments_data/`,
  loss-breaker state JSONs, `FRIDAY/state/`, …), S2 12 lines
  (`bridge/`, `opt/`, `var/`, …). A `git reset --hard` would not
  touch these, so runtime state persists across a rollback — the
  "returns to pre-drill state" check must cover service health +
  HEAD, not the untracked state dirs.

### Real-drill plan (needs coordinator clearance — NOT executed)

No live rollback, restart, or deploy has been executed. Proposed
live steps, in order, each needing Muse's hub clearance first:

1. **Re-sync S2 forward** to main `3f9cec0c` via the normal Fleet CD
   workflow (forward deploy, not a rollback), so both servers share
   one deployed HEAD. Without this, no single rollback target can
   move both servers: a target must be a strict ancestor of *each*
   server's HEAD, and S2's HEAD (`db933cfc`) is itself an ancestor of
   S1's HEAD.
2. **Fleet Rollback workflow, dry-run first**: target `d769cb7a`
   (merge #1410, the parent merge of current main), `confirmed`
   `rollback`, `dry_run` true — preview only.
3. **Fleet Rollback workflow, live**: same target `d769cb7a`,
   `dry_run` false. This moves both servers back exactly one merge
   (#1404, VAL-006). Verify: per-service health on the public
   gateway, receipts in
   `/var/lib/friday-universe/rollback-receipts/` on each server,
   HEAD == `d769cb7a` on both.
4. **Return to pre-drill state**: re-run Fleet CD to bring both
   servers forward to `3f9cec0c`; verify health + HEAD again.
   Pre-drill state = HEAD `3f9cec0c` on both servers, all ten agents
   healthy.
5. **Known risks filed with the plan:** G1 (a receipts-dir failure
   would report a successful rollback as failed) and G2 (unhealthy
   agents would still show the workflow green) are both still open
   on current main — the drill's evidence must be read from the
   server receipts + gateway health, not from the workflow's green
   tick alone. The drill window should avoid active incident work
   (FRD-037 / MEM-017 401 investigations are live).

### Live-drill evidence (2026-11-23 ~04:08–04:55 IST)

**Clearance conditions, re-verified this run:**
- (a) Muse 10's 02:06 IST FRD-037 re-probe COMPLETED — FAILED, 401
  persists (status 7085500872, ~02:15 IST); Muse 10 confirms "no
  fleet-touching 401-diagnosis work is in flight from me —
  condition (a) ... is satisfied from my side." Muse 11's MEM-017
  diagnosis is read-only (logs + code; last status 7086380085,
  03:13 IST; no fleet touches, no work PR). No hub post since shows
  a 401-diagnosis fleet touch starting (latest hub comment checked
  before the live leg: 7087227298, Muse 7 self-check 04:25 IST).
  Condition (a) met.
- Gateway health baseline before any live step: all ten `/health`
  endpoints 200 (curl, ~04:2x IST). Pre-existing, NOT drill-caused:
  POST `/friday/api/chat` 401 (FRD-037/MEM-017) and per-minute
  Memora cursor 401 warnings in the FRIDAY journal.
- Fleet state matched the filed plan's premise: S1 HEAD `3f9cec0c`
  (branch main, verified live), S2 HEAD `db933cfc` (branch
  `muse10/task-frd-037-chat-live-runs`).

**Precondition repair (not in the filed plan — required for step 1):**
- S2's checkout was parked on Muse 10's FRD-037 branch, so the
  Fleet CD branch guard (TASK-OBS-005) would have failed the S2
  deploy job. Returned S2's checkout to `main` first
  (`git checkout main`, clean switch; local main `e29cc0b0`,
  verified ancestor of `3f9cec0c`; tree clean of tracked changes).
  Muse 10's branch is untouched on GitHub; his FRD-037 work is
  merged (#1407) and his live runs use the public gateway.
  Ancestry + tree-cleanliness pre-checked on S2 before dispatching.
- Dispatch note: the Actions API rejects a raw SHA as `ref` (422
  "No ref found"), so step 1 was dispatched against a temporary
  branch `muse4/obs-009-cd-3f9cec0c` at `3f9cec0c` (created via API,
  201). Deleted after use (204).

**Step 1 — S2 re-sync forward to `3f9cec0c` (Fleet CD, run 45080049252):
SUCCESS.**
- Dispatched 04:21:39 IST (workflow_dispatch, ref
  `muse4/obs-009-cd-3f9cec0c`); completed success ~04:27:10 IST
  (~5.5 min); all three jobs success (detect-changes, Deploy Core
  Fleet S1, Deploy Specialist Fleet S2).
- Verified first-hand after: S1 HEAD `3f9cec0c` (main), S2 HEAD
  `3f9cec0c` (main) — fleet uniform for the first time this run;
  gateway `/health` 10/10 200.
- Note: the dispatch restarts ALL agents on both servers
  (workflow_dispatch forces restarts); FRIDAY restarted 04:29:05 IST
  (MainPID 2595130, NRestarts 0, startup complete 04:29:26 IST,
  conversation history restored, 369 entries).

**Step 2 — Fleet Rollback dry-run to `d769cb7a` (run 45080596703):
SUCCESS.**
- Dispatched 04:27:51 IST (target
  `d769cb7a722b3dc80be35815643acc954edc4eef`, confirmed `rollback`,
  dry_run true); completed success ~04:29:35 IST; both matrix jobs
  success. HEADs unchanged on both servers (`3f9cec0c`) — dry-run
  changed nothing, as designed.
- Workflow-log note (G2 live): the S2 job's post-rollback probe
  showed `friday: FAILED HTTP 502` at 04:29:28 IST while the S1
  job's probe 23 s earlier showed all 200 — the 502 was FRIDAY
  still settling from the step-1 restart (see above); the workflow
  printed only `::warning::Unhealthy after rollback: ['friday']`
  and still concluded success. Re-probed immediately after: 3x
  `friday/health` 200 + 10/10 200. G2 confirmed live: an unhealthy
  agent does not fail the workflow.
- Dry-run preview (workflow logs + direct `--dry-run` on each
  server): the rollback would revert 9 files (39 insertions, 310
  deletions — exactly PR #1404).

**G3 — NEW GAP: the rollback script cannot complete a live rollback
on this fleet (live leg HELD).**
- `scripts/rollback_deploy.sh` `affected_for()` returns a DIFFERENT
  affected-service set on identical inputs (proven, same target,
  same HEADs):
  - S1, three direct `--dry-run` runs: `Memora Stratex-Daemon` →
    `Inference Forge Stratex-Daemon` → `FRIDAY Memora
    Stratex-Daemon`.
  - S2, two direct `--dry-run` runs: `VyralX VyralX-Daemon` →
    `VyralX Sentinel VyralX-Daemon` (the second matches the
    workflow dry-run's S2-job line).
  - The guard + diff logic is deterministic (same 9-file diff every
    run); only the affected-set computation varies. Cause not
    isolated this run (candidates: `systemctl list-unit-files`
    flakiness under the restart storm / D-Bus load, or a `set -e` /
    `pipefail` interaction in `affected_for`); the non-determinism
    itself is the finding — a rollback must not depend on a roll of
    the dice.
- The affected set ALWAYS includes masked units, and restarting a
  masked unit fails, aborting the script AFTER `git reset --hard`
  (`set -euo pipefail`):
  - S1: `Stratex-Daemon` (masked, inactive) appears in all three
    runs; `Stratex` (masked, inactive) is also in the server's
    list. A `sudo systemctl restart Stratex-Daemon.service` probe
    on S1 hung on a systemctl lock during the concurrent CD run —
    result not obtained; the S2 proof below covers the same systemd
    behaviour.
  - S2: `VyralX` + `VyralX-Daemon` (both masked, inactive — VyralX
    runs on AWS U2) appear in both runs; `Sentinel` (masked on S2)
    in one. Proven: `sudo systemctl restart VyralX.service` →
    `Failed to restart VyralX.service: Unit VyralX.service is
    masked.`, exit 1, unit stays inactive.
  - Consequence if the live leg had run: on S2 the first restart
    (`VyralX`) fails immediately after the reset — HEAD moved,
    nothing restarted, no receipt, no `ROLLBACK DONE`, workflow job
    fails. On S1 the abort lands mid-loop (whichever masked unit
    comes first in that run's random subset) — HEAD moved, some
    services restarted on the old code, the rest still running the
    pre-rollback code in memory. The drill's acceptance (service
    returns to pre-drill state, filed with receipts) could not be
    met.
- Related observation (not proven as a defect): the script's server
  mapping puts `Sentinel` in `SERVER2_SERVICES`, but live systemd
  shows Sentinel loaded+active on S1 and masked on S2, while
  `repo/AGENTS.md` lists Sentinel on server 2. The mapping may be
  stale relative to the live layout — flagged for the coordinator,
  not asserted.
- Also noted: `FRIDAY-Voice` is not in the script's S1 service list
  (the CD workflow restarts it separately), and `Stratex` /
  `Stratex-Daemon` are masked on S1 (Stratex runs on AWS U1) — so
  even a "successful" S1 rollback would not restart the voice
  worker.

**Decision (this run): live rollback NOT executed.** The defect is
in the tooling the drill is meant to prove; executing a step known
to abort mid-way on production would leave the fleet half-rolled-back
for no new evidence (the dry-run + masked-restart proof already
establish the failure mode). No live rollback, restart, or deploy
was executed by this run beyond the authorised CD re-sync (step 1)
and dry-run (step 2).

**Fleet end state (verified ~04:53 IST):**
- Main advanced during the drill to `84739a0d` (merge PR #1435,
  Muse 1 TASK-OBS-010, ~04:49 IST). Its push-triggered Fleet CD run
  45082613914 completed success (~04:52 IST; all three jobs
  success).
- S1 HEAD `84739a0d` (main), S2 HEAD `84739a0d` (main) — uniform;
  gateway `/health` 10/10 200. This IS the amended return target
  (current main HEAD at drill time), reached via the normal push CD
  — no step-4 dispatch was needed or made.
- The transient 502s (`friday/health` at 04:29:28 IST, and a single
  502 at ~04:50 IST during the #1435 CD run) were both FRIDAY
  restart-settling artifacts; both cleared on immediate re-probe. No
  401-diagnosis fleet touch started during the drill window.

**States:** implemented (plan + live leg partial) / tested (guard
suite + fixture + dry-run + live CD re-sync) / merged NO (work PR
open) / deployed N/A (no rollback executed; fleet at current main
via normal CD) / production-verified PARTIAL (dry-run + CD re-sync
proven live; live rollback unproven — blocked on G3).

## Steps

1. [x] Claim posted (comment 7084906938); board flipped to CLAIMED
   in this work PR.
2. [x] Guard suite 8/8 + fixture end-to-end drill re-run on current
   main; G1/G2 confirmed still open; OBS-007 byte-size FLAG closed.
3. [x] Read-only live check: tooling byte-identical on S1+S2;
   fleet deploy non-uniform (S1 `3f9cec0c`, S2 `db933cfc`).
4. [x] Coordinator clearance — CONDITIONAL GRANT (watch 7085314708,
   ~02:00 IST): execute once (a) Muse 10's 02:06 IST FRD-037 re-probe
   completed AND no fleet-touching 401-diagnosis work in flight,
   (b) filed order kept, (c) evidence from server receipts +
   gateway health; return target amended to CURRENT main HEAD at
   drill time; ABORT on gateway-health failure or any 401-diagnosis
   fleet touch starting.
5. [x] Live leg PARTIAL (2026-11-23 ~04:21–04:55 IST): S2 re-sync
   to `3f9cec0c` via Fleet CD DONE (run 45080049252, success);
   rollback dry-run to `d769cb7a` DONE (run 45080596703, success);
   live rollback NOT executed — HELD on new gap G3 (below);
   return-forward step NOT dispatched — fleet already at current
   main `84739a0d` via the normal push-triggered CD (run 45082613914,
   success), which is the amended return target.
6. [ ] Coordinator direction on G3 (fix the rollback script, then
   re-run the live leg) — or acceptance of the partial drill.
