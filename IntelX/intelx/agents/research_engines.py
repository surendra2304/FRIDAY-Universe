"""INTELX — Multi-engine research routing (TASK-INT-051).

Adapts the Local Deep Research pattern (LearningCircuit/local-deep-research,
MIT) that TASK-IG2-INT-02 left as a single-provider loop: the upstream tool
searches 10+ engines (web/SearXNG, arXiv, PubMed, Semantic Scholar, plus
private documents) and synthesises a cited report. IntelX's loop already
does the search -> grade -> follow-up -> cited-synthesis shape; what it
lacked was the multi-engine fan-out. This module is that fan-out:

  * ``arxiv_engine`` / ``pubmed_engine`` / ``semantic_scholar_engine`` —
    the three public, no-key scholarly APIs (arXiv Atom API, PubMed
    E-utilities, Semantic Scholar Graph API). Each takes an optional
    ``httpx`` transport so tests run hermetically.
  * ``web_engine`` — delegates to IntelX's existing ``WebSearchConnector``
    (Tavily / SearXNG / Google News / Wikipedia / DuckDuckGo), i.e. the
    web leg the loop already used, now as one engine among several.
  * ``MultiEngineSearch`` — fans one query out to every configured engine
    concurrently, isolates per-engine failures (one dead engine never
    kills the run), dedupes by normalised URL, caps per-engine and total
    results, and returns ``SearchResult`` lists the loop consumes
    unchanged. ``fetch`` is drop-in for ``IterativeDeepResearcher``'s
    search callable; ``search_detailed`` reports the per-engine counts
    and errors for observability.

Deliberately NOT adapted from the upstream stack: no Ollama/local LLM
(the fleet has no GPU and the upstream benchmark needs a 3090-class
card), no self-hosted SearXNG instance (the loop already routes to the
configured one), no SQLCipher knowledge library (IntelX's canonical
store is the library), and no resident web/DB app — this is a library
call inside the existing loop, not a service.
"""

from __future__ import annotations

import asyncio
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from intelx.connectors.search import SearchResult

logger = logging.getLogger("intelx.research_engines")

EngineFn = Callable[[str, int], Awaitable[list[SearchResult]]]

_DEFAULT_TIMEOUT_S = 20.0
_DEFAULT_PER_ENGINE = 5
_DEFAULT_MAX_TOTAL = 15
_ARXIV_NS = "{http://www.w3.org/2005/Atom}"
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def _normalise_url(url: str) -> str:
    """Dedupe key: lowercase host, no trailing slash, no tracking params."""
    parsed = urllib.parse.urlsplit((url or "").strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    kept = [(k, v) for k, v in query if k.lower() not in _TRACKING_PARAMS]
    rebuilt = urllib.parse.urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            urllib.parse.urlencode(kept),
            "",
        )
    )
    return rebuilt


def _clean(text: str | None, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()[:limit]


# ---------------------------------------------------------------------------
# Engines (public, no-key APIs)
# ---------------------------------------------------------------------------


def arxiv_engine(transport: httpx.AsyncBaseTransport | None = None) -> EngineFn:
    """arXiv Atom API: ``export.arxiv.org/api/query``."""

    async def search(query: str, max_results: int) -> list[SearchResult]:
        params = {
            "search_query": f"all:{query}",
            "start": "0",
            "max_results": str(max(1, max_results)),
        }
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            resp = await client.get(url, headers={"Accept": "application/atom+xml"})
        resp.raise_for_status()
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as exc:
            raise ValueError(f"arXiv returned unparseable Atom: {exc}") from exc
        out: list[SearchResult] = []
        for entry in root.findall(f"{_ARXIV_NS}entry"):
            title = _clean((entry.findtext(f"{_ARXIV_NS}title") or ""), 200)
            summary = _clean(entry.findtext(f"{_ARXIV_NS}summary") or "")
            link = ""
            for link_el in entry.findall(f"{_ARXIV_NS}link"):
                if link_el.get("rel") in (None, "alternate") and link_el.get("href"):
                    link = str(link_el.get("href"))
                    break
            if link and title:
                out.append(SearchResult(url=link, title=title, snippet=summary))
        return out

    return search


def pubmed_engine(transport: httpx.AsyncBaseTransport | None = None) -> EngineFn:
    """PubMed E-utilities: esearch (ids) then esummary (titles). No key."""

    async def search(query: str, max_results: int) -> list[SearchResult]:
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        search_url = (
            base
            + "/esearch.fcgi?"
            + urllib.parse.urlencode(
                {
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retmax": str(max(1, max_results)),
                }
            )
        )
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            resp = await client.get(search_url)
            resp.raise_for_status()
            ids = resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []
            summary_url = (
                base
                + "/esummary.fcgi?"
                + urllib.parse.urlencode(
                    {"db": "pubmed", "id": ",".join(str(i) for i in ids), "retmode": "json"}
                )
            )
            summary = await client.get(summary_url)
            summary.raise_for_status()
            docs = summary.json().get("result", {})
        out: list[SearchResult] = []
        for pmid in ids:
            doc = docs.get(str(pmid))
            if not isinstance(doc, dict):
                continue
            title = _clean(str(doc.get("title") or ""), 200)
            if not title:
                continue
            journal = _clean(str(doc.get("fulljournalname") or ""), 120)
            snippet = journal or "PubMed record"
            out.append(
                SearchResult(
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    title=title,
                    snippet=snippet,
                )
            )
        return out

    return search


def semantic_scholar_engine(transport: httpx.AsyncBaseTransport | None = None) -> EngineFn:
    """Semantic Scholar Graph API paper search. No key."""

    async def search(query: str, max_results: int) -> list[SearchResult]:
        url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(
            {"query": query, "fields": "title,abstract,url", "limit": str(max(1, max_results))}
        )
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError as exc:
            raise ValueError(f"Semantic Scholar returned unparseable JSON: {exc}") from exc
        out: list[SearchResult] = []
        for paper in data.get("data", []) if isinstance(data, dict) else []:
            if not isinstance(paper, dict):
                continue
            title = _clean(str(paper.get("title") or ""), 200)
            paper_url = str(paper.get("url") or "")
            if not title or not paper_url:
                continue
            out.append(
                SearchResult(
                    url=paper_url,
                    title=title,
                    snippet=_clean(str(paper.get("abstract") or "")),
                )
            )
        return out

    return search


def web_engine(connector=None) -> EngineFn:
    """IntelX's existing web search router as one engine among several."""

    async def search(query: str, max_results: int) -> list[SearchResult]:
        from intelx.connectors.search import WebSearchConnector

        target = connector or WebSearchConnector()
        return list(await target.fetch(query, max_results=max_results))

    return search


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@dataclass
class MultiEngineResult:
    """One fanned-out search: merged results plus per-engine accounting."""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    per_engine: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "result_count": len(self.results),
            "per_engine": dict(self.per_engine),
            "errors": dict(self.errors),
            "results": [
                {"url": r.url, "title": r.title, "snippet": r.snippet} for r in self.results
            ],
        }


class MultiEngineSearch:
    """Fan one query out to several search engines; merge, dedupe, cap.

    ``fetch`` returns a plain ``list[SearchResult]`` and is drop-in for
    ``IterativeDeepResearcher``'s search callable. ``search_detailed``
    returns the same results with per-engine counts and errors.
    """

    def __init__(
        self,
        engines: dict[str, EngineFn] | None = None,
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        max_results_per_engine: int = _DEFAULT_PER_ENGINE,
        max_total: int = _DEFAULT_MAX_TOTAL,
    ) -> None:
        if max_results_per_engine < 1 or max_total < 1:
            raise ValueError("engine result caps must be positive")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._engines = engines
        self.timeout_s = timeout_s
        self.max_results_per_engine = max_results_per_engine
        self.max_total = max_total

    @property
    def engines(self) -> dict[str, EngineFn]:
        if self._engines is None:
            self._engines = {
                "arxiv": arxiv_engine(),
                "pubmed": pubmed_engine(),
                "semantic_scholar": semantic_scholar_engine(),
                "web": web_engine(),
            }
        return self._engines

    async def search_detailed(
        self, query: str, *, max_results_per_engine: int | None = None
    ) -> MultiEngineResult:
        cleaned = " ".join((query or "").split())
        if not cleaned:
            raise ValueError("research query must not be empty")
        per_engine_cap = max_results_per_engine or self.max_results_per_engine
        result = MultiEngineResult(query=cleaned)

        async def run_one(
            name: str, fn: EngineFn
        ) -> tuple[str, list[SearchResult] | None, str | None]:
            try:
                found = await asyncio.wait_for(fn(cleaned, per_engine_cap), self.timeout_s)
                return name, list(found)[:per_engine_cap], None
            except Exception as exc:  # one dead engine never kills the run
                logger.warning("research engine %s failed: %s", name, exc)
                return name, None, f"{type(exc).__name__}: {exc}"

        gathered = await asyncio.gather(*(run_one(name, fn) for name, fn in self.engines.items()))
        seen: set[str] = set()
        for name, found, error in gathered:
            if error is not None:
                result.errors[name] = error
                result.per_engine[name] = 0
                continue
            kept = 0
            for item in found or []:
                key = _normalise_url(item.url)
                if not key or key in seen:
                    continue
                seen.add(key)
                if len(result.results) >= self.max_total:
                    break
                result.results.append(item)
                kept += 1
            result.per_engine[name] = kept
        return result

    async def fetch(self, query: str, **kwargs) -> list[SearchResult]:
        """Loop-compatible search: ``query`` -> merged, deduped results."""
        cap = kwargs.get("max_results_per_engine")
        detailed = await self.search_detailed(query, max_results_per_engine=cap)
        return detailed.results


def build_default_search(
    *,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
    max_results_per_engine: int = _DEFAULT_PER_ENGINE,
    max_total: int = _DEFAULT_MAX_TOTAL,
) -> MultiEngineSearch:
    """Default router: arXiv + PubMed + Semantic Scholar + IntelX web search."""
    return MultiEngineSearch(
        timeout_s=timeout_s,
        max_results_per_engine=max_results_per_engine,
        max_total=max_total,
    )


__all__ = [
    "MultiEngineResult",
    "MultiEngineSearch",
    "arxiv_engine",
    "build_default_search",
    "pubmed_engine",
    "semantic_scholar_engine",
    "web_engine",
]
