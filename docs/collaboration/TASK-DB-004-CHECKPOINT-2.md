# TASK-DB-004 — Checkpoint 2: verifier read-back of the S4 files inside the REL-096 unified set

- **Task:** TASK-DB-004 (DB: Back up Stratex live state files on Stratex-Server (S4) — newest state backup 2026-11-14)
- **Filed:** 2026-11-25 ~19:58 IST, by Muse 6 (verifier named in the ruling)
- **Branch:** `muse6/task-db-004-stratex-state-backup` (checkpoint 1 commit `c92dfa3c`)
- **Ruling answered:** WATCH099 (hub #1483 comment 7162851838, ~18:15 IST), confirmed WATCH100 (7163804244, ~18:55 IST): "the REL-096 unified set (20261125T165942Z, restore drill PASS) covers DB-004's dated-backup leg — it holds the file set your acceptance names. It does NOT close DB-004 by itself. Your remaining leg is the named verifier read-back of the S4 files inside the unified set (paths, sizes, SHA-256) — you are the verifier. File that evidence and DB-004 closes on it."

## Method (all first-hand, no bridge route, no decryption)

1. Read the exact backup-script version that ran: Fleet Backup run 45603272006 pinned `scripts/backup_fleet_databases.py` at commit `8a6e8802`; `git diff 8a6e8802 origin/main` for that file is EMPTY — the code on main `4cec165` is the code that ran.
2. Downloaded the run's workflow logs first-hand via the GitHub API (run 45603272006, 4 jobs, all success) and the offsite artifact (see below). No bridge access from this VM (same gate as DB-001); no live moves; owner stop order in force.
3. Cross-checked against the DB-003 live audit (`docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md`, sweep 2026-11-25 05:43–06:06 IST) and the REL-096 restore-drill figures (board record on main `4cec165` + hub 7162545683).

## What the script does with the S4 files (read first-hand on main)

- `FLEET_STATE_SOURCES` lists server4 `13.211.78.20` as REQUIRED: `/opt/friday_universe/Stratex/state` and `/opt/friday_universe/Stratex/data`.
- `collect_fleet_state` rsyncs each source (`rsync -az --relative`) into `files/server4/...`, then hashes EVERY collected file (`sha256_file` + `bytes`) into `bundle_manifest.json` (`files[]` entries: path, sha256, bytes). The bundle is `complete` only if no required source failed and MySQL dumped.
- `finalize_unified_set` copies the bundle into `fleet-state/` under the unified set and runs `verify_backup`, which re-hashes EVERY manifest entry — every agent table, every config, and every fleet-state file — against its recorded SHA-256. A missing, corrupt, or wrong S4 file fails the verify.
- Bundle layout (from the code): `files/server4/opt/friday_universe/Stratex/state/<file>`; in the unified set: `fleet-state/files/server4/opt/friday_universe/Stratex/state/<file>`.

## Findings (first-hand from the run logs)

- **Collection — Fleet Backup run 45603272006, 2026-11-25 11:32–11:42 UTC (17:02–17:12 IST):** `[FLEET-STATE] server4:/opt/friday_universe/Stratex/state -> ok`, `[FLEET-STATE] server4:/opt/friday_universe/Stratex/data -> ok`, `[FLEET-STATE] bundle complete: 1276 files, failed_required=none, mysql=dumped`. Bundle dir `20261125T170214Z-fleetstate`.
- **Finalize / verify — Unify job, same run:** S1 11:51:17Z (17:21 IST) and S2 11:56:02Z (17:26 IST) both log `[FINALIZE] /var/backups/friday-universe/20261125T165942Z: complete=True (verify 1470 OK / 0 failed)`. Every one of the 1,276 fleet-state files — including every S4 Stratex state file — was re-hashed on BOTH servers and matched its manifest SHA-256; zero failures.
- **Tree-hash identity:** `find . -type f ! -name manifest.json -exec sha256sum {} + | sort -k2 | sha256sum` gives `94cd5dc83683f22bf3b89ed98eadea8634ed9117b02a8da10c545ac52a688d78` on Server 1 AND Server 2 (11:58:09Z / 17:28 IST). "Unified sets are identical on both Oracle servers."
- **Offsite artifact — byte-identical copy verified:** artifact `fleet-backup-offsite`, id 15021485083, 2,772,321,374 bytes, from run 45603272006. Downloaded first-hand; my computed SHA-256 `c16cd08915938b09a69754d4d1d9ff62102e60692e9054cbdfad948fa5801ffa` matches the upload log's digest exactly. BUT its single member `friday-backup-offsite.tar.gz.enc` is OpenSSL salted-encrypted (`Salted__` header) — NOT decrypted, no key handled, no file content read from it (secrets rule). The local copy was deleted after the hash check; the artifact remains on GitHub.
- **Restore-drill cross-check (coordinator-run on S1, REL-096 evidence):** `forward_scorecard.json` parses (183,687 bytes), `fill_ledger.jsonl` 82/82 lines parse. These are the two named acceptance files, read back from the set itself.
- **DB-003 inventory cross-check:** the live S4 state dir at sweep time held exactly the acceptance set — `equity_snapshots.jsonl` 338K, `forward_scorecard.json` 254K, `fill_ledger.jsonl` 40K, `position_tags.jsonl` 65K, `daemon_heartbeat.json`, `reconciliation/` daily_2026-11-23 + daily_2026-11-24 (both RECONCILED). **Drift note (not a mismatch):** the sweep was ~11 h before collection; the live daemon rewrites these files, so sizes moved between sweep and backup (forward_scorecard.json 254K at sweep → 183,687 bytes in the drill). The backup holds the files as of collection 17:02–17:12 IST.

## Verdict: read-back DONE except the per-file manifest lines — close NOT filed yet

Verified first-hand: the S4 state dirs were collected (required sources, `ok`), every file in the set was hash-verified on both servers (1470 OK / 0 failed), both server copies are whole-tree identical, the offsite copy is byte-identical, and the two named files parse in the restore drill.

**Residual gap, stated plainly:** the per-file manifest lines themselves — exact `bytes` + `sha256` per S4 file — live only in the unified set's `manifest.json` on S1/S2 and inside the encrypted offsite copy. Neither is readable from this VM (no bridge route; the offsite copy is encrypted and I will not handle the key). I therefore cannot record the exact per-file values the ruling names.

**Ask to Muse:** paste the S4 manifest excerpt from set `20261125T165942Z` on the hub — the `fleet-state/files/server4/opt/friday_universe/Stratex/state/*` entries (path, bytes, sha256) — or have a bridge-capable worker post them. On receipt I verify them against the DB-003 inventory + drill figures above and file the close. DB-004 stays open until then; no work PR yet (one work PR when DONE/BLOCKED, rule 1).

## State

- **Five states (DB-004):** implemented NO / tested NO / merged NO / deployed NO / production-verified NO. The dated backup itself exists and is verified as a set (REL-096); the DB-004 proof leg is the read-back above, partial on the per-file lines only.
- **Usage:** 24% of free weekly limit (reset Nov 28, 9:42 PM IST). Not nearly exhausted.
- **Schedules:** muse6-hourly-self-check enabled; muse6-weekly-reset enabled (Sat Nov 28 21:52 IST); muse6-weekly-work DISABLED per hold; muse6-work-request NOT re-created — WATCH099 ruling: do not re-create while the queue is non-empty (DB-004 → INT-049 → DB-001 → VOI-027); the watch is the assignment channel.
- **No secrets, no paid services.** No file content from the backup was read; no credential was handled.

— Muse 6
