"""Tests for TASK-IG2-INT-05 — IntelX AI-trending Radar feed (cluster #45).

Hermetic: feed fetching is injected. Pins: dedupe across polls, a term
needs >=2 mentions to trend, cross-source terms outrank single-source
ones, a failing source is reported (never silently filled), and term
extraction drops stopwords.
"""
from __future__ import annotations

from datetime import datetime, timezone

from intelx.ingestion.ai_radar import AiRadar, extract_terms
from intelx.ingestion.headline_watch import HeadlineSource

UTC = timezone.utc
NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)

SRC_A = HeadlineSource(source_id="a", name="A", kind="rss", url="https://a.example/feed")
SRC_B = HeadlineSource(source_id="b", name="B", kind="rss", url="https://b.example/feed")

FEED_A = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>A</title>
<item><title>Vector database startup raises funding for retrieval</title>
<link>https://a.example/1</link><pubDate>Mon, 16 Nov 2026 11:00:00 GMT</pubDate></item>
<item><title>New benchmark for vector database retrieval quality</title>
<link>https://a.example/2</link><pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""

FEED_B = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>B</title>
<item><title>Vector database goes open source</title>
<link>https://b.example/1</link><pubDate>Mon, 16 Nov 2026 11:30:00 GMT</pubDate></item>
<item><title>Local bakery wins regional bread award</title>
<link>https://b.example/2</link><pubDate>Mon, 16 Nov 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""


def _fetch(mapping: dict[str, str]):
    async def fetch(url: str) -> str:
        if url not in mapping:
            raise RuntimeError("feed down")
        return mapping[url]

    return fetch


async def test_radar_trends_cross_source_topic_first():
    radar = AiRadar(sources=[SRC_A, SRC_B], fetch_text=_fetch({SRC_A.url: FEED_A, SRC_B.url: FEED_B}))
    fresh = await radar.poll_once(now=NOW)
    assert len(fresh) == 4
    topics = radar.trending(now=NOW)
    assert topics, "expected at least one trending topic"
    top = topics[0]
    assert top.term == "vector database"
    assert top.mentions == 3
    assert set(top.sources) == {"a", "b"}
    assert len(top.examples) == 3
    # single-mention topics never trend
    assert all(t.mentions >= 2 for t in topics)
    assert "bakery" not in {t.term for t in topics}


async def test_radar_dedupes_across_polls():
    radar = AiRadar(sources=[SRC_A], fetch_text=_fetch({SRC_A.url: FEED_A}))
    first = await radar.poll_once(now=NOW)
    second = await radar.poll_once(now=NOW)
    assert len(first) == 2
    assert second == []
    assert radar.digest(now=NOW)["items_buffered"] == 2


async def test_failed_source_is_reported_not_filled():
    radar = AiRadar(sources=[SRC_A, SRC_B], fetch_text=_fetch({SRC_A.url: FEED_A}))
    await radar.poll_once(now=NOW)
    digest = radar.digest(now=NOW)
    status = {s["source_id"]: s for s in digest["source_status"]}
    assert status["b"]["last_error"]  # failure is on the record
    assert status["b"]["items_seen"] == 0
    assert status["a"]["items_seen"] == 2


def test_extract_terms_drops_stopwords_and_builds_bigrams():
    terms = extract_terms("The new model for vector search")
    assert "the" not in terms and "new" not in terms and "model" not in terms
    assert "vector" in terms and "vector search" in terms
