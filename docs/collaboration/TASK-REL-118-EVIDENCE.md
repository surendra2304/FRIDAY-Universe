# TASK-REL-118 — CD SSH deploy-step repair: diagnosis + fix

Claim: hub #2045 comment 7220464904 (WATCH223 §C, BE 19:14 §A adopted).
Branch: `muse13/task-rel-118-cd-ssh-deploy` @ main `09691836`.
Repair PR due 2026-11-28 12:00 IST.

## 1. Diagnosis — the failing run, first-hand

Run 45969056089 (workflow `.github/workflows/deploy-monorepo.yml`,
"FRIDAY Universe Fleet Continuous Deployment", push to main,
head `7175b9b0`, 2026-11-27 08:52:26Z / 14:22 IST): completed/failure.
"Analyze Changed Agents" succeeded; BOTH deploy jobs failed at the
single SSH step (`appleboy/ssh-action`, exit code 1):

### Server 1 — stale `.git/index.lock` (the repairable leg)

Job 140404815165, step "Update Changed Agents on Server 1":

```
From https://github.com/surendra2304/FRIDAY-Universe
 * branch  7175b9b01d78785e210231ad3362605e1579421f -> FETCH_HEAD
Updating bf3c76c9..7175b9b0
error: Unable to create '/opt/friday_universe/.git/index.lock': File exists.
Another git process seems to be running in this repository, e.g.
an editor opened by 'git commit'. ...
2026/11/27 08:53:08 Process exited with status 1
```

The fetch succeeded; the ff-only merge died on the lock. The branch
guard and dirty-tree guard both passed first, so the tree is on main
and clean — only the lock blocks the deploy.

### Server 2 — parked branch, guard correct (the operational leg)

Job 140404815222, step "Update Changed Agents on Server 2":

```
=== Syncing FRIDAY Universe on Server 2 (FRIDAY Universe VNIC 2) ===
##[error]TASK-OBS-005 branch guard: /opt/friday_universe is checked out
on branch 'musetp13/task-frd-046-storage-repair-sequences' instead of
'main' — refusing to fast-forward. Return the checkout to the main
branch and re-run this deploy.
```

The guard did its job. No workflow change can or should fix this:
auto-switching branches would strand TP13's work. The checkout must be
returned to `main` on Server 2 by whoever owns that session (TP13 /
Muse) — a live-server action, not a code change.

## 2. Recurrence — both failures persist, no green deploy since

| Run | Head | Time (IST) | S1 | S2 |
|---|---|---|---|---|
| 45969056089 | 7175b9b0 | 14:22 | index.lock | parked branch (TP13) |
| 46006566115 | 1cd2e2c8 | 18:52 | index.lock (same lock, checkout still `bf3c76c9`) | parked branch (TP13) |

Every later "success" run of the workflow (46002625893, 46006530810,
46006606291, 46006861383, 46008694701, 46011723166, 46011775687) had
BOTH deploy jobs SKIPPED — board-only merges, no agent changes — so
none of them proves the deploy step works. The last two real deploy
attempts both failed both servers. The S1 lock survived 4.5h across two
attempts with the checkout unmoved: it is stale, not a concurrent
process (no live git process survives that window across two deploys).

Context: on 2026-11-26 the same two servers tripped different guards
(REL-102 evidence: S1 dirty-tree, S2 parked on
`muse10/task-voi-044-acceptance-run-27`). The S1 state has since moved
from dirty-tree to stale-lock; the S2 parked branch changed hands
(M10 -> TP13). The deploy step has not completed a real deploy since
the REL-102 break.

## 3. Fix — stale-lock recovery in the workflow (this PR)

`.github/workflows/deploy-monorepo.yml`, both deploy jobs, new marked
block `# BEGIN/END STALE-LOCK RECOVERY (TASK-REL-118)`, placed after
the branch guard and before the dirty-tree guard:

- If `.git/index.lock` exists, check for a git process working in THIS
  checkout (`pgrep -x git`, cwd-scoped via `/proc/<pid>/cwd`).
- Live process found -> refuse loudly (`::error::`, names the pid),
  lock preserved, deploy fails and must be re-run. Never delete a live
  process's lock: it would corrupt the index it is writing.
- `pgrep` unavailable -> refuse loudly as well; the lock is never
  removed blind.
- No git process in this checkout -> remove the stale lock, log it,
  proceed. (A git process in a DIFFERENT directory does not block.)
- No lock -> no-op.

Tests: `tests/test_fleet_cd_rel118_stale_lock.py`, following the
established extract-and-execute pattern (OBS-005 / REL-102). Six
tests: two structural pins (exactly two blocks, byte-identical,
positioned branch guard -> recovery -> dirty-tree guard) and four
behavioural proofs executed in scratch repos — stale lock removed,
live process refuses + lock preserved, no-lock no-op, foreign-dir git
process does not block. The live-process case uses a copy of
`/bin/sleep` named `git` so `pgrep -x git` matches it exactly like a
real git process.

Dry-run proof (local, 2026-11-27 ~20:00 IST): all 6 new tests pass,
and the existing `test_fleet_cd_branch_guard.py` +
`test_fleet_cd_rel102_checkout_guards.py` suites still pass —
**19 passed, 0 failed** (pytest 9.2.0), including the
`bash -n` validity check on both full job scripts.

## 4. What this PR does NOT prove (honest caveats)

- **No green CD run yet.** A green run needs (a) this PR merged, (b)
  the S1 stale lock cleared — the fixed script does this itself on the
  next deploy attempt — and (c) the S2 checkout returned to `main`
  (operational, needs server access; requested on the hub). Until (c)
  happens, S2 will keep tripping the branch guard correctly. The next
  agent-changing push after merge + (c) is the live proof; it is NOT
  claimed here.
- **Server 1's lock is assumed stale, not verified on the server.**
  The evidence is circumstantial but strong: identical lock, identical
  base `bf3c76c9`, 4.5h apart, two failed attempts. The fix is
  fail-closed by design — if a git process IS running at deploy time,
  the deploy refuses rather than deleting the lock.
- **Board record:** TASK-REL-118 is not on the board yet; the NEW
  record (CLAIMED muse_13) rides the next coordinator board PR per
  WATCH223 §E. This PR carries no board hunk.
