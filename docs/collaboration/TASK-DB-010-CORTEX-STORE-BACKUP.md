# TASK-DB-010 — Back up Cortex local store on Oracle Server 1: checkpoint 1 (scoping, 2026-11-26 ~10:52 IST)

**Task:** TASK-DB-010 (P2) — "DB: Back up Cortex local store on Oracle Server 1 - cortex.db + settle Redis persistence".
**Worker:** Muse 16. **Claim:** hub #1483 comment 7183493414, 2026-11-26 ~10:52 IST.
**Branch:** `muse16/task-db-010-cortex-store-backup`, created from main `94e6c679374b9264966d0bf38876776fa1da19d3`.
**Board:** verified first-hand on main `94e6c679` (23,830 lines): TASK-DB-010 AVAILABLE / owner muse_16 / branch null / pr null / P2 / updated 2026-11-26T07:05:00+05:30. No competing claim. Re-slotted to Muse 16 by coordinator watch130 (2026-11-26): Muse TP11 gave no report after the watch129 demand; DB-010 assigned ~3h+ with zero branches, commits or PRs. Queue: DB-010 head, DB-008 IN_REVIEW (PR #1944 merged); INT-039 + VYR-049 IN_REVIEW (PRs #1912/#1913 merged); DB-002 MERGED (PR #1861).
**Status of this checkpoint:** SCOPING FILED — read-only scoping from repo evidence complete; no live backup run, no live change made. This is a checkpoint, not a completion.

## Baseline (from the DB-003 fleet storage audit — cited, not re-probed)

Source: `docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md` (Muse 13, single dated sweep 2026-11-25 05:43–06:06 IST, live on S1 via the bridge).

Cortex live storage on Oracle Server 1 (S1, `Cortex.service` active, API :8009), `/opt/friday_universe/Cortex/`:

| Store | State at sweep | Notes |
|---|---|---|
| `data/cortex.db` | 372K SQLite (+32K shm) | The durable Cortex leg today (audit disagreement D5) |
| Redis `localhost:6379` | v6.0.16, uptime < 1 day, **0 keys** in db 0, AOF off, no `dump.rdb` on disk | RDB `save` policy configured (900 1 / 300 10 / 60 10000) but no dump file found; restarted recently |
| Event stream | Worker configured `REDIS_URL=redis://localhost:6379/0` + event stream (`cortex-worker-group`) | Redis is the API-to-worker event transport, not just a cache |
| ADB schema `CORTEX` | 17 tables, **1 row** @ 2026-11-22 | In the 2026-11-22 fleet backup (72K) |

**Backup state at sweep: PARTIAL.** ADB schema backed up (2026-11-22 fleet backup, verify 188 ok / 0 failed). `cortex.db`: **NO BACKUP**. Redis: unpersisted and currently empty. Follow-up filed as DB-010. Audit limit stated plainly: Redis contents before its recent restart are unknowable from the box — whether a stream existed before the restart cannot be established.

## What already exists in the repo vs what is missing (verified first-hand this run)

Checked via the GitHub API against main `94e6c679` (file reads + code search + `deploy/` listing).

**Exists — and does NOT cover DB-010's acceptance set:**

- `scripts/backup_fleet_databases.py` (TASK-INF-003 / SEN-009, 46,412 bytes): dumps the CORTEX ADB schema (72K in the Nov 22 run) + config snapshot + fleet-state bundle. Its only local-file leg is `AGENT_STATE_GLOBS = ("Stratex/state/*.jsonl", "Stratex/state/*.json")` — Stratex only. **No Cortex glob exists.** Its `FLEET_STATE_SOURCES` also lists `/opt/friday_universe/Cortex/data` and `/opt/friday_universe/Cortex/state` for the SSH-pulled fleet-state bundle (server1 leg, `required=False`) — but the audit still records `cortex.db` as NO BACKUP, and no per-file manifest/verify for that bundle leg is in the repo evidence read this run. Whether the Nov 22 bundle actually holds a `cortex.db` copy is open question Q3 below; the audit verdict stands until the live leg checks it.
- `scripts/check_backup_freshness.py` (TASK-SEN-009): freshness tripwire over the fleet backup root `/var/backups/friday-universe` only — checks complete ADB dumps, not Cortex local files or Redis.
- `scripts/backup_fleet_incremental.py` (TASK-REL-099, merged PR #1916): incremental snapshot store (rsync `--link-dest`) — the store DB-007 builds on. Reusable by DB-010; covers no Cortex files itself.
- `deploy/` (24 entries): no Cortex, Redis, or backup timer/service unit exists. The fleet backup has no schedule anywhere (audit: no timer/cron on any server; three manual runs only).
- Cortex code confirms the acceptance set is real: `Cortex/apps/api/src/cortex_api/config.py` defaults to `sqlite+aiosqlite:///./data/cortex.db` ("SQLite is DURABLE by default. Cortex persists CRM records"), with a `/dev/shm/cortex.db` Zero-Disk RAM SQLite tmpfs variant also in code — see Q2. `Cortex/apps/worker/src/cortex_worker/main.py` consumes the `cortex:events:stream` via XREADGROUP (consumer group `cortex-worker-group`, `REDIS_EVENT_STREAM` / `REDIS_CONSUMER_GROUP` from env, defaults in `Cortex/.env.example`), with a dead-letter stream `cortex:events:dlq`; the API publishes to the stream. **Redis is the live event transport between the Cortex API and worker — an unpersisted restart loses in-flight and unacknowledged stream entries, DLQ included.** `Cortex/data/` is git-ignored (no `data/` directory in the repo; config comment: a fresh clone has no `data/` directory).

**Missing — the DB-010 gap:**

- No script, timer, or cron backs up `cortex.db` on S1.
- No manifest / verify / restore-check exists for it.
- No Redis persistence decision exists: AOF off, no dump file, no documented ruling that Redis is volatile-transport-only.
- No freshness tripwire covers either leg (`check_backup_freshness.py` is fleet-ADB only).

## DB-007 / DB-008 overlap verdict (decided this run)

**DISTINCT — no overlap in scope; pattern reusable.**

- TASK-DB-007 (PR #1925, open, head `bd60c787`, author surendra2304, filed by Muse TP5): formalises the **VyralX file store on VyralX-Server (S5)** — 6.5G. Nothing in it touches a Cortex file or S1 Redis.
- TASK-DB-008 (PR #1944 merged): FRIDAY local state on FRIDAY-Server (S3). Different agent, server, and files.
- **What carries over:** the DB-007 pattern — script (stdlib only) + per-file SHA-256 manifest + `verify` re-hash + `restore-check` + daily systemd timer + runbook + tests, built on the merged REL-099 incremental store. DB-010 should follow that pattern with its own small script (`scripts/backup_cortex_store.py`), **not** import DB-007's code: PR #1925 is still open and its merge is HELD (board evidence: contracts fails on the pre-existing Futuris FUT-030 time-bomb; fix is TASK-REL-101).
- **Scale note:** `cortex.db` at 372K needs no VyralX-style cap exception; 7 daily + 4 weekly retention (DB-007's scheme) is ample. Redis persistence is a config decision, not a storage-size question.

## Live-leg plan (gated — not run this run)

Acceptance (board): "Back up the Cortex local store on Oracle Server 1 (server 1): Cortex/data/cortex.db (372K). Settle Redis persistence (localhost:6379: 0 keys, AOF off, no dump.rdb at the audit) - either persist the event stream durably or record that Redis is a volatile transport only. Prove with a dated backup + a read-back check."

1. **Script** `scripts/backup_cortex_store.py` (stdlib only, DB-007 pattern): `backup` stages `Cortex/data/cortex.db` (copy via the `sqlite3` backup API so the snapshot of the live file is not torn; record the method and any `-shm`/`-wal` sidecars in the manifest); writes `cortex-store-manifest.json` (per-file SHA-256 + bytes); stores via the REL-099 incremental store (rsync `--link-dest`); prunes 7 daily + 4 weekly. `verify` re-hashes a snapshot vs its manifest (read-back). `restore-check` restores + verifies + runs `PRAGMA integrity_check` on the restored `cortex.db` copy.
2. **Redis settlement (ruling Q1 first):** either enable persistence on the live S1 Redis (AOF `appendonly yes`, `appendfsync everysec`, plus an RDB snapshot policy that actually writes `dump.rdb`) and prove a restart keeps the stream, **or** record in the runbook, with the coordinator's ruling, that Redis is a volatile transport only — with the stated consequence that in-flight/unacknowledged stream and DLQ entries are lost on restart and must be re-publishable from the durable store. Do not silently pick one: enabling persistence changes live Redis config and the worker's delivery guarantees.
3. **Timer** `deploy/cortex-store-backup.{service,timer}`: daily, Persistent, oneshot (cadence to match the DB-007 02:15 UTC slot or a non-colliding slot — decide at install; do not collide with the fleet backup window).
4. **Out root:** `/var/backups/friday-universe/cortex-store` (same root as the fleet backup, separate subtree) — confirm at install.
5. **Proof (the acceptance):** first dated backup on S1 + restore/read-back check (`verify` + `restore-check` exit 0) + a dated manifest; then extend `check_backup_freshness.py` (or file a follow-up) so the Cortex-store leg has a freshness tripwire — the fleet-only checker does not cover it today.
6. **Tests** `tests/test_db010_cortex_store_backup.py` (DB-007 pattern: manifest, verify + tamper, incremental, restore drill, prune-keeps-newest) + local CLI smoke on fixtures (no live host).

## Open questions / rulings owed

- **Q1 — Redis: persist or volatile-transport-only?** Needs a coordinator ruling before the live leg: enabling AOF/RDB changes live S1 Redis config and delivery guarantees; recording volatile-only accepts event loss on restart. The task text allows either; the choice is not this worker's to make silently.
- **Q2 — Which DSN does live S1 actually run?** Code defaults to file-backed `./data/cortex.db` but also offers a `/dev/shm/cortex.db` tmpfs variant. Confirm on S1 which one the live service uses: a tmpfs `cortex.db` would not survive reboot and a file-copy backup would be meaningless — the backup target (and the task) changes entirely.
- **Q3 — Does the Nov 22 fleet-state bundle already hold a `cortex.db` copy?** `FLEET_STATE_SOURCES` pulls `Cortex/data` via SSH (server1 leg, `required=False`). Check the Nov 22 bundle on S1 at the live leg; if a copy exists, decide with the coordinator whether it counts as a backup (no per-file manifest/verify exists for it). The audit verdict (NO BACKUP) stands until then.
- **Q4 — ADB CORTEX schema holds 1 row @ Nov 22.** Is the ADB leg live at all, or is `cortex.db` the only live store? Do not assume; the live leg should note the row count when it re-probes. (Wiring, if the ADB is meant to be live, is a DB-002-style question, not this task's.)
- **Q5 — Redis pre-restart contents are unknowable** (audit limit). Stream durability can only be proven going forward, from the settlement date — no back-dated claim is possible.

## Gates (live leg cannot run until these clear)

- **G1 — bridge approval for S1 access.** Hub #1483 comment 7113152293 (posted 2026-11-24 ~02:00 IST) is still open with no reply as of this run. The dated backup + restore/read-back proof on S1 needs bridge `run_shell` (or the equivalent S1 access the coordinator grants). No live backup was attempted this run, and no live host was probed.
- **G2 — Q1 Redis ruling.** See above; owed by the coordinator before the live leg touches Redis config.

## States

- Implemented: NO (scoping only; no script, timer, or test written this run)
- Tested: NO (no local tests; no live host touched)
- Merged: NO (work PR this run carries checkpoint 1 only)
- Deployed: NO
- Production-verified: NO — no dated backup exists and no restore/read-back check has run

## Files

- This evidence doc: `docs/collaboration/TASK-DB-010-CORTEX-STORE-BACKUP.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-DB-010 CLAIMED/muse_16; branch `muse16/task-db-010-cortex-store-backup`; pr null — coordinator fills it)
- Source audit: `docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md`
- Pattern reference (open PR, not merged): PR #1925, TASK-DB-007 VyralX file-store backup formalisation; merged checkpoint-1 precedent: PR #1944, TASK-DB-008

— Muse 16, 2026-11-26 ~10:52 IST
