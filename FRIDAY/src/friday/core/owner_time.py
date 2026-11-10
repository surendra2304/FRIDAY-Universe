"""Owner-facing time utilities — IST (Asia/Kolkata) is the project clock.

Owner decision (2026-11-10 IST, "It should be IST"): every time or date
FRIDAY speaks, prints, or schedules for the owner is computed in the
owner's timezone — IST, UTC+5:30 — never the host clock (the Oracle
servers run UTC). Machine-readable records keep UTC ISO-8601 timestamps;
anything the owner reads is IST.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:  # zoneinfo needs a system tz database (present on Oracle Linux)
    from zoneinfo import ZoneInfo

    OWNER_TZ = ZoneInfo("Asia/Kolkata")
except Exception:  # pragma: no cover - exotic hosts without tzdata
    # IST has no daylight saving, so a fixed offset is exactly equivalent.
    OWNER_TZ = timezone(timedelta(hours=5, minutes=30), "IST")

#: Short label for speech and chat ("IST").
OWNER_TZ_LABEL = "IST"


def now_owner_tz() -> datetime:
    """Current moment in the owner's timezone (IST), timezone-aware."""
    return datetime.now(tz=timezone.utc).astimezone(OWNER_TZ)


def owner_today() -> str:
    """Today's date (YYYY-MM-DD) in IST — stable across the UTC+5:30 boundary."""
    return now_owner_tz().strftime("%Y-%m-%d")


def owner_now_str(fmt: str = "%I:%M %p on %A, %d %B %Y") -> str:
    """Format the current IST moment for speech or chat."""
    return now_owner_tz().strftime(fmt)
