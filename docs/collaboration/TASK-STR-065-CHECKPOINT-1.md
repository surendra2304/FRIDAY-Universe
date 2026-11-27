# TASK-STR-065 checkpoint 1: scoping — Safety Nets stop-out rule into the advisory/risk gate

- Claim: hub #1483 comment 7194350675, 2026-11-26 19:39 IST. Branch `muse20/task-str-065` @ `28cc4ecb` (main at claim time; merge of PR #1990).
- Board on main (blob `b60200a0`, fetched 2026-11-26 ~20:30 IST): STR-065 CLAIMED / muse_20 / branch null / pr null. FRG-025 IN_REVIEW / muse_20 / pr 1972 (work PR #1972 MERGED 18:03 IST, merge `087e05d6`). SEN-033 AVAILABLE / muse_20 (pre-staged next).
- Decision: implement the rule's two triggers as guardrail checks in `AdvisoryGate.validate()` (`Stratex/advisory_gate.py`, 580 lines on main, read first-hand). REJECT verdict with STR-065-cited reasons; audit event `RECOMMENDATION_REJECTED`, same pattern as the existing gate rejections.

## Overlap verdict: NO OVERLAP with FWD-006 daily breaker / DD kill (first-hand)

- `Stratex/testnet_engine/daily_loss_breaker.py` (161 lines): trips when day PnL <= `-loss_limit_pct` of day-start equity (the 3% daily breaker); pauses ALL new entries via the `trading_pause` flag; never touches open positions. A threshold breach on cumulative day PnL, on the execution path.
- `Stratex/risk/drawdown_controller.py` (197 lines): staged peak-to-trough thresholds — 5% WARNING (sizing x0.7), 8% ACTION (halve open, halt entries), 12% CRITICAL (flatten, halt, 48h paper recovery). Execution-path sizing/halt.
- `AdvisoryGate` today has only a 15% hard drawdown cutoff (`MAX_DRAWDOWN_CUTOFF_PCT`) — a late threshold, not an onset trigger.
- STR-065 triggers are onset / sign-change signals in the advisory layer: (1) session flips from profit to loss; (2) capital drawdown starts. Different layer (advisory validation, not execution), different trigger semantics (onset vs cumulative/staged thresholds), different effect (REJECT advisory parameter changes vs pause entries / flatten positions). Adjacent, not duplicative. The 15% cutoff and the staged controller are the boundary neighbours. Confirms Muse 16's read-only verdict.

## Gaps (honest)

- S-05 wording STILL UNVERIFIED: `GAP-LIST.md` is absent from the repo (full recursive tree listing checked 2026-11-26 ~20:30 IST); Muse 16 also could not find it (hub 7159669287). Implementation proceeds on the board acceptance wording; the exact source phrasing is unconfirmed. Flag for Muse/coordinator if the wording matters for the trigger definitions.
- Muse 16 design pack INACCESSIBLE: `~/workspace/muse16-str065/STR-065-ANALYSIS.md` is not in this VM's workspace and not in the repo, so the drafted design + 12 tests cannot be consumed sight-unseen. Design below is re-derived from `AdvisoryGate` on main.

## Design (scoped)

- Location: `AdvisoryGate.validate()` only. Parity in `validate_bounded_recommendation()` is a decision owed at checkpoint 2 (either a parity check or an explicit NOT-APPLICABLE with reason).
- New optional inputs: `session_pnl_pct_prev`, `session_pnl_pct_now` (flip = prev >= 0 and now < 0); `drawdown_pct_prev`, `drawdown_pct_now` (onset = prev == 0 and now > 0). Existing `current_drawdown_pct` stays as the 15% cutoff input. `None` = check skipped, consistent with the existing telemetry / trade-count / drawdown `None`-skip pattern.
- Check placement: after the existing drawdown-cutoff check, before the AI-status check; to be confirmed at implementation.
- Invariants preserved: advisory-only; `FORBIDDEN_PARAMS` untouched; risk limits immutable; no new execution-path wiring (no `trading_pause`, no position changes).

## Tests (planned, 12; new file `Stratex/tests/test_str065_safety_nets.py`; `test_advisory.py` must stay green)

1. Session flip profit -> loss => REJECT.
2. Session stays profitable => no flip trigger.
3. Session stays in loss (prev < 0, now < 0) => no flip trigger (not an onset).
4. Drawdown onset (0 -> >0) => REJECT.
5. Drawdown ongoing (prev > 0) => no onset trigger.
6. Drawdown recovered to 0 => no trigger.
7. Both triggers together => REJECT, both reasons cited.
8. `None` inputs => checks skipped.
9. Boundary: prev session PnL exactly 0.0, now < 0 => flip fires.
10. Trigger active in shadow mode => still REJECT (safety beats shadow).
11. Bounded-recommendation path: parity decision recorded at checkpoint 2.
12. Audit event recorded with the STR-065 reason.

## Next

- Checkpoint 2: implementation + 12 tests green. Test execution route owed at checkpoint 2 (S1 via bridge `run_shell`, the STR-068 precedent, or local if this runtime passes its execution check).
- Then work PR with the board flip (STR-065 -> IN_REVIEW, branch + pr set in-PR).

## Five states

- implemented NO / tested NO / merged NO / deployed NO / production-verified NO.
