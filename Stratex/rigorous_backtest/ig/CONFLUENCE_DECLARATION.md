# TASK-IG-STR-06 — Pre-declaration: Fib/BOS confluence family

**Declared 2026-11-15, before any backtest of this family has been run.**
Frozen declaration: `declaration.json` in this directory (its SHA-256 is
stated in the PR and in the completion comment on issue #35). The
declaration governs; if the code and the declaration disagree, the
declaration wins and the code is wrong.

## Source

IG reference corpus item `DYeU6nSBl9K` — an "SK-System" confluence
entry model: Fibonacci retracement zone + break-of-structure
confirmation + extension target. The video's performance framing is an
unverified claim and is treated as such: it bought this family a
pre-declared test, nothing more.

## The hypothesis

After an impulsive leg, a retracement into the 0.500–0.618 zone that
holds (no close beyond the leg origin) and then breaks the leg's
extreme continues in the leg's direction often enough — and far enough
toward the 1.272 / 1.618 extensions — to clear the RD programme bar
net of costs.

## Exact rules

Implemented in `confluence.py` (long side; short is the mirror):

1. **Leg** — swing low L (fractal window 2) followed by swing high
   H > L; range R = H − L.
2. **Retracement** — after H, a candle's range intersects
   [H − 0.618R, H − 0.500R]; any close below L before confirmation
   kills the leg.
3. **Confirmation (BOS)** — first close above H after the zone touch;
   entry at that close.
4. **Stop** = L. **Targets** = leg extensions from L:
   T1 = L + 1.272R, T2 = L + 1.618R.
5. One signal per leg. Parameters are frozen — variants require a new
   declaration and raise the trial count.

## The bar (unchanged from the programme)

- expectancy_net > 0 and profit_factor_net ≥ 1.2 (strict, OOS)
- ≥ 200 OOS trades; ≥ 4 of 5 walk-forward folds positive
- programme cost model **and** a 2×-cost shadow, both passing
- Bonferroni against the programme trial floor at run time
  (≥ 1,980 trials as of 2026-11-15, rising — the run states its floor)
- `rd.common.holdout_check` passes

## Status

DECLARED, NOT RUN. The backtest run (crypto30 + forex_cross41 panels,
1h/4h, walk-forward) is the declared next step, in a separate PR.
Passing the bar would make this a forward-test *candidate* under the
Phase-3 protocol — demo only, like everything else. Failing it closes
the family, like RD-004/006/012/014/016 before it.
