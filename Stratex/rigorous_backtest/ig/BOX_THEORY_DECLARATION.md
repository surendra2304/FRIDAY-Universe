# TASK-IG2-STR-13 — Pre-declaration: Box Theory family

**Declared 2026-11-16, before any backtest of this family has been run.**
Frozen declaration: `box_theory_declaration.json` in this directory
(its SHA-256 is stated in the PR and in the completion comment on
issue #35). The declaration governs; if the code and the declaration
disagree, the declaration wins and the code is wrong.

## Source

IG reference corpus item `DWDUW26DYbZ` (sweep crew-14) — a presenter
teaching "the box theory": each day, draw a box from the previous
day's high to low on a 15-minute chart, mark the middle; trade only
at the extremes — buy at the bottom, sell at the top, on a "John Wick
candlestick" entry — and avoid trades near the middle line, "where
all the false signals are". The community response was divided, with
experienced traders calling the method simplistic or gambling; the
video's performance framing is an unverified claim and is treated as
such: it bought this family a pre-declared test, nothing more.

## The hypothesis

Price revisiting the outer quartiles of the previous day's range
with a wick-rejection trigger mean-reverts toward the box mid /
opposite extreme often enough — and far enough — to clear the RD
programme bar net of costs.

## Exact rules (as implemented in `box_theory.py`)

1. **Box** — for day D: high = max high, low = min low of the
   previous present day's 15-minute bars; mid = (high + low) / 2.
   No previous day (or a zero-height box) → no signals that day.
   The box uses only the previous day's bars; a signal uses only
   its own bar's OHLC. No lookahead anywhere.
2. **Zones** — bottom zone [low, low + 0.25·height] for longs, top
   zone [high − 0.25·height, high] for shorts. The middle 50% is a
   no-trade zone: a trigger pattern there produces NO signal. (The
   source says "extremes only / avoid the middle" without a number;
   the quartile freeze is this declaration's resolution of that
   ambiguity, made before any run.)
3. **Trigger ("John Wick")** — long: lower wick ≥ 2× body and close
   in the upper half of the bar's own range; short mirrored (upper
   wick ≥ 2× body, close in lower half). (The source names the
   pattern without measurements; the 2×/upper-half freeze is this
   declaration's resolution, made before any run.) Entry at the
   trigger bar's close.
4. **Stop** = box low (long) / box high (short). **Targets** —
   T1 = box mid, T2 = opposite extreme.
5. **One signal per day** — the first qualifying extreme; no
   re-entry the same day.
6. Parameters are frozen (`ZONE_FRACTION=0.25`, `WICK_TO_BODY=2.0`)
   — variants require a new declaration and raise the trial count.

## The bar (unchanged from the programme)

- expectancy_net > 0 and profit_factor_net ≥ 1.2 (strict, OOS)
- ≥ 200 OOS trades; ≥ 4 of 5 walk-forward folds positive
- programme cost model **and** a 2×-cost shadow, both passing;
  exits under the harness convention (entry managed from the next
  bar, stop-before-target worst case)
- Bonferroni against the programme trial floor at run time
  (≥ 1,980 trials as of 2026-11-15, rising — the run states its floor)
- `rd.common.holdout_check` passes

## Status

DECLARED, NOT RUN. No backtest is executed in this PR — the module
ships signal generation only, with mechanics tests. The declared run
(15-minute panel per the declaration's data plan, walk-forward) is
the next step, in a separate PR. Passing the bar would make this a
forward-test *candidate* under the Phase-3 protocol — demo only,
like everything else. Failing it closes the family.
