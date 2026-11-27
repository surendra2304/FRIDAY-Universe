# TASK-DB-009 — Back up Sentinel local audit ledger on Oracle Server 1

- **Task:** TASK-DB-009 (DB: Back up Sentinel local audit ledger on Oracle Server 1 - audit.jsonl, 33 entries)
- **Assignment:** WATCH241 TP3 re-scope (hub #2045 comment 7227807232), board flip watch242: TP3 works DB-009 now as working head; FRD-048 and MEM-017 stay queued BLOCKED on owner gates.
- **Claim:** hub #2045 comment 7228694659 (2026-11-28 ~03:13 IST)
- **Branch:** `musetp3/task-db-009-sentinel-audit-ledger-backup` from main `f15516b0`
- **Acceptance:** "Back up the Sentinel local audit ledger on Oracle Server 1 (server 1): Sentinel/logs/audit.jsonl (33 entries at the audit). Cross-check the file against the API-served ledger and the SENTINEL ADB schema (17 rows @ Nov 22) and record which is authoritative. Prove with a dated backup + a read-back check."

## Board verified first-hand

Live main `ff5806b2` (board blob `4601fcfa`, updated 2026-11-28T02:36:15+05:30), 2026-11-28 ~05:10 IST:
TASK-DB-009 reads CLAIMED / owner muse_tp3 (next_action: working head for muse_tp3, WATCH241 ruling). TASK-FRD-048 BLOCKED (Fish Audio route before Nov 30), TASK-MEM-017 BLOCKED (Halo key paste, blocker 7200182638).

## Source state (live probe, Oracle Server 1 `friday-universe-vnic`, 2026-11-28 ~05:15 IST)

- Source `/opt/friday_universe/Sentinel/logs/audit.jsonl`: **55 lines**, **46,146 bytes**, sha256 `1bdc7536dc3742ec06982518cbef07cf8fdc32723b3b1961b8f8e8fd38dbbb53`, mtime 2026-11-28 04:44:11 +0530.
- Growth: 33 entries at the DB-003 audit (Nov 25) → 54 lines at the 04:08 IST probe (45,284 B, sha256 `b09f9755…`) → 55 lines now. The ledger is live and appending.
- No ledger content was read or copied in any probe — counts, sizes and hashes only.

## Gap confirmed: no existing backup of the local file

- Fleet backups exist on S1 under `/var/backups/friday-universe/` (dated dirs `20261128T023026Z`, `20261128T031931Z`, `20261128T040750Z`, `20261128T044909Z`), each with per-agent subdirs including `SENTINEL/` (15 table exports, e.g. `SENTINEL_AUDIT_LOGS.jsonl.gz`).
- `find /var/backups/friday-universe/ -name 'audit.jsonl'` returns **nothing** — the local file `Sentinel/logs/audit.jsonl` is not in the fleet backup globs (matches DB-003). The fleet backup covers the ADB table export, not the local ledger file.

## Dated backup (2026-11-27T23:49:47Z / 2026-11-28 05:19:49 IST)

Created with `sudo cp -p` (bridge shell runs as `ubuntu`; `/var/backups` is root-owned). Original file untouched.

| Artifact | Size | Note |
|---|---|---|
| `/var/backups/friday-universe/sentinel-audit-20261127T234947Z.jsonl` | 46,146 B, 55 lines | point-in-time copy of `Sentinel/logs/audit.jsonl` |
| `/var/backups/friday-universe/sentinel-audit-20261127T234947Z.jsonl.sha256` | sidecar | `1bdc7536dc3742ec06982518cbef07cf8fdc32723b3b1961b8f8e8fd38dbbb53` |

## Read-back check (same run, live)

- Source sha256 before copy == backup sha256 == source sha256 after copy: `1bdc7536…dbbb53` (no append raced the copy).
- `sha256sum -c` against the sidecar: **OK** — backup is byte-identical to the source at copy time.
- Line counts: source 55, backup 55.

## Cross-check: file vs API-served ledger vs ADB schema

| Store | Count (this run) | Evidence |
|---|---|---|
| Local file `Sentinel/logs/audit.jsonl` | **55 lines** | `wc -l` + sha256 above, S1 live |
| API-served ledger (Sentinel.service, uvicorn `sentinel.apps.api.main:app` :8008) | **55 entries** | `GET /health` 200 at 2026-11-27T23:49:49Z: `audit_chain_entries: 55`, `audit_chain_valid: true`, `audit_durable: true` (`durable_store_configured`) |
| ADB schema `sentinel_audit_logs` (alembic `0001_initial_core_models.py`) | **4 rows in latest fleet export** | `zcat …/20261128T044909Z/SENTINEL/SENTINEL_AUDIT_LOGS.jsonl.gz \| wc -l` = 4 (1,287 B, mtime Nov 28 04:51 IST). Board record said 17 rows @ Nov 22. |

**Which is authoritative:** the local file and the API-served chain agree exactly (55 entries, chain valid, durable store configured) — together they are the complete audit ledger. The ADB export (4 rows) does **not** corroborate them and cannot be the complete record; whether the live ADB table holds 4 rows, a filtered subset, or a lagging sync is **not proven here** — a live ADB row count requires DB credentials, which TP3 does not handle. The divergence (55 vs 4) is flagged for a coordinator ruling. A literal `audit.jsonl` path string was not found in `Sentinel/app|apps|scripts` Python sources (writer path likely constructed dynamically) — recorded as an unresolved detail; it does not affect the backup proof.

## Limits, stated plainly

- The backup is a **point-in-time snapshot** (2026-11-27T23:49:47Z). The ledger keeps appending (33 → 54 → 55 across Nov 25–28); the copy does not track later entries.
- **No schedule was set:** this is a one-time dated backup. Adding `Sentinel/logs/audit.jsonl` to the fleet backup globs (so the gap does not recur) is a coordinator decision, not part of this task.
- Live ADB row count not queried (credentials not handled); the fleet-export count is the credential-free proxy and is labelled as such.

## Verdict

TASK-DB-009 acceptance met: dated backup exists on S1 with a recorded sha256, read-back proves it byte-identical (55/55 lines), and the cross-check records the file/API chain (55, valid) as authoritative with the ADB-export divergence (4) flagged. Paired verification requested — a different chat verifies the backup independently.

— Muse TP3
