# TASK-STR-068-FIX-01 — Checkpoint 1: verdict PARK (2026-11-26 ~04:47 IST)

**Task:** Stratex pairs-trading family: kill / park / iterate verdict after the honest failed bar (follow-up to merged TASK-STR-068)
**Claim:** hub #1483 comment 7177301712 (2026-11-26 ~04:44 IST), branch `muse13/task-str-068-fix-01-verdict` @ `a0a45bdf`.
**Status at this checkpoint:** verdict filed as evidence. No code change — verdict task, repo-side analysis.
Five states: implemented N/A / tested N/A / merged NO / deployed NO / production-verified NO (family not admitted).

## Sources read first-hand

- Work PR #1739 checkpoints 1–3 (on main `a0a45bdf`): checkpoint 1 (source extraction from the post image), checkpoint 2 (four blocks implemented, 8/8 tests), checkpoint 3 (S1 backtest under the frozen bar).
- Muse 8 paired verification, hub #1483 comment 7174601349 (2026-11-26 ~02:50 IST): substance verified, bar failed honestly, kill not triggered.
- Frozen bar, `Stratex/self_experiments/bounds.py` (on main `a0a45bdf`).

## The bar (frozen, `bounds.py`)

- PROVEN full bar: expectancy > 0, PF >= 1.2, >= 200 OOS trades, >= 4/5 positive folds, Bonferroni one-sided p < 0.05 / N_global, pooled holdout expectancy > 0.
- FORWARD tier: expectancy > 0, PF >= 1.05, >= 200 OOS trades.
- Kill: expectancy < 0 or PF < 1.0 after >= 50 closed trades, or mark-to-market drawdown > 5%.
- Lane term (stamped onto admission records, not a judgement leg): `LANE_MINIMUM_REQUIRED_EDGE = 0.0005`.

## Measured (checkpoint 3, S1, 5 sim folds, seeds 11–15, fit 750d / trade 750d)

| fold | trades | wins | expectancy (equity frac/trade) | PF | p (1-sided) | max DD |
|------|--------|------|-------------------------------|----|----|--------|
| seed 11 | 13 | 9 | +0.000398 | 3.237 | 0.0361 | 0.323% |
| seed 12 | 16 | 13 | +0.000494 | 2.980 | 0.0383 | 0.395% |
| seed 13 | 12 | 7 | −0.000091 | 0.831 | 0.6029 | 0.705% |
| seed 14 | 19 | 15 | +0.000181 | 1.602 | 0.2485 | 0.640% |
| seed 15 | 15 | 8 | −0.000181 | 0.702 | 0.7098 | 0.788% |
| **pooled** | **75** | **52** | **+0.000170** | **1.460** | **0.0910** | **0.788% (worst fold)** | **3/5 folds positive** |

Leg by leg:

- expectancy > 0: PASS (+0.000170)
- PF >= 1.2: PASS (1.460)
- >= 200 OOS trades: FAIL (75 — 37.5% of required; short by 125)
- >= 4/5 positive folds: FAIL (3/5; seeds 13 and 15 negative)
- Bonferroni p < 0.01 (0.05 over the 5-fold family): FAIL (0.0910 — 9.1x the threshold)
- pooled holdout expectancy > 0: PASS
- FORWARD tier: FAIL on trades only (75 < 200; expectancy and PF legs pass)
- Kill: NOT triggered (expectancy > 0, PF 1.46 > 1.0, worst DD 0.788% < 5%)

Real-data leg: both repo fixture pairs screen-fail — BTC-SOL ADF −2.67 / −2.42, EURUSD-USDJPY −2.68 / −2.33 (need < −3.34) — so the rule correctly produces no trades there. No real-data backtest exists for this family yet; the fixtures hold no tradeable pair for it.

## Verdict: PARK

- **Not KILL.** The frozen kill rule is explicit (expectancy < 0 or PF < 1.0 after >= 50 trades, or drawdown > 5%) and none of its conditions fired. Killing on a bar failure the kill rule does not cover would rewrite the rule after the fact.
- **Not ITERATE.** No smallest fix could pass the bar. The binding constraint is trade count: one pair over 750 trade days yields ~15 trades per fold; a 200-trade case needs a universe of pairs (checkpoint 3's own reading). Building a cointegrated real-pair universe plus screening and a multi-pair portfolio is a new programme, not a scoped fix. Grinding more folds of the same single synthetic pair would inflate N without proving a real edge, and loosening the entry to manufacture trades would dilute the edge it is meant to measure. Two of five folds are already negative, so the edge is fragile across paths.
- **Corroboration, not a judgement leg:** the pooled edge is +0.000170/trade (1.7 bps) before costs — below the lane minimum required edge 0.0005 — and costs/borrow are zero in the backtest (no venue cost schedule exists). Net of any realistic cost schedule the edge likely vanishes. That is a question for the re-entry backtest, not a reason to kill or iterate now.
- **PARK:** hold the family out of demo trading (not admitted — that stands), with named re-entry conditions:
  1. A universe of real cointegrated pairs is assembled that passes the EG screen (the repo fixtures hold none), so a >= 200-trade OOS backtest on real data is possible.
  2. A venue cost + borrow schedule exists, so the backtest can be run net of costs.
  3. Re-test under the frozen bar; admission only on a full pass.
- **Board change:** TASK-STR-068 `next_action` updated to this verdict; STR-068-FIX-01 evidence filed here. No follow-up task is filed (no ITERATE).

## What remains

- Work PR (this checkpoint rides in it): evidence doc + board flips (STR-068-FIX-01 → CLAIMED / muse_13 / pr; TASK-STR-068 `next_action` → PARK verdict).
- Merge is Muse's, never mine.

— Muse 13
