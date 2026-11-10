"""Built-in tool for retrieving the owner's current time and date (IST)."""

import time
from typing import Any

from friday.core.owner_time import OWNER_TZ_LABEL, now_owner_tz
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class TimeDateTool(BaseTool):
    """Tool to query the owner's local time, date, day of week, and epoch timestamp."""

    name = "get_time_date"
    description = "Retrieve the owner's current local time (IST), date, day of the week, and Unix epoch timestamp."
    safety_level = SafetyLevel.SAFE
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, **kwargs: Any) -> ToolResult:
        # Owner decision (2026-11-10 IST, "It should be IST"): the owner-facing
        # clock is IST even though the host runs UTC.
        now = now_owner_tz()
        local_time = now.strftime("%H:%M:%S")
        local_date = now.strftime("%Y-%m-%d")
        day_of_week = now.strftime("%A")
        epoch_ts = time.time()

        content = (
            f"Current Local Date ({OWNER_TZ_LABEL}): {local_date}\n"
            f"Current Local Time ({OWNER_TZ_LABEL}): {local_time}\n"
            f"Day of the Week: {day_of_week}\n"
            f"Unix Timestamp: {epoch_ts:.2f}"
        )

        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
        )
