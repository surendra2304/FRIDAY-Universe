"""Regression tests for TASK-FRD-068 (FRIDAY memory reporting fix).

FRD-067 proved the defect live: FRIDAY's chat answers quoted HOST memory
(875 MB of 1,905 MB, ~46%) while the service's own cgroup sat at 95–99.9%
of its 200 MB cap, and claimed "no active alerts" while the guard notices
listed 93–100% readings — 0/3 correct. Every status/memory path must now
report the service's own cgroup memory when the process runs under a capped
memory cgroup, and fall back to host memory exactly as before when it does
not (dev machines, CI, Windows, containers without a cap).

The cgroup trees below are fabricated exactly like the FRD-041 guard tests
(``CGROUP_BASE`` monkeypatched to a tmp dir); the host figures are the
FRD-067 live numbers so a test that still quoted host memory would fail.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import friday.observability.proactive_engine as engine_module
from friday.observability.proactive_engine import service_memory

# FRD-067 live numbers: host 875 MB of 1,905 MB (45.9%); service cgroup
# 204,951,552 of 209,715,200 (97.7% of the 200 MB cap).
HOST_PERCENT = 45.9
HOST_TOTAL = 1905 * 1024 * 1024
HOST_USED = 875 * 1024 * 1024
CGROUP_LIMIT = 209715200
CGROUP_USED = 204951552


def _write_cgroup_v2(base: Path, *, limit=CGROUP_LIMIT, used=CGROUP_USED) -> None:
    (base / "memory.max").write_text(str(limit))
    (base / "memory.current").write_text(str(used))


def _mock_host_psutil(monkeypatch):
    """Host RAM reads as the FRD-067 live host (45.9% of 1,905 MB)."""
    import psutil

    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            percent=HOST_PERCENT, total=HOST_TOTAL, used=HOST_USED,
            available=HOST_TOTAL - HOST_USED, free=HOST_TOTAL - HOST_USED,
        ),
    )
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 10.0)
    monkeypatch.setattr(
        psutil, "disk_usage",
        lambda path: SimpleNamespace(percent=20.0, total=100 * 1024**3,
                                     used=20 * 1024**3, free=80 * 1024**3),
    )
    monkeypatch.setattr(psutil, "sensors_battery", lambda: None)


# -- service_memory() helper ------------------------------------------------


def test_service_memory_capped(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    result = service_memory()
    assert result == {
        "percent": 97.7,
        "used_mb": 195.5,
        "limit_mb": 200.0,
        "scope": "cgroup",
    }


def test_service_memory_unlimited(tmp_path, monkeypatch):
    (tmp_path / "memory.max").write_text("max")
    (tmp_path / "memory.current").write_text("12345678")
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    assert service_memory() is None


def test_service_memory_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    assert service_memory() is None


# -- health_check tool (the FRD-067 wrong reply) ----------------------------


def test_health_check_reports_cgroup_pressure(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    from friday.tools.builtin.health_monitor import HealthCheckTool

    from friday.tools.builtin.health_monitor import HealthCheckTool, SystemHealthMonitor

    report = SystemHealthMonitor(log_dir=tmp_path).collect_health_report()
    assert report["memory_scope"] == "cgroup"
    assert report["ram_percent"] == 97.7
    assert report["ram_used_mb"] == 195.5
    assert report["ram_total_mb"] == 200.0
    assert report["host_ram_percent"] == HOST_PERCENT
    assert report["healthy"] is False
    assert any("Service memory usage is very high" in a for a in report["alerts"])

    tool_result = HealthCheckTool(
        monitor=SystemHealthMonitor(log_dir=tmp_path)
    ).execute()
    assert not tool_result.is_error
    assert "97.7%" in tool_result.content
    assert "200.0 MB service limit" in tool_result.content
    assert "875" not in tool_result.content  # host figure must not leak
    assert "No active alerts" not in tool_result.content
    assert "WARNING" in tool_result.content


def test_health_check_calm_cgroup_still_reports_no_alerts(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path, used=100 * 1024 * 1024)  # 50% of the cap
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    from friday.tools.builtin.health_monitor import (
        HealthCheckTool,
        SystemHealthMonitor,
    )

    report = SystemHealthMonitor(log_dir=tmp_path).collect_health_report()
    assert report["memory_scope"] == "cgroup"
    assert report["ram_percent"] == 50.0
    assert report["healthy"] is True
    tool_result = HealthCheckTool(
        monitor=SystemHealthMonitor(log_dir=tmp_path)
    ).execute()
    assert "No active alerts" in tool_result.content
    assert "50.0%" in tool_result.content


def test_health_check_host_fallback_without_cgroup(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    from friday.tools.builtin.health_monitor import SystemHealthMonitor

    report = SystemHealthMonitor(log_dir=tmp_path).collect_health_report()
    assert report["memory_scope"] == "host"
    assert report["ram_percent"] == HOST_PERCENT
    assert report["ram_used_mb"] == 875
    assert report["ram_total_mb"] == 1905
    assert report["healthy"] is True


# -- get_system_resources tool ----------------------------------------------


def test_get_system_resources_reports_cgroup(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda *a, **k: [])
    from friday.tools.builtin.system_monitor import GetSystemResourcesTool

    result = GetSystemResourcesTool().execute()
    assert not result.is_error
    assert "RAM Usage: 97.7%" in result.content
    assert "195.5 MB / 200.0 MB service limit" in result.content
    assert "875" not in result.content
    assert result.metadata["memory_scope"] == "cgroup"
    assert result.metadata["host_ram_percent"] == HOST_PERCENT


def test_get_system_resources_host_fallback_without_cgroup(tmp_path, monkeypatch):
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda *a, **k: [])
    from friday.tools.builtin.system_monitor import GetSystemResourcesTool

    result = GetSystemResourcesTool().execute()
    assert not result.is_error
    assert "RAM Usage: 45.9%" in result.content
    assert result.metadata["memory_scope"] == "host"


# -- system_control system_status action ------------------------------------


def test_system_control_status_reports_cgroup(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    from friday.tools.builtin.system_control import SystemControlTool

    result = SystemControlTool().execute(action="system_status")
    assert not result.is_error
    assert "97.7%" in result.content
    assert "200.0 MB service limit" in result.content
    assert "875" not in result.content


# -- audit skill rating follows the service figure --------------------------


def test_system_health_audit_rating_follows_cgroup(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda *a, **k: [])
    from friday.skills.builtins.system_health_audit import SystemHealthAuditSkill
    from friday.tools.builtin.system_monitor import GetSystemResourcesTool

    registry = {"get_system_resources": GetSystemResourcesTool()}
    result = SystemHealthAuditSkill().execute(
        "audit system health", tool_registry=registry
    )
    assert result.success
    assert "ATTENTION" in result.output
    assert "97.7%" in result.output
    assert "OPTIMAL" not in result.output


def test_system_health_audit_rating_optimal_when_calm(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path, used=100 * 1024 * 1024)  # 50% of the cap
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    import psutil

    monkeypatch.setattr(psutil, "process_iter", lambda *a, **k: [])
    from friday.skills.builtins.system_health_audit import SystemHealthAuditSkill
    from friday.tools.builtin.system_monitor import GetSystemResourcesTool

    registry = {"get_system_resources": GetSystemResourcesTool()}
    result = SystemHealthAuditSkill().execute(
        "audit system health", tool_registry=registry
    )
    assert result.success
    assert "OPTIMAL" in result.output
    assert "ATTENTION" not in result.output


# -- controller self-repair memory check ------------------------------------


@pytest.mark.asyncio
async def test_self_repair_memory_check_reports_cgroup(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    _mock_host_psutil(monkeypatch)
    from friday.autonomous import controller as controller_module

    monkeypatch.setattr(controller_module.psutil, "process_iter", lambda *_a, **_k: [])

    async def statuses(force_refresh=False):
        return [SimpleNamespace(status="ONLINE")]

    monkeypatch.setattr(controller_module.fleet_client, "get_all_statuses", statuses)
    result = await controller_module.AutonomousController().execute_self_repair()
    check = next(c for c in result["metadata"]["checks"] if c["name"] == "memory")
    assert check["status"] == "DEGRADED"
    assert "97.7%" in check["evidence"]
    assert "service limit" in check["evidence"]
