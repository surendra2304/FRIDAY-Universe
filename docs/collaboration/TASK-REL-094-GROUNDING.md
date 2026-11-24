# TASK-REL-094 — Grounding (checkpoint 1)

- **Task:** TASK-REL-094 (Reliability, P1) — backup restore re-drill after the
  REL-091 CLOB fix: prove JSON/CLOB fidelity on a fresh backup.
- **Owner:** Muse 19. **Branch:** `muse19/task-rel-094` (from main `ce5c1bd4`).
- **Claim:** hub #1483 comment 7130628034, 2026-11-24 ~17:20 IST, on the
  coordinator 16:57 watch (blocked-head rule — skip blocked EARN-005, take
  the next queued task). Board flip rides in the work PR.
- **Acceptance (board):** fresh backup restored to a scratch location with
  every JSON/CLOB value intact; the REL-089 failure class is closed or the
  new defect is named.
- **Status this checkpoint:** repo-side grounding DONE. Live re-drill leg
  HELD — no fresh post-fix backup verified from the repo side, no
  `run_shell` grant, and the owner stop order still freezes all server
  moves except key architecture / bridge work / Inference (coordinator
  17:17 watch 7130910007). No live move attempted in this run.

## 1. What REL-089 proved (the defect this re-drill must close)

Source: `docs/collaboration/TASK-REL-089-BACKUP-RESTORE-DRILL.md`
(Muse 13, drill 2026-11-23 ~22:40–23:10 IST; work PR #1539 MERGED
2026-11-24 ~05:05 IST, merge `7292d5a3`, CI 9/9).

- Backup used: latest Sentinel backup on Server 1,
  `/var/backups/friday-universe/20261122T171929Z` (scheduled Fleet Backup
  run 45019170405; manifest `complete: true`, `--verify` 188 files OK).
- Structure passed: 15/15 files hash-clean, 17/17 rows loaded into a
  throwaway SQLite scratch DB, restored columns shape-exact vs live Oracle
  schema, scalar columns byte-identical, Phase A 14 match / 1 drift
  (SENTINEL_EVENTS 12 → 25, live writes since backup — expected drift).
- **Content FAILED: every JSON/CLOB value empty in the backup** — 21 values
  across 17 rows: 4 audit `details`, 12 event `payload`s, 4 scope JSON
  columns (`allowed_targets`, `in_scope_declarations`,
  `out_of_scope_declarations`, `scope_contract`). A restore would boot
  Sentinel with its audit details, event payloads and scope contract empty.
- Root cause proven live: `scripts/backup_fleet_databases.py`,
  `jsonl_encode_value` called `value.read(LOB_CAP_BYTES)`; python-oracledb's
  signature is `LOB.read(offset=1, amount=None)` — the cap was passed as
  the *offset*, so every CLOB under 1 MB read back `""`. Fleet-wide:
  **14,414 empty strings** in the Nov 22 backup (FORGE 5,815, FRIDAY 3,361,
  INFERENCE 2,598, INTELX 1,216, MEMORA 984, VYRALX 419, SENTINEL 20,
  CORTEX 1, FUTURIS 0, STRATEX 0).
- Known non-defects / carried gaps (do not re-litigate in the re-drill):
  R2 `--verify` + manifest cannot detect content loss (checksums/counts
  only); R3 Oracle audit mirror starts mid-chain (`verify_audit_chain`
  fails on the live mirror too); R4 v2 audit entries are not re-verifiable
  from the mirror (no `seq` / `tenant_id` / `action_id` /
  `integrity_version` stored); R5 Phase B1/B2 Oracle `--apply` leg gated
  (needs B2 scratch user + coordinator go-ahead — no go-ahead exists).
  The drill made no live writes: no `--apply`, no service restarts, all
  scratch in `/tmp`, deleted afterwards.

## 2. What REL-091 fixed (verified first-hand on main `ce5c1bd4`)

Source: `docs/collaboration/TASK-REL-091-CLOB-LOSS-FIX.md` (Muse 4);
work PR #1576 **MERGED 2026-11-24T08:01:34Z (~13:31 IST)**,
merge commit `61044159`, CI 10/10 on head `8a4facbd` (8 success, 2 skipped),
+155/-7, 4 files, 2 commits — verified first-hand this run.

- The one-line fix, `scripts/backup_fleet_databases.py:122` (verified on
  main `ce5c1bd4`, with the REL-091 signature comment at lines 118–121):
  `raw = value.read(1, LOB_CAP_BYTES)` — offset 1, amount capped at
  1,000,000. CLOBs over the cap still truncate at exactly the cap.
- Regression tests in `tests/test_backup_fleet_databases.py`
  (`TestClobLossRegression`, fake LOB with real `read(offset, amount)`
  slicing): small CLOB non-empty + exact call `(1, LOB_CAP_BYTES)`, just
  under cap in full, over cap truncates at exactly the cap, genuinely
  empty CLOB stays empty, BLOB dumps as base64. Local pytest 22/22
  (17 original + 5 new); 4 failed against the OLD code, demonstrating the
  regression.
- REL-091's own live legs (fresh backup + re-drill to zero) were still owed
  at filing — **that is exactly this task (REL-094)**.

## 3. Re-drill plan (mirrors the REL-089 drill, §2 of its doc)

Tooling on main `ce5c1bd4` (verified first-hand):
`scripts/restore_fleet_database.py` — `iter_backup_rows(backup_dir,
table_entry)`, `compare_to_live(conn, entry, log=print)`,
`load_manifest(backup_dir, agent)`, `apply_restore(...)` (B2-gated);
`scripts/backup_fleet_databases.py --verify`;
`scripts/check_backup_freshness.py --json`.

Live steps (all on Server 1, via the bridge `run_shell` — HELD, see §4):

0. **Fresh backup identification.** List `/var/backups/friday-universe/`:
   the re-drill backup must be taken AFTER the REL-091 merge
   (2026-11-24 ~13:31 IST) with the fixed code from main. The daily
   scheduled run fires ~11:49 UTC (~17:19 IST); whether the Nov 24 run
   landed with fixed code is **unverified from the repo side** — first
   live step is to confirm a post-fix backup dir exists and read its
   manifest (`complete: true`, SENTINEL entry present). If none exists,
   a fresh backup with the fixed code must be taken first (scheduled run
   or coordinator-directed manual run — NOT self-started under the freeze).
1. **Backup tool's own `--verify`** on the fresh dir (expect 188 files OK
   equivalent; record the count — it cannot see content loss, per R2).
2. **Integrity + scratch load + Phase A** with the restore tool's own
   `iter_backup_rows` / `compare_to_live` / `resolve_target` (same method
   as REL-089): SHA-256 vs manifest + gunzipped line count vs `row_count`
   per file; all rows into throwaway SQLite in `/tmp`; count per table vs
   manifest; restored keys vs live Oracle columns; `compare_to_live`
   read-only `SELECT COUNT(*)`.
3. **Content equality vs live** — the pass/fail leg: every restored row
   compared field by field against the live Oracle row with the same
   primary key (read-only SELECTs). Target: the 20 Sentinel CLOB values
   (4 `details`, 12 `payload`s, 4 scope JSON) NON-EMPTY and equal to live,
   plus a fleet-wide empty-string count of **zero** where live is
   non-empty (spot-check at least one JSON column per agent — the REL-089
   follow-up audit; Sentinel is the proven set, the other agents are the
   same signature at scale).
4. **Audit-chain note** (record, do not fail on): R3/R4 still apply — the
   mirror starts mid-chain and v2 entries are not re-verifiable from it.
   The live service's `/health` (`audit_chain_valid: true`) is the boot
   signal, as in REL-089 step 5.
5. **Teardown:** delete all `/tmp/rel094_*` scratch; no live writes, no
   `--apply` (B2 gate), no service stop/restart.

**Pass bar:** fresh post-fix backup restores to scratch with every
JSON/CLOB value intact (zero empty dumps where live is non-empty);
REL-089 failure class CLOSED — or the new defect is named with the same
proof standard (live LOB read, exact call, counts).

## 4. Held items (live leg — not attempted this run)

- **Fresh backup existence unverified.** No post-fix backup dir confirmed
  from the repo side; the hub shows no fresh-backup landing report since
  the ~13:31 IST merge. First live step (§3 step 0) settles it.
- **No `run_shell` grant for REL-094.** Standing client is read-only;
  the MEM-026 grant question is still open and its live leg is HELD per
  the 17:17 watch — a REL-094 grant (or a combined drill grant) is owed
  via the coordinator before any S1 command runs.
- **Owner stop order (partial lift 17:26 IST):** lifted ONLY for key
  architecture work, bridge work, and the Inference move (already done).
  All other server moves remain FROZEN. A backup/restore drill writes to
  `/var/backups` and scratch state on S1 — it is a server move, not
  covered by the lift. Live leg waits for the freeze lift (or a
  coordinator ruling that the drill is covered).
- **B2 Oracle `--apply` leg** still gated (REL-089 R5) — no go-ahead
  exists; the SQLite scratch load is the restore proof for this task,
  as in REL-089.

## 5. Files

- `docs/collaboration/TASK-REL-094-GROUNDING.md` — this doc (NEW)
- `docs/collaboration/WORK_BOARD.yaml` — REL-094 AVAILABLE → CLAIMED
  (board flip in the work PR)
- Next: re-drill content-check script (adapted from the REL-089 drill
  method, against `scripts/restore_fleet_database.py` on main), then the
  live re-drill once the §4 holds clear.

— Muse 19, 2026-11-24 ~18:17 IST. Usage: 7% of free weekly limit
(reset Dec 1, 12:06 AM IST).
