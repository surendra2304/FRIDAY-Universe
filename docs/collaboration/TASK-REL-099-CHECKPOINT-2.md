# TASK-REL-099 — Checkpoint 2: rsync --link-dest incremental store (implemented + proven locally)

- **Task:** TASK-REL-099 — Git-style incremental fleet backup for Oracle Cloud
- **Branch:** `muse12/task-rel-099-incremental-fleet-backup` @ main `a0a45bdf`
- **Board:** IN_PROGRESS → IN_REVIEW rides in this work PR; LAP-003 branch
  `null` → `muse12/task-lap-003-laptop-phone-wave2` rides in the same PR
  (branch existed since checkpoint 33; the flip was owed since 02:53 IST)

## Tool decision (probe evidence, checkpoint 33)

- Probe 2026-11-26 03:00–03:08 IST: restic absent on both Oracle servers,
  rsync present at `/usr/bin/rsync` on both. Checkpoint 2 therefore builds
  the **rsync `--link-dest` fallback** (checkpoint 1 design). Restic stays
  the preferred tool if it is installed later; the snapshot layout is
  tool-neutral (one directory per snapshot, report alongside).

## What was built

- `scripts/backup_fleet_incremental.py` (new, stdlib only): the snapshot
  store with CLI (`store` / `list` / `diff` / `prune` / `restore`).
  - `store_snapshot`: `rsync -a --link-dest=<latest snapshot>`; pure-python
    hardlink fallback when rsync is missing. Reports files linked/copied,
    newly stored bytes, store total, free space after.
  - Ownership is by first appearance (inode set), not link count: a file
    linked into two snapshots has nlink 2 in both, so link-count accounting
    would own it in neither. `newly_stored_bytes` = bytes whose inode no
    earlier snapshot holds; `store_total_bytes` = each distinct inode once.
  - `diff_snapshots`: added / removed / modified (size+mtime quick check,
    SHA-256 confirmation).
  - `prune_snapshots`: retention 7 daily + 4 weekly, then the 6 GB hard cap
    (oldest first, never the newest), with the post-prune free-space check
    in the report. Honest limit found in testing: pruning an old snapshot
    frees only its owned bytes — fully-shared content stays owned by the
    newest snapshot that still links it, so the cap cannot shrink a store
    below the newest snapshot's content. The report says so in bytes.
  - `restore_snapshot`: copies a snapshot out as independent files.
- `tests/test_rel099_incremental_store.py` (new, 11 tests): rsync argv shape,
  no-change run stores 0 new bytes, changed file stored once / unchanged
  file shares the inode, old snapshot keeps old content, diff, rsync path
  when the binary is present, daily retention, hard cap, restore at the
  REL-096 bar, store aborts (missing source, duplicate snapshot).

## Proof (local, this run — fixture set, not live fleet data)

Two consecutive runs on a 50,331,833-byte fixture set (48 MB VyralX-style
renders + Stratex ledger/scorecard + manifests + CREDENTIALS.md), rsync path:

| run | result |
| --- | --- |
| 1 — `20261126T050000Z` | 8 files, 0 linked, 8 copied, newly stored **50,331,833 bytes** |
| 2 — no change | 8 files, 8 linked, 0 copied, newly stored **0 bytes** |
| 3 — one ledger line appended | 8 files, 7 linked, 1 copied, newly stored **54 bytes** |

- `du`: 3 snapshots occupy **49 MB** on disk (old full-set scheme: 3 × 48 MB
  = 144 MB). `diff` run 1 → run 2 is empty.
- Prune (`--keep-daily 2`): run 1 removed (outside retention, owned 0 bytes —
  its files live on in runs 2/3), 2 kept, store total 50,331,887 bytes, free
  space recorded in the report.
- Restore of run 3 passes the REL-096 bar: manifest `complete`, ledger 6
  JSON lines (line-complete), forward scorecard parses (`n` = 42),
  CREDENTIALS.md present, restored files are independent copies (nlink 1).
- Tests: **25 passed** (`tests/` in a scratch tree: 11 new REL-099 + 14
  REL-096, no regression). CI on this PR is the gate.

## NOT yet proven (checkpoint 3, gated)

- Two consecutive runs on the **live fleet set** and the restore drill on
  real data, plus wiring the store into `.github/workflows/fleet-backup.yml`
  (replacing the per-run full-set write). Both need a server run, which
  needs Muse clearance on the hub under the owner stop order — no
  live-server change in this PR. This checkpoint is repo-side only.
- The 150 MB no-change-run target from the board is met trivially here
  (0 bytes on the fixture); the live number is checkpoint-3 evidence.

## Queue / context carried

- **REL-099 checkpoint 1 merged** (PR #1887, merge `3f9d8967`,
  2026-11-26 01:22 IST). Branch recreated at current main `a0a45bdf` this
  run (was at `5639ea26`, behind after merges #1902/#1907); LAP-003 branch
  recreated at the same main.
- **WATCH122/123/124 read in full:** no M12 directive; no stop-order lift;
  M5 live-leg still gated. Board-PR pipeline blocked by the execution-risk
  check; coordinator rebuild PR #1909 open (drops the API-007 flip).
  M12 queue per WATCH123: REL-099 → LAP-003 → EARN-029.
- **FUT-019:** still unscorable — IARI table ends 23/11 (last verified
  03:53 IST); not re-checked this run.
- **Usage:** 29% of free weekly limit (checked this run; reset Nov 29
  6:04 PM IST).

— Muse 12
