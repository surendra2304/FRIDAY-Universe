"""Built-in tool for retrieving the current time and date.

TASK-REL-006A: the tool used to ignore its arguments entirely and always
answer with the owner's IST clock — so "what time is it in Tokyo?" (the
round-1 production prompt) could only ever be answered with the wrong
city's time, even when the model correctly asked for
``timezone="Asia/Tokyo"``. The tool now honours an optional IANA
``timezone``; the default stays the owner's IST clock (owner decision
2026-11-10), and an unrecognised zone falls back to IST *and says so*.
"""

import time
from datetime import datetime, timezone
from typing import Any

from friday.core.owner_time import OWNER_TZ, OWNER_TZ_LABEL, now_owner_tz
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class TimeDateTool(BaseTool):
    """Tool to query the current time/date, IST by default or any IANA zone."""

    name = "get_time_date"
    description = (
        "Retrieve the current local time, date, day of the week, and Unix "
        "epoch timestamp. Defaults to the owner's timezone (IST). Pass an "
        "IANA timezone name (e.g. 'Asia/Tokyo', 'America/New_York') when the "
        "user asks for the time somewhere else."
    )
    safety_level = SafetyLevel.SAFE
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Optional IANA timezone name, e.g. 'Asia/Tokyo'. Omit for the owner's IST clock.",
            },
        },
        "required": [],
    }

    def execute(self, **kwargs: Any) -> ToolResult:
        tz_name = str(kwargs.get("timezone") or kwargs.get("tz") or "").strip()
        tz = OWNER_TZ
        label = OWNER_TZ_LABEL
        fallback_note = ""
        if tz_name and tz_name != OWNER_TZ_LABEL:
            try:
                from zoneinfo import ZoneInfo

                tz = ZoneInfo(tz_name)
                label = tz_name
            except Exception:
                fallback_note = (
                    f" (Note: '{tz_name}' is not a timezone I recognise, "
                    "so this is the owner's IST clock instead.)"
                )
                tz = OWNER_TZ
                label = OWNER_TZ_LABEL
        now = datetime.now(tz=timezone.utc).astimezone(tz)
        if not tz_name:
            now = now_owner_tz()
        local_time = now.strftime("%H:%M:%S")
        local_date = now.strftime("%Y-%m-%d")
        day_of_week = now.strftime("%A")
        epoch_ts = time.time()

        content = (
            f"Current Date ({label}): {local_date}\n"
            f"Current Time ({label}): {local_time}\n"
            f"Day of the Week: {day_of_week}\n"
            f"Unix Timestamp: {epoch_ts:.2f}"
            f"{fallback_note}"
        )

        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
        )
