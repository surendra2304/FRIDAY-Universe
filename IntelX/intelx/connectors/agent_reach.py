"""INTELX — Agent Reach no-login channels (TASK-INT-051).

Implements the corpus idea from item DerbBtfzj8p, the channels
``SocialLinkReader`` (TASK-IG-INT-02) does not cover. Agent Reach
(Panniantong/Agent-Reach, MIT, Python 3.10+) exposes 14 channels behind
one command; this module adapts the four no-login channels IntelX lacked:

  * GitHub — public repo metadata (``api.github.com``, no token) and raw
    file reads (``raw.githubusercontent.com``);
  * RSS/Atom — any public feed URL, parsed with the standard library;
  * V2EX — public topic JSON API (``v2ex.com/api/topics/show.json``);
  * Bilibili — public video metadata API (``api.bilibili.com/.../view``).

What is deliberately NOT adopted (the card's care note binds):

  * Logged-in channels (X/Twitter, LinkedIn, Facebook, Xiaohongshu,
    Weibo) — ``read()`` refuses them with an explicit reason. Nothing
    here uses the owner's accounts or a background browser.
  * YouTube / Reddit / Instagram — already covered by SocialLinkReader;
    this reader reports them ``unsupported`` and defers to it.

READ-ONLY by construction: the reader issues HTTP GETs only, through an
injectable fetch callable (``(status, final_url, body)``). The default
fetch is the hardened ``HttpFetchConnector`` (SSRF guard, robots, byte
caps). Every returned document is a ``SocialLinkDocument`` — the same
verbatim-text + provenance shape as SocialLinkReader — so quotes stay
checkable character-for-character against what was fetched.

No token, no key, no login anywhere in this module. GitHub's public API
answers unauthenticated at 60 requests/hour; a 403/429 from it is
reported as unavailable, never worked around.
"""

from __future__ import annotations

import html as html_mod
import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from urllib.parse import quote, urlparse

from intelx.connectors.social_links import SocialLinkDocument

logger = logging.getLogger("intelx.agent_reach")

UTC = UTC

FetchBytes = tuple  # (status: int, final_url: str, body: bytes) per call

_MAX_TEXT_CHARS = 100_000
_MAX_FEED_ITEMS = 20

_GITHUB_HOSTS = {"github.com", "www.github.com", "raw.githubusercontent.com"}
_V2EX_HOSTS = {"v2ex.com", "www.v2ex.com"}
_BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com"}
_LOGIN_GATED_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
    "xiaohongshu.com",
    "www.xiaohongshu.com",
    "weibo.com",
    "www.weibo.com",
}
_FEED_SUFFIXES = (".xml", ".rss", ".atom")

_BV_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")
_TOPIC_ID_RE = re.compile(r"^\d+$")


class AgentReachUnavailable(RuntimeError):
    """Raised when a link cannot be read; ``reason`` says exactly why."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"cannot read {url}: {reason}")
        self.url = url
        self.reason = reason


def classify_reach_url(url: str) -> str:
    """Return the Agent Reach channel for a URL.

    ``github`` | ``rss`` | ``v2ex`` | ``bilibili`` | ``login_gated`` |
    ``unsupported``. YouTube / Reddit / Instagram are ``unsupported``
    here on purpose — SocialLinkReader owns them.
    """
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https"):
        return "unsupported"
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    if host in _LOGIN_GATED_HOSTS:
        return "login_gated"
    if host in _GITHUB_HOSTS:
        return "github"
    if host in _V2EX_HOSTS and path.startswith("/t/"):
        return "v2ex"
    if host in _BILIBILI_HOSTS and path.startswith("/video/"):
        return "bilibili"
    lowered = path.lower()
    if lowered.endswith(_FEED_SUFFIXES) or "/feed" in lowered or "/rss" in lowered:
        return "rss"
    return "unsupported"


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


def _strip_tags(text: str) -> str:
    """Remove HTML tags and unescape entities (feed descriptions)."""
    no_tags = re.sub(r"<[^>]+>", " ", text or "")
    return html_mod.unescape(re.sub(r"\s+", " ", no_tags)).strip()


def _element_text(element) -> str:
    """All text under an element, including nested children (``<b>`` etc.)."""
    if element is None:
        return ""
    return _strip_tags("".join(element.itertext()))


def _parse_feed(body: bytes) -> tuple[str, list[dict]]:
    """Parse an RSS 2.0 or Atom feed; return (feed_title, items)."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError(f"not a parseable feed: {exc}") from exc
    tag = root.tag.split("}")[-1].lower()
    items: list[dict] = []
    if tag == "rss":
        channel = root.find("channel")
        title = ""
        if channel is not None:
            title = _element_text(channel.find("title"))
            for item in channel.findall("item")[:_MAX_FEED_ITEMS]:
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                items.append(
                    {
                        "title": _element_text(title_el),
                        "link": (link_el.text or "").strip() if link_el is not None else "",
                        "text": _element_text(desc_el),
                    }
                )
        return title, items
    if tag == "feed":
        title = _element_text(root.find("{http://www.w3.org/2005/Atom}title"))
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f"{ns}entry")[:_MAX_FEED_ITEMS]:
            title_el = entry.find(f"{ns}title")
            link = ""
            for link_el in entry.findall(f"{ns}link"):
                if link_el.get("rel") in (None, "alternate"):
                    link = link_el.get("href") or ""
                    break
            summary_el = entry.find(f"{ns}summary")
            items.append(
                {
                    "title": _element_text(title_el),
                    "link": link,
                    "text": _element_text(summary_el),
                }
            )
        return title, items
    raise ValueError(f"unsupported feed root element: {tag!r}")


class AgentReachReader:
    """Reads public links on the Agent Reach no-login channels. GET-only."""

    def __init__(self, fetch=None) -> None:
        self._fetch = fetch or _default_fetch

    async def read(self, url: str) -> SocialLinkDocument:
        channel = classify_reach_url(url)
        if channel == "login_gated":
            raise AgentReachUnavailable(
                url,
                "login-gated channel is not adopted: Agent Reach logged-in "
                "channels are never used with the owner's accounts",
            )
        if channel == "unsupported":
            raise AgentReachUnavailable(
                url,
                "no Agent Reach no-login channel covers this URL "
                "(YouTube / Reddit / Instagram are read by SocialLinkReader)",
            )
        handler = {
            "github": self._read_github,
            "rss": self._read_rss,
            "v2ex": self._read_v2ex,
            "bilibili": self._read_bilibili,
        }[channel]
        return await handler(url)

    # -- GitHub ------------------------------------------------------------
    async def _read_github(self, url: str) -> SocialLinkDocument:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        parts = [p for p in parsed.path.split("/") if p]
        if host == "raw.githubusercontent.com":
            # /{owner}/{repo}/{ref}/{path...}
            if len(parts) < 4:
                raise AgentReachUnavailable(url, "raw GitHub URL has no file path")
            owner, repo, ref = parts[0], parts[1], parts[2]
            path = "/".join(parts[3:])
            return await self._read_github_file(url, owner, repo, ref, path)
        if len(parts) < 2:
            raise AgentReachUnavailable(url, "GitHub URL names no repository")
        owner, repo = parts[0], parts[1]
        if parts[1] == "blob" or (len(parts) >= 4 and parts[2] in ("blob", "raw")):
            # /{owner}/{repo}/blob/{ref}/{path...}
            if len(parts) < 5:
                raise AgentReachUnavailable(url, "GitHub blob URL has no file path")
            ref = parts[3]
            path = "/".join(parts[4:])
            return await self._read_github_file(url, owner, repo, ref, path)
        return await self._read_github_repo(url, owner, repo)

    async def _read_github_repo(self, url: str, owner: str, repo: str) -> SocialLinkDocument:
        api_url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
        status, _final, body = await self._fetch(api_url)
        if status == 404:
            raise AgentReachUnavailable(url, "repository not found on GitHub")
        if status == 403:
            raise AgentReachUnavailable(
                url, "GitHub API rate limit reached for unauthenticated requests; try later"
            )
        if status != 200:
            raise AgentReachUnavailable(url, f"GitHub API answered HTTP {status}")
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AgentReachUnavailable(
                url, f"GitHub API returned unparseable JSON: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise AgentReachUnavailable(url, "GitHub API returned an unexpected shape")
        license_name = ""
        if isinstance(data.get("license"), dict):
            license_name = str(data["license"].get("name") or "")
        lines = [
            f"Repository: {data.get('full_name') or f'{owner}/{repo}'}",
            f"Description: {data.get('description') or '(none)'}",
            f"Stars: {data.get('stargazers_count', 0)}",
            f"Language: {data.get('language') or '(none)'}",
            f"License: {license_name or '(none)'}",
            f"Default branch: {data.get('default_branch') or '(unknown)'}",
        ]
        homepage = data.get("homepage")
        if homepage:
            lines.append(f"Homepage: {homepage}")
        return SocialLinkDocument(
            platform="github",
            url=url,
            canonical_url=str(data.get("html_url") or url),
            author=owner,
            title=str(data.get("full_name") or f"{owner}/{repo}"),
            text="\n".join(lines),
            fetched_at=datetime.now(UTC),
            extraction_method="github_api_repo",
            media_kind="repository",
        )

    async def _read_github_file(
        self, url: str, owner: str, repo: str, ref: str, path: str
    ) -> SocialLinkDocument:
        raw_url = (
            f"https://raw.githubusercontent.com/{quote(owner)}/{quote(repo)}"
            f"/{quote(ref)}/{quote(path)}"
        )
        status, final_url, body = await self._fetch(raw_url)
        if status == 404:
            raise AgentReachUnavailable(url, "file not found in that repository")
        if status != 200:
            raise AgentReachUnavailable(url, f"raw GitHub content answered HTTP {status}")
        text = body.decode("utf-8", errors="replace")
        if len(text) > _MAX_TEXT_CHARS:
            text = text[:_MAX_TEXT_CHARS] + "\n[truncated at 100,000 characters]"
        return SocialLinkDocument(
            platform="github",
            url=url,
            canonical_url=final_url,
            author=owner,
            title=f"{owner}/{repo}@{ref}:{path}",
            text=text,
            fetched_at=datetime.now(UTC),
            extraction_method="github_raw_file",
            media_kind="file",
        )

    # -- RSS / Atom ----------------------------------------------------------
    async def _read_rss(self, url: str) -> SocialLinkDocument:
        status, final_url, body = await self._fetch(url)
        if status == 404:
            raise AgentReachUnavailable(url, "feed URL not found")
        if status != 200:
            raise AgentReachUnavailable(url, f"feed answered HTTP {status}")
        try:
            title, items = _parse_feed(body)
        except ValueError as exc:
            raise AgentReachUnavailable(url, str(exc)) from exc
        if not items:
            raise AgentReachUnavailable(url, "feed parsed but contains no items")
        lines = []
        for item in items:
            line = item["title"] or "(untitled)"
            if item["link"]:
                line += f" — {item['link']}"
            if item["text"]:
                line += f"\n{item['text']}"
            lines.append(line)
        return SocialLinkDocument(
            platform="rss",
            url=url,
            canonical_url=final_url,
            author="",
            title=title or url,
            text="\n\n".join(lines),
            fetched_at=datetime.now(UTC),
            extraction_method="rss_feed",
            media_kind="feed",
        )

    # -- V2EX ----------------------------------------------------------------
    async def _read_v2ex(self, url: str) -> SocialLinkDocument:
        parsed = urlparse(url)
        topic_id = parsed.path.split("/t/")[-1].split("/")[0].split("#")[0]
        if not _TOPIC_ID_RE.match(topic_id or ""):
            raise AgentReachUnavailable(url, "V2EX topic URL has no numeric topic id")
        api_url = f"https://www.v2ex.com/api/topics/show.json?id={topic_id}"
        status, _final, body = await self._fetch(api_url)
        if status != 200:
            raise AgentReachUnavailable(url, f"V2EX API answered HTTP {status}")
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AgentReachUnavailable(url, f"V2EX API returned unparseable JSON: {exc}") from exc
        if not isinstance(data, list) or not data:
            raise AgentReachUnavailable(url, "V2EX topic not found")
        topic = data[0]
        member = topic.get("member") or {}
        node = topic.get("node") or {}
        text = str(topic.get("content") or topic.get("content_rendered") or "").strip()
        if not text:
            text = "(topic has no text content)"
        return SocialLinkDocument(
            platform="v2ex",
            url=url,
            canonical_url=f"https://www.v2ex.com/t/{topic_id}",
            author=str(member.get("username") or ""),
            title=str(topic.get("title") or f"V2EX topic {topic_id}"),
            text=f"[{node.get('title') or 'V2EX'}] {text}",
            fetched_at=datetime.now(UTC),
            extraction_method="v2ex_api",
            media_kind="post",
        )

    # -- Bilibili ------------------------------------------------------------
    async def _read_bilibili(self, url: str) -> SocialLinkDocument:
        parsed = urlparse(url)
        bvid = parsed.path.split("/video/")[-1].split("/")[0].split("?")[0]
        if not _BV_RE.match(bvid or ""):
            raise AgentReachUnavailable(url, "Bilibili URL has no valid BV video id")
        api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        status, _final, body = await self._fetch(api_url)
        if status != 200:
            raise AgentReachUnavailable(url, f"Bilibili API answered HTTP {status}")
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AgentReachUnavailable(
                url, f"Bilibili API returned unparseable JSON: {exc}"
            ) from exc
        if not isinstance(data, dict) or data.get("code") != 0:
            raise AgentReachUnavailable(url, "Bilibili video not found or unavailable")
        video = data.get("data") or {}
        owner = video.get("owner") or {}
        stat = video.get("stat") or {}
        desc = str(video.get("desc") or "").strip() or "(no description)"
        text = (
            f"{desc}\n"
            f"Views: {stat.get('view', 0)} | Likes: {stat.get('like', 0)} | "
            f"Duration: {video.get('duration', 0)}s"
        )
        return SocialLinkDocument(
            platform="bilibili",
            url=url,
            canonical_url=f"https://www.bilibili.com/video/{bvid}",
            author=str(owner.get("name") or ""),
            title=str(video.get("title") or bvid),
            text=text,
            fetched_at=datetime.now(UTC),
            extraction_method="bilibili_api",
            media_kind="video",
        )


__all__ = [
    "AgentReachReader",
    "AgentReachUnavailable",
    "classify_reach_url",
]
