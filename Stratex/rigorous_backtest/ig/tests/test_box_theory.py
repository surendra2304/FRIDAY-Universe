"""Tests for TASK-IG2-STR-13 box_theory — MECHANICS ONLY.

The family is PRE-DECLARED and NOT RUN: these tests verify the signal
rules match the frozen declaration on hand-built bars. They assert
nothing about profitability and execute no backtest.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.box_theory import compute_boxes, generate_signals  # noqa: E402


def bar(day, hhmm, o, h, l, c):
    return {"time": f"2026-01-{day:02d}T{hhmm}:00Z",
            "open": o, "high": h, "low": l, "close": c}


def day1():
    # Previous day range: high 110, low 90 -> box mid 100, height 20,
    # bottom zone [90, 95], top zone [105, 110].
    return [
        bar(5, "09:00", 100, 110, 95, 105),
        bar(5, "09:15", 105, 108, 90, 95),
    ]


def test_box_comes_from_previous_day_only():
    bars = day1() + [bar(6, "09:00", 100, 130, 70, 100)]
    boxes = compute_boxes(bars)
    assert boxes["2026-01-06"].high == 110
    assert boxes["2026-01-06"].low == 90
    assert boxes["2026-01-06"].mid == 100
    assert "2026-01-05" not in boxes  # first day has no previous day


def test_long_wick_at_bottom_extreme_signals_long():
    # Bar dips to 92 (inside bottom zone [90,95]), long lower wick:
    # open 96, close 97.5 (body 1.5), low 92 -> wick 4 >= 2*1.5; close
    # in upper half of range [92, 98].
    bars = day1() + [bar(6, "09:00", 96, 98, 92, 97.5)]
    signals = generate_signals(bars)
    assert len(signals) == 1
    s = signals[0]
    assert s.side == "LONG" and s.entry == 97.5
    assert s.stop == 90 and s.target1 == 100 and s.target2 == 110


def test_short_wick_at_top_extreme_signals_short():
    # Upper wick: open 104, close 102.5 (body 1.5), high 108 -> wick 4;
    # close in lower half of range [102, 108].
    bars = day1() + [bar(6, "09:00", 104, 108, 102, 102.5)]
    signals = generate_signals(bars)
    assert len(signals) == 1
    s = signals[0]
    assert s.side == "SHORT" and s.stop == 110
    assert s.target1 == 100 and s.target2 == 90


def test_wick_pattern_in_the_middle_is_no_trade():
    # Same long-wick shape but around the mid (100): range [97, 103]
    # never touches either zone.
    bars = day1() + [bar(6, "09:00", 99, 103, 97, 102.5)]
    assert generate_signals(bars) == []


def test_zone_touch_without_wick_pattern_is_no_signal():
    # Reaches 91 (bottom zone) but body dominates: open 99, close 91.5
    # (body 7.5), lower wick 0.5 < 2*body.
    bars = day1() + [bar(6, "09:00", 99, 99.5, 91, 91.5)]
    assert generate_signals(bars) == []


def test_one_signal_per_day():
    trigger = bar(6, "09:00", 96, 98, 92, 97.5)
    trigger2 = bar(6, "09:15", 96, 98, 92, 97.5)
    bars = day1() + [trigger, trigger2]
    assert len(generate_signals(bars)) == 1


def test_first_day_produces_no_signals():
    bars = [bar(5, "09:00", 96, 98, 92, 97.5)]
    assert generate_signals(bars) == []
