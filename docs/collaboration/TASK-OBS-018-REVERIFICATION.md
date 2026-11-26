# TASK-OBS-018 — S1 git-objects re-verification (Muse TP5, 2026-11-26)

**Task:** TASK-OBS-018 — Fleet: repair the S1 git-objects root ownership (G4)
and re-run the OBS-013 live rollback leg.
**Run:** 2026-11-26 ~18:10 IST, hourly self-check (musetp5-hourly-self-check).
**Clearance:** coordinator WATCH159 ruling 1 (hub #1483 comment 7191367811):
leg-(2) = ANSWERED — TP5 runs the read-only S1 re-verification (ownership
counts, HEAD vs main, FETCH_HEAD, fsck) this hour and files the evidence,
citing the OBS-013 answer. No rollback re-run, no fleet mutation.
**Method:** read-only bridge probes only (`run_shell` on Oracle Server 1,
server 1; bridge health 200 this run). No `git fetch`, no `chown`/`chmod`,
no checkout, no `git status` (index refresh), no restart, no deploy, no
Fleet CD dispatch. Current main at probe time: `087e05d6` (merge PR #1972).

## OBS-013 answer (cited per WATCH159)

- G4 abort + repair (2026-11-23): S1 `git fetch` rc=128 on root-owned
  `.git/objects` entries (94 non-ubuntu, incl. pack-1716efea); scoped repair
  `sudo chown -R ubuntu:ubuntu /opt/friday_universe/.git/objects` under
  coordinator watch 7092909496 took the count 94 → 0, fetch rc=0, fsck rc=0
  (~12:25 IST). CD re-sync then failed on the S2 post-deploy health gate
  (pre-existing Futuris/IntelX 503), aborting the leg. Evidence:
  `docs/collaboration/TASK-OBS-013-G3-FIX.md` (PR #1459, merge `292823f0`)
  and `docs/collaboration/TASK-OBS-018-G4-DIAGNOSIS.md` (Muse 14).
- Disposition ANSWERED: Muse 14 released OBS-018 2026-11-24 ~22:00 IST
  (hub 7138017641); the coordinator ruled the S2 503 evidence stands and no
  rollback leg is needed. Leg (a) verification merged as PR #1542. Board
  record carries this disposition; WATCH159 ruling 1 re-affirms it
  (a rollback re-run is a fleet mutation, barred by the owner stop order).
  Acceptance (2) is therefore closed by answer, not by re-run.

## S1 re-verification results (probed 2026-11-26 ~18:10 IST, read-only)

Host `friday-universe-vnic` (Oracle Server 1), bridge user ubuntu (uid 1001).
Repo `/opt/friday_universe`. Batch A exit code 0.

| Check | Result |
|---|---|
| Branch / HEAD | `main` @ `b51ef05f` (Merge PR #1669) — **not** current main `087e05d6` |
| Current main head present locally | **NO** (`git cat-file -e 087e05d6…` → MISSING) |
| `FETCH_HEAD` | `cc66b42d` branch 'main', mtime **2026-11-24 22:11:06 IST** (last fetch ~2 days ago) |
| `refs/heads/main` mtime | 2026-11-24 19:02:23 IST |
| Non-ubuntu entries under `.git/objects` | **0** (user or group) |
| Root-owned entries under `.git/objects` | **0** |
| Total entries under `.git/objects` | 1960 |
| `.git` / `.git/objects` ownership | `ubuntu:ubuntu` |
| Lock files | **`.git/index.lock` present** — 0 bytes, ubuntu-owned, mtime 2026-11-25 17:51:00 IST (~24h old; see findings) |
| `git count-objects -v` | 1645 loose (153 MB), 40480 in-pack, 28 packs, garbage 0 |
| Disk | 49% used (50G free of 97G) |
| `git fsck --no-dangling` | **PENDING** — launched 18:10 IST; bridge client timed out (no JSON-RPC response); server-side process verified still running at 18:10:34 IST (pid 1149797, state R). rc not yet known; not re-run (never stack). |

## Findings — honest reading

1. **G4 repair is holding.** Zero non-ubuntu and zero root-owned entries
   under S1 `.git/objects`, ~3 days after the 94 → 0 repair. The rc=128
   fetch blocker is not present. Acceptance (1), ownership half: **met and
   verified live this run.**
2. **S1 is not on current main — and that is not G4.** S1 sits at `b51ef05f`
   with a last fetch of 2026-11-24 22:11 IST. With ownership clean, a fetch
   would not hit the G4 permission failure; S1's lag is consistent with the
   closed live gate (owner stop order in force, Fleet CD deploy checks
   failing — WATCH160). No fetch was run this hour (a fetch mutates
   FETCH_HEAD/objects; WATCH159 bars fleet mutation), so **fetch rc=0 is
   NOT claimed**. Acceptance (1), CD-to-current-main half: **not currently
   true; gated, not failed-by-G4.**
3. **Stale `.git/index.lock`.** 0 bytes, ~24h old, no git writer holding it
   (the only git process at check time was this run's fsck, which does not
   take the index lock). Left untouched — removal is a fleet mutation and
   needs coordinator clearance. Flagged for disposition; a stale index lock
   will block the next index-writing git operation (e.g. CD merge) until
   cleared.
4. **fsck outcome owed.** The bridge stall matches the known transport
   behaviour (diagnosis §7). The fsck is running server-side; its rc must
   be collected next run before any fsck claim is made. No corruption
   output was observed (output unreachable after the client timeout).

## States

- implemented: YES (this evidence doc; no live change made)
- tested: YES (read-only live probes first-hand on S1, batch A rc=0;
  fsck launched, result pending)
- merged: NO (this PR)
- deployed: N/A (verification only)
- production-verified: PARTIAL — G4 ownership repair verified holding on
  the live S1 repo this run; CD re-sync to current main and fsck rc remain
  unverified (gated / pending, stated above). TASK-OBS-018 is **not DONE**
  on this evidence alone.

## Owed next

1. Collect fsck completion (process check; rc if recoverable) — next run.
2. Coordinator disposition on the stale `.git/index.lock` (removal is a
   fleet mutation; no action taken).
3. Fleet CD re-sync of S1 to current main when the live gate opens —
   outside this read-only leg.
4. Board flip for OBS-018 (record still reads AVAILABLE / branch null /
   pr null on main `087e05d6`) via coordinator board PR.

— Muse TP5
