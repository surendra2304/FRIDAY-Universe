"""Synthetic tests for the TASK-STR-RD-023 grid / passive-MM harness.

Stdlib-only, deterministic, hand-computed scenarios. These tests
pin the DECLARED mechanics of grid_mm.py (frozen declaration
SHA-256 2b5d807a5b00c893b1dd28af4d23b943a7fb587c15dc9a7e6cf8a5bdd8a7d66c):

- grid placement is causal and matches hand-computed percentiles;
- a fill requires the bar's range to SPAN the level and trade
  THROUGH it by the 10 bps margin — a touch never fills, and a
  level the bar never reached never fills (no phantom fills);
- no same-bar exit, no same-bar re-buy after a sale;
- the inventory cap (one unit per line, <= 10 open units) holds;
- teardown force-closes everything at the placement bar's close
  and no inventory carries across epochs;
- per-fill fee + adverse-selection accounting at both cost stacks.

Warm-up: 672 bars whose closes cycle [90, 95, 100, 105, 110].
Sorted counts: 90 x135, 95 x135, 100 x134, 105 x134, 110 x134, so
P10 = 90.0 and P90 = 110.0 exactly, and the first grid (placed at
the close of bar 671) is lines 90, 92, ..., 110 (step 2.0).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from grid_mm import (ADVERSE_SELECTION_BPS_PER_FILL, EPOCH_BARS,
                     FIRST_PLACEMENT_BAR, GRID_COSTS, GRID_COSTS_2X,
                     GRID_INTERVALS, MAX_OPEN_UNITS, TRAILING_WINDOW_BARS,
                     Trade, build_grid, net_return_long, percentile_type7,
                     simulate)

PAT = [90.0, 95.0, 100.0, 105.0, 110.0]
EXPECTED_LINES = [90.0 + 2.0 * k for k in range(11)]


def _bar(t, high, low, close):
    return {"time": t, "open": close, "high": high, "low": low, "close": close}


def _warmup(n=TRAILING_WINDOW_BARS):
    return [_bar(i, PAT[i % 5] + 0.5, PAT[i % 5] - 0.5, PAT[i % 5])
            for i in range(n)]


def _quiet(t):
    # Spans buy lines 90..98 but trades through none of them and
    # touches none; spans no sell target at/above 100.
    return _bar(t, 99.0, 98.5, 99.0)


def _series(epoch_bars, total=768):
    """Warm-up + crafted epoch bars (from index 672) + quiet fill."""
    bars = _warmup()
    by_idx = {b["time"]: b for b in epoch_bars}
    for t in range(TRAILING_WINDOW_BARS, total):
        bars.append(by_idx.get(t, _quiet(t)))
    return bars


# ----------------------------------------------------------------
# Placement mathematics

def test_percentile_type7_hand_computed():
    vals = [float(i) for i in range(100)]
    assert math.isclose(percentile_type7(vals, 10), 9.9, abs_tol=1e-12)
    assert math.isclose(percentile_type7(vals, 90), 89.1, abs_tol=1e-12)
    assert percentile_type7([5.0], 50) == 5.0


def test_build_grid_hand_computed_and_degenerate():
    window = [PAT[i % 5] for i in range(TRAILING_WINDOW_BARS)]
    assert build_grid(window) == EXPECTED_LINES
    assert build_grid([100.0] * TRAILING_WINDOW_BARS) is None
    try:
        build_grid([100.0] * 10)
    except ValueError:
        pass
    else:
        raise AssertionError("build_grid accepted a short window")


# ----------------------------------------------------------------
# Fill model: span + trade-through; touch is not a fill

def test_touch_is_not_a_fill_and_through_is():
    bars = _series([
        _bar(672, 99.0, 97.95, 98.5),   # spans 98, touches, not through
        _bar(673, 99.0, 97.90, 98.2),   # spans 98, through -> BUY @98
        _bar(674, 99.5, 98.6, 99.0),    # target 100 not even touched
        _bar(675, 100.05, 99.95, 99.8),  # target touched, not through
        _bar(676, 100.2, 99.95, 100.1),  # target through -> SELL @100
    ])
    trades, stats = simulate(bars, "BTCUSDT")
    assert stats["buy_fills"] == 1
    assert stats["sell_fills"] == 1
    assert stats["teardown_exits"] == 0
    # touches: bar 672 buy-side (98); bar 675 sell-side (100) AND
    # buy-side (100); bar 676 buy-side (100). The span rule is what
    # keeps bar 672 from filling line 100 (low 97.95 <= 99.9 would
    # have filled it under a through-only rule — a phantom fill at
    # a price the bar never reached).
    assert stats["touch_no_fill"] == 4
    assert len(trades) == 1
    tr = trades[0]
    assert (tr.entry_price, tr.exit_price) == (98.0, 100.0)
    assert (tr.entry_time, tr.exit_time) == (673, 676)
    assert tr.exit_reason == "GRID_SELL" and tr.side == "LONG"
    assert math.isclose(tr.net_return,
                        net_return_long(98.0, 100.0, GRID_COSTS),
                        rel_tol=0.0, abs_tol=1e-15)


def test_no_same_bar_exit():
    bars = _series([
        # Buys lines 98 AND 100 (a genuine cascade). The same bar's
        # high (101) spans and trades through 98's target (100) —
        # but the unit was not open at the bar's start, so no exit.
        _bar(672, 101.0, 97.9, 100.0),
        # Gap bar entirely above 100: the 98-unit's target is NOT
        # spanned (low 101.95 > 100) so it cannot sell — the
        # conservative gap miss. The 100-unit sells at 102.
        _bar(673, 102.3, 101.95, 102.0),
        # The 98-unit finally sells at 100; line 100 re-buys.
        _bar(674, 100.3, 99.7, 100.0),
    ])
    trades, stats = simulate(bars, "BTCUSDT")
    assert all(tr.exit_time != 672 for tr in trades)
    assert [(tr.entry_price, tr.exit_price, tr.exit_time, tr.exit_reason)
            for tr in trades] == [
        (100.0, 102.0, 673, "GRID_SELL"),
        (98.0, 100.0, 674, "GRID_SELL"),
        (100.0, 99.0, 767, "TEARDOWN"),
    ]
    assert stats["buy_fills"] == 3 and stats["sell_fills"] == 2
    assert stats["teardown_exits"] == 1


def test_no_same_bar_rebuy_after_sale():
    bars = _series([
        _bar(672, 99.0, 97.9, 98.5),     # BUY @98 (only line spanned)
        _bar(673, 100.2, 97.8, 99.0),    # SELL the 98-unit @100; the
        # same bar trades through 98 downward again — re-buying THE
        # SAME line in its sale bar is FORBIDDEN (the intra-bar path
        # is unknowable). Buying a DIFFERENT line (100) in that bar
        # is declared-legal and does happen.
        _bar(674, 99.5, 97.8, 99.0),     # one bar later the 98
        # re-buy IS allowed (line 100 is not spanned by this bar).
    ])
    trades, stats = simulate(bars, "BTCUSDT")
    assert stats["buy_fills"] == 3 and stats["sell_fills"] == 1
    assert stats["teardown_exits"] == 2
    assert not any(tr.entry_price == 98.0 and tr.entry_time == 673
                   for tr in trades), "same-bar re-buy after sale occurred"
    assert [(tr.entry_price, tr.entry_time, tr.exit_price, tr.exit_time,
             tr.exit_reason) for tr in trades] == [
        (98.0, 672, 100.0, 673, "GRID_SELL"),
        (98.0, 674, 99.0, 767, "TEARDOWN"),   # re-bought at 674, NOT 673
        (100.0, 673, 99.0, 767, "TEARDOWN"),  # the legal different-line buy
    ]


# ----------------------------------------------------------------
# Inventory cap

def test_inventory_cap_enforced():
    crash = lambda t: _bar(t, 111.0, 89.0, 100.0)  # spans + through ALL lines
    bars = _series([crash(672), crash(673), crash(674)])
    trades, stats = simulate(bars, "BTCUSDT")
    # Bar 672: all 10 buy lines fill. Bar 673: all 10 units sell
    # (targets spanned + through); no buys (all lines were occupied
    # at bar start). Bar 674: all 10 lines fill again. The cap is
    # structural: open units never exceed one per line.
    assert stats["max_open_units"] == MAX_OPEN_UNITS == 10
    assert stats["buy_fills"] == 20 and stats["sell_fills"] == 10
    assert stats["teardown_exits"] == 10  # the bar-674 cohort
    assert len(trades) == 20


# ----------------------------------------------------------------
# Teardown: force-close at the placement close; no carry

def test_teardown_closes_all_and_nothing_carries():
    bars = _warmup()
    bars.append(_bar(672, 99.0, 97.9, 98.5))        # BUY @98
    for t in range(673, 767):
        bars.append(_quiet(t))
    # Placement bar 767: fills run under the OLD grid first (line
    # 96 buys on the way down), THEN teardown closes both units at
    # this bar's close, THEN the new grid is placed.
    bars.append(_bar(767, 99.0, 94.5, 95.0))
    for t in range(768, 864):
        bars.append(_bar(t, 95.4, 94.6, 95.0))      # quiet under grid 2
    trades, stats = simulate(bars, "BTCUSDT")
    assert stats["sell_fills"] == 0 and stats["teardown_exits"] == 2
    # Teardown emits in line order (96 before 98).
    assert [(tr.entry_price, tr.entry_time, tr.exit_price, tr.exit_time,
             tr.exit_reason) for tr in trades] == [
        (96.0, 767, 95.0, 767, "TEARDOWN"),
        (98.0, 672, 95.0, 767, "TEARDOWN"),
    ]
    # No trade survives the epoch boundary: nothing entered under
    # grid 1 exits after bar 767.


def test_degenerate_window_places_no_grid():
    bars = [_bar(i, 100.5, 99.5, 100.0) for i in range(900)]
    trades, stats = simulate(bars, "BTCUSDT")
    assert trades == [] and stats["buy_fills"] == 0
    assert stats["placements"] == 3          # bars 671, 767, 863
    assert stats["epochs_with_grid"] == 0
    trades2, stats2 = simulate(bars[:100], "BTCUSDT")
    assert trades2 == [] and stats2["placements"] == 0


# ----------------------------------------------------------------
# Causality: mutating the future changes nothing in the past

def test_placement_and_fills_are_causal():
    def series(mutant):
        out = []
        for i in range(1300):
            c = 100.0 + 8.0 * math.sin(i / 25.0) + (i % 7) * 0.3
            if mutant and i > 999:
                c *= 3.0
            out.append(_bar(i, c + 0.6, c - 0.6, c))
        return out

    trades_a, _ = simulate(series(False), "ETHUSDT")
    trades_b, _ = simulate(series(True), "ETHUSDT")
    past_a = [tr for tr in trades_a if tr.exit_time <= 999]
    past_b = [tr for tr in trades_b if tr.exit_time <= 999]
    assert past_a, "causality test is vacuous: no trades before bar 1000"
    assert past_a == past_b


# ----------------------------------------------------------------
# Fee accounting (both stacks, hand-computed)

def test_fee_accounting_both_stacks():
    assert GRID_COSTS.per_fill_rate == (8.0 + 5.0) / 10000.0
    assert GRID_COSTS_2X.per_fill_rate == (16.0 + 5.0) / 10000.0
    assert GRID_COSTS.describe()["effective_round_trip_bps"] == 26.0
    assert GRID_COSTS_2X.describe()["effective_round_trip_bps"] == 42.0
    # Flat round trip loses exactly the stack (26 / 42 bps, in
    # return space slightly less than the nominal bps).
    assert math.isclose(net_return_long(100.0, 100.0, GRID_COSTS),
                        -0.00259662, abs_tol=1e-7)
    assert math.isclose(net_return_long(100.0, 100.0, GRID_COSTS_2X),
                        -0.00419120, abs_tol=1e-7)
    # One grid step at the bottom of the test grid (90 -> 92),
    # hand-computed under the programme stack.
    assert math.isclose(net_return_long(98.0, 100.0, GRID_COSTS),
                        0.0177586, abs_tol=1e-6)
    step = net_return_long(90.0, 92.0, GRID_COSTS)
    assert 0.0 < step < (92.0 - 90.0) / 90.0  # net < gross, still > 0


def test_frozen_constants_match_declaration():
    assert FIRST_PLACEMENT_BAR == TRAILING_WINDOW_BARS - 1 == 671
    assert EPOCH_BARS == 96 and GRID_INTERVALS == 10
    assert ADVERSE_SELECTION_BPS_PER_FILL == 5.0
    assert MAX_OPEN_UNITS == GRID_INTERVALS
