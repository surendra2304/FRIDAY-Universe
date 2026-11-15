"""Event-context classification tests (TASK-IG-FUT-02).

The classifier is deterministic and citation-bound: an event exists
only because an IntelX report's own text matched, the event title is
that text verbatim, and near-miss words ("warning") never classify.
"""

from datetime import datetime, timezone
from uuid import uuid4

from futuris.connectors.intelx_context import IntelXResearchReport
from futuris.features.event_context import (
    GEOPOLITICAL_CONFLICT,
    SANCTIONS_TRADE,
    build_event_context,
    extract_events,
    headline_event,
)

UTC = timezone.utc
T1 = datetime(2026, 3, 10, tzinfo=UTC)
T2 = datetime(2026, 3, 12, tzinfo=UTC)


def _report(findings, *, summary="Market research note.", tags=None, when=T1):
    return IntelXResearchReport(
        report_id=uuid4(),
        asset_or_sector="BTCUSDT",
        published_at=when,
        summary=summary,
        sentiment_score=0.0,
        volatility_impact_factor=1.0,
        key_findings=findings,
        tags=tags or ["intelx"],
    )


def test_war_finding_classifies_as_geopolitical_with_citation():
    report = _report(["Missile strikes hit energy infrastructure overnight"])
    events = extract_events([report])
    assert len(events) == 1
    event = events[0]
    assert event.category == GEOPOLITICAL_CONFLICT
    assert event.title == "Missile strikes hit energy infrastructure overnight"
    assert event.source == "intelx"
    assert event.source_report_id == str(report.report_id)
    assert event.published_at == T1


def test_warning_is_not_war_word_boundaries_hold():
    report = _report(["Risk warning: volatility elevated into the close"])
    assert extract_events([report]) == []


def test_tariff_finding_classifies_as_sanctions_trade():
    report = _report(["New tariffs on semiconductor imports take effect Monday"])
    events = extract_events([report])
    assert [e.category for e in events] == [SANCTIONS_TRADE]


def test_tag_alone_classifies_using_first_finding_as_title():
    report = _report(
        ["Regional tensions push safe-haven flows"],
        tags=["intelx", "geopolitics"],
    )
    events = extract_events([report])
    assert len(events) == 1
    assert events[0].category == GEOPOLITICAL_CONFLICT
    assert events[0].title == "Regional tensions push safe-haven flows"


def test_summary_is_scanned_when_findings_do_not_match():
    report = _report(
        ["Liquidity conditions remain orderly"],
        summary="Ceasefire talks collapsed; bombardment resumed near the border.",
    )
    events = extract_events([report])
    assert len(events) == 1
    assert events[0].category == GEOPOLITICAL_CONFLICT
    assert events[0].title.startswith("Ceasefire talks collapsed")


def test_neutral_report_yields_no_events():
    report = _report(["Spot accumulation continues at a steady pace"])
    assert extract_events([report]) == []


def test_events_order_newest_first_and_headline_prefers_geopolitical():
    older_war = _report(["Invasion fears rattle regional markets"], when=T1)
    newer_tariff = _report(["Tariffs raised on steel imports"], when=T2)
    events = extract_events([older_war, newer_tariff])
    assert len(events) == 2
    assert events[0].published_at == T2  # newest first
    headline = headline_event(events)
    assert headline is not None
    assert headline.category == GEOPOLITICAL_CONFLICT  # war outranks newer tariff


def test_build_event_context_statuses_are_honest():
    war = _report(["Airstrikes reported near the capital"])
    neutral = _report(["Steady accumulation continues"])

    ctx = build_event_context([war], requested=False, source_failed=False)
    assert ctx.status == "not_requested" and ctx.events == []

    ctx = build_event_context([], requested=True, source_failed=True)
    assert ctx.status == "source_unavailable" and ctx.events == []

    ctx = build_event_context([neutral], requested=True, source_failed=False)
    assert ctx.status == "none_reported" and ctx.events == []

    ctx = build_event_context([war], requested=True, source_failed=False)
    assert ctx.status == "available" and len(ctx.events) == 1
