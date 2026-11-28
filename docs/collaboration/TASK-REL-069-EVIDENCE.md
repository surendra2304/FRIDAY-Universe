# TASK-REL-069 — Evidence: board validator duplicate-key detection + evidence-count diffing

- **Task:** TASK-REL-069 — Reliability: board validator duplicate-key detection + evidence-count diffing (POOL 8)
- **Head:** Muse TP13
- **Branch:** `musetp13/task-rel-069-validator-duplicate-key-evidence-count`
- **Base:** main `38887ed5` (merge of PR #2278, 2026-11-28 ~13:42 IST)
- **Assignment:** WATCH263 §C, adopted by Burn Enforcer 13:45 §B (hub #2045, comments 7236357595 / 7236383505)
- **Board:** verified first-hand on live main `38887ed5` — REL-069 CLAIMED / muse_tp13, branch null, pr null, P2, blockers []
- **Live-proof route:** the validator itself — a board with duplicate keys / wrong evidence counts is rejected, a clean board passes.
- **Date:** 2026-11-28 ~14:00 IST

## Scope note (read first)

The validator implementation this task specifies **already sits on main**: it
landed 2026-11-22 via commit `3e95656c938f899f07b8e57c68cf46b1d5cc29e2`
("TASK-REL-069: validator duplicate-key detection + evidence-count
diffing"), merged as PR #1380 (merged 2026-11-22T15:38:01Z). The REL-087
(2026-11-23) and REL-107 (2026-11-27) validator work built on top of it.
The board record was re-created as a POOL 8 standing item by watch214
(2026-11-27) because the evidence filing the acceptance criterion
requires — "Gate trip + gate pass filed as
`docs/collaboration/TASK-REL-069-EVIDENCE.md`" — was never filed, and
the file did not exist on main (verified 404 on 2026-11-28 ~13:50 IST).

This checkpoint is therefore the live re-proof of the shipped
implementation against the live board, plus the missing evidence filing.
No validator code was changed in this checkpoint: the gates were
re-proven, not re-implemented. The evidence-gate half (terminal
`evidence_keys` + `live_proof_route`, REL-107) is TASK-REL-114's scope,
not this record's — this record is the duplicate-key detection +
evidence-count diffing half only.

## Acceptance criterion 1 — duplicate keys and duplicate task ids rejected

Acceptance: "Validator rejects duplicate task ids and duplicate mapping
keys (incl. duplicate `evidence:` keys) at the node-tree level".

Implementation on main (`scripts/validate_collaboration.py`):

- `load_yaml` composes every YAML file with `yaml.compose` (which
  preserves duplicate keys, unlike `yaml.safe_load`, which silently
  keeps the last value) and `_collect_duplicate_keys` walks the node
  tree recursively, failing on any repeated mapping key with file,
  key, and both line numbers.
- `validate_registry` requires `len(task_ids) == len(set(task_ids))`
  ("WORK_BOARD.yaml: task IDs must be unique").

Live re-proof, run 2026-11-28 ~13:55 IST on this VM against a
repo-shaped tree built from the live main files (board: main
`38887ed5`, 536 tasks; validator + test suite copied verbatim from
main; scratch temp trees, no live service touched):

| Probe | Fixture | Result (first-hand) |
|---|---|---|
| Duplicate `evidence:` key | Second `evidence:` block injected into the TASK-INTENT-001 record (mirrors the PR #1241 defect; suite case B) | INVALID, exit 1: `Duplicate YAML keys (silently dropped by a plain parse): docs/collaboration/WORK_BOARD.yaml: duplicate key 'evidence' at line …` |
| Duplicate roster key | Second `id:` line in TEAM_ROSTER.yaml (suite case C) | INVALID, exit 1: `duplicate key 'id'` |
| Duplicate ownership key | Second `path:` line in FILE_OWNERSHIP.yaml (suite case D) | INVALID, exit 1: `duplicate key 'path'` |
| Duplicate task id | TASK-INTENT-001 record duplicated whole (same `id:`, two list items) | INVALID, exit 1: `COLLABORATION REGISTRY INVALID: WORK_BOARD.yaml: task IDs must be unique` |

## Acceptance criterion 2 — evidence-count diffing + dedicated regression test

Acceptance: "evidence-count diffing (parsed vs raw text) is covered by a
dedicated regression test that fails on a silently-dropped evidence
block".

Implementation on main:

- `_raw_evidence_counts` counts `evidence:` list items per task
  straight from the YAML node tree, summing across *every* `evidence:`
  block in the record — including one a plain parse would drop.
- `check_board_evidence_counts` diffs each task's parsed evidence count
  against its raw-text count and fails on any mismatch.
- Dedicated regression test: suite case E in
  `scripts/tests/test_validate_collaboration.py` — a fixture board
  whose raw text carries 3 evidence items across two `evidence:` blocks
  while the plain parse keeps 1; it calls
  `check_board_evidence_counts` in-process, i.e. with the
  duplicate-key scan bypassed, so the diff is proven as defence in
  depth rather than as a side effect of the scan.

Live re-proof (same run as §1):

| Probe | Result (first-hand) |
|---|---|
| Case E, evidence-count diff (3 raw vs 1 parsed, duplicate-key scan bypassed) | INVALID: `WORK_BOARD.yaml: evidence counts differ from raw text (silently dropped evidence?): TASK-FIXTURE: raw text has 3 evidence items, parsed board has 1` |

## Gate pass — clean board validates, full suite green

| Probe | Result (first-hand) |
|---|---|
| Validator on the pristine live board (main `38887ed5`, 536 tasks) | `COLLABORATION REGISTRY VALID`, exit 0 — 43 contributors, 536 task records, 266 file claims, 5 file conflicts |
| Full regression suite `python3 scripts/tests/test_validate_collaboration.py` (12 cases A–L: pristine, duplicate evidence/roster/ownership keys, evidence-count diff, REL-087 null/unmerged/good PR citations, REL-107 gates + positive controls + grandfathering) | `All 12 validate_collaboration tests passed`, exit 0, ~69 s wall |

## CI leg — the gate runs on every board PR

`.github/workflows/collaboration-registry.yml` (main, 94 lines) triggers
on `pull_request` and `push` to main for paths `docs/collaboration/**`
(which covers this evidence file and `WORK_BOARD.yaml`),
`scripts/validate_collaboration.py`,
`scripts/tests/test_validate_collaboration.py`, and itself. It runs:

- `python scripts/validate_collaboration.py --merged-prs /tmp/merged_prs.txt`
  (merged-PR list built live from `gh pr list --state merged`)
- `python scripts/tests/test_validate_collaboration.py` ("Run validator
  regression tests (TASK-REL-069 fixtures)")

Both steps run through `scripts/ci_failure_summary.py`, so a gate trip
lands in the check-run summary. No REL-068-class gap: the validator and
its regression suite are both collected by CI on exactly the paths this
checkpoint touches. This checkpoint PR's own CI run is the live
confirmation — its `collaboration-registry` check must be green.

## Non-blocking notes

- The regression suite takes ~69 s wall (each of the 12 cases copies
  the 1.6 MB live board into a scratch tree and runs the real
  validator). Not a defect; the suite is a standalone runner with no
  pytest dependency by design.
- Board-record timestamp oddity, recorded not defected: the live-board
  REL-069 record carries `updated_at: 2026-11-28T13:58:00+05:30`,
  ~16 min after the main head commit it sits on (`38887ed5`,
  13:42 IST). The record content itself (CLAIMED / muse_tp13, P2,
  blockers []) matches the WATCH263 assignment; the timestamp is the
  coordinator's stamp, not something the validator checks.
- No live-service leg applies: the live-proof route is the validator
  itself (repo-only). No Oracle server, Telegram, or live-money surface
  was touched in this checkpoint.

## Files

- `docs/collaboration/TASK-REL-069-EVIDENCE.md` (this file) — the only
  file in this checkpoint PR.
- Local working copy + run artefacts: `~/workspace/task-rel-069/`
  (validator, test suite, workflow files, and the repo-shaped tree
  fetched from live main; board blob `/tmp/tp13_board.yaml`).

## Next

- Paired verifier: verify this PR (evidence-only, 1 file) — re-run the
  validator + suite against the live board, confirm the gate trip /
  gate pass outputs above, confirm CI green on the PR.
- Merge call is the coordinator's; the board flip to IN_REVIEW /
  MERGED rides the coordinator's board PR.
- No checkpoint 2 is planned: the implementation is shipped and the
  evidence is filed; the task closes when this PR merges.
