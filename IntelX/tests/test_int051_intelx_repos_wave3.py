"""Tests for TASK-INT-051 — IntelX repos wave 3.

Agent Reach (adapt), Camofox Browser (adapt), Local Deep Research
(adapt), Helix (adapt), Robin (adapt), OpenDirectory Finder (reject).

Hermetic: every fetch is injected or faked; no network, no live keys.
Route tests use the conftest ``client`` fixture (ASGI transport) with
the same monkeypatch-at-the-module-seam pattern as
test_ig_intelx_wiring_consumers.py.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from intelx.agents.deep_research_loop import IterativeDeepResearcher
from intelx.agents.research_engines import (
    MultiEngineSearch,
    arxiv_engine,
    build_default_search,
    pubmed_engine,
    semantic_scholar_engine,
)
from intelx.agents.retriever import RetrieverAgent
from intelx.agents.scout import SourceCandidate
from intelx.api.v1 import osint_tools
from intelx.connectors.agent_reach import (
    AgentReachReader,
    AgentReachUnavailable,
    classify_reach_url,
)
from intelx.connectors.camofox_macros import (
    CamofoxMacroRunner,
    build_search_url,
    parse_transcript_json3,
    parse_transcript_xml,
    youtube_transcript_url,
)
from intelx.connectors.search import SearchResult
from intelx.connectors.social_links import SocialLinkDocument, SocialLinkUnavailable
from intelx.connectors.web import FetchResult
from intelx.ingestion.investigation_store import InvestigationStore
from intelx.ingestion.untrusted_ingest import run_investigation
from intelx.osint.helix_lookup import HelixHit, HelixReport
from intelx.osint.helix_watch import HelixWatchStore, diff_helix_reports
from intelx.osint.username import PLATFORMS

UTC = UTC

# ---------------------------------------------------------------------------
# Registry pins (the board verdicts for this task)
# ---------------------------------------------------------------------------


def test_registry_verdicts_for_wave3() -> None:
    from intelx.scouted_repos import by_agent, by_repo

    assert [e["repo"] for e in by_agent("IntelX")] == [
        "Panniantong/Agent-Reach",
        "jo-inc/camofox-browser",
        "LearningCircuit/local-deep-research",
        "thalha-a9/helix",
        "ewasion/opendirectory-finder",
        "apurvsinghgautam/robin",
    ]
    assert by_repo("Panniantong/Agent-Reach")["fit"] == "adapt"
    assert by_repo("jo-inc/camofox-browser")["fit"] == "adapt"
    assert by_repo("LearningCircuit/local-deep-research")["fit"] == "adapt"
    assert by_repo("thalha-a9/helix")["fit"] == "adapt"
    assert by_repo("apurvsinghgautam/robin")["fit"] == "adapt"
    assert by_repo("ewasion/opendirectory-finder")["fit"] == "reject"


# ---------------------------------------------------------------------------
# Fake fetch (Agent Reach)
# ---------------------------------------------------------------------------


class FakeFetch:
    """routes: substring -> (status, body). Records every URL fetched."""

    def __init__(self, routes: dict[str, tuple[int, bytes]]) -> None:
        self.routes = routes
        self.urls: list[str] = []

    async def __call__(self, url: str) -> tuple[int, str, bytes]:
        self.urls.append(url)
        for key, (status, body) in self.routes.items():
            if key in url:
                return status, url, body
        return 404, url, b""


GITHUB_REPO_JSON = json.dumps(
    {
        "full_name": "octocat/Hello-World",
        "description": "My first repository on GitHub!",
        "stargazers_count": 42,
        "language": "Python",
        "license": {"name": "MIT License"},
        "default_branch": "main",
        "html_url": "https://github.com/octocat/Hello-World",
        "homepage": "",
    }
).encode()

RSS_FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<title>Example Feed</title>
<item><title>First post</title><link>https://example.com/1</link>
<description>hello <b>world</b></description></item>
<item><title>Second post</title><link>https://example.com/2</link>
<description>second post body</description></item>
</channel></rss>"""

ATOM_FEED = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Feed</title>
<entry><title>Entry one</title><link href="https://example.com/a"/>
<summary>atom summary text</summary></entry></feed>"""

V2EX_JSON = json.dumps(
    [
        {
            "id": 123,
            "title": "Hello V2EX",
            "content": "topic body text",
            "member": {"username": "alice"},
            "node": {"title": "Python"},
        }
    ]
).encode()

BILIBILI_JSON = json.dumps(
    {
        "code": 0,
        "data": {
            "title": "Test video",
            "desc": "video description",
            "owner": {"name": "creator"},
            "stat": {"view": 100, "like": 5},
            "duration": 120,
        },
    }
).encode()


def test_classify_reach_url_channels() -> None:
    assert classify_reach_url("https://github.com/octocat/Hello-World") == "github"
    assert classify_reach_url("https://raw.githubusercontent.com/o/r/main/f.txt") == "github"
    assert classify_reach_url("https://example.com/feed.xml") == "rss"
    assert classify_reach_url("https://example.com/blog/rss") == "rss"
    assert classify_reach_url("https://www.v2ex.com/t/123456") == "v2ex"
    assert classify_reach_url("https://www.bilibili.com/video/BV1xx411c7mD") == "bilibili"
    assert classify_reach_url("https://x.com/someone") == "login_gated"
    assert classify_reach_url("https://www.linkedin.com/in/someone") == "login_gated"
    assert classify_reach_url("https://www.facebook.com/someone") == "login_gated"
    assert classify_reach_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "unsupported"
    assert classify_reach_url("https://example.com/article") == "unsupported"
    assert classify_reach_url("ftp://example.com/file") == "unsupported"


async def test_agent_reach_github_repo() -> None:
    fetch = FakeFetch({"api.github.com/repos/octocat/Hello-World": (200, GITHUB_REPO_JSON)})
    doc = await AgentReachReader(fetch=fetch).read("https://github.com/octocat/Hello-World")
    assert doc.platform == "github"
    assert doc.title == "octocat/Hello-World"
    assert doc.author == "octocat"
    assert "My first repository" in doc.text
    assert "Stars: 42" in doc.text
    assert doc.extraction_method == "github_api_repo"
    assert fetch.urls == ["https://api.github.com/repos/octocat/Hello-World"]


async def test_agent_reach_github_repo_not_found_and_rate_limited() -> None:
    missing = FakeFetch({"api.github.com": (404, b"{}")})
    with pytest.raises(AgentReachUnavailable, match="not found"):
        await AgentReachReader(fetch=missing).read("https://github.com/octocat/Nope")
    limited = FakeFetch({"api.github.com": (403, b"{}")})
    with pytest.raises(AgentReachUnavailable, match="rate limit"):
        await AgentReachReader(fetch=limited).read("https://github.com/octocat/Hello-World")


async def test_agent_reach_github_raw_file() -> None:
    fetch = FakeFetch({"raw.githubusercontent.com": (200, b"print('hello')\n")})
    doc = await AgentReachReader(fetch=fetch).read(
        "https://github.com/octocat/Hello-World/blob/main/hello.py"
    )
    assert doc.platform == "github"
    assert doc.extraction_method == "github_raw_file"
    assert doc.text == "print('hello')\n"
    assert "raw.githubusercontent.com/octocat/Hello-World/main/hello.py" in fetch.urls[0]


async def test_agent_reach_rss_and_atom() -> None:
    fetch = FakeFetch({"example.com/feed.xml": (200, RSS_FEED)})
    doc = await AgentReachReader(fetch=fetch).read("https://example.com/feed.xml")
    assert doc.platform == "rss"
    assert doc.title == "Example Feed"
    assert "First post — https://example.com/1" in doc.text
    assert "hello world" in doc.text  # tags stripped, entities unescaped
    assert "Second post" in doc.text

    atom = FakeFetch({"example.com/atom.xml": (200, ATOM_FEED)})
    doc = await AgentReachReader(fetch=atom).read("https://example.com/atom.xml")
    assert doc.title == "Atom Feed"
    assert "Entry one — https://example.com/a" in doc.text
    assert "atom summary text" in doc.text


async def test_agent_reach_rss_unparseable_is_unavailable() -> None:
    fetch = FakeFetch({"example.com/feed.xml": (200, b"<html>not a feed</html>")})
    with pytest.raises(AgentReachUnavailable):
        await AgentReachReader(fetch=fetch).read("https://example.com/feed.xml")


async def test_agent_reach_v2ex_and_bilibili() -> None:
    fetch = FakeFetch(
        {
            "v2ex.com/api/topics/show.json": (200, V2EX_JSON),
            "api.bilibili.com": (200, BILIBILI_JSON),
        }
    )
    reader = AgentReachReader(fetch=fetch)
    v2ex = await reader.read("https://www.v2ex.com/t/123")
    assert v2ex.platform == "v2ex"
    assert v2ex.author == "alice"
    assert v2ex.title == "Hello V2EX"
    assert "topic body text" in v2ex.text
    bili = await reader.read("https://www.bilibili.com/video/BV1xx411c7mD")
    assert bili.platform == "bilibili"
    assert bili.author == "creator"
    assert bili.title == "Test video"
    assert "Views: 100" in bili.text


async def test_agent_reach_refuses_login_gated_before_any_fetch() -> None:
    fetch = FakeFetch({})
    with pytest.raises(AgentReachUnavailable, match="login-gated"):
        await AgentReachReader(fetch=fetch).read("https://x.com/someone")
    assert fetch.urls == []  # gate fires before any network traffic
    with pytest.raises(AgentReachUnavailable, match="no Agent Reach"):
        await AgentReachReader(fetch=fetch).read("https://example.com/article")
    assert fetch.urls == []


# ---------------------------------------------------------------------------
# Camofox macros + transcripts
# ---------------------------------------------------------------------------


def test_build_search_url_known_sites() -> None:
    assert build_search_url("github", "helix osint") == (
        "https://github.com/search?q=helix+osint&type=repositories"
    )
    assert build_search_url("arxiv", "solid state battery") == (
        "https://arxiv.org/search/?query=solid+state+battery&searchtype=all"
    )
    assert build_search_url("pubmed", "lockbit") == (
        "https://pubmed.ncbi.nlm.nih.gov/?term=lockbit"
    )
    with pytest.raises(ValueError, match="unknown search-macro site"):
        build_search_url("myspace", "hello")
    with pytest.raises(ValueError, match="must not be empty"):
        build_search_url("github", "   ")
    with pytest.raises(ValueError, match="over 500"):
        build_search_url("github", "x" * 501)


def test_youtube_transcript_url_validation() -> None:
    assert youtube_transcript_url("dQw4w9WgXcQ") == (
        "https://www.youtube.com/api/timedtext?v=dQw4w9WgXcQ&lang=en&fmt=json3"
    )
    with pytest.raises(ValueError, match="invalid YouTube video id"):
        youtube_transcript_url("not a video id!!")


def test_parse_transcript_json3_and_xml() -> None:
    payload = {
        "events": [
            {"segs": [{"utf8": "hello "}, {"utf8": "world"}]},
            {"segs": [{"utf8": "second line"}]},
            {"segs": []},
        ]
    }
    assert parse_transcript_json3(payload) == "hello world\nsecond line"
    with pytest.raises(ValueError, match="no events"):
        parse_transcript_json3({"wireMagic": "x"})
    xml = b'<?xml version="1.0"?><transcript><text start="0">hello world</text></transcript>'
    assert parse_transcript_xml(xml) == "hello world"
    with pytest.raises(ValueError, match="not parseable"):
        parse_transcript_xml(b"not xml at all")


async def test_macro_runner_uses_injected_snapshot() -> None:
    seen: list[str] = []

    async def fake_snapshot(url: str) -> tuple[str, str]:
        seen.append(url)
        return url, "snapshot body text"

    runner = CamofoxMacroRunner(fetch_snapshot=fake_snapshot)
    result = await runner.run_macro("github", "helix osint")
    assert result.site == "github"
    assert result.search_url == "https://github.com/search?q=helix+osint&type=repositories"
    assert result.snapshot_text == "snapshot body text"
    assert seen == [result.search_url]
    assert result.to_dict()["site"] == "github"


async def test_macro_runner_transcript() -> None:
    json3 = json.dumps({"events": [{"segs": [{"utf8": "caption one "}, {"utf8": "two"}]}]}).encode()
    fetch = FakeFetch({"timedtext": (200, json3)})
    runner = CamofoxMacroRunner(fetch_bytes=fetch)
    assert await runner.fetch_transcript("dQw4w9WgXcQ") == "caption one two"
    empty = FakeFetch({"timedtext": (200, b"")})
    assert await CamofoxMacroRunner(fetch_bytes=empty).fetch_transcript("dQw4w9WgXcQ") == ""
    missing = FakeFetch({"timedtext": (404, b"")})
    with pytest.raises(RuntimeError, match="not found"):
        await CamofoxMacroRunner(fetch_bytes=missing).fetch_transcript("dQw4w9WgXcQ")


async def test_camofox_client_macro_and_transcript() -> None:
    from intelx.connectors.browser_sidecar import CamofoxClient, SidecarConfig

    opened: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)
        if request.method == "POST" and path == "/tabs":
            opened.append(json.loads(request.content.decode())["url"])
            return httpx.Response(200, json={"tabId": "tab-1"})
        if request.method == "GET" and path == "/tabs/tab-1/snapshot":
            return httpx.Response(200, json={"snapshot": "macro snapshot", "url": opened[0]})
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        if "timedtext" in str(request.url):
            return httpx.Response(
                200,
                json={"events": [{"segs": [{"utf8": "client caption"}]}]},
            )
        return httpx.Response(404, json={})

    client = CamofoxClient(SidecarConfig(), transport=httpx.MockTransport(handler))
    final_url, snapshot = await client.fetch_macro("wikipedia", "helix")
    assert opened == ["https://en.wikipedia.org/w/index.php?search=helix"]
    assert final_url == opened[0]
    assert snapshot == "macro snapshot"
    assert await client.fetch_transcript("dQw4w9WgXcQ") == "client caption"


# ---------------------------------------------------------------------------
# Multi-engine research routing (Local Deep Research)
# ---------------------------------------------------------------------------


def _result(url: str, title: str = "t", snippet: str = "s") -> SearchResult:
    return SearchResult(url=url, title=title, snippet=snippet)


async def _engine(results: list[SearchResult], fail: bool = False):
    async def search(query: str, n: int) -> list[SearchResult]:
        if fail:
            raise RuntimeError("engine down")
        return list(results[:n])

    return search


async def test_multi_engine_merges_and_dedupes() -> None:
    router = MultiEngineSearch(
        engines={
            "arxiv": await _engine([_result("https://arxiv.org/abs/1", "Paper A", "dendrite")]),
            "web": await _engine(
                [
                    _result("https://arxiv.org/abs/1/", "Paper A dup", "dendrite"),
                    _result("https://example.com/b?utm_source=x", "Page B", "battery"),
                ]
            ),
        }
    )
    detailed = await router.search_detailed("dendrite battery")
    assert len(detailed.results) == 2  # arxiv dup + utm variant deduped
    assert detailed.per_engine == {"arxiv": 1, "web": 1}
    assert detailed.errors == {}
    assert [r.url for r in detailed.results] == [
        "https://arxiv.org/abs/1",
        "https://example.com/b?utm_source=x",
    ]


async def test_multi_engine_isolates_a_dead_engine() -> None:
    router = MultiEngineSearch(
        engines={
            "arxiv": await _engine([], fail=True),
            "pubmed": await _engine([_result("https://pubmed.ncbi.nlm.nih.gov/1/")]),
        }
    )
    detailed = await router.search_detailed("lockbit")
    assert len(detailed.results) == 1
    assert "arxiv" in detailed.errors
    assert "engine down" in detailed.errors["arxiv"]
    assert detailed.per_engine["arxiv"] == 0
    assert detailed.per_engine["pubmed"] == 1


async def test_multi_engine_caps_and_timeout() -> None:
    async def slow(query: str, n: int) -> list[SearchResult]:
        import asyncio

        await asyncio.sleep(5)
        return [_result("https://slow.example/")]

    router = MultiEngineSearch(
        engines={
            "slow": slow,
            "fast": await _engine([_result(f"https://example.com/{i}") for i in range(5)]),
        },
        timeout_s=0.1,
        max_total=2,
    )
    detailed = await router.search_detailed("battery")
    assert "slow" in detailed.errors  # timed out, recorded, run survived
    assert len(detailed.results) == 2  # max_total cap
    with pytest.raises(ValueError, match="must not be empty"):
        await router.search_detailed("   ")


async def test_multi_engine_fetch_is_loop_drop_in() -> None:
    router = MultiEngineSearch(
        engines={
            "web": await _engine(
                [
                    SearchResult(
                        url="https://arxiv.org/abs/1234.5678",
                        title="Solid state battery dendrite suppression study",
                        snippet="solid state battery dendrite suppression evidence",
                    ),
                    SearchResult(
                        url="https://www.nature.com/articles/s41586-001",
                        title="Dendrite suppression in solid state battery cells",
                        snippet="battery dendrite suppression measurements and evidence",
                    ),
                    SearchResult(
                        url="https://pinterest.com/pin/1",
                        title="cute phone cases",
                        snippet="shop cute cases now",
                    ),
                ]
            )
        }
    )
    researcher = IterativeDeepResearcher(router.fetch, min_sources_per_item=2, max_rounds=2)
    result = await researcher.research(
        "battery research",
        plan_items=["solid state battery dendrite suppression evidence"],
    )
    assert result.stop_reason == "coverage_complete"
    assert len(result.sources) == 2
    assert all("pinterest" not in s.url for s in result.sources)


def test_build_default_search_has_four_engines() -> None:
    router = build_default_search()
    assert set(router.engines) == {"arxiv", "pubmed", "semantic_scholar", "web"}


ARXIV_ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>  Dendrite suppression\nstudy </title>
<summary>Evidence from cycling experiments.</summary>
<link href="https://arxiv.org/abs/1234.5678" rel="alternate" type="text/html"/>
</entry></feed>"""

PUBMED_ESEARCH = {"esearchresult": {"idlist": ["123", "456"]}}
PUBMED_ESUMMARY = {
    "result": {
        "123": {"title": "First paper", "fulljournalname": "Nature"},
        "456": {"title": "Second paper", "fulljournalname": "Science"},
    }
}
SEMANTIC_SCHOLAR_JSON = {
    "data": [
        {
            "title": "Scholar paper",
            "abstract": "abstract text",
            "url": "https://www.semanticscholar.org/paper/abc",
        }
    ]
}


async def test_real_engine_parsers_against_canned_payloads() -> None:
    def arxiv_handler(request: httpx.Request) -> httpx.Response:
        assert "export.arxiv.org" in str(request.url)
        return httpx.Response(200, content=ARXIV_ATOM)

    arxiv = await arxiv_engine(transport=httpx.MockTransport(arxiv_handler))("dendrite", 5)
    assert len(arxiv) == 1
    assert arxiv[0].url == "https://arxiv.org/abs/1234.5678"
    assert arxiv[0].title == "Dendrite suppression study"
    assert arxiv[0].snippet == "Evidence from cycling experiments."

    def pubmed_handler(request: httpx.Request) -> httpx.Response:
        if "esearch.fcgi" in str(request.url):
            return httpx.Response(200, json=PUBMED_ESEARCH)
        return httpx.Response(200, json=PUBMED_ESUMMARY)

    pubmed = await pubmed_engine(transport=httpx.MockTransport(pubmed_handler))("lockbit", 5)
    assert [p.url for p in pubmed] == [
        "https://pubmed.ncbi.nlm.nih.gov/123/",
        "https://pubmed.ncbi.nlm.nih.gov/456/",
    ]
    assert pubmed[0].snippet == "Nature"

    def scholar_handler(request: httpx.Request) -> httpx.Response:
        assert "api.semanticscholar.org" in str(request.url)
        return httpx.Response(200, json=SEMANTIC_SCHOLAR_JSON)

    scholar = await semantic_scholar_engine(transport=httpx.MockTransport(scholar_handler))(
        "battery", 5
    )
    assert len(scholar) == 1
    assert scholar[0].title == "Scholar paper"


# ---------------------------------------------------------------------------
# Helix watch history
# ---------------------------------------------------------------------------


def _report(username: str, hits: list[tuple[str, str]], discarded: list[str] | None = None):
    return HelixReport(
        username=username,
        control_username="hxctl0000000000zz",
        sites_checked=len(PLATFORMS),
        hits=[
            HelixHit(platform=p, profile_url=f"https://example.com/{p}", confidence=c)
            for p, c in hits
        ],
        discarded=[
            {"platform": p, "profile_url": "", "reason": "control probe also found"}
            for p in (discarded or [])
        ],
    )


def test_helix_watch_first_seen_and_diff() -> None:
    store = HelixWatchStore()
    first = _report("alice", [("GitHub", "LOW")])
    diff = store.diff("alice", first)
    assert diff["first_seen"] is True
    assert diff["added_platforms"] == ["GitHub"]
    store.record(first)

    second = _report("alice", [("GitHub", "MEDIUM"), ("Keybase", "LOW")], discarded=["Reddit"])
    diff = store.diff("alice", second)
    assert diff["first_seen"] is False
    assert diff["added_platforms"] == ["Keybase"]
    assert diff["removed_platforms"] == []
    assert diff["confidence_changes"] == [
        {"platform": "GitHub", "old_confidence": "LOW", "new_confidence": "MEDIUM"}
    ]
    assert diff["newly_discarded"] == ["Reddit"]
    assert diff["overall_confidence"] == {"old": "LOW", "new": "MEDIUM"}
    store.record(second)
    assert len(store.history("alice")) == 2
    assert store.last("alice")["report"]["username"] == "alice"
    assert store.history("nobody") == []
    assert store.last("nobody") is None

    removed = _report("alice", [("Keybase", "LOW")])
    diff = store.diff("alice", removed)
    assert diff["removed_platforms"] == ["GitHub"]
    assert diff["no_longer_discarded"] == ["Reddit"]


def test_diff_helix_reports_on_dicts() -> None:
    old = _report("bob", [("GitHub", "LOW")]).to_dict()
    new = _report("bob", [("GitHub", "LOW")]).to_dict()
    assert diff_helix_reports(old, new)["added_platforms"] == []
    assert diff_helix_reports(old, new)["confidence_changes"] == []


# ---------------------------------------------------------------------------
# Robin investigation store: save / follow-up / pivots
# ---------------------------------------------------------------------------


async def _lockbit_search(query: str) -> list[dict]:
    return [
        {
            "title": "LockBit reporting",
            "url": "https://example.com/1",
            "snippet": "lockbit affiliate news",
        }
    ]


async def _lockbit_fetch(url: str) -> str:
    return "lockbit affiliate activity observed in the wild"


async def _saved_result() -> tuple[InvestigationStore, str]:
    store = InvestigationStore()
    result = await run_investigation(
        "lockbit affiliate activity", search=_lockbit_search, fetch=_lockbit_fetch
    )
    return store, store.save(result)


async def test_investigation_store_save_get_pivots() -> None:
    store, investigation_id = await _saved_result()
    assert investigation_id.startswith("inv-")
    saved = store.get(investigation_id)
    assert saved is not None
    assert saved.evidence[0].url == "https://example.com/1"
    assert store.get("inv-doesnotexist") is None
    pivots = store.pivots(investigation_id)
    assert pivots  # refine_query derives pivots from the key terms
    assert any("lockbit" in p for p in pivots)
    with pytest.raises(KeyError):
        store.pivots("inv-doesnotexist")


async def test_investigation_store_follow_up_is_grounded() -> None:
    store, investigation_id = await _saved_result()
    follow_up = await store.follow_up(
        investigation_id,
        "lockbit affiliates latest",
        search=_lockbit_search,
        fetch=_lockbit_fetch,
    )
    assert follow_up.saved_id == investigation_id
    assert len(follow_up.result.evidence) == 1
    assert len(follow_up.grounded_in) == 1  # saved evidence shares "lockbit"
    assert follow_up.grounded_in[0].url == "https://example.com/1"
    assert follow_up.to_dict()["grounded_in"][0]["url"] == "https://example.com/1"
    with pytest.raises(KeyError):
        await store.follow_up("inv-doesnotexist", "x", search=_lockbit_search, fetch=_lockbit_fetch)
    with pytest.raises(ValueError, match="must not be empty"):
        await store.follow_up(investigation_id, "   ", search=_lockbit_search, fetch=_lockbit_fetch)


# ---------------------------------------------------------------------------
# OpenDirectory Finder (reject): guardrail proof of absence
# ---------------------------------------------------------------------------


def test_opendirectory_finder_is_rejected_and_absent() -> None:
    from intelx.scouted_repos import by_repo

    assert by_repo("ewasion/opendirectory-finder")["fit"] == "reject"
    # No module, route, import or fetch of it anywhere in the IntelX
    # package — the rejection is a guardrail, not a paper judgement.
    package = Path(__file__).resolve().parent.parent / "intelx"
    hits = []
    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        if "opendirectory" in text or "filechef" in text:
            hits.append(str(path))
    assert hits == []
    import importlib.util

    assert importlib.util.find_spec("intelx.opendirectory_finder") is None


# ---------------------------------------------------------------------------
# Retriever seam: Agent Reach in the real fetch path
# ---------------------------------------------------------------------------


class _FakeHttpConnector:
    """Returns canned bytes per URL substring; records every fetch."""

    def __init__(self, routes: dict[str, tuple[int, bytes]]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    async def fetch(self, location: str) -> FetchResult:
        self.calls.append(location)
        for key, (status, body) in self.routes.items():
            if key in location:
                return FetchResult(
                    url=location,
                    final_url=location,
                    content=body,
                    content_type="application/json",
                    status_code=status,
                    robots_ok=True,
                )
        return FetchResult(
            url=location,
            final_url=location,
            content=b"",
            content_type="text/html",
            status_code=404,
            robots_ok=True,
        )


async def test_retriever_uses_agent_reach_for_github() -> None:
    http = _FakeHttpConnector({"api.github.com/repos/octocat/Hello-World": (200, GITHUB_REPO_JSON)})
    agent = RetrieverAgent(http_connector=http)
    candidate = SourceCandidate(
        location="https://github.com/octocat/Hello-World",
        title="Hello-World",
        reason="test",
    )
    plan = await agent._social_ingest_plan(candidate, candidate.location, "github.com")
    assert plan is not None
    assert plan.content_type == "text/plain; format=agent-reach"
    assert b"My first repository" in plan.raw_bytes
    assert plan.title == "octocat/Hello-World"
    assert http.calls == ["https://api.github.com/repos/octocat/Hello-World"]


async def test_retriever_ignores_reach_for_plain_web() -> None:
    http = _FakeHttpConnector({})
    agent = RetrieverAgent(http_connector=http)
    candidate = SourceCandidate(
        location="https://example.com/article", title="Article", reason="test"
    )
    plan = await agent._social_ingest_plan(candidate, candidate.location, "example.com")
    assert plan is None
    assert http.calls == []  # reach reader refuses before any fetch


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _reach_doc(url: str) -> SocialLinkDocument:
    return SocialLinkDocument(
        platform="github",
        url=url,
        canonical_url=url,
        author="octocat",
        title="octocat/Hello-World",
        text="My first repository on GitHub!",
        fetched_at=datetime.now(UTC),
        extraction_method="github_api_repo",
        media_kind="repository",
    )


class _BlockedSocialReader:
    def __init__(self, fetch=None) -> None:
        pass

    async def read(self, url: str) -> SocialLinkDocument:
        raise SocialLinkUnavailable(url, "login-gated")


class _GoodReachReader:
    def __init__(self, fetch=None) -> None:
        pass

    async def read(self, url: str) -> SocialLinkDocument:
        return _reach_doc(url)


class _BlockedReachReader:
    def __init__(self, fetch=None) -> None:
        pass

    async def read(self, url: str) -> SocialLinkDocument:
        raise AgentReachUnavailable(url, "no Agent Reach no-login channel covers this URL")


async def test_social_link_route_falls_back_to_agent_reach(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import intelx.connectors.agent_reach as reach_mod
    import intelx.connectors.social_links as social_mod

    monkeypatch.setattr(social_mod, "SocialLinkReader", _BlockedSocialReader)
    monkeypatch.setattr(reach_mod, "AgentReachReader", _GoodReachReader)
    resp = await client.get(
        "/api/v1/osint/social-link",
        params={"url": "https://github.com/octocat/Hello-World"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["platform"] == "github"
    assert body["title"] == "octocat/Hello-World"

    monkeypatch.setattr(reach_mod, "AgentReachReader", _BlockedReachReader)
    blocked = await client.get(
        "/api/v1/osint/social-link",
        params={"url": "https://github.com/octocat/Hello-World"},
    )
    assert blocked.status_code == 422
    assert "login-gated" in blocked.json()["detail"]
    assert "Agent Reach" in blocked.json()["detail"]


async def test_username_lookup_route_gate_and_mock_mode(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INTELX_HELIX_APPROVED_SUBJECTS", "alice")
    denied = await client.post("/api/v1/osint/username-lookup", json={"username": "mallory"})
    assert denied.status_code == 403
    # conftest runs with INTELX_MOCK_MODE=true: approved subjects still 503.
    refused = await client.post("/api/v1/osint/username-lookup", json={"username": "alice"})
    assert refused.status_code == 503
    history_denied = await client.get("/api/v1/osint/username-lookup/mallory/history")
    assert history_denied.status_code == 403


async def test_username_lookup_route_happy_path_and_watch(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from intelx.core.settings import get_settings

    monkeypatch.setenv("INTELX_MOCK_MODE", "false")
    monkeypatch.setenv("INTELX_HELIX_APPROVED_SUBJECTS", "int051watch")
    get_settings.cache_clear()
    reports = [
        _report("int051watch", [("GitHub", "LOW")]),
        _report("int051watch", [("GitHub", "MEDIUM"), ("Keybase", "LOW")]),
    ]
    calls = {"n": 0}

    async def fake_lookup(username, *, approved_subjects, **kwargs):
        assert username in approved_subjects
        report = reports[calls["n"]]
        calls["n"] += 1
        return report

    # NOTE: patch via sys.modules — `intelx.osint.__init__` re-exports the
    # `helix_lookup` function, so attribute traversal of
    # `intelx.osint.helix_lookup` lands on the function, not the module.
    import sys

    monkeypatch.setattr(sys.modules["intelx.osint.helix_lookup"], "helix_lookup", fake_lookup)
    first = await client.post("/api/v1/osint/username-lookup", json={"username": "int051watch"})
    assert first.status_code == 200
    assert first.json()["changes_since_last"]["first_seen"] is True
    second = await client.post("/api/v1/osint/username-lookup", json={"username": "int051watch"})
    assert second.status_code == 200
    changes = second.json()["changes_since_last"]
    assert changes["first_seen"] is False
    assert changes["added_platforms"] == ["Keybase"]
    assert changes["confidence_changes"][0]["platform"] == "GitHub"
    history = await client.get("/api/v1/osint/username-lookup/int051watch/history")
    assert history.status_code == 200
    assert len(history.json()["snapshots"]) == 2


async def test_investigation_routes_save_and_follow_up(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from intelx.core.settings import get_settings

    monkeypatch.setenv("INTELX_MOCK_MODE", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(osint_tools, "_investigation_search", _lockbit_search)
    monkeypatch.setattr(osint_tools, "_investigation_fetch", _lockbit_fetch)

    created = await client.post(
        "/api/v1/research/investigations", json={"query": "lockbit affiliate activity"}
    )
    assert created.status_code == 200
    body = created.json()
    assert body["evidence_count"] == 1
    investigation_id = body["id"]
    assert investigation_id.startswith("inv-")

    saved = await client.get(f"/api/v1/research/investigations/{investigation_id}")
    assert saved.status_code == 200
    assert saved.json()["evidence_count"] == 1
    assert saved.json()["pivot_queries"]

    missing = await client.get("/api/v1/research/investigations/inv-doesnotexist")
    assert missing.status_code == 404

    follow_up = await client.post(
        f"/api/v1/research/investigations/{investigation_id}/follow-up",
        json={"question": "lockbit affiliates latest"},
    )
    assert follow_up.status_code == 200
    follow_body = follow_up.json()
    assert follow_body["saved_id"] == investigation_id
    assert len(follow_body["grounded_in"]) == 1
    assert follow_body["result"]["evidence_count"] == 1

    missing_follow_up = await client.post(
        "/api/v1/research/investigations/inv-doesnotexist/follow-up",
        json={"question": "lockbit affiliates latest"},
    )
    assert missing_follow_up.status_code == 404
