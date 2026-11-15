"""Event context for market outlooks (TASK-IG-FUT-02).

Owner IG-corpus idea (source video ``DVbDGQCDzkJ``): *"Fold
geopolitical-event context into market outlooks so forecasts explain
war-driven moves."*

Futuris market forecasts already ingest IntelX research reports, but
until now the reports only nudged numeric multipliers and one
"catalyst" sentence: a forecast issued while a war drove the market
said nothing about the war. This module closes that gap
deterministically:

* every IntelX report is scanned (tags, key findings, summary) against
  conservative per-category keyword sets, with word-boundary matching
  so "warning" never reads as "war";
* each match becomes a :class:`MarketEvent` that **cites the report it
  came from** -- title is the report's own finding/summary text,
  verbatim, never paraphrased or invented;
* the market router surfaces the events as a structured
  ``event_context`` block and folds the headline event into the
  forecast rationale, labelled with its source.

Discipline (FUT-005): classification is explanatory only. It changes
no number in the forecast, names no event IntelX did not report, and
when IntelX itself is unreachable the router reports
``source_unavailable`` rather than filling the gap.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field

from futuris.connectors.intelx_context import IntelXResearchReport

#: Event categories, most market-violent first. Plain strings --
#: production runs Python 3.10, so no 3.11+ enum helpers.
GEOPOLITICAL_CONFLICT = "geopolitical_conflict"
SANCTIONS_TRADE = "sanctions_trade"
ENERGY_SUPPLY = "energy_supply"
MONETARY_POLICY = "monetary_policy"
REGULATORY = "regulatory"

CATEGORY_PRIORITY: tuple[str, ...] = (
    GEOPOLITICAL_CONFLICT,
    SANCTIONS_TRADE,
    ENERGY_SUPPLY,
    MONETARY_POLICY,
    REGULATORY,
)

#: Conservative keyword sets per category. Phrases are matched on
#: word boundaries against lowercased report text. A term is included
#: only if, in a research finding, it plainly denotes the category --
#: when in doubt the term is left out (a missed event is a smaller
#: failure than an invented one).
_CATEGORY_PHRASES: dict[str, tuple[str, ...]] = {
    GEOPOLITICAL_CONFLICT: (
        "war",
        "invasion",
        "invaded",
        "airstrike",
        "airstrikes",
        "air strike",
        "air strikes",
        "missile",
        "missiles",
        "military operation",
        "armed conflict",
        "ceasefire",
        "cease-fire",
        "troops",
        "bombardment",
        "geopolitical",
        "geopolitics",
        "martial law",
        "declares war",
        "declared war",
    ),
    SANCTIONS_TRADE: (
        "sanction",
        "sanctions",
        "sanctioned",
        "tariff",
        "tariffs",
        "trade war",
        "export controls",
        "export ban",
        "import ban",
        "embargo",
    ),
    ENERGY_SUPPLY: (
        "opec",
        "oil supply",
        "crude supply",
        "energy supply",
        "gas supply",
        "strait of hormuz",
        "pipeline shutdown",
        "oil output cut",
        "production cut",
    ),
    MONETARY_POLICY: (
        "rate hike",
        "rate cut",
        "interest rate decision",
        "central bank",
        "fomc",
        "federal reserve",
        "monetary policy",
        "quantitative easing",
        "quantitative tightening",
    ),
    REGULATORY: (
        "antitrust",
        "sec charges",
        "sec sues",
        "regulatory action",
        "regulatory ban",
        "court ruling",
        "lawsuit",
    ),
}


def _compile(phrases: tuple[str, ...]) -> re.Pattern[str]:
    parts = [r"\b" + re.escape(p) + r"\b" for p in phrases]
    return re.compile("|".join(parts))


_PATTERNS: dict[str, re.Pattern[str]] = {
    category: _compile(phrases) for category, phrases in _CATEGORY_PHRASES.items()
}


class MarketEvent(BaseModel):
    """One real-world event cited from one IntelX research report."""

    title: str  # the report's own finding/summary text, verbatim
    category: str
    source: str = "intelx"
    source_report_id: str
    published_at: datetime


class EventContext(BaseModel):
    """Structured event context attached to a market forecast.

    ``status`` is one of:

    * ``available`` -- at least one event was classified from reports;
    * ``none_reported`` -- IntelX answered, no report matched an event
      category (stated, not filled);
    * ``source_unavailable`` -- IntelX could not be read, so no event
      context could be derived (never backfilled);
    * ``not_requested`` -- the caller did not include IntelX context.
    """

    status: str
    events: list[MarketEvent] = Field(default_factory=list)


def _report_texts(report: IntelXResearchReport) -> list[str]:
    """Texts scanned for a report, most specific first."""
    texts = [f for f in report.key_findings if f and f.strip()]
    if report.summary and report.summary.strip():
        texts.append(report.summary)
    return texts


def _matches(category: str, text: str) -> bool:
    return _PATTERNS[category].search(text.lower()) is not None


def extract_events(reports: list[IntelXResearchReport]) -> list[MarketEvent]:
    """Classify IntelX reports into cited market events.

    At most one event per (report, category): the first matching
    finding (or the summary) becomes the event title. Tags are scanned
    too -- a report IntelX itself tagged "geopolitics" classifies even
    if its findings are terse. Events are ordered newest first, with
    category priority breaking ties, so the headline event is the most
    consequential recent one.
    """
    events: list[MarketEvent] = []
    for report in reports:
        tag_text = " ".join(report.tags or [])
        texts = _report_texts(report)
        for category in CATEGORY_PRIORITY:
            title: str | None = None
            if _matches(category, tag_text):
                title = texts[0] if texts else report.summary
            else:
                for text in texts:
                    if _matches(category, text):
                        title = text
                        break
            if title:
                events.append(
                    MarketEvent(
                        title=title.strip(),
                        category=category,
                        source_report_id=str(report.report_id),
                        published_at=report.published_at,
                    )
                )
    priority = {name: idx for idx, name in enumerate(CATEGORY_PRIORITY)}
    events.sort(
        key=lambda e: (e.published_at, -priority[e.category]),
        reverse=True,
    )
    return events


def headline_event(events: list[MarketEvent]) -> MarketEvent | None:
    """The event a forecast rationale should name, if any.

    A geopolitical-conflict event outranks everything else (that is
    the class of move this feature exists to explain); otherwise the
    most recent event, per :func:`extract_events` ordering.
    """
    for event in events:
        if event.category == GEOPOLITICAL_CONFLICT:
            return event
    return events[0] if events else None


def build_event_context(
    reports: list[IntelXResearchReport],
    *,
    requested: bool,
    source_failed: bool,
) -> EventContext:
    """Compose the honest event-context block for one forecast."""
    if not requested:
        return EventContext(status="not_requested")
    events = extract_events(reports)
    if events:
        return EventContext(status="available", events=events)
    if source_failed:
        return EventContext(status="source_unavailable")
    return EventContext(status="none_reported")
