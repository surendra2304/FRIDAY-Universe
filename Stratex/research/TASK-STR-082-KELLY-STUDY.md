# Kelly-criterion paper study — TASK-STR-082, leg 2

**Status:** paper study only — evaluation, no parameter change.
**Sources:** S-09 (item DX6peBwCRW3 — Kelly Criterion proposed for
risk-per-trade calculation, plus the conservative worked example).
**Live parameters compared against:** FWD-006 (per-trade risk 0.1% of
venue equity; aggregate portfolio-heat cap 2% of venue equity).

## 1. The Kelly formula

For a trade with win probability `p`, loss probability `q = 1 - p`,
and average win / average loss ratio `R`, the Kelly fraction — the
share of bankroll to risk on the trade that maximises long-run log
growth — is:

```
f* = p - (1 - p) / R
```

Equivalently `f* = (b·p - q) / b` where `b = R` is the net odds.

## 2. The source's worked example (S-09)

Capital $10,000 at 0.25% risk per trade:

```
risk budget = $10,000 x 0.0025 = $25 per trade
position size = $25 / stop distance
```

| Stop distance | Position size ($25 / distance) | Live FWD-006 size ($10 / distance) |
|---|---|---|
| $0.50 | 50 units | 20 units |
| $2.00 | 12.5 units | 5 units |
| $5.00 | 5 units | 2 units |
| $10.00 | 2.5 units | 1 unit |

The worked example is the *conservative* case in its own source —
and it still risks **2.5x the live FWD-006 per-trade budget**
($25 vs $10 on $10,000). Adopting the example's 0.25% would breach
FWD-006. It is NOT adopted.

## 3. What full Kelly implies against the live parameters

| Win rate p | Avg win/loss R | Kelly f* | Risk on $10,000 | Multiple of live $10 budget |
|---|---|---|---|---|
| 0.50 | 2.0 | 0.25 | $2,500 | 250x |
| 0.55 | 1.5 | 0.25 | $2,500 | 250x |
| 0.60 | 1.0 | 0.20 | $2,000 | 200x |
| 0.40 | 2.0 | 0.10 | $1,000 | 100x |

Arithmetic check (row 1): `f* = 0.50 - 0.50/2.0 = 0.25`. Even the
weakest edge in the table (p = 0.40, R = 2.0) implies risking 10% of
bankroll per trade — 100x the live budget. Even quarter-Kelly at
p = 0.50, R = 2.0 is 6.25% ($625), 62.5x the live budget.

## 4. Why Kelly is not adopted

1. **Scale.** Full Kelly fractions are two orders of magnitude above
   the FWD-006 risk posture (0.1% per trade, 2% heat cap). Adopting
   them would void the forward protocol's kill coherence.
2. **Estimation error.** Kelly assumes `p` and `R` are known. Real
   edge estimates are noisy; overestimating the edge over-bets, and
   Kelly over-betting is punished worse than under-betting.
3. **Drawdowns.** Full Kelly maximises log growth at the cost of
   extreme drawdowns (50%+ bankroll swings are routine). The 5%
   strategy kill and the scale-up gate's 10% drawdown bar both exist
   to keep the book nowhere near that regime.
4. **No evidence through the gate.** No forward record supports any
   Kelly-sized risk budget. A parameter change would need evidence
   through the normal gate (frozen admission bar), and none exists.

## 5. Verdict

- The Kelly formula and the 0.25% worked example are recorded here
  as a reference for sizing discussions. **No parameter changes.**
- The 0.25% worked example is NOT adopted: it is 2.5x the live
  per-trade budget and would breach FWD-006.
- Any future size increase is governed by the scale-up gate
  (`Stratex/measurement/scale_up_gate.py`, TASK-STR-082 leg 1), not
  by a Kelly fraction.

— Muse 20, 2026-11-25
