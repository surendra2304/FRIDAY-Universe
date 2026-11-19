"""TASK-VOI-002: proactive morning brief.

Every morning (once, inside the owner's awake window — Surendra wakes at
09:00), FRIDAY composes a brief from REAL data and pushes it as a proactive
notification so it is spoken/surfaced on the owner's first interaction:

* the daily focus goal (DailyRhythmManager, existing);
* live fleet status (FleetStatusTool — the same truth as /api/agents/status);
* the portfolio snapshot (StratexPortfolioTool — Binance demo, read-only);
* overnight mail triage (agentic inbox — unread counts by category plus the
  most urgent subject; TASK-FRD-027);
* today's first meeting (calendar tool, when a feed is configured;
  TASK-FRD-027);
* overnight events (pending proactive notifications — system alerts etc.).

TASK-FRD-027 is the OpenJarvis-parity delta (IG intake round 2, reel
Df12EVmO3EL): a spoken morning brief that sums up overnight email and names
the first meeting. The same reel's sleep line and missed-texts line are NOT
composed — FRIDAY has no health-data feed, and the phone lane is paired by
the owner — so they are absent rather than invented.

Truthfulness rules (unchanged from the tools it composes from):
- every line comes from a real probe/record — nothing invented;
- a failing probe contributes an honest "could not check" line, never a
  fabricated "all good";
- the brief is composed at most once per morning, and a failure to compose
  never blocks or crashes the caller.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, time as dtime
from typing import Any

from friday.core.owner_time import OWNER_TZ, now_owner_tz, owner_today

logger = logging.getLogger(__name__)

#: Morning window: fire once between 09:00 and 12:00 local time.
MORNING_WINDOW_START = dtime(9, 0)
MORNING_WINDOW_END = dtime(12, 0)

#: Composition lock: never compose twice concurrently.
_COMPOSE_LOCK = threading.Lock()

#: In-memory record of the last composed morning (YYYY-MM-DD). A process
#: restart may re-compose once — acceptable for a brief; the date is also
#: carried in the notification metadata for downstream dedupe.
_last_morning_date: str | None = None


def _today() -> str:
    # Owner decision (2026-11-10 IST, "It should be IST"): the brief belongs
    # to the owner's morning — the IST date, not the server's UTC date.
    return owner_today()


def _in_morning_window(now: datetime | None = None) -> bool:
    # The window is the owner's morning: 09:00–12:00 IST (the Oracle host
    # runs UTC, where that window would land at 14:30–17:30 IST — wrong day
    # part for the owner).
    if now is None:
        now = now_owner_tz()
    elif now.tzinfo is not None:
        now = now.astimezone(OWNER_TZ)
    return MORNING_WINDOW_START <= now.time() <= MORNING_WINDOW_END


def _fleet_line() -> str:
    from friday.tools.builtin.fleet_status import FleetStatusTool

    result = FleetStatusTool().execute(detail="summary")
    if result.is_error:
        return "Fleet status: I could not probe the agents just now, so I won't guess."
    first = result.content.split("Attention:")[0].strip().rstrip(".")
    return first


def _portfolio_line() -> str:
    from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool

    result = StratexPortfolioTool().execute(question="morning portfolio snapshot")
    if result.is_error:
        return "Portfolio: I could not reach Stratex just now, so no numbers today yet."
    lines = [ln for ln in result.content.splitlines() if ln.strip().startswith("-")]
    picked = []
    for ln in lines:
        if any(k in ln for k in ("Balance", "Cash", "Open positions", "Active strategies")):
            picked.append(ln.strip())
        if len(picked) >= 3:
            break
    if not picked:
        return "Portfolio: no snapshot was returned."
    return "Portfolio: " + "; ".join(x.lstrip("- ") for x in picked)


#: Spoken-friendly labels for the agentic-inbox categories, in the order a
#: morning brief should name them (most owner-relevant first).
_INBOX_CATEGORY_LABELS: list[tuple[str, str]] = [
    ("security", "security"),
    ("action_required", "needing action"),
    ("finance", "finance"),
    ("meeting", "meetings"),
    ("personal", "personal"),
    ("newsletter", "newsletters"),
    ("other", "other"),
]


def _inbox_line(triage: Any | None = None) -> str:
    """Overnight mail triage (TASK-FRD-027; OpenJarvis parity).

    Uses the agentic inbox's own deterministic triage — unread counts by
    category plus the single highest-priority subject. Read-only: no
    drafts are created and nothing is sent. An unconfigured mailbox omits
    the section (an optional source, not a failure); a configured mailbox
    that cannot be read contributes the brief's usual honest line.
    """
    if triage is None:
        from friday.proactive.agentic_inbox import triage_inbox

        triage = triage_inbox
    report = triage(limit=20, only_unread=True)
    status = str(getattr(report, "status", "") or "")
    if status.startswith("not_configured"):
        return ""
    if status != "ok":
        return (
            "Mail: I could not read your inbox just now "
            f"({status[:120]}), so I won't guess."
        )
    items = list(getattr(report, "items", []) or [])
    if not items:
        return "Mail: no unread mail this morning."
    counts = report.counts()
    parts = [
        f"{counts[key]} {label}"
        for key, label in _INBOX_CATEGORY_LABELS
        if counts.get(key)
    ]
    line = f"Mail: {len(items)} unread"
    if parts:
        line += " — " + ", ".join(parts)
    subject = str(
        getattr(getattr(items[0], "message", None), "subject", "") or ""
    ).strip()
    if subject:
        line += f"; most urgent: {subject[:80]}"
    return line + "."


def _calendar_line(tool: Any | None = None) -> str:
    """Today's first meeting (TASK-FRD-027; OpenJarvis parity).

    Uses the existing calendar tool (FRIDAY_CALENDAR_ICS_URL). No feed
    configured omits the section; a feed that fails to load contributes
    the honest line; a configured empty day says so.
    """
    if tool is None:
        from friday.tools.builtin.calendar import GetTodaysEventsTool

        tool = GetTodaysEventsTool()
    result = tool.execute()
    if getattr(result, "is_error", False):
        return "Calendar: I could not read today's calendar just now, so I won't guess."
    content = str(getattr(result, "content", "") or "")
    if content.startswith("No calendar feed configured"):
        return ""
    if "no meetings scheduled for today" in content:
        return "Calendar: nothing scheduled today."
    for raw in content.splitlines():
        entry = raw.strip()
        if entry.startswith("1. "):
            return f"First meeting: {entry[3:]}."
    return ""


def _goal_line() -> str:
    from friday.autonomous.daily_rhythm import daily_rhythm

    return daily_rhythm.get_morning_briefing()


def _overnight_lines(notifications: Any) -> list[str]:
    """Pending notifications are the overnight events; pop nothing here."""
    try:
        pending = notifications.fetch_pending_notifications(mark_delivered=False)
        return [p.message for p in (pending or [])[:3]]
    except Exception as exc:
        logger.debug(f"overnight events fetch failed: {exc}")
        return []


def compose_morning_brief(notifications: Any | None = None) -> str | None:
    """Compose the morning brief from real data. None outside the window
    or when already composed today.

    Never raises: a failed component contributes an honest line instead.
    """
    global _last_morning_date
    if not _in_morning_window():
        return None
    with _COMPOSE_LOCK:
        today = _today()
        if _last_morning_date == today:
            return None
        try:
            sections: list[str] = []

            try:
                sections.append(_goal_line())
            except Exception as exc:
                sections.append(
                    f"Daily goal: I could not read today's goal just now ({type(exc).__name__})."
                )

            try:
                sections.append(_fleet_line())
            except Exception as exc:
                sections.append(
                    f"Fleet status: probe failed ({type(exc).__name__}), so I won't guess."
                )

            try:
                sections.append(_portfolio_line())
            except Exception as exc:
                sections.append(
                    f"Portfolio: Stratex unreachable ({type(exc).__name__}), so no numbers yet."
                )

            try:
                inbox = _inbox_line()
                if inbox:
                    sections.append(inbox)
            except Exception as exc:
                sections.append(
                    f"Mail: probe failed ({type(exc).__name__}), so I won't guess."
                )

            try:
                calendar = _calendar_line()
                if calendar:
                    sections.append(calendar)
            except Exception as exc:
                sections.append(
                    f"Calendar: probe failed ({type(exc).__name__}), so I won't guess."
                )

            if notifications is not None:
                overnight = _overnight_lines(notifications)
                if overnight:
                    sections.append("Overnight: " + " | ".join(overnight))

            # A11: active long-term goals join the brief — a goal stated
            # Monday is still reported Friday ("still on it, Boss").
            try:
                from friday.memory.memora_client import memora_client as _memora
                from friday.proactive.goals import morning_brief_goal_line

                goal_line = morning_brief_goal_line(_memora)
                if goal_line:
                    sections.append(goal_line)
            except Exception as exc:
                logger.debug(f"goal line skipped in morning brief: {exc}")

            _last_morning_date = today
            return " | ".join(sections)
        except Exception as exc:
            logger.warning(f"morning brief composition failed: {exc}")
            return None


def maybe_deliver_morning_brief(notifications: Any | None = None) -> str | None:
    """Compose (once per morning) and push the brief as a proactive notification.

    The greeting fast path already pops pending notifications and (in voice
    mode) speaks them — so pushing here makes the brief proactive: the owner
    hears it on his first "hello friday" of the morning without asking.
    """
    brief = compose_morning_brief(notifications)
    if not brief:
        return None
    try:
        notifications.post_notification(
            brief,
            category="morning_brief",
            severity="info",
            metadata={"date": _today(), "source": "TASK-VOI-002"},
        )
    except Exception as exc:
        logger.debug(f"morning brief notification push skipped: {exc}")
    return brief


def reset_for_tests() -> None:
    """Test-only: forget the once-per-day marker."""
    global _last_morning_date
    _last_morning_date = None
