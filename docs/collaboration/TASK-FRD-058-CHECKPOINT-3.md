# TASK-FRD-058 — Checkpoint 3: WATCH144 test failure fixed

- **Date:** 2026-11-26 ~12:20 IST
- **Branch:** `musetp6/task-frd-058-rsvp-reader` @ `07ad6fa1` (fix commit)
- **Work PR:** #1962 (head `07ad6fa1`, base `4c56e44d`, 12 files +1341/-5)
- **Coordinator:** WATCH144 (hub 7184377833, ~12:05 IST) HELD #1962 — CI 9/10, `test` FAILED.

## The failure (precise, first-hand)

- CI run 45766036925, job `test`: step 12 "Run FRIDAY tier-1 tests" failed.
- Failing test: `FRIDAY/tests/test_ig_frd_058_rsvp.py::test_current_word` — after
  `jump position=3`, `current_word` returned `'fox'`, expected `'jumps'`.
  22/23 tests in the file passed; all other CI checks on the head passed
  (7 success + 2 skipped + the failing `test` job).
- Coordinator reproduced locally first-hand on head `86adaed0` and called it
  an off-by-one. This checkpoint records the diagnosis and the fix.

## Diagnosis: the test expectation was off by one, not the implementation

Text under test: `"The quick brown fox jumps over the lazy dog"` — 9 words,
0-indexed: The=0, quick=1, brown=2, **fox=3**, **jumps=4**, over=5, the=6,
lazy=7, dog=8.

Position semantics are 0-indexed everywhere in this implementation, pinned
by four independent places:

1. `RsvpControlTool` schema: jump position documented as
   `"Word position to jump to (0-based)."`
2. Reading surface `FRIDAY/src/friday/api/rsvp.html`: displays
   `words[Math.min(pos, words.length - 1)]` — `words[position]`.
3. Status text renders `position + 1` as the human word number
   (`word {position + 1} of {total}`).
4. Other tests in the same file pin it: fresh session position 0 →
   `current_word` `"The"`; jump 4 → position 4, percent 4/9; jump 999 →
   clamped to 8 (last index); jump 2 → position 2, remaining 7.

Under those semantics jump(3) must yield `"fox"`. The test jumped to 3
while expecting `"jumps"` (index 4) — a miscount in the test, written
when the file was authored. No implementation change can satisfy the old
expectation without breaking the 0-indexed contract above (e.g. returning
`words[position + 1]` would make position 0 show `"quick"` and break the
surface's `words[pos]` display).

## The fix (commit 07ad6fa1)

`FRIDAY/tests/test_ig_frd_058_rsvp.py`, `test_current_word` only:

- Jump to position 3 now asserts `"fox"` (pins the 0-based semantics).
- Jump to position 4 then asserts `"jumps"` (keeps the original intent:
  jump lands on the named word).
- Comment in the test records the WATCH144 catch and why the expectation
  (not the implementation) changed.

No implementation file changed. No local test run: the standing
execution-risk flag stands — CI is the proof. CI re-runs on the new push;
merge stays held until green per WATCH144.

## Superseded PR #1850 — closed

Per WATCH144 ("TP6: please also close superseded PR #1850 (#1962 replaces
it)"): a superseded note was posted on #1850 and the PR was closed by TP6
this run. #1850 was TP9's earlier FRD-058 attempt, already superseded by
WATCH129; #1962 is the live work PR.

## What is left

1. CI green on head `07ad6fa1` (re-running on push).
2. Coordinator review + merge of #1962 (peer merge only; never own PR).
3. Live leg still GATED: one real article read through the RSVP surface on
   production FRIDAY at two different rates — production clearance owed,
   per WATCH130 pattern. The task is NOT DONE on merge.
4. Queue next: TASK-VYR-087 (P1, supervised cycle 6 candidate pool),
   AVAILABLE / muse_tp6 on main — claim when FRD-058 merges.

— Muse TP6
