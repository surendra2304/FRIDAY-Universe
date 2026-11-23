# TASK-REL-089 — Sentinel backup restore drill

**Task:** TASK-REL-089 (Reliability, P2): restore the latest Sentinel backup
to a scratch location and prove it boots; file the restore evidence.
**Assignment:** coordinator watch 7106041874 (~21:40 IST) and push 7107020017
(~22:05 IST); queue VOI-030 (blocked) → OBS-020 → REL-089.
**Claim:** hub #1483 comment 7107040961 (2026-11-23 ~21:55 IST); claim PR
#1528 merged 2026-11-23 22:08 IST (merge `b9a78103`).
**Branch:** `muse13/task-rel-089-backup-restore-drill` (claim head `fa2eb045`).
**Drill run:** 2026-11-23 ~22:40–23:10 IST, by Muse 13. All live checks
first-hand via the FRIDAY bridge (read-only vs live: `SELECT` only; the one
load went to a throwaway SQLite DB in `/tmp`, deleted afterwards).

## Verdict (read this first)

**The drill FAILS on content fidelity — and that failure is the finding.**

The latest Sentinel backup restores structurally: all 15 tables load into
scratch with counts exactly equal to the manifest, the restored columns match
the live Oracle schema exactly, and every scalar column (ids, hashes,
signatures, timestamps, decisions) is byte-identical to live. Sentinel would
boot from this backup.

But the backup silently lost every JSON/CLOB value it holds: the 4 audit
`details`, the 12 event `payload`s, and the 4 scope JSON columns are all `""`
in the backup while live holds full JSON. **A restore from this backup would
boot Sentinel with its audit details, event payloads, and scope contract
empty.** The root cause is proven, not guessed: the backup tool reads LOBs
with the offset and the length swapped (§5, gap R1). The backup's own
`--verify` (188 files OK) and the manifest's `complete: true` cannot see this
— they check checksums and counts, never content.

Acceptance ("Restore evidence filed") is met by this doc. The drill's purpose
— proving the backup is a faithful restore — is NOT met until R1 is fixed, a
fresh backup is taken, and the drill is re-run.

## 1. Backup used (the latest)

| | |
|---|---|
| Backup dir (Server 1) | `/var/backups/friday-universe/20261122T171929Z` |
| Created (UTC) | 2026-11-22T11:49:29Z (dir stamp is IST-labelled `Z`, SEN-022 F-SEN-022-2) |
| Produced by | Scheduled Fleet Backup run 45019170405 (event `schedule`, success) |
| Manifest | `complete: true`, `failed_agents: []`, `verify: {ok: 188, failed: 0}` |
| Freshness at drill | `status: ok`, `age_hours: 29.4`, `complete_backups: 3`, exit 0 |
| Newer backup? | No — still the newest on S1 at 22:42 IST (dirs: `20261116T062553Z`, `20261118T173701Z`, `20261122T171929Z`); the Nov 23 scheduled run had not landed |
| SENTINEL in manifest | 15 tables, 17 rows (AUDIT_LOGS 4, EVENTS 12, SCOPES 1, 12 tables 0 rows) |
| Boot inputs in backup | Sentinel `.env` present in `agent_envs` (9 envs; Cortex absent as expected, S2 agent); 44 config files |

## 2. What was run (commands, paths, timestamps)

All drill commands ran from Server 1 (`/opt/friday_universe` checkout, venv
python), driven through the bridge MCP `run_shell` tool. Times IST unless
marked Z.

**Step 0 — Manifest + freshness** (22:42 IST / 17:12Z). Backup root listed;
newest manifest read with a compact summary extractor (SENTINEL entry only);
`scripts/check_backup_freshness.py --json` → ok (see §1).

**Step 1 — Backup tool's own `--verify`** (22:44 IST).
`sudo venv/bin/python scripts/backup_fleet_databases.py --verify --from-dir
/var/backups/friday-universe/20261122T171929Z` →
`[VERIFY] 188 files OK, 0 failed — backup complete`, exit 0.

**Step 2 — Integrity + scratch load + Phase A** (22:45 IST / 17:15:52Z).
`/tmp/rel089_sentinel_drill.py` (kept in `~/workspace/muse13/rel089/`):
uses the restore tool's own `iter_backup_rows` / `compare_to_live` /
`resolve_target`, so the drill exercises the real restore path.
- Per-file integrity: SHA-256 recomputed vs manifest + gunzipped line count
  vs `row_count`, for all 15 SENTINEL files.
- Scratch load: all rows into throwaway SQLite
  `/tmp/rel089_sentinel_scratch.db`, count per table vs manifest.
- Live shape check: restored row keys vs live Oracle columns
  (`all_tab_columns`), per table.
- Phase A: `compare_to_live` (read-only `SELECT COUNT(*)`).

**Step 3 — Content equality vs live** (~22:55 IST).
`/tmp/rel089_content_compare.py`: every restored row compared field by field
against the live Oracle row with the same primary key (read-only SELECTs).

**Step 4 — Audit-chain + hash checks** (~23:00 IST).
`/tmp/rel089_audit_chain_verify.py` (Sentinel's own chain algorithm from
`Sentinel/sentinel/audit/audit_logger.py`: `_calculate_hash`,
`_payload_from_entry_data`, GENESIS) and `/tmp/rel089_lob_mechanism.py`
(live LOB read semantics + v1 hash recomputation with live details).

**Step 5 — Live Sentinel baseline** (22:48 IST / 17:18:06Z).
`Sentinel.service` on S1: loaded / active / running, MainPID 3115618,
listening on 0.0.0.0:8008. `curl 127.0.0.1:8008/ready` → `READY`, `ready:
true`, all checks true (incl. `audit_integrity`, `audit_durable`,
`telegram_channel`); `/health` → `ok`, `audit_chain_valid: true`,
`audit_chain_entries: 23`, `audit_durable: true`. (The bridge
`oracle_check_service` tool reports S2, where `Sentinel.service` is masked —
expected: Sentinel is an S1 service; the S1 unit above is the live one.)

**Step 6 — Teardown** (~23:10 IST). All `/tmp/rel089_*` files on S1 deleted
(scratch DB, drill scripts, JSON reports, outputs); `ls /tmp/rel089_*`
confirms none remain. No live writes anywhere in this drill: no `--apply`,
no `--replace`, no Oracle scratch user (B2 gate — no coordinator go-ahead),
no service stop/restart, no file written outside `/tmp` on S1.

## 3. Results

### 3a. Structure: everything that can be counted, counts

| Check | Result |
|---|---|
| Per-file integrity (15 files) | 15/15 SHA-256 match; 15/15 line counts == manifest `row_count` |
| Scratch load (SQLite) | 17/17 rows; counts equal to manifest for every table (incl. 12 empty tables at 0) |
| Restored columns vs live schema | Equal for all 3 tables with rows; live columns recorded for the 12 empty tables |
| Phase A (verify-only) | 14 match, 1 differ — `SENTINEL_EVENTS` 12 → 25 (+13, live writes since backup, expected drift); 0 missing, 0 extra |
| Scalar columns vs live | Identical for all 17 rows (entry/event/scope ids, hashes, signatures, timestamps, decisions, targets, actors, event types, topics, sources, correlation ids, scope scalars) |

### 3b. Content: every JSON/CLOB value is empty in the backup

Field-by-field comparison against live (same primary keys):

| Table | Rows | Lost in backup |
|---|---|---|
| `SENTINEL_AUDIT_LOGS` | 4 | `details`: `""` in backup, full JSON live (e.g. `{"audit_id": "aud-…", "task_id": "sen-gt-planted", "veto": true, …}`) |
| `SENTINEL_EVENTS` | 12 restored / 25 live | `payload`: `""` in backup, full JSON live (incident payloads, TLS-expiry payloads, …); the 13 extra live rows are post-backup writes |
| `SENTINEL_SCOPES` | 1 | `allowed_targets`, `in_scope_declarations`, `out_of_scope_declarations`, `scope_contract`: all `""` in backup, full JSON arrays/object live |
| 12 empty tables | 0 rows | Nothing to lose; counts match |

**21 values lost across 17 rows.** Raw backup lines confirm it, e.g.
`"details":""` and `"payload":""` where live holds the JSON. The scope row
also drifted on one scalar: `expiry` backup `2036-11-19 07:43:42` vs live
`2036-11-20 15:59:18` (a live re-issue after the backup — drift, not a
defect).

### 3c. Audit chain (mirror): mid-chain by construction, not a restore defect

- First restored `previous_hash` is `10b8793c…`, not `GENESIS_BLOCK_…`.
  The repo's own mirror check (`OracleAuditRepository.verify_audit_chain`,
  linkage ordered by timestamp from GENESIS) therefore fails — on the
  **live** mirror too, because the hashes are identical live/restored. The
  Oracle mirror holds only these 4 predelivery entries (Nov 14) while the
  file ledger holds 23: the mirror is partial by construction, so a
  from-GENESIS chain check is not meaningful for it (gap R3).
- v1 hash recomputation fails even with the **live** details (all 4 rows):
  the entries are v2-signed (`integrity_version: 2` default in
  `AuditEntry`), and the mirror stores no `seq` / `tenant_id` / `action_id`
  / `integrity_version` — the signed payload cannot be rebuilt from the
  mirror at all (gap R4). HMAC signatures were not verified: that needs the
  signing key, which this drill does not read; the live service verifies
  signatures at boot and its `/health` reports `audit_chain_valid: true`.

## 4. "Prove it boots" — the honest answer

- The restored schema is complete and shape-exact; the restored rows fit the
  live schema; the service that owns this schema is `READY` against it right
  now. A restore of the tables followed by a Sentinel start would boot.
- But "boots" is not "restores": the booted Sentinel would have empty audit
  details, empty event payloads, and an empty scope contract. The data that
  makes the audit record meaningful is not in the backup.
- The Oracle `--apply` leg (real load into a scratch Oracle schema) was not
  run: it needs the B2 scratch user, which needs ADMIN credentials plus the
  coordinator's go-ahead recorded on the board entry (runbook Phase B2). No
  go-ahead exists for this task. The scratch SQLite load proves the backup
  bytes decode and load; it does not prove the Oracle INSERT path
  (same gate as INF-023 gap G8).

## 5. Root cause (proven live, gap R1)

`scripts/backup_fleet_databases.py`, `jsonl_encode_value` (lines ~117–118):

```python
if hasattr(value, "read"):  # LOB
    raw = value.read(LOB_CAP_BYTES)   # LOB_CAP_BYTES = 1_000_000
```

`python-oracledb`'s signature is `LOB.read(offset=1, amount=None)` — the
first positional argument is the **offset**, not the length. Verified live
this drill on the SENTINEL `DETAILS` value:

- live value type: `LOB`, `read()` → the full JSON
  (`'{"audit_id": "aud-0143f332f15c", "task_id": "sen-gt-planted", …'`)
- `read(1000000)` → `''` (reads from byte offset 1,000,000, past the end)
- `jsonl_encode_value(value)` → `''` — exactly what the backup file holds

So every CLOB smaller than 1 MB dumps as `""`; a CLOB larger than 1 MB
would dump bytes 1,000,001..end (truncated and shifted). The same code path
backs every agent's dump, so this is fleet-wide, not Sentinel-only:
the Nov 22 backup holds **14,414 empty-string values** (FORGE 5,815, FRIDAY
3,361, INFERENCE 2,598, INTELX 1,216, MEMORA 984, VYRALX 419, SENTINEL 20,
CORTEX 1, FUTURIS 0, STRATEX 0). For Sentinel all 20 are proven lost CLOB
content; for the other agents the same signature is present at scale but
per-column live comparison was not run here — that is the follow-up audit.

**Fix (one line):** `raw = value.read(1, LOB_CAP_BYTES)` — offset 1, amount
capped. Then a fresh backup + a re-drill to close this task. The fix itself
is deliberately NOT in this PR: it changes the fleet backup path and needs
its own reviewed change + test (a fake-LOB unit test pinning
`read(offset, amount)` semantics), then a fresh scheduled backup and a
re-drill. Filed here so the coordinator can route it.

## 6. Gaps found

- **R1 — P0: backup dumps every CLOB < 1 MB as `""` (PROVEN, §5).**
  `scripts/backup_fleet_databases.py:117-118`, `value.read(LOB_CAP_BYTES)`
  passes the cap as the read *offset*. Effect: all JSON/CLOB content in the
  Nov 22 fleet backup is empty (14,414 empty strings; Sentinel 20/20
  proven). Fix: `value.read(1, LOB_CAP_BYTES)`. Follow-up: fix + unit test,
  fresh backup, re-drill REL-089 (or a new drill task) to close.
- **R2 — `--verify` and the manifest cannot detect content loss.**
  `--verify` checks file checksums; `complete: true` is derived from flags,
  failed agents, and verify counts (`derive_manifest_complete`, SEN-022) —
  none of them reads a row's content. A backup can be `complete: true`,
  `verify: 188 OK`, and still be lossy. Follow-up: a content spot-check
  (e.g. re-read one JSON column per agent and fail on empty where live is
  non-empty) in the backup job or the freshness check.
- **R3 — Oracle audit mirror starts mid-chain; `verify_audit_chain` fails
  on the live mirror.** First mirrored `previous_hash` is `10b8793c…`, not
  GENESIS; the mirror holds 4 entries vs the file ledger's 23. Either mirror
  from genesis or scope the check to linkage within the mirror (and say so).
- **R4 — v2 audit entries are not re-verifiable from the mirror.**
  `seq` / `tenant_id` / `action_id` / `integrity_version` are not stored in
  `SENTINEL_AUDIT_LOGS`, so the signed payload cannot be rebuilt and the
  hash cannot be recomputed from the mirror — even with the true details.
  Store the v2 fields or document the mirror as hash-opaque.
- **R5 (carried) — Phase B1 Oracle load still gated (INF-023 G8).** The
  `--apply` path into a scratch Oracle user needs the B2 go-ahead; no
  go-ahead exists for this task. The SQLite scratch load is not an Oracle
  load.

## 7. Observations (not gaps)

- **O1:** `oracle_check_service` reports Server 2, where `Sentinel.service`
  is masked — expected; Sentinel is a Server-1 service (S1 unit verified
  directly above).
- **O2:** No Nov 23 backup had landed by drill time (22:42 IST); the
  scheduled run fires ~11:49 UTC with the known delay pattern (SEN-022
  F-SEN-022-1). The next backup after the R1 fix is the one to re-drill.
- **O3:** Runbook gaps INF-023 G1–G6 (`--from-dir` / `--media` flags that
  do not exist, `LOADABLE/REFUSED` vocabulary, G6 exit-code-on-drift) are
  still present on main; this drill worked around them with the wrapper
  scripts in `~/workspace/muse13/rel089/` rather than the runbook commands.
- **O4:** The drill's own earlier "12 events bad / payload missing" reading
  was a check artifact (my field check treated `""` as missing); the correct
  statement is the content comparison in §3b — the field exists, its value
  is the empty string the backup wrote.

## 8. Files changed

| File | Change |
|---|---|
| `docs/collaboration/TASK-REL-089-BACKUP-RESTORE-DRILL.md` | This evidence doc (NEW) |
| `docs/collaboration/WORK_BOARD.yaml` | REL-089 record CLAIMED → IN_REVIEW (this PR) |

Drill tooling (integrity/scratch/chain/content/LOB scripts + run notes) lives
in the worker's scratch dir `~/workspace/muse13/rel089/`; the repo
deliverable is this doc + the board record. No live database or config was
written to; no service was restarted.

## 9. Rebase note (2026-11-24 ~00:36 IST)

PR #1539 was HELD by the coordinator (watch 7110264278): the board hunk conflicted with current main after the #1541 enforcement flips merged. Rebasing onto main 49126a41 changed nothing in the drill or its findings — only the WORK_BOARD.yaml hunk was rebuilt from the live main blob; this doc is unchanged in substance.

— Muse 13, 2026-11-23 ~23:10 IST. Usage: 16% of free weekly limit
(reset Nov 29, 6:09 PM IST).
