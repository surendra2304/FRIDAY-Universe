"""Checklists G6 + G12 (MASTER_COMPLETION_CHECKLIST): the overnight mission queue.

The owner queues work in the evening ("add to tonight's missions: research X"),
FRIDAY executes the queue while he sleeps (03:00–05:00 IST window), and the
morning brief reports the outcomes. The same queue is the owner's TODO intake
(G12): anything he says in chat that looks like a deferred task can be parked
here with one line, then executed overnight through the real chat brain.

Design:
- File-backed (``FRIDAY/.data/missions/queue.json``) so a restart never
  loses the owner's queued work; writes are atomic (tmp + os.replace) and
  locked.
- A mission is a plain command string plus metadata (id, created, status,
  attempts, last_result). Statuses: pending → running → completed | failed
  | skipped. Nothing is ever marked completed without a real execution.
- Execution goes through the SAME brain as the dashboard chat
  (``execute_command``) — no mini-brain, no shortcuts: a mission that the
  brain refuses is reported as refused, not failed-and-retried forever.
- Bounded retries: attempts < MAX_ATTEMPTS (2). A mission that keeps
  failing is marked failed and reported honestly in the morning.
- The executor runs inside the server lifespan (gate check every 10 min,
  run window 03:00–05:00 IST, once per night); a chat fast-path runs it on
  demand ("run my missions now").
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable

from friday.core.owner_time import OWNER_TZ, now_owner_tz, owner_today

logger = logging.getLogger(__name__)

#: Execution window: while the owner sleeps, after nightly consolidation
#: (02:00–05:00) starts, missions run 03:00–05:00 IST.
RUN_WINDOW_START = 3
RUN_WINDOW_END = 5
#: A mission that fails twice is reported failed — never retried forever.
MAX_ATTEMPTS = 2
#: Cap one night's execution time so the loop can never wedge the service.
MAX_MISSIONS_PER_NIGHT = 10
MAX_MISSION_SECONDS = 240

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_SKIPPED}


def _default_queue_path() -> str:
    """The queue FILE lives with the service's runtime data.

    Resolution order: the process working directory first (the systemd unit
    sets WorkingDirectory=/opt/friday_universe/FRIDAY, so ``.data`` lands
    beside the other runtime stores), then the package-tree fallback for
    non-standard cwd (tests, manual runs).
    """
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "missions", "queue.json"))
    here = os.path.dirname(__file__)  # .../friday/proactive
    return os.path.abspath(os.path.join(here, "..", "..", ".data", "missions", "queue.json"))


class MissionQueue:
    """File-backed overnight mission queue."""

    def __init__(self, queue_path: str | None = None) -> None:
        self._path = queue_path or _default_queue_path()
        self._lock = threading.RLock()
        self._cache: list[dict[str, Any]] | None = None
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    # ------------------------------------------------------------------
    # persistence (atomic, honest)
    # ------------------------------------------------------------------
    def _load(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = list(data.get("missions") or [])
        except FileNotFoundError:
            self._cache = []
        except Exception as exc:
            logger.warning("[MISSIONS] queue file unreadable (%s) — starting empty, file not touched", exc)
            self._cache = []
        return self._cache

    def _save(self, missions: list[dict[str, Any]]) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"missions": missions, "saved_at": time.time()}, f, indent=2)
        os.replace(tmp, self._path)

    # ------------------------------------------------------------------
    # queue API
    # ------------------------------------------------------------------
    def add(self, command: str, *, source: str = "chat") -> dict[str, Any]:
        command = (command or "").strip()
        if not command:
            raise ValueError("empty mission")
        mission = {
            "id": f"m_{uuid.uuid4().hex[:12]}",
            "command": command,
            "source": source,
            "status": STATUS_PENDING,
            "attempts": 0,
            "created_at": time.time(),
            "created_ist": now_owner_tz().isoformat(),
            "last_result": "",
            "last_error": "",
        }
        with self._lock:
            missions = self._load()
            missions.append(mission)
            self._save(missions)
        logger.info("[MISSIONS] queued %s (%s): %s", mission["id"], source, command[:80])
        return dict(mission)

    def pending(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(m) for m in self._load() if m.get("status") == STATUS_PENDING]

    def all_missions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(m) for m in self._load()]

    def missions_since(self, since_ist_date: str) -> list[dict[str, Any]]:
        """Missions created on/after an IST date (for the morning report)."""
        with self._lock:
            out = []
            for m in self._load():
                created = str(m.get("created_ist") or "")
                # ISO prefix compare: same date or newer.
                if created[:10] >= since_ist_date:
                    out.append(dict(m))
            return out

    def _mutate(self, mission_id: str, **fields: Any) -> dict[str, Any] | None:
        with self._lock:
            missions = self._load()
            for m in missions:
                if m.get("id") == mission_id:
                    m.update(fields)
                    self._save(missions)
                    return dict(m)
        return None

    def remove(self, mission_id: str) -> bool:
        with self._lock:
            missions = self._load()
            kept = [m for m in missions if m.get("id") != mission_id]
            if len(kept) == len(missions):
                return False
            self._save(kept)
            return True

    def clear_finished(self) -> int:
        with self._lock:
            missions = self._load()
            kept = [m for m in missions if m.get("status") not in TERMINAL_STATUSES]
            removed = len(missions) - len(kept)
            if removed:
                self._save(kept)
            return removed

    # ------------------------------------------------------------------
    # execution
    # ------------------------------------------------------------------
    async def execute_pending_async(
        self,
        brain: Callable[[str], Any],
        *,
        limit: int = MAX_MISSIONS_PER_NIGHT,
        max_seconds: float = MAX_MISSION_SECONDS,
    ) -> dict[str, Any]:
        """Execute pending missions through an async brain (awaited, never
        deadlocked: call from the event loop that owns the brain).

        The brain receives the raw command string and returns the execute_command
        result dict. Never raises.
        """
        import asyncio

        report = {"executed": 0, "completed": 0, "failed": 0, "skipped": 0, "results": []}
        started = time.monotonic()
        with self._lock:
            candidates = [dict(m) for m in self._load() if m.get("status") == STATUS_PENDING]
        for mission in candidates[:limit]:
            if time.monotonic() - started > max_seconds:
                logger.warning(
                    "[MISSIONS] night budget reached (%ss) — remaining missions stay pending",
                    int(time.monotonic() - started),
                )
                break
            self._mutate(mission["id"], status=STATUS_RUNNING, attempts=mission["attempts"] + 1)
            try:
                result = brain(mission["command"])
                if asyncio.iscoroutine(result):
                    result = await result
                result = result or {}
                reply = str(result.get("reply") or "").strip()
                metadata = result.get("metadata") or {}
                refused = bool(metadata.get("refused") or metadata.get("security_blocked"))
                success = not refused and result.get("success") is not False
                status = STATUS_COMPLETED if success else STATUS_SKIPPED if refused else STATUS_FAILED
                self._mutate(
                    mission["id"],
                    status=status,
                    last_result=reply[:2000],
                    last_error="" if success else str(metadata.get("error") or "engine reported failure")[:500],
                )
                report["executed"] += 1
                report[status] += 1
                report["results"].append(
                    {"id": mission["id"], "command": mission["command"], "status": status, "reply": reply[:2000]}
                )
            except Exception as exc:
                attempts = mission["attempts"] + 1
                final = attempts >= MAX_ATTEMPTS
                self._mutate(
                    mission["id"],
                    status=STATUS_FAILED if final else STATUS_PENDING,
                    attempts=attempts,
                    last_error=f"{type(exc).__name__}: {exc}"[:500],
                )
                report["executed"] += 1
                if final:
                    report["failed"] += 1
                    report["results"].append(
                        {"id": mission["id"], "command": mission["command"], "status": STATUS_FAILED,
                         "reply": f"Engine error: {type(exc).__name__}"}
                    )
                else:
                    report["skipped"] += 1
        return report

    def execute_pending(
        self,
        brain: Callable[[str], Any],
        *,
        limit: int = MAX_MISSIONS_PER_NIGHT,
        max_seconds: float = MAX_MISSION_SECONDS,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Execute pending missions through a synchronous brain. Never raises.

        NOTE: when the brain bridges onto an event loop (e.g. the server's
        execute_command), this must be called from a NON-loop thread (the
        Telegram gateway thread) — calling it from the loop itself deadlocks.
        On-loop callers use :meth:`execute_pending_async`.
        """
        report = {"executed": 0, "completed": 0, "failed": 0, "skipped": 0, "results": []}
        started = time.monotonic()
        with self._lock:
            candidates = [
                dict(m)
                for m in self._load()
                if m.get("status") == STATUS_PENDING
            ]
        for mission in candidates[:limit]:
            if time.monotonic() - started > max_seconds:
                logger.warning(
                    "[MISSIONS] night budget reached (%ss) — %d mission(s) left pending for tomorrow",
                    int(time.monotonic() - started),
                    max(0, len(candidates) - report["executed"]),
                )
                break
            self._mutate(mission["id"], status=STATUS_RUNNING, attempts=mission["attempts"] + 1)
            try:
                result = brain(mission["command"])
                reply = str((result or {}).get("reply") or "").strip()
                metadata = (result or {}).get("metadata") or {}
                refused = bool(metadata.get("refused") or metadata.get("security_blocked"))
                success = not refused and (result or {}).get("success") is not False
                status = STATUS_COMPLETED if success else STATUS_SKIPPED if refused else STATUS_FAILED
                self._mutate(
                    mission["id"],
                    status=status,
                    last_result=reply[:2000],
                    last_error="" if success else str(metadata.get("error") or "engine reported failure")[:500],
                )
                report["executed"] += 1
                report[status] += 1
                report["results"].append(
                    {
                        "id": mission["id"],
                        "command": mission["command"],
                        "status": status,
                        "reply": reply[:2000],
                    }
                )
            except Exception as exc:
                attempts = mission["attempts"] + 1
                final = attempts >= MAX_ATTEMPTS
                self._mutate(
                    mission["id"],
                    status=STATUS_FAILED if final else STATUS_PENDING,
                    attempts=attempts,
                    last_error=f"{type(exc).__name__}: {exc}"[:500],
                )
                report["executed"] += 1
                if final:
                    report["failed"] += 1
                    report["results"].append(
                        {
                            "id": mission["id"],
                            "command": mission["command"],
                            "status": STATUS_FAILED,
                            "reply": f"Engine error: {type(exc).__name__}",
                        }
                    )
                else:
                    report["skipped"] += 1
        return report

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def render_status(self) -> str:
        """The /missions reply: queue state in the owner's tone."""
        missions = self.all_missions()
        if not missions:
            return (
                "The overnight mission queue is empty, Boss. Queue work with "
                "\"add to tonight's missions: <task>\" and I'll run it while you sleep."
            )
        lines = []
        counts = {"pending": 0, "completed": 0, "failed": 0, "running": 0, "skipped": 0}
        for m in missions[-10:]:
            st = str(m.get("status") or "pending")
            counts[st] = counts.get(st, 0) + 1
            icon = {
                STATUS_PENDING: "🕒",
                STATUS_RUNNING: "⚙️",
                STATUS_COMPLETED: "✅",
                STATUS_FAILED: "❌",
                STATUS_SKIPPED: "⛔",
            }.get(st, "•")
            when = str(m.get("created_ist") or "")[:16].replace("T", " ")
            lines.append(f"{icon} {m['command'][:100]} ({when} IST)")
        summary = ", ".join(f"{v} {k}" for k, v in counts.items() if v)
        return f"Overnight missions ({summary}):\n" + "\n".join(lines)

    def render_morning_report(self, day: str | None = None) -> str:
        """Yesterday-evening + overnight outcomes for the morning brief."""
        day = day or owner_today()
        missions = self.missions_since(day)
        run_states = [m for m in missions if m.get("status") in TERMINAL_STATUSES or m.get("status") == STATUS_RUNNING]
        if not missions:
            return "No missions were queued for last night."
        completed = [m for m in run_states if m.get("status") == STATUS_COMPLETED]
        failed = [m for m in run_states if m.get("status") == STATUS_FAILED]
        pending = [m for m in missions if m.get("status") == STATUS_PENDING]
        parts = [f"Overnight missions: {len(completed)} completed, {len(failed)} failed, {len(pending)} still pending."]
        for m in completed[:5]:
            parts.append(f"✅ {m['command'][:80]} → {(m.get('last_result') or 'done')[:120]}")
        for m in failed[:5]:
            parts.append(f"❌ {m['command'][:80]} → {m.get('last_error') or 'failed'}")
        return " ".join(parts)

    def reset_for_tests(self, queue_path: str | None = None) -> None:
        """Test-only: point at a fresh path and clear the cache."""
        self._path = queue_path or self._path
        self._cache = None


#: Process-wide singleton (the server and the gateway share one queue).
mission_queue = MissionQueue()


# ---------------------------------------------------------------------------
# chat intent detection (used by the server's dispatch chain)
# ---------------------------------------------------------------------------

_ADD_PATTERNS = (
    "add to tonight's missions",
    "add to tonights missions",
    "add to my missions",
    "add to tonight's mission",
    "queue for tonight",
    "queue for tonight:",
    "add a mission",
    "add mission",
    "new mission",
    "save for tonight",
    "for tonight's missions",
    "add to the mission queue",
    "add to my todo",
    "add to todo",
    "add to my to-do",
    "queue a task for tonight",
    "tonight's mission:",
    "tonight's missions:",
)

_LIST_PATTERNS = (
    "show my missions",
    "show tonight's missions",
    "what are my missions",
    "what's on my missions",
    "whats on my missions",
    "list my missions",
    "my missions",
    "mission status",
    "show my todo",
    "what's on my todo",
    "whats on my todo",
    "my todo list",
    "show the mission queue",
)

_RUN_PATTERNS = (
    "run my missions now",
    "run the missions now",
    "run tonight's missions now",
    "execute my missions",
    "run my missions",
    "clear finished missions",
)


def is_add_mission_intent(text: str) -> str | None:
    """Return the mission text when the message queues work for tonight.

    Matches on the lowercased form but slices from the ORIGINAL text so the
    queued mission keeps the owner's casing (same rule as the memory paths).
    """
    low = (text or "").lower()
    for pattern in _ADD_PATTERNS:
        idx = low.find(pattern)
        if idx < 0:
            continue
        # take the text after the pattern; colon or ' :' separated payload
        after = text[idx + len(pattern):].lstrip(" :,-")
        if not after.strip():
            continue
        return after.strip()
    # "tonight: research X" style — colon payload after a tonight marker
    for marker in ("tonight:", "for tonight:"):
        idx = low.find(marker)
        if idx >= 0:
            after = text[idx + len(marker):].strip()
            after_low = after.lower()
            if after and any(w in after_low for w in ("research", "run ", "check ", "write ", "scan ", "forecast", "draft ", "summarize", "analyze", "make ", "create ")):
                return after
    return None


def is_list_missions_intent(low: str) -> bool:
    return any(p in low for p in _LIST_PATTERNS)


def is_run_missions_intent(low: str) -> bool:
    return any(p in low for p in _RUN_PATTERNS)
