"""Proactive System Health Monitor for FRIDAY.

Monitors CPU, RAM, disk space, battery level, and logs status to ~/friday/system_health.log.
Detects potential issues (low disk, critical battery, high load) and provides alerts.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = get_logger("agent.health_monitor")


def disk_mount_point() -> str:
    """The volume FRIDAY measures when it reports disk usage.

    ``C:\\`` on Windows, the filesystem root elsewhere. The report used to
    hardcode the label ``Disk (C:)`` next to a value read from ``/``, so a Linux
    machine announced a C: drive that does not exist - a small thing, but it is
    the same failure as every other one in this file: a sentence about the world
    that the code never checked.
    """
    return "C:\\" if os.name == "nt" else "/"


class SystemHealthMonitor:
    """Proactive system telemetry and health metrics tracker."""

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or (Path.home() / ".friday")
        self.log_file = self.log_dir / "system_health.log"
        self._ensure_log_dir()

    def _ensure_log_dir(self) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.debug(f"Could not create health monitor log directory: {e}")

    def log_health_metric(self, metric_name: str, value: Any, unit: str = "%") -> None:
        """Append metric sample to system_health.log."""
        try:
            now_iso = datetime.now().isoformat()
            line = f"[{now_iso}] METRIC: {metric_name} = {value} {unit}\n"
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.debug(f"Could not log health metric: {e}")

    def collect_health_report(self) -> dict[str, Any]:
        """Collect current system telemetry and return structured health status."""
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(disk_mount_point())
        battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None

        # TASK-FRD-068: report the service's own memory (its cgroup cap),
        # not host RAM. On the live host the cgroup is the kill threshold:
        # host RAM can read 46% while the service is at 98% of its 200 MB
        # cap — and the old code then claimed "no active alerts" while the
        # guard notices listed 93–100% readings (FRD-067, 0/3). When no
        # capped cgroup exists (dev/CI/Windows) the host figures are used
        # exactly as before.
        try:
            from friday.observability.proactive_engine import (
                MEMORY_CRITICAL_PERCENT,
                MEMORY_WARN_PERCENT,
                service_memory,
            )

            svc = service_memory()
        except Exception:
            svc = None
            MEMORY_CRITICAL_PERCENT = 90.0
            MEMORY_WARN_PERCENT = 75.0
        if svc is not None:
            ram_percent = svc["percent"]
            ram_used_mb = svc["used_mb"]
            ram_total_mb = svc["limit_mb"]
            memory_scope = "cgroup"
        else:
            ram_percent = ram.percent
            ram_used_mb = ram.used // (1024**2)
            ram_total_mb = ram.total // (1024**2)
            memory_scope = "host"

        self.log_health_metric("cpu_percent", cpu)
        self.log_health_metric("ram_percent", ram_percent)
        self.log_health_metric("disk_used_percent", disk.percent)
        if battery:
            self.log_health_metric("battery_percent", battery.percent)

        alerts = []
        if disk.percent > 90.0:
            alerts.append(f"Disk space is low ({disk.percent:.1f}% used, {disk.free // (1024**3):,} GB free).")
        if memory_scope == "cgroup":
            # Alert on the same thresholds the OOM guard uses, so this
            # report can never say "no active alerts" while the guard is
            # warning about the same memory.
            if ram_percent >= MEMORY_CRITICAL_PERCENT:
                alerts.append(f"Service memory usage is very high ({ram_percent:.1f}% of the {ram_total_mb:.0f} MB service limit).")
            elif ram_percent >= MEMORY_WARN_PERCENT:
                alerts.append(f"Service memory usage is high ({ram_percent:.1f}% of the {ram_total_mb:.0f} MB service limit).")
        elif ram.percent > 90.0:
            alerts.append(f"System memory usage is very high ({ram.percent:.1f}%).")
        if battery and not battery.power_plugged and battery.percent < 20.0:
            alerts.append(f"Battery is low ({battery.percent:.0f}% remaining).")

        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu,
            "ram_percent": ram_percent,
            "ram_used_mb": ram_used_mb,
            "ram_total_mb": ram_total_mb,
            "memory_scope": memory_scope,
            # Host RAM stays available for diagnostics, under an explicit
            # name, so nothing that quotes "RAM" can mistake it for the
            # service's own memory.
            "host_ram_percent": ram.percent,
            "host_ram_used_mb": ram.used // (1024**2),
            "host_ram_total_mb": ram.total // (1024**2),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free // (1024**3),
            # The volume that was actually measured, so the report can name it
            # instead of asserting a drive letter the machine may not have.
            "disk_mount": disk_mount_point(),
            "battery_percent": battery.percent if battery else None,
            "battery_plugged": battery.power_plugged if battery else None,
            "alerts": alerts,
            "healthy": len(alerts) == 0,
        }


class HealthCheckTool(BaseTool):
    """Tool to inspect proactive system health and active alerts."""

    name = "health_check"
    description = (
        "Inspect proactive system health, resources (CPU, RAM, disk, battery), "
        "and check for hardware or performance alerts."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self, monitor: SystemHealthMonitor | None = None):
        super().__init__()
        self.monitor = monitor or SystemHealthMonitor()

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            report = self.monitor.collect_health_report()
            alerts_str = "\n".join([f"- [ALERT] {a}" for a in report["alerts"]]) if report["alerts"] else "- All metrics nominal. No active alerts."
            batt_info = f"{report['battery_percent']:.0f}% ({'Plugged in' if report['battery_plugged'] else 'On battery'})" if report['battery_percent'] is not None else "N/A"
            # TASK-FRD-068: name the service limit when the figures are the
            # service's own cgroup memory, so the reply cannot be read as
            # host RAM.
            ram_line = f"- RAM: {report['ram_percent']:.1f}% ({report['ram_used_mb']:,} MB / {report['ram_total_mb']:,} MB)"
            if report.get("memory_scope") == "cgroup":
                ram_line = f"- RAM: {report['ram_percent']:.1f}% ({report['ram_used_mb']:,} MB / {report['ram_total_mb']:,} MB service limit)"
            content = (
                f"Proactive Health Status (Status: {'HEALTHY' if report['healthy'] else 'WARNING'}):\n"
                f"- CPU: {report['cpu_percent']:.1f}%\n"
                f"{ram_line}\n"
                f"- Disk ({report.get('disk_mount', disk_mount_point())}): "
                f"{report['disk_percent']:.1f}% used ({report['disk_free_gb']:,} GB free)\n"
                f"- Battery: {batt_info}\n"
                f"Alerts:\n{alerts_str}"
            )
            return ToolResult(name=self.name, content=content, is_error=False, safety_level=self.safety_level)
        except Exception as e:
            return ToolResult(name=self.name, content=f"Failed to check health: {e}", is_error=True, safety_level=self.safety_level)
