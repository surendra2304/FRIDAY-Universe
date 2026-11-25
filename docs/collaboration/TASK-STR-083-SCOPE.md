# TASK-STR-083 — SCOPE (Muse 8, 2026-11-25)

**Task:** Stratex: RiskGovernor deltas — per-engine trade-count cap and breach
callback, plus Saturday retrain-cadence evaluation.
**Claim:** hub #1483 comment 7155163914 (2026-11-25 ~12:17 IST), on coordinator
watch081 assignment (7154336804). Branch `muse8/task-str-083` @ main `fbc26ea4`.
**Queue:** STR-083 (head) → STR-084 → EARN-009. STR-047 stays BLOCKED (owner
freeze; no S1-allowlist clearance).

## 1. What already exists on main (verified first-hand, main `fbc26ea4`)

- `Stratex/rigorous_backtest/ig/risk_governor.py` (9,863 B, sha `fd09fd2b`)
  — TASK-IG2-STR-16, package S-15, item DZ-QETCTygV. Research-only, stdlib-only.
  **Already implements both named deltas as a component pattern:**
  per-engine trade-count cap (`max_trades_per_engine`, latch + `blocked`) and
  breach callback (`on_breach`, fires exactly once per blocking, recorded in
  `self.breaches`). Per-trade risk cap (0.1% default) + heat cap (2%) mirror
  FWD-006. Explicitly NOT wired to anything live: "the live daemon never
  imports this module".
- `Stratex/rigorous_backtest/ig/tests/test_risk_governor.py` (7,185 B,
  sha `1f97a241`, 203 lines, 14 test fns) — includes
  `test_trade_count_cap_breach_callback_fires_once_and_latches` and
  `test_research_only_no_io_or_production_imports` (the governor module must
  stay free of production imports).
- `Stratex/rigorous_backtest/ig/walkforward_gate.py` (12,898 B, sha `b421079a`)
  — TASK-IG2-STR-04, PR #683 MERGED. Rolling (train 200 / test 100 / step 100
  bars) windows, `fit_fn` refits every window, pass bar = pooled expectancy
  > 0, pooled PF >= 1.2, >= 60% windows positive. **No calendar/retrain
  cadence concept** — windows are bar-count, not weekday-anchored.
- `Stratex/paper_engine/kill_switch.py` (8,927 B, sha `36988e87`) —
  `trigger_kill_switch(reason, portfolio, ...)` is the kill action: writes the
  lock file (blocks new signals), flattens open positions with realistic
  costs, ledgers `reason=KILL_SWITCH`. Paper-engine code, not stdlib-only
  (imports `atomic_io`, `logger`, `research_phase9.cost_engine`).

## 2. What STR-083 still has to build (the delta)

**Leg 1 — breach callback fires the kill action.** Nothing on main wires
`on_breach` to `trigger_kill_switch`. Build a breach→kill adapter in a
separate module (the governor's research-only contract forbids production
imports inside `risk_governor.py` itself): the adapter passes an `on_breach`
that calls `trigger_kill_switch` with the breach event as the reason, then a
**breach drill** proving the callback fires the kill action — lock file
written, new signals blocked, forced exits ledgered `KILL_SWITCH`. The drill
must be hermetic (temp working dir, synthetic portfolio, observed prices
only) and must never touch the live daemon or any server.

**Leg 2 — Saturday retrain-cadence evaluation (S-16).** Evaluate the
"ML retrain every Saturday" walk-forward cadence against the existing gate:
add a calendar-aware retrain schedule to the gate evaluation (refit only at
Saturday boundaries; bars carry `time`, so weekday anchoring is derivable)
and run it head-to-head against the current every-window refit on the same
panels. **Adopt only if it strengthens the gate** (same or better pooled PF
/ positive-window fraction with fewer refits, or a documented robustness
gain). Verdict recorded either way; a negative verdict closes the leg
without changing the gate.

## 3. Acceptance mapping

- "Both deltas live" = cap + callback already live as the research component
  (IG2-STR-16); this task makes them live as a **wired** behaviour via the
  breach→kill adapter + drill.
- "Breach drill proving the callback fires the kill action" = Leg 1 drill
  test, green in CI.
- "Cadence verdict recorded" = Leg 2 head-to-head numbers + adopt/reject
  verdict filed in the work PR.
- Out of scope: the item's own strategy (no rules in evidence), its Telegram
  signals product, any live-daemon change, any server action (owner freeze).

## 4. Risks / open questions

- Q1: which paper-engine harness should own the adapter (new module under
  `Stratex/rigorous_backtest/ig/` vs `Stratex/paper_engine/`)? Decided during
  implementation; the governor's no-production-import test constrains it.
- Q2: `time` field format in gate bars (epoch vs string) — determines the
  Saturday-anchoring implementation; read `walkforward_gate.py` fully + its
  test before coding Leg 2.
- The S-15/S-16 source packages are video/package records, not repo files;
  the acceptance text above is the build contract, not the videos.

## 5. Next steps

1. Read `walkforward_gate.py` + `test_walkforward_gate.py` in full; confirm
   bar `time` format and `fit_fn` contract.
2. Prototype the breach→kill adapter + drill; add tests; run the ig test
   suite.
3. Run the Saturday-cadence head-to-head; record the verdict.
4. Open the work PR when done (board flip AVAILABLE → IN_REVIEW rides in it,
   per watch081; no checkpoint PRs per owner order 7143628341 rule 1).
