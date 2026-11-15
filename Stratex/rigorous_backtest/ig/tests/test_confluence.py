"""Tests for TASK-IG-STR-06 confluence (stdlib-only, offline).

The fixtures encode the declared rules by construction: a leg up
100 -> 120, a retracement into the Fib zone, then a close above 120
must signal; a shallow retracement or a close below the leg origin
must not.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.confluence import generate_signals


def _c(h, l, c):
    return {"high": h, "low": l, "close": c}


def _long_setup(retrace_low=109.0, bos_close=121.0, kill=False):
    # calm base, swing low at index 3 (low 100), leg up to swing high
    # at index 7 (high 120), retrace, then BOS close.
    candles = [
        _c(104, 102, 103), _c(104, 101, 102), _c(103, 100.5, 101),
        _c(102, 100, 101),                       # swing low L=100 (idx 3)
        _c(108, 102, 107), _c(114, 108, 113), _c(118, 112, 117),
        _c(120, 114, 118),                       # swing high H=120 (idx 7)
        _c(116, 112, 113),
        _c(118, retrace_low, (118 + retrace_low) / 2),  # the retrace candle
        _c(116, 112, 114),                       # low 112 stays above the zone top (110)
    ]
    if kill:
        candles.append(_c(110, 98, 99))          # close below L -> dead
    else:
        candles.append(_c(122, 116, bos_close))  # BOS close above H
        candles.append(_c(123, 118, 122))
        candles.append(_c(124, 119, 123))
    return candles


def test_long_signal_fires_with_declared_geometry():
    sigs = [s for s in generate_signals(_long_setup()) if s["direction"] == "long"]
    assert len(sigs) == 1
    s = sigs[0]
    assert s["entry"] == 121.0
    assert s["stop"] == 100.0
    assert abs(s["target1"] - (100 + 1.272 * 20)) < 1e-9
    assert abs(s["target2"] - (100 + 1.618 * 20)) < 1e-9


def test_shallow_retracement_no_signal():
    # retrace only to 115: zone is [107.64, 110] for a 20-range leg
    sigs = [s for s in generate_signals(_long_setup(retrace_low=115.0))
            if s["direction"] == "long"]
    assert sigs == []


def test_close_below_origin_kills_leg():
    sigs = [s for s in generate_signals(_long_setup(kill=True))
            if s["direction"] == "long"]
    assert sigs == []


def test_flat_series_no_signals():
    flat = [_c(100, 99, 99.5) for _ in range(20)]
    assert generate_signals(flat) == []


def test_short_mirror_fires():
    # invert the long fixture around 110: highs/lows swap roles
    long_c = _long_setup()
    short_c = [{"high": 220 - c["low"], "low": 220 - c["high"],
                "close": 220 - c["close"]} for c in long_c]
    sigs = [s for s in generate_signals(short_c) if s["direction"] == "short"]
    assert len(sigs) == 1
    s = sigs[0]
    assert s["entry"] == 220 - 121.0
    assert s["stop"] == 220 - 100.0
    assert abs(s["target1"] - (120 - 1.272 * 20)) < 1e-9
