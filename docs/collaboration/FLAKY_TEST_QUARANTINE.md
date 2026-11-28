# Flaky-test quarantine list

**List:** TASK-REL-108 (Muse TP11). **Enforcement:** TASK-REL-121 (Muse 7).
**Machine-readable form:** `docs/collaboration/FLAKY_TEST_QUARANTINE.yaml`
(read by `scripts/flaky_quarantine.py`; this file is the human-readable form
and must stay in step with it).

## Rules

- Every entry names the flaky test surface, its **owner**, and an **expiry**.
- Quarantined tests are **skipped in PR CI** (`tests/conftest.py`
  TASK-REL-121 hook, mode `pr`) and **run on the nightly gate**
  (`.github/workflows/flaky-quarantine-nightly.yml`, mode `nightly`), so a
  recurrence is caught nightly instead of blocking PRs. Push-to-main gate
  runs are unskipped.
- **Expiry forces a fix-or-remove decision; it never silently extends.**
  An expired entry fails CI collection (`scripts/flaky_quarantine.py
  --check`) until the owner files the decision.
- Grounded entries only: an entry needs an identical-signature recurrence
  record plus a root-cause doc or a diagnosed signature.

## Entries

### 1. Fleet-layout SIGABRT flake (REL-070) — first entry

- **Test surface:** `.github/workflows/validate-monorepo.yml` — `pytest -q tests`
  step (the fleet-layout gate). The step passes, then the process aborts at
  interpreter shutdown: exit 134 = 128 + SIGABRT (6).
- **Quarantined nodeids:** `tests/test_e2e_real_repo_integration.py::TestStratexE2E`
  — the class whose fixture imports `Stratex.dashboard`, historically starting
  the supervision keeper threads behind the abort. The REL-070 regression
  tests (`tests/test_rel070_shutdown_threads.py`) are **not** quarantined:
  they guard the fix and keep running in PR CI.
- **Signature:** daemon-thread `ValueError: I/O operation on closed file` in
  `logging.emit`, then `Fatal Python error: _enter_buffered_busy ... at
  interpreter shutdown, possibly due to daemon threads` from
  `Stratex/api/friday_supervision.py`.
- **First seen / recurrences:** 2026-11-21; 10 of 12 failed gate runs in the
  2026-11-21/22 window, identical signature; 5 further recurrences
  (exit 250 form) with the first fix in tree, through 2026-11-26.
- **Root cause:** `docs/collaboration/TASK-REL-070-EXIT-134-ROOT-CAUSE.md`;
  complete fix in `docs/collaboration/TASK-REL-070-EVIDENCE.md` (PR #2178,
  merged `8048ca75`, TP8 VERIFIED).
- **Owner:** muse_4 (fix author; owns the fix-or-remove decision).
- **Expiry:** 2026-12-05.
- **Status:** quarantined (post-fix watch).
- **Decision on expiry:** zero exit-134 recurrences on the nightly/push gates
  in the window → remove this entry. Any recurrence → re-open a REL-070
  follow-up instead of silently re-quarantining.

— Muse 7 (TASK-REL-121 enforcement); list maintained by muse_tp11 (TASK-REL-108)
