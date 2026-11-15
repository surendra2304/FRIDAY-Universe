"""INTELX — Social-link reader (TASK-IG-INT-02, Agent Reach pattern).

Implements the corpus idea from item DerbBtfzj8p: a free, read-only tool that
lets an agent READ public links from Instagram, YouTube, Reddit and more —
"he can look, he can't like". This module is IntelX's version, adapted from
the Agent Reach pattern (repo card: fit = adapt; MIT; Python 3.10+):

  * READ-ONLY by construction: the reader issues HTTP GETs only. There is no
    code path that can post, comment, like, follow or message.
  * No-login channels by default: YouTube oEmbed + watch-page metadata,
    Reddit public JSON, Instagram OpenGraph metadata, and a generic HTML
    extractor for everything else. Nothing here uses the owner's accounts
    or a background browser (Agent Reach's logged-in channels are NOT
    adopted — that care note on the card binds).
  * Citation discipline (INT-008/009): the returned ``text`` is the verbatim
    extracted text from the fetched page, stored with its canonical URL and
    extraction method, so any later quote can be checked character-for-
    character against what was actually fetched. When a platform refuses
    (login wall, HTTP 403), the reader raises ``SocialLinkUnavailable``
    with the reason — it never invents content for a link it could not read.

Fetching composes with ``HttpFetchConnector`` (SSRF guard, robots, byte
caps). Fetchers are injectable for hermetic tests.

Python 3.10 compatible (production interpreter).
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Awaitable, Callable
from urllib.parse import parse_qs, quote, urlparse

logger = logging.getLogger("intelx.social_links")

UTC = timezone.utc


class SocialLinkUnavailable(RuntimeError):
    """Raised when a link cannot be read; ``reason`` says exactly why."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"cannot read {url}: {reason}")
        self.url = url
        self.reason = reason


@dataclass(frozen=True)
class SocialLinkDocument:
    """One read social link, with verbatim text and full provenance."""

    platform: str  # youtube | reddit | instagram | web
    url: str  # as supplied by the caller
    canonical_url: str  # normalised form actually fetched
    author: str
    title: str
    text: str  # verbatim extracted text (never paraphrased by this module)
    fetched_at: datetime
    extraction_method: str  # e.g. youtube_oembed+watch_page, reddit_json, opengraph, generic_html
    media_kind: str = ""  # video | post | link | article | ""

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "author": self.author,
            "title": self.title,
            "text": self.text,
            "fetched_at": self.fetched_at.isoformat(),
            "extraction_method": self.extraction_method,
            "media_kind": self.media_kind,
        }


# ---------------------------------------------------------------------------
# URL classification / canonicalisation
# ---------------------------------------------------------------------------

_YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
_IG_HOSTS = {"instagram.com", "www.instagram.com"}
_REDDIT_HOSTS = {"reddit.com", "www.reddit.com", "old.reddit.com", "np.reddit.com"}


def classify_social_url(url: str) -> str:
    """Return the platform key for a URL (youtube | reddit | instagram | web)."""
    host = (urlparse(url).hostname or "").lower()
    if host in _YT_HOSTS:
        return "youtube"
    if host in _REDDIT_HOSTS:
        return "reddit"
    if host in _IG_HOSTS:
        return "instagram"
    return "web"


def youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.endswith("youtu.be"):
        return parsed.path.strip("/").split("/")[0] or None
    if parsed.path == "/watch":
        values = parse_qs(parsed.query).get("v")
        return values[0] if values else None
    for prefix in ("/shorts/", "/embed/", "/live/"):
        if parsed.path.startswith(prefix):
            return parsed.path[len(prefix) :].split("/")[0] or None
    return None


def canonicalise(url: str) -> str:
    """Normalise a social URL to the form the platform serves publicly."""
    platform = classify_social_url(url)
    parsed = urlparse(url)
    if platform == "youtube":
        vid = youtube_video_id(url)
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"
    if platform == "reddit":
        path = re.sub(r"/+$", "", parsed.path)
        return f"https://www.reddit.com{path}"
    if platform == "instagram":
        path = re.sub(r"/+$", "", parsed.path)
        return f"https://www.instagram.com{path}/"
    return url


# ---------------------------------------------------------------------------
# HTML metadata / text extraction (stdlib only)
# ---------------------------------------------------------------------------


class _MetaParser(HTMLParser):
    """Collects <title>, OpenGraph/Twitter meta, and paragraph text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.paragraphs: list[str] = []
        self._in_title = False
        self._in_p = False
        self._p_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "meta":
            key = attr.get("property") or attr.get("name") or ""
            content = attr.get("content") or ""
            if key and content:
                self.meta[key.lower()] = content
        elif tag == "title":
            self._in_title = True
        elif tag == "p":
            self._in_p = True
            self._p_parts = []
        elif tag in ("script", "style", "noscript"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "p" and self._in_p:
            self._in_p = False
            text = " ".join(" ".join(self._p_parts).split())
            if len(text) >= 40:  # skip nav/footer fragments
                self.paragraphs.append(text)
        elif tag in ("script", "style", "noscript") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        if self._in_p:
            self._p_parts.append(data)


def _parse_html(html_text: str) -> _MetaParser:
    parser = _MetaParser()
    parser.feed(html_text)
    return parser


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]  # (status, final_url, body)


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


class SocialLinkReader:
    """Reads public social links into citation-safe documents. GET-only."""

    def __init__(self, fetch: FetchBytes | None = None) -> None:
        self._fetch = fetch or _default_fetch

    async def read(self, url: str) -> SocialLinkDocument:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise SocialLinkUnavailable(url, f"unsupported scheme '{parsed.scheme}' (http/https only)")
        platform = classify_social_url(url)
        canonical = canonicalise(url)
        if platform == "youtube":
            return await self._read_youtube(url, canonical)
        if platform == "reddit":
            return await self._read_reddit(url, canonical)
        if platform == "instagram":
            return await self._read_instagram(url, canonical)
        return await self._read_web(url, canonical)

    # -- YouTube -------------------------------------------------------------
    async def _read_youtube(self, url: str, canonical: str) -> SocialLinkDocument:
        oembed_url = f"https://www.youtube.com/oembed?url={quote(canonical, safe='')}&format=json"
        status, _, body = await self._fetch(oembed_url)
        if status != 200:
            raise SocialLinkUnavailable(url, f"YouTube oEmbed returned HTTP {status}")
        try:
            meta = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise SocialLinkUnavailable(url, f"YouTube oEmbed returned invalid JSON: {exc}") from exc

        title = str(meta.get("title", ""))
        author = str(meta.get("author_name", ""))
        description = ""
        method = "youtube_oembed"
        # The watch page carries the full description; og:description is the
        # fallback. Both are the uploader's own verbatim text.
        wstatus, _, wbody = await self._fetch(canonical)
        if wstatus == 200:
            page = wbody.decode("utf-8", errors="replace")
            match = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', page)
            if match:
                try:
                    description = json.loads(f'"{match.group(1)}"')
                    method = "youtube_oembed+watch_page"
                except json.JSONDecodeError:
                    description = ""
            if not description:
                og = _parse_html(page).meta.get("og:description", "")
                if og:
                    description = og
                    method = "youtube_oembed+og_description"
        text = description or title
        return SocialLinkDocument(
            platform="youtube",
            url=url,
            canonical_url=canonical,
            author=author,
            title=title,
            text=text,
            fetched_at=datetime.now(UTC),
            extraction_method=method,
            media_kind="video",
        )

    # -- Reddit ---------------------------------------------------------------
    async def _read_reddit(self, url: str, canonical: str) -> SocialLinkDocument:
        json_url = canonical + "/.json"
        status, _, body = await self._fetch(json_url)
        if status != 200:
            raise SocialLinkUnavailable(
                url, f"Reddit public JSON returned HTTP {status} (Reddit rate-limits/blocks some networks; nothing was invented to fill the gap)"
            )
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
            post = payload[0]["data"]["children"][0]["data"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise SocialLinkUnavailable(url, f"Reddit public JSON had an unexpected shape: {exc}") from exc
        title = str(post.get("title", ""))
        selftext = str(post.get("selftext", "") or "")
        outbound = str(post.get("url_overridden_by_dest", "") or "")
        text = selftext if selftext else title
        if outbound and outbound != canonical:
            text = f"{text}\n\nLinked URL: {outbound}".strip()
        return SocialLinkDocument(
            platform="reddit",
            url=url,
            canonical_url=canonical,
            author=f"u/{post.get('author', '')}",
            title=title,
            text=text,
            fetched_at=datetime.now(UTC),
            extraction_method="reddit_json",
            media_kind="post",
        )

    # -- Instagram --------------------------------------------------------------
    async def _read_instagram(self, url: str, canonical: str) -> SocialLinkDocument:
        status, final_url, body = await self._fetch(canonical)
        if status != 200:
            raise SocialLinkUnavailable(url, f"Instagram returned HTTP {status} for the public page")
        page = body.decode("utf-8", errors="replace")
        meta = _parse_html(page).meta
        description = meta.get("og:description", "")
        title = meta.get("og:title", "")
        if not description or "/accounts/login" in final_url or "Login • Instagram" in page[:2000]:
            raise SocialLinkUnavailable(
                url,
                "Instagram served a login wall instead of public metadata; the post text is not "
                "publicly readable without an account, and this reader does not use accounts",
            )
        author = ""
        m = re.match(r"^(?P<handle>[^ ]+) on Instagram", title)
        if m:
            author = f"@{m.group('handle')}"
        return SocialLinkDocument(
            platform="instagram",
            url=url,
            canonical_url=canonical,
            author=author,
            title=title,
            text=html_mod.unescape(description),
            fetched_at=datetime.now(UTC),
            extraction_method="opengraph",
            media_kind="post",
        )

    # -- Generic web --------------------------------------------------------------
    async def _read_web(self, url: str, canonical: str) -> SocialLinkDocument:
        status, _, body = await self._fetch(canonical)
        if status != 200:
            raise SocialLinkUnavailable(url, f"page returned HTTP {status}")
        page = body.decode("utf-8", errors="replace")
        parsed = _parse_html(page)
        title = parsed.meta.get("og:title") or " ".join(parsed.title_parts).strip()
        description = parsed.meta.get("og:description", "")
        body_text = "\n\n".join(parsed.paragraphs)
        text = body_text or description or title
        if not text:
            raise SocialLinkUnavailable(url, "page contained no extractable text")
        return SocialLinkDocument(
            platform="web",
            url=url,
            canonical_url=canonical,
            author=parsed.meta.get("article:author", ""),
            title=title,
            text=text,
            fetched_at=datetime.now(UTC),
            extraction_method="generic_html",
            media_kind="article",
        )


__all__ = [
    "SocialLinkDocument",
    "SocialLinkReader",
    "SocialLinkUnavailable",
    "canonicalise",
    "classify_social_url",
    "youtube_video_id",
]
