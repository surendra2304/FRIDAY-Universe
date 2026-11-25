# TASK-DB-009 — Grounding (checkpoint 1)

**Filed:** 2026-11-26 ~04:25 IST, Muse 19 hourly self-check (stall repair —
branches carried zero commits ~1h after the ~03:20 IST claim).
**Task:** DB: Back up Sentinel local audit ledger on Oracle Server 1 —
audit.jsonl, 33 entries. **Board (main `bf5a08b7`):** AVAILABLE / owner
muse_19 / branch null / pr null. P2. Board flip AVAILABLE → CLAIMED rides
in the work PR (owner rule 4). No PR with this checkpoint (owner rule 1).

## Acceptance (board, verbatim)

- Back up the Sentinel local audit ledger on Oracle Server 1 (server 1):
  `Sentinel/logs/audit.jsonl` (33 entries at the audit). Cross-check the
  file against the API-served ledger and the SENTINEL ADB schema (17 rows
  @ Nov 22) and record which is authoritative. Prove with a dated backup +
  a read-back check.

## Verified from the repo (main `bf5a08b7`, first-hand this run)

- Source: `docs/collaboration/TASK-DB-003-FLEET-STORAGE-AUDIT.md` (Muse 13
  fleet storage audit, sweep 2026-11-25 05:43–06:06 IST), lines 41 / 78 / 91.
- Ledger: `/opt/friday_universe/Sentinel/logs/audit.jsonl` — **27,617 bytes,
  33 lines, newest 2026-11-24 13:34 IST (seq 33, TLS_CERT_ALERT)**.
- ADB SENTINEL schema: 15 tables, **17 rows @ 2026-11-22**, in the
  2026-11-22 fleet backup (PARTIAL).
- **NO BACKUP of `audit.jsonl`** — not in the fleet script's file globs.
  This task is the follow-up.
- Sentinel.service active, API `:8008`, on Oracle Server 1 (same sweep).
- Discrepancy **D8** (filed in the audit doc): ledger file (33 entries) vs
  ADB schema (17 rows) counts differ. Whether the API-served ledger and
  the file are the same store needs a cross-check (verifier).
- Fleet backup pattern (same doc): logical JSONL dump per table + manifest
  (row counts + SHA-256) + config snapshot, out root
  `/var/backups/friday-universe`, script
  `scripts/backup_fleet_databases.py` (TASK-INF-003 / SEN-009).
  NOTE: that script is **not in the repo tree** at `bf5a08b7` (7,848 blobs
  searched) — it lives on the server. The DB-009 backup follows its
  manifest pattern; the exact script path is confirmed on access.

## Cross-check plan (live leg)

1. Read back the file: line count, SHA-256, seq continuity 1–33.
2. API-served ledger: query the Sentinel API (`:8008`) for the served
   ledger and compare entry-for-entry with the file (endpoint TBD on
   access — not named in the audit doc).
3. ADB SENTINEL rows: recount; note the date gap (file newest Nov 24 vs
   schema Nov 22) — the 33-vs-17 gap may be timing, not a second store.
   Record as hypothesis until the recount proves it; do not assert.
4. Authoritative store: the file, unless the API serves entries the file
   lacks (then name the divergence, do not paper over it).
5. Dated backup + manifest (row count + SHA-256 + read-back check) filed
   as the completion evidence.

## Blockers (live leg — nothing attempted)

- **Backup write is a server write — HELD under the owner stop order.**
  No freeze lift in WATCH120–123 (read in full this run). No server move
  attempted.
- **Live cross-checks need bridge / server read access.** No bridge CLI
  exists in this environment (checked `/opt/hatch/bin` — only unrelated
  `*-mcp` CLIs); the bridge MCP was verified at onboarding but has no
  local client here. Read-only ledger/API/ADB reads are owed, not done.
- `run_shell` grant for server reads is not held (MEM-026 precedent:
  grant owed via the trusted route).

## Next

On clearance: run the dated backup + read-back check + the three-way
cross-check, file the evidence, open the single work PR (grounding +
backup evidence + board flip). REL-094 stays parked; SEN-028 is the
parallel head.

— Muse 19
