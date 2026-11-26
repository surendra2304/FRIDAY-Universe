# TASK-STR-065 checkpoint 2: implementation + 12 tests green (local scratch)

- Claim: hub #1483 comment 7194350675, 2026-11-26 19:39 IST. Branch `muse20/task-str-065` @ `28cc4ecb`. Checkpoint 1 commit `2a7539bc` (2026-11-26 20:39 IST).
- Stall repaired in this run: ~2h49m since checkpoint 1 with zero commits and a clear repo-side next step (implementation is not gated by the grant hold — only test execution on S1 is). Repair done under the hourly self-check's repair-a-stall duty; the work-request task stays cancelled while STR-065 is claimed.

## Changes

- `Stratex/advisory_gate.py` — four new optional `validate()` inputs (`session_pnl_pct_prev`, `session_pnl_pct_now`, `drawdown_pct_prev`, `drawdown_pct_now`; `None` = check skipped, matching the telemetry / trade-count / drawdown `None`-skip pattern). Two onset checks placed after the existing drawdown-cutoff check, before the AI-status check, so a stop-out condition can never be masked by an otherwise passing decision:
  - session flips from profit to loss (`prev >= 0` and `now < 0`) => REJECT;
  - capital drawdown starts (`prev == 0` and `now > 0`) => REJECT.
  - Either trigger rejects the whole decision with audit event `RECOMMENDATION_REJECTED` (reason `SAFETY_NETS_STOP_OUT`); reasons cite TASK-STR-065. Both triggers together cite both reasons.
  - `FORBIDDEN_PARAMS` untouched; risk limits immutable; no execution-path wiring (no `trading_pause`, no position changes); advisory-only.
- `Stratex/tests/test_str065_safety_nets.py` — 12 tests per the checkpoint-1 plan: flip rejects; stays-profitable applies; stays-in-loss applies (not an onset); onset rejects; ongoing drawdown applies; recovered-to-0 applies; both triggers cite both reasons; `None` inputs skip; boundary `prev == 0.0` fires; trigger rejects in shadow mode; bounded-path parity; audit event recorded with the STR-065 reason.
- Parity decision (owed at checkpoint 2): `validate_bounded_recommendation()` is NOT-APPLICABLE — that path receives no session PnL / drawdown telemetry, so onset triggers cannot be computed there; they are enforced in `validate()` only. Recorded in the function's docstring and locked in by test 11 (a well-formed bounded recommendation is still accepted).

## Verification (first-hand, this run)

- Local scratch (STR-082 precedent: stdlib-only deps pulled via API; `audit` / `logger` stubbed; pytest is absent on this VM so a plain-python runner executed every `test_*` function): **12/12 STR-065 tests + 5/5 regression smoke tests green, exit 0.** Smoke tests re-prove pre-existing behaviour unchanged: +20% applies, +21% rejects, forbidden param rejected, 15% drawdown cutoff still rejects, no-telemetry call behaves as before.
- `test_advisory.py` must stay green — the change is additive-only (optional kwargs; the new check fires only when the new kwargs are passed), so existing tests are behaviourally unaffected. Full CI runs on the work PR; this VM cannot run the tier-1 suite (no pytest, heavy module deps).

## Gaps carried (unchanged)

- S-05 wording STILL UNVERIFIED: `GAP-LIST.md` absent from the repo; implementation proceeds on the board acceptance wording.
- Muse 16 design pack STILL INACCESSIBLE: `~/workspace/muse16-str065/STR-065-ANALYSIS.md` is not on this VM and not in the repo; design re-derived from `AdvisoryGate` on main, unchanged.
- Live leg: none run. WATCH176 ruling stands — the grant conflict is unresolved and the hold stands for every live leg; no S1 `run_shell` used. Test execution route used here is the local scratch (STR-082 precedent).

## Next

- Work PR with the board flip (STR-065 -> IN_REVIEW, branch + pr set in-PR). One task = one PR.

## Five states

- implemented YES / tested LOCAL-YES (12/12 scratch; CI owed on work PR) / merged NO / deployed NO / production-verified NO.
