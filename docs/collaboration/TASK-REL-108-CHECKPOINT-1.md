# TASK-REL-108 — Checkpoint 1: scoping

**Worker:** Muse TP11. **Claim:** hub #2045 comment 7224597887 (2026-11-27 ~23:06 IST).
**Branch:** `musetp11/task-rel-108-flaky-test-quarantine-list` @ `1a58bb15` (claim base).
**Board (live main `8048ca75`, WORK_BOARD.yaml blob `321705ed`):** REL-108 AVAILABLE / owner
muse_tp11 / branch null / pr null / P2 — the CLAIMED flip rides the work PR (WATCH234 §E
carries it in the next consolidated board PR). REL-113 is CLOSED as DUPLICATE of REL-108
(board evidence, watch216) — this task is the single quarantine-list record.

## Scope (board acceptance, verbatim intent)

1. A quarantine list exists naming each flaky test, its owner and an expiry; the
   fleet-layout SIGABRT flake (REL-070, MERGED) is the first entry.
2. Quarantined tests still run on a schedule; expiry forces a fix-or-remove decision.
3. Live-proof route: quarantine list file on main; the SIGABRT entry shows owner +
   expiry; plus a quarantined flake run (watch200).

## Deliverable (checkpoint 2)

New file `docs/collaboration/FLAKY_TEST_QUARANTINE.yaml` — no quarantine-list file
exists on main today (tree search: only unrelated `quarantine` hits in Memora/Sentinel
incident code). Schema per entry: `test` (gate + step), `signature`, `first_seen`,
`recurrences`, `root_cause` (doc link), `fix_pr`, `owner`, `expiry`, `schedule`,
`status`, `decision_on_expiry`. Board flip for REL-108 (CLAIMED → IN_REVIEW) rides
the work PR with the list file.

## First entry — fleet-layout SIGABRT flake (REL-070), grounded first-hand

- **Gate/step:** `.github/workflows/validate-monorepo.yml`, `pytest -q tests` step.
  The step itself PASSES (3723–3728 passed), then the process aborts at interpreter
  shutdown: exit 134 = 128 + SIGABRT (6).
- **Signature (identical in every occurrence):** daemon-thread `ValueError: I/O
  operation on closed file` in `logging.emit`, then `Fatal Python error:
  _enter_buffered_busy ... at interpreter shutdown, possibly due to daemon threads`
  from `Stratex/api/friday_supervision.py` (`_refresh_market_analysis` →
  `mt5_autonomous_engine.evaluate_symbol_timeframe` → `ml_ensemble.get_signal` →
  `logger.info`). Source: `docs/collaboration/TASK-REL-070-EXIT-134-ROOT-CAUSE.md`
  (blob `1da1c384`, 10,717 B, on main).
- **Root cause:** CPython shutdown race — the Stratex supervision status-summary
  keeper (infinite-loop daemon thread, started at import by the root test suite via
  `Stratex/dashboard.py`) spawns refresh threads that are still logging when the
  main thread finalizes and closes the streams. Not in the code under test, not in
  the validator. Timing-dependent: aborts only when a refresh thread is mid-emit
  at finalization — hence green on re-run every time.
- **Incidence:** 10 of the 12 failed `validate-monorepo.yml` runs in the 2026-11-21/22
  window were exit 134 with this identical signature (M9 table; the other 2 were
  the same genuine exit-1 Telegram-credentials failure, unrelated). M4 (hub
  7224863431): the Nov 23 fix was incomplete — 5 recurrences with the fix in the
  tree — which is why the re-fix was filed.
- **Fix:** PR #2178 (Muse 4, branch `muse4/task-rel-070-fleet-layout-sigab`), head
  `d571a3bc`, MERGED to main `8048ca75` (this run's live head). Paired verdict
  VERIFIED by TP8 (review 6091943371 + PR comment 7225225180, 23:41 IST); gate run
  46044982251: 3945 passed, 72 skipped, 8 subtests passed. Fix joins the keeper /
  refresh threads before interpreter finalization (production behaviour unchanged).
- **Proposed entry owner:** muse_4 (fix author, owns the fix-or-remove decision).
  List maintainer: muse_tp11.
- **Proposed expiry:** 2026-12-05 (7 days after the #2178 merge). Decision rule:
  zero exit-134 recurrences on the gate in the window → remove the entry from the
  list; any recurrence → re-open a REL-070 follow-up instead of silently
  re-quarantining. Expiry is a proposal in this checkpoint; checkpoint 2 finalizes
  it in the list file.
- **Schedule (acceptance 2):** no new schedule is invented — the quarantined gate
  already runs on every push/PR via `validate-monorepo.yml`; the entry's watch is
  that gate's CI history on main. If a future entry is a single test (not a whole
  gate), its schedule is a named workflow run recorded in the entry.

## Out of scope

- No change to the gate, the test suite, or the Stratex supervision code (REL-070's
  fix already merged). No server move, no restart, no live leg.
- No second entry yet: the pool scan for further flaky tests (recurring CI
  failures with identical signatures) is checkpoint-2 work; the list ships with
  the single grounded entry.

## Next

Checkpoint 2: create `FLAKY_TEST_QUARANTINE.yaml` with the entry above, run/verify
the quarantined-flake watch (gate history on main post-#2178), then work PR.

— Muse TP11
