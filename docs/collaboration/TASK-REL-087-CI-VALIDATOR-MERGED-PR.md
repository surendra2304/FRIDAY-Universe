# TASK-REL-087 — CI validator must fail on MERGED-with-null/unmerged-PR

## Verdict

Implemented, tested locally, filed for review. The validator now rejects
both defect classes on a test fixture; the live board still validates.

## Diagnosis — the gap

`scripts/validate_collaboration.py` checked task IDs, status validity,
owner registration, titles, next actions, duplicate YAML keys and
evidence counts — but never the `pr` citation of a post-merge task. A
board PR could flip a task to MERGED with `pr: null`, or citing a PR
that never merged, and the registry still reported VALID. The adjacent
evidence: the 2026-11-23 ~22:15 coordinator watch records that board PR
#1525's union rebuild dropped the OBS-014 MERGED flip — board-PR
rebuilds can misstate merge state, and nothing in CI would have caught
a MERGED flip with no merged PR behind it.

Live-board census (main 074f5116, 2026-11-23 ~22:30 IST, 751 records; the in-scope violation count was re-checked on this main after PR #1531 merged):

- MERGED with `pr: null`: 95 records. DEPLOYED/VERIFIED with `pr: null`:
  80 records. None of them was created or updated on/after 2026-11-23;
  the newest are TASK-STR-FWD-030, TASK-REL-063, TASK-FUT-015 (created
  2026-11-21) and TASK-OBS-007 (created 2026-11-22). They predate the
  PR-citation convention (zai / claude-era records, many merged before
  the board tracked PRs at all) and are grandfathered while untouched.
- In-scope post-merge records citing a real PR (e.g. TASK-FUT-016 pr
  1372, TASK-VAL-005 pr 1393) all cite merged PRs; the board cites 462
  distinct PR numbers in total.

## Fix

`scripts/validate_collaboration.py` (TASK-REL-087):

- New `check_board_merged_pr_citations(board, merged_prs=None)`, wired
  into `validate_registry()`. For every record in a post-merge state
  (MERGED, DEPLOYED, VERIFIED — DEPLOYED/VERIFIED imply MERGED)
  created or updated on/after `MERGED_PR_RULE_EFFECTIVE = "2026-11-23"`:
  - `pr` must be a positive integer (bool excluded). Null, missing,
    string, zero or negative citations fail.
  - When a merged-PR list is supplied (`--merged-prs FILE`, one number
    per line), the cited PR must be in the list; otherwise the
    "unmerged-PR" half cannot be checked offline and is skipped, and
    the validator says so in its output.
- An empty merged-PR list is refused outright (it would fail every
  citation); a missing or malformed list file fails the run.
- Grandfathering: records created AND updated before 2026-11-23 stay
  valid with `pr: null`. Touching one bumps its `updated_at` and brings
  it under the rule; the fix is then a one-line `pr` citation.

`.github/workflows/collaboration-registry.yml`:

- New step lists merged PRs with `gh pr list --state merged --limit
  5000 --json number` (repo has ~1,530 PRs) and refuses an empty list.
- The validator step now passes `--merged-prs /tmp/merged_prs.txt`.
- Permissions gain `pull-requests: read` (the token was `contents:
  read` only, which cannot list PRs).

## Fixture proof — tests

`scripts/tests/test_validate_collaboration.py`, cases F–H (all 8 tests
pass; run locally against a scratch tree built from main 074f5116):

- F. TASK-REL-087 record flipped to MERGED with `pr: null` → INVALID,
  exit 1: "TASK-REL-087: status MERGED with null/invalid pr citation".
- G. Same flip citing PR 999999, merged-PR list built from every PR the
  live board cites → INVALID, exit 1: "cites PR #999999 which is not in
  the merged-PR list".
- H. Same flip citing PR 1372 (TASK-FUT-016's merged PR, in the list)
  → VALID, exit 0.
- A–E unchanged and passing (pristine registry VALID; duplicate-key and
  evidence-count cases still fail as before).

Extra local check: the validator run against the pristine board with a
merged-PR list of all 462 cited PRs → VALID, exit 0, "verified against
462 merged PRs". The pristine-board case A (no list) also passes, so
the new check does not break the live board.

## CI run 1 — failure, diagnosed, fixed (same run)

- The validator step PASSED in real CI (run 45225125378, head 19683358):
  "COLLABORATION REGISTRY VALID ... verified against 1225 merged PRs" —
  the new `gh pr list` step and the `--merged-prs` wiring work.
- The regression-tests step FAILED in case F: `set_rel087_merged`
  asserted the REL-087 record reads `status: CLAIMED`, but the test
  suite builds its scratch tree from the PR checkout, where this PR's
  own board flip already sets REL-087 to IN_REVIEW/pr 1536. The
  fixture assumed a live-board state the PR itself changes.
- Fix: `set_rel087_merged` now replaces the status and `pr` lines
  whatever they currently say (regex-anchored), so the fixture works
  against both the pristine board and the PR checkout. Re-verified
  locally in both contexts — all 8 tests pass against the pristine
  main board AND against the PR-checkout board. No validator change
  was needed; the defect was test-only.
- Note for the merge: board PR #1534 merged to main (a96c7bd9) while
  this PR was open; it did not touch the REL-087 record (verified by
  segment diff), so the board flip in this PR still applies cleanly.

## Limits (stated, not hidden)

- The offline validator cannot know a PR's merged state without the
  list; a local run without `--merged-prs` checks only the null/invalid
  half. CI always supplies the list.
- The 95 + 80 legacy null-`pr` post-merge records are grandfathered,
  not backfilled; a future board PR that touches one must add its PR
  citation or CI fails on that PR.
- No live GitHub state was changed by this work beyond the PR itself;
  no service was restarted; no merge by me (workers never merge).

## Files

- `scripts/validate_collaboration.py` — the check.
- `scripts/tests/test_validate_collaboration.py` — cases F–H.
- `.github/workflows/collaboration-registry.yml` — merged-PR list step
  + `--merged-prs` wiring + `pull-requests: read`.
- This evidence doc.
- Board flip CLAIMED → IN_REVIEW rides in the work PR.
