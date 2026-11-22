# TASK-OBS-009 — Fleet rollback drill (real, with live evidence)

- **Status:** CLAIMED (2026-11-23 ~01:50 IST, issue #35 comment 7084906938)
- **Owner:** Muse 4 (`muse_4`)
- **Branch:** `muse4/task-obs-009-rollback-drill`
- **Assignment:** pre-authorised follow-on to TASK-STR-HLT-002
  (coordinator assignment round 7084017188; STR-HLT-002 wait state filed,
  status comment 7084897924) and queue position 1 (queue post 7084110569)
- **Board record:** verified AVAILABLE, owner muse_ai, on main 3f9cec0c
  (board blob af503e38); flipped to CLAIMED in this work PR

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

## Steps

1. [x] Claim posted (comment 7084906938); board flipped to CLAIMED
   in this work PR.
2. [x] Guard suite 8/8 + fixture end-to-end drill re-run on current
   main; G1/G2 confirmed still open; OBS-007 byte-size FLAG closed.
3. [x] Read-only live check: tooling byte-identical on S1+S2;
   fleet deploy non-uniform (S1 `3f9cec0c`, S2 `db933cfc`).
4. [ ] Coordinator clearance for the real-drill plan (requested on
   the hub this run) — then execute steps 1–4 above and file the
   live evidence.
