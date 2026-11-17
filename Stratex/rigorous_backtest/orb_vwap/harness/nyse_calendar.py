"""NYSE session calendar for the SRS TSLA panel (2023-01-01 -> 2026-10-31).

Self-contained (stdlib only). Encodes full-day closures and 13:00 ET early
closes for the declared panel window. The tables are validated by the
session counts they reproduce: PROVENANCE.md section 1 computed, from
weekdays minus NYSE holidays (incl. the 2025-01-09 national day of
mourning), 961 panel sessions and OOS folds W1..W5 = 128/122/128/123/86
(587 total). test_srs_data_tools.py asserts exactly those counts; if a
table entry is wrong, the counts break loudly instead of silently
mis-auditing the panel.

Bars per session: a full session has 26 regular-session 15-minute bars
(bar-start 09:30..15:45 ET); an early-close (13:00 ET) session has 10
(bar-start 09:30..12:45 ET).

Re-confirm against the official NYSE holiday calendar on run day —
free-tier terms and calendars are point-in-time facts.
"""
from __future__ import annotations

import datetime as dt

# Full-day closures inside the panel window (date -> reason).
NYSE_CLOSURES: dict[dt.date, str] = {
    # 2023
    dt.date(2023, 1, 2): "New Year's Day (observed, Mon)",
    dt.date(2023, 1, 16): "Martin Luther King Jr. Day",
    dt.date(2023, 2, 20): "Washington's Birthday",
    dt.date(2023, 4, 7): "Good Friday",
    dt.date(2023, 5, 29): "Memorial Day",
    dt.date(2023, 6, 19): "Juneteenth National Independence Day",
    dt.date(2023, 7, 4): "Independence Day",
    dt.date(2023, 9, 4): "Labor Day",
    dt.date(2023, 11, 23): "Thanksgiving Day",
    dt.date(2023, 12, 25): "Christmas Day",
    # 2024
    dt.date(2024, 1, 1): "New Year's Day",
    dt.date(2024, 1, 15): "Martin Luther King Jr. Day",
    dt.date(2024, 2, 19): "Washington's Birthday",
    dt.date(2024, 3, 29): "Good Friday",
    dt.date(2024, 5, 27): "Memorial Day",
    dt.date(2024, 6, 19): "Juneteenth National Independence Day",
    dt.date(2024, 7, 4): "Independence Day",
    dt.date(2024, 9, 2): "Labor Day",
    dt.date(2024, 11, 28): "Thanksgiving Day",
    dt.date(2024, 12, 25): "Christmas Day",
    # 2025
    dt.date(2025, 1, 1): "New Year's Day",
    dt.date(2025, 1, 9): "National Day of Mourning (President Carter)",
    dt.date(2025, 1, 20): "Martin Luther King Jr. Day",
    dt.date(2025, 2, 17): "Washington's Birthday",
    dt.date(2025, 4, 18): "Good Friday",
    dt.date(2025, 5, 26): "Memorial Day",
    dt.date(2025, 6, 19): "Juneteenth National Independence Day",
    dt.date(2025, 7, 4): "Independence Day",
    dt.date(2025, 9, 1): "Labor Day",
    dt.date(2025, 11, 27): "Thanksgiving Day",
    dt.date(2025, 12, 25): "Christmas Day",
    # 2026 (panel ends 2026-10-31; later 2026 closures are out of window)
    dt.date(2026, 1, 1): "New Year's Day",
    dt.date(2026, 1, 19): "Martin Luther King Jr. Day",
    dt.date(2026, 2, 16): "Washington's Birthday",
    dt.date(2026, 4, 3): "Good Friday",
    dt.date(2026, 5, 25): "Memorial Day",
    dt.date(2026, 6, 19): "Juneteenth National Independence Day",
    dt.date(2026, 7, 3): "Independence Day (observed, Fri; Jul 4 is Sat)",
    dt.date(2026, 9, 7): "Labor Day",
}

# 13:00 ET early closes inside the panel window.
NYSE_EARLY_CLOSES: set[dt.date] = {
    dt.date(2023, 7, 3),    # day before Independence Day
    dt.date(2023, 11, 24),  # day after Thanksgiving
    dt.date(2024, 7, 3),
    dt.date(2024, 11, 29),
    dt.date(2024, 12, 24),  # Christmas Eve
    dt.date(2025, 7, 3),
    dt.date(2025, 11, 28),
    dt.date(2025, 12, 24),
    dt.date(2026, 7, 2),    # day before the observed Independence Day holiday
}

FULL_SESSION_BARS = 26
EARLY_CLOSE_BARS = 10


def is_session(day: dt.date) -> bool:
    """True if NYSE held a regular session on `day`."""
    return day.weekday() < 5 and day not in NYSE_CLOSURES


def expected_bars(day: dt.date) -> int | None:
    """Expected 15m regular-session bars for `day`, or None if no session."""
    if not is_session(day):
        return None
    return EARLY_CLOSE_BARS if day in NYSE_EARLY_CLOSES else FULL_SESSION_BARS


def sessions_between(start: dt.date, end: dt.date) -> list[dt.date]:
    """All NYSE session dates in [start, end] inclusive."""
    out: list[dt.date] = []
    day = start
    while day <= end:
        if is_session(day):
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def expected_bar_starts(day: dt.date) -> list[dt.time]:
    """Expected 15m bar-start times (ET) for a session date."""
    n = expected_bars(day)
    if n is None:
        return []
    starts = []
    t = dt.datetime.combine(day, dt.time(9, 30))
    for _ in range(n):
        starts.append(t.time())
        t += dt.timedelta(minutes=15)
    return starts
