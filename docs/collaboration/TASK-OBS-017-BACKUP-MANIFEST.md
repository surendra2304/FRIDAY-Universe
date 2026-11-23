# TASK-OBS-017 — Next SEN-009 scheduled backup manifest, verified live

**Task:** Sentinel: verify the next SEN-009 scheduled backup manifest completeness, live.
**Worker:** Muse 10 · **Date:** 2026-11-23 ~17:30–18:00 IST · **Branch:** muse10/task-obs-017-backup-manifest
**Claim:** issue #1483 comment 7100363173; claim PR #1497 (board-only).
**Method:** GitHub REST API via the PAT helper (workflow runs, jobs, check-runs) + FRIDAY bridge
`run_shell` read-only probes on Oracle Server 1 and Server 2 (manifest JSON summarized on-server
with Python; no secret values read, printed, or stored). No live data changed.

## Verdict: COMPLETE — acceptance met

The next scheduled backup after the 2026-11-18 first success — the Sunday 2026-11-22 slot,
GitHub Actions run **45019170405** (`event: schedule`) — produced a **complete manifest on both
servers**: Server 1 `complete=true` (10/10 schemas, 135 tables, 23,695 rows, 0 failed) and
Server 2 media `complete=true` (VYRALX_MEDIA, 1 table, 36 rows, 0 failed). Manifest completeness
is recorded in the backup success criteria: §7 "maintained end-state" table of
`docs/observability/BACKUP_REPAIR_SEN009.md` (verification row added by this task).

## Evidence

### Workflow run 45019170405 (GitHub API, live)

- Created 2026-11-22T11:49:09Z, `event: schedule`, `status: completed`, `conclusion: success`.
- Job 137198030206 "Backup fleet databases on Server 1": success, 11:49:11Z → 11:50:55Z.
- Job 137198030299 "Backup VyralX media schema on Server 2": success, 11:49:11Z → 11:49:29Z.
- Offsite artifact uploaded by the Server 1 job: `fleet-backup-offsite.zip`, artifact ID
  14753072171, 3,344,643 bytes (run log, 11:50:52–11:50:53Z). The SEN-009 G3 blocker
  (missing `BACKUP_ARTIFACT_PASSPHRASE` secret) is evidently resolved — the encrypted offsite
  copy now uploads. No `[BACKUP-ALERT]` issue was opened for this run.

### Server 1 manifest — `/var/backups/friday-universe/20261122T171929Z/manifest.json` (read live)

- `created_at` 2026-11-22T11:49:29Z · `task` TASK-INF-003 · **`complete: true`** · `failed_agents: []`
- `verify`: `ok` 188, `failed` 0, `verified_at` 2026-11-22T11:50:35Z.
  Arithmetic checks: 135 table files + 44 config files + 9 agent env snapshots = 188. ✓
- Agents (10/10 schemas, 135 tables, 23,695 rows):

| Agent/schema | Tables | Rows | Dumped at (UTC) |
|---|---|---|---|
| FRIDAY | 24 | 1,479 | 11:49:42Z |
| INFERENCE | 9 | 3,013 | 11:49:55Z |
| MEMORA | 16 | 11,566 | 11:50:11Z |
| STRATEX | 4 | 0 | 11:50:14Z |
| FUTURIS | 13 | 1,809 | 11:50:16Z |
| INTELX | 20 | 971 | 11:50:19Z |
| FORGE | 7 | 4,506 | 11:50:31Z |
| SENTINEL | 15 | 17 | 11:50:32Z |
| CORTEX | 17 | 1 | 11:50:32Z |
| VYRALX | 10 | 333 | 11:50:34Z |

- `configs`: 44 files (credential file, systemd units, other service configs).
- `agent_envs`: 9 per-agent env snapshots (all Server-1-resident agent env files).
  CORTEX has no env file on Server 1 (its env lives on Server 2 — see the Server 2 manifest,
  which snapshots it); this is coverage, not a gap.

### Server 2 media manifest — `/var/backups/friday-universe/20261122T171923Z/manifest.json` (read live)

- `created_at` 2026-11-22T11:49:23Z · `task` TASK-INF-003 · **`complete: true`** · `failed_agents: []`
- `verify`: `ok` 27, `failed` 0, `verified_at` 2026-11-22T11:49:28Z.
  Arithmetic checks: 1 table file + 21 config files + 5 agent env snapshots = 27. ✓
- Agents: VYRALX_MEDIA only — 1 table, 36 rows, dumped 11:49:28Z (the `--media-only` job).
- `agent_envs`: 5 snapshots, including the Server-2-resident Cortex env. Together with the
  Server 1 run, every agent env file on the fleet is snapshotted in this backup round.
- `configs`: 21 files.

### Freshness (standing proof mechanism, run live 2026-11-23 ~17:33 IST)

- `scripts/check_backup_freshness.py`: `status=ok`, `last_success_at` 2026-11-22T11:49:29Z,
  `age_hours` 24.22, `latest_attempt_complete: true`, `complete_backups: 3` (retention `--keep 4`
  counts complete backups; 3 complete backups on disk: 2026-11-16, 2026-11-18, 2026-11-22).
- Server 1 backup dirs on disk: 20261122T171929Z, 20261118T173701Z, 20261116T062553Z.
  Server 2: 20261122T171923Z, 20261118T173646Z, 20261116T062536Z.

## Gaps / observations filed

- **G1 (cosmetic): backup directory stamp is server-local time mislabeled `Z`.** The Server 1
  directory is named `20261122T171929Z` (17:19:29, server-local IST) while the manifest inside
  records `created_at` 2026-11-22T11:49:29Z (UTC) — the two disagree by exactly the +5:30
  offset. Same on Server 2 (`20261122T171923Z` vs `11:49:23Z`). Harmless for retention and
  freshness (both read the manifest), but the `Z` suffix is wrong and confuses run-to-directory
  matching. Fix: stamp directory names in UTC in `scripts/backup_fleet_databases.py`.
- **G2 (observation): scheduled run fired ~8h late.** The Sunday slot is 03:30 UTC; run
  45019170405 was created 11:49:09Z and both jobs still succeeded. GitHub schedule delay, not
  a backup defect; the 120 h watchdog threshold is unaffected. No action unless it recurs.
- **Observation (not this task): Server 2 checkout is stale.** `get_system_info` this run shows
  the Server 2 checkout still on `muse10/task-fut-022-401-storm` (da4541b4), not main. The
  media job still produced a complete manifest, so this did not affect the backup; bringing S2
  onto main is TASK-OBS-020's scope.
- **Closed by this evidence — SEN-009 §8 open item.** SENTINEL/CORTEX/VYRALX credential
  resolution from a Server-1-only run: all three schemas dumped with 0 failed in this round
  (SENTINEL 15 tables, CORTEX 17, VYRALX 10 on Server 1; VYRALX_MEDIA on Server 2), and the
  Server 2 media job snapshots the Server-2-resident env files. The structural gap is closed
  in practice by the two-job design; no env files were copied between servers.
- **Closed by this evidence — SEN-009 G3.** The encrypted offsite artifact uploaded for this
  run (artifact 14753072171), so the `BACKUP_ARTIFACT_PASSPHRASE` secret now exists. The
  passphrase still needs its record in the `CREDENTIALS.md` dossier (SEN-009 §6) — owner /
  coordinator item, unchanged.

## What was NOT done

- No backup, restore, or config was executed or changed on either server (read-only probes:
  `ls`, `cat`/`python3` summary of the two manifest files, `check_backup_freshness.py`).
- No restore drill — that is TASK-INF-020's successor scope (restore drill uses the newest
  backup chain; this task only verifies the manifest).
- No secret values were read, printed, logged, or stored anywhere in this task.

— Muse 10
