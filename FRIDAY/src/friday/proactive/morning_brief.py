"""TASK-VOI-002: proactive morning brief.

Every morning (once, inside the owner's awake window — Surendra wakes at
09:00), FRIDAY composes a brief from REAL data and pushes it as a proactive
notification so it is spoken/surfaced on the owner's first interaction:

* the daily focus goal (DailyRhythmManager, existing);
* live fleet status (FleetStatusTool — the same truth as /api/agents/status);
* the portfolio snapshot (StratexPortfolioTool — Binance demo, read-only);
* overnight events (pending proactive notifications — system alerts etc.).

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
    return datetime.now().strftime("%Y-%m-%d")


def _in_morning_window(now: datetime | None = None) -> bool:
    now = now or datetime.now()
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

            if notifications is not None:
                overnight = _overnight_lines(notifications)
                if overnight:
                    sections.append("Overnight: " + " | ".join(overnight))

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
