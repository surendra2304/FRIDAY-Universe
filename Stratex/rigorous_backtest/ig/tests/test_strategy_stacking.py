"""Tests for TASK-IG-STR-12 strategy_stacking (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.strategy_stacking import compose, normalise_weights, stack_stats

A = [0.10, -0.05, 0.02]
B = [0.00, 0.05, -0.01]


def test_weights_normalise():
    w = normalise_weights({"a": 3.0, "b": 1.0})
    assert w == {"a": 0.75, "b": 0.25}
    try:
        normalise_weights({"a": -1.0, "b": 2.0})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for negative weight")


def test_compose_weighted_mix():
    out = compose({"A": A, "B": B}, {"A": 1.0, "B": 1.0})
    assert out == [0.05, 0.0, 0.005]
    only_a = compose({"A": A, "B": B}, {"A": 1.0})
    assert only_a == A


def test_compose_rejects_misalignment_and_unknown():
    try:
        compose({"A": A, "B": [0.01]}, {"A": 1.0, "B": 1.0})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for misaligned series")
    try:
        compose({"A": A}, {"ZZZ": 1.0})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown strategy")


def test_stack_stats_known_curve():
    combined = compose({"A": A, "B": B}, {"A": 1.0, "B": 1.0})
    st = stack_stats(combined, {"A": A, "B": B}, {"A": 1.0, "B": 1.0})
    expected_total = 1.05 * 1.0 * 1.005 - 1.0
    assert abs(st["total_return"] - expected_total) < 1e-12
    assert st["periods"] == 3
    assert 0.0 <= st["max_drawdown"] < 0.01
    assert abs(st["contribution"]["A"] - 0.5 * sum(A)) < 1e-12
    dd = stack_stats([0.10, -0.20, 0.05])
    assert dd["max_drawdown"] > 0.19  # 1.10 -> 0.88 is a 20% peak-to-trough
    assert "RD programme bar" in st["note"]
