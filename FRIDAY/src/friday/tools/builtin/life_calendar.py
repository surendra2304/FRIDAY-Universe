"""Life-in-weeks dot-grid calendar (TASK-IG-FRD-009).

Pattern source: IG corpus item ``DTjp4aaE_bT`` — a life rendered as a
grid of week-dots: one row per year, one dot per week, lived weeks
filled and remaining weeks empty. It is a planning/memento-mori view;
this tool is the computation behind it (the website renders the grid).

Pure and stateless: the date of birth arrives as an argument and is
never stored. Conventions are declared, not hidden: 52 weeks per year,
lifespan default 90 years. A life past the assumed lifespan clamps at
100% — remaining weeks never go negative.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

WEEKS_PER_YEAR = 52
DEFAULT_LIFESPAN_YEARS = 90


def compute_life_calendar(
    dob: date,
    lifespan_years: int = DEFAULT_LIFESPAN_YEARS,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute the life-in-weeks grid data for ``dob``.

    Returns total/lived/remaining weeks, percent lived, the current
    week index, and ``grid``: one string per year of life, 52 chars,
    ``#`` = lived week, ``o`` = current week, ``.`` = remaining week.
    """
    today = today or date.today()
    if dob > today:
        raise ValueError("Date of birth is in the future.")
    if not (1 <= lifespan_years <= 150):
        raise ValueError("lifespan_years must be between 1 and 150.")

    total_weeks = lifespan_years * WEEKS_PER_YEAR
    days_lived = (today - dob).days
    weeks_lived = min(days_lived // 7, total_weeks)
    past_lifespan = days_lived // 7 >= total_weeks
    weeks_remaining = total_weeks - weeks_lived
    pct_lived = round(100.0 * weeks_lived / total_weeks, 2) if total_weeks else 0.0

    grid = []
    for year in range(lifespan_years):
        row_start = year * WEEKS_PER_YEAR
        chars = []
        for w in range(WEEKS_PER_YEAR):
            idx = row_start + w
            if idx < weeks_lived:
                chars.append("#")
            elif idx == weeks_lived and not past_lifespan:
                chars.append("o")
            else:
                chars.append(".")
        grid.append("".join(chars))

    return {
        "dob": dob.isoformat(),
        "today": today.isoformat(),
        "lifespan_years": lifespan_years,
        "weeks_per_year": WEEKS_PER_YEAR,
        "total_weeks": total_weeks,
        "weeks_lived": weeks_lived,
        "weeks_remaining": weeks_remaining,
        "pct_lived": pct_lived,
        "current_week_index": None if past_lifespan else weeks_lived,
        "current_year_of_life": None if past_lifespan else weeks_lived // WEEKS_PER_YEAR + 1,
        "past_assumed_lifespan": past_lifespan,
        "grid": grid,
    }


class LifeCalendarTool(BaseTool):
    """Compute the life-in-weeks grid for a date of birth."""

    name = "life_calendar"
    description = (
        "Compute the 'life in weeks' dot-grid calendar for a date of "
        "birth: total weeks in an assumed lifespan (default 90 years), "
        "weeks lived and remaining, percent lived, and the full grid "
        "data (one row per year) for display. Stateless — the date of "
        "birth is used for this computation only and never stored."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "dob": {"type": "string", "description": "Date of birth, YYYY-MM-DD."},
            "lifespan_years": {
                "type": "integer",
                "description": "Assumed lifespan in years (default 90).",
            },
        },
        "required": ["dob"],
    }

    def execute(self, dob: str = "", lifespan_years: int = DEFAULT_LIFESPAN_YEARS, **kwargs: Any) -> ToolResult:
        try:
            parsed = date.fromisoformat((dob or "").strip())
        except ValueError:
            return ToolResult(
                name=self.name,
                content=f"Could not parse dob {dob!r}; expected YYYY-MM-DD.",
                is_error=True,
            )
        try:
            data = compute_life_calendar(parsed, lifespan_years=int(lifespan_years))
        except (ValueError, TypeError) as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        summary = (
            f"Life in weeks (dob {data['dob']}, lifespan {data['lifespan_years']}y): "
            f"{data['weeks_lived']:,} of {data['total_weeks']:,} weeks lived "
            f"({data['pct_lived']}%), {data['weeks_remaining']:,} remaining."
        )
        if data["past_assumed_lifespan"]:
            summary += " The assumed lifespan has been fully lived — grid is complete."
        else:
            summary += (
                f" Currently in year {data['current_year_of_life']} of life, "
                f"week {data['current_week_index'] + 1} overall."
            )
        return ToolResult(
            name=self.name,
            content=summary,
            metadata=data,
        )


__all__ = ["compute_life_calendar", "LifeCalendarTool", "WEEKS_PER_YEAR", "DEFAULT_LIFESPAN_YEARS"]
