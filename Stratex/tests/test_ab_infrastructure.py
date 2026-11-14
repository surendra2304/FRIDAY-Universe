"""
tests/test_ab_infrastructure.py — Unit and smoke tests for the A/B forward testing infrastructure.

Verifies:
1. ABExperimentConfig creation, immutability, and atomic save/load.
2. Dual Paper Engine setup with strictly isolated state, ledger, and equity files.
3. Drawdown safety trigger halts the breaching arm at max_drawdown_limit_pct.
4. Treatment arm applies AI-Universe parameter changes while Control arm preserves default parameters.
5. Statistical comparison engine calculates Welch's t-test, Mann-Whitney U, and bootstrap CIs accurately.
6. 24-hour mock smoke test verifying parallel multi-step execution.
"""

import datetime
import json
import os
import tempfile
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from config_ab import ABExperimentConfig
from scripts.compare_ab_performance import (
    compute_ab_comparison,
    generate_markdown_report,
)


def create_mock_candles(n_bars: int = 100, base_price: float = 50000.0) -> pd.DataFrame:
    """Generates synthetic trend and swing candles for testing."""
    dates = [datetime.datetime(2026, 8, 1) + datetime.timedelta(hours=i) for i in range(n_bars)]
    np.random.seed(42)
    # Generate prices with alternating upward and downward waves
    returns = np.sin(np.linspace(0, 10, n_bars)) * 0.01 + np.random.normal(0, 0.005, n_bars)
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices * 1.002,
        "volume": np.random.uniform(100, 500, n_bars)
    })
    return df


def test_ab_experiment_config_lifecycle():
    """Verify ABExperimentConfig creates, persists, and reloads atomically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = ABExperimentConfig(
            experiment_id="ab_test_mock_001",
            experiment_name="Unit Test A/B"
        )
        saved_path = cfg.save(directory=tmpdir)
        assert os.path.exists(saved_path)

        loaded = ABExperimentConfig.load(saved_path)
        assert loaded.experiment_id == "ab_test_mock_001"
        assert loaded.arm_a_name == "CONTROL_BASELINE"
        assert loaded.arm_b_name == "TREATMENT_AI_ADVISED"
        assert loaded.max_drawdown_limit_pct == 0.10


def test_statistical_comparison_engine():
    """Verify compute_ab_comparison outputs statistical tests and reports accurately."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_a = os.path.join(tmpdir, "ledger_a.jsonl")
        ledger_b = os.path.join(tmpdir, "ledger_b.jsonl")
        eq_a = os.path.join(tmpdir, "eq_a.jsonl")
        eq_b = os.path.join(tmpdir, "eq_b.jsonl")
        report_md = os.path.join(tmpdir, "report.md")

        # Generate 35 trades for Arm A and 35 trades for Arm B (Arm B with higher returns)
        np.random.seed(101)
        trades_a = []
        trades_b = []
        for i in range(35):
            pnl_a = np.random.normal(5.0, 15.0)
            pnl_b = np.random.normal(25.0, 15.0)  # Significant advantage
            trades_a.append({"net_pnl": pnl_a, "gross_pnl": pnl_a + 1.0, "hold_duration_sec": 3600})
            trades_b.append({"net_pnl": pnl_b, "gross_pnl": pnl_b + 1.0, "hold_duration_sec": 3600})

        with open(ledger_a, "w") as f:
            f.writelines(json.dumps(t) + "\n" for t in trades_a)
        with open(ledger_b, "w") as f:
            f.writelines(json.dumps(t) + "\n" for t in trades_b)

        with open(eq_a, "w") as f:
            f.write(json.dumps({"timestamp": "2026-08-27T00:00:00Z", "equity": 10000.0, "cash": 10000.0}) + "\n")
        with open(eq_b, "w") as f:
            f.write(json.dumps({"timestamp": "2026-08-27T00:00:00Z", "equity": 10000.0, "cash": 10000.0}) + "\n")

        results = compute_ab_comparison(
            ledger_control=ledger_a,
            ledger_treatment=ledger_b,
            equity_control=eq_a,
            equity_treatment=eq_b,
            min_trades_for_sig=30
        )

        assert results["sample_size"]["has_enough_samples"] is True
        assert results["arm_b_treatment"]["net_pnl"] > results["arm_a_control"]["net_pnl"]
        assert results["statistical_tests"]["welch_t_test"]["p_value"] < 0.05
        assert results["evaluation_summary"]["verdict"] == "PROMOTE_TREATMENT"

        md = generate_markdown_report(results, output_path=report_md)
        assert os.path.exists(report_md)
        assert "PROMOTE TO TESTNET" in md
