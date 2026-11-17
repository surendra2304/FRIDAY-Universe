"""test_fxsession.py — synthetic mechanics tests for TASK-STR-RD-018.

No network, no real data: every bar is constructed. These tests pin
the declared mechanics of fxsession.py / run_fxsession.py:
session-window construction across DST (fixed UTC), the range
computed on completed in-window candles only, no look-ahead (setup
frozen at 06:00 UTC; entry at the next bar's open), the fade /
stop / target / time-exit rules, the one-setup-per-day rule and its
guard-voiding, and the cost model's 1x vs 2x arithmetic.

Run from this directory:  python3 -m pytest test_fxsession.py -q
"""
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fxsession import Bar, asian_range, day_slice, generate_trades  # noqa: E402
from run_fxsession import _t_cdf, t_test_one_sided_greater  # noqa: E402

BAR_LEN = timedelta(minutes=15)
# Declared geometry used across scenarios:
# range (1.1010, 1.0990) -> W = 0.0020, midpoint 1.1000,
# SHORT stop 1.1020, LONG stop 1.0980.
D = date(2024, 6, 3)  # a Monday


def make_day(d, overrides=None):
    """41 bars for date d. Range bars (idx 0..23): h=1.1010,
    l=1.0990, o=c=1.1000. Fade bars (24..39) and the 10:00 bar
    (idx 40): flat 1.1000. overrides: {idx: {field: value}}."""
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    bars = []
    for i in range(41):
        o = h = l = c = 1.1000
        if i < 24:
            h, l = 1.1010, 1.0990
        vals = {"o": o, "h": h, "l": l, "c": c, "complete": True}
        if overrides and i in overrides:
            vals.update(overrides[i])
        bars.append(Bar(start + i * BAR_LEN, vals["o"], vals["h"],
                        vals["l"], vals["c"], vals["complete"]))
    return bars


def close(a, b):
    return math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)


# --- session-window construction ------------------------------------

def test_range_window_boundaries():
    # idx 23 (05:45) is the last in-window bar; idx 24 starts 06:00.
    day = make_day(D, {23: {"h": 1.2000}, 24: {"h": 1.3000, "l": 0.9000}})
    rng = asian_range(day)
    assert rng is not None
    assert close(rng[0], 1.2000)      # 05:45 extreme counts
    assert close(rng[1], 1.0990)      # 06:00 bar's low does NOT count


def test_windows_fixed_utc_across_dst():
    # London DST transitions 2024: BST starts Sun 2024-03-31,
    # ends Sun 2024-10-27. Identical bar patterns must produce
    # identical ranges on both sides — windows never shift.
    for d in (date(2024, 3, 28), date(2024, 4, 1),
              date(2024, 10, 25), date(2024, 10, 28)):
        day = make_day(d)
        sliced = day_slice(day, d)
        assert len(sliced) == 41
        assert sliced[0].ts == datetime(d.year, d.month, d.day,
                                        tzinfo=timezone.utc)
        rng = asian_range(sliced)
        assert rng is not None and close(rng[0], 1.1010) and close(rng[1], 1.0990)


def test_partial_window_no_setup():
    day = make_day(D, {28: {"h": 1.1015}, 29: {"o": 1.1008, "h": 1.1008,
                                              "l": 1.1008, "c": 1.1008}})
    assert len(generate_trades(day, "EURUSD")) == 1  # sanity: full day trades
    broken = day[:10] + day[11:]                     # one range bar missing
    assert generate_trades(broken, "EURUSD") == []
    broken2 = day[:30] + day[31:]                    # one fade bar missing
    assert generate_trades(broken2, "EURUSD") == []


def test_incomplete_bar_voids_day():
    day = make_day(D, {5: {"complete": False},
                       28: {"h": 1.1015},
                       29: {"o": 1.1008, "h": 1.1008, "l": 1.1008, "c": 1.1008}})
    assert generate_trades(day, "EURUSD") == []


def test_zero_height_range_no_setup():
    start = datetime(2024, 6, 3, tzinfo=timezone.utc)
    flat = [Bar(start + i * BAR_LEN, 1.1, 1.1, 1.1, 1.1, True)
            for i in range(41)]
    assert asian_range(flat) is None
    assert generate_trades(flat, "EURUSD") == []


# --- no look-ahead ----------------------------------------------------

def test_no_lookahead_setup_frozen():
    # Day A: post-entry bar spikes to 1.5000 (stop territory and far
    # beyond the frozen range). Day B: identical through the entry
    # bar, then drifts to the target. Setup fields must be identical.
    common = {28: {"h": 1.1015, "l": 1.1004},
              29: {"o": 1.1008, "h": 1.1008, "l": 1.1008, "c": 1.1008}}
    day_a = make_day(D, {**common, 30: {"o": 1.1008, "h": 1.5000,
                                        "l": 1.1004, "c": 1.1008}})
    day_b = make_day(D, {**common,
                         30: {"o": 1.1008, "h": 1.1008, "l": 1.1004, "c": 1.1004},
                         31: {"o": 1.1004, "h": 1.1004, "l": 1.0995, "c": 1.0999}})
    ta = generate_trades(day_a, "EURUSD")
    tb = generate_trades(day_b, "EURUSD")
    assert len(ta) == len(tb) == 1
    a, b = ta[0], tb[0]
    assert a.entry_time == b.entry_time
    assert close(a.entry_price, 1.1008) and close(b.entry_price, 1.1008)
    assert close(a.stop, 1.1020) and close(b.stop, 1.1020)   # range frozen at 06:00
    assert close(a.target, 1.1000) and close(b.target, 1.1000)
    assert a.exit_reason == "SL" and b.exit_reason == "TP"   # only exits differ


def test_entry_is_next_bar_open():
    day = make_day(D, {28: {"h": 1.1015, "l": 1.1004, "c": 1.1014},
                       29: {"o": 1.1008, "h": 1.1008, "l": 1.1008, "c": 1.1008},
                       30: {"o": 1.1004, "h": 1.1004, "l": 1.0995, "c": 1.0999}})
    (t,) = generate_trades(day, "EURUSD")
    start = datetime(2024, 6, 3, tzinfo=timezone.utc)
    assert t.entry_time == start + 29 * BAR_LEN      # not the touch bar
    assert close(t.entry_price, 1.1008)              # the next bar's OPEN


# --- fade mechanics ---------------------------------------------------

def _short_setup(extra):
    base = {28: {"h": 1.1015, "l": 1.1004},
            29: {"o": 1.1008, "h": 1.1008, "l": 1.1008, "c": 1.1008}}
    base.update(extra)
    return make_day(D, base)


def test_short_fade_target():
    day = _short_setup({30: {"o": 1.1004, "h": 1.1004, "l": 1.1004, "c": 1.1004},
                        31: {"o": 1.1004, "h": 1.1004, "l": 1.0995, "c": 1.0999}})
    (t,) = generate_trades(day, "EURUSD")
    assert t.side == "SHORT" and t.exit_reason == "TP"
    assert close(t.exit_price, 1.1000)               # range midpoint
    assert t.ret_gross > 0 and 0 < t.ret_net < t.ret_gross


def test_long_fade_target():
    day = make_day(D, {28: {"h": 1.1004, "l": 1.0985},
                       29: {"o": 1.0992, "h": 1.0992, "l": 1.0992, "c": 1.0992},
                       30: {"o": 1.0996, "h": 1.0996, "l": 1.0996, "c": 1.0996},
                       31: {"o": 1.0996, "h": 1.1005, "l": 1.0996, "c": 1.1001}})
    (t,) = generate_trades(day, "EURUSD")
    assert t.side == "LONG" and t.exit_reason == "TP"
    assert close(t.exit_price, 1.1000)
    assert close(t.stop, 1.0980)
    assert t.ret_gross > 0 and 0 < t.ret_net < t.ret_gross


def test_stop_first_when_bar_spans_both():
    day = _short_setup({29: {"o": 1.1008, "h": 1.1030, "l": 1.0990, "c": 1.1008}})
    (t,) = generate_trades(day, "EURUSD")
    assert t.exit_reason == "SL"
    assert close(t.exit_price, 1.1020)
    assert t.exit_time == t.entry_time               # resolved on the fill bar


def test_time_exit_at_1000_open():
    day = _short_setup({40: {"o": 1.1006, "h": 1.1006, "l": 1.1006, "c": 1.1006}})
    # fade bars after entry default flat 1.1000: their low == target
    # would TP — lift them above the midpoint so nothing triggers.
    for i in range(30, 40):
        day[i] = Bar(day[i].ts, 1.1004, 1.1004, 1.1004, 1.1004, True)
    (t,) = generate_trades(day, "EURUSD")
    assert t.exit_reason == "TIME"
    assert close(t.exit_price, 1.1006)               # the 10:00 bar's open
    assert t.exit_time == day[40].ts


def test_touch_at_exact_extreme_counts():
    day = _short_setup({28: {"h": 1.1010, "l": 1.1004},   # high == range high
                        30: {"o": 1.1004, "h": 1.1004, "l": 1.0995, "c": 1.0999}})
    assert len(generate_trades(day, "EURUSD")) == 1


def test_both_extremes_bar_no_trade():
    day = make_day(D, {28: {"h": 1.1015, "l": 1.0985},
                       29: {"o": 1.1000, "h": 1.1000, "l": 1.1000, "c": 1.1000}})
    assert generate_trades(day, "EURUSD") == []


def test_entry_beyond_stop_no_trade():
    day = _short_setup({29: {"o": 1.1025, "h": 1.1025, "l": 1.1025, "c": 1.1025}})
    assert generate_trades(day, "EURUSD") == []


def test_entry_beyond_target_no_trade():
    day = _short_setup({29: {"o": 1.0998, "h": 1.0998, "l": 1.0998, "c": 1.0998}})
    assert generate_trades(day, "EURUSD") == []


def test_touch_on_last_fade_bar_no_trade():
    day = make_day(D, {39: {"h": 1.1015, "l": 1.1004}})
    assert generate_trades(day, "EURUSD") == []


def test_one_trade_per_day_and_guard_void_consumes_day():
    # Two clean touches -> exactly one trade.
    day = _short_setup({31: {"o": 1.1004, "h": 1.1004, "l": 1.0995, "c": 1.0999},
                        34: {"h": 1.1016, "l": 1.1004}})
    assert len(generate_trades(day, "EURUSD")) == 1
    # First touch's entry guard fails (entry beyond stop); a later
    # clean touch must NOT revive the day — the setup is consumed.
    day2 = make_day(D, {28: {"h": 1.1015, "l": 1.1004},
                        29: {"o": 1.1025, "h": 1.1025, "l": 1.1025, "c": 1.1025},
                        32: {"h": 1.1015, "l": 1.1004},
                        33: {"o": 1.1008, "h": 1.1008, "l": 1.1008, "c": 1.1008},
                        34: {"o": 1.1004, "h": 1.1004, "l": 1.0995, "c": 1.0999}})
    assert generate_trades(day2, "EURUSD") == []


# --- costs --------------------------------------------------------------

def test_cost_shadow_arithmetic():
    day = _short_setup({30: {"o": 1.1004, "h": 1.1004, "l": 1.0995, "c": 1.0999}})
    (t1,) = generate_trades(day, "EURUSD", slip_bps_per_side=3.0)
    (t2,) = generate_trades(day, "EURUSD", slip_bps_per_side=6.0)
    assert close(t1.ret_gross, t2.ret_gross)
    diff = t1.ret_net - t2.ret_net
    assert 0.00055 < diff < 0.00065                  # ~6 bps round trip apart


# --- judging helpers ----------------------------------------------------

def test_t_cdf_known_values():
    assert close(_t_cdf(0.0, 10), 0.5)
    assert abs(_t_cdf(1.3722, 10) - 0.90) < 0.002    # t_{0.90,10} = 1.3722
    assert abs(_t_cdf(2.0423, 30) - 0.975) < 0.002   # t_{0.975,30} = 2.0423
    assert abs(_t_cdf(-1.3722, 10) - 0.10) < 0.002


def test_t_test_direction():
    assert t_test_one_sided_greater([0.01] * 30 + [0.005] * 20) < 0.01
    assert t_test_one_sided_greater([-0.01] * 30 + [-0.005] * 20) > 0.99


def test_bars_must_be_sorted():
    day = make_day(D)
    day[3], day[4] = day[4], day[3]
    try:
        generate_trades(day, "EURUSD")
    except ValueError:
        return
    raise AssertionError("out-of-order bars must raise")
