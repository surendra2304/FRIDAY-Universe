"""Regression tests for the FRIDAY memory guard (TASK-FRD-041).

The 2026-11-23 08:03 IST OOM kill was a *cgroup* kill (FRIDAY.service
MemoryMax=200M on Server 1), not a system-RAM kill — the kernel's own record
reads ``memory: usage 204800kB, limit 204800kB``. The guard therefore watches
the service's own cgroup: warn at 75%, escalate at 90% with a direct Telegram
send (the old ram_critical warning sat in the in-memory queue and died with
the process ~4 minutes before the kill), recover below 60%.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from friday.agent.agent import FridayAgent
from friday.llm.base import BaseLLMProvider
from friday.core.types import Message, Role
from friday.memory.in_memory import InMemoryConversationMemory
from friday.observability.notifications import NotificationManager
from friday.observability.proactive_engine import (
    MEMORY_CRITICAL_PERCENT,
    MEMORY_RECOVERED_PERCENT,
    MEMORY_WARN_PERCENT,
    ProactiveEngine,
    SystemSnapshot,
    capture_snapshot,
    read_cgroup_memory,
)
import friday.observability.proactive_engine as engine_module


class DummyLLM(BaseLLMProvider):
    def __init__(self, model="dummy-model"):
        super().__init__(model=model)

    @property
    def provider_name(self) -> str:
        return "dummy"

    def generate(self, messages, tools=None):
        return Message(role=Role.ASSISTANT, content="I'm here to help.")


def _snap(cgroup_pct=None, used_mb=None, limit_mb=None, swap_pct=None):
    """A SystemSnapshot with only the memory-guard fields set."""
    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=10.0,
        ram_percent=40.0,
        ram_used_gb=0.4,
        ram_total_gb=0.93,
        battery_percent=None,
        battery_plugged=None,
        disk_percent=20.0,
        network_up_kbps=1.0,
        network_down_kbps=1.0,
        cgroup_mem_percent=cgroup_pct,
        cgroup_mem_used_mb=used_mb,
        cgroup_mem_limit_mb=limit_mb,
        cgroup_swap_percent=swap_pct,
    )


def _write_cgroup_v2(base: Path, *, limit=209715200, used=157286400,
                     swap_limit=201326592, swap_used=100663296):
    (base / "memory.max").write_text(str(limit))
    (base / "memory.current").write_text(str(used))
    (base / "memory.swap.max").write_text(str(swap_limit))
    (base / "memory.swap.current").write_text(str(swap_used))


# -- cgroup reader ----------------------------------------------------------


def test_read_cgroup_memory_v2(tmp_path):
    _write_cgroup_v2(tmp_path)
    import friday.observability.proactive_engine as mod

    old = mod.CGROUP_BASE
    mod.CGROUP_BASE = str(tmp_path)
    try:
        result = read_cgroup_memory()
    finally:
        mod.CGROUP_BASE = old
    assert result is not None
    assert result.limit_bytes == 209715200
    assert result.used_bytes == 157286400
    assert result.percent == 75.0
    assert result.swap_limit_bytes == 201326592
    assert result.swap_used_bytes == 100663296
    assert result.swap_percent == 50.0


def test_read_cgroup_memory_unlimited(tmp_path):
    (tmp_path / "memory.max").write_text("max")
    (tmp_path / "memory.current").write_text("12345678")
    import friday.observability.proactive_engine as mod

    old = mod.CGROUP_BASE
    mod.CGROUP_BASE = str(tmp_path)
    try:
        result = read_cgroup_memory()
    finally:
        mod.CGROUP_BASE = old
    assert result is not None
    assert result.limit_bytes is None
    assert result.used_bytes == 12345678
    assert result.percent is None


def test_read_cgroup_memory_missing(tmp_path):
    import friday.observability.proactive_engine as mod

    old = mod.CGROUP_BASE
    mod.CGROUP_BASE = str(tmp_path)
    try:
        assert read_cgroup_memory() is None
    finally:
        mod.CGROUP_BASE = old


def test_read_cgroup_memory_v1_fallback(tmp_path):
    mem_dir = tmp_path / "memory"
    mem_dir.mkdir()
    # Real cgroup v1 names carry the "memory." prefix inside the
    # memory/ controller directory.
    (mem_dir / "memory.limit_in_bytes").write_text("209715200")
    (mem_dir / "memory.usage_in_bytes").write_text("188743680")
    (mem_dir / "memory.memsw.limit_in_bytes").write_text("201326592")
    (mem_dir / "memory.memsw.usage_in_bytes").write_text("201326592")
    import friday.observability.proactive_engine as mod

    old = mod.CGROUP_BASE
    mod.CGROUP_BASE = str(tmp_path)
    try:
        result = read_cgroup_memory()
    finally:
        mod.CGROUP_BASE = old
    assert result is not None
    assert result.percent == 90.0
    assert result.swap_percent == 100.0


# -- own-cgroup resolution (TASK-FRD-043) -----------------------------------
#
# The FRD-041 reader looked only under CGROUP_BASE (``/sys/fs/cgroup``),
# i.e. the hierarchy root. On the live host the root carries no memory.*
# files, so read_cgroup_memory() returned None and the guard could never
# fire — while the service cgroup itself hit its 200 MB cap and the kernel
# OOM-killed FRIDAY on 2026-11-27 00:56 UTC with no warning. The reader
# must resolve the process's OWN cgroup from /proc/self/cgroup first.


def test_own_cgroup_relpath_v2(tmp_path):
    proc = tmp_path / "cgroup"
    proc.write_text("0::/system.slice/FRIDAY.service\n")
    assert engine_module._own_cgroup_relpath(str(proc)) == "/system.slice/FRIDAY.service"


def test_own_cgroup_relpath_v1_memory_controller(tmp_path):
    proc = tmp_path / "cgroup"
    proc.write_text(
        "12:devices:/system.slice/FRIDAY.service\n"
        "8:memory:/system.slice/FRIDAY.service\n"
    )
    assert engine_module._own_cgroup_relpath(str(proc)) == "/system.slice/FRIDAY.service"


def test_own_cgroup_relpath_missing(tmp_path):
    assert engine_module._own_cgroup_relpath(str(tmp_path / "nope")) is None


def _write_cgroup_v2_at(base: Path, *, limit=209715200, used=157286400,
                        swap_limit=201326592, swap_used=100663296):
    base.mkdir(parents=True, exist_ok=True)
    _write_cgroup_v2(base, limit=limit, used=used,
                     swap_limit=swap_limit, swap_used=swap_used)


def test_read_cgroup_memory_own_cgroup(tmp_path, monkeypatch):
    service = tmp_path / "system.slice" / "FRIDAY.service"
    _write_cgroup_v2_at(service)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    monkeypatch.setattr(
        engine_module, "_own_cgroup_relpath",
        lambda path="/proc/self/cgroup": "/system.slice/FRIDAY.service",
    )
    result = read_cgroup_memory()
    assert result is not None
    assert result.limit_bytes == 209715200
    assert result.used_bytes == 157286400
    assert result.percent == 75.0
    assert result.swap_percent == 50.0


def test_read_cgroup_memory_own_cgroup_beats_root_decoy(tmp_path, monkeypatch):
    # Root carries whole-system numbers; the service cgroup must win.
    _write_cgroup_v2(tmp_path, limit=1073741824, used=107374182,
                     swap_limit=1073741824, swap_used=0)
    service = tmp_path / "system.slice" / "FRIDAY.service"
    _write_cgroup_v2_at(service)
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    monkeypatch.setattr(
        engine_module, "_own_cgroup_relpath",
        lambda path="/proc/self/cgroup": "/system.slice/FRIDAY.service",
    )
    result = read_cgroup_memory()
    assert result is not None
    assert result.percent == 75.0
    assert result.limit_bytes == 209715200


def test_read_cgroup_memory_missing_root_but_present_in_service(tmp_path, monkeypatch):
    # The exact production shape: no memory.* files at the hierarchy root,
    # files present in the service cgroup. The old reader returned None here.
    service = tmp_path / "system.slice" / "FRIDAY.service"
    _write_cgroup_v2_at(service, used=188743680)  # 90% of 200 MB
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    monkeypatch.setattr(
        engine_module, "_own_cgroup_relpath",
        lambda path="/proc/self/cgroup": "/system.slice/FRIDAY.service",
    )
    result = read_cgroup_memory()
    assert result is not None
    assert result.percent == 90.0


# -- thresholds -------------------------------------------------------------


def test_snapshot_thresholds():
    assert _snap(74.9).memory_pressure_warning() is False
    assert _snap(75.0).memory_pressure_warning() is True
    assert _snap(75.0).memory_pressure_critical() is False
    assert _snap(89.9).memory_pressure_critical() is False
    assert _snap(90.0).memory_pressure_critical() is True
    assert _snap(None).memory_pressure_warning() is False
    assert _snap(None).memory_pressure_critical() is False
    assert MEMORY_WARN_PERCENT == 75.0
    assert MEMORY_CRITICAL_PERCENT == 90.0
    assert MEMORY_RECOVERED_PERCENT == 60.0


# -- engine evaluation ------------------------------------------------------


def _engine():
    sent: list[str] = []
    notifications = NotificationManager()
    engine = ProactiveEngine(
        notifications=notifications,
        telegram_sender=lambda text: sent.append(text) or True,
    )
    return engine, notifications, sent


def _pending(notifications):
    return notifications.fetch_pending_notifications(mark_delivered=False)


def _wait_for(sent, count, timeout=2.0):
    deadline = time.monotonic() + timeout
    while len(sent) < count and time.monotonic() < deadline:
        time.sleep(0.05)
    return list(sent)


def test_evaluate_posts_warning_without_telegram():
    engine, notifications, sent = _engine()
    engine._evaluate(_snap(80.0, used_mb=160.0, limit_mb=200.0), None)
    pending = _pending(notifications)
    assert [n.category for n in pending] == ["memory_pressure"]
    assert pending[0].severity == "warning"
    assert "80.0%" in pending[0].message
    assert "200.0 MB" in pending[0].message
    assert _wait_for(sent, 1, timeout=0.3) == []


def test_evaluate_posts_critical_and_telegrams():
    engine, notifications, sent = _engine()
    engine._evaluate(_snap(95.0, used_mb=190.0, limit_mb=200.0), None)
    pending = _pending(notifications)
    assert [n.category for n in pending] == ["memory_critical"]
    assert pending[0].severity == "critical"
    assert "95.0%" in pending[0].message
    delivered = _wait_for(sent, 1)
    assert len(delivered) == 1
    assert "95.0%" in delivered[0]
    assert "200.0 MB" in delivered[0]


def test_evaluate_cooldown_dedupes_critical():
    engine, notifications, sent = _engine()
    current = _snap(95.0, used_mb=190.0, limit_mb=200.0)
    engine._evaluate(current, None)
    engine._evaluate(current, current)
    assert len(_pending(notifications)) == 1
    assert len(_wait_for(sent, 1)) == 1


def test_evaluate_recovery_after_critical():
    engine, notifications, sent = _engine()
    previous = _snap(95.0, used_mb=190.0, limit_mb=200.0)
    engine._evaluate(_snap(50.0, used_mb=100.0, limit_mb=200.0), previous)
    pending = _pending(notifications)
    assert [n.category for n in pending] == ["memory_recovered"]
    assert pending[0].severity == "info"
    assert _wait_for(sent, 1, timeout=0.3) == []


def test_evaluate_no_cgroup_no_memory_alert():
    engine, notifications, sent = _engine()
    engine._evaluate(_snap(None), None)
    assert _pending(notifications) == []
    assert sent == []


def test_capture_snapshot_reads_cgroup(tmp_path, monkeypatch):
    _write_cgroup_v2(tmp_path, used=104857600)  # 100 MB of 200 MB = 50%
    monkeypatch.setattr(engine_module, "CGROUP_BASE", str(tmp_path))
    snapshot = capture_snapshot()
    assert snapshot.cgroup_mem_percent == 50.0
    assert snapshot.cgroup_mem_used_mb == 100.0
    assert snapshot.cgroup_mem_limit_mb == 200.0
    assert snapshot.cgroup_swap_percent == 50.0


def test_diagnostics_exposes_cgroup_fields():
    agent = FridayAgent(llm_provider=DummyLLM(), memory=InMemoryConversationMemory())
    try:
        agent.proactive._last_snapshot = _snap(
            82.5, used_mb=165.0, limit_mb=200.0, swap_pct=99.0
        )
        diagnostics = agent.get_system_diagnostics()
        assert diagnostics["cgroup_mem_percent"] == 82.5
        assert diagnostics["cgroup_mem_used_mb"] == 165.0
        assert diagnostics["cgroup_mem_limit_mb"] == 200.0
        assert diagnostics["cgroup_swap_percent"] == 99.0
    finally:
        agent.close()
