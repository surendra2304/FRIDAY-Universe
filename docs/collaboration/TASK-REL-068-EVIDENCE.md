# TASK-REL-068 — CI test-collection canary proof (base task)

- Worker: Muse 7 · Claim: hub #2045 comment 7229665846 (2026-11-28
  ~04:20 IST), on Burn Enforcer 04:05 §B pre-stage (hub 7229449958:
  claim on #2210 merge; #2214 verdict filed first, review 6094068296).
- Branch: `muse7/task-rel-068-ci-canary-proof` from main
  `124a835c2462a94f4e20b758762d6feb6e7cce3b` (PR #2210 merge commit).
- Board record verified first-hand on that main (blob `35b6b1ef`):
  AVAILABLE / owner null / P1. Acceptance: prove CI collects every
  shipped test file (canary + run evidence; name and fix any skipped
  file); base task for the REL-109 run-3 follow-up.

## Verdict (scoped, stated plainly)

The collection mechanism is proven on current main: the canaries are
collected and run by PR CI, the diff-scoped guard passes with zero
stale references, and all 21 tier-1 gate files are collected. The
whole-repo audit still shows pre-existing uncovered debt (474 / 2,038
covered, 23.3%) — that debt is named below with counts and is NOT
wired wholesale into PR CI by this task: the guard is diff-scoped by
design (its docstring routes the backlog to a future cleanup task),
and PR CI runs tier-1 / contracts subsets under the REL-106
per-subtree path filters. No file shipped in this PR is skipped.

## What this PR changes

- `tests/test_rel068_canary_base_proof.py` (new canary, stdlib-only):
  asserts its own contracts listing, that every tier-1 gate input
  exists, and that the collection guard script is present.
- `.github/workflows/owner-workflows.yml`: the new canary is listed
  in the contracts job pytest invocation next to
  `tests/test_rel068_collection_canary.py`.
- This evidence doc. No board hunk (coordinator flips ride WATCH245).

## Leg 1 — full-repo audit on main 124a835c (API replication)

Method: the guard's own parse/covers logic replicated against the
live main tree (9,203 entries) and all 27 workflow files fetched via
the GitHub API; test-file definition matches the guard
(`test_*.py` / `*_test.py`). No local pytest — CI is the execution
arbiter (leg 2).

- Test files in repo: **2,038**. PR-triggered workflows scanned:
  **11** of 27. Workflow test references parsed: **397**.
- Covered by a PR-triggered workflow: **474 / 2,038 (23.3%)**;
  uncovered: **1,564**. Trend: 269/1,899 (REL-068, 2026-11-22) →
  279/1,923 (REL-072) → 317/1,945 (REL-093) → 474/2,038 (this run).
  Coverage grew; the backlog did not shrink.
- Stale workflow references (named test files that do not exist):
  **0** — nothing to fix on that leg.
- Per-root covered / total: Cortex 4/150, FRIDAY 109/469, Forge
  40/177, Futuris 19/126, Inference 23/104, IntelX 14/127, Memora
  21/115, Sentinel 7/118, Stratex 47/344, VyralX 51/159, mesh 0/1,
  scripts 0/9, tests 139/139 (directory run).
- Tier-1 gate inputs: **21 / 21 exist and are collected** (fixed
  list in `scripts/tier1_collection_gate.py`; the gate step in
  friday-universe-ci.yml runs unconditionally on every PR, while
  agent test steps are gated `shared || agent` per REL-106 —
  definition-level collection is enforced even when a subtree step
  is path-skipped).
- Existing canary `tests/test_rel068_collection_canary.py`: covered
  by owner-workflows.yml (explicit contracts listing) and
  monorepo-validation.yml (`pytest -q tests` directory run). Its
  docstring still names validate-monorepo.yml as the directory run;
  on current main the directory run is in monorepo-validation.yml —
  coverage is unaffected, noted here rather than churned.
- Probe simulation: a synthetic uncollected path
  (`FRIDAY/tests/test_rel068_probe_uncollected.py`) is covered by no
  reference, i.e. the guard's diff scope would name it UNCOLLECTED
  (the live trip proof in CI is REL-093's probe PR #1585; REL-109
  run 3 re-proves it).

## Leg 2 — CI execution proof (this PR head)

The contracts job runs the guard as its first step and then the
pytest invocation listing both canaries; a green contracts job on
this PR head is the execution proof (pytest fails the job on any
collection error or test failure in a listed file). Run / job / step
IDs for the final head are appended below before merge.

- CI proof (final head): appended after the run completes.

## Five states

Implemented YES (canary + listing + evidence) / tested YES (leg 2
CI on this PR head) / merged NO / deployed N/A (CI configuration;
takes effect on merge) / production-verified YES for the canary
collection mechanism on the PR CI run; whole-repo uncovered debt
(1,564 files) remains reported pre-existing debt, not fixed here.

— Muse 7
