# TASK-STR-083 — EVIDENCE: Leg-2 Saturday-cadence verdict (Muse 8, 2026-11-25)

**Task:** Stratex: RiskGovernor deltas — per-engine trade-count cap and breach
callback, plus Saturday retrain-cadence evaluation.
**Work PR #1851 MERGED** 2026-11-25 20:17:53 IST by surendra2304
(merge `5c901138`, CI 10/10 green on head `3c5d9066`: 8 success, 2 skipped,
0 failed). Branch `muse8/task-str-083` deleted post-merge (verified: refs API
404 + `git ls-remote` empty, 2026-11-25 ~20:30 IST).
**This follow-up PR** files the Leg-2 verdict the repair post promised
(hub #1483 comment 7164943661: "the adopt/reject verdict + evidence doc
follow in the PR once CI reports them"). CI ran `pytest -q` without `-s`,
so the head-to-head print lines never reached the CI log — the numbers in §2
are reproduced first-hand from merged main (§3), not quoted from the log.

## 1. Leg 1 — breach→kill adapter (DONE, merged in #1851)

- `Stratex/paper_engine/breach_kill_adapter.py` (+80) — `on_breach` calls
  `trigger_kill_switch` with the breach event as the reason.
- `Stratex/rigorous_backtest/ig/tests/test_breach_kill_drill.py` (+131) —
  hermetic drill: lock file written, new signals blocked, forced exits
  ledgered `KILL_SWITCH`; temp working dir, synthetic portfolio, observed
  prices only; never touches the live daemon or any server.
- Both files wired into the Stratex tier-1 step
  (`.github/workflows/friday-universe-ci.yml`, REL-068 guard). CI `test` job
  green; tier-1 step "45 passed in 13.30s", including these tests.

## 2. Leg 2 — Saturday-cadence head-to-head (numbers)

- Test: `Stratex/rigorous_backtest/ig/tests/test_saturday_cadence.py`
  (+204), 4 tests, green in CI and reproduced locally (§3).
- Method: same synthetic daily panels (deterministic hand-built price paths —
  mechanics evidence, never performance evidence), same `GateConfig`
  (train 60 / test 14 / step 1, min 3 windows, min 3 pooled trades).
  Baseline = every-window refit; Saturday arm = refit only when the train
  segment's end crosses a Saturday boundary (`SaturdayCadenceFit` wrapper).
- **TREND panel** (steady +0.5%/day uptrend, 4% dip every 25 bars):
  base PF=6.345051767000572 pos=0.881 refits=227 |
  sat PF=6.345051767000572 pos=0.881 refits=34 |
  verdict `{'adopt': True, 'same_or_better_pf': True,
  'same_or_better_positive_fraction': True, 'fewer_refits': True}`.
- **FLIP panel** (uptrend first half, downtrend second — stale params hurt):
  base PF=5.130166087241937 pos=0.841 refits=227 |
  sat PF=4.964113331602475 pos=0.837 refits=34 |
  verdict `{'adopt': False, 'same_or_better_pf': False,
  'same_or_better_positive_fraction': False, 'fewer_refits': True}`.

## 3. How the numbers were obtained (provenance — read before trusting §2)

- CI's `test` job runs `pytest -q` without `-s`, so the `print()` lines from
  the passing head-to-head tests are captured and do NOT appear in the CI log.
  Verified first-hand: `test` job log (job `139265727472`, 507,777 bytes,
  4,550 lines) — grep for `TREND panel` / `FLIP panel` returns nothing; the
  step result is "45 passed in 13.30s".
- Reproduced locally 2026-11-25 ~20:40 IST: fresh shallow clone of main at
  the merge commit `5c901138`, venv + pytest 9.2.0, Python 3.12.3,
  `pytest -s rigorous_backtest/ig/tests/test_saturday_cadence.py -v`
  → **4 passed in 0.10s**, both panels printed verbatim as quoted in §2.
- Determinism: panels are fixed hand-built closes, `START_EPOCH` fixed
  (2026-01-05, a Monday), no randomness, no wall-clock, no network — the
  local run computes the same numbers the CI run computed (same code, same
  tests, same inputs). CI passing the same 4 tests corroborates the code path;
  the `-s` run supplies the printed values.

## 4. Verdict: REJECT — do not adopt the Saturday cadence

- Adoption bar (scope §2): same or better pooled PF / positive-window
  fraction with fewer refits, or a documented robustness gain.
- TREND passes all three conditions (identical PF and positive fraction,
  227 → 34 refits, 6.7× fewer).
- FLIP fails two of three: sat PF 4.964 < base 5.130 (−3.2%), sat pos 0.837
  < base 0.841 (−0.004); fewer refits holds (34 < 227).
- The FLIP panel is the adversarial case the evaluation was designed around —
  a regime change where stale parameters hurt — and the cadence is worse there
  on both quality measures. A cadence that is no-worse on one panel but worse
  on the other does not strengthen the gate. No robustness gain is documented
  (the Saturday arm wins nothing on FLIP).
- Therefore: **REJECT. The gate is unchanged** — no code change in this PR
  beyond this doc + the board flip. Leg 2 closes with this evaluation as
  evidence, per scope §2 ("a negative verdict closes the leg without changing
  the gate").

## 5. Task state

- Leg 1 DONE (merged in #1851). Leg 2 DONE (verdict REJECT, filed here).
  TASK-STR-083 → MERGED (board flip rides in this PR).
- Queue after STR-083: FRD-055 → EARN-026 (board on main `5c901138`:
  both AVAILABLE / owner `muse_8`). STR-047 MERGED (pr 1663), STR-051
  MERGED (pr 1749), EARN-009 MERGED (pr 1826) — all verified first-hand on
  the same board blob.
- Usage: 41% of free weekly limit (checked 2026-11-25 ~20:16 IST; reset
  Nov 27 09:46 IST) — not nearly gone.
