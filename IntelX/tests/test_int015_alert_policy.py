"""Tests for the watch alert policy (TASK-INT-015).

Owner decision 2026-11-18: instant alert for big breaks, ONE digest for
the rest — replacing the v1 all-digest behaviour. These tests pin the
per-watch instant bars (derived from the rule weights), the envelope
contract for both classes, the instant outbox lane, and the guarantee
that a watch without a bar never alerts instantly.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from intelx.watches.engine import (
    WATCHES,
    WATCH_PLATFORM_POLICY,
    WATCH_WORLD_EVENTS,
    FeedItem,
    FeedSource,
    WatchService,
    build_envelope,
    with_overrides,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)


def item(title: str, summary: str = "") -> FeedItem:
    return FeedItem(
        url="https://example.com/story",
        title=title,
        summary=summary,
        published_at=NOW,
        publisher="Fixture",
        source_feed="https://example.com/feed",
    )


# ---------------------------------------------------------------------------
# The bars themselves
# ---------------------------------------------------------------------------


def test_instant_bars_are_pinned_and_above_min_score():
    expected = {
        "ai_model_releases": 6,  # release_language(3) + model_name_with_version(3)
        "crypto_market_structure": 6,  # two weight-3 structure rules
        "india_tech_regulatory": 6,  # regulator_action(3) + payments_structure(3)
        "platform_policy": 6,  # policy_surface(3) + change_language(2) + platform_name(1)
        "fleet_tools": 7,  # security_event(3) + python_version(2) + release_event(2)
        "world_events": 5,  # infra_outage(3) + impact_scale(2)
    }
    for watch_id, bar in expected.items():
        watch = WATCHES[watch_id]
        assert watch.instant_min_score == bar, watch_id
        assert bar > watch.min_score, watch_id


def test_envelope_classes():
    digest = build_envelope(WATCH_PLATFORM_POLICY, item("Some alert"), 5, [], NOW)
    assert digest["alert_class"] == "digest"
    assert digest["severity"] == "info"
    assert digest["quiet_hours_exempt"] is False

    instant = build_envelope(
        WATCH_PLATFORM_POLICY, item("Big break"), 6, [], NOW, alert_class="instant"
    )
    assert instant["alert_class"] == "instant"
    assert instant["severity"] == "high"
    assert instant["quiet_hours_exempt"] is True
    # Same item, same dedupe identity — the class never forks the record.
    assert instant["dedupe_key"] == build_envelope(
        WATCH_PLATFORM_POLICY, item("Big break"), 6, [], NOW
    )["dedupe_key"]


# ---------------------------------------------------------------------------
# End to end: one poll, both classes
# ---------------------------------------------------------------------------

PLATFORM_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Fixture</title>
<item><title>YouTube updates Partner Program eligibility requirements for monetization</title>
<link>https://example.com/partner-program</link>
<description>Creators must now meet new subscriber thresholds.</description>
<pubDate>Tue, 17 Nov 2026 05:00:00 GMT</pubDate></item>
<item><title>An Update on the Content We Recommend on Instagram in India</title>
<link>https://example.com/recommend-update</link>
<description>We have strengthened the default protections behind what Instagram recommends.</description>
<pubDate>Tue, 17 Nov 2026 03:58:09 GMT</pubDate></item>
</channel></rss>"""

WORLD_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Fixture</title>
<item><title>Undersea cable cut leaves millions without internet across West Africa</title>
<link>https://example.com/cable-cut</link>
<description>Repair ships have been dispatched; traffic is rerouted.</description>
<pubDate>Tue, 17 Nov 2026 06:00:00 GMT</pubDate></item>
<item><title>Powerful earthquake strikes Taiwan</title>
<link>https://example.com/quake</link>
<description>Millions without power as a state of emergency is declared.</description>
<pubDate>Tue, 17 Nov 2026 04:00:00 GMT</pubDate></item>
<item><title>Waymo suspends driverless freeway rides across US after California ban</title>
<link>https://example.com/waymo</link>
<description>Waymo is pausing the service.</description>
<pubDate>Tue, 17 Nov 2026 02:00:00 GMT</pubDate></item>
</channel></rss>"""


class FakeFetcher:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def fetch(self, url: str) -> tuple[int, bytes]:
        return (200, self.payload)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


async def test_poll_splits_instant_and_digest(tmp_path: Path):
    watch = with_overrides(
        WATCH_PLATFORM_POLICY,
        sources=(FeedSource("https://feed.example/meta.xml", "Meta Fixture"),),
        max_alerts_per_poll=2,
        max_alerts_per_day=3,
    )
    service = WatchService(
        state_path=tmp_path / "state.json",
        outbox_path=tmp_path / "outbox.jsonl",
        fetcher=FakeFetcher(PLATFORM_RSS),
    )
    result = await service.poll_once(watch, now=NOW)
    assert len(result.alerted) == 2
    assert result.alerted_instant == 1
    by_title = {e["title"]: e for e in result.alerted}
    instant = by_title["YouTube updates Partner Program eligibility requirements for monetization"]
    digest = by_title["An Update on the Content We Recommend on Instagram in India"]
    assert instant["alert_class"] == "instant" and instant["severity"] == "high"
    assert instant["quiet_hours_exempt"] is True
    assert digest["alert_class"] == "digest" and digest["severity"] == "info"
    assert digest["quiet_hours_exempt"] is False

    # The main outbox is the complete record; the instant lane holds only
    # the instant envelope.
    main_lines = read_jsonl(tmp_path / "outbox.jsonl")
    instant_lines = read_jsonl(tmp_path / "instant_outbox.jsonl")
    assert len(main_lines) == 2
    assert [e["dedupe_key"] for e in instant_lines] == [instant["dedupe_key"]]
    assert result.to_dict()["alerted_instant"] == 1


async def test_world_events_bar_is_an_outage_with_impact(tmp_path: Path):
    watch = with_overrides(
        WATCH_WORLD_EVENTS,
        sources=(FeedSource("https://feed.example/aj.xml", "AJ Fixture"),),
        max_alerts_per_poll=3,
        max_alerts_per_day=4,
    )
    service = WatchService(
        state_path=tmp_path / "state.json",
        outbox_path=tmp_path / "outbox.jsonl",
        fetcher=FakeFetcher(WORLD_RSS),
    )
    result = await service.poll_once(watch, now=NOW)
    classes = {e["title"]: e["alert_class"] for e in result.alerted}
    assert classes == {
        "Undersea cable cut leaves millions without internet across West Africa": "instant",
        "Powerful earthquake strikes Taiwan": "digest",
    }
    assert result.alerted_instant == 1
    assert result.below_threshold == 1  # the Waymo item


async def test_watch_without_a_bar_never_alerts_instantly(tmp_path: Path):
    watch = with_overrides(
        WATCH_PLATFORM_POLICY,
        sources=(FeedSource("https://feed.example/meta.xml", "Meta Fixture"),),
        max_alerts_per_poll=2,
        max_alerts_per_day=3,
        instant_min_score=None,
    )
    service = WatchService(
        state_path=tmp_path / "state.json",
        outbox_path=tmp_path / "outbox.jsonl",
        fetcher=FakeFetcher(PLATFORM_RSS),
    )
    result = await service.poll_once(watch, now=NOW)
    assert len(result.alerted) == 2
    assert result.alerted_instant == 0
    assert all(e["alert_class"] == "digest" for e in result.alerted)
    assert read_jsonl(tmp_path / "instant_outbox.jsonl") == []
