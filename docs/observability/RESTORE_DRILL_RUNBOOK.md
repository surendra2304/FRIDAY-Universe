# Restore Drill Runbook — TASK-SEN-009 (G6)

**Purpose:** prove — with evidence, not assertion — that a fleet backup can actually be restored. A backup that has never been restored is a hypothesis; SEN-007 found the fleet ran on that hypothesis for five weeks with zero complete backups.

**Tool:** `scripts/restore_fleet_database.py` (TASK-INF-003). Read-only by default: it compares a backup against the live schema and prints `LOADABLE / REFUSED / MISSING / DRIFT` per table. `--apply` loads only into **empty** live tables; `--replace` (with `--yes-i-understand`) drops and recreates a live table from the backup.

**Companion docs:** `docs/observability/BACKUP_REPAIR_SEN009.md` (§4 produces the first complete backup this drill needs), `docs/runbooks/BACKUP_RESTORE_AND_LEDGER_DRILL.md` (the INF-003-era drill + ledger procedure).

---

## Preconditions (all must hold)

1. A **complete** backup exists: newest manifest on Server 1 has `complete: true` and `failed_agents: []` (see BACKUP_REPAIR_SEN009.md §4), and a complete VYRALX_MEDIA manifest exists on Server 2.
2. `python3 scripts/backup_fleet_databases.py --verify` exits 0 on the newest backup directory.
3. Phase A needs nothing else. Phase B2/B3 need the coordinator's go-ahead recorded on the TASK-SEN-009 board entry (B3 touches a live schema; B2 needs ADB admin credentials from the dossier to create a scratch user).
4. Run drills from the server that hosts the backup (`/opt/friday_universe` checkout, venv python). Credentials resolve exactly as the backup resolved them.

## Phase A — Verify-only drill (zero risk; run immediately after the first complete backup)

For every agent **and** the media schema:

```bash
cd /opt/friday_universe
for A in FRIDAY INFERENCE MEMORA STRATEX FUTURIS INTELX FORGE SENTINEL CORTEX VYRALX; do
  sudo /opt/friday_universe/venv/bin/python scripts/restore_fleet_database.py \
    --agents "$A" --from-dir /var/backups/friday-universe/<STAMP>
done
# on Server 2:
sudo /opt/friday_universe/venv/bin/python scripts/restore_fleet_database.py \
  --media --from-dir /var/backups/friday-universe/<MEDIA_STAMP>
```

**Expected:** every table reports `DRIFT` (live rows ≥ backup rows — the fleet kept writing after the backup) or `LOADABLE`. Any `REFUSED` means the backup table's shape does not match the live schema (backup of a *different* schema version — investigate before trusting the backup); any `MISSING` means the live schema lost a table the backup has (schema drift — also investigate).

**Record:** the full output, per agent, on the TASK-SEN-009 board entry. Phase A passing for all 11 targets = the backup is *readable and shape-compatible*. It does not yet prove a load works — that is Phase B.

## Phase B1 — Apply mechanics on an empty target (safe; no live data touched)

The restore tool's `--apply` refuses non-empty tables, so a load test needs an empty table set. Use the smallest schema — **FORGE (7 tables)** — against a scratch target:

1. Point a drill env file at a throwaway login on the same ADB (creating that login is the B2 gate below; if a scratch user already exists, skip to 3):
   `cp` the FORGE entry into `/tmp/drill.env` as `FORGE_DATABASE_URL=<scratch-user-url>` (same DSN, scratch credentials from the dossier).
2. Create FORGE's tables in the scratch schema using the agent's own bootstrap (run Forge's schema initialisation with the drill env), so the shape is the real one.
3. `python3 scripts/restore_fleet_database.py --agents FORGE --from-dir <STAMP> --env-file /tmp/drill.env --apply`
4. **Verify:** re-run without `--apply` against the drill env — every table must now report `DRIFT` with live rows **equal** to the backup's `row_count` for that table (equality, not ≥, because the scratch schema holds only what the drill loaded). Any mismatch = the drill failed; record it, do not rationalise it.

## Phase B2 — Scratch-schema gate (owner/coordinator-held)

Creating/dropping an Oracle user on the production ADB needs the ADMIN credentials in `CREDENTIALS.md` (Server 2). The drill does not need them until this phase; the commands, once authorised:

```sql
CREATE USER SEN009_DRILL IDENTIFIED BY "<generated, recorded in dossier>";
GRANT CONNECT, RESOURCE, UNLIMITED TABLESPACE TO SEN009_DRILL;
-- after Phase B1 verification:
DROP USER SEN009_DRILL CASCADE;
```

**Teardown is part of the drill:** the scratch user must not survive it. Record create/drop timestamps on the board entry.

## Phase B3 — Production-shaped drill (maintenance window; coordinator-gated)

Only if B1's scratch path is impossible: pick the smallest, least-active live schema (FORGE), take a **fresh complete backup immediately before**, then during a window with Forge stopped:

```bash
sudo systemctl stop friday-forge   # service name per host runbook
python3 scripts/restore_fleet_database.py --agents FORGE --from-dir <FRESH_STAMP> --replace --yes-i-understand
python3 scripts/restore_fleet_database.py --agents FORGE --from-dir <FRESH_STAMP>   # verify: rows == manifest counts
sudo systemctl start friday-forge
curl -s localhost:8006/health
```

Rollback = the fresh backup taken at the top of the window, same commands. Abort the drill if the fresh backup is not `complete: true`.

## Success criteria (the drill counts as done only when all hold)

- [ ] Phase A output recorded for all 10 agents + media; zero unexplained `REFUSED`/`MISSING`.
- [ ] Phase B1: FORGE backup loaded into an empty target; post-load row counts **equal** the manifest's `row_count` for all 7 tables.
- [ ] Scratch target torn down (B2 user dropped) or B3 service healthy with counts verified.
- [ ] Timings recorded (how long a real restore takes is an RTO fact the fleet currently does not know).
- [ ] Board entry updated with the evidence; only then may TASK-SEN-009's G6 be called complete.

## What this drill deliberately does not do

* It does not restore over live data as a first test (that is a recovery, not a drill).
* It does not test the offsite artifact path (BACKUP_REPAIR_SEN009.md §6) — decrypt-and-verify of one artifact is a worthwhile second drill once `BACKUP_ARTIFACT_PASSPHRASE` exists.
* It does not cover Server 2's schemas' restore from a Server 1 backup until the §8 open item in the repair doc (Server-2 credential reachability) is resolved.
