"""INTELX — Camofox search macros + transcript fetch (TASK-INT-051).

Extends the camofox-browser sidecar (TASK-IG2-INT-01,
``connectors/browser_sidecar.py``) with the two upstream features the
sidecar ships but IntelX never exposed:

  * **Search macros** — camofox-browser offers search macros for common
    sites: a named site plus a query builds the site's search URL, which
    the sidecar then opens in a tab and snapshots. ``build_search_url``
    is the pure URL builder; ``CamofoxMacroRunner`` runs a macro through
    an injected snapshot callable (in production,
    ``CamofoxClient.fetch_snapshot``); ``CamofoxClient.fetch_macro`` is
    the same path bound to a live client.
  * **YouTube transcripts** — camofox-browser extracts YouTube
    transcripts via yt-dlp. IntelX does the same read without the
    binary: the public, no-login ``timedtext`` endpoint serves captions
    for public videos. ``fetch_transcript`` parses the JSON3 form
    (``fmt=json3``) and falls back to the plain XML form.

Macros never bypass IntelX's fetch policy: a macro URL is still fetched
through the sidecar (robots + domain policy + SSRF checks live in the
sidecar connector), and a transcript fetch goes through the hardened
``HttpFetchConnector``. No login, no key, no browser state is smuggled
in — a macro is only a URL template.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable
from urllib.parse import quote_plus

logger = logging.getLogger("intelx.camofox_macros")

UTC = timezone.utc

_MAX_QUERY_CHARS = 500
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")

# Site -> search URL template. Templates are the sites' own public search
# endpoints; ``{q}`` is the URL-encoded query. Keep the list to sites
# IntelX research actually uses — a macro is a shortcut, not a directory.
SEARCH_MACROS: dict[str, str] = {
    "youtube": "https://www.youtube.com/results?search_query={q}",
    "github": "https://github.com/search?q={q}&type=repositories",
    "reddit": "https://www.reddit.com/search/?q={q}",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search={q}",
    "arxiv": "https://arxiv.org/search/?query={q}&searchtype=all",
    "stackoverflow": "https://stackoverflow.com/search?q={q}",
    "hackernews": "https://hn.algolia.com/?q={q}",
    "pubmed": "https://pubmed.ncbi.nlm.nih.gov/?term={q}",
    "semantic_scholar": "https://www.semanticscholar.org/search?q={q}",
}


def build_search_url(site: str, query: str) -> str:
    """Build a site's search URL for ``query``.

    Raises :class:`ValueError` for an unknown site, an empty query, or a
    query over 500 characters (a macro is a search shortcut, not a pastebin).
    """
    template = SEARCH_MACROS.get((site or "").lower())
    if template is None:
        raise ValueError(
            f"unknown search-macro site {site!r}; known sites: {', '.join(sorted(SEARCH_MACROS))}"
        )
    cleaned = " ".join((query or "").split())
    if not cleaned:
        raise ValueError("search-macro query must not be empty")
    if len(cleaned) > _MAX_QUERY_CHARS:
        raise ValueError(f"search-macro query over {_MAX_QUERY_CHARS} characters")
    return template.format(q=quote_plus(cleaned))


def youtube_transcript_url(video_id: str) -> str:
    """Public no-login timedtext URL for a YouTube video's English captions."""
    if not _VIDEO_ID_RE.match(video_id or ""):
        raise ValueError(f"invalid YouTube video id {video_id!r}")
    return f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en&fmt=json3"


def parse_transcript_json3(payload: dict) -> str:
    """Extract plain caption text from a timedtext ``fmt=json3`` payload."""
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        raise ValueError("transcript payload has no events list")
    lines: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        parts = []
        for seg in event.get("segs") or []:
            if isinstance(seg, dict) and isinstance(seg.get("utf8"), str):
                parts.append(seg["utf8"])
        text = "".join(parts).replace("\n", " ").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def parse_transcript_xml(body: bytes) -> str:
    """Extract plain caption text from a timedtext XML payload."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError(f"transcript XML is not parseable: {exc}") from exc
    lines = [(el.text or "").strip() for el in root.iter("text")]
    return "\n".join(line for line in lines if line)


@dataclass(frozen=True)
class MacroResult:
    """One search-macro run: the URL built, the page snapshotted."""

    site: str
    query: str
    search_url: str
    final_url: str
    snapshot_text: str
    fetched_at: datetime

    def to_dict(self) -> dict:
        return {
            "site": self.site,
            "query": self.query,
            "search_url": self.search_url,
            "final_url": self.final_url,
            "snapshot_text": self.snapshot_text,
            "fetched_at": self.fetched_at.isoformat(),
        }


SnapshotFn = Callable[[str], Awaitable[tuple[str, str]]]
FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]


class CamofoxMacroRunner:
    """Runs search macros and transcript fetches through injected callables.

    ``fetch_snapshot`` is the sidecar tab snapshot
    (``CamofoxClient.fetch_snapshot`` in production); ``fetch_bytes`` is
    the hardened HTTP fetch used for the no-login timedtext endpoint.
    Nothing here performs network I/O of its own.
    """

    def __init__(
        self,
        fetch_snapshot: SnapshotFn | None = None,
        fetch_bytes: FetchBytes | None = None,
    ) -> None:
        self._fetch_snapshot = fetch_snapshot
        self._fetch_bytes = fetch_bytes

    async def run_macro(self, site: str, query: str) -> MacroResult:
        """Build the macro URL and snapshot it through the sidecar."""
        if self._fetch_snapshot is None:
            raise RuntimeError("no snapshot fetcher configured for macro runs")
        search_url = build_search_url(site, query)
        final_url, snapshot_text = await self._fetch_snapshot(search_url)
        return MacroResult(
            site=site.lower(),
            query=" ".join(query.split()),
            search_url=search_url,
            final_url=final_url,
            snapshot_text=snapshot_text,
            fetched_at=datetime.now(UTC),
        )

    async def fetch_transcript(self, video_id: str) -> str:
        """Fetch a public video's English captions as plain text.

        Returns ``""`` when the video has no English captions (the
        timedtext endpoint answers 200 with an empty body in that case);
        raises :class:`RuntimeError` on an HTTP error, and
        :class:`ValueError` on an unparseable payload — a missing
        transcript is never reported as transcript text.
        """
        if self._fetch_bytes is None:
            raise RuntimeError("no HTTP fetcher configured for transcript fetches")
        url = youtube_transcript_url(video_id)
        status, _final, body = await self._fetch_bytes(url)
        if status == 404:
            raise RuntimeError(f"transcript endpoint not found for video {video_id!r}")
        if status != 200:
            raise RuntimeError(f"transcript endpoint answered HTTP {status}")
        if not body.strip():
            return ""
        try:
            return parse_transcript_json3(json.loads(body.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            return parse_transcript_xml(body)


__all__ = [
    "SEARCH_MACROS",
    "CamofoxMacroRunner",
    "MacroResult",
    "build_search_url",
    "parse_transcript_json3",
    "parse_transcript_xml",
    "youtube_transcript_url",
]
