# TASK-DB-008 — Back up FRIDAY local state files on FRIDAY-Server (S3): checkpoint 1 (scoping, 2026-11-26 ~09:00 IST)

**Task:** TASK-DB-008 (P2) — "DB: Back up FRIDAY local state files on FRIDAY-Server (S3) - friday.db + JSON state".
**Worker:** Muse 16. **Claim:** hub #1483 comment 7180832667, 2026-11-26 ~07:52 IST.
**Branch:** `muse16/task-db-008-friday-state-backup`, created from main `ffa7ee2f`, fast-forwarded this run to main `036fb2da78a8a9e948382cdd0c6411cf3540a9cc` (merge PR #1941, board PR watch135b) — zero work commits before this checkpoint, ~60 min after claim; this checkpoint is the stall repair.
**Board:** verified first-hand on main `036fb2da` (23,812 lines, blob `53de3c97`): TASK-DB-008 AVAILABLE / owner muse_16 / branch null / pr null / P2 / updated 2026-11-25T22:36 IST. Queue: DB-008 head, DB-010 next; INT-039 + VYR-049 IN_REVIEW (PRs #1912/#1913 merged); DB-002 MERGED (PR #1861).
**Status of this checkpoint:** SCOPING FILED — read-only scoping from repo evidence complete; no live backup run, no live change made. This is a checkpoint, not a completion.

## Baseline (from the DB-003 fleet storage audit — cited, not re-probed)

Source: `docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md` (Muse 13, single dated sweep 2026-11-25 05:43–06:06 IST, live on S3 via the bridge).

FRIDAY live storage on FRIDAY-Server (S3, `FRIDAY.service` active), `/opt/friday_universe/FRIDAY/`:

| File | Size / mtime at sweep | Notes |
|---|---|---|
| `data/friday.db` | 344K, mtime 2026-10-27 | **Stale** (audit disagreement D7) — live FRIDAY state is the ADB schema + current JSON files |
| `data/gemini_pool_state.json` | mtime 2026-11-24 21:18 | Current |
| `data/voice_worker_status.json` | mtime 2026-11-24 21:20 | Current |
| `state/proactive_intelx_watch.json` | 2026-11-25 00:21 UTC | Current; `memory/cold_storage/` empty |
| ADB schema `FRIDAY` | 24 tables, 1,479 rows @ 2026-11-22 | In the 2026-11-22 fleet backup, complete |

**Backup state at sweep: PARTIAL.** ADB schema backed up (2026-11-22 fleet backup, verify 188 ok / 0 failed). Local files: **NO current backup** — `FRIDAY/backups/friday/` empty; `.backups` newest 2026-11-04 (dashboard snapshot, stale). Total local state ~392K. Follow-up filed as DB-008.

## What already exists in the repo vs what is missing (verified first-hand this run)

Checked via the GitHub API against main `036fb2da` (code search + file reads + `scripts/` and `deploy/` listings).

**Exists — and does NOT cover DB-008's files:**

- `scripts/backup_fleet_databases.py` (TASK-INF-003 / SEN-009, 46,352 bytes): ADB schema dumps (FRIDAY schema included) + config snapshot + fleet-state bundle. Its only local-file leg is `AGENT_STATE_GLOBS = ("Stratex/state/*.jsonl", "Stratex/state/*.json")` — Stratex only. **No FRIDAY `data/` or `state/` glob exists.** The Nov 22 run captured nothing for FRIDAY local files.
- `scripts/check_backup_freshness.py` (TASK-SEN-009): freshness tripwire over the fleet backup root `/var/backups/friday-universe` only — checks complete ADB dumps, not FRIDAY local files.
- `scripts/backup_fleet_incremental.py` (TASK-REL-099, merged PR #1916): incremental snapshot store (rsync `--link-dest`) — the store DB-007 builds on. Reusable by DB-008; covers no FRIDAY files itself.
- `FRIDAY/src/friday/core/backup_recovery.py` (6,443 bytes): in-process snapshot manager writing JSON snapshots of in-memory state (memory state, skills, operator states, preferences) to `backups/friday`, 6-hour cadence, 7-day retention. Referenced by `FRIDAY/src/friday/operators/memory_health_operator.py` and docs/tests. **It does not copy `friday.db`, `gemini_pool_state.json`, `voice_worker_status.json`, or `FRIDAY/state/`** — it snapshots in-memory state as JSON, not the files on disk. And the audit found `FRIDAY/backups/friday/` empty on S3, so no live backup files exist from it on the live host. It is not a backup of the DB-008 acceptance set.
- `deploy/`: no backup timer or service unit exists (24 entries: fleet-health-watcher, friday-self-heal, intelx-soak-runner, stratex-forward-scorecard timers; no backup timer). The fleet backup has no schedule anywhere (audit: no timer/cron on any server; three manual runs only).

**Missing — the DB-008 gap:**

- No script, timer, or cron backs up FRIDAY's local state files on S3.
- No manifest / verify / restore-check exists for these files.
- No freshness tripwire covers them (`check_backup_freshness.py` is fleet-ADB only).

## DB-007 overlap verdict (G2 — decided this run)

**DISTINCT — no overlap in scope; pattern reusable.**

- TASK-DB-007 (PR #1925, open, head `0f3ab624`, base `4c0acbfa`, author surendra2304, filed by Muse TP5): formalises the **VyralX file store on VyralX-Server (S5)** — `renders/` 221 files / 2.2G, `media/` 702 / 3.9G, `data/` 79 / 403M. Five files, +582: `scripts/backup_vyralx_filestore.py`, `deploy/vyralx-filestore-backup.{service,timer}` (daily 02:15 UTC), `docs/collaboration/TASK-DB-007-VYRALX-FILESTORE-BACKUP.md`, `tests/test_db007_vyralx_filestore_backup.py`. VyralX-specific 20 GiB cap (one snapshot ~6.5G exceeds the REL-099 fleet 6 GB cap).
- DB-008 covers **FRIDAY local state on FRIDAY-Server (S3)** — `friday.db` + two JSON state files + `FRIDAY/state/`, ~392K total. Different agent, different server, different files, different scale. Nothing in DB-007's script, timer, or manifest touches a FRIDAY file.
- **What carries over:** the DB-007 pattern — script (stdlib only) + per-file SHA-256 manifest + `verify` re-hash + `restore-check` (restore + verify + parse the state JSONs) + daily systemd timer + runbook + tests, built on the merged REL-099 incremental store. DB-008 should follow that pattern with its own small script (`scripts/backup_friday_state.py`), **not** import DB-007's code: PR #1925 is still open and its merge is HELD (board evidence: contracts fails on the pre-existing Futuris FUT-030 time-bomb; fix is TASK-REL-101, Muse TP10; rebase owed once REL-101 lands).
- **Scale note:** DB-008's ~392K needs no VyralX-style cap exception and no prune pressure; 7 daily + 4 weekly retention (DB-007's scheme) is ample.

## Live-leg plan (gated — not run this run)

Acceptance (board): "Back up the FRIDAY local state files on FRIDAY-Server (server 3): FRIDAY/data/friday.db + gemini_pool_state.json + voice_worker_status.json + FRIDAY/state/. Prove with a dated backup + a restore/read-back check."

1. **Script** `scripts/backup_friday_state.py` (stdlib only, DB-007 pattern): `backup` stages `FRIDAY/data/friday.db`, `FRIDAY/data/gemini_pool_state.json`, `FRIDAY/data/voice_worker_status.json`, `FRIDAY/state/`; writes `friday-state-manifest.json` (per-file SHA-256 + bytes, per-tree counts); stores via the REL-099 incremental store (rsync `--link-dest`); prunes 7 daily + 4 weekly. `friday.db` is a live SQLite file — copy via the `sqlite3` backup API (or a service-quiesced file copy) so the snapshot is not torn; record the method in the manifest. `verify` re-hashes a snapshot vs its manifest (read-back). `restore-check` restores + verifies + runs `PRAGMA integrity_check` on the restored `friday.db` copy and parses the restored JSONs.
2. **Timer** `deploy/friday-state-backup.{service,timer}`: daily, Persistent, oneshot (cadence to match the DB-007 02:15 UTC slot or a non-colliding slot — decide at install; do not collide with the fleet backup window).
3. **Out root:** `/var/backups/friday-universe/friday-state` (same root as the fleet backup, separate subtree) — confirm at install; `FRIDAY/backups/` on S3 is the legacy in-process dir and stays out of the fleet root.
4. **Proof (the acceptance):** first dated backup on S3 + restore/read-back check (`verify` + `restore-check` exit 0) + a dated manifest; then extend `check_backup_freshness.py` (or file a follow-up) so the FRIDAY-state leg has a freshness tripwire — the fleet-only checker does not cover it today.
5. **Tests** `tests/test_db008_friday_state_backup.py` (DB-007 pattern: exclusions n/a, manifest, verify + tamper, incremental, restore drill, prune-keeps-newest) + local CLI smoke on fixtures (no live host).
6. **Open question for the coordinator (D7):** `friday.db` is stale (mtime 2026-10-27) — live FRIDAY state is ADB + current JSON files. The task names the file, so it stays in scope, but confirm at the live leg whether the backup should also flag staleness (freshness check on the source) rather than silently archiving a month-old file.

## Gates (live leg cannot run until these clear)

- **G1 — bridge approval for S2/S3 access.** Hub #1483 comment 7113152293 (posted 2026-11-24 ~02:00 IST) is still open with no reply as of this run. The dated backup + restore/read-back proof on S3 needs bridge `run_shell` (or the equivalent S3 access the coordinator grants). No live backup was attempted this run.
- **G2 — DB-007 overlap verdict.** Decided this run: DISTINCT, pattern reusable (see above). No coordinator ruling needed on scope; the DB-007 merge hold (REL-101) does not block DB-008's own script, which builds on the merged REL-099 store.

## States

- Implemented: NO (scoping only; no script, timer, or test written this run)
- Tested: NO (no local tests; no live host touched)
- Merged: NO (work PR this run carries checkpoint 1 only)
- Deployed: NO
- Production-verified: NO — no dated backup exists and no restore/read-back check has run

## Files

- This evidence doc: `docs/collaboration/TASK-DB-008-FRIDAY-STATE-BACKUP.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-DB-008 AVAILABLE/muse_16; branch + pr flip owed — no board edit in this PR, the flip rides in the coordinator board PR per the INT-039/VYR-049 precedent)
- Source audit: `docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md`
- Pattern reference (open PR, not merged): PR #1925, TASK-DB-007 VyralX file-store backup formalisation

— Muse 16, 2026-11-26 ~09:00 IST
