"""TASK-VOI-002: proactive morning brief.

Every morning (once, 09:00-12:00 local), FRIDAY composes a brief from REAL
data — daily goal, live fleet status, portfolio snapshot, overnight events —
and pushes it as a proactive notification so it is spoken/surfaced on the
owner's first interaction without being asked.

Rules pinned here:
- composed at most once per morning;
- nothing outside the morning window;
- every failing component contributes an honest line, never a guess;
- composition failure never raises to the caller.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit]

from friday.proactive import morning_brief as mb


class _FakeNotifications:
    def __init__(self, pending=None):
        self.pending = pending or []
        self.posted = []

    def fetch_pending_notifications(self, mark_delivered=True):
        return list(self.pending)

    def post_notification(self, message, category="x", severity="info", metadata=None, notification_id=None):
        self.posted.append({"message": message, "category": category, "metadata": metadata})
        return "id"


class _BrokenNotifications:
    def fetch_pending_notifications(self, mark_delivered=True):
        raise ConnectionError("down")

    def post_notification(self, *a, **k):
        raise ConnectionError("down")


def _in_window(monkeypatch, hour=10):
    monkeypatch.setattr(mb, "_in_morning_window", lambda now=None: True)
    monkeypatch.setattr(mb, "_today", lambda: f"2026-11-10-T{hour}")


class TestMorningBrief:
    def test_composes_once_per_morning(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        with patch.object(mb, "_goal_line", return_value="Good morning Surendra. Focus: X (0%)."), \
             patch.object(mb, "_fleet_line", return_value="Fleet status: 9/9 specialist agents up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 10,792.80; Open positions: none"):
            first = mb.compose_morning_brief(_FakeNotifications())
            second = mb.compose_morning_brief(_FakeNotifications())
        assert first and "9/9 specialist agents up" in first
        assert "10,792.80" in first
        assert second is None  # once per morning

    def test_nothing_outside_the_window(self, monkeypatch) -> None:
        monkeypatch.setattr(mb, "_in_morning_window", lambda now=None: False)
        mb.reset_for_tests()
        assert mb.compose_morning_brief(_FakeNotifications()) is None

    def test_failing_probe_contributes_honest_line(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        with patch.object(mb, "_goal_line", return_value="Good morning Surendra. What is your primary objective for today?"), \
             patch.object(mb, "_fleet_line", side_effect=ConnectionError("probe down")), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 10,792.80"):
            brief = mb.compose_morning_brief(_FakeNotifications())
        assert brief
        assert "probe failed (ConnectionError)" in brief
        assert "won't guess" in brief
        assert "10,792.80" in brief  # other components still compose

    def test_overnight_events_are_included(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        notes = _FakeNotifications(pending=[
            type("N", (), {"message": "CPU ran hot at 03:12"})(),
        ])
        with patch.object(mb, "_goal_line", return_value="Good morning."), \
             patch.object(mb, "_fleet_line", return_value="Fleet: 9/9 up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 1"):
            brief = mb.compose_morning_brief(notes)
        assert "CPU ran hot at 03:12" in brief

    def test_delivery_pushes_a_notification(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        notes = _FakeNotifications()
        with patch.object(mb, "_goal_line", return_value="Good morning."), \
             patch.object(mb, "_fleet_line", return_value="Fleet: 9/9 up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 1"):
            delivered = mb.maybe_deliver_morning_brief(notes)
        assert delivered
        assert len(notes.posted) == 1
        assert notes.posted[0]["category"] == "morning_brief"
        assert notes.posted[0]["metadata"]["source"] == "TASK-VOI-002"

    def test_broken_notification_system_never_raises(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        with patch.object(mb, "_goal_line", return_value="Good morning."), \
             patch.object(mb, "_fleet_line", return_value="Fleet: 9/9 up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 1"):
            result = mb.maybe_deliver_morning_brief(_BrokenNotifications())
        assert result  # composed; the push failure is swallowed

    def test_goal_line_is_real_or_honestly_failed(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        with patch.object(mb, "_fleet_line", return_value="Fleet: up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: up"):
            brief = mb.compose_morning_brief(_FakeNotifications())
        assert brief
        # Either the real daily-rhythm line (Oracle available) or the honest
        # failure line — never a fabricated goal, never a missing section.
        assert brief.startswith("Good morning") or "could not read today's goal" in brief


class _FakeReport:
    """Minimal stand-in for agentic_inbox.TriageReport."""

    def __init__(self, status="ok", counts=None, subjects=None):
        self.status = status
        self._counts = counts or {}
        self.items = [
            type("Item", (), {"message": type("M", (), {"subject": s})()})()
            for s in (subjects or [])
        ]

    def counts(self):
        return dict(self._counts)


class TestInboxLine:
    """TASK-FRD-027: overnight mail triage joins the brief (OpenJarvis parity)."""

    def test_counts_and_most_urgent_subject(self) -> None:
        report = _FakeReport(
            counts={"action_required": 1, "newsletter": 1},
            subjects=["Password reset for your account", "Weekly digest"],
        )
        line = mb._inbox_line(triage=lambda **kw: report)
        assert "2 unread" in line
        assert "1 needing action" in line
        assert "1 newsletters" in line
        assert "most urgent: Password reset for your account" in line

    def test_unconfigured_mailbox_omits_the_section(self) -> None:
        report = _FakeReport(status="not_configured: FRIDAY_EMAIL_ADDRESS unset")
        assert mb._inbox_line(triage=lambda **kw: report) == ""

    def test_failed_fetch_is_an_honest_line(self) -> None:
        report = _FakeReport(status="fetch_failed: ConnectionError: boom")
        line = mb._inbox_line(triage=lambda **kw: report)
        assert "could not read your inbox" in line
        assert "won't guess" in line

    def test_empty_inbox_says_so(self) -> None:
        line = mb._inbox_line(triage=lambda **kw: _FakeReport())
        assert "no unread mail" in line


class _FakeCalendarTool:
    def __init__(self, content, is_error=False):
        self._content = content
        self._is_error = is_error

    def execute(self):
        return type(
            "R", (), {"content": self._content, "is_error": self._is_error}
        )()


class TestCalendarLine:
    """TASK-FRD-027: today's first meeting joins the brief (OpenJarvis parity)."""

    def test_first_meeting_is_named(self) -> None:
        tool = _FakeCalendarTool(
            "You have 2 meetings scheduled today:\n"
            "1. Weekly sync at 09:00 AM - 09:30 AM\n"
            "2. Client call at 12:00 PM - 12:30 PM"
        )
        line = mb._calendar_line(tool=tool)
        assert line == "First meeting: Weekly sync at 09:00 AM - 09:30 AM."

    def test_unconfigured_feed_omits_the_section(self) -> None:
        tool = _FakeCalendarTool(
            "No calendar feed configured. Set FRIDAY_CALENDAR_ICS_URL in your .env file."
        )
        assert mb._calendar_line(tool=tool) == ""

    def test_failed_feed_is_an_honest_line(self) -> None:
        tool = _FakeCalendarTool("Failed to fetch calendar feed: boom", is_error=True)
        line = mb._calendar_line(tool=tool)
        assert "could not read today's calendar" in line
        assert "won't guess" in line

    def test_empty_day_says_so(self) -> None:
        tool = _FakeCalendarTool("You have no meetings scheduled for today.")
        assert mb._calendar_line(tool=tool) == "Calendar: nothing scheduled today."


class TestBriefIncludesParitySections:
    def test_mail_and_calendar_sections_compose(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        with patch.object(mb, "_goal_line", return_value="Good morning."), \
             patch.object(mb, "_fleet_line", return_value="Fleet: 9/9 up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 1"), \
             patch.object(mb, "_inbox_line", return_value="Mail: 2 unread — 1 needing action."), \
             patch.object(mb, "_calendar_line", return_value="First meeting: Weekly sync at 09:00 AM - 09:30 AM."):
            brief = mb.compose_morning_brief(_FakeNotifications())
        assert brief
        assert "Mail: 2 unread" in brief
        assert "First meeting: Weekly sync" in brief

    def test_unconfigured_sources_add_no_sections(self, monkeypatch) -> None:
        _in_window(monkeypatch)
        mb.reset_for_tests()
        with patch.object(mb, "_goal_line", return_value="Good morning."), \
             patch.object(mb, "_fleet_line", return_value="Fleet: 9/9 up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 1"), \
             patch.object(mb, "_inbox_line", return_value=""), \
             patch.object(mb, "_calendar_line", return_value=""):
            brief = mb.compose_morning_brief(_FakeNotifications())
        assert brief
        assert "Mail:" not in brief
        assert "First meeting" not in brief


class TestGreetingDelivery:
    """The owner's first greeting of the morning carries the brief."""

    def test_agent_greeting_carries_the_brief(self, monkeypatch) -> None:
        from friday.agent.agent import FridayAgent
        from friday.core.config import Settings

        _in_window(monkeypatch)
        mb.reset_for_tests()
        with patch.object(mb, "_goal_line", return_value="Good morning Surendra."), \
             patch.object(mb, "_fleet_line", return_value="Fleet: 9/9 up"), \
             patch.object(mb, "_portfolio_line", return_value="Portfolio: Balance: 10,792.80"):
            agent = FridayAgent(settings=Settings(env="testing"))
            response = agent.process_message("hello friday")
        # In the morning window the brief (or the notification summary that
        # wraps it) precedes or joins the greeting.
        combined = response.content
        assert "Fleet" in combined or "Good morning" in combined
