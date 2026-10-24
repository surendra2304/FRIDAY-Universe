"""
tests/test_real_cross_agent_integration.py — Real cross-agent integration tests.

These tests actually run multiple agents together in real workflows:
- Trading workflow: Stratex signals -> Inference reasons -> Memora stores -> Cortex decides
- Security workflow: Sentinel scans -> IntelX correlates -> Cortex decides -> Memora stores
- Code workflow: Forge generates -> Sentinel scans -> Cortex reviews -> Memora stores
- Content workflow: VyralX predicts -> Futuris forecasts -> Cortex decides -> Memora stores

Priority 1: Real cross-agent integration — not mock or simulated
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load the cross-agent engine
_cross_agent = load_module(
    "FRIDAY/apps/core/src/friday_core/real_cross_agent_engine.py",
    "real_cross_agent_engine"
)


@pytest.fixture
def cross_engine(tmp_path):
    """Create a cross-agent engine with temporary state."""
    return _cross_agent.CrossAgentEngine(state_dir=str(tmp_path / "cross_agent"))


class TestRealTradingWorkflow:
    """Test the full trading workflow with real agents working together."""

    def test_trading_workflow_completes(self, cross_engine):
        """Test that the full trading workflow runs end to end."""
        # Generate realistic price data
        prices = []
        price = 100.0
        for i in range(100):
            price += (i % 15 - 7) * 0.15
            if i % 30 == 0:
                price += 1.0
            prices.append(price)

        result = cross_engine.run_trading_workflow("TEST", prices)

        assert result.status == "completed"
        assert len(result.steps) == 5
        assert all(s.status == "completed" for s in result.steps)
        assert result.final_output in ("Execute", "Skip")
        assert result.total_time_ms > 0

    def test_trading_workflow_steps_have_results(self, cross_engine):
        """Test that each step in the workflow produces a result."""
        prices = [100 + i * 0.5 for i in range(60)]
        result = cross_engine.run_trading_workflow("TEST", prices)

        # Step 1: Signals generated
        assert result.steps[0].result["signal_count"] >= 0
        # Step 2: Backtest completed
        assert "return_pct" in result.steps[1].result
        # Step 3: Bayesian reasoning
        assert "buy_probability" in result.steps[2].result
        # Step 4: Memory stored
        assert "memory_id" in result.steps[3].result
        # Step 5: Decision made
        assert "decision" in result.steps[4].result


class TestRealSecurityWorkflow:
    """Test the full security workflow with real agents working together."""

    def test_security_workflow_completes(self, cross_engine):
        """Test that the full security workflow runs end to end."""
        code = 'password = "admin123"\ndef login():\n    return True'
        logs = "SELECT * FROM users WHERE id='1' OR '1'='1' --"

        result = cross_engine.run_security_workflow(code, logs)

        assert result.status == "completed"
        assert len(result.steps) == 5
        assert all(s.status == "completed" for s in result.steps)
        assert result.final_output in ("Block Immediately", "Monitor", "Investigate")

    def test_security_workflow_detects_threats(self, cross_engine):
        """Test that the security workflow actually detects threats."""
        code = 'password = "supersecret123"'
        logs = "<script>alert('xss')</script> union select password from users"

        result = cross_engine.run_security_workflow(code, logs)

        # Step 1 should find vulnerabilities
        assert result.steps[0].result["vuln_count"] >= 1
        # Step 2 should detect threats
        assert result.steps[1].result["threat_count"] >= 1


class TestRealCodeWorkflow:
    """Test the full code workflow with real agents working together."""

    def test_code_workflow_completes(self, cross_engine):
        """Test that the full code workflow runs end to end."""
        result = cross_engine.run_code_workflow("function that adds two numbers")

        assert result.status == "completed"
        assert len(result.steps) == 5
        assert all(s.status == "completed" for s in result.steps)
        assert result.final_output in ("Deploy", "Refactor")

    def test_code_workflow_generates_and_scans(self, cross_engine):
        """Test that code is generated and scanned for vulnerabilities."""
        result = cross_engine.run_code_workflow("function that adds two numbers")

        # Step 1: Code generated
        assert result.steps[0].result["lines"] > 0
        # Step 2: Tests generated
        assert result.steps[1].result["test_count"] >= 1
        # Step 3: Code scanned
        assert "vuln_count" in result.steps[2].result
        # Step 4: Review decision
        assert "score" in result.steps[3].result


class TestRealContentWorkflow:
    """Test the full content workflow with real agents working together."""

    def test_content_workflow_completes(self, cross_engine):
        """Test that the full content workflow runs end to end."""
        result = cross_engine.run_content_workflow(
            "How to Build AI Apps",
            "A comprehensive tutorial on building AI applications"
        )

        assert result.status == "completed"
        assert len(result.steps) == 4
        assert all(s.status == "completed" for s in result.steps)
        assert result.final_output in ("Publish Now", "Schedule")

    def test_content_workflow_predicts_and_forecasts(self, cross_engine):
        """Test that content performance is predicted and growth forecasted."""
        result = cross_engine.run_content_workflow(
            "Top 10 AI Trends 2024",
            "The best AI trends you need to know about"
        )

        # Step 1: Performance predicted
        assert "engagement_score" in result.steps[0].result
        # Step 2: Growth forecasted
        assert "forecast" in result.steps[1].result
        # Step 3: Decision made
        assert "decision" in result.steps[2].result


class TestUniverseStatus:
    """Test the universe status report."""

    def test_universe_status(self, cross_engine):
        """Test that universe status is reported correctly."""
        status = cross_engine.get_universe_status()

        assert "decision_engine" in status
        assert "reasoning_engine" in status
        assert "memory_engine" in status
        assert "trading_engine" in status
        assert "security_engine" in status
        assert "threat_intel" in status
        assert "forecast_engine" in status
        assert "content_engine" in status

    def test_universe_status_after_workflows(self, cross_engine):
        """Test that universe status reflects completed workflows."""
        # Run a trading workflow
        prices = [100 + i * 0.5 for i in range(60)]
        cross_engine.run_trading_workflow("TEST", prices)

        # Run a security workflow
        cross_engine.run_security_workflow("password = 'x'", "union select 1")

        status = cross_engine.get_universe_status()

        # Memory should have stored items
        assert status["memory_engine"]["total_memories"] >= 2
        # Decisions should have been made
        assert status["decision_engine"]["total_decisions"] >= 2
