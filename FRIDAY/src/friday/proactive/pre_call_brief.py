"""TASK-FRD-047: Nod-style one-page pre-call brief from Gmail + Calendar.

Before each calendar call, FRIDAY reads Gmail + Calendar + the client's
latest news and writes a one-page brief, unprompted — the Nod pattern from
the owner's intake (CLASSIFICATION-2026-11-24 section 1, item 7). The brief
is delivered as a proactive notification (the morning-brief pattern) so the
owner hears/sees it on the greeting just before the call.

Sections (one page = bounded length, capped chars/lines):
* the call — title, time, location, attendees (from the .ics feed);
* recent Gmail threads with the attendees (IMAP TEXT search on the
  attendee name; the tool's own query path);
* the client's latest news — Google News RSS headlines filtered by
  attendee/company keywords (``get_news`` is category-only, so keyword
  filtering over the returned headlines is the query path);
* an honest "could not check" line per failing source, never a guess.

Truthfulness rules (same as the morning brief):
- every line comes from a real probe/record — nothing invented;
- a failing probe contributes an honest "could not check" line, never a
  fabricated "all good";
- the brief is composed at most once per call (dedupe by event title +
  start) and only inside a 30-minute lead window;
- composition is read-only: the brief itself never sends, pays, or
  deletes. Any follow-up action goes through FRIDAY's existing
  confirmation flow — the acceptance line is preserved by construction;
- composition failure never raises to the caller and never breaks a
  greeting.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timedelta
from typing import Any, Callable

from friday.core.owner_time import OWNER_TZ, now_owner_tz

logger = logging.getLogger(__name__)

#: Lead window: a call counts as "upcoming" when it starts within this
#: many minutes. 30 minutes is the proposal from checkpoint 1 — Muse may
#: rule a different window; it is one constant to change.
LEAD_WINDOW_MINUTES = 30

#: One page: hard cap on the composed brief.
MAX_BRIEF_CHARS = 1800
MAX_MAIL_SUBJECTS = 3
MAX_NEWS_ITEMS = 3

#: News is fetched from these categories and keyword-filtered (get_news is
#: category-only; there is no free-text query path).
NEWS_CATEGORIES = ("business", "general")

#: Words too generic to use as news keywords.
_NEWS_STOPWORDS = {
    "call", "meeting", "sync", "weekly", "daily", "standup", "catch",
    "chat", "intro", "review", "update", "check", "with", "team",
}

#: Composition lock: never compose twice concurrently.
_COMPOSE_LOCK = threading.Lock()

#: In-memory record of delivered calls ("YYYY-MM-DD|title|start-iso").
#: A process restart may re-deliver once — acceptable for a brief; the
#: event key is also carried in the notification metadata for downstream
#: dedupe.
_delivered_keys: set[str] = set()


def _now() -> datetime:
    return now_owner_tz()


def _event_key(event: dict[str, Any]) -> str:
    start = event.get("start_dt")
    start_iso = start.isoformat() if isinstance(start, datetime) else str(event.get("start", ""))
    return f"{start.date().isoformat() if isinstance(start, datetime) else ''}|{event.get('title', '')}|{start_iso}"


def _prune_delivered(today_iso: str) -> None:
    for key in list(_delivered_keys):
        if not key.startswith(today_iso):
            _delivered_keys.discard(key)


def _mail_configured() -> bool:
    """True only when Gmail credentials are present.

    Checked first so an unconfigured mailbox never reaches the Gmail tool:
    the tool's unconfigured path opens the Gmail web UI (and its IMAP
    failure path opens a browser tab too) — neither belongs in a
    background greeting hook.
    """
    try:
        from friday.core.config import get_settings

        settings = get_settings()
        address = getattr(settings, "email_address", None) or os.getenv("FRIDAY_EMAIL_ADDRESS")
        password = getattr(settings, "email_app_password", None) or os.getenv("FRIDAY_EMAIL_APP_PASSWORD")
        return bool(address and password)
    except Exception:
        return bool(os.getenv("FRIDAY_EMAIL_ADDRESS") and os.getenv("FRIDAY_EMAIL_APP_PASSWORD"))


def _fetch_ics_text() -> str | None:
    """Fetch the raw .ics feed text, mirroring GetTodaysEventsTool.

    Supports a plain local path, a file:// URL (used by the repo-side
    tests), and an https URL. None when no feed is configured or the
    fetch fails.
    """
    from friday.core.config import get_settings

    settings = get_settings()
    url = getattr(settings, "calendar_ics_url", None) or os.getenv("FRIDAY_CALENDAR_ICS_URL")
    if not url:
        return None
    target = url.strip()
    path = target[7:] if target.startswith("file://") else target
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        import httpx

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(target)
            resp.raise_for_status()
            return resp.text
    except Exception as exc:
        logger.debug(f"pre-call brief calendar fetch failed: {exc}")
        return None


def _fetch_upcoming_events(now: datetime) -> list[dict[str, Any]]:
    """Events with a start time, today + tomorrow, earliest first.

    Tomorrow is included so a call just after midnight is still caught
    by a late-evening greeting. Empty on any failure — a failed feed
    means no brief, not a guessed one.
    """
    from friday.tools.builtin.calendar import _parse_ics_content

    ics_text = _fetch_ics_text()
    if not ics_text:
        return []
    events: list[dict[str, Any]] = []
    try:
        for day_offset in (0, 1):
            day = (now.date() + timedelta(days=day_offset))
            for ev in _parse_ics_content(ics_text, day):
                if isinstance(ev.get("start_dt"), datetime):
                    events.append(ev)
    except Exception as exc:
        logger.debug(f"pre-call brief calendar parse failed: {exc}")
        return []
    events.sort(key=lambda e: e["start_dt"])
    return events


def _next_call(
    events: list[dict[str, Any]],
    now: datetime,
    lead_minutes: int = LEAD_WINDOW_MINUTES,
) -> dict[str, Any] | None:
    """Earliest event starting inside [now, now + lead]. All-day events
    (no start_dt) never count as a call."""
    window_end = now + timedelta(minutes=lead_minutes)
    for ev in sorted(events, key=lambda e: e.get("start_dt") or now):
        start = ev.get("start_dt")
        if not isinstance(start, datetime):
            continue
        start_owner = start.astimezone(OWNER_TZ)
        if now <= start_owner <= window_end:
            return ev
    return None


def _call_line(event: dict[str, Any], now: datetime) -> str:
    title = str(event.get("title", "Untitled meeting")).strip()
    time_range = str(event.get("time_range", "")).strip()
    start = event.get("start_dt")
    day_word = ""
    if isinstance(start, datetime) and start.astimezone(OWNER_TZ).date() != now.date():
        day_word = "Tomorrow, "
    line = f"Call: {day_word}{title}"
    if time_range and time_range != "All Day":
        line += f" at {time_range}"
    location = str(event.get("location", "") or "").strip()
    if location:
        line += f" ({location})"
    attendees = [str(a) for a in (event.get("attendees") or []) if str(a).strip()]
    if attendees:
        line += " with " + ", ".join(attendees[:4])
    return line + "."


def _mail_lines(
    event: dict[str, Any],
    gmail_tool: Any | None = None,
) -> str:
    """Recent Gmail threads with the attendees (TASK-FRD-047).

    Attendee-scoped: one TEXT search per attendee (max two), subjects
    only — the brief cites real thread subjects, never a summary of
    mail it did not read. An unconfigured mailbox omits the section;
    a configured mailbox that cannot be read contributes the honest line.
    """
    attendees = [str(a) for a in (event.get("attendees") or []) if str(a).strip()]
    if not attendees:
        return "Mail: no attendees named on the invite, so no mail search."
    if gmail_tool is None and not _mail_configured():
        return ""
    if gmail_tool is None:
        from friday.tools.builtin.gmail_tools import ReadGmailInboxTool

        gmail_tool = ReadGmailInboxTool()
    subjects: list[str] = []
    try:
        for attendee in attendees[:2]:
            result = gmail_tool.execute(query=attendee, max_emails=MAX_MAIL_SUBJECTS)
            if getattr(result, "is_error", False):
                return "Mail: I could not read your inbox just now, so I won't guess."
            content = str(getattr(result, "content", "") or "")
            if "No matching emails found" in content:
                continue
            for match in re.finditer(r"\*\*Subject:\*\*\s*(.+)", content):
                subject = match.group(1).strip()
                if subject and subject not in subjects:
                    subjects.append(subject)
    except Exception as exc:
        return f"Mail: probe failed ({type(exc).__name__}), so I won't guess."
    if not subjects:
        return f"Mail: no recent threads with {', '.join(attendees[:2])}."
    shown = "; ".join(s[:80] for s in subjects[:MAX_MAIL_SUBJECTS])
    return f"Mail: recent threads with {', '.join(attendees[:2])}: {shown}."


def _news_keywords(event: dict[str, Any]) -> list[str]:
    """Attendee names + significant title words, for headline filtering."""
    keywords: list[str] = []
    for attendee in (event.get("attendees") or []):
        name = str(attendee).strip()
        if name:
            keywords.append(name)
            for part in name.split():
                if len(part) >= 4:
                    keywords.append(part)
    for word in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", str(event.get("title", ""))):
        lowered = word.lower()
        if lowered not in _NEWS_STOPWORDS and lowered not in {k.lower() for k in keywords}:
            keywords.append(word)
    return keywords


def _news_lines(
    event: dict[str, Any],
    news_tool: Any | None = None,
) -> str:
    """The client's latest news: headlines matching the call (TASK-FRD-047).

    get_news is category-only, so headlines from business + general are
    keyword-filtered against the attendees/title. No match says so
    honestly — unrelated headlines are never passed off as the client's
    news. A failed fetch contributes the honest line.
    """
    keywords = _news_keywords(event)
    if not keywords:
        return ""
    if news_tool is None:
        from friday.tools.builtin.news import NewsTool

        news_tool = NewsTool()
    headlines: list[str] = []
    try:
        for category in NEWS_CATEGORIES:
            result = news_tool.execute(category=category, limit=5)
            if getattr(result, "is_error", False):
                return "News: I could not fetch the news just now, so I won't guess."
            content = str(getattr(result, "content", "") or "")
            for match in re.finditer(r"^\d+\.\s+(.+?)(?:\s+\[.+?\])?\s*$", content, re.M):
                headline = match.group(1).strip()
                if not headline or headline in headlines:
                    continue
                lowered = headline.lower()
                if any(k.lower() in lowered for k in keywords):
                    headlines.append(headline)
            if len(headlines) >= MAX_NEWS_ITEMS:
                break
    except Exception as exc:
        return f"News: probe failed ({type(exc).__name__}), so I won't guess."
    if not headlines:
        return f"News: nothing matching {', '.join(keywords[:3])} in today's headlines."
    shown = "; ".join(h[:90] for h in headlines[:MAX_NEWS_ITEMS])
    return f"News: {shown}."


def compose_pre_call_brief(
    event: dict[str, Any] | None,
    *,
    gmail_tool: Any | None = None,
    news_tool: Any | None = None,
    now: datetime | None = None,
) -> str | None:
    """Compose the one-page brief for ``event``. None when no event.

    Never raises: a failed component contributes an honest line instead.
    """
    if not event:
        return None
    if now is None:
        now = _now()
    elif now.tzinfo is not None:
        now = now.astimezone(OWNER_TZ)
    try:
        sections: list[str] = []
        try:
            sections.append(_call_line(event, now))
        except Exception as exc:
            sections.append(f"Call: I could not read the invite just now ({type(exc).__name__}).")

        try:
            mail = _mail_lines(event, gmail_tool=gmail_tool)
            if mail:
                sections.append(mail)
        except Exception as exc:
            sections.append(f"Mail: probe failed ({type(exc).__name__}), so I won't guess.")

        try:
            news = _news_lines(event, news_tool=news_tool)
            if news:
                sections.append(news)
        except Exception as exc:
            sections.append(f"News: probe failed ({type(exc).__name__}), so I won't guess.")

        brief = " | ".join(sections)
        if len(brief) > MAX_BRIEF_CHARS:
            brief = brief[: MAX_BRIEF_CHARS - 20].rstrip() + "… (trimmed to one page)"
        return brief
    except Exception as exc:
        logger.warning(f"pre-call brief composition failed: {exc}")
        return None


def maybe_deliver_pre_call_brief(
    notifications: Any | None = None,
    *,
    now: datetime | None = None,
    calendar_fetcher: Callable[[datetime], list[dict[str, Any]]] | None = None,
    gmail_tool: Any | None = None,
    news_tool: Any | None = None,
    lead_minutes: int = LEAD_WINDOW_MINUTES,
) -> str | None:
    """Compose (once per call, inside the lead window) and push the brief.

    Mirrors ``maybe_deliver_morning_brief``: the greeting fast path calls
    this, and the notification it pushes is spoken/surfaced on the
    owner's next greeting. Returns the brief when one was composed, else
    None. Never raises.
    """
    if now is None:
        now = _now()
    elif now.tzinfo is not None:
        now = now.astimezone(OWNER_TZ)
    with _COMPOSE_LOCK:
        try:
            fetcher = calendar_fetcher or _fetch_upcoming_events
            events = fetcher(now)
        except Exception as exc:
            logger.debug(f"pre-call brief calendar fetch failed: {exc}")
            return None
        event = _next_call(events or [], now, lead_minutes=lead_minutes)
        if event is None:
            return None
        _prune_delivered(now.date().isoformat())
        key = _event_key(event)
        if key in _delivered_keys:
            return None
        brief = compose_pre_call_brief(
            event, gmail_tool=gmail_tool, news_tool=news_tool, now=now
        )
        if not brief:
            return None
        _delivered_keys.add(key)
        if notifications is not None:
            try:
                start = event.get("start_dt")
                notifications.post_notification(
                    brief,
                    category="pre_call_brief",
                    severity="info",
                    metadata={
                        "event": str(event.get("title", "")),
                        "start": start.isoformat() if isinstance(start, datetime) else "",
                        "source": "TASK-FRD-047",
                    },
                )
            except Exception as exc:
                logger.debug(f"pre-call brief notification push skipped: {exc}")
        return brief


def reset_for_tests() -> None:
    """Test-only: forget the delivered-call markers."""
    global _delivered_keys
    _delivered_keys = set()
