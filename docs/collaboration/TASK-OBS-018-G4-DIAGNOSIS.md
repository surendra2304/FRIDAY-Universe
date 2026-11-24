# TASK-OBS-018 — G4 diagnosis (S1 git-objects root ownership)

**Task:** TASK-OBS-018 — Fleet: repair the S1 git-objects root ownership (G4)
and re-run the OBS-013 live rollback leg.
**Date:** 2026-11-23, probed ~23:41–23:55 IST.
**Method:** read-only bridge probes (`get_system_info`, `run_shell` read-only
git/ownership checks) + GitHub API reads. No `git fetch`, no `chown`/`chmod`,
no restart, no deploy, no Fleet CD dispatch by this run. **Diagnosis only.**
**Branch:** `muse14/task-obs-018-s1-git-objects`, rebased onto main `8c0ef142`.

## Verdict up front

**The G4 root-ownership breakage is NOT present on S1 anymore.** As of
23:41 IST, S1 `/opt/friday_universe/.git/objects` has **zero** non-ubuntu
entries (it had 94 at the OBS-013 abort, chowned to 0 in the 12:25 IST
repair), S1 `main` is already on current main `8c0ef142`, and a fetch of
that head demonstrably succeeded at 23:41:11 IST via Fleet CD run
45235566621 (push, head `8c0ef142`, in progress at check time).

What remains is **verification, not repair**: a direct live
`git fetch origin main` (rc=0) + `git fsck` (rc=0) on S1, confirmation
that CD run 45235566621 completes success, and then the OBS-013 live
rollback leg re-run with fresh preconditions. No S1 repair is owed right
now; the exact repair procedure is filed in §6 for recurrence.

No owner hold is claimed here. The clearance requested in §7 is the
**coordinator's hub clearance for a fleet mutation**, per the OBS-018
board record — not a clearance from Surendra.

## 1. What G4 was (OBS-013 evidence)

Source: PR #1459 (merge `292823f0`, merged 11:42 IST 2026-11-23),
`docs/collaboration/TASK-OBS-013-G3-FIX.md` (live-leg + attempt-2 sections).

**Attempt 1 — live leg ABORTED on G4, ~10:54–11:07 IST (Muse 4):**

- S1 `git fetch origin main` failed reproducibly, rc=128:
  `error: insufficient permission for adding an object to repository
  database .git/objects / fatal: failed to write object /
  fatal: unpack-objects failed`. `origin/main` stayed stale at `fde0591b`
  while ls-remote showed `136533e5`.
- Root cause (read-only diagnosis then): `/opt/friday_universe/.git/objects`
  on S1 held root-owned entries — whole fan-out dirs (`f2`, `b7`, `cb`,
  `e3`, `f9`, `64`, `25`, `94`, `ce`, `5f`, `a4`, `2b`, `b9`, `ac`, `74`,
  …) non-writable by ubuntu, many root-owned loose objects, and
  root-owned pack
  `pack-1716efea08f3e00d4bff7af001ca8a19484b9c95.{pack,idx}` dated Nov 23
  04:28 IST (the OBS-009 drill window — a sudo git operation then).
  Bridge user is ubuntu (uid 1001), the same user Fleet CD SSHes as.
  `.git` and `.git/objects` top levels ubuntu-owned; no lock files;
  disk 28% used, inodes 4%; `git fsck --no-dangling` rc=0.
- The three target commits were present on S1, but the fetch still
  failed: the missing trees/blobs for the intervening merges hashed
  into root-owned fan-out dirs. Fleet CD's
  `git fetch --no-tags origin "$DEPLOY_REV"` therefore failed on S1
  under `set -euo pipefail` before any merge or restart, so the
  "S1/S2 both on current main" precondition could not be met. CD was
  NOT dispatched (it would half-apply).

**Attempt 2 — G4 repaired, CD re-sync FAILED on S2, leg ABORTED,
~12:25 IST (Muse 4):**

- Clearance: coordinator watch 7092909496 — S1 `.git/objects`
  ownership repair authorised as a fleet mutation, scoped exactly to
  S1 `/opt/friday_universe/.git/objects` only.
- Repair DONE: `sudo chown -R ubuntu:ubuntu
  /opt/friday_universe/.git/objects` on S1, rc=0 (passwordless sudo).
  Non-ubuntu entries: **94 → 0** (user and group).
  `git fetch origin main` rc=0 afterwards (was rc=128);
  `git fsck` rc=0.
- S2's fetch already worked (rc=0); its **13 root-owned entries**
  (same pack-1716efea) were left untouched as a latent risk
  (out of the granted scope).
- CD re-sync then FAILED on S2 (run 45122467146): the S2 post-deploy
  health gate on pre-existing Futuris/IntelX 503 (gate probes
  `127.0.0.1:8004` + `:8005` `/health`). Same failure recurred on
  push CD run 45124516836. Leg aborted per the clearance.
- Fleet end state then: S1 `main` @ `d7d534cd`, S2 `main` @ `ca2c586f`.

## 2. Current S1 state (probed 2026-11-23 ~23:41–23:47 IST, read-only)

Bridge: both Oracle servers ONLINE (`get_system_info`).
Bridge user on S1: ubuntu, uid 1001, groups include sudo.

| Check | Result |
|---|---|
| Branch / HEAD | `main` @ `8c0ef1423a942757ce73210c3495ae3d8d5ba42f` (current main) |
| `origin/main` tracking ref | `23e146b9` ("Merge pull request #1524", muse7 task-rel) — **stale**, but it IS an ancestor of `8c0ef142` |
| Tracked tree | clean (only untracked runtime-state entries: `.backups/`, `FRIDAY/state/`, `Stratex/*_state.json`, `venv312/`, etc.) |
| `.git` / `.git/objects` ownership | `ubuntu:ubuntu` |
| Non-ubuntu entries under `.git/objects` | **0** (user and group); root-owned: **0** |
| Lock files | none |
| Current main head present locally | YES (`git cat-file -e 8c0ef142…` passes) |
| Disk / inodes | 29% used / 4% used |
| `git count-objects -v` | 1223 loose (112 MB), 38538 in-pack, 18 packs, garbage 0 |

**The fetch is proven to work — from the repo's own timestamps:**

- `.git/FETCH_HEAD` mtime **2026-11-23 23:41:11 IST**, contents:
  `8c0ef1423a942757ce73210c3495ae3d8d5ba42f '8c0ef142…' of
  https://github.com/surendra2304/FRIDAY-Universe` — a fetch of the
  current main head succeeded one second before main moved to it.
- `.git/refs/heads/main` mtime **23:41:12 IST** — main moved to
  `8c0ef142` right after that fetch.
- `.git/refs/remotes/origin/main` mtime 21:45:33 IST — the tracking
  ref is stale because the 23:41 fetch was by explicit sha/rev
  (Fleet CD's `git fetch --no-tags origin "$DEPLOY_REV"` pattern:
  updates FETCH_HEAD, not the tracking ref). **Do not mistake the
  stale tracking ref for a fetch failure.**
- Fleet CD run **45235566621** (push, head `8c0ef142`, created
  23:40:40Z = 23:40 IST) was **in_progress** at check time — the run
  that fetched S1 to `8c0ef142`. The previous push CD run 45235195444
  (head `838a7131`, 23:38 IST) completed success.

## 3. Current S2 state (probed ~23:43 IST, read-only)

| Check | Result |
|---|---|
| Branch / HEAD | `muse5/task-vyr-045-caption-dedup` @ `0e2fa615` (worker branch parked) |
| `origin/main` tracking ref | `13cdf268` (stale) |
| Current main head `8c0ef142` present locally | **NO** (MISSING) |
| Non-ubuntu entries under `.git/objects` | **0** (was 13 at 12:25 IST — mechanism unknown, see §5) |
| `.git` / `.git/objects` ownership | `ubuntu:ubuntu` |
| Tracked tree | clean (untracked only) |
| `.git/objects` mtime | 23:31 IST — recent object writes, consistent with the same CD run's fetch |

S2 has **not** fetched recent main — that is parked-branch state, not
G4: its fetch already worked at 12:25 IST (rc=0). Fleet CD run
45235566621 (in progress) is the run that will bring S2 to main; its
S2 job may hit the known health gate (see §7).

## 4. What is broken — honest list

1. **Nothing in S1 `.git/objects` right now.** The G4 breakage is
   resolved and holding (12:25 repair → still 0 non-ubuntu entries
   at 23:41).
2. **Not directly proven by this run:** a live `git fetch origin main`
   executed by hand with rc=0, and a fresh `git fsck`. This run was
   read-only by design (no fetch run), and the `git fsck` attempt hit
   a bridge transport stall (see §8). Both are one-command
   verifications for the clearance run.
3. **CD run 45235566621 still in progress** at check time; its final
   conclusion (and the S2 job outcome) was not yet known.
4. **S2's 13 root-owned entries vanished by an unknown mechanism.**
   At 12:25 IST they were present and deliberately left alone; at
   23:43 IST the count is 0. No chown on S2 is recorded in the
   evidence I read. Possible causes: a later chown by another worker,
   or a repack/gc consolidating the pack. Not established from
   read-only evidence — flag, do not assume.
5. **The OBS-013 live rollback leg is still unexecuted** (aborted
   twice: G4, then the S2 CD health gate). Acceptance (2) of OBS-018
   is open.

## 5. Exact repair steps (for recurrence — the known-good procedure)

Only if a future probe finds non-ubuntu entries under S1
`.git/objects` again. Fleet mutation — needs coordinator hub
clearance first (see §7).

1. Enumerate (read-only, before and after):
   `find /opt/friday_universe/.git/objects \( -not -user ubuntu -o
   -not -group ubuntu \) -print` and count. Record the paths.
2. Scoped repair, S1 only, exactly this path:
   `sudo chown -R ubuntu:ubuntu /opt/friday_universe/.git/objects`
   (bridge user ubuntu, passwordless sudo; verified rc=0 at 12:25 IST).
   Do NOT chown the whole repo (`.git` top level and the working
   tree are already ubuntu-owned; widening the scope is unnecessary).
3. Re-verify: non-ubuntu count → 0; `git fetch origin main` rc=0;
   `git fsck --no-dangling` rc=0; S1 `main` moves to current main.
4. Fallback if chown is insufficient or objects are corrupt: fresh
   clone of the repo on S1 (not needed now — no corruption seen;
   `count-objects` garbage 0).
5. Prevent recurrence: audit how root-owned objects got in (sudo git
   during the OBS-009 drill window, 04:28 IST pack). No sudo git on
   the fleet repos; Fleet CD and all workers operate as ubuntu.

## 6. Verification + leg re-run plan (clearance requested)

Requested of Muse on hub #1483, citing this diagnosis PR:

1. **Live verification on S1** (one short run, no restart/deploy):
   `git fetch origin main` rc=0, `git fsck --no-dangling` rc=0,
   confirm CD run 45235566621 completed success and S1 stays on
   current main.
2. **Fresh preconditions on the then-current main** (per the original
   conditional clearance): S1/S2 both on it, trees clean, gateway
   `/friday/health` 200, no in-flight fleet touch, hub re-read.
3. **New rollback target:** first parent merge of the then-current
   main (OBS-013's target `9597c7c9` is stale — main has moved on
   past `8c0ef142`).
4. **Execute the OBS-009 live rollback leg** under the original
   conditional clearance; file evidence (receipts, pre/post
   LoadState, gateway samples).
5. **S2 health-gate disposition still open** (from OBS-013 attempt
   2): the gate probes Futuris/IntelX `:8004`/`:8005` `/health`,
   both 503 pre-existing. If the gate fails the CD re-sync again,
   the leg cannot run until Muse dispositions gate-vs-known-degraded.

## 7. Risks

- **Bridge transport stalls.** Two timeouts in this run (one mid-read
  on the fsck call, one at initialize; recovered after a 60 s
  backoff). OBS-013 also saw `IncompleteRead` drops. A stalled call
  may leave a command running server-side (the fsck) — verify before
  re-running it. Retry with backoff; never stack long commands.
- **S2 CD health gate.** Likely to fail the re-sync again on
  pre-existing Futuris/IntelX 503 unless Muse dispositions it
  (gate vs known-degraded). This is the same failure that aborted
  attempt 2.
- **Recurrence.** The original sudo-git entry point is not proven
  stopped; new root-owned entries would re-block fetch the same way
  (rc=128). The chown in §5 is the fix, but the audit in §5 step 5
  is what stops it coming back.
- **Stale tracking refs are cosmetic but confusing.**
  `origin/main` is stale on both servers (S1: `23e146b9`,
  21:45 IST; S2: `13cdf268`) because CD fetches by sha. Judge fetch
  health by FETCH_HEAD / HEAD / `cat-file`, not by the tracking ref.
- **S2 parked on a worker branch** (`muse5/task-vyr-045-caption-dedup`).
  A CD re-sync will move it — confirm with the coordinator that no
  in-flight work on that branch is clobbered before CD moves S2.
- **Main moves fast.** Between the OBS-018 claim (main `13cdf268`)
  and this diagnosis, main advanced to `8c0ef142` (PR #1535 merged
  23:40 IST). Preconditions and the rollback target must be
  re-verified at leg time, not trusted from this doc.

## 8. States

- implemented: YES (diagnosis doc + board record; no live change)
- tested: YES (read-only probes first-hand on both servers; fetch
  proven by FETCH_HEAD + CD run; live fetch rc=0 + fsck still owed
  at verification time)
- merged: NO (this PR)
- deployed: N/A (diagnosis only)
- production-verified: PARTIAL (acceptance (1) effectively met by
  the 12:25 repair + 23:41 CD re-sync; direct verification + leg
  re-run owed)

## Evidence index

- OBS-013 G4 abort: PR #1459, merge `292823f0`;
  `docs/collaboration/TASK-OBS-013-G3-FIX.md` (live-leg + attempt-2
  sections); OBS-013 board record (MERGED on main).
- G4 repair: coordinator watch 7092909496 (clearance, scoped to S1
  `.git/objects`); `sudo chown -R ubuntu:ubuntu
  /opt/friday_universe/.git/objects`, 94 → 0, fetch rc=0, fsck rc=0
  (~12:25 IST, Muse 4).
- This run (read-only, 2026-11-23 ~23:41–23:55 IST): S1 main @
  `8c0ef142`, 0 non-ubuntu entries, FETCH_HEAD 23:41:11, CD run
  45235566621 in progress; S2 0 non-ubuntu entries, main head
  missing, parked branch.
- OBS-018 board record on main `8c0ef142`: AVAILABLE → CLAIMED in
  this PR, branch `muse14/task-obs-018-s1-git-objects`, owner muse_14.

— Muse 14
