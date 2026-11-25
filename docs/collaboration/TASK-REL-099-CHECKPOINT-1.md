# TASK-REL-099 — Checkpoint 1: scoping + starting state verified

- **Task:** TASK-REL-099 — Git-style incremental fleet backup for Oracle Cloud (owner order 2026-11-26)
- **Claimed:** 2026-11-26 ~01:02 IST by Muse 12 (hub #1483; queue head assigned by coordinator WATCH114 ruling — STR-077 ruled to Muse 17, M12 released to REL-099)
- **Branch:** `muse12/task-rel-099-incremental-fleet-backup` @ main `70ce1089`
- **Board:** AVAILABLE → CLAIMED rides in this work PR

## Source (verified first-hand on main 70ce1089)

- Board entry TASK-REL-099 (board raw read, 2,930,382 bytes): status AVAILABLE,
  owner muse_12 (board PR #1885, merge 1df0af15), P1, files
  `scripts/backup_fleet_databases.py`, `tests/test_rel096_backup_fleet_state.py`,
  `.github/workflows/fleet-backup.yml`, `.github/workflows/backup-watchdog.yml`.
- Owner order 2026-11-26 ~00:07 IST: "Implement git in my Oracle Cloud" —
  backups must add only the modified files, just like git; not all videos need
  to sit in Oracle Cloud; the backup must stop deleting the old set and
  creating a whole new one every day.

## Starting state verified first-hand (this run, main 70ce1089)

- `scripts/backup_fleet_databases.py` (46,412 bytes, blob 85557d1e) writes a
  complete new timestamped set on every run: `shutil.copy2` throughout,
  `shutil.copytree(bundle_dir, fs_dest)` for the unified set.
- `.github/workflows/fleet-backup.yml` (24,881 bytes, blob e1c25f02) runs it
  DAILY (cron `30 3 * * *`) and on pushes touching agent trees; retention only
  prunes whole sets after the fact (Oracle Server 2 `--keep 3`, Server 1 keep 4),
  so every run still writes the full set first.
- Cost per the board evidence (not re-measured this run): unified set
  20261125T165942Z is 2.7 GB (VyralX renders 2.2 GB + data 403 MB); Oracle
  Server 2 49G disk at 95% used, 2.8G free.

## Design direction (board evidence, coordinator design note)

- **Recommended: restic** — content-defined chunking dedupes at sub-file level,
  snapshots + retention (forget/prune) built in, encrypted store, single static
  binary, small RAM footprint.
- **Fallback: rsync --link-dest hardlink snapshots** — no new dependency, but
  whole-file granularity.
- **Not recommended: bare git repo** — 2.2 GB binary renders bloat the object
  store, GC/repack OOM risk on ~1 GB RAM boxes, secrets stay in history.
- The owner requirement is the git *behaviour* (incremental, versioned,
  bounded), not the git binary.

## Open question — tool availability on the Oracle servers

- A bridge `read_file` probe for `/usr/bin/restic` and `/usr/bin/rsync` on
  Server 2 returned "File not found" for both. That probe is **inconclusive**:
  `read_file` cannot distinguish a missing binary from an unreadable binary
  (rsync is already the fleet transport in the unify job, so it is present
  somewhere). Proper confirmation needs a `which`-style check; bridge
  `run_shell` is not allow-listed without Muse clearance, so this is carried
  as checkpoint-2 work: confirm restic installability / presence on both
  Oracle servers via the coordinator route before writing the new store.

## Plan

1. Confirm the chosen tool on both Oracle servers (restic preferred).
2. Implement the incremental store (restic, or rsync --link-dest fallback),
   keeping the TASK-REL-096 manifest + verify + restore-drill harness as the
   acceptance gate around the new store.
3. Prove it with two consecutive runs + the run-over-run stored-bytes report
   (no-change run target: under 150 MB newly stored vs the current 2.7 GB
   full set) + a restore drill at the TASK-REL-096 bar.
4. Retire the old per-run full-set directories by a stated migration step once
   the new store has passed its first drill.

## Acceptance (board)

- INCREMENTAL: second consecutive run stores only what changed; no-change run
  dramatically smaller than 2.7 GB (target under 150 MB newly stored).
- VERSIONED + BOUNDED: list snapshots, restore any retained snapshot, diff two
  snapshots; retention enforced by the job itself (proposal 7 daily + 4 weekly),
  hard cap on the S2 backup footprint (proposal 6 GB total), post-prune
  free-space check in every run log.
- NO MEDIA PILE-UP: VyralX renders/data deduplicated by content; unchanged
  render stored exactly once across snapshots; REL-096 exclusion of VyralX/media
  source clips (3.9 GB, re-obtainable) stays.
- RESTORE DRILL PASSES at the REL-096 bar (Memora restore ZERO empty strings,
  VyralX manifests parse, Stratex forward_scorecard.json + fill_ledger.jsonl
  parse line-complete, MySQL stratex_research dump restores, fleet
  CREDENTIALS.md present in the restored tree).
- NO COVERAGE REGRESSION vs REL-096; daily full-set growth stops; both Oracle
  servers hold a restorable copy; Backup Watchdog freshness alert still fires
  on a missed run.

## Queue / context carried

- **TASK-SEN-034 MERGED** this run: work PR #1877 merged by Surendra
  (merge ff0bba89, 2026-11-26 00:10:45 IST); board on main 70ce1089 reads
  MERGED / pr 1877. Tracked item goal_d87e512046a2 closed.
- **TASK-STR-077 ruled to Muse 17** (WATCH114): M12 released; board on main
  reads AVAILABLE / owner muse_17. M12 does not touch STR-077.
- **Owner stop order still in force** (WATCH114: no clearance; M5 live-leg
  clearance still gated). No live-server change in this task without Muse
  clearance on the hub; implementation is repo-side until the store work
  needs a server run, which will be cleared first.
- **Usage:** 27% of free weekly limit (subscription-status, checked this run;
  reset Nov 29 6:04 PM IST).

— Muse 12
