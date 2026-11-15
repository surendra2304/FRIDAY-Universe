"""System Control tool for process inspection and service status.

TASK-FRD-002 (2026-11-15): process termination was removed from this
SAFE-classified tool. It previously exposed a working ``terminate_process``
action (real ``psutil`` terminate calls behind only a small protected-name
list) that the headless production authorizer auto-approved with no
confirmation — while the dedicated ``kill_process`` tool is classified
DANGEROUS and always requires explicit authorization. Termination now lives
only in ``kill_process``, behind that gate.
"""

import os
from typing import Any

import psutil

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

logger = get_logger("tools.system_control")


class SystemControlTool(BaseTool):
    """System control tool for listing processes and checking resources."""

    name = "system_control"
    description = (
        "Perform system diagnostics. Actions: 'list_processes' (top processes by memory/cpu), "
        "'system_status' (CPU, RAM, battery, disk telemetry). Process termination is not offered "
        "here; use the 'kill_process' tool, which requires explicit authorization."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_processes", "system_status"],
                "description": "System control action to execute.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of processes to return (default: 10).",
            },
        },
        "required": ["action"],
    }

    def execute(
        self,
        action: str = "",
        process_name: str = "",
        limit: int = 10,
        **kwargs: Any,
    ) -> ToolResult:
        act = (action or "").strip().lower()

        if act == "system_status":
            try:
                cpu = psutil.cpu_percent(interval=0.1)
                ram = psutil.virtual_memory()
                from friday.tools.builtin.health_monitor import disk_mount_point

                disk_mount = disk_mount_point()
                disk = psutil.disk_usage(disk_mount)
                battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
                batt_str = f"{battery.percent:.0f}% ({'Plugged in' if battery.power_plugged else 'Battery'})" if battery else "N/A"
                report = (
                    f"System Status:\n"
                    f"- CPU Usage: {cpu:.1f}%\n"
                    f"- RAM: {ram.percent:.1f}% used ({ram.used // (1024**2):,} MB / {ram.total // (1024**2):,} MB)\n"
                    f"- Disk ({disk_mount}): {disk.percent:.1f}% used ({disk.free // (1024**3):,} GB free)\n"
                    f"- Battery: {batt_str}"
                )
                return ToolResult(name=self.name, content=report, is_error=False, safety_level=self.safety_level)
            except Exception as e:
                return ToolResult(name=self.name, content=f"Failed to query system status: {e}", is_error=True, safety_level=self.safety_level)

        if act == "list_processes":
            try:
                procs = []
                for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
                    try:
                        info = p.info
                        procs.append(info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                procs.sort(key=lambda x: x.get("memory_percent") or 0.0, reverse=True)
                top = procs[: max(1, min(50, limit))]
                lines = [f"{p['pid']:>6} | {p['name']:<25} | RAM: {p['memory_percent']:.1f}%" for p in top]
                out = "PID    | Process Name              | Memory\n" + "-" * 45 + "\n" + "\n".join(lines)
                return ToolResult(name=self.name, content=out, is_error=False, safety_level=self.safety_level)
            except Exception as e:
                return ToolResult(name=self.name, content=f"Failed to list processes: {e}", is_error=True, safety_level=self.safety_level)

        # 'terminate_process' intentionally falls through to the unknown-action
        # error below (TASK-FRD-002): termination is only available via the
        # DANGEROUS-classified 'kill_process' tool, behind its authorization gate.
        return ToolResult(name=self.name, content=f"Unknown action '{action}'.", is_error=True, safety_level=self.safety_level)
