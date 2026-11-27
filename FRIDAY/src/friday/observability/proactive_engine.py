"""FRIDAY Proactive Engine: ambient awareness and unprompted announcements.

FRIDAY does not wait to be asked. She watches system diagnostics, memory pressure,
active tasks, and speaks up the moment something needs attention. This engine
continuously monitors system state and emits proactive announcements that FRIDAY
surfaces over voice and text without the user prompting.

Monitors:
  - System telemetry  : CPU, RAM, battery, disk, network
  - Active window     : what the user is currently doing
  - Anomaly detection : sudden spikes, low battery, hot CPU
  - Memory guard (TASK-FRD-041): the service's own cgroup limit — the
    kernel kills FRIDAY when the *cgroup* (200 MB on Server 1) fills,
    long before system RAM looks critical, so the guard watches
    /sys/fs/cgroup memory.max/memory.current and warns at 75%, escalates
    at 90% with a direct Telegram send (the 2026-11-23 08:03 IST kill
    proved a queued-only warning dies with the process).
"""

from __future__ import annotations

import os
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import psutil

from friday.core.logging import get_logger
from friday.observability.notifications import NotificationManager

logger = get_logger("observability.proactive")


#: Memory-guard thresholds (TASK-FRD-041), as a share of the service's own
#: cgroup memory cap. On Server 1 the cap is 200 MB (FRIDAY.service
#: MemoryMax=200M): warning at 150 MB used leaves ~50 MB of headroom, critical
#: at 180 MB leaves ~20 MB. The 2026-11-23 victim grew to ~164 MB RSS in
#: ~6 minutes, so these are minutes of warning, not hours — by design.
MEMORY_WARN_PERCENT = 75.0
MEMORY_CRITICAL_PERCENT = 90.0
MEMORY_RECOVERED_PERCENT = 60.0

#: Cgroup base path; tests monkeypatch this to a fabricated tree.
CGROUP_BASE = "/sys/fs/cgroup"


def _own_cgroup_relpath(path: str = "/proc/self/cgroup") -> str | None:
    """This process's cgroup path, e.g. ``/system.slice/FRIDAY.service``.

    Read from /proc/self/cgroup: the ``0::`` line is the cgroup v2 unified
    path; a ``memory`` entry is the cgroup v1 controller path. Returns None
    when the file cannot be read or has no usable entry.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return None
    for line in lines:
        parts = line.split(":")
        if len(parts) == 3 and parts[0] == "0" and parts[2]:
            return parts[2]
    for line in lines:
        parts = line.split(":")
        if len(parts) == 3 and "memory" in parts[1].split(",") and parts[2]:
            return parts[2]
    return None


def _cgroup_file_bases() -> list[str]:
    """Directories holding this process's cgroup files, best first.

    TASK-FRD-043: the original reader looked only under CGROUP_BASE
    (``/sys/fs/cgroup``), i.e. the hierarchy root. On the live host the
    root carries no memory.* files, so read_cgroup_memory() returned None
    and the guard could never fire — while the service cgroup itself hit
    its 200 MB cap and the kernel OOM-killed FRIDAY on 2026-11-27 00:56 UTC.
    The process's own cgroup (from /proc/self/cgroup) comes first; the
    bare root is kept last so dev machines and containers without a
    service cgroup behave exactly as before.
    """
    bases: list[str] = []
    own = _own_cgroup_relpath()
    if own:
        rel = own.lstrip("/")
        bases.append(os.path.join(CGROUP_BASE, rel))
        bases.append(os.path.join(CGROUP_BASE, "memory", rel))
    bases.append(CGROUP_BASE)
    bases.append(os.path.join(CGROUP_BASE, "memory"))
    return bases


def _read_cgroup_int(*relative_paths: str) -> int | None:
    """Read the first readable cgroup value file; None when absent/unlimited.

    Searches each candidate base directory (own cgroup first, hierarchy
    root last) for each relative name in order. A file containing ``max``
    means the resource is unlimited and is treated as no limit (None). Any
    read/parse failure returns None — the guard degrades to "no cgroup
    data" instead of raising.
    """
    for base in _cgroup_file_bases():
        for relative in relative_paths:
            try:
                with open(os.path.join(base, relative), encoding="utf-8") as handle:
                    raw = handle.read().strip()
            except (OSError, ValueError):
                continue
            if raw in ("", "max"):
                return None
            try:
                return int(raw)
            except ValueError:
                continue
    return None


@dataclass
class CgroupMemory:
    """The service's own memory-cgroup accounting (cgroup v2, v1 fallback)."""

    limit_bytes: int | None  # None when the cgroup has no memory cap
    used_bytes: int
    swap_limit_bytes: int | None
    swap_used_bytes: int | None

    @property
    def percent(self) -> float | None:
        if self.limit_bytes is None or self.limit_bytes <= 0:
            return None
        return round(self.used_bytes / self.limit_bytes * 100, 1)

    @property
    def swap_percent(self) -> float | None:
        if self.swap_limit_bytes is None or self.swap_limit_bytes <= 0:
            return None
        if self.swap_used_bytes is None:
            return None
        return round(self.swap_used_bytes / self.swap_limit_bytes * 100, 1)


def read_cgroup_memory() -> CgroupMemory | None:
    """Read this process's memory-cgroup accounting; None when unavailable.

    Reads the process's OWN cgroup (resolved from /proc/self/cgroup, e.g.
    ``/system.slice/FRIDAY.service`` under the hierarchy root), preferring
    cgroup v2 (memory.max / memory.current / memory.swap.*) with a v1
    fallback (memory/memory.limit_in_bytes / memory/memory.usage_in_bytes /
    memory/memory.memsw.*). Returns None when no cgroup files exist at all
    (dev machines, containers without limits) or the used value cannot be read.
    A present-but-unlimited cap yields limit_bytes=None with a real used_bytes.
    """
    used = _read_cgroup_int(
        "memory.current",
        "memory.usage_in_bytes",
        "memory/memory.usage_in_bytes",
    )
    if used is None:
        return None
    return CgroupMemory(
        limit_bytes=_read_cgroup_int(
            "memory.max",
            "memory.limit_in_bytes",
            "memory/memory.limit_in_bytes",
        ),
        used_bytes=used,
        swap_limit_bytes=_read_cgroup_int(
            "memory.swap.max",
            "memory.memsw.limit_in_bytes",
            "memory/memory.memsw.limit_in_bytes",
        ),
        swap_used_bytes=_read_cgroup_int(
            "memory.swap.current",
            "memory.memsw.usage_in_bytes",
            "memory/memory.memsw.usage_in_bytes",
        ),
    )


@dataclass
class SystemSnapshot:
    """A single point-in-time reading of system health."""

    timestamp: datetime
    cpu_percent: float | None
    ram_percent: float | None
    ram_used_gb: float | None
    ram_total_gb: float | None
    battery_percent: float | None
    battery_plugged: bool | None
    disk_percent: float | None
    network_up_kbps: float | None
    network_down_kbps: float | None
    active_window: str = ""
    top_processes: list[str] = field(default_factory=list)
    measurement_error: str | None = None
    # Memory guard (TASK-FRD-041): the service's own cgroup, not system RAM.
    # None when the process runs without a cgroup memory cap (dev/CI).
    cgroup_mem_percent: float | None = None
    cgroup_mem_used_mb: float | None = None
    cgroup_mem_limit_mb: float | None = None
    cgroup_swap_percent: float | None = None

    def cpu_hot(self) -> bool:
        return self.cpu_percent is not None and self.cpu_percent >= 85

    def ram_critical(self) -> bool:
        return self.ram_percent is not None and self.ram_percent >= 90

    def battery_low(self) -> bool:
        return self.battery_percent is not None and self.battery_percent <= 20 and not self.battery_plugged

    def disk_full(self) -> bool:
        return self.disk_percent is not None and self.disk_percent >= 90

    def memory_pressure_warning(self) -> bool:
        """Cgroup use at/above the warning threshold (TASK-FRD-041)."""
        return self.cgroup_mem_percent is not None and self.cgroup_mem_percent >= MEMORY_WARN_PERCENT

    def memory_pressure_critical(self) -> bool:
        """Cgroup use at/above the critical threshold (TASK-FRD-041)."""
        return self.cgroup_mem_percent is not None and self.cgroup_mem_percent >= MEMORY_CRITICAL_PERCENT


def capture_snapshot() -> SystemSnapshot:
    """Grab one system telemetry reading (safe, never raises)."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        battery = psutil.sensors_battery()
        net = psutil.net_io_counters()
        up_kbps = round(net.bytes_sent / 1024, 1)
        down_kbps = round(net.bytes_recv / 1024, 1)
        top: list[str] = []
        try:
            for p in psutil.process_iter(["name", "cpu_percent"]):
                info = p.info
                if info.get("name") and (info.get("cpu_percent") or 0) > 5:
                    top.append(str(info["name"]))
                if len(top) >= 5:
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
        # Memory guard (TASK-FRD-041): the cgroup cap is the real kill
        # threshold — system RAM can look fine while the cgroup is full.
        cgroup = read_cgroup_memory()
        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=round(cpu, 1),
            ram_percent=round(ram.percent, 1),
            ram_used_gb=round(ram.used / (1024 ** 3), 2),
            ram_total_gb=round(ram.total / (1024 ** 3), 2),
            battery_percent=round(battery.percent, 1) if battery else None,
            battery_plugged=battery.power_plugged if battery else None,
            disk_percent=round(disk.percent, 1),
            network_up_kbps=up_kbps,
            network_down_kbps=down_kbps,
            top_processes=top,
            cgroup_mem_percent=cgroup.percent if cgroup else None,
            cgroup_mem_used_mb=round(cgroup.used_bytes / (1024 ** 2), 1) if cgroup else None,
            cgroup_mem_limit_mb=round(cgroup.limit_bytes / (1024 ** 2), 1) if cgroup and cgroup.limit_bytes else None,
            cgroup_swap_percent=cgroup.swap_percent if cgroup else None,
        )
    except Exception as exc:
        logger.warning(f"System snapshot failed: {exc}")
        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc),
            cpu_percent=None, ram_percent=None, ram_used_gb=None, ram_total_gb=None,
            battery_percent=None, battery_plugged=None,
            disk_percent=None, network_up_kbps=None, network_down_kbps=None,
            measurement_error=str(exc),
        )


PROACTIVE_OPENERS = (
    "While you were not looking -",
    "Quick heads-up:",
    "Before you ask -",
    "Something you should know:",
    "If I may interject -",
    "Worth noting:",
    "Just keeping you in the loop:",
)


def _phrase(message: str) -> str:
    """Wrap a raw monitoring fact in FRIDAY proactive voice."""
    return f"{random.choice(PROACTIVE_OPENERS)} {message}"


class ProactiveEngine:
    """Continuously monitors system state and emits proactive announcements.

    Runs a background polling loop. Call start() once at agent init and
    stop() at shutdown. Announcements are posted to the NotificationManager
    so FRIDAY surfaces them on the next turn (or immediately over voice).
    """

    def __init__(
        self,
        notifications: NotificationManager,
        user_name: str = "Surendra",
        poll_interval_seconds: float = 30.0,
        telegram_sender: Callable[[str], bool] | None = None,
    ) -> None:
        self.notifications = notifications
        self.user_name = user_name
        self.poll_interval = poll_interval_seconds
        # Memory guard (TASK-FRD-041): direct Telegram sender for the critical
        # threshold. None means "use the real Telegram gateway lazily"; tests
        # pass a recorder. The sender must never raise — see _send_telegram.
        self._telegram_sender = telegram_sender
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_snapshot: SystemSnapshot | None = None
        self._last_announcement_at: dict[str, datetime] = {}
        self._announcement_cooldown = timedelta(minutes=5)
        self._custom_checks: list[Callable[[SystemSnapshot, SystemSnapshot | None], str | None]] = []

    def start(self) -> None:
        """Start the background monitoring loop."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="friday-proactive", daemon=True)
        self._thread.start()
        logger.info("ProactiveEngine started")

    def stop(self) -> None:
        """Stop the background monitoring loop."""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("ProactiveEngine stopped")

    def register_check(
        self, fn: Callable[[SystemSnapshot, SystemSnapshot | None], str | None]
    ) -> None:
        """Register a custom check function.

        The function receives (current, previous) snapshots and returns either
        an announcement string or None. Use this to add domain-specific monitoring.
        """
        self._custom_checks.append(fn)

    @property
    def last_snapshot(self) -> SystemSnapshot | None:
        return self._last_snapshot

    def _run(self) -> None:
        while self._running and not self._stop_event.is_set():
            try:
                snapshot = capture_snapshot()
                self._evaluate(snapshot, self._last_snapshot)
                self._last_snapshot = snapshot
            except Exception as exc:
                logger.error(f"ProactiveEngine poll error: {exc}")
            self._stop_event.wait(self.poll_interval)

    def _evaluate(self, current: SystemSnapshot, previous: SystemSnapshot | None) -> None:
        # Announcement-storm fix (2026-11-13, ZAI Agent 2, measured live):
        # the old dedupe keyed on message[:60] — but the CPU message embeds
        # the percentage ("hot at 99.8%" vs "99.6%"), so a pinned server
        # produced a "different" alert every 30s poll and the summary burst
        # with 17 near-identical lines on the owner's next question.
        # Dedupe is now per CATEGORY with state-change awareness: one live
        # alert per condition, re-announced only after the cooldown lapses.
        announcements: list[tuple[str, str, str, str | None]] = []  # (category, message, severity, direct-telegram text or None)
        if current.cpu_hot():
            announcements.append((
                "cpu_hot",
                f"CPU is running hot at {current.cpu_percent}%. "
                f"{'Top offender: ' + current.top_processes[0] if current.top_processes else 'Keeping an eye on it.'}",
                "warning",
                None,
            ))
        if current.ram_critical():
            announcements.append((
                "ram_critical",
                f"RAM usage is at {current.ram_percent}% ({current.ram_used_gb}/{current.ram_total_gb} GB). "
                "Might want to close a few things.",
                "warning",
                None,
            ))
        if current.battery_low():
            announcements.append((
                "battery_low",
                f"Battery is at {current.battery_percent}% and not charging. "
                "Plugging in would be wise.",
                "warning",
                None,
            ))
        if current.disk_full():
            announcements.append((
                "disk_full",
                f"Disk is {current.disk_percent}% full. Running low on space.",
                "warning",
                None,
            ))
        # Memory guard (TASK-FRD-041): the cgroup cap is what kills FRIDAY,
        # so warn on cgroup use, not system RAM. Critical also goes straight
        # to Telegram: on 2026-11-23 the ram_critical warning sat in the
        # in-memory queue and died with the process ~4 minutes later, before
        # any turn surfaced it. The direct send is gated by the same
        # per-category cooldown as the queue post, so it fires at most once
        # per 5 minutes while the condition holds.
        if current.memory_pressure_critical():
            announcements.append((
                "memory_critical",
                f"my memory use is at {current.cgroup_mem_percent}% of the "
                f"{current.cgroup_mem_limit_mb} MB service limit "
                f"({current.cgroup_mem_used_mb} MB used). If it keeps climbing "
                "the kernel will kill me without warning.",
                "critical",
                f"FRIDAY memory critical: {current.cgroup_mem_percent}% of the "
                f"{current.cgroup_mem_limit_mb} MB service limit "
                f"({current.cgroup_mem_used_mb} MB used). I may be killed soon.",
            ))
        elif current.memory_pressure_warning():
            announcements.append((
                "memory_pressure",
                f"my memory use is at {current.cgroup_mem_percent}% of the "
                f"{current.cgroup_mem_limit_mb} MB service limit "
                f"({current.cgroup_mem_used_mb} MB used).",
                "warning",
                None,
            ))
        if (
            previous
            and current.cpu_percent is not None
            and previous.cpu_percent is not None
            and current.cpu_percent < 30
            and previous.cpu_percent >= 85
        ):
            announcements.append(("cpu_cooled", "CPU has cooled down. Crisis averted.", "info", None))
        if (
            previous
            and (previous.memory_pressure_warning() or previous.memory_pressure_critical())
            and current.cgroup_mem_percent is not None
            and current.cgroup_mem_percent < MEMORY_RECOVERED_PERCENT
        ):
            announcements.append((
                "memory_recovered",
                "Memory pressure has eased back below "
                f"{MEMORY_RECOVERED_PERCENT:.0f}% of the service limit.",
                "info",
                None,
            ))
        for fn in self._custom_checks:
            try:
                result = fn(current, previous)
                if result:
                    announcements.append((f"custom:{fn.__name__}", result, "info", None))
            except Exception as exc:
                logger.warning(f"Custom proactive check failed: {exc}")
        for category, message, severity, telegram_text in announcements:
            if self._should_announce(category):
                self.notifications.post_notification(
                    message=_phrase(message),
                    category=category,
                    severity=severity,
                )
                if telegram_text is not None:
                    self._send_telegram(telegram_text)

    def _send_telegram(self, text: str) -> None:
        """Best-effort direct Telegram send in a daemon thread; never raises.

        The gateway is imported lazily so the engine stays importable without
        Telegram configured. An injected ``telegram_sender`` (tests, or a
        caller that already owns a gateway) is used instead when present.
        An unconfigured gateway stays silent.
        """
        def _deliver() -> None:
            try:
                if self._telegram_sender is not None:
                    self._telegram_sender(text)
                    return
                from friday.proactive.telegram_gateway import telegram_gateway

                if not telegram_gateway.is_configured():
                    return
                telegram_gateway.send_message(text)
            except Exception as exc:  # never break the monitoring loop
                logger.warning(f"Memory-guard Telegram send failed: {exc}")

        threading.Thread(
            target=_deliver, name="friday-memory-guard-telegram", daemon=True
        ).start()

    def _should_announce(self, category: str) -> bool:
        """Per-category cooldown so we do not repeat the same condition.

        The key is the CONDITION (cpu_hot, ram_critical, ...), never the
        message text — a reading that merely drifted from 99.8% to 99.7%
        is the same condition, not a new announcement.
        """
        now = datetime.now(timezone.utc)
        last = self._last_announcement_at.get(category)
        if last and (now - last) < self._announcement_cooldown:
            return False
        self._last_announcement_at[category] = now
        return True
