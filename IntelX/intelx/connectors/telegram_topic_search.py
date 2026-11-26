"""INTELX — Telegram topic-search source discovery (TASK-INT-046).

Route A of the scope doc: a topic query returns a ranked candidate-source
list of relevant PUBLIC Telegram channels/groups that IntelX can propose
for watch inclusion. Credential-free by construction:

  * Discovery runs through the existing web-search seam
    (``WebSearchConnector``) with a ``site:t.me <topic>`` query — no new
    credential, no Telegram account, no MTProto (route C is gated and is
    not attempted here).
  * Each candidate handle is verified against its public web preview
    (``https://t.me/s/<handle>``) and parsed with a small stdlib HTML
    parser written in this module. It does NOT import Sentinel's
    ``telegram_channels`` module (different package, different failure
    domain); it follows the same public-preview approach.

Fail-closed, throughout: a search failure yields zero candidates; a
preview fetch/parse failure skips that handle (never invented); a
preview that carries no title, no description and no posts is
unverified and is not proposed. Subscriber counts are reported only
when the preview actually carries them (``None`` otherwise) — never
fabricated. The returned text is the channel's own verbatim title /
description / recent-post text, stored with its preview URL and fetch
time, so any later quote can be checked against what was fetched.

Watch inclusion (design decision, recorded in the scope doc before
implementation): inclusion stays MANUAL in this task. ``FeedSource`` is
an RSS/Atom URL + publisher and a Telegram channel has no RSS feed, so
a candidate cannot be appended as a feed source; the adapter for a
Telegram-channel source kind is a separate follow-up task. Every
candidate therefore carries a structured ``proposal`` (``inclusion:
"manual"`` + reason + suggested record) that a human/coordinator
reviews — the route proposes, it does not enroll.

Python 3.10 compatible. Fetchers injectable for hermetic tests.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Awaitable, Callable
from urllib.parse import urlparse

logger = logging.getLogger("intelx.telegram_topic_search")

UTC = timezone.utc

PREVIEW_URL = "https://t.me/s/{handle}"
CHANNEL_URL = "https://t.me/{handle}"

# t.me paths that are not channel handles (invite/share/service pages).
_RESERVED_HANDLES = {
    "s",
    "joinchat",
    "addstickers",
    "addtheme",
    "share",
    "proxy",
    "socks",
    "iv",
    "setlanguage",
    "confirmphone",
    "login",
    "auth",
    "premium",
    "stars",
    "giftcode",
}
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]  # (status, final_url, body)


class TelegramTopicSearchUnavailable(RuntimeError):
    """A Telegram topic search could not be run; the message says why."""


# ---------------------------------------------------------------------------
# Preview data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TelegramPreview:
    """What a channel's public preview page actually carries."""

    handle: str
    title: str  # "" when the preview carries no title
    description: str  # "" when the preview carries no description
    subscriber_count: int | None  # None when the preview carries no count
    recent_texts: list[str]  # verbatim recent-post texts, most recent first
    fetched_at: datetime

    def to_dict(self) -> dict:
        return {
            "handle": self.handle,
            "title": self.title,
            "description": self.description,
            "subscriber_count": self.subscriber_count,
            "recent_texts": list(self.recent_texts),
            "fetched_at": self.fetched_at.isoformat(),
        }


class _PreviewHTMLParser(HTMLParser):
    """Extracts channel info + recent posts from a t.me/s/ preview page.

    Only these facts are relied on — everything else is ignored:
      * ``og:title`` / ``og:description`` meta (the page's own summary)
      * ``tgme_channel_info_header_title`` / ``tgme_channel_info_description``
      * ``tgme_channel_info_counter`` (subscriber count, digits only)
      * ``tgme_widget_message_text`` divs (recent-post text)

    stdlib only, following the social_links _MetaParser style.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.header_title_parts: list[str] = []
        self.header_desc_parts: list[str] = []
        self.counter_parts: list[str] = []
        self.posts: list[str] = []
        self._in_header_title = False
        self._in_header_desc = False
        self._in_counter = False
        self._in_post = False
        self._post_depth = 0
        self._post_chunks: list[str] = []
        self._skip_depth = 0

    @staticmethod
    def _has_class(attr: dict[str, str | None], wanted: str) -> bool:
        return wanted in (attr.get("class") or "").split()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "meta":
            key = (attr.get("property") or attr.get("name") or "").lower()
            content = attr.get("content") or ""
            if key and content:
                self.meta[key] = content
        elif tag in ("script", "style", "noscript"):
            self._skip_depth += 1
        elif tag == "div":
            if self._has_class(attr, "tgme_channel_info_header_title"):
                self._in_header_title = True
            elif self._has_class(attr, "tgme_channel_info_description"):
                self._in_header_desc = True
            elif self._has_class(attr, "tgme_channel_info_counter"):
                self._in_counter = True
            elif self._has_class(attr, "tgme_widget_message_text"):
                self._in_post = True
                self._post_depth = 1
                self._post_chunks = []
            elif self._in_post:
                self._post_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip_depth:
            self._skip_depth -= 1
        if tag != "div":
            return
        if self._in_header_title:
            self._in_header_title = False
        elif self._in_header_desc:
            self._in_header_desc = False
        elif self._in_counter:
            self._in_counter = False
        elif self._in_post:
            self._post_depth -= 1
            if self._post_depth == 0:
                self._in_post = False
                text = " ".join("".join(self._post_chunks).split())
                if text:
                    self.posts.append(text)

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_header_title:
            self.header_title_parts.append(data)
        if self._in_header_desc:
            self.header_desc_parts.append(data)
        if self._in_counter:
            self.counter_parts.append(data)
        if self._in_post:
            self._post_chunks.append(data)


def _parse_subscriber_count(raw: str) -> int | None:
    """Digits out of a counter string like "12 345 subscribers" / "1.2K".

    Returns None when no count can be read — never a guessed number.
    Thousands separators (space/comma) inside the number are stripped;
    a K/M suffix multiplies. The number must end at a word boundary,
    so a digit run glued to a word is not read as a count.
    """
    text = (raw or "").replace("\u00a0", " ").strip()
    if not text:
        return None
    m = re.search(r"(\d[\d\s,]*(?:\.\d+)?)\s*([KkMm])?\b", text)
    if not m:
        return None
    digits = m.group(1).replace(" ", "").replace(",", "")
    try:
        value = float(digits)
    except ValueError:
        return None
    suffix = (m.group(2) or "").upper()
    if suffix == "K":
        value *= 1_000
    elif suffix == "M":
        value *= 1_000_000
    return int(value)


def parse_channel_preview(html: str, handle: str) -> TelegramPreview:
    """Parse a t.me/s/<handle> preview page into its channel facts.

    Never raises for a malformed page: an unparseable page yields an
    empty preview (title/description "", no posts, no count), which the
    caller treats as unverified and skips.
    """
    parser = _PreviewHTMLParser()
    try:
        parser.feed(html or "")
    except Exception:  # malformed HTML must not crash discovery
        logger.warning("telegram preview parse failed for @%s", handle)
        return TelegramPreview(
            handle=handle,
            title="",
            description="",
            subscriber_count=None,
            recent_texts=[],
            fetched_at=datetime.now(UTC),
        )
    title = " ".join(" ".join(parser.header_title_parts).split()) or parser.meta.get("og:title", "")
    description = (
        " ".join(" ".join(parser.header_desc_parts).split())
        or parser.meta.get("og:description", "")
    )
    counter_text = " ".join(" ".join(parser.counter_parts).split())
    return TelegramPreview(
        handle=handle,
        title=title.strip(),
        description=description.strip(),
        subscriber_count=_parse_subscriber_count(counter_text),
        recent_texts=parser.posts[:5],
        fetched_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Query + handle extraction
# ---------------------------------------------------------------------------


def build_search_query(topic: str) -> str:
    """The discovery query: restrict the web-search seam to t.me pages."""
    return f"site:t.me {topic.strip()}"


def extract_handles(results: list) -> list[str]:
    """Channel handles out of search results, in first-seen order, deduped.

    Accepts ``t.me/<handle>``, ``t.me/s/<handle>`` and ``t.me/<handle>/<id>``
    links; anything else (other hosts, reserved t.me paths, malformed
    handles) is dropped — a candidate is only ever a real channel handle.
    """
    handles: list[str] = []
    seen: set[str] = set()
    for result in results or []:
        url = getattr(result, "url", "") or ""
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        host = (parsed.hostname or "").lower()
        if host not in ("t.me", "www.t.me"):
            continue
        segments = [s for s in parsed.path.split("/") if s]
        if not segments:
            continue
        handle = segments[1] if segments[0] == "s" and len(segments) > 1 else segments[0]
        handle = handle.strip()
        if handle.lower() in _RESERVED_HANDLES:
            continue
        if not _HANDLE_RE.match(handle):
            continue
        if handle not in seen:
            seen.add(handle)
            handles.append(handle)
    return handles


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def topic_terms(topic: str) -> list[str]:
    """Substantive query terms (lowercased, deduped, order kept)."""
    terms: list[str] = []
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", topic.lower()):
        if word not in terms:
            terms.append(word)
    return terms


def score_candidate(topic: str, preview: TelegramPreview, snippet: str = "") -> tuple[float, list[str]]:
    """Deterministic relevance score in [0, 1] + the matched terms.

    Title hits weigh 3, description hits 2, recent-post hits 1, all
    normalised by the term count. A subscriber count (when the preview
    carries one) adds at most 0.05 as a tiebreak — it can never outweigh
    a term match. The score is explainable from the returned terms.
    """
    terms = topic_terms(topic)
    if not terms:
        return 0.0, []
    hay_title = preview.title.lower()
    hay_desc = preview.description.lower()
    hay_posts = " ".join(preview.recent_texts).lower()
    hay_snippet = (snippet or "").lower()
    matched: list[str] = []
    title_hits = desc_hits = post_hits = 0
    for term in terms:
        in_title = term in hay_title
        in_desc = term in hay_desc
        in_posts = term in hay_posts or term in hay_snippet
        if in_title or in_desc or in_posts:
            matched.append(term)
        if in_title:
            title_hits += 1
        if in_desc:
            desc_hits += 1
        if in_posts:
            post_hits += 1
    base = (3 * title_hits + 2 * desc_hits + post_hits) / (6 * len(terms))
    tiebreak = 0.0
    if preview.subscriber_count is not None and preview.subscriber_count > 0:
        tiebreak = 0.05 * min(1.0, math.log10(preview.subscriber_count + 1) / 6.0)
    return round(min(1.0, base + tiebreak), 4), matched


# ---------------------------------------------------------------------------
# Candidate + proposal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TelegramCandidateSource:
    """One verified public Telegram channel proposed for a topic."""

    handle: str
    title: str
    description: str
    preview_url: str
    channel_url: str
    subscriber_count: int | None
    score: float
    matched_terms: list[str]
    provenance: dict = field(default_factory=dict)
    proposal: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "handle": self.handle,
            "title": self.title,
            "description": self.description,
            "preview_url": self.preview_url,
            "channel_url": self.channel_url,
            "subscriber_count": self.subscriber_count,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
            "provenance": dict(self.provenance),
            "proposal": dict(self.proposal),
        }


def propose_for_watch(candidate: TelegramCandidateSource) -> dict:
    """The watch-inclusion proposal for one candidate.

    Inclusion is MANUAL in this task (see the scope doc): a Telegram
    channel has no RSS feed, so it cannot be appended as a FeedSource,
    and the Telegram-channel source-kind adapter is a separate
    follow-up task. This proposal is what a human/coordinator reviews
    and adds — it is not an enrollment.
    """
    return {
        "inclusion": "manual",
        "reason": (
            "A Telegram channel has no RSS/Atom feed, so it cannot be appended "
            "as a FeedSource; the Telegram-channel source-kind adapter "
            "(polled via the t.me/s/ preview) is a separate follow-up task. "
            "A human/coordinator reviews this candidate and adds the channel "
            "manually, or waits for that adapter."
        ),
        "suggested_record": {
            "kind": "telegram_channel",
            "handle": candidate.handle,
            "preview_url": candidate.preview_url,
            "channel_url": candidate.channel_url,
            "title": candidate.title,
            "description": candidate.description,
            "score": candidate.score,
        },
    }


# ---------------------------------------------------------------------------
# Discovery service
# ---------------------------------------------------------------------------


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


class TelegramTopicSearch:
    """Route-A discovery: web search (site:t.me) + public-preview verify.

    Search and preview fetchers are injectable; the defaults compose
    with the existing seams (``WebSearchConnector`` + ``HttpFetchConnector``).
    Every failure mode is fail-closed: a failed search yields zero
    candidates, a failed preview skips that handle, an unverifiable
    preview (no title, no description, no posts) is not proposed.
    """

    def __init__(self, search=None, fetch: FetchBytes | None = None) -> None:
        self._search = search
        self._fetch = fetch or _default_fetch

    async def _default_search(self, query: str, max_results: int) -> list:
        from intelx.connectors.search import WebSearchConnector

        return await WebSearchConnector().fetch(query, max_results=max_results)

    async def search(
        self, topic: str, max_results: int = 10, max_candidates: int = 10
    ) -> list[TelegramCandidateSource]:
        """Return a ranked candidate list for ``topic`` (possibly empty).

        Never raises for upstream failures and never invents a channel:
        an empty list is the honest answer when search or every preview
        fails, or when nothing matches.
        """
        topic = (topic or "").strip()
        if not topic:
            return []
        query = build_search_query(topic)
        try:
            if self._search is not None:
                results = await self._search.fetch(query, max_results=max_results)
            else:
                results = await self._default_search(query, max_results)
        except Exception as exc:  # search seam down — fail closed
            logger.warning("telegram topic search failed for %r (%s)", topic, type(exc).__name__)
            return []
        handles = extract_handles(results)
        if not handles:
            return []
        snippets = {}
        for result in results or []:
            for handle in extract_handles([result]):
                snippets.setdefault(handle, getattr(result, "snippet", "") or "")

        candidates: list[TelegramCandidateSource] = []
        for handle in handles[: max(1, max_candidates * 2)]:
            preview_url = PREVIEW_URL.format(handle=handle)
            try:
                status, _final_url, body = await self._fetch(preview_url)
            except Exception as exc:  # preview fetch failed — skip handle
                logger.warning("telegram preview fetch failed for @%s (%s)", handle, type(exc).__name__)
                continue
            if status != 200:
                logger.warning("telegram preview for @%s returned HTTP %s", handle, status)
                continue
            preview = parse_channel_preview(body.decode("utf-8", errors="replace"), handle)
            if not preview.title and not preview.description and not preview.recent_texts:
                logger.warning("telegram preview for @%s is unverifiable (no title/description/posts)", handle)
                continue
            score, matched = score_candidate(topic, preview, snippets.get(handle, ""))
            candidate = TelegramCandidateSource(
                handle=handle,
                title=preview.title,
                description=preview.description,
                preview_url=preview_url,
                channel_url=CHANNEL_URL.format(handle=handle),
                subscriber_count=preview.subscriber_count,
                score=score,
                matched_terms=matched,
                provenance={
                    "search_query": query,
                    "preview_url": preview_url,
                    "preview_status": status,
                    "preview_fetched_at": preview.fetched_at.isoformat(),
                },
            )
            candidates.append(replace(candidate, proposal=propose_for_watch(candidate)))
        # Rank: score desc, subscriber count desc (None last), handle asc.
        candidates.sort(
            key=lambda c: (
                -c.score,
                -(c.subscriber_count or -1),
                c.handle,
            )
        )
        return candidates[: max(1, max_candidates)]


__all__ = [
    "FetchBytes",
    "TelegramCandidateSource",
    "TelegramPreview",
    "TelegramTopicSearch",
    "TelegramTopicSearchUnavailable",
    "build_search_query",
    "extract_handles",
    "parse_channel_preview",
    "propose_for_watch",
    "score_candidate",
    "topic_terms",
]
