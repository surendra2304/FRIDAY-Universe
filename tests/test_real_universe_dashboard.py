"""
tests/test_real_universe_dashboard.py — Functional tests for universe dashboard.

Tests real working dashboard:
- AgentStatusMonitor: health monitoring
- AlertManager: alert management
- UniverseDashboardServer: unified dashboard
"""
import sys
import pytest
import os
import tempfile
import shutil
import importlib.util
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(relpath, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


dash = load_module("FRIDAY/apps/core/src/friday_core/universe_dashboard.py", "dashboard")


@pytest.fixture
def temp_state():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestAgentStatusMonitor:
    @pytest.fixture
    def engine(self, temp_state):
        return dash.AgentStatusMonitor(state_dir=os.path.join(temp_state, "monitor"))

    def test_register_agent(self, engine):
        status = engine.register_agent("test_agent", "Test Agent", 3, 5)
        assert status.status == "healthy"
        assert status.layers == 3
        assert status.engine_count == 5

    def test_heartbeat(self, engine):
        engine.register_agent("test_agent", "Test", 2, 3)
        assert engine.heartbeat("test_agent") is True
        assert engine.heartbeat("nonexistent") is False

    def test_report_error(self, engine):
        engine.register_agent("test_agent", "Test", 2, 3)
        for i in range(6):
            engine.report_error("test_agent", f"Error {i}")
        status = engine.get_status()
        agent = [a for a in status["agents"] if a["agent_id"] == "test_agent"][0]
        assert agent["status"] == "degraded"
        assert agent["error_count"] == 6

    def test_register_all(self, engine):
        engine.register_all_agents()
        status = engine.get_status()
        assert len(status["agents"]) == 9
        assert all(a["status"] == "healthy" for a in status["agents"])

    def test_state_persistence(self, temp_state):
        monitor_dir = os.path.join(temp_state, "monitor")
        engine1 = dash.AgentStatusMonitor(state_dir=monitor_dir)
        engine1.register_agent("persistent", "Persistent", 3, 4)

        # Create new instance - should load from state
        engine2 = dash.AgentStatusMonitor(state_dir=monitor_dir)
        status = engine2.get_status()
        assert len(status["agents"]) == 1
        assert status["agents"][0]["agent_id"] == "persistent"


class TestAlertManager:
    def test_check_rule(self):
        am = dash.AlertManager()
        alert = am.check_rule("high_error_count", 6.0)
        assert alert is not None
        assert alert.level == "error"

    def test_no_alert_below_threshold(self):
        am = dash.AlertManager()
        alert = am.check_rule("high_error_count", 3.0)
        assert alert is None

    def test_ack_alert(self):
        am = dash.AlertManager()
        alert = am.check_rule("memory_high", 0.9)
        assert alert is not None
        assert am.ack_alert(alert.alert_id) is True

    def test_get_alerts(self):
        am = dash.AlertManager()
        am.check_rule("cpu_high", 0.8)
        am.check_rule("memory_high", 0.9)
        alerts = am.get_alerts()
        assert len(alerts) == 2

    def test_unacked_only(self):
        am = dash.AlertManager()
        alert1 = am.check_rule("cpu_high", 0.8)
        am.check_rule("memory_high", 0.9)
        am.ack_alert(alert1.alert_id)
        unacked = am.get_alerts(unacked_only=True)
        assert len(unacked) == 1


class TestUniverseDashboardServer:
    @pytest.fixture
    def engine(self, temp_state):
        return dash.UniverseDashboardServer(state_dir=os.path.join(temp_state, "dash"))

    def test_dashboard_data(self, engine):
        data = engine.get_dashboard_data()
        assert data["version"] == "3.0.0"
        assert len(data["agents"]) == 9
        assert "alerts" in data
        assert "pipeline" in data
        assert "workflows" in data

    def test_process_security_event(self, engine):
        result = engine.process_security_event("Failed login: admin", "eval('1+1')")
        assert "results" in result
        assert len(result["results"]) >= 1

    def test_process_trading_event(self, engine):
        prices = [100 + i for i in range(10)]
        result = engine.process_trading_event("TEST", prices)
        assert "results" in result
        assert len(result["results"]) >= 1

    def test_get_benchmarks(self, engine):
        benchmarks = engine.get_benchmarks()
        assert len(benchmarks) == 5
        assert all("ops_per_second" in b for b in benchmarks.values())
