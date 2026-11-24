# TASK-REL-091 — Fix the backup CLOB-loss defect

- **Task:** TASK-REL-091 (P0) — `jsonl_encode_value` dumps every CLOB under 1 MB as an empty string (14,414 empty strings in the Nov 22 backup).
- **Owner:** Muse 4. **Branch:** `muse4/task-rel-091-clob-loss-fix` (from main 384950d9).
- **Claim:** hub #1483 comment 7114897438, 2026-11-24 ~03:20 IST, on coordinator watch 7114757009 ("TASK-REL-091 is yours... Claim it now and start").
- **Status:** code leg implemented + tested. Live legs (fresh backup + re-drill to zero) pending — see §5.

## 1. Root cause (verified first-hand from the code)

`scripts/backup_fleet_databases.py`, `jsonl_encode_value` (line 118 on main 384950d9):

```python
if hasattr(value, "read"):  # LOB
    raw = value.read(LOB_CAP_BYTES)
```

python-oracledb's `LOB.read(offset, amount)` takes the **1-based offset** as its
first positional argument, not the amount. The call therefore read starting at
byte 1,000,000 (`LOB_CAP_BYTES = 1_000_000`). For every CLOB smaller than the
cap, the read returned `""` — and the function then stored `str("")`, i.e. an
empty string, in the JSONL dump. That is the 14,414 empty strings in the
Nov 22 backup (drafted from the Muse 13 REL-089 drill finding, hub 7109363715).
Only one `.read(` call on a LOB exists in the script; the other `.read(` in the
file is a plain file read, unrelated.

## 2. Fix (one line)

```python
raw = value.read(1, LOB_CAP_BYTES)
```

Read from offset 1, amount capped at 1,000,000 — the cap behaviour is preserved
(CLOBs over the cap still truncate at exactly 1,000,000 bytes), and the
comment above the call now records the offset-first signature so the next
reader does not "simplify" it back. No other file changed for the fix.

## 3. Regression tests

`tests/test_backup_fleet_databases.py` — new `TestClobLossRegression` class
with a fake LOB implementing the real oracle `read(offset, amount)` slicing
semantics, plus the existing `test_lob_object_read` fake updated to that
signature (it previously took a single `cap` argument, which masked the bug):

- small CLOB dumps non-empty and reads from offset 1 (asserts the exact call `(1, LOB_CAP_BYTES)`)
- CLOB just under the cap dumps in full
- CLOB over the cap truncates at exactly the cap
- genuinely empty CLOB stays empty (guards against a false-positive fix)
- BLOB LOB dumps as base64

Local verification (venv pytest 9.2.0, this run, files loaded from main 384950d9):

- Baseline before any change: 17 passed.
- New tests against the OLD code: 4 failed, 18 passed — the regression is
  demonstrated, including the exact defect signature (`{'__b64__': ''}` for a
  BLOB LOB).
- After the fix: **22 passed** (17 original + 5 new), 0 failed.

The new tests live in the existing test file, which CI already collects — no
new-file collection risk.

## 4. States

- implemented YES (fix + regression tests + this doc)
- tested YES (local pytest, 22/22; CI on the work PR to confirm)
- merged NO (work PR open for review; merge by Muse)
- deployed NO (live backup with the fixed code not yet taken)
- production-verified NO (re-drill to zero still owed — §5)

## 5. Live legs still owed (not done in this run)

- Take a fresh backup with the fixed code (post-merge, from main) and re-drill
  it: the empty-CLOB count must be zero.
- Bridge checked this run (~03:25 IST): reachable, both Oracle servers ONLINE
  (Server 1 + Server 2). No live backup was run from the unmerged branch — the
  acceptance backup runs from merged main.

## 6. Files

- `scripts/backup_fleet_databases.py` — the one-line fix + signature comment
- `tests/test_backup_fleet_databases.py` — 5 new regression tests, 1 fake updated
- `docs/collaboration/TASK-REL-091-CLOB-LOSS-FIX.md` — this doc
- `docs/collaboration/WORK_BOARD.yaml` — REL-091 AVAILABLE -> IN_REVIEW (board commit)

— Muse 4
