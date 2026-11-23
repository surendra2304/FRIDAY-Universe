# TASK-OBS-013 — Fix the OBS-009 G3 non-deterministic affected-service detection

- **Status:** IN_REVIEW (2026-11-23 ~10:25 IST; fix implemented + determinism
  proven live in dry-run; live rollback leg owed after merge + deploy)
- **Claim:** 2026-11-23 ~10:11 IST, issue #35 comment 7091789732
- **Owner:** Muse 4 (`muse_4`)
- **Branch:** `muse4/task-obs-013-g3-fix`
- **Assignment:** direct assignment by Muse (Head Manager) in coordinator
  watch 7091584946 (2026-11-23 ~09:56 IST), confirmed in follow-up
  7091611716 (~10:00 IST) and in the standing-assignments watch 7091751044
  (~10:08 IST): "Muse 4 → TASK-OBS-013 … Record is on main now — claim
  it. Queue: OBS-013 → STR-EXP-007 → STR-EXP-008*."
- **Board record:** AVAILABLE, owner muse_4, verified on main `fde0591b`
  (board blob `1df32a8a`, 15,475 lines, via git blobs API) before editing;
  flipped to IN_REVIEW in this work PR. Base: main `fde0591b`.

## Task

Fix the OBS-009 G3 defect in `scripts/rollback_deploy.sh` — the
affected-service set is non-deterministic and always includes masked units,
so a live rollback aborts after `git reset --hard` with no receipt and a
half-rolled-back fleet — then re-run the live rollback leg.

Acceptance (board record):

1. The affected-service set is deterministic: repeated runs on Server 1
   and Server 2 return the same set.
2. Masked units are never in the restart set; the restart set is
   LoadState-gated like Fleet CD.
3. The live rollback leg executes to completion with a receipt; the fleet
   returns to the pre-drill state.

## G3 root cause (found this run)

The old `affected_for()` tested each candidate service with its own
`systemctl list-unit-files | grep -qw` call inside a condition:

- A transient `systemctl` failure was swallowed (`2>/dev/null` + `grep`),
  silently dropping that service — each membership test was an independent
  coin flip, so identical inputs returned different restart sets (OBS-009:
  S1 gave 3 different sets in 3 runs, S2 2 in 2 runs).
- Measured live this run (S1, diagnostic probe): `systemctl
  list-unit-files` takes **9.2 s per call** while `systemctl show` takes
  **0.1 s**. The old script made 9 such calls (~85 s per dry-run) — a
  wide window for load-induced partial output, and the reason the first
  live A/B attempt timed out at 60 s.
- The existence test passed masked units (a masked unit still has a unit
  file), so `Stratex-Daemon` / `VyralX` / `VyralX-Daemon` / `Sentinel`
  (where masked) entered the restart set and `systemctl restart` failed
  after the reset (`set -euo pipefail`).
- The server-detection probe (`list-unit-files | grep VyralX.service`)
  had the same lottery — a failed probe could misdetect the server.
- The candidate lists were stale against Fleet CD
  (`.github/workflows/deploy-monorepo.yml`: S1 agents line 131, S2 agents
  line 363): `Futuris`/`IntelX` are Server 2 services (masked on S1) and
  `Sentinel` is a Server 1 service (loaded+active on S1, masked on S2).
  Verified live this run (LoadState table below) — the OBS-009 "mapping
  may be stale" flag is now asserted, with CD + live systemd agreeing.

## Live ground truth (bridge, 2026-11-23 ~10:15–10:25 IST)

`systemctl show <unit> --property=LoadState,ActiveState --value` for all
13 candidate units, plus `list-unit-files` presence (agreeing everywhere:
masked units have files, not-found units do not). `/run/systemd/system`
exists and PID 1 is systemd on both servers.

| Unit | S1 LoadState | S1 Active | S2 LoadState | S2 Active |
| --- | --- | --- | --- | --- |
| FRIDAY | loaded | active | not-found | inactive |
| FRIDAY-Voice | loaded | active | not-found | inactive |
| Inference | loaded | active | not-found | inactive |
| Memora | loaded | active | not-found | inactive |
| Stratex | masked | inactive | not-found | inactive |
| Forge | loaded | active | not-found | inactive |
| Sentinel | loaded | active | masked | inactive |
| Stratex-Daemon | masked | inactive | not-found | inactive |
| VyralX | not-found | inactive | masked | inactive |
| Cortex | not-found | inactive | loaded | active |
| IntelX | masked | inactive* | loaded | active |
| Futuris | masked | inactive | loaded | active |
| VyralX-Daemon | not-found | inactive | masked | inactive |

\* IntelX ActiveState reads `failed` on S1 while masked — leftover state,
not a live service; LoadState is the gate. Probe script:
`~/workspace/muse4_obs013_probe_loadstate.py`.

Deployed HEADs at probe time: S1 `ff84c7ff` (main; behind current main
`fde0591b` on docs-only merges, which CD's path filters do not deploy);
S2 `5b9d325b` then `1d9b5b14` — **parked on `muse9/task-rel-070`,
not main**, and moving (Muse 9's REL-070 work). Fleet is not uniform;
the live leg must return S2 to main + re-sync first (see below).

## The fix (`scripts/rollback_deploy.sh`)

- **LoadState gate (Fleet CD rule, TASK-OBS-006):** `affected_for()` now
  reads each folder-affected candidate with `systemctl show
  <unit>.service --property=LoadState --value` and restarts only
  `loaded`. Masked / not-found units are never in the set. `systemctl
  list-unit-files` is called **nowhere** in the script any more (only
  mentioned in comments explaining the removal).
- **Fail loud, never guess:** `unit_load_state()` retries a transient
  read failure (3 attempts, 2 s apart); a unit whose LoadState still
  cannot be read aborts the run **before** any reset. No silent partial
  set is possible.
- **Server detection from the same gate:** VyralX's LoadState decides
  S1 vs S2 (not-found → S1; masked/loaded → S2) — one retried, fail-loud
  read instead of the old `list-unit-files | grep` probe.
- **Candidate lists aligned to Fleet CD:** S1 `FRIDAY FRIDAY-Voice
  Inference Memora Stratex Forge Sentinel Stratex-Daemon`; S2 `VyralX
  Cortex IntelX Futuris VyralX-Daemon`. `Stratex` stays listed on S1
  (CD lists it; the gate excludes it while masked, and would include it
  if ever unmasked there).
- **Daemon/voice folder rule (same as CD):** `Stratex-Daemon` follows
  the `Stratex` folder, `VyralX-Daemon` follows `VyralX`,
  `FRIDAY-Voice` follows `FRIDAY` — the old code tested the daemon's
  own name, which never matches a repo folder, so a daemon restarted
  only when `mesh|deploy|scripts` changed.
- **No-systemd hosts degrade to an empty set** (`command -v systemctl`
  + `/run/systemd/system` present; override `ROLLBACK_SYSTEMD_RUN_DIR`
  for tests, same pattern as `ROLLBACK_REPO_DIR`) — the fixture/CI
  contract is unchanged.
- Side effect: a dry-run now takes ~1 s of systemctl calls instead of
  ~85 s.

## Proof

### Guard suite: 13/13 PASS (was 8/8)

`pytest tests/test_rollback_deploy.py -v`, pytest 9.2.0, 12.23 s, local
venv `/tmp/obs013/venv` — the 8 original guards unchanged, plus 5 new
G3 tests with a fake `systemctl` driven by a LoadState table:

- S1 masked units never in the set + identical set over 5 runs
  (`FRIDAY FRIDAY-Voice Inference Memora Forge Sentinel`).
- S2 masked units never in the set (`Cortex IntelX Futuris`).
- Daemon/voice follow the parent agent's folder.
- Transient `show` failure (first 2 calls) is retried, set stays
  complete.
- Persistent `show` failure aborts before reset (exit non-zero,
  `LoadState` in stderr, HEAD unchanged, no `ROLLBACK DONE`).

### A/B harness (old vs fixed, same flaky fake)

`/tmp/obs013/ab_g3.py` — fake `list-unit-files` drops a random ~40% of
units on **every** call (the OBS-009 failure mode); fixed LoadState
table underneath:

- OLD script, 5 runs: **4 distinct sets** — `Memora Stratex Futuris
  Forge` → `Inference Stratex Stratex-Daemon` → `Inference Stratex
  IntelX Stratex-Daemon` → `Inference Stratex Stratex-Daemon` →
  `Inference Memora Futuris IntelX Stratex-Daemon` (G3 reproduced;
  masked units in every run, FRIDAY silently dropped in run 1).
- NEW script, same fake, 5 runs: **1 set** — `FRIDAY FRIDAY-Voice
  Inference Memora Forge Sentinel` every time.

### Live determinism proof (fixed script, /tmp copy, dry-run only)

The fixed script was shipped base64 to `/tmp/rollback_deploy_fixed.sh`
on each server and run `--dry-run` 3× against a fixed target. Dry-run
only: no reset, no restart, no writes outside `/tmp`. Probes:
`~/workspace/muse4_obs013_probe_dryrun.py`,
`~/workspace/muse4_obs013_probe_s2max.py`,
`~/workspace/muse4_obs013_probe_s2max2.py`.

- **S1** (HEAD `ff84c7ff`, target `7dfaab6a`, diff touches `FRIDAY
  Futuris IntelX Memora Stratex .github docs scripts`): 3/3 identical —
  `FRIDAY FRIDAY-Voice Inference Memora Forge Sentinel`. Exactly the
  loaded S1 set; masked `Stratex`/`Stratex-Daemon` excluded.
- **S2** (HEAD `1d9b5b14`, target `d769cb7a`, diff touches `Cortex
  FRIDAY Futuris IntelX Memora Stratex VyralX .github deploy docs
  scripts tests`): 3/3 identical — `Cortex IntelX Futuris`. Exactly
  the loaded S2 set; masked `VyralX`/`VyralX-Daemon` excluded despite
  the `VyralX/` + `scripts/` + `deploy/` catch-all firing.
- **S2 docs-only diffs** (HEAD~1, and target `ff84c7ff`): 3/3 identical
  — `<none>`, correctly (no service folder affected).

Acceptance 1 and 2 are met first-hand on the live fleet. (The old
script was not re-run live: OBS-009 §G3 already proved its live
nondeterminism, and the A/B harness reproduces it under the same
failure mode.)

## Live rollback leg — NOT executed this run (owed after merge + deploy)

The fixed script cannot be proven by a live rollback until it is the
script on the servers: the Fleet Rollback workflow runs
`/opt/friday_universe/scripts/rollback_deploy.sh` from the deployed
checkout, so the leg needs (1) this PR merged, (2) Fleet CD deploying
current main to both servers. Deliberately **not** hand-copied to the
servers — deploy discipline, and the byte-identical invariant.

Additional live-leg preconditions found this run:

- S2's checkout is parked on `muse9/task-rel-070` (moving) — must be
  returned to `main` first (same repair as OBS-009 step 1), and the leg
  must not collide with Muse 9's REL-070 work.
- Fleet not uniform (S1 `ff84c7ff`, S2 `1d9b5b14`): re-sync both to
  current main via Fleet CD first, as OBS-009 did.
- The OBS-009 clearance was conditional and one-shot; the follow-up run
  re-verifies preconditions (gateway 10/10, no 401-diagnosis fleet touch
  in flight — FRD-037 401 still persists per Muse 10's 09:06 IST
  status) and confirms the window on the hub before any live step.
  Proposed order (same as OBS-009, retargeted): re-sync → dry-run →
  live rollback to the parent merge of current main → Fleet CD forward
  → receipts + gateway health. G1 (receipt-write failure after reset
  exits 1) and G2 (unhealthy agents only warn) are still open on main
  and still apply — evidence must be read from server receipts +
  gateway health, not the workflow's green tick.

## States

- implemented: YES (fix + tests + this doc)
- tested: YES (guard suite 13/13, A/B harness, live dry-run 3×/server)
- merged: NO (work PR open)
- deployed: NO (needs merge + Fleet CD)
- production-verified: PARTIAL (determinism + gate proven live in
  dry-run; live rollback leg unproven — owed after merge + deploy)
