# TASK-OBS-013 — Fix the OBS-009 G3 non-deterministic affected-service detection

- **Status:** IN_REVIEW (2026-11-23 ~11:07 IST; fix MERGED as PR #1455, merge
  705ab92d; live rollback leg ABORTED on new gap G4 — see below)
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

## Live rollback leg — ABORTED on new gap G4 (2026-11-23 ~10:54–11:07 IST)

Clearance: coordinator watch 7092357321 (~10:37–10:55 IST): "Muse 4 —
CLEARANCE GRANTED (conditional): return S2 to main + Fleet CD re-sync,
re-verify preconditions live on the then-current main (S1/S2 both on it,
trees clean, gateway /friday/health 200, no in-flight fleet touch), then
execute the OBS-009 live rollback leg. Abort + report on ANY precondition
failure; no live step until preconditions re-verify. (Note: main has
advanced past 705ab92d since your 10:44 check — re-fetch at leg time.)"

Preconditions re-verified live this run (bridge, read-only probes +
gateway curl from this VM; main `136533e5` throughout):

- S1: branch `main`, HEAD `705ab92d` (the OBS-013 merge), tracked tree
  clean, 11 untracked (runtime state); deployed rollback script
  byte-identical to main `136533e5` (sha256 `23e1946c…`, 8,574 B,
  LoadState gate present); LoadState table identical to §Live ground
  truth (FRIDAY/FRIDAY-Voice/Inference/Memora/Forge/Sentinel
  loaded+active; Stratex/Stratex-Daemon masked; VyralX/Cortex/VyralX-Daemon
  not-found; IntelX masked/failed; Futuris masked). No
  rollback-receipts dir yet.
- S2: branch `muse9/task-rel-070`, HEAD `1d9b5b14`, tracked clean, 12
  untracked; `origin/main` `136533e5`; local main `ff84c7ff` (ancestor
  of `origin/main`); deployed script still the OLD pre-fix version
  (sha256 `062838a8…`, 5,274 B — parked branch predates the G3 merge);
  LoadState table identical to §Live ground truth (Cortex/IntelX/Futuris
  loaded+active; VyralX/VyralX-Daemon masked; Sentinel masked). No
  receipts dir yet.
- Gateway `/health`, two samples (~11:03 and ~11:07 IST): 8/10 200 both
  times (friday, inference, memora, forge, sentinel, cortex, vyralx +
  stratex on re-probe). Futuris 503 and IntelX connection-closed in
  BOTH samples — persistent, pre-existing degradation (ORCH-014
  evidence, ~09:44 IST: "overall still degraded on pre-existing IntelX
  + Futuris DEGRADED"; Muse 7 INT-020 0/3 live runs), NOT drill-caused.
  Stratex closed-connection in sample 1 only (transient; 200 in sample
  2). `/friday/health` 200 in both samples — the clearance's literal
  gateway condition met.
- Hub re-read before any live step (latest: coordinator watch 7092549861,
  ~11:05 IST): no fleet-touching work in flight (Muse 9 INT-023 claim —
  compile task; Muse 12 FUT-019 claim — forecast proof; Muse 1 VAL-013
  merged; Muse 12 REL-070 reconciliation, read-only). Main still
  `136533e5`.
- Rollback target (parent merge of current main): `9597c7c9` (merge PR
  #1449). Verified ancestor of `136533e5` (compare: ahead 2, behind 0).
  NOTE: the `136533e5`→`9597c7c9` diff is board-only
  (`docs/collaboration/WORK_BOARD.yaml`, PR #1457) — the affected
  restart set would have been empty; the leg as filed proves the
  end-to-end live path + receipt, while the LoadState-gate live proof
  remains the 3×/server dry-run in §Proof.

Step 1 — S2 return to main: DONE (~11:06 IST). `git checkout main` on
S2, rc=0, clean switch; branch `main`, HEAD `ff84c7ff`, tracked clean,
12 untracked. REL-070 is merged (PR #1452, merge `27b7d4e2a`); Muse 9
has moved to INT-023; nothing lost. The OBS-005 branch-guard landmine
is removed: the next server2-changing push CD will no longer fail its
S2 job.

G4 — NEW GAP: S1 cannot fetch, so Fleet CD cannot re-sync S1 (live leg
ABORTED here).

- `git fetch origin main` on S1 fails reproducibly, rc=128: "error:
  insufficient permission for adding an object to repository database
  .git/objects / fatal: failed to write object / fatal: unpack-objects
  failed" (pre-check probe + CD-equivalent `git fetch --no-tags origin
  136533e5…` test, same rc=128). `origin/main` stays stale at
  `fde0591b` while ls-remote shows `136533e5`.
- Root cause (read-only diagnosis):
  `/opt/friday_universe/.git/objects` on S1 contains root-owned entries
  — whole fan-out dirs (`f2`, `b7`, `cb`, `e3`, `f9`, `64`, `25`, `94`,
  `ce`, `5f`, `a4`, `2b`, `b9`, `ac`, `74`, …) non-writable by ubuntu,
  many root-owned loose objects, and root-owned pack
  `pack-1716efea08f3e00d4bff7af001ca8a19484b9c95.{pack,idx}` dated Nov 23
  04:28 IST (the OBS-009 drill window — a sudo git operation then).
  Bridge user is ubuntu (uid 1001), the same user Fleet CD SSHes as;
  `.git` and `.git/objects` top levels are ubuntu-owned, no lock files,
  disk 28% used, inodes 4%, `git fsck --no-dangling` rc=0 with no errors
  in sampled output.
- The three target commits (`136533e5`, `0d26176b`, `9597c7c9`) ARE
  present on S1, but the fetch still fails: the missing trees/blobs for
  the intervening merges hash into root-owned fan-out dirs.
- Consequence: Fleet CD's `git fetch --no-tags origin "$DEPLOY_REV"`
  fails on S1 under `set -euo pipefail` before any merge or restart, so
  the re-sync cannot bring S1 to current main (`136533e5`) and the
  "S1/S2 both on current main" precondition cannot be met. Fleet CD was
  NOT dispatched (it would half-apply: S2 would move + restart while S1
  stays behind — no new evidence, only fleet churn; the fetch test
  already proves the S1 job outcome). No rollback workflow was
  dispatched; no live rollback, restart, or deploy was executed by this
  run beyond the S2 checkout.
- Repair owed (fleet mutation, NOT in this clearance — needs coordinator
  direction): restore ubuntu ownership of S1's `.git/objects` (e.g.
  `sudo chown -R ubuntu:ubuntu /opt/friday_universe/.git/objects`, or a
  fresh clone) and re-verify `git fetch origin main` rc=0, then re-run
  the leg. Suggested follow-up: audit how root-owned objects got in
  (sudo git during the OBS-009 drill window?) and stop it recurring.
- Bridge transport note: the MCP bridge dropped mid-response twice this
  run (`http.client.IncompleteRead`, 699 and 4,507 bytes read); both
  retries succeeded. Not blocking; noted.

Fleet end state (verified ~11:07 IST): S1 `main` @ `705ab92d` (tracked
clean), S2 `main` @ `ff84c7ff` (tracked clean) — both on main, not
uniform; gateway 8/10 (Futuris/IntelX pre-existing 503/closed). No
rollback executed; no receipt written (receipts dir still absent on
both servers).

## Live-leg attempt 2 — G4 repaired, CD re-sync FAILED on S2; leg ABORTED (2026-11-23 ~12:25 IST, Muse 4)

- **Clearance:** coordinator watch 7092909496 (run 11:17–11:55 IST) —
  "Muse 4 — G4 CLEARANCE GRANTED: the S1 `.git/objects` ownership
  repair is authorised as a fleet mutation, scoped exactly: restore
  ubuntu ownership under S1 `/opt/friday_universe/.git/objects` only
  (the root-owned fan-out dirs + pack from the OBS-009 drill window),
  re-verify `git fetch origin main` succeeds on S1, then re-run the
  live rollback leg under the original conditional clearance
  (preconditions re-verified live on the then-current main, abort +
  report on ANY failure). S2 is already on main."
- **G4 repair — DONE:** `sudo chown -R ubuntu:ubuntu
  /opt/friday_universe/.git/objects` on S1, rc=0 (passwordless sudo;
  bridge user ubuntu). Non-ubuntu entries: 94 → 0 (user and group).
  `git fetch origin main` rc=0 afterwards (was rc=128, "insufficient
  permission for adding an object to repository database
  .git/objects"); `git fsck` rc=0. S2's fetch already worked (rc=0,
  tested this run) — its 13 root-owned entries (same pack-1716efea)
  are a latent risk only, left untouched (out of the granted scope).
- **Preconditions re-verified (main `136533e5`):** S1 `main` @
  `705ab92d`, tracked clean; S2 `main` @ `ff84c7ff`, tracked clean;
  gateway `/health` 8/10 in two samples (`/friday/health` 200;
  Futuris + IntelX 503, pre-existing); hub re-read — no
  fleet-touching work in flight. Rollback target `9597c7c9` (first
  parent of `136533e5`; diff board-only).
- **CD re-sync — FAILED on S2:** Fleet CD run 45122467146
  (workflow_dispatch, ref `main`, head `136533e5`): "Analyze Changed
  Agents" success; "Deploy Core Fleet (Server 1)" success; "Deploy
  Specialist Fleet (Server 2)" FAILURE at step "Update Changed Agents
  on Server 2". **Probable cause — S2 post-deploy health gate on
  pre-existing degradation (NOT proven from the job log):** the gate
  is the S2 script's last step (fetch, merge, restarts precede it)
  and probes `127.0.0.1:8004` (Futuris) + `:8005` (IntelX) `/health`,
  both 503 before the deploy and still 503 after the restarts (live:
  Cortex `:8009` 200; all three loaded+active, NRestarts 0). The
  same failure recurred on the later push CD run 45124516836 (head
  `ca2c586f`, also failure) while push CDs that skip the S2 job
  succeed — consistent with the gate, not the checkout. The job log
  itself could NOT be read: the logs endpoint redirects to an Azure
  blob URL, which raised approval 9fcd7226 (requested 11:48 IST;
  still pending at last check) — not retried.
- **Leg ABORTED per the clearance:** no rollback dry-run, no live
  rollback, no receipts, no CD forward for the leg. No live
  rollback/restart/deploy by this run beyond the CD runs themselves.
- **Fleet end state (verified live):** SAFE but not uniform; main has
  moved on (`23324fdd`, later `f4386589` at filing time). S1 `main` @
  `d7d534cd`, tracked clean; all S1 agents loaded+active, NRestarts
  0; local `/health` 200 (FRIDAY/Inference/Memora/Forge/Sentinel). S2
  `main` @ `ca2c586f`, tracked clean; Cortex/IntelX/Futuris
  loaded+active, NRestarts 0; local Cortex 200, Futuris/IntelX 503
  (pre-existing). Gateway `/health` 8/10, same as the pre-leg
  baseline — no new degradation. Fixed rollback script (`sha256
  23e1946c…`) deployed on both servers.
- **Direction requested (hub status 7093788546):** (1) disposition
  the S2 health-gate failure (gate vs known-degraded Futuris/IntelX);
  (2) whether the leg re-runs on the new main once dispositioned
  (fresh preconditions + new rollback target); (3) whether S2's
  `.git/objects` latent risk gets the same repair.

## States

- implemented: YES (fix + tests + this doc; two live-leg attempts filed)
- tested: YES (guard suite 13/13, A/B harness, live dry-run 3×/server;
  live leg NOT executed — aborted twice: G4, then S2 CD health gate)
- merged: YES (G3 fix PR #1455, merge `705ab92d`; live-leg evidence PR
  #1459 merged 11:42 IST; board record MERGED on main)
- deployed: PARTIAL (fixed script on both servers; fleet not uniform)
- production-verified: PARTIAL (determinism + gate proven live in
  dry-run; live rollback leg still unproven — re-run owed after the S2
  health-gate disposition + fresh preconditions on the new main)
