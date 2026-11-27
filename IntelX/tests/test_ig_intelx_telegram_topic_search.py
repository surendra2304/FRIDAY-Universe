"""Tests for the Telegram topic-search discovery service (TASK-INT-046).

Hermetic: the web-search seam and the preview fetcher are injected fakes;
no live Telegram call is made. Fixture HTML follows the real t.me/s/
preview shape (og meta, tgme_channel_info header, subscriber counter,
tgme_widget_message_text blocks).
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from intelx.api.v1 import osint_tools
from intelx.connectors import telegram_topic_search as tts
from intelx.connectors.named_sources import NAMED_SOURCES, seed_search_url
from intelx.connectors.search import ProviderError, SearchResult, WebSearchConnector
from intelx.core.settings import Settings

PREVIEW_HTML = """<html><head>
<meta property="og:title" content="Quantum Batteries Daily">
<meta property="og:description" content="News and research on quantum batteries and solid-state cells.">
<title>Telegram: View @quantumbatt</title>
</head><body>
<div class="tgme_channel_info_header">
<div class="tgme_channel_info_header_title">Quantum Batteries Daily</div>
<div class="tgme_channel_info_description">News and research on quantum batteries and solid-state cells.</div>
<div class="tgme_channel_info_counter"><span class="counter_value">12 345</span> subscribers</div>
</div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="quantumbatt/101">
<div class="tgme_widget_message_text js-message_text">Solid-state quantum battery cells hit 500 Wh/kg in the lab.</div>
</div></div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="quantumbatt/100">
<div class="tgme_widget_message_text js-message_text">Weekly roundup: sodium-ion news.</div>
</div></div>
</body></html>"""

PREVIEW_OG_ONLY = """<html><head>
<meta property="og:title" content="Solid State Weekly">
<meta property="og:description" content="Solid-state battery news, weekly.">
</head><body><p>no channel header here</p></body></html>"""


# ---------------------------------------------------------------------------
# Query construction + handle extraction
# ---------------------------------------------------------------------------


def test_build_search_query_restricts_to_telegram():
    assert tts.build_search_query("quantum batteries") == "site:t.me quantum batteries"
    assert tts.build_search_query("  solid-state  ") == "site:t.me solid-state"


def test_extract_handles_from_mixed_results():
    results = [
        SearchResult(url="https://t.me/quantumbatt", title="a", snippet=""),
        SearchResult(url="https://t.me/s/solidstateweekly", title="b", snippet=""),
        SearchResult(url="https://t.me/quantumbatt/101", title="c", snippet=""),
        SearchResult(url="https://example.com/not-telegram", title="d", snippet=""),
        SearchResult(url="https://t.me/joinchat/AAAA", title="e", snippet=""),
        SearchResult(url="https://t.me/s/", title="f", snippet=""),
        SearchResult(url="https://t.me/ab", title="g", snippet=""),  # too short for a handle
    ]
    assert tts.extract_handles(results) == ["quantumbatt", "solidstateweekly"]


# ---------------------------------------------------------------------------
# Preview parsing
# ---------------------------------------------------------------------------


def test_parse_channel_preview_full_fixture():
    preview = tts.parse_channel_preview(PREVIEW_HTML, "quantumbatt")
    assert preview.handle == "quantumbatt"
    assert preview.title == "Quantum Batteries Daily"
    assert preview.description == "News and research on quantum batteries and solid-state cells."
    assert preview.subscriber_count == 12345
    assert preview.recent_texts == [
        "Solid-state quantum battery cells hit 500 Wh/kg in the lab.",
        "Weekly roundup: sodium-ion news.",
    ]


def test_parse_channel_preview_og_fallback():
    preview = tts.parse_channel_preview(PREVIEW_OG_ONLY, "solidstateweekly")
    assert preview.title == "Solid State Weekly"
    assert preview.description == "Solid-state battery news, weekly."
    assert preview.subscriber_count is None
    assert preview.recent_texts == []


def test_parse_channel_preview_empty_is_unverified_not_invented():
    preview = tts.parse_channel_preview("<html><body>garbage {{{</body></html>", "nopehandle")
    assert preview.title == ""
    assert preview.description == ""
    assert preview.subscriber_count is None
    assert preview.recent_texts == []


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12 345 subscribers", 12345),
        ("1.2K subscribers", 1200),
        ("2M subscribers", 2_000_000),
        ("987 subscribers", 987),
        ("no count here", None),
        ("", None),
    ],
)
def test_parse_subscriber_count(raw, expected):
    assert tts._parse_subscriber_count(raw) == expected


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def test_score_candidate_ranks_title_over_posts():
    topic = "quantum batteries"
    strong = tts.TelegramPreview(
        handle="quantumbatt",
        title="Quantum Batteries Daily",
        description="News on quantum batteries.",
        subscriber_count=100,
        recent_texts=["Solid-state quantum battery cells hit 500 Wh/kg."],
        fetched_at=tts.datetime.now(tts.UTC),
    )
    weak = tts.TelegramPreview(
        handle="energynews",
        title="Energy News",
        description="General energy news.",
        subscriber_count=999999,
        recent_texts=["A post that mentions quantum once."],
        fetched_at=tts.datetime.now(tts.UTC),
    )
    strong_score, strong_terms = tts.score_candidate(topic, strong)
    weak_score, weak_terms = tts.score_candidate(topic, weak)
    assert strong_score > weak_score  # term matches outweigh the subscriber tiebreak
    assert set(strong_terms) == {"quantum", "batteries"}
    assert weak_terms == ["quantum"]


# ---------------------------------------------------------------------------
# Discovery service (injected fakes)
# ---------------------------------------------------------------------------


class _FakeSearch:
    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.queries: list[str] = []

    async def fetch(self, query, max_results=10):
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        return self.results[:max_results]


class _FakeFetch:
    def __init__(self, pages=None, error_handles=None, status_map=None):
        self.pages = pages or {}
        self.error_handles = set(error_handles or [])
        self.status_map = status_map or {}
        self.urls: list[str] = []

    async def __call__(self, url):
        self.urls.append(url)
        handle = url.rsplit("/", 1)[-1]
        if handle in self.error_handles:
            raise RuntimeError("boom")
        status = self.status_map.get(handle, 200)
        body = self.pages.get(handle, b"")
        return status, url, body


def _result(url, title="t", snippet=""):
    return SearchResult(url=url, title=title, snippet=snippet)


async def test_search_happy_path_ranks_and_proposes():
    search = _FakeSearch(
        results=[
            _result("https://t.me/quantumbatt", snippet="quantum batteries daily"),
            _result("https://example.com/ignore-me"),
            _result("https://t.me/solidstateweekly", snippet="solid state"),
        ]
    )
    fetch = _FakeFetch(pages={"quantumbatt": PREVIEW_HTML.encode(), "solidstateweekly": PREVIEW_OG_ONLY.encode()})
    service = tts.TelegramTopicSearch(search=search, fetch=fetch)
    candidates = await service.search("quantum batteries")
    assert search.queries == ["site:t.me quantum batteries"]
    assert [c.handle for c in candidates] == ["quantumbatt", "solidstateweekly"]
    top = candidates[0]
    assert top.title == "Quantum Batteries Daily"
    assert top.subscriber_count == 12345
    assert top.preview_url == "https://t.me/s/quantumbatt"
    assert top.channel_url == "https://t.me/quantumbatt"
    assert top.score > 0
    assert "quantum" in top.matched_terms and "batteries" in top.matched_terms
    assert top.provenance["search_query"] == "site:t.me quantum batteries"
    assert top.provenance["preview_status"] == 200
    assert top.proposal["inclusion"] == "manual"
    assert top.proposal["suggested_record"]["handle"] == "quantumbatt"


async def test_search_dedupes_handles():
    search = _FakeSearch(
        results=[
            _result("https://t.me/quantumbatt"),
            _result("https://t.me/quantumbatt/101"),
            _result("https://t.me/s/quantumbatt"),
        ]
    )
    fetch = _FakeFetch(pages={"quantumbatt": PREVIEW_HTML.encode()})
    candidates = await tts.TelegramTopicSearch(search=search, fetch=fetch).search("quantum batteries")
    assert [c.handle for c in candidates] == ["quantumbatt"]
    assert len(fetch.urls) == 1  # preview fetched once per handle


async def test_search_fail_closed_on_search_error():
    search = _FakeSearch(error=RuntimeError("search seam down"))
    candidates = await tts.TelegramTopicSearch(search=search, fetch=_FakeFetch()).search("quantum batteries")
    assert candidates == []


async def test_search_fail_closed_on_fetch_error_skips_only_that_handle():
    search = _FakeSearch(
        results=[_result("https://t.me/quantumbatt"), _result("https://t.me/solidstateweekly")]
    )
    fetch = _FakeFetch(
        pages={"solidstateweekly": PREVIEW_OG_ONLY.encode()},
        error_handles={"quantumbatt"},
    )
    candidates = await tts.TelegramTopicSearch(search=search, fetch=fetch).search("quantum batteries")
    assert [c.handle for c in candidates] == ["solidstateweekly"]


async def test_search_fail_closed_on_non200_preview():
    search = _FakeSearch(results=[_result("https://t.me/quantumbatt")])
    fetch = _FakeFetch(pages={"quantumbatt": PREVIEW_HTML.encode()}, status_map={"quantumbatt": 404})
    candidates = await tts.TelegramTopicSearch(search=search, fetch=fetch).search("quantum batteries")
    assert candidates == []


async def test_search_fail_closed_on_unverifiable_preview():
    search = _FakeSearch(results=[_result("https://t.me/ghostchan")])
    fetch = _FakeFetch(pages={"ghostchan": b"<html><body>nothing here</body></html>"})
    candidates = await tts.TelegramTopicSearch(search=search, fetch=fetch).search("quantum batteries")
    assert candidates == []


async def test_search_empty_topic_returns_nothing():
    search = _FakeSearch(results=[_result("https://t.me/quantumbatt")])
    candidates = await tts.TelegramTopicSearch(search=search, fetch=_FakeFetch()).search("   ")
    assert candidates == []
    assert search.queries == []


# ---------------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------------


def test_propose_for_watch_is_manual_with_reason():
    candidate = tts.TelegramCandidateSource(
        handle="quantumbatt",
        title="Quantum Batteries Daily",
        description="News.",
        preview_url="https://t.me/s/quantumbatt",
        channel_url="https://t.me/quantumbatt",
        subscriber_count=12345,
        score=0.8,
        matched_terms=["quantum"],
    )
    proposal = tts.propose_for_watch(candidate)
    assert proposal["inclusion"] == "manual"
    assert "RSS" in proposal["reason"]
    assert proposal["suggested_record"]["kind"] == "telegram_channel"
    assert proposal["suggested_record"]["handle"] == "quantumbatt"


# ---------------------------------------------------------------------------
# Named-source registration
# ---------------------------------------------------------------------------


def test_telegram_public_preview_registered_keyless():
    entry = next(s for s in NAMED_SOURCES if s.name == "Telegram Public Preview")
    assert entry.kind == "api_keyless"
    assert entry.home_url == "https://t.me"
    assert seed_search_url("Telegram Public Preview", "quantumbatt") == "https://t.me/s/quantumbatt"


# ---------------------------------------------------------------------------
# Route (flag-gated)
# ---------------------------------------------------------------------------


async def test_route_flag_off_answers_503(monkeypatch):
    monkeypatch.setattr(
        osint_tools, "get_settings", lambda: SimpleNamespace(ENABLE_TELEGRAM_TOPIC_SEARCH=False)
    )
    with pytest.raises(HTTPException) as excinfo:
        await osint_tools.telegram_topic_search(topic="quantum batteries")
    assert excinfo.value.status_code == 503


async def test_route_flag_on_returns_candidates(monkeypatch):
    monkeypatch.setattr(
        osint_tools, "get_settings", lambda: SimpleNamespace(ENABLE_TELEGRAM_TOPIC_SEARCH=True)
    )

    class _FakeService:
        def __init__(self, *args, **kwargs):
            pass

        async def search(self, topic, max_results=10, max_candidates=10):
            candidate = tts.TelegramCandidateSource(
                handle="quantumbatt",
                title="Quantum Batteries Daily",
                description="News.",
                preview_url="https://t.me/s/quantumbatt",
                channel_url="https://t.me/quantumbatt",
                subscriber_count=12345,
                score=0.9,
                matched_terms=["quantum"],
                proposal={"inclusion": "manual"},
            )
            return [candidate]

    monkeypatch.setattr(tts, "TelegramTopicSearch", _FakeService)
    payload = await osint_tools.telegram_topic_search(topic="quantum batteries")
    assert payload["topic"] == "quantum batteries"
    assert payload["query"] == "site:t.me quantum batteries"
    assert payload["count"] == 1
    assert payload["candidates"][0]["handle"] == "quantumbatt"
    assert payload["candidates"][0]["proposal"]["inclusion"] == "manual"


# ---------------------------------------------------------------------------
# Live mode (TASK-INT-046-FIX-01): the discovery search path never falls
# back to mock fixtures, even when the global MOCK_MODE default is on.
# ---------------------------------------------------------------------------


def _searxng_transport(results):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": results})

    return httpx.MockTransport(handler)


class _FakeNewsEmpty:
    async def fetch(self, target, **kwargs):
        return []


class _FakeWikiEmpty:
    async def fetch(self, target, **kwargs):
        return []


class _FakeDdgDown:
    async def fetch(self, target, **kwargs):
        raise ProviderError(
            "DuckDuckGo search request failed", details={"provider": "duckduckgo"}
        )


async def test_web_search_live_mode_bypasses_mock():
    """live=True runs the real provider chain while MOCK_MODE is on.

    The SearXNG transport is a fake that returns a t.me link; the same
    query without live=True returns the mock fixtures (none for this
    query) and never touches the live chain.
    """
    settings = Settings(
        MOCK_MODE=True,
        SEARXNG_URL="https://searx.example.invalid",
        TAVILY_API_KEY=None,
    )
    live_results = [
        {
            "url": "https://t.me/coinmarketcapannouncements",
            "title": "CoinMarketCap Announcements",
            "content": "crypto news",
        },
    ]
    connector = WebSearchConnector(
        settings=settings, transport=_searxng_transport(live_results)
    )
    connector._google_news = _FakeNewsEmpty()  # hermetic: no real news call
    live = await connector.fetch("site:t.me cryptocurrency", max_results=10, live=True)
    assert [r.url for r in live] == ["https://t.me/coinmarketcapannouncements"]
    assert live[0].title == "CoinMarketCap Announcements"
    # Without live=True the same connector returns mock fixtures (none
    # for this query) — the live SearXNG result is never consulted.
    mocked = await connector.fetch("site:t.me cryptocurrency", max_results=10)
    assert mocked == []


async def test_web_search_live_mode_fail_closed_without_provider():
    """live=True with no provider configured fail-closes, never mocks.

    No Tavily key, no SearXNG URL, Google News + Wikipedia return
    nothing and DuckDuckGo fails: the live chain raises ProviderError.
    The same call without live=True returns the mock fixtures instead
    of raising — that is the bug FIX-01 removes from the live path.
    """
    settings = Settings(MOCK_MODE=True, SEARXNG_URL=None, TAVILY_API_KEY=None)
    connector = WebSearchConnector(settings=settings)
    connector._google_news = _FakeNewsEmpty()
    connector._wikipedia = _FakeWikiEmpty()
    connector._ddg = _FakeDdgDown()
    with pytest.raises(ProviderError):
        await connector.fetch("site:t.me cryptocurrency", max_results=10, live=True)
    mocked = await connector.fetch("site:t.me cryptocurrency", max_results=10)
    assert mocked == []


async def test_default_search_uses_live_mode(monkeypatch):
    """TelegramTopicSearch's default search passes live=True."""
    calls: list[dict] = []

    class _RecordingSearch:
        def __init__(self, *args, **kwargs):
            pass

        async def fetch(self, query, max_results=10, **kwargs):
            calls.append({"query": query, "max_results": max_results, **kwargs})
            return []

    monkeypatch.setattr(
        "intelx.connectors.search.WebSearchConnector", _RecordingSearch
    )
    service = tts.TelegramTopicSearch()
    await service._default_search("site:t.me cryptocurrency", 10)
    assert calls == [
        {"query": "site:t.me cryptocurrency", "max_results": 10, "live": True}
    ]
