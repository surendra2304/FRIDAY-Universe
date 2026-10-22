"""
Production Monitoring, System Telemetry, Alerting, and Prometheus Metrics Exporter for Project FORGE.
"""

import shutil
import time
from collections import defaultdict
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("monitoring.production")


class AlertStatus(BaseModel):
    has_active_alerts: bool = False
    alerts: list[str] = Field(default_factory=list)


class ProductionMonitor:
    """Tracks application request counts, error rates, system resource usage, and exports Prometheus metrics."""

    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.endpoint_requests: dict[str, int] = defaultdict(int)
        self.task_submissions = 0
        self.task_completions = 0
        self.task_failures = 0
        self.verification_passes = 0
        self.verification_fails = 0
        self.security_scans_total = 0
        self.security_scans_passed = 0
        self.security_scans_blocked = 0
        self.security_findings_total = 0
        self.intelx_research_queries_total = 0
        self.research_informed_builds_total = 0
        self.futuris_predictions_consulted_total = 0
        self.prediction_informed_template_selections_total = 0
        self.capacity_aware_queuing_decisions_total = 0
        self.start_time = time.time()

    def record_request(self, endpoint: str, is_error: bool = False):
        self.total_requests += 1
        self.endpoint_requests[endpoint] += 1
        if is_error:
            self.total_errors += 1

    def record_task_event(self, event_type: str):
        if event_type == "submitted":
            self.task_submissions += 1
        elif event_type == "completed":
            self.task_completions += 1
        elif event_type == "failed":
            self.task_failures += 1

    def record_verification(self, passed: bool):
        if passed:
            self.verification_passes += 1
        else:
            self.verification_fails += 1

    def record_security_scan(self, passed: bool, blocked: bool, findings_count: int = 0):
        self.security_scans_total += 1
        self.security_findings_total += findings_count
        if passed and not blocked:
            self.security_scans_passed += 1
        if blocked:
            self.security_scans_blocked += 1

    def record_intelx_query(self):
        self.intelx_research_queries_total += 1

    def record_research_informed_build(self):
        self.research_informed_builds_total += 1

    def record_futuris_consultation(self):
        self.futuris_predictions_consulted_total += 1

    def record_prediction_informed_selection(self):
        self.prediction_informed_template_selections_total += 1

    def record_capacity_queue_decision(self):
        self.capacity_aware_queuing_decisions_total += 1

    def get_system_metrics(self) -> dict[str, Any]:
        """Collect current host CPU, RAM, and workspace disk metrics."""
        settings = get_settings()
        if psutil is not None:
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            mem_pct = mem.percent
            mem_used_mb = round(mem.used / (1024 * 1024), 1)
        else:
            cpu_pct = 0.0
            mem_pct = 0.0
            mem_used_mb = 0.0

        # Disk space for workspaces directory
        disk_pct = 0.0
        try:
            ws_path = settings.workspaces_dir
            if not ws_path.exists():
                ws_path = settings.base_dir
            usage = shutil.disk_usage(str(ws_path))
            disk_pct = round((usage.used / usage.total) * 100.0, 1)
        except Exception:
            pass

        return {
            "cpu_percent": cpu_pct,
            "memory_percent": mem_pct,
            "memory_used_mb": mem_used_mb,
            "disk_used_percent": disk_pct,
            "uptime_seconds": round(time.time() - self.start_time, 1),
        }

    def check_alerts(self) -> AlertStatus:
        """Evaluate telemetry against production operational alert thresholds."""
        alerts = []
        sys_m = self.get_system_metrics()

        # 1. Disk usage > 80%
        if sys_m["disk_used_percent"] > 80.0:
            alerts.append(
                f"High disk space usage ({sys_m['disk_used_percent']}%) on workspaces volume."
            )

        # 2. Error rate > 5%
        if self.total_requests > 20:
            err_rate = (self.total_errors / self.total_requests) * 100.0
            if err_rate > 5.0:
                alerts.append(f"Elevated HTTP error rate ({err_rate:.1f}% > 5.0%).")

        # 3. Task failure rate > 20%
        total_finished = self.task_completions + self.task_failures
        if total_finished >= 5:
            fail_rate = (self.task_failures / total_finished) * 100.0
            if fail_rate > 20.0:
                alerts.append(f"Elevated task synthesis failure rate ({fail_rate:.1f}% > 20.0%).")

        return AlertStatus(has_active_alerts=len(alerts) > 0, alerts=alerts)

    def export_prometheus_metrics(self) -> str:
        """Generate standard Prometheus-compatible exposition format text."""
        sys_m = self.get_system_metrics()
        lines = [
            "# HELP forge_uptime_seconds Total runtime of FORGE engine in seconds.",
            "# TYPE forge_uptime_seconds gauge",
            f"forge_uptime_seconds {sys_m['uptime_seconds']}",
            "",
            "# HELP forge_requests_total Total HTTP requests processed.",
            "# TYPE forge_requests_total counter",
            f"forge_requests_total {self.total_requests}",
            "",
            "# HELP forge_errors_total Total HTTP errors encountered.",
            "# TYPE forge_errors_total counter",
            f"forge_errors_total {self.total_errors}",
            "",
            "# HELP forge_tasks_total Total tasks processed by outcome.",
            "# TYPE forge_tasks_total counter",
            f'forge_tasks_total{{status="submitted"}} {self.task_submissions}',
            f'forge_tasks_total{{status="completed"}} {self.task_completions}',
            f'forge_tasks_total{{status="failed"}} {self.task_failures}',
            "",
            "# HELP forge_verifications_total Total verification outcomes.",
            "# TYPE forge_verifications_total counter",
            f'forge_verifications_total{{result="passed"}} {self.verification_passes}',
            f'forge_verifications_total{{result="failed"}} {self.verification_fails}',
            "",
            "# HELP forge_security_scans_total Total pre-verification output security scans.",
            "# TYPE forge_security_scans_total counter",
            f'forge_security_scans_total{{result="passed"}} {self.security_scans_passed}',
            f'forge_security_scans_total{{result="blocked"}} {self.security_scans_blocked}',
            "",
            "# HELP forge_security_findings_total Total security vulnerabilities identified across scans.",
            "# TYPE forge_security_findings_total counter",
            f"forge_security_findings_total {self.security_findings_total}",
            "",
            "# HELP forge_intelx_research_queries_total Total IntelX technical research queries performed.",
            "# TYPE forge_intelx_research_queries_total counter",
            f"forge_intelx_research_queries_total {self.intelx_research_queries_total}",
            "",
            "# HELP forge_research_informed_builds_total Total builds guided by IntelX technical research.",
            "# TYPE forge_research_informed_builds_total counter",
            f"forge_research_informed_builds_total {self.research_informed_builds_total}",
            "",
            "# HELP forge_futuris_predictions_consulted_total Total Futuris predictions consulted before build.",
            "# TYPE forge_futuris_predictions_consulted_total counter",
            f"forge_futuris_predictions_consulted_total {self.futuris_predictions_consulted_total}",
            "",
            "# HELP forge_prediction_informed_template_selections_total Total template selections optimized by Futuris success predictions.",
            "# TYPE forge_prediction_informed_template_selections_total counter",
            f"forge_prediction_informed_template_selections_total {self.prediction_informed_template_selections_total}",
            "",
            "# HELP forge_capacity_aware_queuing_decisions_total Total task queueing decisions based on Futuris capacity exhaustion forecasts.",
            "# TYPE forge_capacity_aware_queuing_decisions_total counter",
            f"forge_capacity_aware_queuing_decisions_total {self.capacity_aware_queuing_decisions_total}",
            "",
            "# HELP forge_system_cpu_percent Host CPU utilization percentage.",
            "# TYPE forge_system_cpu_percent gauge",
            f"forge_system_cpu_percent {sys_m['cpu_percent']}",
            "",
            "# HELP forge_system_memory_percent Host Memory utilization percentage.",
            "# TYPE forge_system_memory_percent gauge",
            f"forge_system_memory_percent {sys_m['memory_percent']}",
            "",
            "# HELP forge_system_disk_percent Workspace disk utilization percentage.",
            "# TYPE forge_system_disk_percent gauge",
            f"forge_system_disk_percent {sys_m['disk_used_percent']}",
        ]
        return "\n".join(lines) + "\n"


production_monitor = ProductionMonitor()
