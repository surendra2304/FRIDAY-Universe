"""TASK-REL-007: WebSearchConnector must merge Google News article
candidates with Tavily results instead of returning Tavily alone.

Production failure: IntelX research_live for headline queries returned
DEGRADED 'sourced_findings_unverified'. Tavily answered 200, but its top
candidates for "today's top AI news headlines" were section/listing pages
that the grounded pipeline correctly refuses to certify as sources, and
the connector never consulted Google News RSS (article-level URLs) when
Tavily returned anything. These tests pin the merge contract.
"""

import pytest

from intelx.connectors.search import SearchResult, WebSearchConnector
from intelx.core.settings import Settings


class _StaticProvider:
    def __init__(self, results):
        self._results = results

    async def fetch(self, target, **kwargs):
        return list(self._results)


class _BrokenProvider:
    async def fetch(self, target, **kwargs):
        raise RuntimeError("provider down")


def _result(url, title="t"):
    return SearchResult(url=url, title=title, snippet="snippet")


def _connector(monkeypatch, tavily, news):
    searcher = WebSearchConnector(
        settings=Settings(MOCK_MODE=False, TAVILY_API_KEY="<redacted>", SEARXNG_URL=None)
    )
    monkeypatch.setattr(searcher, "_tavily", _StaticProvider(tavily))
    monkeypatch.setattr(searcher, "_google_news", _StaticProvider(news) if news is not None else _BrokenProvider())
    return searcher


@pytest.mark.asyncio
async def test_tavily_results_are_merged_with_google_news_articles(monkeypatch):
    tavily = [
        _result("https://example.com/tag/ai", "Section page"),
        _result("https://example.com/topic/ai", "Topic page"),
    ]
    news = [
        _result("https://publisher.example/story-1", "Article one"),
        _result("https://publisher.example/story-2", "Article two"),
    ]
    searcher = _connector(monkeypatch, tavily, news)

    results = await searcher.fetch("today top AI news headlines", max_results=10)

    urls = [r.url for r in results]
    # Primary provider still leads the merged list.
    assert urls[0] == "https://example.com/tag/ai"
    # Article-level candidates are now present for the research pipeline.
    assert "https://publisher.example/story-1" in urls
    assert "https://publisher.example/story-2" in urls
    assert "https://example.com/topic/ai" in urls


@pytest.mark.asyncio
async def test_merge_dedupes_by_url_and_caps_at_max_results(monkeypatch):
    shared = "https://shared.example/story"
    tavily = [_result(shared), _result("https://a.example/1"), _result("https://a.example/2")]
    news = [_result(shared), _result("https://b.example/1"), _result("https://b.example/2")]
    searcher = _connector(monkeypatch, tavily, news)

    results = await searcher.fetch("headlines", max_results=4)

    urls = [r.url for r in results]
    assert len(urls) == 4
    assert len(set(urls)) == 4
    assert urls.count(shared) == 1


@pytest.mark.asyncio
async def test_google_news_failure_falls_back_to_tavily_alone(monkeypatch):
    tavily = [_result("https://example.com/tag/ai")]
    searcher = _connector(monkeypatch, tavily, None)

    results = await searcher.fetch("headlines", max_results=10)

    assert [r.url for r in results] == ["https://example.com/tag/ai"]


@pytest.mark.asyncio
async def test_google_news_empty_falls_back_to_tavily_alone(monkeypatch):
    tavily = [_result("https://example.com/tag/ai")]
    searcher = _connector(monkeypatch, tavily, [])

    results = await searcher.fetch("headlines", max_results=10)

    assert [r.url for r in results] == ["https://example.com/tag/ai"]
