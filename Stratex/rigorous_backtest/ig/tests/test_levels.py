"""Tests for TASK-IG-STR-03 levels (stdlib-only, offline)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.levels import annotate_levels, find_levels, swing_points


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


# TASK-STR-066: PDO/PDC + current-day 5-minute levels in the output.

def _base_candles():
    # repeated ceiling at 110 and floor at 90, last close 100
    highs = [100, 110, 100, 110, 100, 110, 100]
    lows = [90, 95, 90, 95, 90, 95, 92]
    closes = [98, 105, 98, 105, 98, 105, 100]
    return _candles(highs, lows, closes)


def test_pdo_pdc_carried_alongside_sr():
    lv = annotate_levels(_base_candles(), prev_day={"open": 105, "close": 98},
                         window=1, tol_frac=0.01, min_touches=2)
    by_kind = {r["kind"]: r for r in lv}
    assert by_kind["pdo"]["price"] == 105
    assert by_kind["pdc"]["price"] == 98
    assert by_kind["pdo"]["origin"] == "prev_day"
    assert by_kind["pdc"]["origin"] == "prev_day"
    assert by_kind["pdo"]["touches"] == 1
    assert by_kind["pdo"]["first_index"] is None
    assert by_kind["pdo"]["last_index"] is None
    # base S/R levels still present
    assert ("resistance", 110) in {(r["kind"], round(r["price"])) for r in lv}
    assert ("support", 90) in {(r["kind"], round(r["price"])) for r in lv}
    # every record is JSON-shaped plain data, sorted by price
    prices = [r["price"] for r in lv]
    assert prices == sorted(prices)
    for r in lv:
        assert set(r) >= {"kind", "price", "touches", "first_index",
                          "last_index", "strength"}


def test_pdo_pdc_at_price_flag():
    # prev-day close equals the last close -> at_price True
    lv = annotate_levels(_base_candles(), prev_day={"open": 105, "close": 100},
                         window=1, tol_frac=0.01, min_touches=2)
    by_kind = {r["kind"]: r for r in lv}
    assert by_kind["pdc"]["at_price"] is True
    assert by_kind["pdo"]["at_price"] is False


def test_today_5m_levels_tagged_and_separate():
    five_m = _candles([100, 112, 100, 112, 100, 112, 100],
                      [96, 98, 96, 98, 96, 98, 97],
                      [99, 106, 99, 106, 99, 106, 100])
    lv = annotate_levels(_base_candles(), today_5m=five_m,
                         window=1, tol_frac=0.01, min_touches=2)
    m5 = [r for r in lv if r.get("timeframe") == "5m"]
    assert m5, "no 5-minute levels in the output"
    assert {(r["kind"], round(r["price"])) for r in m5} >= {
        ("resistance", 112)}
    # 5m indices refer to the 5-minute series, not the base series
    assert all(0 <= r["first_index"] < len(five_m) for r in m5)
    # base records carry no timeframe tag
    assert all("timeframe" not in r for r in lv if r not in m5)


def test_annotate_without_extras_matches_find_levels():
    base = _base_candles()
    assert annotate_levels(base, window=1, tol_frac=0.01,
                           min_touches=2) == find_levels(
        base, window=1, tol_frac=0.01, min_touches=2)


def test_annotate_strength_normalised_across_combined_set():
    lv = annotate_levels(_base_candles(), prev_day={"open": 105, "close": 98},
                         window=1, tol_frac=0.01, min_touches=2)
    top = max(r["touches"] for r in lv)
    assert max(r["strength"] for r in lv) == 1.0
    pdo = [r for r in lv if r["kind"] == "pdo"][0]
    assert pdo["strength"] == pytest.approx(1 / top)


def test_prev_day_missing_keys_raises():
    with pytest.raises(ValueError):
        annotate_levels(_base_candles(), prev_day={"open": 105})
    with pytest.raises(ValueError):
        annotate_levels(_base_candles(), prev_day={"close": 98})


def test_annotate_empty_series():
    assert annotate_levels([]) == []
    assert annotate_levels([], prev_day={"open": 1, "close": 2}) == []
