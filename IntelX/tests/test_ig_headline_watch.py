"""Tests for TASK-IG-INT-01 — standing real-time financial-headline watch.

Hermetic: all fetching is injected; no network is touched.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from intelx.ingestion.headline_watch import (
    DEFAULT_SOURCES,
    HeadlineSource,
    HeadlineWatch,
    classify_impact,
    headline_fingerprint,
    parse_feed,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)

RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>FinancialJuice</title>
<item><title>FinancialJuice: Fed cuts rates by 25bp in emergency meeting</title>
<link>https://www.financialjuice.com/News/1/fed.aspx</link>
<pubDate>Sun, 15 Nov 2026 11:58:00 GMT</pubDate><guid isPermaLink="false">1</guid></item>
<item><title>Local bakery wins regional bread award</title>
<link>https://www.financialjuice.com/News/2/bread.aspx</link>
<pubDate>Sun, 15 Nov 2026 11:57:00 GMT</pubDate><guid isPermaLink="false">2</guid></item>
<item><title>Bitcoin ETF approval sparks liquidation cascade</title>
<link>https://www.financialjuice.com/News/3/btc.aspx</link>
<pubDate>Sun, 15 Nov 2026 11:56:00 GMT</pubDate><guid isPermaLink="false">3</guid></item>
</channel></rss>"""

ATOM_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Example Wire</title>
<entry><title>US CPI inflation rate rises to 3.4%</title>
<link rel="alternate" href="https://example.com/cpi"/>
<published>2026-11-15T11:50:00Z</published></entry>
</feed>"""

SRC = HeadlineSource(source_id="t_rss", name="Test RSS", kind="rss", url="https://example.com/feed")


def test_parse_rss_fixture() -> None:
    heads = parse_feed(RSS_FIXTURE, SRC, NOW)
    assert len(heads) == 3
    assert heads[0].source_id == "t_rss"
    assert heads[0].published_at == datetime(2026, 11, 15, 11, 58, tzinfo=UTC)
    assert heads[0].url.endswith("fed.aspx")
    assert all(h.fingerprint for h in heads)
    assert len({h.fingerprint for h in heads}) == 3


def test_parse_atom_fixture() -> None:
    src = HeadlineSource(source_id="t_atom", name="Atom", kind="rss", url="https://example.com/atom")
    heads = parse_feed(ATOM_FIXTURE, src, NOW)
    assert len(heads) == 1
    assert heads[0].title.startswith("US CPI")
    assert heads[0].url == "https://example.com/cpi"
    assert heads[0].impact.tier in ("critical", "high")


def test_parse_feed_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_feed("this is not xml", SRC, NOW)


def test_classify_impact_tiers() -> None:
    fed = classify_impact("Fed cuts rates by 25bp in emergency meeting")
    assert fed.score >= 60 and fed.tier == "critical"
    assert "federal reserve" in fed.matched_phrases or "emergency meeting" in fed.matched_phrases

    cpi = classify_impact("US CPI inflation rate rises to 3.4%")
    assert cpi.score >= 35 and cpi.tier in ("critical", "high")

    btc = classify_impact("Bitcoin ETF approval sparks liquidation cascade")
    assert "BTC" in btc.assets
    assert btc.score >= 35

    mundane = classify_impact("Local bakery wins regional bread award")
    assert mundane.score < 15 and mundane.tier == "low"
    assert mundane.assets == ()


def test_classify_direction_is_labelled_heuristic() -> None:
    assert classify_impact("Bitcoin surges to record high").direction == "bullish"
    assert classify_impact("Exchange hack sparks plunge").direction == "bearish"
    assert classify_impact("Committee meets on Tuesday").direction == "neutral"


def test_fingerprint_stable_and_source_scoped() -> None:
    a = headline_fingerprint("s1", "Same  Title", "https://x/1")
    b = headline_fingerprint("s1", "same title", "https://x/1")
    c = headline_fingerprint("s2", "same title", "https://x/1")
    assert a == b
    assert a != c


async def _watch_with(feeds: dict[str, str], sources: list[HeadlineSource]) -> HeadlineWatch:
    async def fetch(url: str) -> str:
        if url not in feeds:
            raise RuntimeError(f"boom for {url}")
        return feeds[url]

    return HeadlineWatch(sources=sources, fetch_text=fetch)


async def test_poll_dedupes_across_sweeps() -> None:
    watch = await _watch_with({"https://example.com/feed": RSS_FIXTURE}, [SRC])
    first = await watch.poll_once()
    assert len(first) == 3
    second = await watch.poll_once()
    assert second == []
    assert len(watch.latest(limit=10)) == 3


async def test_latest_filters_by_impact_and_asset() -> None:
    watch = await _watch_with({"https://example.com/feed": RSS_FIXTURE}, [SRC])
    await watch.poll_once()
    high = watch.latest(limit=10, min_score=35)
    assert high and all(h.impact.score >= 35 for h in high)
    btc = watch.latest(limit=10, asset="BTC")
    assert len(btc) == 1 and "BTC" in btc[0].impact.assets


async def test_one_bad_source_does_not_kill_sweep() -> None:
    bad = HeadlineSource(source_id="bad", name="Bad", kind="rss", url="https://example.com/bad")
    watch = await _watch_with({"https://example.com/feed": RSS_FIXTURE}, [SRC, bad])
    fresh = await watch.poll_once()
    assert len(fresh) == 3
    report = {r["source_id"]: r for r in watch.source_report()}
    assert "boom" in report["bad"]["last_error"]
    assert report["t_rss"]["headlines_new"] == 3


async def test_x_account_sources_never_fabricate() -> None:
    xsrc = HeadlineSource(
        source_id="deltaone_x",
        name="DeltaOne",
        kind="x_account",
        handle="Deltaone",
        active=False,
        unavailable_reason="no keyless feed",
    )

    async def fetch(url: str) -> str:  # must never be called for x_account
        raise AssertionError("x_account source was fetched")

    watch = HeadlineWatch(sources=[xsrc], fetch_text=fetch)
    fresh = await watch.poll_once()
    assert fresh == []
    report = watch.source_report()[0]
    assert report["active"] is False
    assert report["unavailable_reason"] == "no keyless feed"


def test_default_sources_cover_named_accounts_honestly() -> None:
    by_id = {s.source_id: s for s in DEFAULT_SOURCES}
    # FinancialJuice wire is live over RSS; the pure-X accounts are registered
    # as inactive with an explicit reason rather than silently dropped.
    assert by_id["financialjuice_rss"].active is True
    for sid in ("deltaone_x", "unusual_whales_x"):
        assert by_id[sid].active is False
        assert "no keyless feed" in by_id[sid].unavailable_reason


async def test_subscriber_receives_new_headlines() -> None:
    watch = await _watch_with({"https://example.com/feed": RSS_FIXTURE}, [SRC])
    received: list[int] = []
    watch.subscribe(lambda batch: received.append(len(batch)))
    await watch.poll_once()
    await watch.poll_once()  # nothing new -> no second callback batch of 3
    assert received == [3]
