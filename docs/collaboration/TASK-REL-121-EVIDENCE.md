# TASK-REL-121 — Flaky-test quarantine enforcement: skip in PR CI, run nightly

**Worker:** Muse 7. **Branch:** `muse7/task-rel-121-flaky-quarantine`.
**Base:** main `7ecab6ce`. **Claim:** hub #2045 comment 7234261181
(2026-11-28 ~10:20 IST), pool pull per WATCH256 §E.

## What was missing

TASK-REL-108 filed the quarantine list
(`docs/collaboration/FLAKY_TEST_QUARANTINE.yaml`, maintainer muse_tp11) with
the fleet-layout SIGABRT flake as its single grounded entry — but nothing
enforced it: the entry's own text said quarantined tests "still run on their
normal schedule", so a recurrence would still block PRs. REL-121's
acceptance requires the list as `FLAKY_TEST_QUARANTINE.md` with the SIGABRT
flake first, owner + expiry per entry, quarantined tests **skipped in PR
CI** and **run on nightly**.

## Implementation

- `docs/collaboration/FLAKY_TEST_QUARANTINE.md` (new): the list in readable
  form; entry 1 is the fleet-layout SIGABRT flake (REL-070), owner muse_4,
  expiry 2026-12-05, decision-on-expiry unchanged from REL-108.
- `docs/collaboration/FLAKY_TEST_QUARANTINE.yaml`: entry gains `nodeids`
  (`tests/test_e2e_real_repo_integration.py::TestStratexE2E` — the class
  whose fixture imports `Stratex.dashboard`, historically starting the
  keeper threads behind the abort), `pr_ci`/`nightly` fields, and the
  nightly schedule. The REL-070 regression tests are deliberately **not**
  quarantined: they guard the fix and keep running in PR CI.
- `scripts/flaky_quarantine.py` (new): single reader of the YAML list
  (PyYAML when available, fallback parser for the controlled subset).
  Validates owner + expiry per entry; an expired quarantine is a hard
  error — expiry forces the fix-or-remove decision, never extends itself.
  CLI: `--check`, `--nodeids`.
- `tests/conftest.py`: `pytest_collection_modifyitems` hook skips
  quarantined nodeids in PR mode (`GITHUB_EVENT_NAME=pull_request` or
  `FRIDAY_FLAKY_QUARANTINE_MODE=pr`), with the owner/expiry in the skip
  reason; in CI an invalid/expired list fails collection. Nightly and
  local runs execute the tests unskipped.
- `.github/workflows/flaky-quarantine-nightly.yml` (new): nightly 03:23 UTC
  (+ workflow_dispatch), validates the list, then runs the full root suite
  unskipped via the REL-081 runner — full-suite context is what the
  SIGABRT race needs to manifest, and the runner banners any exit-134
  recurrence with its signature check.
- `tests/test_rel121_flaky_quarantine.py` (new): 9 tests pinning the
  loader, fallback-parser parity, expiry/owner validation, class-nodeid
  matching, mode selection, and the MD/workflow wiring.

## Evidence (first-hand, this run)

- `python3 scripts/flaky_quarantine.py --check` →
  `FLAKY QUARANTINE VALID: 1 entries, 1 quarantined nodeids`.
- New tests: **9 passed** (local venv, pytest 9.2.0).
- PR-mode skip proof (local):
  `FRIDAY_FLAKY_QUARANTINE_MODE=pr pytest -rs ...::TestStratexE2E` →
  `SKIPPED [10] ... TASK-REL-121 quarantine: ... (owner muse_4, expiry
  2026-12-05); runs on the nightly gate` — 10 skipped.
- Nightly-mode collection proof (local): same class collects **10 tests,
  0 skipped**; executing them locally stops at missing CI-only deps
  (`dotenv` via `Stratex/config.py`) — the nightly workflow installs
  `requirements-ci.txt`, which is the green-run surface.
- REL-070 regression tests fail locally for the same missing-dep reason
  (pre-existing env limit, unrelated to this change); CI is their proof
  surface, as on main.

## Five states

- implemented YES / tested YES (local, above; PR CI is the deciding run)
- merged NO / deployed NO (nightly schedule arms only on main)
- production-verified NO — the live-proof route needs a PR CI run showing
  the quarantined class skipped plus a green nightly run; the nightly leg
  can only execute after this PR merges (schedules run from the default
  branch). First nightly run post-merge closes it; expiry 2026-12-05
  forces muse_4's fix-or-remove decision either way.

— Muse 7
