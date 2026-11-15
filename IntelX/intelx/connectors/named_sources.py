"""Named research/archive source utilities (TASK-IG-INT-05).

Implements the corpus item DZ7MtMhjAZI ("secret websites" roundup): five
named research/archive utilities, each registered with its REAL access
method — no fake APIs are invented for sites that do not offer one:

  * **Internet Archive (archive.org)** — a WORKING keyless connector:
    advancedsearch + metadata APIs (verified live 2026-11-15). Unknown
    identifiers return ``{}`` from the metadata API and are reported as
    not-found, never dressed up.
  * **WolframAlpha** — real API, but it requires an AppID. The adapter
    fails closed with a clear ``NamedSourceUnavailable`` naming the missing
    ``WOLFRAMALPHA_APPID`` env var when unconfigured.
  * **OpenCulture, AlternativeTo, JustWatch** — no public API exists.
    Registered as seed-site sources: the canonical search URL pattern a
    researcher (or the generic web fetch/search connectors) starts from.
    The registry says exactly that; nothing pretends to query them
    programmatically.

Python 3.10 compatible. Fetchers injectable for hermetic tests.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import quote, urlencode

logger = logging.getLogger("intelx.named_sources")

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]  # (status, final_url, body)


class NamedSourceUnavailable(RuntimeError):
    """A named source cannot be used; the message says exactly why."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NamedSource:
    name: str
    kind: str  # api_keyless | api_keyed | seed_site
    home_url: str
    access_note: str
    search_url_template: str = ""  # contains {q} for seed sites

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "home_url": self.home_url,
            "access_note": self.access_note,
            "search_url_template": self.search_url_template,
        }


NAMED_SOURCES: tuple[NamedSource, ...] = (
    NamedSource(
        name="Internet Archive",
        kind="api_keyless",
        home_url="https://archive.org",
        access_note="Working connector in this module: advancedsearch + metadata APIs, no key required.",
        search_url_template="https://archive.org/search?query={q}",
    ),
    NamedSource(
        name="WolframAlpha",
        kind="api_keyed",
        home_url="https://www.wolframalpha.com",
        access_note="Real API; requires WOLFRAMALPHA_APPID. Adapter fails closed when the key is absent.",
        search_url_template="https://www.wolframalpha.com/input?i={q}",
    ),
    NamedSource(
        name="OpenCulture",
        kind="seed_site",
        home_url="https://www.openculture.com",
        access_note="No public API. Curated free-course/media catalogue; use the site search URL as a seed for web fetch/search.",
        search_url_template="https://www.openculture.com/search-results?q={q}",
    ),
    NamedSource(
        name="AlternativeTo",
        kind="seed_site",
        home_url="https://alternativeto.net",
        access_note="No public API. Software-alternatives catalogue; use the site search URL as a seed for web fetch/search.",
        search_url_template="https://alternativeto.net/browse/search/?q={q}",
    ),
    NamedSource(
        name="JustWatch",
        kind="seed_site",
        home_url="https://www.justwatch.com",
        access_note="No public API (partner API is commercial). Streaming-availability catalogue; use the site search URL as a seed.",
        search_url_template="https://www.justwatch.com/in/search?q={q}",
    ),
)


def seed_search_url(source_name: str, query: str) -> str:
    """Build the canonical search URL for any registered named source."""
    for source in NAMED_SOURCES:
        if source.name.lower() == source_name.lower():
            if not source.search_url_template:
                raise NamedSourceUnavailable(f"{source.name} has no search URL pattern registered")
            return source.search_url_template.format(q=quote(query))
    raise NamedSourceUnavailable(f"unknown named source {source_name!r}")


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


# ---------------------------------------------------------------------------
# Internet Archive — working keyless connector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArchiveItem:
    identifier: str
    title: str
    creator: str
    date: str
    mediatype: str
    item_url: str

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "creator": self.creator,
            "date": self.date,
            "mediatype": self.mediatype,
            "item_url": self.item_url,
        }


@dataclass(frozen=True)
class ArchiveMetadata:
    identifier: str
    title: str
    description: str
    creator: str
    item_url: str
    files: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "identifier": self.identifier,
            "title": self.title,
            "description": self.description,
            "creator": self.creator,
            "item_url": self.item_url,
            "files": self.files,
        }


class ArchiveOrgClient:
    """Search + metadata against archive.org's public APIs (keyless)."""

    def __init__(self, fetch: FetchBytes | None = None) -> None:
        self._fetch = fetch or _default_fetch

    async def search(self, query: str, rows: int = 10) -> list[ArchiveItem]:
        params = urlencode(
            [
                ("q", query),
                ("fl[]", "identifier"),
                ("fl[]", "title"),
                ("fl[]", "creator"),
                ("fl[]", "date"),
                ("fl[]", "mediatype"),
                ("rows", str(max(1, min(rows, 50)))),
                ("output", "json"),
            ]
        )
        status, _, body = await self._fetch(f"https://archive.org/advancedsearch.php?{params}")
        if status != 200:
            raise NamedSourceUnavailable(f"archive.org advancedsearch returned HTTP {status}")
        payload = json.loads(body.decode("utf-8", errors="replace"))
        docs = (payload.get("response") or {}).get("docs") or []
        return [
            ArchiveItem(
                identifier=str(d.get("identifier", "")),
                title=str(d.get("title", "")),
                creator=str(d.get("creator", "")),
                date=str(d.get("date", "")),
                mediatype=str(d.get("mediatype", "")),
                item_url=f"https://archive.org/details/{d.get('identifier', '')}",
            )
            for d in docs
            if d.get("identifier")
        ]

    async def metadata(self, identifier: str) -> ArchiveMetadata | None:
        """Return item metadata, or None when archive.org has no such item
        (the API answers ``{}`` for unknown identifiers — verified live)."""
        status, _, body = await self._fetch(f"https://archive.org/metadata/{quote(identifier, safe='')}")
        if status != 200:
            raise NamedSourceUnavailable(f"archive.org metadata returned HTTP {status}")
        payload = json.loads(body.decode("utf-8", errors="replace"))
        if not payload:
            return None
        meta = payload.get("metadata") or {}
        files = [
            {"name": str(f.get("name", "")), "format": str(f.get("format", "")), "size": str(f.get("size", ""))}
            for f in payload.get("files") or []
        ]
        return ArchiveMetadata(
            identifier=str(meta.get("identifier", identifier)),
            title=str(meta.get("title", "")),
            description=str(meta.get("description", "")),
            creator=str(meta.get("creator", "")),
            item_url=f"https://archive.org/details/{meta.get('identifier', identifier)}",
            files=files,
        )


# ---------------------------------------------------------------------------
# WolframAlpha — keyed adapter, fails closed
# ---------------------------------------------------------------------------


class WolframAlphaClient:
    """WolframAlpha query adapter. Requires WOLFRAMALPHA_APPID."""

    def __init__(self, appid: str | None = None, fetch: FetchBytes | None = None) -> None:
        self._appid = appid if appid is not None else os.environ.get("WOLFRAMALPHA_APPID", "")
        self._fetch = fetch or _default_fetch

    @property
    def configured(self) -> bool:
        return bool(self._appid)

    async def query(self, question: str) -> list[dict]:
        """Return result pods as {title, plaintext} dicts (verbatim output)."""
        if not self.configured:
            raise NamedSourceUnavailable(
                "WolframAlpha requires an AppID: set WOLFRAMALPHA_APPID to use this source. "
                "No result was fabricated in its place."
            )
        params = urlencode({"input": question, "appid": self._appid, "output": "json", "format": "plaintext"})
        status, _, body = await self._fetch(f"https://api.wolframalpha.com/v2/query?{params}")
        if status != 200:
            raise NamedSourceUnavailable(f"WolframAlpha API returned HTTP {status}")
        payload = json.loads(body.decode("utf-8", errors="replace"))
        pods = ((payload.get("queryresult") or {}).get("pods")) or []
        results: list[dict] = []
        for pod in pods:
            texts = [
                str(sub.get("plaintext", ""))
                for sub in pod.get("subpods") or []
                if sub.get("plaintext")
            ]
            if texts:
                results.append({"title": str(pod.get("title", "")), "plaintext": "\n".join(texts)})
        return results


__all__ = [
    "NAMED_SOURCES",
    "ArchiveItem",
    "ArchiveMetadata",
    "ArchiveOrgClient",
    "NamedSource",
    "NamedSourceUnavailable",
    "WolframAlphaClient",
    "seed_search_url",
]
