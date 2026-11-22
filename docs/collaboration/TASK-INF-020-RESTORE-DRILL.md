# TASK-INF-020 — Restore-drill evidence for TASK-INF-003

**Task:** TASK-INF-020 (restore-drill evidence for TASK-INF-003: Oracle DBs and service configs).
**Drill date:** 2026-11-22, run by Muse 10. **Board:** CLAIMED → IN_REVIEW with this PR.
**Outcome in one line:** Newest backup chain (2026-11-18) verified end-to-end — all 136 table files hash- and row-count-clean, Phase A verify-only passes for all 10 agents + media (all drift positive, as expected), and all 21,055 rows loaded into scratch databases with counts equal to the manifests; no live database or config was written to.

## 1. Backup chain used (newest)

| Backup | Location | Created (UTC) | Manifest | Config files |
|---|---|---|---|---|
| Fleet (10 agents) | Server 1 `/var/backups/friday-universe/20261118T173701Z` | 2026-11-18T12:07:01Z | `complete: true`, `failed_agents: []` | 44 configs + 8 agent-env files |
| Media (VYRALX_MEDIA) | Server 2 `/var/backups/friday-universe/20261118T173646Z` | 2026-11-18T12:06:46Z | `complete: true`, `failed_agents: []` | 23 configs |

Older chain member on each server: `20261116T062553Z` (Server 1) / `20261116T062536Z` (Server 2). Weekly Fleet Backup workflow; the 2026-11-18 backup is the first scheduled success (SEN-009) and the newest chain. Per-agent rows in the Server 1 manifest: FRIDAY 1,411 (24 tables), INFERENCE 2,380 (9), MEMORA 11,420 (16), STRATEX 0 (4), FUTURIS 44 (13), INTELX 971 (20), FORGE 4,506 (7), SENTINEL 8 (15), CORTEX 1 (17), VYRALX 278 (10) — 21,019 rows, 135 tables. Media manifest: VYRALX_MEDIA 36 rows, 1 table (`MEDIA_FILES`).

## 2. What was run (commands, paths, timestamps)

All drill commands ran from the server that hosts the backup (`/opt/friday_universe` checkout, venv python). Times in IST (UTC+5:30) unless marked Z.

**Step 1 — Independent integrity re-check of the backup files** (2026-11-22 ~11:11 IST).
For every table file in each manifest: recomputed SHA-256 and compared it to the manifest's `sha256`, gunzipped and counted lines, compared the count to the manifest's `row_count`.
- Server 1: 135/135 files, SHA-256 match, gzip-readable, line counts == manifest row_counts. 21,019 rows, 2,685,987 bytes total. **Mismatches: none.**
- Server 2 (media): 1/1 file, SHA-256 match, 36 rows, 5,503 bytes. **Mismatches: none.**

**Step 2 — Backup tool's own `--verify`** (runbook precondition 2).
- Server 1, ~11:12 IST: `sudo /opt/friday_universe/venv/bin/python scripts/backup_fleet_databases.py --verify --from-dir /var/backups/friday-universe/20261118T173701Z` → `[VERIFY] 187 files OK, 0 failed`, exit 0, 3.4 s.
- Server 2, ~11:16 IST: same command with `--from-dir /var/backups/friday-universe/20261118T173646Z` → `[VERIFY] 27 files OK, 0 failed`, exit 0.

**Step 3 — Phase A verify-only drill** (runbook Phase A, read-only: compares live row counts against the manifest; no writes). Note: the runbook's `--from-dir` flag does not exist on the restore tool — the working flag is `--backup-dir` (gap G1 below). Commands were run in the background and polled because the bridge MCP layer drops calls longer than ~45 s.
- Server 1, 11:14:33–11:14:47 IST (2026-11-22T05:44:33–47Z): `sudo /opt/friday_universe/venv/bin/python scripts/restore_fleet_database.py --backup-dir /var/backups/friday-universe/20261118T173701Z --agents FRIDAY,INFERENCE,MEMORA,STRATEX,FUTURIS,INTELX,FORGE,SENTINEL,CORTEX,VYRALX`
- Server 2, 11:17:43–11:17:45 IST (2026-11-22T05:47:43–45Z): same tool, `--backup-dir /var/backups/friday-universe/20261118T173646Z --agents VYRALX_MEDIA`

**Step 4 — Scratch load test** (restore-to-scratch, safe form). The restore tool's own row reader (`scripts/restore_fleet_database.py`, `iter_backup_rows`) decoded every backup file and loaded the rows into a scratch SQLite database in `/tmp`, verifying the loaded count per table against the manifest. This proves the backup bytes decode and load; it is not an Oracle load (see gap G8 — the Oracle `--apply` path needs the gated scratch user).
- Server 1, ~11:19 IST: `/tmp/muse10_scratch.db` — 135/135 tables, 21,019/21,019 rows, counts equal to manifest for every table. **Problems: none.** Scratch DB 12,869,632 bytes, deleted afterwards.
- Server 2, ~11:21 IST: `/tmp/muse10_scratch_media.db` — `VYRALX_MEDIA/MEDIA_FILES` 36/36 rows. Scratch DB 20,480 bytes, deleted afterwards.
- Teardown verified on both servers: no `/tmp/muse10_*` files remain.

**Not run:** no `--apply`, no `--replace`, no `--yes-i-understand`, no service stop/restart, no live writes of any kind. No live database or config was overwritten (acceptance 3).

## 3. Phase A results (per agent)

`match` = live rows == backup rows; `differ` = live rows != backup rows (all differ here are live **greater** than backup — the fleet kept writing after the 2026-11-18 backup, i.e. the runbook's expected DRIFT); `missing` = backup table absent from live schema; `extra` = live table not in backup.

| Agent | match | differ | missing | extra |
|---|---:|---:|---:|---:|
| FRIDAY | 21 | 3 | 0 | 0 |
| INFERENCE | 5 | 4 | 0 | 0 |
| MEMORA | 8 | 7 | 1 | 1 |
| STRATEX | 4 | 0 | 0 | 0 |
| FUTURIS | 7 | 6 | 0 | 0 |
| INTELX | 20 | 0 | 0 | 0 |
| FORGE | 7 | 0 | 0 | 0 |
| SENTINEL | 14 | 1 | 0 | 0 |
| CORTEX | 17 | 0 | 0 | 0 |
| VYRALX | 5 | 5 | 0 | 0 |
| VYRALX_MEDIA (Server 2) | 1 | 0 | 0 | 0 |
| **Total** | **109** | **26** | **1** | **1** |

Differ details (backup → live, all positive):
- FRIDAY: CONVERSATION_HISTORY 329→349 (+20), MEMORA_RECORDS 303→304 (+1), MESSAGES 773→801 (+28).
- INFERENCE: MEMORIES 199→253 (+54), MESSAGES 807→1023 (+216), RUNS 1145→1434 (+289), TASKS 220→274 (+54).
- MEMORA: AUDIT_LOGS 6338→6400 (+62), DELETION_TOMBSTONES 319→323 (+4), EVENT_LOG 1183→1198 (+15), MEMORA_VECTOR_STORE 481→488 (+7), MEMORY_RECORDS 481→488 (+7), MEMORY_RELATIONSHIPS 2109→2110 (+1), `VECTOR$MEMORA_VECTOR_STORE_IDX$154120_154126_0$HNSW_SHARED_JOURNAL_CHANGE_LOG` 0→7 (+7).
- FUTURIS: AUDIT_LOGS 11→12 (+1), EVIDENCE_REFS 11→277 (+266), FORECASTS 11→362 (+351), FORECAST_EVENTS 11→613 (+602), FORECAST_SCORES 0→146 (+146), OUTCOMES 0→147 (+147). Large deltas are 4 days of active forecasting, not a defect.
- SENTINEL: SENTINEL_EVENTS 3→10 (+7).
- VYRALX: ASSETS, PUBLISH_JOBS, RENDER_JOBS, SOURCES, VIDEO_PROJECTS 54→65 (+11 each).
- Zero negative deltas anywhere: no live table holds fewer rows than the backup, so nothing was lost between backup and drill.

Tool verdicts: Server 1 run printed `[DRILL] ISSUES FOUND at 2026-11-22T05:44:47Z` (exit 1) — this is gap G6, not a drill failure: the tool exits 1 on any drift, and drift is the expected outcome. Server 2 media run printed `[DRILL] OK at 2026-11-22T05:47:45Z` (exit 0).

## 4. Gaps found (with file/line)

- **G1 — Runbook commands use a flag the tool does not have.** `docs/observability/RESTORE_DRILL_RUNBOOK.md:26`, `:30`, `:44`, `:66–67` use `--from-dir` for `scripts/restore_fleet_database.py`. The tool's argparse has no `--from-dir`; the working flag is `--backup-dir` (`scripts/restore_fleet_database.py:198`). Copy-pasting the runbook's Phase A/B commands fails with an argparse error. (`--from-dir` exists only on the *backup* tool, `scripts/backup_fleet_databases.py:465`, for `--verify`.)
- **G2 — Runbook uses a `--media` flag the restore tool does not have.** `docs/observability/RESTORE_DRILL_RUNBOOK.md:30`. The restore tool has no `--media` argument; the media schema is addressed as agent `VYRALX_MEDIA` (`scripts/restore_fleet_database.py:46`, `AGENT_ENV_DIRS`).
- **G3 — Runbook's expected output vocabulary does not exist in the tool.** `docs/observability/RESTORE_DRILL_RUNBOOK.md:5` and `:33` say the tool prints `LOADABLE / REFUSED / MISSING / DRIFT` per table and "every table reports DRIFT or LOADABLE". The tool's verify-only mode prints `match / differ / missing_in_live / extra_in_live` (`scripts/restore_fleet_database.py`, `compare_to_live`). A driller following the runbook cannot map the expected outcome to real output.
- **G4 — Runbook cites a companion doc at the wrong path.** `docs/observability/RESTORE_DRILL_RUNBOOK.md:7` cites `docs/runbooks/BACKUP_RESTORE_AND_LEDGER_DRILL.md`; the file lives at `docs/observability/BACKUP_RESTORE_AND_LEDGER_DRILL.md`.
- **G5 — Restore tool docstring cites a runbook that does not exist.** `scripts/restore_fleet_database.py:21`: `Runbook: docs/observability/BACKUP_RESTORE_DRILL.md`. No such file; the runbook is `docs/observability/RESTORE_DRILL_RUNBOOK.md`.
- **G6 — Drill exit code contradicts the runbook's expected outcome.** `scripts/restore_fleet_database.py:227`, `:231`, `:235–236`: `overall_ok` is set False on any differing or missing table, so a drill with only expected positive drift prints `[DRILL] ISSUES FOUND` and exits 1. A clean drill looks like a failure, and automation cannot distinguish drift from real breakage. Fix: treat all-positive drift as OK (or add a `--expect-drift` mode), and reserve exit 1 for negative deltas / missing user tables.
- **G7 — Backup dumps Oracle-internal VECTOR$ index tables that cannot be restored as-is.** `scripts/backup_fleet_databases.py:276` (`tables = list_tables(conn)`, unfiltered) and `scripts/oracle_db.py:257–268` (`list_tables` selects every row of `all_tables`, no exclusion). Evidence: the MEMORA backup contains `VECTOR$MEMORA_VECTOR_STORE_IDX$154120_154126_285$HNSW_ROWID_VID_MAP` (481 rows), but live now holds `..._289$HNSW_ROWID_VID_MAP` instead — the vector index was rebuilt and the old internal table is gone (Phase A: 1 missing, 1 extra, both `VECTOR$…ROWID_VID_MAP`). An `--apply` restore would report `MISSING_IN_LIVE` for it. The user data itself is intact (`MEMORA_VECTOR_STORE`, 481→488 rows). Fix: exclude `VECTOR$*` internal tables from backups (they are rebuilt with the index), or document them as unrestorable by design.
- **G8 — BLOCKED, not a defect: Phase B1 (real Oracle load into an empty target) was not run.** The runbook's Phase B1/B2 needs a scratch ADB user (`SEN009_DRILL`), which needs ADMIN credentials from the dossier plus the coordinator's go-ahead recorded on the board entry (`docs/observability/RESTORE_DRILL_RUNBOOK.md`, Phase B2). No go-ahead exists for this task, so no scratch user was created and no Oracle `--apply` was attempted. The scratch SQLite load in §2 step 4 proves the backup bytes decode and load, but does **not** prove the Oracle INSERT path (`insert_table`, `scripts/restore_fleet_database.py`) end-to-end. Follow-up: coordinator authorises the B2 gate, then a B1 drill loads FORGE (7 tables, 4,506 rows) into the scratch user and verifies post-load counts equal the manifest.
- **G9 — Observation, resolved by this drill's evidence:** `docs/observability/BACKUP_REPAIR_SEN009.md` §8 left open whether SENTINEL/CORTEX/VYRALX credentials resolve from a Server-1-only run. The 2026-11-18 backup (`complete: true`, `failed_agents: []`) and this drill's successful Server 1 connections for all 10 agents — including SENTINEL, CORTEX and VYRALX — show it resolved in practice.

## 5. What this drill deliberately did not do (per runbook)

- No restore over live data (that is a recovery, not a drill); no `--replace`.
- No offsite-artifact decrypt-and-verify (`BACKUP_REPAIR_SEN009.md` §6; needs `BACKUP_ARTIFACT_PASSPHRASE`, which does not exist yet).
- No Phase B3 production-shaped drill (maintenance window, coordinator-gated).

## 6. Environment notes

- Bridge checkout on Server 2 was on another worker's branch (`muse7/task-str-fwd-035-daemon-timeframe-label`, `c6c129ea`) — drill commands used only the bridge's read/`run_shell` tools, never its git tools. Server 1 checkout was on `main` (`ef42312f`); the restore/backup scripts there match main's blobs (flag lines verified identical).
- The bridge MCP layer dropped several `run_shell` calls mid-flight ("MCP request did not complete"); timed-out calls provably did not execute on the server (no process, no log file), and each was retried. Long drill commands were therefore launched in the background and polled — worth knowing for anyone re-running this drill.

— Muse 10, 2026-11-22
