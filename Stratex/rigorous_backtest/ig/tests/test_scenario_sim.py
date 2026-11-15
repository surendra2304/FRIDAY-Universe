"""Tests for TASK-IG-STR-04 scenario_sim (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.scenario_sim import pool_from_spec, simulate

POOL = [2.0, 2.0, -1.0, -1.0, 2.0, -1.0, 3.0, -1.0, -1.0, 2.0]


def test_deterministic_for_seed():
    a = simulate(POOL, trades_per_path=50, n_paths=300, seed=7)
    b = simulate(POOL, trades_per_path=50, n_paths=300, seed=7)
    assert a == b


def test_positive_expectancy_pool_mostly_profits():
    out = simulate(POOL, trades_per_path=100, n_paths=1000, seed=3)
    assert out["sample_expectancy_r"] > 0.3
    assert out["p_profit"] > 0.9
    pct = out["final_r_percentiles"]
    assert pct["p5"] < pct["p50"] < pct["p95"]
    assert out["max_dd_r_percentiles"]["p99"] >= out["max_dd_r_percentiles"]["p50"]


def test_all_losses_never_profit():
    out = simulate([-1.0, -0.5], trades_per_path=20, n_paths=200, seed=1)
    assert out["p_profit"] == 0.0
    assert out["final_r_percentiles"]["p95"] < 0


def test_sizing_kill_and_ruin_accounting():
    # risking 100% per trade on a pool containing -1R means ruin is certain
    out = simulate(POOL, trades_per_path=50, n_paths=300, seed=5,
                   risk_per_trade_pct=1.0, kill_dd_pct=0.05)
    assert out["p_ruin"] > 0.9
    # tiny risk: kill breaches still possible via drawdown in R terms
    out2 = simulate(POOL, trades_per_path=100, n_paths=300, seed=5,
                    risk_per_trade_pct=0.001, kill_dd_pct=0.05)
    assert out2["p_ruin"] == 0.0
    assert 0.0 <= out2["p_kill_breach"] <= 1.0


def test_pool_from_spec():
    pool = pool_from_spec(0.5, 2.0, 1.0, n=400, seed=2)
    assert set(pool) <= {2.0, -1.0}
    wins = sum(1 for x in pool if x > 0) / len(pool)
    assert 0.4 < wins < 0.6
    try:
        pool_from_spec(1.5, 2.0, 1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for win_rate > 1")


def test_validation_and_disclaimer():
    try:
        simulate([], trades_per_path=10)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for empty pool")
    out = simulate(POOL, trades_per_path=5, n_paths=10, seed=0)
    assert "not a forecast" in out["disclaimer"]
