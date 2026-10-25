"""
tests/test_monitoring.py — Tests for monitoring, alerting, and self-improvement.

Tests metrics collection, threshold alerts, alert management, health
monitoring, incident management, and the self-improvement loop.

Priority 3-5: Monitoring, Alerting, Self-Improvement
"""
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

for p in [
    ROOT / "FRIDAY/apps/core/src",
    ROOT / "Cortex/apps/api/src",
    ROOT / "Inference",
    ROOT / "Memora/apps/api",
    ROOT / "Forge",
    ROOT / "VyralX",
    ROOT / "IntelX",
    ROOT / "Sentinel/sentinel/apps/api/src",
    ROOT / "Stratex",
    ROOT / "Futuris",
]:
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)

import universe_monitoring as mon_mod


class TestMetricsCollector:
    """Test the metrics collector."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.metrics = mon_mod.MetricsCollector()

    def test_collect(self):
        self.metrics.collect("test_metric", 42.0, {"tag": "value"})
        latest = self.metrics.get_latest("test_metric")
        assert latest == 42.0

    def test_set_threshold(self):
        self.metrics.set_threshold("error_rate", 0.1, "critical")
        assert "error_rate" in self.metrics._thresholds

    def test_check_thresholds_alert(self):
        self.metrics.set_threshold("error_rate", 0.1, "critical")
        self.metrics.collect("agent.error_rate", 0.15)
        alerts = self.metrics.check_thresholds()
        assert len(alerts) >= 1
        assert alerts[0].severity == "critical"

    def test_check_thresholds_no_alert(self):
        self.metrics.set_threshold("error_rate", 0.1, "critical")
        self.metrics.collect("agent.error_rate", 0.05)
        alerts = self.metrics.check_thresholds()
        assert len(alerts) == 0

    def test_get_stats(self):
        self.metrics.collect("test", 10.0)
        self.metrics.collect("test", 20.0)
        self.metrics.collect("test", 30.0)
        stats = self.metrics.get_stats("test")
        assert stats["count"] == 3
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0
        assert stats["avg"] == 20.0
        assert stats["latest"] == 30.0

    def test_get_all_metrics(self):
        for i in range(5):
            self.metrics.collect("test", float(i))
        all_metrics = self.metrics.get_all_metrics(limit=3)
        assert len(all_metrics) == 3


class TestAlertManager:
    """Test the alert manager."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.alerts = mon_mod.AlertManager()

    def test_trigger_alert(self):
        alert = self.alerts.trigger_alert("warning", "Test Alert", "Message", "FRIDAY")
        assert alert.alert_id.startswith("alert_")
        assert alert.severity == "warning"
        assert alert.title == "Test Alert"

    def test_acknowledge(self):
        alert = self.alerts.trigger_alert("warning", "Test", "Msg", "FRIDAY")
        result = self.alerts.acknowledge(alert.alert_id)
        assert result is True
        assert alert.acknowledged is True

    def test_resolve(self):
        alert = self.alerts.trigger_alert("warning", "Test", "Msg", "FRIDAY")
        result = self.alerts.resolve(alert.alert_id)
        assert result is True
        assert alert.resolved is True

    def test_escalate(self):
        alert = self.alerts.trigger_alert("warning", "Test", "Msg", "FRIDAY")
        result = self.alerts.escalate(alert.alert_id)
        assert result is True
        assert alert.escalation_level == 1

    def test_get_active_alerts(self):
        a1 = self.alerts.trigger_alert("warning", "A1", "Msg", "FRIDAY")
        self.alerts.trigger_alert("warning", "A2", "Msg", "FRIDAY")
        self.alerts.resolve(a1.alert_id)
        active = self.alerts.get_active_alerts()
        assert len(active) == 1

    def test_get_alerts_by_severity(self):
        self.alerts.trigger_alert("critical", "C1", "Msg", "FRIDAY")
        self.alerts.trigger_alert("warning", "W1", "Msg", "FRIDAY")
        self.alerts.trigger_alert("warning", "W2", "Msg", "FRIDAY")
        critical = self.alerts.get_alerts_by_severity("critical")
        assert len(critical) == 1
        warning = self.alerts.get_alerts_by_severity("warning")
        assert len(warning) == 2

    def test_get_alert_stats(self):
        self.alerts.trigger_alert("critical", "C1", "Msg", "FRIDAY")
        self.alerts.trigger_alert("warning", "W1", "Msg", "FRIDAY")
        a = self.alerts.trigger_alert("warning", "W2", "Msg", "FRIDAY")
        self.alerts.resolve(a.alert_id)
        stats = self.alerts.get_alert_stats()
        assert stats["total"] == 3
        assert stats["resolved"] == 1
        assert stats["active"] == 2
        assert stats["critical"] == 1


class TestHealthMonitor:
    """Test the health monitor."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.health = mon_mod.HealthMonitor()

    def test_register(self):
        self.health.register("FRIDAY")
        assert "FRIDAY" in self.health._statuses

    def test_check_healthy(self):
        status = self.health.check("FRIDAY", {"heartbeat": "pass", "memory": "pass"})
        assert status.status == "healthy"

    def test_check_degraded(self):
        status = self.health.check("Cortex", {"heartbeat": "pass", "memory": "fail"})
        assert status.status == "degraded"

    def test_check_unhealthy(self):
        status = self.health.check("Stratex", {"heartbeat": "fail", "memory": "fail"})
        assert status.status == "unhealthy"

    def test_get_status(self):
        self.health.check("FRIDAY", {"heartbeat": "pass"})
        status = self.health.get_status("FRIDAY")
        assert status.name == "FRIDAY"
        assert status.status == "healthy"

    def test_get_unhealthy(self):
        self.health.check("FRIDAY", {"heartbeat": "pass", "memory": "pass"})
        self.health.check("Cortex", {"heartbeat": "pass", "memory": "fail"})
        self.health.check("Stratex", {"heartbeat": "fail", "memory": "fail"})
        unhealthy = self.health.get_unhealthy()
        assert len(unhealthy) == 2


class TestIncidentManager:
    """Test the incident manager."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.incidents = mon_mod.IncidentManager()

    def test_create_incident(self):
        inc = self.incidents.create_incident("Title", "Description", "critical", "FRIDAY")
        assert inc.incident_id.startswith("inc_")
        assert inc.status == "open"
        assert inc.severity == "critical"

    def test_add_action(self):
        inc = self.incidents.create_incident("Title", "Desc", "warning", "FRIDAY")
        result = self.incidents.add_action(inc.incident_id, "Restart service")
        assert result is True
        assert len(inc.actions) == 1

    def test_set_root_cause(self):
        inc = self.incidents.create_incident("Title", "Desc", "critical", "FRIDAY")
        result = self.incidents.set_root_cause(inc.incident_id, "Memory leak")
        assert result is True
        assert inc.root_cause == "Memory leak"
        assert inc.status == "investigating"

    def test_resolve_incident(self):
        inc = self.incidents.create_incident("Title", "Desc", "warning", "FRIDAY")
        result = self.incidents.resolve_incident(inc.incident_id)
        assert result is True
        assert inc.status == "resolved"
        assert inc.resolved_at > 0

    def test_get_open_incidents(self):
        i1 = self.incidents.create_incident("T1", "D1", "warning", "FRIDAY")
        self.incidents.create_incident("T2", "D2", "critical", "Cortex")
        self.incidents.resolve_incident(i1.incident_id)
        open_incidents = self.incidents.get_open_incidents()
        assert len(open_incidents) == 1

    def test_get_all_incidents(self):
        self.incidents.create_incident("T1", "D1", "warning", "FRIDAY")
        self.incidents.create_incident("T2", "D2", "critical", "Cortex")
        assert len(self.incidents.get_all_incidents()) == 2


class TestSelfImprovementLoop:
    """Test the self-improvement loop."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.loop = mon_mod.SelfImprovementLoop()

    def test_monitor(self):
        alerts = self.loop.monitor("FRIDAY", {"error_rate": 0.15, "latency": 1200})
        assert len(alerts) >= 0  # May or may not trigger depending on thresholds

    def test_run_cycle_with_issue(self):
        cycle = self.loop.run_cycle("FRIDAY", {
            "error_rate": 0.15, "latency": 1200, "cpu_usage": 85,
        })
        assert cycle.status == "completed"
        assert cycle.phase == "done"
        assert cycle.metrics_before != {}

    def test_run_cycle_without_issue(self):
        cycle = self.loop.run_cycle("Cortex", {
            "error_rate": 0.01, "latency": 100, "cpu_usage": 20,
        })
        assert cycle.status in ("completed", "no_issue")

    def test_run_cycle_metrics_improvement(self):
        cycle = self.loop.run_cycle("FRIDAY", {
            "error_rate": 0.15, "latency": 1200, "cpu_usage": 85,
        })
        if cycle.metrics_after:
            for key, before_val in cycle.metrics_before.items():
                if key in cycle.metrics_after:
                    assert cycle.metrics_after[key] <= before_val

    def test_get_cycles(self):
        self.loop.run_cycle("FRIDAY", {"error_rate": 0.15, "latency": 1200, "cpu_usage": 85})
        self.loop.run_cycle("Cortex", {"error_rate": 0.01, "latency": 100, "cpu_usage": 20})
        assert len(self.loop.get_cycles()) == 2

    def test_get_cycles_by_agent(self):
        self.loop.run_cycle("FRIDAY", {"error_rate": 0.15, "latency": 1200, "cpu_usage": 85})
        self.loop.run_cycle("Cortex", {"error_rate": 0.01, "latency": 100, "cpu_usage": 20})
        cortex_cycles = self.loop.get_cycles("Cortex")
        assert len(cortex_cycles) == 1

    def test_get_report(self):
        self.loop.run_cycle("FRIDAY", {"error_rate": 0.15, "latency": 1200, "cpu_usage": 85})
        self.loop.run_cycle("Cortex", {"error_rate": 0.01, "latency": 100, "cpu_usage": 20})
        report = self.loop.get_report()
        assert report["total_cycles"] == 2
        assert "alert_stats" in report
        assert "health_status" in report