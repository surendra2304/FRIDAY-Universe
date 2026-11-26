# TASK-DB-009 — Checkpoint 2: three-way cross-check (LIVE evidence)

**Filed:** 2026-11-26 ~20:25 IST, Muse 19 hourly self-check (20:17 run).
**Task:** DB: Back up Sentinel local audit ledger on Oracle Server 1 —
`audit.jsonl`, 33 entries at the audit.
**Board (main `49cfd862`):** AVAILABLE / owner muse_19 / branch null / pr null.
P2. Board flip AVAILABLE → CLAIMED rides in the work PR (owner rule 4).
No PR with this checkpoint (owner rule 1 — one work PR at completion).

## Bridge channel — RECOVERED this run

- 19:17 run: bridge MCP init 200 (v1.30.0) but `tools/list` returned 0 bytes
  (IncompleteRead) — run_shell not confirmable, no tool call made (hub
  7193949440). WATCH166 directed: retry next run; report as channel failure
  if still down, not a clearance wait.
- This run: init 200, session established, `tools/list` 200 — **31 tools
  including `run_shell`** (args: command, server, cwd, timeout). One
  transient SSL EOF on a later call (bridge dropped stream — same pattern
  as WATCH162/163); immediate retry succeeded. Channel usable, flaky.
- Grant basis: owner ruling hub 7192682851 (18:25 IST, FULL run_shell for
  all worker chats, approval 7113152293 CLOSED) + confirmation 7193378286.
  All calls below are **read-only**; no server move, no write.

## Cross-check — live, Server 1, 2026-11-26 ~20:21–20:28 IST

### 1. Ledger file (leg 1)

- Path: `/opt/friday_universe/Sentinel/logs/audit.jsonl`
- **42 entries** (was 33 at the Nov 25 audit — the ledger is still growing)
- SHA-256: `659bae3791ab084dbf8e172d593ac4ed0b70ba2b47c06d95272259de523bb240`
- **seq continuous 1–42: True.** Event types: TLS_CERT_ALERT ×37,
  APPROVAL_AUTO_APPROVED ×5.
- Timestamp range: 2026-11-20T18:21:35Z → 2026-11-26T13:56:41Z
  (newest: seq 42, TLS_CERT_ALERT).
- `Sentinel.service`: active.

### 2. API-served ledger (leg 2)

- `GET http://127.0.0.1:8008/health` → status ok, service sentinel,
  `audit_chain_valid: true`, **`audit_chain_entries: 42`**,
  `audit_durable: true`, observed 2026-11-26T14:51:47Z.
- **File and API agree exactly: 42 entries, chain valid.** The API serves
  the same store as the file.

### 3. ADB / fleet-backup side (leg 3)

- Latest fleet backup on Server 1: `/var/backups/friday-universe/
  20261126T192515Z` (manifest created 2026-11-26T13:55:15Z; dirs
  root-owned, read via `sudo -n` read-only listing).
- SENTINEL schema in that backup: **15 tables, 45 rows total** —
  SENTINEL_AUDIT_LOGS 4, SENTINEL_EVENTS 40, SENTINEL_SCOPES 1, rest 0.
- `SENTINEL_AUDIT_LOGS.jsonl.gz`: 4 rows, all PRE_DELIVERY_SECURITY_AUDIT
  (Nov 14, wave-3 Sentinel veto records). Recomputed SHA-256
  `09c26e165616d09bf52042f765c33fd4404d14e5e6e33157f3a46361e2c427f3`
  **matches the manifest exactly** (read-back check of the fleet backup
  itself: pass).
- The ADB SENTINEL_AUDIT_LOGS table is a **different store** from the local
  audit chain — pre-delivery audit records, not a mirror of `audit.jsonl`.

## Verdict — which store is authoritative

- **The ledger file is authoritative for the audit chain, corroborated by
  the API (42 = 42, chain valid).**
- D8 (file 33 vs ADB 17) is resolved as a **category error plus timing**:
  the "17 rows @ Nov 22" was the whole-SENTINEL-schema total in the Nov 22
  backup, not the audit-log table; the schema total today is 45 rows, and
  the ledger file grew 33 → 42 in two days. The file-vs-ADB count gap was
  never a second ledger — the ADB holds pre-delivery audit records and
  events separately.
- Open note, not a contradiction: SENTINEL_EVENTS holds 40 rows vs the
  chain's 42 — a different table; no claim made about their relationship.

## What remains (completion)

- **Dated backup of `audit.jsonl` + manifest (row count + SHA-256) +
  read-back check — a server WRITE, still NOT granted.** WATCH164 keeps
  TP4's DB-005 Leg B (dated backup + restore/read-back) NOT granted; same
  class as this backup. No backup write attempted or planned until that
  grant lands. When it lands: run the backup, file the evidence, open the
  single work PR (grounding + cp2 + backup evidence + board flip).
- SEN-028 live walkthrough and REL-094 re-drill reads are now actionable
  on the recovered channel; next run.

— Muse 19
