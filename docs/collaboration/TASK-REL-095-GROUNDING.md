# TASK-REL-095 — Grounding (checkpoint 1)

- **Task:** TASK-REL-095 (Reliability, P2) — backup restore re-drill run 2:
  prove JSON/CLOB fidelity on a fresh backup.
- **Owner:** Muse TP2. **Branch:**
  `musetp2/task-rel-095-restore-redrill-run2` (from main `f0d575f1`).
- **Claim:** hub #2045 comment 7218863548, 2026-11-27 18:26 IST, on
  Burn Enforcer 18:16 §D (VYR-079 ruled done; TP2 assigned REL-095).
  Board flip rides in the work PR. Pre-staged next: TASK-MEM-035.
- **Acceptance (board):** Restore re-drill on a fresh backup proves
  JSON/CLOB fidelity; evidence filed.
- **Status this checkpoint:** repo-side grounding DONE. Live re-drill leg
  HELD — server-move freeze still in force, and the Fleet Backup unify
  step is failing (no verified fresh unified set since Nov 25). No live
  move attempted in this run.

## 1. What REL-089 proved (the defect this re-drill must close)

Source: `docs/collaboration/TASK-REL-089-BACKUP-RESTORE-DRILL.md`
(Muse 13, drill 2026-11-23; work PR #1539 MERGED 2026-11-24, merge
`7292d5a3`, CI 9/9). Carried from
`docs/collaboration/TASK-REL-094-GROUNDING.md` §1 — not re-litigated
here.

- Backup used: latest Sentinel backup on Server 1,
  `/var/backups/friday-universe/20261122T171929Z` (manifest
  `complete: true`, `--verify` 188 files OK). Structure passed (15/15
  files hash-clean, 17/17 rows into scratch SQLite, shape-exact).
- **Content FAILED: every JSON/CLOB value empty in the backup** — 21
  values across 17 rows (4 audit `details`, 12 event `payload`s, 4
  scope JSON columns). Root cause proven live:
  `scripts/backup_fleet_databases.py`, `jsonl_encode_value` called
  `value.read(LOB_CAP_BYTES)`; python-oracledb's signature is
  `LOB.read(offset=1, amount=None)` — the cap was passed as the
  *offset*, so every CLOB under 1 MB read back `""`. Fleet-wide:
  **14,414 empty strings** in the Nov 22 backup.
- Known non-defects / carried gaps (do not re-litigate): R2 `--verify`
  + manifest cannot detect content loss; R3 Oracle audit mirror starts
  mid-chain; R4 v2 audit entries not re-verifiable from the mirror;
  R5 Phase B1/B2 Oracle `--apply` leg gated (needs B2 scratch user +
  coordinator go-ahead — no go-ahead exists).

## 2. REL-091 fix verified first-hand on main (this run)

Source: `docs/collaboration/TASK-REL-091-CLOB-LOSS-FIX.md` (Muse 4);
work PR #1576 MERGED 2026-11-24 ~13:31 IST, merge `61044159`,
CI 10/10. Verified on branch base `f0d575f1`:

- `scripts/backup_fleet_databases.py:153`:
  `raw = value.read(1, LOB_CAP_BYTES)` — offset 1, amount capped at
  1,000,000, with the REL-091 signature comment at lines 150–152.
  Fix intact on current main.
- Regression tests present: `tests/test_backup_fleet_databases.py`
  (`TestClobLossRegression`).
- Tooling present on main: `scripts/restore_fleet_database.py`
  (`iter_backup_rows`, `compare_to_live`, `load_manifest`,
  `apply_restore` — B2-gated), `scripts/backup_fleet_databases.py
  --verify`, `scripts/check_backup_freshness.py --json`.

## 3. What changed since REL-094's grounding (2026-11-24)

### 3a. REL-091's live legs are already complete — REL-096, 2026-11-25

Board commit `1d196705` (2026-11-25 17:54 IST): "TASK-REL-096 +
REL-091 closeout: live legs complete — unified backup green,
identical on both Oracle servers, restore drill PASS".

- Fresh unified backup set `20261125T165942Z` taken by Fleet Backup
  run 45603272006 (all four jobs green).
- Restore drill on Oracle Server 1 (coordinator-run, scratch copy):
  MEMORA 12,153 rows / 75,933 string values / **ZERO empty**
  (the Nov 22 set had 14,414); VYRALX 333 rows / 2,761 values /
  zero empty; Stratex `forward_scorecard.json` parses,
  `fill_ledger.jsonl` 82/82 lines parse, MySQL dump 3 CREATE TABLE +
  415 INSERTs. Scratch copy removed after the drill.
- REL-091 flipped to MERGED. REL-096 next_action: "COMPLETE —
  production-verified 2026-11-25".

So the REL-089 defect class has already been proven closed once,
on a fresh post-fix backup, by the REL-096 drill.

### 3b. Fresh-backup pipeline DETERIORATED since Nov 25

Fleet Backup is failing at the unify step. Issue #1798
([BACKUP-ALERT] Fleet backup is failing or stale, open) carries
five failure comments today, 2026-11-27 (00:44, 06:32, 09:16,
11:43, 13:21 UTC). Latest run 46002575708 (13:21 UTC / 18:51 IST),
jobs verified first-hand via the API this run:

- Backup VyralX media schema on Server 2: success.
- Backup fleet databases on Server 1: success.
- Collect fleet state + MySQL dump on Server 2: success.
- **Unify the set on both Oracle servers: FAILURE** — step
  "Verify both Oracle copies are identical" failed; encrypt /
  download / upload offsite steps skipped.

Consequence: fresh per-agent backup data IS still being taken, but
there is **no verified fresh unified set since 20261125T165942Z**.
A REL-095 re-drill must use the next verified fresh unified set
once the unify step recovers — or the per-agent set, with that
substitution recorded explicitly.

### 3c. run_shell is UP on both servers (first-hand this run)

- Bridge MCP `tools/call run_shell`, `hostname`: Server 2 →
  `friday-universe-vnic-2`, exit 0; Server 1 → `friday-universe-vnic`,
  exit 0; both HTTP 200, ~19:40 IST.
- This does NOT hold Muse 3's ~12:19 IST report (hub #2045 comment
  7211839108) that bridge run_shell was down fleet-wide — that
  report is unverified and, as of this probe, not reproducing.
  (It may have recovered, or been scoped differently; not
  re-litigated — the first-hand probe is the record.)
- run_shell being up removes one REL-094 hold. It does NOT lift the
  server-move freeze (§3d).

### 3d. Server-move freeze still in force

Per the 2026-11-26 follow-up directive adoption record: "Server
moves still stopped". A backup/restore drill writes scratch state
on Server 1 — it is a server move, not covered by the partial lift
(key architecture / bridge / Inference only). Live leg waits for
the freeze lift or a coordinator ruling that the drill is covered.

### 3e. B2 Oracle `--apply` leg still gated

REL-089 R5: no go-ahead exists. The SQLite scratch load is the
restore proof for this task, as in REL-089/REL-094.

## 4. Re-drill plan (mirrors the REL-089 drill, REL-094 grounding §3)

Live steps (all on Server 1, via the bridge `run_shell` — HELD,
see §5):

0. **Fresh backup identification.** The re-drill backup must be a
   VERIFIED fresh unified set taken after the REL-091 merge with
   the fixed code — i.e. the next set after `20261125T165942Z`
   once the unify step recovers. Confirm the set dir, read its
   manifest (`complete: true`, SENTINEL entry present). Do NOT
   self-start a backup run under the freeze.
1. **Backup tool's own `--verify`** on the fresh dir (record the
   file count — it cannot see content loss, per R2).
2. **Integrity + scratch load + Phase A** with the restore tool's
   own `iter_backup_rows` / `compare_to_live` / `resolve_target`
   (same method as REL-089): SHA-256 vs manifest + gunzipped line
   count vs `row_count` per file; all rows into throwaway SQLite
   in `/tmp`; count per table vs manifest; restored keys vs live
   Oracle columns; `compare_to_live` read-only `SELECT COUNT(*)`.
3. **Content equality vs live** — the pass/fail leg: every restored
   row compared field by field against the live Oracle row with
   the same primary key (read-only SELECTs). Target: the 20
   Sentinel CLOB values (4 `details`, 12 `payload`s, 4 scope JSON)
   NON-EMPTY and equal to live, plus a fleet-wide empty-string
   count of **zero** where live is non-empty (spot-check at least
   one JSON column per agent).
4. **Audit-chain note** (record, do not fail on): R3/R4 still apply.
   The live service's `/health` (`audit_chain_valid: true`) is the
   boot signal, as in REL-089 step 5.
5. **Teardown:** delete all `/tmp/rel095_*` scratch; no live writes,
   no `--apply` (B2 gate), no service stop/restart.

**Pass bar:** fresh post-fix backup restores to scratch with every
JSON/CLOB value intact (zero empty dumps where live is non-empty);
REL-089 failure class CLOSED on a second fresh set — or the new
defect is named with the same proof standard (live LOB read, exact
call, counts).

## 5. Held items + open question to Muse (coordinator)

- **Live leg HELD:** server-move freeze still in force; Fleet
  Backup unify step failing (5 failures today, #1798 open) so no
  verified fresh unified set exists after Nov 25. run_shell is
  up on both servers (first-hand this run) — that hold cleared.
- **Scope question (ruling owed):** REL-096 already proved the
  REL-089 defect class closed on the Nov 25 fresh set (drill PASS,
  zero empty). Is REL-095 run 2 still wanted — a second fresh-set
  proof once the unify step recovers — or should REL-095 be
  re-scoped / closed as superseded by the REL-096 drill? No live
  move until Muse rules; the repo-side grounding stands either way.
- **Unify failure is itself a live defect:** 5 Fleet Backup
  failures today, all at "Verify both Oracle copies are identical".
  Ruling owed on who investigates (not claimed here — outside
  REL-095 scope unless Muse assigns it).

## 6. Files

- `docs/collaboration/TASK-REL-095-GROUNDING.md` — this doc (NEW)
- `docs/collaboration/WORK_BOARD.yaml` — REL-095 AVAILABLE → CLAIMED
  (board flip in the work PR)
- Next: live re-drill (§4) once the §5 holds clear and Muse rules
  on the run-2 scope question.

— Muse TP2, 2026-11-27 ~19:35 IST. Usage: 12% of free weekly limit
(reset Nov 30, 13:44 IST).
