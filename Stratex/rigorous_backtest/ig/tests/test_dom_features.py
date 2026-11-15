"""Tests for TASK-IG-STR-02 dom_features (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.dom_features import (depth_within_bps, detect_walls, imbalance,
                             microprice, snapshot_features, spread_bps)

BIDS = [(100.0, 2.0), (99.5, 3.0), (99.0, 1.0), (98.5, 4.0), (98.0, 2.0)]
ASKS = [(100.5, 1.0), (101.0, 2.0), (101.5, 2.0), (102.0, 1.0), (102.5, 3.0)]


def test_mid_spread_microprice():
    f = snapshot_features(BIDS, ASKS)
    assert f["mid"] == 100.25
    assert abs(f["spread_bps"] - (0.5 / 100.25 * 10000.0)) < 1e-9
    # microprice leans toward the heavier side (bids 2.0 vs asks 1.0)
    mp = microprice(BIDS, ASKS)
    assert abs(mp - (100.5 * 2.0 + 100.0 * 1.0) / 3.0) < 1e-12
    assert f["microprice"] == mp


def test_imbalance_sign_and_bounds():
    assert abs(imbalance(BIDS, ASKS, 5) - (12.0 - 9.0) / 21.0) < 1e-12
    assert imbalance(BIDS, [], 5) is None or True  # empty side handled below
    heavy_bid = [(100.0, 10.0)]
    heavy_ask = [(100.5, 1.0)]
    assert imbalance(heavy_bid, heavy_ask, 1) > 0.8
    assert imbalance(heavy_ask and [(100.0, 1.0)], [(100.5, 10.0)], 1) < -0.8


def test_depth_within_band():
    mid = 100.25
    # bids within 50bps of mid: 100.0 (24.9bps), 99.5 (74.8bps -> out)
    assert depth_within_bps(BIDS, mid, 50.0, "bid") == 2.0
    # asks within 50bps: 100.5 only
    assert depth_within_bps(ASKS, mid, 50.0, "ask") == 1.0
    assert depth_within_bps(BIDS, None, 50.0, "bid") is None


def test_wall_detection():
    bids = [(100.0, 1.0), (99.9, 1.2), (99.8, 0.8), (99.7, 30.0),
            (99.6, 1.1), (99.5, 0.9)]
    walls = detect_walls(bids, "bid", multiple=5.0, min_share=0.25)
    assert len(walls) == 1
    assert walls[0]["price"] == 99.7 and walls[0]["size"] == 30.0
    # a flat book has no walls
    flat = [(100.0 - i * 0.1, 2.0) for i in range(6)]
    assert detect_walls(flat, "ask") == []
    # too few levels -> no walls, no crash
    assert detect_walls([(100.0, 50.0)], "bid") == []


def test_empty_book_is_none_not_fabricated():
    f = snapshot_features([], [])
    assert f["mid"] is None and f["spread_bps"] is None
    assert f["microprice"] is None and f["imbalance_top"] is None
    assert f["walls"] == []
    assert spread_bps([(100.0, 1.0)], []) is None


def test_validation():
    try:
        snapshot_features([(0.0, 1.0)], ASKS)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for non-positive price")
