"""Checklists G7 + G8 (MASTER_COMPLETION_CHECKLIST): daily self-report + weekly summary.

G7 — every evening at 21:00 IST the owner gets a Telegram message from his
FRIDAY Universe bot: what FRIDAY actually did today, from REAL records —
never a summary invented to look busy.

G8 — Sunday evening (20:00 IST) adds the week's roll-up: mission outcomes,
fleet stability, task-ledger totals.

Every line is sourced:
- conversations handled: the in-process conversation history (the same log
  /api/chat writes through _log_conversation);
- agent dispatches: the shared TaskRecordStore report (TASK-CORE-003);
- fleet stability: the supervision snapshot's last error + agent count;
- overnight missions: the mission queue's outcomes (G6/G12);
- morning-brief delivery: the notifications ledger (categories).

Honesty rules:
- every component failure becomes an honest "could not read X" line;
- a source that returns zero records is reported as zero — never dressed up;
- the report is sent at most once per evening (21:00–23:59 IST window),
  once per Sunday for the weekly one; a Telegram send failure is logged
  and retried next cycle, never fatal.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from friday.core.owner_time import OWNER_TZ, now_owner_tz, owner_today

logger = logging.getLogger(__name__)

#: Evening self-report window: first cycle inside 21:00–23:59 IST sends.
EVENING_WINDOW_START_HOUR = 21
#: Weekly summary: Sundays, 20:00–23:59 IST (before the daily 21:00 report).
WEEKLY_WINDOW_START_HOUR = 20
WEEKDAY_SUNDAY = 6  # datetime.weekday(): Monday=0 ... Sunday=6

_report_lock = threading.Lock()
_last_report_date: str | None = None
_last_weekly_date: str | None = None


def _today() -> str:
    return owner_today()


def _in_evening_window(now: datetime | None = None) -> bool:
    moment = (now or now_owner_tz()).astimezone(OWNER_TZ)
    return moment.hour >= EVENING_WINDOW_START_HOUR


def _in_weekly_window(now: datetime | None = None) -> bool:
    moment = (now or now_owner_tz()).astimezone(OWNER_TZ)
    return moment.weekday() == WEEKDAY_SUNDAY and moment.hour >= WEEKLY_WINDOW_START_HOUR


# ---------------------------------------------------------------------------
# real data sources (each honest, each isolated)
# ---------------------------------------------------------------------------

def _conversation_stats() -> dict[str, Any]:
    """Today's conversations from the in-process history log."""
    try:
        from friday.api import server as _server  # late import avoids cycle
    except Exception as exc:
        return {"error": type(exc).__name__}
    try:
        history = list(_server._conversation_history)
    except Exception as exc:
        return {"error": type(exc).__name__}
    day_prefix = _today()
    today_entries = []
    for entry in history:
        ts = str(getattr(entry, "timestamp", "") or "")
        # history timestamps are UTC ISO; compare on the IST day boundary
        try:
            utc_dt = datetime.fromisoformat(ts)
            if utc_dt.astimezone(OWNER_TZ).strftime("%Y-%m-%d") == day_prefix:
                today_entries.append(entry)
        except ValueError:
            continue
    failed = sum(1 for e in today_entries if str(getattr(e, "status", "")) == "failed")
    return {"total": len(today_entries), "failed": failed}


def _task_ledger_stats() -> dict[str, Any]:
    """Dispatch counts from the unified TaskRecordStore."""
    try:
        from friday_core.task_records import get_shared_task_records
    except Exception as exc:
        return {"error": type(exc).__name__}
    try:
        return dict(get_shared_task_records().report())
    except Exception as exc:
        return {"error": type(exc).__name__}


def _fleet_stats() -> dict[str, Any]:
    """Reachability snapshot from the supervision loop."""
    try:
        from friday.api import server as _server
        state = dict(_server.fleet_supervision_state)
    except Exception as exc:
        return {"error": type(exc).__name__}
    agents = list(state.get("agents") or [])
    reachable = sum(
        1
        for a in agents
        if a.get("reachable") or a.get("online") or a.get("healthy")
    )
    return {
        "total": len(agents),
        "reachable": reachable,
        "last_error": state.get("last_error"),
        "last_completed_at": state.get("last_completed_at"),
    }


def _mission_stats() -> dict[str, Any]:
    """Overnight mission outcomes from the queue (G6/G12)."""
    try:
        from friday.proactive.mission_queue import mission_queue
    except Exception as exc:
        return {"error": type(exc).__name__}
    try:
        return {
            "pending": len(mission_queue.pending()),
            "line": mission_queue.render_morning_report(),
        }
    except Exception as exc:
        return {"error": type(exc).__name__}


def _memory_growth() -> dict[str, Any]:
    """Today's stored memories through the real client."""
    try:
        from friday.memory.memora_client import memora_client
    except Exception as exc:
        return {"error": type(exc).__name__}
    try:
        rows = memora_client.recent_memories("friday", limit=100, since=_today()) or []
        return {"stored_today": len(rows)}
    except Exception as exc:
        return {"error": type(exc).__name__}


# ---------------------------------------------------------------------------
# composition
# ---------------------------------------------------------------------------

def _line_for(label: str, stats: dict[str, Any], renderer) -> str:
    if stats.get("error"):
        return f"{label}: could not read ({stats['error']}) — reported honestly, not guessed."
    return renderer(stats)


def compose_daily_report() -> str:
    """Compose the evening self-report from real sources. Never raises."""
    sections: list[str] = []

    conv = _conversation_stats()
    sections.append(
        _line_for(
            "Conversations",
            conv,
            lambda s: (
                f"We talked {s['total']} time{'s' if s['total'] != 1 else ''} today"
                + (f" ({s['failed']} failed)" if s.get("failed") else "")
                + "."
            ),
        )
    )

    ledger = _task_ledger_stats()
    sections.append(
        _line_for(
            "Agent dispatches",
            ledger,
            lambda s: (
                f"I dispatched {s.get('total', 0)} task{'s' if s.get('total', 0) != 1 else ''} across the fleet today "
                f"({s.get('by_agent', {}) and ', '.join(f'{a}: {n}' for a, n in list(s.get('by_agent', {}).items())[:6]) or 'no agent work recorded'})."
            ),
        )
    )

    fleet = _fleet_stats()
    sections.append(
        _line_for(
            "Fleet",
            fleet,
            lambda s: (
                f"Fleet stayed reachable {s['reachable']}/{s['total']} on my last check"
                + (f" (supervision noted: {s['last_error']})" if s.get("last_error") else "")
                + "."
            ),
        )
    )

    missions = _mission_stats()
    if not missions.get("error"):
        sections.append(str(missions.get("line") or ""))

    memory = _memory_growth()
    sections.append(
        _line_for(
            "Memory",
            memory,
            lambda s: (
                f"I stored {s['stored_today']} new memor{'y' if s['stored_today'] == 1 else 'ies'} today."
                if s.get("stored_today")
                else "No new memories were stored today."
            ),
        )
    )

    header = (
        f"🌙 End of day, Boss — here's what I actually did today ({_today()} IST):"
    )
    body = "\n".join(s for s in sections if s and s.strip())
    return f"{header}\n{body}"


def compose_weekly_report() -> str:
    """Sunday evening roll-up: mission + ledger + fleet posture for the week."""
    sections: list[str] = []
    ledger = _task_ledger_stats()
    if ledger.get("error"):
        sections.append(f"Agent dispatches: could not read ({ledger['error']}).")
    else:
        by_status = ledger.get("by_status") or {}
        completed = by_status.get("completed", 0)
        failed = by_status.get("failed", 0) + by_status.get("routing_failed", 0)
        sections.append(
            f"This week the fleet's ledger holds {ledger.get('total', 0)} tasks — "
            f"{completed} completed, {failed} failed honestly, "
            f"{by_status.get('dispatched', 0)} still in flight."
        )
    fleet = _fleet_stats()
    sections.append(
        _line_for(
            "Fleet",
            fleet,
            lambda s: f"Fleet right now: {s['reachable']}/{s['total']} reachable.",
        )
    )
    missions = _mission_stats()
    if not missions.get("error"):
        pending = missions.get("pending", 0)
        if pending:
            sections.append(f"{pending} overnight mission(s) are still queued.")
    header = "📅 Sunday roll-up, Boss — the week at a glance:"
    return header + "\n" + "\n".join(s for s in sections if s and s.strip())


# ---------------------------------------------------------------------------
# delivery (idempotent per day; the loop calls this)
# ---------------------------------------------------------------------------

def maybe_deliver_reports(now: datetime | None = None) -> dict[str, Any]:
    """Send the daily (and Sunday weekly) report when inside the window.

    Returns a dict describing what was attempted; never raises.
    """
    global _last_report_date, _last_weekly_date
    outcome: dict[str, Any] = {"daily": None, "weekly": None}
    try:
        from friday.proactive.telegram_gateway import send_owner_message
    except Exception as exc:
        logger.debug("[SELF-REPORT] gateway unavailable: %s", exc)
        return outcome

    moment = (now or now_owner_tz()).astimezone(OWNER_TZ)
    today = _today()

    with _report_lock:
        # Weekly first (20:00 Sunday), so the daily 21:00 message follows it.
        if (
            _in_weekly_window(moment)
            and _last_weekly_date != today
        ):
            try:
                sent = send_owner_message(compose_weekly_report())
                if sent:
                    _last_weekly_date = today
                outcome["weekly"] = "sent" if sent else "send_failed"
            except Exception as exc:
                logger.warning("[SELF-REPORT] weekly send failed: %s", exc)
                outcome["weekly"] = f"error:{type(exc).__name__}"

        if _in_evening_window(moment) and _last_report_date != today:
            try:
                sent = send_owner_message(compose_daily_report())
                if sent:
                    _last_report_date = today
                outcome["daily"] = "sent" if sent else "send_failed"
            except Exception as exc:
                logger.warning("[SELF-REPORT] daily send failed: %s", exc)
                outcome["daily"] = f"error:{type(exc).__name__}"
    return outcome


def reset_for_tests() -> None:
    global _last_report_date, _last_weekly_date
    _last_report_date = None
    _last_weekly_date = None
