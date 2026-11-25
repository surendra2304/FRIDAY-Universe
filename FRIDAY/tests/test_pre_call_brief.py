"""TASK-FRD-047: Nod-style one-page pre-call brief from Gmail + Calendar.

Rules pinned here:
- a call counts only when it starts inside the 30-minute lead window;
- the brief names the call, cites real Gmail thread subjects for the
  attendees, and filters news headlines by attendee/title keywords;
- every failing source contributes an honest line, never a guess;
- the brief is delivered at most once per call;
- composition failure never raises to the caller;
- repo-side only: no credentials, no network — the calendar feed is a
  local .ics file and Gmail/news are fakes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.unit]

from friday.core.owner_time import OWNER_TZ, now_owner_tz
from friday.proactive import pre_call_brief as pcb


@pytest.fixture(autouse=True)
def _reset():
    pcb.reset_for_tests()
    yield
    pcb.reset_for_tests()


class _FakeNotifications:
    def __init__(self):
        self.posted = []

    def post_notification(self, message, category="x", severity="info", metadata=None, notification_id=None):
        self.posted.append({"message": message, "category": category, "metadata": metadata})
        return "id"


class _FakeToolResult:
    def __init__(self, content, is_error=False):
        self.content = content
        self.is_error = is_error


class _FakeGmailTool:
    """Canned inbox: subjects keyed by the query string."""

    def __init__(self, by_query=None, is_error=False):
        self.by_query = by_query or {}
        self.is_error = is_error
        self.queries = []

    def execute(self, query=None, max_emails=3, **kwargs):
        self.queries.append(query)
        if self.is_error:
            return _FakeToolResult("Could not connect via IMAP (boom).", is_error=True)
        subjects = self.by_query.get(query or "", [])
        if not subjects:
            return _FakeToolResult("No matching emails found in Gmail inbox.")
        body = "\n\n".join(
            f"📧 **Subject:** {s}\n   **From:** someone@example.com\n   **Date:** Mon, 25 Nov 2026"
            for s in subjects
        )
        return _FakeToolResult(f"Found {len(subjects)} email(s) in inbox:\n\n{body}")


class _FakeNewsTool:
    def __init__(self, headlines_by_category=None, is_error=False):
        self.headlines_by_category = headlines_by_category or {}
        self.is_error = is_error

    def execute(self, category="general", limit=5, **kwargs):
        if self.is_error:
            return _FakeToolResult("Could not retrieve news at this time: boom", is_error=True)
        headlines = self.headlines_by_category.get(category, [])
        lines = [f"Top {len(headlines)} {category.title()} News Headlines:"]
        for i, h in enumerate(headlines, 1):
            lines.append(f"{i}. {h} [Reuters]")
            lines.append("   URL: https://example.com/x")
        return _FakeToolResult("\n".join(lines))


def _event(title="Call with Priya Nair — Acme renewal", minutes_from_now=15,
           attendees=("Priya Nair",), now=None):
    now = now or now_owner_tz()
    start = now + timedelta(minutes=minutes_from_now)
    return {
        "title": title,
        "start": start.strftime("%I:%M %p"),
        "end": (start + timedelta(minutes=30)).strftime("%I:%M %p"),
        "time_range": f"{start.strftime('%I:%M %p')} - {(start + timedelta(minutes=30)).strftime('%I:%M %p')}",
        "location": "Zoom",
        "attendees": list(attendees),
        "start_dt": start,
        "end_dt": start + timedelta(minutes=30),
    }


def _gmail_with_subjects():
    return _FakeGmailTool(by_query={"Priya Nair": ["Q3 renewal terms", "Acme invoice — overdue"]})


def _news_with_headlines():
    return _FakeNewsTool(headlines_by_category={
        "business": ["Acme announces Q3 results", "Markets rally on rate hopes"],
        "general": ["Local festival draws crowds"],
    })


class TestNextCall:
    def test_picks_call_inside_the_lead_window(self):
        now = now_owner_tz()
        events = [
            _event("Far call", minutes_from_now=90, now=now),
            _event("Past call", minutes_from_now=-30, now=now),
            _event("Next call", minutes_from_now=15, now=now),
        ]
        found = pcb._next_call(events, now)
        assert found is not None
        assert found["title"] == "Next call"

    def test_ignores_all_day_events(self):
        now = now_owner_tz()
        event = _event("All-day", minutes_from_now=15, now=now)
        event["start_dt"] = None
        assert pcb._next_call([event], now) is None

    def test_nothing_upcoming(self):
        now = now_owner_tz()
        assert pcb._next_call([_event("Far call", minutes_from_now=120, now=now)], now) is None


class TestCompose:
    def test_names_the_call_and_cites_real_subjects(self):
        event = _event()
        brief = pcb.compose_pre_call_brief(
            event, gmail_tool=_gmail_with_subjects(), news_tool=_news_with_headlines()
        )
        assert brief
        assert "Call with Priya Nair" in brief
        assert "Zoom" in brief
        assert "Q3 renewal terms" in brief
        assert "Acme invoice" in brief
        assert "Acme announces Q3 results" in brief
        # Unrelated headlines are never passed off as the client's news.
        assert "Markets rally" not in brief
        assert "Local festival" not in brief

    def test_no_attendees_means_no_mail_search(self):
        event = _event(attendees=())
        brief = pcb.compose_pre_call_brief(
            event, gmail_tool=_gmail_with_subjects(), news_tool=_news_with_headlines()
        )
        assert brief
        assert "no attendees named on the invite" in brief
        assert "Q3 renewal terms" not in brief

    def test_no_matching_mail_says_so(self):
        event = _event()
        brief = pcb.compose_pre_call_brief(
            event, gmail_tool=_FakeGmailTool(), news_tool=_news_with_headlines()
        )
        assert "no recent threads with Priya Nair" in brief

    def test_no_matching_news_says_so(self):
        event = _event()
        news = _FakeNewsTool(headlines_by_category={
            "business": ["Markets rally on rate hopes"],
            "general": ["Local festival draws crowds"],
        })
        brief = pcb.compose_pre_call_brief(
            event, gmail_tool=_gmail_with_subjects(), news_tool=news
        )
        assert "nothing matching" in brief
        assert "Markets rally" not in brief

    def test_failing_sources_contribute_honest_lines(self):
        event = _event()
        brief = pcb.compose_pre_call_brief(
            event,
            gmail_tool=_FakeGmailTool(is_error=True),
            news_tool=_FakeNewsTool(is_error=True),
        )
        assert brief
        assert "could not read your inbox" in brief
        assert "could not fetch the news" in brief
        assert "won't guess" in brief
        assert "Call with Priya Nair" in brief  # the call still composes

    def test_brief_is_capped_to_one_page(self):
        event = _event()
        gmail = _FakeGmailTool(by_query={"Priya Nair": ["x" * 500, "y" * 500, "z" * 500]})
        news = _FakeNewsTool(headlines_by_category={
            "business": ["Acme " + "n" * 600],
            "general": [],
        })
        brief = pcb.compose_pre_call_brief(event, gmail_tool=gmail, news_tool=news)
        assert brief
        assert len(brief) <= pcb.MAX_BRIEF_CHARS

    def test_no_event_means_no_brief(self):
        assert pcb.compose_pre_call_brief(None) is None

    def test_broken_tools_never_raise(self):
        event = _event()

        class _ExplodingTool:
            def execute(self, *a, **k):
                raise ConnectionError("down")

        brief = pcb.compose_pre_call_brief(
            event, gmail_tool=_ExplodingTool(), news_tool=_ExplodingTool()
        )
        assert brief
        assert "probe failed (ConnectionError)" in brief


class TestDelivery:
    def test_delivers_once_per_call(self):
        now = now_owner_tz()
        event = _event(now=now)
        notes = _FakeNotifications()
        first = pcb.maybe_deliver_pre_call_brief(
            notes, now=now, calendar_fetcher=lambda n: [event],
            gmail_tool=_gmail_with_subjects(), news_tool=_news_with_headlines(),
        )
        second = pcb.maybe_deliver_pre_call_brief(
            notes, now=now, calendar_fetcher=lambda n: [event],
            gmail_tool=_gmail_with_subjects(), news_tool=_news_with_headlines(),
        )
        assert first
        assert second is None  # once per call
        assert len(notes.posted) == 1
        assert notes.posted[0]["category"] == "pre_call_brief"
        assert notes.posted[0]["metadata"]["source"] == "TASK-FRD-047"
        assert "Priya Nair" in notes.posted[0]["metadata"]["event"]

    def test_nothing_to_deliver_when_no_call_is_close(self):
        now = now_owner_tz()
        notes = _FakeNotifications()
        far = _event("Far call", minutes_from_now=120, now=now)
        assert pcb.maybe_deliver_pre_call_brief(
            notes, now=now, calendar_fetcher=lambda n: [far]
        ) is None
        assert notes.posted == []

    def test_broken_notification_system_never_raises(self):
        now = now_owner_tz()
        event = _event(now=now)

        class _BrokenNotifications:
            def post_notification(self, *a, **k):
                raise ConnectionError("down")

        result = pcb.maybe_deliver_pre_call_brief(
            _BrokenNotifications(), now=now, calendar_fetcher=lambda n: [event],
            gmail_tool=_gmail_with_subjects(), news_tool=_news_with_headlines(),
        )
        assert result  # composed; the push failure is swallowed


class TestIcsFeed:
    """The real calendar fetch against a local .ics file (no network)."""

    def test_file_feed_event_is_found_with_attendees(self, tmp_path, monkeypatch):
        from friday.tools.builtin.calendar import _parse_ics_content

        now = now_owner_tz()
        # 10:00 IST today; the greeting under test runs at 09:45 IST.
        # (A UTC-Zulu DTSTART keeps the parse independent of host TZ.)
        day = now.date()
        start_utc = datetime(day.year, day.month, day.day, 4, 30, tzinfo=timezone.utc)
        end_utc = datetime(day.year, day.month, day.day, 5, 0, tzinfo=timezone.utc)

        def fmt(dt):
            return dt.strftime("%Y%m%dT%H%M%SZ")
        ics = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//FRIDAY test//EN\r\n"
            "BEGIN:VEVENT\r\nUID:test-call-1\r\n"
            f"DTSTART:{fmt(start_utc)}\r\nDTEND:{fmt(end_utc)}\r\n"
            "SUMMARY:Call with Priya Nair — Acme renewal\r\n"
            "LOCATION:Zoom\r\n"
            "ATTENDEE;CN=Priya Nair:mailto:priya@example.com\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        feed = tmp_path / "test.ics"
        feed.write_text(ics, encoding="utf-8")

        # _parse_ics_content gains attendees + start_dt (TASK-FRD-047).
        events = _parse_ics_content(ics, day)
        assert len(events) == 1
        assert events[0]["attendees"] == ["Priya Nair"]
        assert isinstance(events[0]["start_dt"], datetime)
        assert events[0]["title"].startswith("Call with Priya Nair")

        # End-to-end: the file:// feed drives a real delivery.
        monkeypatch.setenv("FRIDAY_CALENDAR_ICS_URL", f"file://{feed}")
        monkeypatch.setattr(
            "friday.core.config.get_settings",
            lambda: SimpleNamespace(
                calendar_ics_url=None, email_address=None, email_app_password=None
            ),
        )
        greeting_now = datetime(
            day.year, day.month, day.day, 9, 45, tzinfo=OWNER_TZ
        )
        notes = _FakeNotifications()
        brief = pcb.maybe_deliver_pre_call_brief(
            notes, now=greeting_now,
            gmail_tool=_gmail_with_subjects(), news_tool=_news_with_headlines(),
        )
        assert brief
        assert "Call with Priya Nair" in brief
        assert "Priya Nair" in brief
        assert len(notes.posted) == 1
