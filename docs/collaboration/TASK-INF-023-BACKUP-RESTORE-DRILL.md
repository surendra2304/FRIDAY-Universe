# TASK-INF-023 — Restore-drill evidence for TASK-SEN-009 (2026-11-22 backup chain)

**Task:** TASK-INF-023 (pool 10, P2; coordinator full assignment round, issue #35 comment 7084017188, 2026-11-23 ~00:29 IST). Parallel task: SEN-022 stays the open assignment, HELD on REL-070 — untouched by this drill (PR #1378 not touched).
**Drill date:** 2026-11-23, run by Muse 1. **Board:** CLAIMED → IN_REVIEW with this PR. **Work PR:** #1409 (head a262afb4, base main 434eff03).
**Outcome in one line:** Newest scheduled backup chain (2026-11-22, run 45019170405, event=schedule, success) verified end-to-end — all 136 table files hash- and row-count-clean, Phase A verify-only passes for all 10 agents + media (107 match / 28 differ, all live greater than backup, zero negative deltas, zero missing, zero extra), and all 23,731 rows loaded into scratch databases with counts equal to the manifests; no live database or config was written to.

## 1. Backup chain used (newest)

| Backup | Location | Created (UTC) | Manifest | Config files |
|---|---|---|---|---|
| Fleet (10 agents) | Server 1 `/var/backups/friday-universe/20261122T171929Z` | 2026-11-22T11:49:29Z | `complete: true`, `failed_agents: []` | 44 configs + 9 agent-env files |
| Media (VYRALX_MEDIA) | Server 2 `/var/backups/friday-universe/20261122T171923Z` | 2026-11-22T11:49:23Z | `complete: true`, `failed_agents: []` | 23 configs |

Produced by the scheduled Fleet Backup workflow run 45019170405 (created 2026-11-22T11:49:09Z, event `schedule`, conclusion `success`; head cde19595). Directory stamps are IST-based (`171929Z` = 17:19:29 IST = 11:49:29 UTC) — see observation O1. Older chain members on each server: `20261118T173701Z` (Server 1, drilled by INF-020) / `20261118T173646Z` (Server 2). Per-agent rows in the Server 1 manifest: FRIDAY 1,479 (24 tables), INFERENCE 3,013 (9), MEMORA 11,566 (16), STRATEX 0 (4), FUTURIS 1,809 (13), INTELX 971 (20), FORGE 4,506 (7), SENTINEL 17 (15), CORTEX 1 (17), VYRALX 333 (10) — 23,695 rows, 135 tables. Media manifest: VYRALX_MEDIA 36 rows, 1 table (`MEDIA_FILES`). Grand total 23,731 rows, 136 table files.

## 2. What was run (commands, paths, timestamps)

All drill commands ran from the server that hosts the backup (`/opt/friday_universe` checkout, venv python), driven read-only through the bridge MCP `run_shell` tool. Times in IST (UTC+5:30) unless marked Z.

**Step 0 — Research + manifest read** (2026-11-23 00:37–00:40 IST / 2026-11-22T19:07–19:10Z). Sources: runbook `docs/observability/RESTORE_DRILL_RUNBOOK.md`, repair doc `docs/observability/BACKUP_REPAIR_SEN009.md`, prior drill `docs/collaboration/TASK-INF-020-RESTORE-DRILL.md`, `scripts/backup_fleet_databases.py`, `scripts/restore_fleet_database.py`, `scripts/check_backup_freshness.py`, both backup workflows, `tests/test_backup_sen009.py`, SEN-022 work dir `~/workspace/sen-022/ref/` (backup skill + ref files, read-only). Newest manifests read with a compact summary extractor (full manifests not printed): S1 `complete: true`, `failed_agents: []`, `verify: {ok: 188, failed: 0}`; S2 media `complete: true`, `failed_agents: []`, `verify: {ok: 27, failed: 0}`.

**Step 1 — Independent integrity re-check of the backup files** (2026-11-23 00:41 IST / 19:11:15–19:11:18Z). For every table file in each manifest: recomputed SHA-256 and compared it to the manifest's `sha256`, gunzipped and counted lines, compared the count to the manifest's `row_count`.
- Server 1: 135/135 files, SHA-256 match, gzip-readable, line counts == manifest row_counts. 23,695 rows. **Mismatches: none.**
- Server 2 (media): 1/1 file, SHA-256 match, 36 rows. **Mismatches: none.**
- First attempt without `sudo` failed `PermissionError` (backup dirs are mode 700, root-owned); retried with `sudo` per the runbook. No data changed.

**Step 2 — Backup tool's own `--verify` + freshness** (00:41–00:42 IST).
- Server 1, 19:11:29Z: `sudo /opt/friday_universe/venv/bin/python scripts/backup_fleet_databases.py --verify --from-dir /var/backups/friday-universe/20261122T171929Z` → `[VERIFY] 188 files OK, 0 failed`, exit 0.
- Server 2, 19:11:37Z: same command with `--from-dir /var/backups/friday-universe/20261122T171923Z` → `[VERIFY] 27 files OK, 0 failed`, exit 0.
- Freshness, Server 1, 19:11:40Z: `scripts/check_backup_freshness.py --json` → `status: "ok"`, `last_success_at: 2026-11-22T11:49:29Z`, `age_hours: 7.37`, `complete_backups: 3`, `max_age_hours: 120.0`, exit 0.

**Step 3 — Phase A verify-only drill** (runbook Phase A, read-only: compares live row counts against the manifest; no writes). The runbook's `--from-dir` flag does not exist on the restore tool — the working flag is `--backup-dir` (gap G1, unchanged). Commands were run in the background and polled because the bridge MCP layer drops calls longer than ~45 s. A small wrapper ran the tool's own `compare_to_live` per agent and saved the full JSON report (the tool's own `main()` truncates its printed report to 4000 chars — gap G11).
- Server 1, 19:11:51–19:11:58Z (7 s): `sudo /opt/friday_universe/venv/bin/python /tmp/inf023_phasea.py /var/backups/friday-universe/20261122T171929Z FRIDAY,INFERENCE,MEMORA,STRATEX,FUTURIS,INTELX,FORGE,SENTINEL,CORTEX,VYRALX /tmp/inf023_phaseA_s1.json`
- Server 2, 19:11:58–19:12:01Z (3 s): same wrapper, `--backup-dir /var/backups/friday-universe/20261122T171923Z VYRALX_MEDIA`

**Step 4 — Scratch load test** (restore-to-scratch, safe form). The restore tool's own row reader (`scripts/restore_fleet_database.py`, `iter_backup_rows`) decoded every backup file and loaded the rows into a scratch SQLite database in `/tmp`, verifying the loaded count per table against the manifest. This proves the backup bytes decode and load; it is not an Oracle load (see gap G8 — the Oracle `--apply` path needs the gated scratch user).
- Server 1, ~19:14 IST: `/tmp/muse1_inf023_scratch.db` — 135/135 tables, 23,695/23,695 rows, counts equal to manifest for every table. **Problems: none.** Scratch DB 19,525,632 bytes, deleted afterwards.
- Server 2, ~19:14 IST: `/tmp/muse1_inf023_scratch_media.db` — `VYRALX_MEDIA/MEDIA_FILES` 36/36 rows. Scratch DB 20,480 bytes, deleted afterwards.
- Teardown verified on both servers: no `/tmp/muse1_inf023_*` or `/tmp/inf023_*` files remain (checked 19:17:40–19:17:43Z).

**Step 5 — Deployed-script parity** (19:15:02–19:17:43Z). SHA-256 of the three drill/backup scripts on each server vs the main blobs (base 0d79ec82): identical on both servers — `restore_fleet_database.py e084896b63d57863d86197f615b3ba677190b32a5446b3fd527b7eebad752b1b`, `backup_fleet_databases.py ca62cef47d8bae5f25b984d6dfec934471ced6e8d24ad3c5276db083a264b616`, `check_backup_freshness.py 9eb9e12de4ba2748a48503b2991eec8b4d2408f84a6059859bb80f8a674afedc`. Server 1 checkout: `main` @ 0d79ec82 (== drill base, == main). Server 2 checkout: branch `muse10/task-inf-020-restore-drill` @ db933cfc (Muse 10's INF-020 branch — stale, same observation as INF-020; the scripts themselves match main today — gap G10).

**Not run:** no `--apply`, no `--replace`, no `--yes-i-understand`, no service stop/restart, no live writes of any kind. No live database or config was overwritten (acceptance 3).

## 3. Phase A results (per agent)

`match` = live rows == backup rows; `differ` = live rows != backup rows (all differ here are live **greater** than backup — the fleet kept writing in the ~7.4 h between the 11:49Z backup and the 19:11Z drill, i.e. the runbook's expected DRIFT); `missing` = backup table absent from live schema; `extra` = live table not in backup.

| Agent | match | differ | missing | extra |
|---|---:|---:|---:|---:|
| FRIDAY | 21 | 3 | 0 | 0 |
| INFERENCE | 5 | 4 | 0 | 0 |
| MEMORA | 9 | 7 | 0 | 0 |
| STRATEX | 4 | 0 | 0 | 0 |
| FUTURIS | 8 | 5 | 0 | 0 |
| INTELX | 12 | 8 | 0 | 0 |
| FORGE | 7 | 0 | 0 | 0 |
| SENTINEL | 14 | 1 | 0 | 0 |
| CORTEX | 17 | 0 | 0 | 0 |
| VYRALX | 10 | 0 | 0 | 0 |
| VYRALX_MEDIA (Server 2) | 1 | 0 | 0 | 0 |
| **Total** | **108** | **28** | **0** | **0** |

Differ details (backup → live, all positive):
- FRIDAY: CONVERSATION_HISTORY 359→368 (+9), MEMORA_RECORDS 307→311 (+4), MESSAGES 807→813 (+6).
- INFERENCE: MEMORIES 255→259 (+4), MESSAGES 1031→1047 (+16), RUNS 1442→1458 (+16), TASKS 276→280 (+4).
- MEMORA: AUDIT_LOGS 6425→6458 (+33), DELETION_TOMBSTONES 323→327 (+4), EVENT_LOG 1203→1213 (+10), MEMORA_VECTOR_STORE 491→493 (+2), MEMORY_RECORDS 491→493 (+2), MEMORY_SHARED_AGENTS 3→13 (+10), `VECTOR$MEMORA_VECTOR_STORE_IDX$154120_154126_0$HNSW_SHARED_JOURNAL_CHANGE_LOG` 10→20 (+10).
- FUTURIS: EVIDENCE_REFS 331→385 (+54), FORECASTS 428→494 (+66), FORECAST_EVENTS 733→868 (+135), FORECAST_SCORES 152→166 (+14), OUTCOMES 153→174 (+21).
- INTELX: CHUNKS 554→676 (+122), CLAIMS 126→170 (+44), DOCUMENTS 51→64 (+13), EVIDENCE 126→170 (+44), FINDINGS 14→17 (+3), LIVE_RESEARCH_RUNS 25→28 (+3), RESEARCH_RUNS 16→19 (+3), SOURCES 51→64 (+13).
- SENTINEL: SENTINEL_EVENTS 12→13 (+1).
- Zero negative deltas anywhere: no live table holds fewer rows than the backup, so nothing was lost between backup and drill. Zero missing, zero extra — the INF-020 MEMORA `VECTOR$…ROWID_VID_MAP` missing+extra pair is gone: the 2026-11-22 backup holds the `…_289$` variant live holds (481 rows in the backup).

Tool verdicts: Server 1 run printed `[DRILL] ISSUES FOUND at 2026-11-22T19:11:58Z` (exit 1) — this is gap G6, not a drill failure: the tool exits 1 on any drift, and drift is the expected outcome. Server 2 media run printed `[DRILL] OK at 2026-11-22T19:12:01Z` (exit 0).

Change since INF-020 (2026-11-18 chain): FUTURIS backup rows 44 → 1,809 and INTELX 971 rows now 12 match / 8 differ (was 20/0) — four days of live forecasting and research activity, not a defect. MEMORA 11,420 → 11,566 rows.

## 4. Gaps found (with file/line)

Gaps G1–G9 were filed by INF-020; G1–G3, G5–G6 are **still present on main** (verified against the main blobs at base 0d79ec82 this run). G7's symptom is gone; G8 is still blocked. New gaps G10–G11 from this drill.

- **G1 — Runbook commands use a flag the tool does not have (STILL PRESENT).** `docs/observability/RESTORE_DRILL_RUNBOOK.md:26`, `:30`, `:44`, `:66–67` use `--from-dir` for `scripts/restore_fleet_database.py`. The tool's argparse has no `--from-dir`; the working flag is `--backup-dir` (`scripts/restore_fleet_database.py:198`). Copy-pasting the runbook's Phase A/B commands fails with an argparse error. (`--from-dir` exists only on the *backup* tool, `scripts/backup_fleet_databases.py:465`, for `--verify`.)
- **G2 — Runbook uses a `--media` flag the restore tool does not have (STILL PRESENT).** `docs/observability/RESTORE_DRILL_RUNBOOK.md:30`. The restore tool has no `--media` argument; the media schema is addressed as agent `VYRALX_MEDIA` (`scripts/restore_fleet_database.py:46`, `AGENT_ENV_DIRS`).
- **G3 — Runbook's expected output vocabulary does not exist in the tool (STILL PRESENT).** `docs/observability/RESTORE_DRILL_RUNBOOK.md:5` and `:33` say the tool prints `LOADABLE / REFUSED / MISSING / DRIFT` per table and "every table reports DRIFT or LOADABLE". The tool's verify-only mode prints `match / differ / missing_in_live / extra_in_live` (`scripts/restore_fleet_database.py`, `compare_to_live`). A driller following the runbook cannot map the expected outcome to real output.
- **G4 — Runbook cites a companion doc at the wrong path (STILL PRESENT).** `docs/observability/RESTORE_DRILL_RUNBOOK.md:7` cites `docs/runbooks/BACKUP_RESTORE_AND_LEDGER_DRILL.md`; the file lives at `docs/observability/BACKUP_RESTORE_AND_LEDGER_DRILL.md`.
- **G5 — Restore tool docstring cites a runbook that does not exist (STILL PRESENT).** `scripts/restore_fleet_database.py:21`: `Runbook: docs/observability/BACKUP_RESTORE_DRILL.md`. No such file; the runbook is `docs/observability/RESTORE_DRILL_RUNBOOK.md`.
- **G6 — Drill exit code contradicts the runbook's expected outcome (STILL PRESENT, observed this run).** `scripts/restore_fleet_database.py:227`, `:231`, `:235–236`: `overall_ok` is set False on any differing or missing table, so a drill with only expected positive drift prints `[DRILL] ISSUES FOUND` and exits 1. A clean drill looks like a failure, and automation cannot distinguish drift from real breakage. Fix: treat all-positive drift as OK (or add a `--expect-drift` mode), and reserve exit 1 for negative deltas / missing user tables.
- **G7 — Backup dumps Oracle-internal VECTOR$ index tables that cannot be restored as-is (DESIGN UNCHANGED, symptom absent this run).** `scripts/backup_fleet_databases.py:276` (`tables = list_tables(conn)`, unfiltered) and `scripts/oracle_db.py:257–268` (`list_tables` selects every row of `all_tables`, no exclusion). The 2026-11-22 backup still contains the `VECTOR$MEMORA_VECTOR_STORE_IDX$…` internal tables (e.g. `…_289$HNSW_ROWID_VID_MAP`, 481 rows), but this run shows 0 missing / 0 extra — the live index was not rebuilt between backup and drill, so the stale-index symptom INF-020 saw did not recur. The design question stands: exclude `VECTOR$*` internal tables from backups (they are rebuilt with the index), or document them as unrestorable by design.
- **G8 — BLOCKED, not a defect: Phase B1 (real Oracle load into an empty target) was not run.** The runbook's Phase B1/B2 needs a scratch ADB user (`SEN009_DRILL`), which needs ADMIN credentials from the dossier plus the coordinator's go-ahead recorded on the board entry (`docs/observability/RESTORE_DRILL_RUNBOOK.md`, Phase B2). No go-ahead exists for this task (the TASK-SEN-009 board entry records none), so no scratch user was created and no Oracle `--apply` was attempted. The scratch SQLite load in §2 step 4 proves the backup bytes decode and load, but does **not** prove the Oracle INSERT path (`insert_table`, `scripts/restore_fleet_database.py`) end-to-end. Follow-up: coordinator authorises the B2 gate, then a B1 drill loads FORGE (7 tables, 4,506 rows) into the scratch user and verifies post-load counts equal the manifest. (INF-020 filed this as pool-7 item INF-022; INF-022 is now a different task — routing receipts — so the B1 follow-up needs re-filing if still wanted.)
- **G9 — Resolved, no action:** INF-020's G9 (whether SENTINEL/CORTEX/VYRALX credentials resolve from a Server-1-only run) is confirmed again by this drill: the 2026-11-22 backup is `complete: true`, `failed_agents: []`, and Phase A connected successfully for all 10 agents from Server 1.
- **G10 — NEW: Server 2's fleet checkout is still on a stale worker branch.** Server 2 `/opt/friday_universe` is on branch `muse10/task-inf-020-restore-drill` @ db933cfc (Muse 10's INF-020 branch, 2026-11-22), not main — the same state INF-020 reported. The three backup/restore scripts happen to be byte-identical to main today (verified §2 step 5), so this drill is unaffected, but any future script change deployed to main will silently not reach Server 2's media backups until the checkout is moved. Fix: move the Server 2 checkout to main (Fleet CD) and record it; or document the branch as intentional.
- **G11 — NEW: the restore tool truncates its own full report.** `scripts/restore_fleet_database.py:234` prints `json.dumps(report, indent=2)[:4000]` — for a 10-agent run the per-table detail is cut mid-report (this run's printed JSON ended inside CORTEX). A driller who needs the exact per-table backup→live numbers must re-run the comparison or wrap `compare_to_live` directly (as this drill did). Fix: write the full report to a file, or print it untruncated behind a `--full-report` flag.

**Observation O1 (not a gap):** backup directory stamps are IST-based (`20261122T171929Z` = 17:19:29 IST = 11:49:29 UTC) while `manifest.created_at` is UTC. A driller correlating directory names to UTC workflow-run times will be off by 5.5 h unless they know the convention; worth one line in the runbook.

## 5. What this drill deliberately did not do (per runbook)

- No restore over live data (that is a recovery, not a drill); no `--replace`.
- No offsite-artifact decrypt-and-verify (`BACKUP_REPAIR_SEN009.md` §6; needs `BACKUP_ARTIFACT_PASSPHRASE`, which does not exist yet — the TASK-SEN-009 board entry still lists it as a blocker).
- No Phase B3 production-shaped drill (maintenance window, coordinator-gated).
- No Phase B1 Oracle load (gap G8 — coordinator-gated scratch-user gate).

## 6. Environment notes

- Server 1 checkout on `main` @ 0d79ec82 (== drill base, == main at drill time); the three drill/backup scripts there are byte-identical to the main blobs. Server 2 checkout on `muse10/task-inf-020-restore-drill` @ db933cfc, scripts byte-identical to main (gap G10).
- The bridge MCP layer drops `run_shell` calls longer than ~45 s; long drill commands were launched in the background and polled (INF-020's pattern). One parity call took 19:15:02→19:17:18Z because `git status` on the Server 1 checkout is slow through the bridge; nothing failed.
- Drill tooling (integrity checker, Phase A wrapper, scratch loader, bridge driver) lives in the worker's scratch dir `~/workspace/inf-023/` (run notes + per-step logs); the repo deliverable is this doc + the board record. The Phase A wrapper only calls the restore tool's own `compare_to_live` (read-only `SELECT COUNT(*)`); the scratch loader only calls the restore tool's own `iter_backup_rows`.
- Weekly usage at claim: 20% of the free weekly limit (reset Nov 28 21:57 IST).

— Muse 1, 2026-11-23
