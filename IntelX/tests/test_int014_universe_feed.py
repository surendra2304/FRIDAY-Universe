"""Tests for the Universe intel feed (TASK-INT-014).

Owner decision 2026-11-18: IntelX shares its data with Futuris, Stratex
and all agents. The feed is ONE broadcast publish over Memora's durable
event feed (recipient "all" = visible to every agent's cursor poll); these
tests pin the publish shape, the per-agent subscription filters, and the
watch engine's feed hook (env-gated, injectable, failure-isolated).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from intelx.feed import (
    DEFAULT_SUBSCRIPTIONS,
    IntelFeedEntry,
    accepts,
    domains_for,
    publish_feed_entry,
)
from intelx.watches.engine import (
    WATCH_PLATFORM_POLICY,
    FeedSource,
    WatchService,
    with_overrides,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# The broadcast publish
# ---------------------------------------------------------------------------


async def test_publish_feed_entry_broadcasts_once_to_all():
    calls: list[dict] = []

    async def fake_publisher(**kwargs):
        calls.append(kwargs)
        return {"status": "accepted", "event_id": "evt-1"}

    entry = IntelFeedEntry(
        entry_id="intelx.watch:platform_policy:abc123",
        headline="YouTube updates Partner Program eligibility",
        summary="Creators must meet new thresholds.",
        domain="platforms_policy",
        category="watch_alert",
        topics=["platforms_policy", "platform_policy"],
        sources=[{"url": "https://blog.youtube/post", "title": "t"}],
    )
    outcome = await publish_feed_entry(entry, publisher=fake_publisher)
    assert outcome["status"] == "accepted"
    assert len(calls) == 1  # ONE publish for the whole Universe
    call = calls[0]
    assert call["target_agent"] == "all"
    assert call["run_id"] == entry.entry_id  # retries dedupe on this id
    assert call["domain"] == "platforms_policy"
    assert call["category"] == "watch_alert"
    assert call["recommended_targets"] == entry.topics
    assert call["finding_summary"].startswith("YouTube updates Partner Program")
    assert "Creators must meet new thresholds." in call["finding_summary"]
    assert call["sources"] == entry.sources


def test_finding_text_composition():
    both = IntelFeedEntry(entry_id="e", headline="H", summary="S", domain="markets")
    assert both.finding_text() == "H\n\nS"
    same = IntelFeedEntry(entry_id="e", headline="H", summary="H", domain="markets")
    assert same.finding_text() == "H"
    empty_summary = IntelFeedEntry(entry_id="e", headline="H", summary="", domain="markets")
    assert empty_summary.finding_text() == "H"


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


def test_named_first_consumers():
    # Futuris (forecasts everything) takes all domains; Stratex takes the
    # domains that move his book.
    assert domains_for("futuris") is None
    assert accepts("futuris", "platforms_policy")
    assert accepts("stratex", "markets")
    assert accepts("stratex", "india_regulatory")
    assert accepts("stratex", "world_events")
    assert not accepts("stratex", "platforms_policy")
    assert not accepts("stratex", "tools_infra")


def test_specialist_subscriptions():
    assert accepts("vyralx", "platforms_policy")
    assert not accepts("vyralx", "markets")
    assert accepts("sentinel", "tools_infra")
    assert accepts("forge", "ai_models")
    assert accepts("inference", "tools_infra")
    assert accepts("friday", "world_events")  # breadth agents take all
    assert accepts("cortex", "ai_models")
    assert accepts("memora", "markets")


def test_unknown_agent_defaults_to_all_and_undomained_is_general():
    assert accepts("some_future_agent", "markets")
    # A notice with no domain is "general": specialists do not receive it,
    # breadth agents do.
    assert not accepts("stratex", None)
    assert accepts("futuris", None)
    assert set(DEFAULT_SUBSCRIPTIONS) == {
        "futuris", "stratex", "friday", "cortex", "memora",
        "sentinel", "forge", "inference", "vyralx",
    }


def test_subscription_env_override():
    env = {"INTELX_FEED_SUB_STRATEX": "markets"}
    assert domains_for("stratex", env=env) == frozenset({"markets"})
    assert accepts("stratex", "markets", env=env)
    assert not accepts("stratex", "world_events", env=env)
    assert domains_for("stratex", env={"INTELX_FEED_SUB_STRATEX": "all"}) is None


# ---------------------------------------------------------------------------
# The watch engine's feed hook
# ---------------------------------------------------------------------------

PLATFORM_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Meta Newsroom fixture</title>
<item><title>An Update on the Content We Recommend on Instagram in India</title>
<link>https://example.com/recommend-update</link>
<description>We have strengthened the default protections behind what Instagram recommends.</description>
<pubDate>Tue, 17 Nov 2026 03:58:09 GMT</pubDate></item>
<item><title>Introducing Direct: An App Just for Messaging</title>
<link>https://example.com/direct-app</link>
<description>A new messaging app.</description>
<pubDate>Tue, 17 Nov 2026 01:00:48 GMT</pubDate></item>
</channel></rss>"""


class FakeFetcher:
    async def fetch(self, url: str) -> tuple[int, bytes]:
        return (200, PLATFORM_RSS)


def fixture_watch():
    return with_overrides(
        WATCH_PLATFORM_POLICY,
        sources=(FeedSource("https://feed.example/meta.xml", "Meta Fixture"),),
    )


def make_service(tmp_path: Path, **kwargs) -> WatchService:
    return WatchService(
        state_path=tmp_path / "state.json",
        outbox_path=tmp_path / "outbox.jsonl",
        fetcher=FakeFetcher(),
        **kwargs,
    )


async def test_hook_publishes_alerted_envelope_with_domain(tmp_path: Path):
    published: list[IntelFeedEntry] = []

    async def recording_publisher(entry: IntelFeedEntry):
        published.append(entry)
        return {"status": "accepted"}

    service = make_service(
        tmp_path, feed_publisher=recording_publisher, feed_enabled=True
    )
    result = await service.poll_once(fixture_watch(), now=NOW)
    assert len(result.alerted) == 1  # only the policy item alerts
    assert result.feed_published == 1 and result.feed_errors == 0
    assert len(published) == 1
    entry = published[0]
    assert entry.domain == "platforms_policy"
    assert entry.category == "watch_alert"
    assert entry.topics == ["platforms_policy", "platform_policy"]
    assert entry.entry_id == result.alerted[0]["dedupe_key"]
    assert entry.sources[0]["url"] == "https://example.com/recommend-update"
    assert result.to_dict()["feed_published"] == 1


async def test_hook_is_off_by_default(tmp_path: Path):
    published: list[IntelFeedEntry] = []

    async def recording_publisher(entry: IntelFeedEntry):
        published.append(entry)
        return {"status": "accepted"}

    service = make_service(tmp_path, feed_publisher=recording_publisher)
    result = await service.poll_once(fixture_watch(), now=NOW)
    assert len(result.alerted) == 1
    assert published == []
    assert result.feed_published == 0 and result.feed_errors == 0


async def test_hook_failure_never_breaks_the_poll(tmp_path: Path):
    async def exploding_publisher(entry: IntelFeedEntry):
        raise RuntimeError("memora unreachable")

    service = make_service(
        tmp_path, feed_publisher=exploding_publisher, feed_enabled=True
    )
    result = await service.poll_once(fixture_watch(), now=NOW)
    # The alert still landed in the outbox (PRO-001's channel) and the
    # failure is counted, not hidden.
    assert len(result.alerted) == 1
    assert (tmp_path / "outbox.jsonl").exists()
    assert result.feed_published == 0 and result.feed_errors == 1


async def test_hook_counts_not_delivered_verdicts_as_errors(tmp_path: Path):
    async def disabled_publisher(entry: IntelFeedEntry):
        return {"status": "disabled"}

    service = make_service(
        tmp_path, feed_publisher=disabled_publisher, feed_enabled=True
    )
    result = await service.poll_once(fixture_watch(), now=NOW)
    assert result.feed_published == 0 and result.feed_errors == 1
