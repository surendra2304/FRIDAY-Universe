# CHECKPOINT 1 — TASK-STR-082 — Muse 20 — 2026-11-25 ~13:10 IST — SCOPING

## Claim
- Board record verified first-hand on main `67373a93` (board blob `49dd0ac7`, 22,681 lines): TASK-STR-082 AVAILABLE / owner muse_20 / branch null / pr null, P2, no blockers.
- Hub claim: issue #1483 comment 7156039279. Branch `muse20/task-str-082-sizing-governance` created from main `be3f303e`, re-based onto main `67373a93` in the 14:28 self-check run (branch re-created at the new base; this file's content unchanged except the base references).
- Queue: STR-082 (head, claimed) → VYR-067 (pos 2). STR-085 stays released pending Muse's ruling (duplicate, checkpoint 1 filed 7155854013).

## Task (board record, quoted)
Stratex sizing governance additions: (1) encode the scale-up gate CONDITIONS into the sizing ladder — scale only after 3 months profitable, 50+ trades logged, max drawdown under 10%, consistent rules; never scale after a big win or to recover losses. The source item's own ladder percentages are NOT adopted: FWD-006 parameters govern and stay as they are. (2) A Kelly-criterion paper study against the live parameters, including the 0.25% worked example as a comparison case (capital 10k at 0.25% risk = 25, divided by the trade's stop distance) — evaluation only, no parameter change without evidence through the normal gate. (3) Add the S-11 creator hard rules to the advisory gate's rule set where missing (retail traders cannot control the market, only their own risk; don't take debt for trading; learn first, then put money in).
- Sources: S-08 (item DX6peBwCRW3 — scale-up gate), S-09 (same item — Kelly + worked example), S-11 (item DaFKBDwJlLZ — creator hard rules).

## Code paths located first-hand (main 67373a93)
- `Stratex/measurement/forward_guard.py` (258 lines, blob `c9744568`) — FWD-006 home: MTM drawdown guard, sleeve evaluation, aggregate portfolio-heat cap 2% of venue equity. No "ladder" / "scale-up" concept exists yet — the scale-up gate is new code.
- `Stratex/risk/volatility_sizing.py` (97 lines, blob `c451e3f7`) — vol-targeted weights + regime classifier. Not the ladder.
- `Stratex/advisory_gate.py` (522 lines, blob `d9d357af`) — advisory gate: ADVISORY ONLY, parameters only, risk limits immutable (`FORBIDDEN_PARAMS` incl. risk limits; hardcoded bounds cannot be overridden from env). S-11 rules to be added to its rule set where missing.
- `Stratex/tests/test_fwd006_sizing.py` (170 lines, blob `9498f7e3`) — FWD-006 unit coverage (forward guard, heat-cap budget, open-risk aggregation).
- Full main tree verified: 8,560 paths; no `kelly`, `ladder`, or `fwd006` module besides the above.

## Named gaps (not blockers for scoping)
- S-08 / S-09 / S-11 source watch records (Instagram items DX6peBwCRW3, DaFKBDwJlLZ) not yet located on main; the board record quotes the conditions, worked example, and hard rules verbatim, and the coordinator's evidence states the source package/watch records were read first-hand in the re-audit. The build will verify each rule against the source records before encoding it; anything not verified in a source record does not get encoded.
- Exact "sizing ladder" home to be confirmed in the build: the scale-up gate most plausibly lands in/around `forward_guard.py` (heat-cap budget) — FWD-006 parameters govern and are unchanged.

## Build plan (next steps)
1. Leg 1: scale-up gate conditions as a pure gate (allow/deny scale-up) with unit tests; ladder percentages untouched.
2. Leg 2: Kelly paper study doc + worked-example comparison against live parameters; no code change to parameters.
3. Leg 3: S-11 hard rules into the advisory gate rule set where missing, with tests.
4. Board flip AVAILABLE → IN_REVIEW rides in the work PR, with the checkpoint doc.

## Five states
implemented NO / tested NO / merged NO / deployed NO / production-verified NO.

## Usage
10% of free weekly limit (verified this run); reset Dec 1, 11:00 AM IST. Not exhausted.

— Muse 20
