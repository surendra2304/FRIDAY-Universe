"""TASK-INT-003: candidate-pool depth for collect_live_brief (no provider calls).

Baseline evidence (2026-11-15, production, fixed six-question set): 59 of
~74 candidate fetches failed (45x HTTP 403) and one question exhausted all
15 candidates with zero sources. The pool is now requested wider (30),
fully iterated, and news.google.com RSS redirector URLs — documented in
TASK-REL-038 as refusing automated fetches — are tried last, never dropped.
"""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

SOURCE = Path(__file__).resolve().parents[1] / "IntelX/intelx/api/live_research_task.py"
spec = importlib.util.spec_from_file_location("live_research_task_int003", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

PROSE = b"Battery capacity is measured and reported in this synthetic source document."


def _doc(url):
    return SimpleNamespace(status_code=200, content_type="text/plain",
                           final_url=url, content=PROSE)


def _candidates(urls):
    return [SimpleNamespace(title="Fixture", url=u) for u in urls]


def test_pool_is_requested_wider_and_fully_iterated():
    # 20 candidates: the first 16 fail, the last 4 succeed. The old pool
    # (request 15, iterate [:15]) could never reach a single success.
    urls = [f"https://example{i}.org/doc" for i in range(20)]
    search = SimpleNamespace(fetch=AsyncMock(return_value=_candidates(urls)))

    async def fetch_side(url, max_bytes=1_000_000):
        idx = int(url.split("example")[1].split(".")[0])
        if idx < 16:
            raise RuntimeError("fixture-403")
        return _doc(url)

    fetch = SimpleNamespace(fetch=AsyncMock(side_effect=fetch_side))
    result = asyncio.run(m.collect_live_brief("battery research", search, fetch))
    assert result["status"] == "SUCCESS"
    assert len(result["sources"]) == 4
    # The wider request is part of the contract: 30 for the default 5 sources.
    assert search.fetch.await_args.kwargs["max_results"] == 30
    # Candidates beyond the old 15-slice were actually attempted.
    assert fetch.fetch.await_count == 20


def test_news_redirectors_are_tried_last_but_never_dropped():
    redirector = "https://news.google.com/rss/articles/FIXTURE"
    direct = "https://example.org/doc"
    search = SimpleNamespace(fetch=AsyncMock(return_value=_candidates([redirector, direct])))
    attempted = []

    async def fetch_side(url, max_bytes=1_000_000):
        attempted.append(url)
        return _doc(url)

    fetch = SimpleNamespace(fetch=AsyncMock(side_effect=fetch_side))
    result = asyncio.run(m.collect_live_brief("battery research", search, fetch, max_sources=1))
    assert result["status"] == "SUCCESS"
    # Direct article URL is attempted first even though search returned the
    # redirector first.
    assert attempted[0] == direct


def test_news_redirector_remains_a_last_resort_when_direct_urls_fail():
    redirector = "https://news.google.com/rss/articles/FIXTURE"
    direct = "https://example.org/doc"
    search = SimpleNamespace(fetch=AsyncMock(return_value=_candidates([direct, redirector])))

    async def fetch_side(url, max_bytes=1_000_000):
        if url == direct:
            raise RuntimeError("fixture-403")
        return _doc(url)

    fetch = SimpleNamespace(fetch=AsyncMock(side_effect=fetch_side))
    result = asyncio.run(m.collect_live_brief("battery research", search, fetch, max_sources=1))
    assert result["status"] == "SUCCESS"
    assert result["sources"][0]["url"] == redirector


def test_duplicate_final_url_does_not_consume_a_source_slot():
    # Two candidate URL variants resolve to the same final document; a
    # third distinct candidate must still fill the second source slot.
    variant_a = "https://example.org/doc?utm_source=fixture"
    variant_b = "https://example.org/doc?ref=fixture"
    distinct = "https://other.org/doc"
    search = SimpleNamespace(fetch=AsyncMock(return_value=_candidates([variant_a, variant_b, distinct])))

    async def fetch_side(url, max_bytes=1_000_000):
        final = distinct if url == distinct else "https://example.org/doc"
        return SimpleNamespace(status_code=200, content_type="text/plain",
                               final_url=final, content=PROSE)

    fetch = SimpleNamespace(fetch=AsyncMock(side_effect=fetch_side))
    result = asyncio.run(m.collect_live_brief("battery research", search, fetch, max_sources=2))
    assert [s["url"] for s in result["sources"]] == ["https://example.org/doc", distinct]
    assert any(f.get("reason") == "duplicate_final_url" for f in result["source_failures"])


def test_max_sources_cap_still_respected_with_wide_pool():
    urls = [f"https://example{i}.org/doc" for i in range(20)]
    search = SimpleNamespace(fetch=AsyncMock(return_value=_candidates(urls)))
    fetch = SimpleNamespace(fetch=AsyncMock(side_effect=lambda url, max_bytes=1_000_000: _doc(url)))
    result = asyncio.run(m.collect_live_brief("battery research", search, fetch, max_sources=2))
    assert len(result["sources"]) == 2
    assert fetch.fetch.await_count == 2
