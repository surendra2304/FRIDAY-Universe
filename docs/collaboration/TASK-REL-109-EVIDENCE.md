# TASK-REL-109 — CI test-collection canary proof run 3 (follow-up REL-068/REL-072)

- Worker: Muse 17 · Claim: hub #2045 comment 7236669753 (2026-11-28
  ~14:05 IST), on WATCH262 §C (hub 7236059938) + BE 13:45 §B (hub
  7236383505) + WATCH264 §E (hub 7236513660): "claim REL-109 by next
  run or it re-slots".
- Branch: `muse17/task-rel-109-canary-run3` from main
  `610eccaa80190a26820b09ef3967b5dbffb694ad`.
- Board record verified first-hand on that main (blob `a98f6dd0`):
  CLAIMED / muse_17 / P1. Acceptance: prove CI collects every
  shipped test file (canary + run evidence); extends REL-068/REL-072.

## Verdict (scoped, stated plainly)

PENDING — leg 1 (audit) complete below; leg 2 (CI execution proof on
the PR head) is filled in after PR CI runs. No file shipped in this PR
is skipped by design: the new canary is listed explicitly in the
contracts job and is also collected by the `pytest -q tests`
directory run.

## What this PR changes

- `tests/test_rel109_canary_run3.py` (new canary, stdlib-only):
  asserts its own contracts listing, that every tier-1 gate input
  exists, that the collection guard script is present, and that both
  REL-068 canaries are still listed (run 3 re-proves the chain).
- `.github/workflows/owner-workflows.yml`: the new canary is listed
  in the contracts job pytest invocation next to the two REL-068
  canaries (one line added, no other change).
- This evidence doc. No board hunk (coordinator flips ride the watch
  board PRs).

## Leg 1 — full-repo audit on main 610eccaa (API replication)

Method: the guard's own parse/covers logic replicated against the
live main tree (9,306 entries) and all 28 workflow files fetched via
the GitHub API; test-file definition matches the guard
(`test_*.py` / `*_test.py`). No local pytest — CI is the execution
arbiter (leg 2).

- Test files in repo: **2,043**. PR-triggered workflows scanned:
  **11** of 28. Workflow test references parsed: **731**.
- Covered by a PR-triggered workflow: **482 / 2,043 (23.6%)**;
  uncovered: **1,561**. Trend: 269/1,899 (REL-068, 2026-11-22) →
  279/1,923 (REL-072) → 317/1,945 (REL-093) → 474/2,038 (REL-068
  base proof, 2026-11-28) → 482/2,043 (this run). Coverage grew;
  the backlog did not shrink.
- Stale workflow references (named test files that do not exist):
  **0** — nothing to fix on that leg.
- Per-root covered / total: Cortex 4/150, FRIDAY 111/470, Forge
  41/178, Futuris 19/127, Inference 24/104, IntelX 14/127, Memora
  21/115, Sentinel 7/118, Stratex 49/344, VyralX 51/159, mesh 0/1,
  scripts 0/9, tests 141/141 (directory run).
- Tier-1 gate inputs: **21 / 21 exist** (fixed list in
  `scripts/tier1_collection_gate.py`; the gate step in
  friday-universe-ci.yml runs unconditionally on every PR).
- Both REL-068 canaries present on main:
  `tests/test_rel068_collection_canary.py`,
  `tests/test_rel068_canary_base_proof.py`; the run-3 canary is
  NOT listed pre-edit (expected — this PR adds the listing).
- Probe simulation: a synthetic uncollected path
  (`FRIDAY/tests/test_rel109_probe_uncollected.py`) is covered by no
  reference, i.e. the guard's diff scope would name it UNCOLLECTED.
- Note: the REL-072 evidence doc is NOT on main (404 on
  `docs/collaboration/TASK-REL-072-EVIDENCE.md`, checked first-hand);
  run 3 re-proves from the REL-068 base proof, whose evidence doc is
  the pattern this doc follows.

## Leg 2 — CI execution proof (this PR head)

PENDING — filled in after PR CI runs on the PR head: Owner Workflow
Contracts run + contracts job (guard step + the invocation listing
all three canaries) and the FRIDAY Universe CI/CD tier-1 gate step.
A green contracts job is the execution proof (pytest fails the job
on any collection error or test failure in a listed file).

## Five states

Implemented YES (canary + listing + evidence) / tested PENDING (leg 2
CI on this PR head) / merged NO / deployed N/A (CI configuration;
takes effect on merge) / production-verified NO.

— Muse 17
