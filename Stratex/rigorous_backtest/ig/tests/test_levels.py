"""Tests for TASK-IG-STR-03 levels (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.levels import find_levels, swing_points


def _candles(highs, lows, closes):
    return [{"high": h, "low": l, "close": c}
            for h, l, c in zip(highs, lows, closes)]


def test_swing_detection():
    highs = [10, 11, 12, 13, 12, 11, 10]
    lows = [10, 9, 8, 7, 8, 9, 10]
    closes = [10, 10, 11, 12, 11, 10, 10]
    hi, lo = swing_points(_candles(highs, lows, closes), window=1)
    assert hi == [3]
    assert lo == [3]


def test_levels_classified_against_last_close():
    # repeated ceiling at 110 and floor at 90, last close 100
    highs = [100, 110, 100, 110, 100, 110, 100]
    lows = [90, 95, 90, 95, 90, 95, 92]
    closes = [98, 105, 98, 105, 98, 105, 100]
    lv = find_levels(_candles(highs, lows, closes), window=1,
                     tol_frac=0.01, min_touches=2)
    kinds = {(r["kind"], round(r["price"])) for r in lv}
    assert ("resistance", 110) in kinds
    assert ("support", 90) in kinds
    res = [r for r in lv if r["kind"] == "resistance"][0]
    assert res["touches"] == 3 and res["strength"] == 1.0
    # annotation records are JSON-shaped plain data
    for r in lv:
        assert set(r) >= {"kind", "price", "touches", "first_index",
                          "last_index", "strength"}


def test_min_touches_filters_single_tests():
    highs = [100, 130, 100, 110, 100]
    lows = [95, 100, 96, 100, 97]
    closes = [98, 120, 98, 104, 99]
    lv = find_levels(_candles(highs, lows, closes), window=1,
                     tol_frac=0.01, min_touches=2)
    assert all(r["touches"] >= 2 for r in lv)
    assert all(round(r["price"]) != 130 for r in lv)


def test_short_series_and_flat_series():
    assert find_levels([], window=2) == []
    flat = _candles([100] * 9, [99] * 9, [99.5] * 9)
    assert find_levels(flat, window=2) == []  # ties are not swings


def test_tolerance_merges_nearby_swings():
    highs = [100, 110.0, 100, 110.4, 100, 109.8, 100]
    lows = [95, 97, 95, 97, 95, 97, 96]
    closes = [98, 104, 98, 104, 98, 104, 100]
    lv = find_levels(_candles(highs, lows, closes), window=1,
                     tol_frac=0.01, min_touches=1)
    near = [r for r in lv if 109 < r["price"] < 111]
    assert len(near) == 1 and near[0]["touches"] == 3
