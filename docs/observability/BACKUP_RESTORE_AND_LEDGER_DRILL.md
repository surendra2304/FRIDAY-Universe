# Database Backup, Restore & Ledger Persistence Drill (TASK-INF-003 + TASK-DATA-003)

**Implemented:** 2026-11-10, ZAI. Code + unit tests live in the repo; the production drills run through GitHub Actions with explicit owner confirmation.

## 1. Scope

| Asset | Production store | Covered by |
|---|---|---|
| All ten agent schemas (FRIDAY, INFERENCE, MEMORA, STRATEX, FUTURIS, INTELX, FORGE, SENTINEL, CORTEX, VYRALX) + VYRALX media | Oracle Autonomous Database 26ai | `scripts/backup_fleet_databases.py` / `scripts/restore_fleet_database.py` |
| Service configuration (DB credential env files, systemd units) | `/etc/friday-universe/*`, `/etc/systemd/system/*.service` | config snapshot inside every backup (mode 600) |
| Memora memory ledger | MEMORA schema (Oracle, fail-closed) | persistence contract test + production drill |
| Stratex order-intent ledger (idempotency + audit trail) | STRATEX schema (Oracle, fail-closed) | persistence contract test + production drill |

## 2. Backup tooling

### Full backup (all agents + configs)
```bash
# on a server (Server 1 has all env files):
sudo /opt/friday_universe/venv/bin/python scripts/backup_fleet_databases.py --keep 4
# → /var/backups/friday-universe/<timestamp>/<AGENT>/<TABLE>.jsonl.gz + manifest.json
```
- One gzipped JSONL file per table, SHA-256 per file in the manifest, manifest written last with a self-verify pass.
- Backup directories are mode 700, files mode 600 (they contain data and config secrets).
- `--dry-run` inventories tables/rows without writing anything (safe read-only evidence).
- `--verify` re-checks any backup's checksums; `--agents MEMORA,STRATEX` narrows scope; `--media` adds the VyralX media schema.

### Scheduled + manual
`.github/workflows/fleet-backup.yml` runs the backup on Server 1 weekly (Sun 03:30 UTC, `--keep 4`, disk-space guard ≥ 2 GB) and can be dispatched manually. The job log (table counts + verify result) is the evidence record.

## 3. Restore

```bash
# Safe drill (read-only): compare a backup against LIVE row counts — measures drift:
sudo python scripts/restore_fleet_database.py --backup-dir /var/backups/friday-universe/<stamp> \
    --agents MEMORA,STRATEX
# Destructive load (only into EMPTY tables by default):
sudo python scripts/restore_fleet_database.py --backup-dir ... --agents MEMORA --apply
# Reload over existing data (truncate first):
sudo python scripts/restore_fleet_database.py --backup-dir ... --agents STRATEX --apply --replace
```
Guards: refuses non-empty target tables without `--replace`; refuses tables missing in live (recreate schema/tables first — boot the agent once); per-table failure reporting, FK-deferred retry pass; every decision printed.

**Catastrophic recovery path:** recreate the Oracle user → boot the agent once (SQLAlchemy creates tables) → `--apply` from the newest backup → restart the agent. For surgical single-table restores prefer Oracle Data Pump; this tooling is fleet-level insurance, and the drill proves it.

## 4. Ledger persistence drill (TASK-DATA-003)

### Contract tests (every CI run)
`tests/test_ledger_persistence_recovery.py` — 4 tests using REAL subprocesses that exit between write and read:
- **Memora:** subprocess A boots the real FastAPI app on a file-backed test DB, ingests a memory via `POST /memories`, dies; subprocess B boots fresh over the same file and reads it back by id AND via query. Proves the memory ledger is on-disk, not process memory.
- **Stratex:** subprocess A reserves an order intent (`OrderIntentStore`) and advances RESERVED → SUBMITTING → ACCEPTED, dies; subprocess B re-opens the file: duplicate read returns the same terminal state and result, the append-only audit trail survived, and a conflicting reuse of the same client-order-id with a different payload still raises `IntentConflictError` after restart — the anti-double-spend contract holds across process death.

### Production restart drill (owner-authorized)
`.github/workflows/ledger-persistence-drill.yml` — manual dispatch with typed confirmation:
1. Snapshot MEMORA + STRATEX ledger row counts (read-only) on Server 1.
2. `sudo systemctl restart Memora Stratex` (the typed confirmation is the owner authorization this restart requires per the security rules).
3. Re-read the same counts and compare — zero row loss = PASS; any shrinkage = FAIL with the diff.
The job log with timestamps is the drill evidence for WORK_BOARD/handoff.

## 5. Retention & offsite

- Local retention: newest 4 weekly backups (`--keep 4`).
- Offsite copy (owner decision): the backup dir can be rsync'd anywhere; recommend at least one copy outside Server 1's boot volume (object storage or the owner's laptop) once backups exceed trivial size.
