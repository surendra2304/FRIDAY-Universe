"""Tests for the IG wiring of the standing feeds (package item X-07).

HeadlineWatch (TASK-IG-INT-01) and AiRadar (TASK-IG2-INT-05) shipped as
libraries with no production consumer. These tests exercise the actual
consumer paths added by the wiring — the /api/v1/feeds routes over the
shared feed_service instances, the lifespan scheduler hooks, and the
StrateX delivery subscriber — not just the libraries. Hermetic: all
network fetches are fakes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from intelx.app.factory import create_app
from intelx.ingestion import feed_service
from intelx.ingestion.headline_watch import (
    DEFAULT_SOURCES,
    Headline,
    HeadlineSource,
    HeadlineWatch,
    ImpactAssessment,
)
from intelx.integrations.stratex_context import StratexConnector

UTC = timezone.utc

RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test Wire</title>
<item><title>FinancialJuice: Fed cuts rates by 25bp in emergency meeting</title>
<link>https://example.com/fed</link><pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Local bakery wins regional bread award</title>
<link>https://example.com/bakery</link><pubDate>Mon, 16 Nov 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""

SRC = HeadlineSource(source_id="t_rss", name="Test RSS", kind="rss", url="https://example.com/feed")


@pytest.fixture(autouse=True)
def _reset_feed_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feed_service, "_headline_watch", None)
    monkeypatch.setattr(feed_service, "_ai_radar", None)
    monkeypatch.setattr(feed_service, "_delivery_attached", False)


async def _fake_fetch(url: str) -> str:
    return RSS_FIXTURE


def _client() -> AsyncClient:
    app = create_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# X-02: First Squawk registration
# ---------------------------------------------------------------------------


def test_first_squawk_registered_inactive_with_reason() -> None:
    by_id = {s.source_id: s for s in DEFAULT_SOURCES}
    squawk = by_id["first_squawk_x"]
    assert squawk.kind == "x_account"
    assert squawk.handle == "FirstSquawk"
    # No keyless X feed exists; the source registers inactive and honest,
    # exactly like the three accounts named in the original video.
    assert squawk.active is False
    assert squawk.unavailable_reason
    # The accounts the baseline under-enumerated stay registered.
    assert by_id["unusual_whales_x"].handle == "unusual_whales"
    assert by_id["financialjuice_x"].handle == "financialjuice"
    assert by_id["deltaone_x"].handle == "Deltaone"


# ---------------------------------------------------------------------------
# TASK-INT-045: First Squawk free-route verdict
# ---------------------------------------------------------------------------


def test_first_squawk_no_free_route_verdict() -> None:
    """The INT-045 verdict is recorded on the source, not just in a doc.

    Probed first-hand 2026-11-25 (evidence doc
    docs/collaboration/TASK-INT-045.md): no free route carries First Squawk
    headlines — no site feed, dead blog RSS, paid-only products, no official
    Telegram channel, dead X mirrors, paid-only X API. The source stays
    registered inactive with the dated verdict as its reason, so the watch
    reports WHY it is unavailable and never invents its headlines.
    """
    from intelx.ingestion.headline_watch import FIRST_SQUAWK_NO_FREE_ROUTE

    by_id = {s.source_id: s for s in DEFAULT_SOURCES}
    squawk = by_id["first_squawk_x"]
    assert squawk.active is False
    assert squawk.kind == "x_account"
    assert squawk.handle == "FirstSquawk"
    assert squawk.unavailable_reason == FIRST_SQUAWK_NO_FREE_ROUTE
    # The verdict names the probe date and every route that was checked.
    assert "2026-11-25" in squawk.unavailable_reason
    assert "TASK-INT-045" in squawk.unavailable_reason
    for route in (
        "firstsquawk.com",
        "blog/feed",
        "2019-03-28",
        "Telegram",
        "FAKE",
        "nitter",
        "xcancel",
        "X API",
        "TASK-INT-045.md",
    ):
        assert route in squawk.unavailable_reason, route


def test_first_squawk_stays_out_of_active_polls() -> None:
    """An inactive source never yields headlines, even with a fake fetch."""
    watch = HeadlineWatch(fetch_text=_fake_fetch)
    fresh = asyncio.run(watch.poll_once())
    assert all(h.source_id != "first_squawk_x" for h in fresh)
    assert watch.status["first_squawk_x"].active is False


# ---------------------------------------------------------------------------
# Consumer path: /api/v1/feeds routes over the shared instances
# ---------------------------------------------------------------------------


async def test_headline_routes_serve_the_shared_watch(monkeypatch: pytest.MonkeyPatch) -> None:
    watch = HeadlineWatch(sources=[SRC], fetch_text=_fake_fetch)
    monkeypatch.setattr(feed_service, "_headline_watch", watch)

    async with _client() as client:
        poll = await client.post("/api/v1/feeds/headlines/poll")
        assert poll.status_code == 200
        assert poll.json()["new"] == 2

        feed = await client.get("/api/v1/feeds/headlines")
        assert feed.status_code == 200
        titles = [h["title"] for h in feed.json()["headlines"]]
        assert any("Fed cuts rates" in t for t in titles)

        # The impact floor is honoured by the consumer query: only the
        # market-moving headline survives a high floor.
        floored = await client.get("/api/v1/feeds/headlines", params={"min_score": 90})
        assert floored.json()["count"] == 1
        assert "Fed cuts rates" in floored.json()["headlines"][0]["title"]

        sources = await client.get("/api/v1/feeds/headlines/sources")
        assert sources.status_code == 200
        report = {s["source_id"]: s for s in sources.json()["sources"]}
        assert report["t_rss"]["headlines_new"] == 2


async def test_ai_radar_route_returns_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    from intelx.ingestion.ai_radar import AiRadar

    radar = AiRadar(fetch_text=_fake_fetch)
    monkeypatch.setattr(feed_service, "_ai_radar", radar)

    async with _client() as client:
        resp = await client.get("/api/v1/feeds/ai-radar")
        assert resp.status_code == 200
        body = resp.json()
        assert "trending" in body and "source_status" in body
        status_ids = {s["source_id"] for s in body["source_status"]}
        assert "arxiv_cs_ai" in status_ids

        poll = await client.post("/api/v1/feeds/ai-radar/poll")
        assert poll.status_code == 200
        # Every radar source is fed the same 2-item fixture; fingerprints
        # are per-source, so all of them land as new buffer items.
        assert poll.json()["new_items"] >= 2
        assert poll.json()["digest"]["items_buffered"] == poll.json()["new_items"]


# ---------------------------------------------------------------------------
# Consumer path: lifespan scheduler hooks drive the shared instances
# ---------------------------------------------------------------------------


async def test_headline_hook_polls_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    from intelx.app import lifespan as lifespan_mod

    polls = 0

    class _CountingWatch:
        async def poll_once(self) -> list:
            nonlocal polls
            polls += 1
            return []

    monkeypatch.setattr(feed_service, "get_headline_watch", lambda: _CountingWatch())
    monkeypatch.setattr(
        lifespan_mod,
        "get_settings",
        lambda: SimpleNamespace(HEADLINE_WATCH_INTERVAL_S=0.01, AI_RADAR_INTERVAL_S=0.01),
    )

    hook = lifespan_mod.HeadlineWatchHook()
    await hook.start()
    await asyncio.sleep(0.055)
    await hook.stop()
    await hook.stop()  # stop is idempotent
    assert polls >= 2


async def test_ai_radar_hook_polls_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    from intelx.app import lifespan as lifespan_mod

    polls = 0

    class _CountingRadar:
        async def poll_once(self) -> list:
            nonlocal polls
            polls += 1
            return []

    monkeypatch.setattr(feed_service, "get_ai_radar", lambda: _CountingRadar())
    monkeypatch.setattr(
        lifespan_mod,
        "get_settings",
        lambda: SimpleNamespace(HEADLINE_WATCH_INTERVAL_S=0.01, AI_RADAR_INTERVAL_S=0.01),
    )

    hook = lifespan_mod.AiRadarHook()
    await hook.start()
    await asyncio.sleep(0.055)
    await hook.stop()
    assert polls >= 2


# ---------------------------------------------------------------------------
# Consumer path: StrateX delivery subscriber
# ---------------------------------------------------------------------------


def _headline(title: str, score: int, fingerprint: str) -> Headline:
    return Headline(
        source_id="t_rss",
        source_name="Test RSS",
        title=title,
        url="https://example.com/x",
        published_at=None,
        fetched_at=datetime.now(UTC),
        fingerprint=fingerprint,
        impact=ImpactAssessment(
            score=score, tier="high" if score >= 50 else "low",
            assets=(), direction="neutral", matched_phrases=(),
        ),
    )


async def test_delivery_forwards_only_above_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    async def _fake_notify(**kwargs) -> dict:
        sent.append(kwargs)
        return {"status": "delivered"}

    monkeypatch.setattr(StratexConnector, "notify_stratex_trade_signal", _fake_notify)
    monkeypatch.setattr(
        feed_service,
        "get_settings",
        lambda: SimpleNamespace(HEADLINE_STRATEX_MIN_SCORE=50, HEADLINE_STRATEX_DELIVERY=True),
    )

    hot = _headline("Fed cuts rates by 25bp", 90, "fp-hot-0123456789abcdef")
    cold = _headline("Local bakery wins award", 10, "fp-cold-0123456789abcdef")
    results = await feed_service.deliver_headlines_to_stratex([hot, cold])

    assert [r["fingerprint"] for r in results] == ["fp-hot-0123456789abcdef"]
    assert results[0]["status"] == "delivered"
    assert len(sent) == 1
    assert sent[0]["domain"] == "market_headlines"
    assert "Fed cuts rates" in sent[0]["finding_text"]
    assert sent[0]["confidence"] == pytest.approx(0.9)


async def test_delivery_failure_is_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(**kwargs) -> dict:
        raise RuntimeError("stratex down")

    monkeypatch.setattr(StratexConnector, "notify_stratex_trade_signal", _boom)
    monkeypatch.setattr(
        feed_service,
        "get_settings",
        lambda: SimpleNamespace(HEADLINE_STRATEX_MIN_SCORE=0, HEADLINE_STRATEX_DELIVERY=True),
    )
    results = await feed_service.deliver_headlines_to_stratex(
        [_headline("Fed cuts rates", 90, "fp-err-0123456789abcdef")]
    )
    assert results == [{"fingerprint": "fp-err-0123456789abcdef", "status": "error"}]
