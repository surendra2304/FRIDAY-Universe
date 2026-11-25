# TASK-DB-003 — Fleet storage audit: one live-verified table of every agent's storage and backup state

- **Task:** TASK-DB-003 (DB: Fleet storage audit — one live-verified table of every agent's storage and backup state, including the VyralX file-store formalisation)
- **Assignment:** coordinator watch 7147595568 (run scheduled 04:37 IST, 2026-11-25): DB-003 is Muse 13's next movable task, queue head (STR-HLT-002 stays queued behind its Spotware gate, VOI-030 stays blocked on the calm window).
- **Claim:** hub #1483 comment 7148234290 (2026-11-25 ~05:45 IST).
- **Branch:** `muse13/task-db-003-fleet-storage-audit` from main `c6254208`.
- **Board verified first-hand on main c6254208** (board blob `4610f511`, 22,297 lines, 970 tasks, 0 dup ids): TASK-DB-003 AVAILABLE / owner null / pr null, P1.
- **Sweep:** single dated sweep 2026-11-25 05:43–06:06 IST (first probe 00:13:15Z, last probe 00:36:01Z), via the FRIDAY Universe Bridge `run_shell` (servers 1–6) and `read_text`. Read-only throughout; no production change. No `.env` or credential file contents were read; no secret appears in this doc, the PR, or any hub post. Database DSNs appear only as redacted in the fleet backup manifest.
- **Work PR:** to be filed this run (number filled into the board flip when known).

## Decided arrangement (reference column — owner orders 2026-11-25 ~02:56 and ~02:59 IST)

Memora → Autonomous DB #1. IntelX + Futuris research → Autonomous DB #2, named "IntelX DB". Stratex research → MySQL HeatWave "FRIDAY Stratex Research". VyralX → FILES ONLY, no database. Cortex → Redis + files. FRIDAY / Sentinel / Forge → files. Inference → stateless.

## Servers swept (live)

| # | Server | Hostname | Disk | Workspace |
|---|---|---|---|---|
| 1 | Oracle Server 1 | friday-universe-vnic | 97G, 36% used | 12G |
| 2 | Oracle Server 2 | friday-universe-vnic-2 | 49G, 62% used | 4.5G |
| 3 | FRIDAY-Server | friday-server | 58G, 28% used | 4.9G |
| 4 | Stratex-Server | stratex-server | 58G, 34% used | 4.9G |
| 5 | VyralX-Server | ip-172-26-12-48 | 58G, 35% used | 8.1G |
| 6 | IntelX-Server | ip-172-26-4-138 | 58G, 13% used | 1.8G |

Live services found: S1 — Cortex, Forge, Memora, Sentinel active (Stratex-Daemon FAILED — sleeping backup, known; IntelX masked/failed — moved; caddy failed on S1). S2 — caddy + friday-bridge only. S3 — FRIDAY, FRIDAY-Voice, Inference active. S4 — Stratex + Stratex-Daemon active. S5 — VyralX active. S6 — Futuris + IntelX active.

## THE TABLE — every agent's storage and backup state, verified live

"Backup" means a backup that actually covers that leg. Fleet DB backup = `scripts/backup_fleet_databases.py` (TASK-INF-003 / SEN-009), out root `/var/backups/friday-universe`.

| Agent | Decided | Live storage (as found) | Live server | Path / DB name | Measured size | Backup state |
|---|---|---|---|---|---|---|
| FRIDAY | files | Oracle ADB FRIDAY schema (24 tables, 1,479 rows @ 2026-11-22) + local files on S3 | S3 (FRIDAY.service active) | ADB schema `FRIDAY`; `/opt/friday_universe/FRIDAY/data/` — `friday.db` 344K (mtime 2026-10-27, stale), `gemini_pool_state.json` (2026-11-24 21:18), `voice_worker_status.json` (2026-11-24 21:20), `state/proactive_intelx_watch.json` (2026-11-25 00:21 UTC); `memory/cold_storage/` empty | ADB rows 1,479; local files ~392K | **PARTIAL** — ADB schema in 2026-11-22 fleet backup (complete). Local files: NO current backup (`FRIDAY/backups/friday/` empty; `.backups` newest 2026-11-04) → follow-up DB-008 |
| Memora | Autonomous DB #1 | Oracle ADB MEMORA schema — 16 tables, 11,566 rows @ 2026-11-22: MEMORY_RECORDS 491, MEMORA_VECTOR_STORE 491, MEMORY_RELATIONSHIPS 2,110, AUDIT_LOGS 6,425, EVENT_LOG 1,203, DELETION_TOMBSTONES 323, AGENTS 10 (up from 436 records / 436 vectors / 1,527 relationships at the 2026-11-15 drill — live growth). Local `memora.db` ABSENT on S1 (only `memora.db-shm` 32K + `memora.db-wal` 0, Oct 23 remnants) | S1 (Memora.service active) | ADB schema `MEMORA` | 11,566 rows; backup dir 2.3M | **BACKED UP** — 2026-11-22 fleet backup, complete, verify 188 ok / 0 failed. No local store to back up |
| IntelX | Autonomous DB #2 ("IntelX DB") | LOCAL FILES (live writes) + ADB INTELX schema (20 tables, 971 rows @ 2026-11-22; recency not verifiable — manifest carries no timestamps). `intelx.db` ABSENT on S6 | S6 (IntelX.service active) | `/opt/friday_universe/IntelX/data/` — `watches/state.json` 1.3M (updated 2026-11-25 00:00 UTC), `raw/` 224K (newest 2026-11-24 21:13), `artifacts/` 4K; ADB schema `INTELX` | Local files ~1.5M; ADB rows 971 | **PARTIAL** — ADB schema in 2026-11-22 fleet backup. Local files: **NO BACKUP** (no `/var/backups` on S6, no backup paths) → follow-up DB-005. Disagreement D1 |
| Futuris | Autonomous DB #2 ("IntelX DB") | LOCAL FILES (live writes) + ADB FUTURIS schema (13 tables, 1,809 rows @ 2026-11-22; recency not verifiable) | S6 (Futuris.service active) | `/opt/friday_universe/Futuris/data/storage/` — 54M, 805 UUID subdirs, parquet snapshots, newest 2026-11-24 23:31–23:34 UTC; ADB schema `FUTURIS` | Local files 54M; ADB rows 1,809 | **PARTIAL** — ADB schema in 2026-11-22 fleet backup. Local files: **NO BACKUP** → follow-up DB-006. Disagreement D1 |
| Stratex | MySQL HeatWave "FRIDAY Stratex Research" | LOCAL STATE FILES (live daemon writes) + empty ADB schema. HeatWave `10.0.0.182:3306` REACHABLE from S1 and S2, NOT REACHABLE from S4 (TCP check this sweep). NO `stratex_research` / `10.0.0.182` / mysql string in the S4 Stratex code (only a test placeholder `mysql://user:pass@host/db`). ADB STRATEX schema: 4 tables, **0 rows** @ 2026-11-22 | S4 (Stratex + Stratex-Daemon active) | `/opt/friday_universe/Stratex/state/` — 884K: `equity_snapshots.jsonl` 338K (2026-11-25 00:02 UTC), `forward_scorecard.json` 254K (00:06 UTC), `fill_ledger.jsonl` 40K (2026-11-24 15:17), `position_tags.jsonl` 65K (16:00), `daemon_heartbeat.json` (00:17 UTC); `state/reconciliation/` daily_2026-11-23 + daily_2026-11-24 (both RECONCILED per STR-051) | State files ~884K; ADB rows 0 | **NO BACKUP** — newest state backup 2026-11-14 (`active_trades.json.bak`); Nov 2 snapshot; fleet backup's STRATEX dir holds only the 4 empty ADB tables (20K) → follow-up DB-004. Disagreement D2. Production-usage verification belongs to DB-001 (AVAILABLE) |
| Cortex | Redis + files | Redis `localhost:6379` UP (v6.0.16, uptime < 1 day) but **0 keys** in db 0, AOF off, no `dump.rdb` on disk (RDB `save` policy configured: 900 1 / 300 10 / 60 10000). Worker configured `REDIS_URL=redis://localhost:6379/0` + event stream (`cortex-worker-group`). Local `data/cortex.db` 372K SQLite (+32K shm). ADB CORTEX schema: 17 tables, **1 row** @ 2026-11-22 | S1 (Cortex.service active, API :8009) | Redis 127.0.0.1:6379; `/opt/friday_universe/Cortex/data/cortex.db`; ADB schema `CORTEX` | Redis 871.76K used, 0 keys; cortex.db 372K; ADB rows 1 | **PARTIAL** — ADB schema in 2026-11-22 fleet backup. `cortex.db`: **NO BACKUP**. Redis: unpersisted and currently empty → follow-up DB-010. Disagreement D5 |
| VyralX | FILES ONLY, no database | FILES (live) + ADB legs (VYRALX schema 10 tables/333 rows + VYRALX_MEDIA 1 table/36 rows @ 2026-11-22 — the media schema is a separate ADB the fleet script dumps from S2). No database wiring done or attempted here, per the owner decision | S5 (VyralX.service active) | `/opt/friday_universe/VyralX/` — `renders/` 221 files, 2.2G; `media/` 702 files, 3.9G; `data/` 403M (`exports/` 267M, 33 files; `bgm/` 135M, 26 files + `catalog.json`; `fonts/` 1.6M; manifests — see formalisation below) | File store 6.5G; ADB rows 333 + 36 | **PARTIAL** — ADB legs in 2026-11-22 fleet backups (S1 + S2 media job). 6.5G file store: **NO SCHEDULED BACKUP** — informal S1 mirror only (see below) → follow-up DB-007 |
| Sentinel | files | Local audit ledger file + ADB SENTINEL schema (15 tables, 17 rows @ 2026-11-22) | S1 (Sentinel.service active, API :8008) | `/opt/friday_universe/Sentinel/logs/audit.jsonl` — 27,617 bytes, 33 lines, newest 2026-11-24 13:34 IST (seq 33, TLS_CERT_ALERT); ADB schema `SENTINEL` | audit.jsonl 27K / 33 entries; ADB rows 17 | **PARTIAL** — ADB schema in 2026-11-22 fleet backup. `audit.jsonl`: **NO BACKUP** (not in the fleet script's file globs) → follow-up DB-009. Note D8: ledger file (33 entries) vs schema (17 rows) counts differ — cross-check owed |
| Forge | files | Local workspaces + ADB FORGE schema (7 tables, 4,506 rows @ 2026-11-22) | S1 (Forge.service active) | `/opt/friday_universe/Forge/` — `workspaces/` 27M, `app/` 7.2M; ADB schema `FORGE` | Workspaces 27M; ADB rows 4,506 | **PARTIAL** — ADB schema in 2026-11-22 fleet backup. Workspaces: **NO FILE BACKUP** → follow-up DB-011 |
| Inference | stateless | Oracle ADB INFERENCE schema (9 tables, 3,013 rows @ 2026-11-22). Local `universe.db` ABSENT on S3 (only `universe.db-shm` 32K + `universe.db-wal` 177K, Oct 23 remnants). Code: production backend is the Oracle ADB; `SQLiteMemory` is tests/local only | S3 (Inference.service active) | ADB schema `INFERENCE` | ADB rows 3,013; no local store | **BACKED UP** — 2026-11-22 fleet backup, complete. Disagreement D4: not stateless — it has a live ADB schema |
| Bridge | files | Code only, no state store; logs via journald | S2 (friday-bridge.service active) | `/opt/friday_universe/bridge/` — 204K (`server.py`, `extra_tools.py`, `auth.py`, rollback scripts) | 204K | **N/A** — no data store (code is in git) |

## VyralX file-store formalisation (verified live on VyralX-Server, S5)

- **Renders:** `/opt/friday_universe/VyralX/renders/` — **221 files, 2.2G**. Matches the 221 counted at the 2026-11-24 move exactly. (`data/renders/` is empty, 0 files — the live renders dir is the top-level one.)
- **Media:** `/opt/friday_universe/VyralX/media/` — **702 files, 3.9G**.
- **Data:** `/opt/friday_universe/VyralX/data/` — **403M, 79 files**: `exports/` 267M (33 files, `crosspost_*` dirs); `bgm/` 135M (26 files + `catalog.json`); `fonts/` 1.6M; `temp_thumbs/` 4K; `renders/` 4K (empty); manifests `audience_learning_state.json` (2026-11-21), `published_shorts_manifest.json` (2026-11-21), `rejected_sources.json` (2026-11-23), `viral_loop_manifest.jsonl` (2026-11-21), `viral_loop_state.json` (2026-11-21), `worker-heartbeat.json` (2026-11-17); `youtube_cookies.txt` (2026-11-24 17:59). `data/credentials/` and `data/secrets/` exist (permission-protected; contents NOT read).
- **Candidate-pool files:** no file under `VyralX/` is named `*candidate*`, `*pool*` or `*metric*` (searched whole tree). The pool state is the manifests above (`viral_loop_manifest.jsonl`, `viral_loop_state.json`, `published_shorts_manifest.json`, `rejected_sources.json`); the candidate logic is code (`scripts/render_master_candidate.py`, `find_viral_candidates*.py`, `inspect_candidates.py`).
- **Metrics-sync outputs:** `vyralx-metrics-sync.timer` active, ~4h cadence (last run 2026-11-24 20:35 UTC, next 2026-11-25 00:35 UTC); runs `scripts/sync_youtube_metrics.py`. No separate metrics output files exist — the sync writes back into the manifests above (newest Nov 21–23).
- **BGM shelf:** `/opt/friday_universe/VyralX/data/bgm/` — **26 files, 135M, + `catalog.json`** — on **VyralX-Server (S5)**, not on Oracle Server 2. The task text's "(shelf lives on Oracle Server 2)" is stale: the shelf moved with VyralX on 2026-11-24. `VyralX/docs/BGM_SHELF.md` (TASK-VYR-030, 2026-11-21) records the shelf at the same path on "U2" with 25 tracks / 5 phonk; live count is 26. A full S2 search (`/opt/friday_universe`, `/home/ubuntu`, `/var`, depth 4) found NO BGM files on S2. Disagreement D3.
- **Backup state (plain):** the 6.5G file store has NO scheduled backup. Oracle Server 1 holds an informal mirror: `VyralX/` 6.5G with identical counts (media 702, renders 221, data 79 files) and identical sizes, and one render file md5-identical on both hosts (`framed--bh5VGbrbLI-5970f1.mp4`, md5 `45344906704ad255c0570c5af8b42c7c`, 15,474,023 bytes, Nov 18 23:46). No rsync/sync timer or cron job maintains it on either host (full timer lists + root/ubuntu crontabs checked on S1 and S5 — both empty of backup entries). Treat the S1 copy as an unverified second copy, not a backup. Follow-up DB-007.
- **VyralX has NO database** by the owner decision 2026-11-25 ~02:59 IST — confirmed: no VyralX database wiring was touched; the VYRALX / VYRALX_MEDIA ADB schemas dumped by the fleet script are pre-existing legs, not a VyralX database.

## Autonomous DB #2 display name — as found live

**Not evidenced on any box: the display name "IntelX DB" does not appear in any live source checked.** Searched IntelX + Futuris code/config/docs on S6 and Memora on S2 for `IntelX DB` / `INTELX_DB` (nothing) and for the old local name `intelx.db` (only historical doc references). The OCI CLI is not installed on any server checked (S2, S6), so no live OCI listing was possible. The fleet backup manifest redacts DSNs (schema name + "from `<AGENT>_DATABASE_URL` in env file" only). What IS live: the Nov 22 fleet backup dumped the INTELX (20 tables / 971 rows) and FUTURIS (13 tables / 1,809 rows) schemas successfully, complete, verify 188 ok / 0 failed — the database exists and is reachable from S1. The rename itself belongs to TASK-DB-002 (AVAILABLE, unclaimed). Conclusion: **rename still pending; "IntelX DB" is the decided name, not a live-verified display name.**

## Fleet backup — the one backup that does run

- Script `scripts/backup_fleet_databases.py` (TASK-INF-003 / SEN-009): logical JSONL dump per table + manifest (row counts + SHA-256) + config snapshot, out root `/var/backups/friday-universe`. Per-agent schemas: FRIDAY, INFERENCE, MEMORA, STRATEX, FUTURIS, INTELX, FORGE, SENTINEL, CORTEX, VYRALX; media schema VYRALX_MEDIA dumped by the S2 job (media credentials live on S2).
- Runs found: S1 — 20261116T062553Z, 20261118T173701Z, **20261122T171929Z** (13M total; newest manifest 2026-11-22T11:49:29Z, `complete: true`, verify ok 188 / failed 0). S2 — 20261116T062536Z, 20261118T173646Z, **20261122T171923Z** (452K total, media only; newest manifest 2026-11-22T11:49:23Z, `complete: true`, verify ok 27 / failed 0).
- **No schedule:** no systemd timer and no cron entry runs this backup on any server (full timer lists on S1/S2/S5; root + ubuntu crontabs empty on S1/S5). The three runs are manual/triggered, ~2–4 days apart. Newest run is 3 days old at sweep time.
- Per-agent backup sizes (2026-11-22, S1): MEMORA 2.3M, FUTURIS 540K, INTELX 180K, FORGE 172K, FRIDAY 144K, INFERENCE 120K, CORTEX 72K, SENTINEL 64K, VYRALX 60K, STRATEX 20K, configs 932K. S2 media job: VYRALX_MEDIA 12K, configs 136K.
- Older file backups are all stale: `.backups` newest 2026-11-04 (dashboard snapshot), `.deploy-backups` newest 2026-10-31, `Stratex/backups` newest 2026-11-02, `FRIDAY/backups` empty, `data/backups` (S2) empty. The fleet DB backup is the only current backup mechanism, and it covers ADB schemas only — not local files (except the script's Stratex-state glob, which in the Nov 22 run captured nothing: the STRATEX dir holds only the 4 empty-table dumps, and the script runs on S1 where `Stratex/state/` is the sleeper copy).

## Disagreements with the decided arrangement (recorded, not fixed — coordinator rules)

- **D1 — IntelX + Futuris research is NOT in Autonomous DB #2 yet.** Live writes go to local files on IntelX-Server (S6): IntelX `watches/state.json` (updated 2026-11-25 00:00 UTC), Futuris parquet snapshots (newest 2026-11-24 23:34 UTC). The ADB INTELX/FUTURIS schemas hold rows as of Nov 22, but recency cannot be verified from the manifest (no timestamps) and the live write path is files. Wiring belongs to TASK-DB-002 (AVAILABLE).
- **D2 — Stratex research is NOT in HeatWave from the live host.** No HeatWave reference in the S4 daemon code; `10.0.0.182:3306` unreachable from S4 (reachable from S1/S2); the ADB STRATEX schema is empty (4 tables, 0 rows). Live Stratex state is local JSONL on S4. Production-usage proof belongs to TASK-DB-001 (AVAILABLE).
- **D3 — BGM shelf is on VyralX-Server (S5), not Oracle Server 2.** Task text is stale (pre-2026-11-24 move). No BGM files exist on S2.
- **D4 — Inference is NOT stateless.** It has a live ADB INFERENCE schema (9 tables, 3,013 rows @ Nov 22). The local SQLite is a dead remnant (no `universe.db` file; shm/wal only, Oct 23).
- **D5 — Cortex Redis is empty and unpersisted.** 0 keys, AOF off, no `dump.rdb` on disk; uptime < 1 day (restarted recently). The durable Cortex leg today is local `cortex.db` (372K).
- **D6 — Memora's local SQLite is gone; the ADB is the store.** `memora.db` absent on S1 (shm/wal remnants only, Oct 23). Matches the decided arrangement (ADB #1) — recorded for completeness, not a disagreement.
- **D7 — FRIDAY's local `friday.db` is stale (mtime 2026-10-27).** Live FRIDAY state is the ADB schema + current JSON state files.
- **D8 — Sentinel ledger: file vs schema count mismatch.** Local `audit.jsonl` holds 33 entries (newest seq 33, Nov 24 13:34 IST); the ADB SENTINEL schema holds 17 rows @ Nov 22. Whether the API-served ledger and the file are the same store needs a cross-check (verifier).
- **D9 — S2's big FRIDAY/Memora dirs are CI venvs, not data.** S2 `FRIDAY/` 723M = `.venv-friday-ci` 690M; `Memora/` 271M = `.venv-memora-ci` 261M. Real data there is ~92K (`.data`) / ~548K (`storage/`).
- **Layout note (not a disagreement):** the 6/4 migration layout in REL-062 is stale — IntelX + Futuris now run live on IntelX-Server (S6), not S2; S2 runs only caddy + bridge plus checkouts. FRIDAY runs live on FRIDAY-Server (S3); Memora/Sentinel/Forge/Cortex run live on S1; Stratex runs live on S4; VyralX on S5.

## Follow-up tasks filed (filing only — no backups built in this task)

| ID | Store with NO backup | Title |
|---|---|---|
| TASK-DB-004 | Stratex live state files (S4) | DB: Back up Stratex live state files on Stratex-Server — newest state backup 2026-11-14 |
| TASK-DB-005 | IntelX local research files (S6) | DB: Back up IntelX local research files on IntelX-Server — watches + raw, no backup |
| TASK-DB-006 | Futuris local forecast files (S6) | DB: Back up Futuris local forecast files on IntelX-Server — data/storage parquet, no backup |
| TASK-DB-007 | VyralX file store (S5, 6.5G) | DB: Formalise VyralX file-store backup on VyralX-Server — only an informal S1 mirror |
| TASK-DB-008 | FRIDAY local state files (S3) | DB: Back up FRIDAY local state files on FRIDAY-Server — friday.db + JSON state |
| TASK-DB-009 | Sentinel local audit ledger (S1) | DB: Back up Sentinel local audit ledger on Oracle Server 1 — audit.jsonl, 33 entries |
| TASK-DB-010 | Cortex local store (S1) | DB: Back up Cortex local store on Oracle Server 1 — cortex.db + settle Redis persistence |
| TASK-DB-011 | Forge workspaces (S1, 27M) | DB: Back up Forge workspaces on Oracle Server 1 — 27M working output, no file backup |

All eight filed as AVAILABLE / P2 board records in this PR (next free DB ids; DB-001/002/003 already exist). Each carries the audit doc as its source.

## What this audit could NOT verify (limits, stated plainly)

- Autonomous DB display names ("IntelX DB" and DB #1's name): no OCI CLI on any box, no on-box source names them. Only the schema names (MEMORA, INTELX, FUTURIS, …) as dumped are verified.
- Per-table recency of the ADB rows: the Nov 22 manifest carries row counts but no per-table timestamps; INTELX/FUTURIS row currency is DB-002's live probe, STRATEX HeatWave usage is DB-001's.
- Redis contents before its recent restart: 0 keys now; whether a stream existed before the restart is unknowable from the box.
- Whether the Sentinel API-served ledger and `audit.jsonl` are the same store (D8).
- The S1 VyralX mirror's sync date: counts/sizes identical and 1 file md5-identical, but no sync job exists to date it; a full-tree hash comparison was not run (6.5G).

## Verdict

Table filed via PR; every row verified live on its box in the single dated sweep above. **Spot-verification owed:** coordinator or paired verifier re-reads at least 3 rows against the live boxes and confirms they match. Eight unbacked stores flagged in the table, eight follow-up tasks filed. No production changes made; no backups built in this task.

— Muse 13
