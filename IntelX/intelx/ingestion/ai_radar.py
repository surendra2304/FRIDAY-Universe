"""IntelX AI-trending Radar feed (TASK-IG2-INT-05, cluster #45).

A trending-topics radar over IntelX's existing ingestion machinery: it
polls free/public AI feeds, dedupes items by the headline-watch
fingerprint, extracts topic terms from headlines, and ranks what is
*hot right now* — a term trends when it appears across multiple recent
items, and it trends harder when independent sources carry it at once.

Sources (all free/public RSS/Atom, polled through the same hardened
``HttpFetchConnector`` the headline watch uses):
  * arXiv cs.AI and cs.CL listing feeds — research-front signal;
  * Hacker News front page — practitioner/community signal;
  * Hugging Face blog — model/tool release signal.
A source that fails to poll is reported in the digest's ``source_status``
with its error — the radar never fills a gap with invented items.

Scoring is deterministic and inspectable (no LLM, no embeddings — fleet
feasible at ~180 MB): for each candidate term, ``score = mentions +
2 * (distinct_sources - 1) + recency_bonus`` where the recency bonus
counts mentions inside the trailing ``recency_window_hours``. Generic
stopwords and one-character tokens are excluded; bigrams of adjacent
content words are tracked alongside unigrams so "vector database" can
trend as a topic, not just "vector".

The radar is a library, like the headline watch: a caller (scheduler,
FRIDAY briefing) drives ``poll_once()`` and reads ``trending()`` /
``digest()``. Nothing here runs a daemon of its own.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from intelx.ingestion.headline_watch import Headline, HeadlineSource, parse_feed

logger = logging.getLogger("intelx.ai_radar")

UTC = timezone.utc

FetchText = Callable[[str], Awaitable[str]]

RADAR_SOURCES: list[HeadlineSource] = [
    HeadlineSource(source_id="arxiv_cs_ai", name="arXiv cs.AI", kind="rss",
                   url="https://export.arxiv.org/rss/cs.AI"),
    HeadlineSource(source_id="arxiv_cs_cl", name="arXiv cs.CL", kind="rss",
                   url="https://export.arxiv.org/rss/cs.CL"),
    HeadlineSource(source_id="hacker_news", name="Hacker News (front page)", kind="rss",
                   url="https://news.ycombinator.com/rss"),
    HeadlineSource(source_id="hf_blog", name="Hugging Face Blog", kind="rss",
                   url="https://huggingface.co/blog/feed.xml"),
]

_STOPWORDS = {
    "the", "a", "an", "of", "for", "and", "or", "in", "on", "to", "with",
    "from", "by", "at", "is", "are", "new", "using", "use", "via", "how",
    "what", "why", "show", "hn", "ai", "ml", "llm", "llms", "model", "models",
}
_TOKEN_RE = re.compile(r"[a-z][a-z0-9][a-z0-9+\-.]*")


def extract_terms(title: str) -> list[str]:
    """Content terms of a headline: unigrams + adjacent bigrams."""
    tokens = [t for t in _TOKEN_RE.findall(title.lower()) if t not in _STOPWORDS and len(t) > 2]
    terms = list(tokens)
    terms.extend(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))
    return terms


@dataclass(frozen=True)
class TrendingTopic:
    term: str
    score: float
    mentions: int
    sources: tuple[str, ...]
    examples: tuple[str, ...]  # up to 3 headline titles carrying the term

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "score": self.score,
            "mentions": self.mentions,
            "sources": list(self.sources),
            "examples": list(self.examples),
        }


@dataclass
class _SourceStatus:
    source_id: str
    last_poll_at: datetime | None = None
    last_error: str = ""
    items_seen: int = 0


class AiRadar:
    """Bounded trending-topics radar over free AI feeds."""

    def __init__(
        self,
        sources: list[HeadlineSource] | None = None,
        fetch_text: FetchText | None = None,
        buffer_size: int = 400,
        recency_window_hours: float = 48.0,
    ) -> None:
        self.sources = list(sources) if sources is not None else list(RADAR_SOURCES)
        self._fetch_text = fetch_text or self._default_fetch
        self.buffer_size = max(10, buffer_size)
        self.recency_window = timedelta(hours=recency_window_hours)
        self._items: list[Headline] = []
        self._seen: set[str] = set()
        self._status: dict[str, _SourceStatus] = {s.source_id: _SourceStatus(s.source_id) for s in self.sources}

    @staticmethod
    async def _default_fetch(url: str) -> str:
        from intelx.connectors.web import HttpFetchConnector

        result = await HttpFetchConnector().fetch(url)
        return result.content.decode("utf-8", errors="ignore")

    async def _poll_source(self, source: HeadlineSource, now: datetime) -> list[Headline]:
        status = self._status[source.source_id]
        status.last_poll_at = now
        try:
            xml_text = await self._fetch_text(source.url)
            parsed = parse_feed(xml_text, source, now)
        except Exception as exc:
            status.last_error = f"{type(exc).__name__}: {exc}"[:200]
            logger.debug("radar poll failed for %s: %s", source.source_id, exc)
            return []
        status.last_error = ""
        status.items_seen += len(parsed)
        return parsed

    async def poll_once(self, now: datetime | None = None) -> list[Headline]:
        """One sweep over all sources; returns only NEW items ingested."""
        now = now or datetime.now(UTC)
        batches = await asyncio.gather(*(self._poll_source(s, now) for s in self.sources))
        fresh: list[Headline] = []
        for batch in batches:
            for item in batch:
                if item.fingerprint in self._seen:
                    continue
                self._seen.add(item.fingerprint)
                fresh.append(item)
        if fresh:
            self._items = (fresh + self._items)[: self.buffer_size]
        return fresh

    def trending(self, limit: int = 10, now: datetime | None = None) -> list[TrendingTopic]:
        """Ranked trending topics over the current buffer."""
        now = now or datetime.now(UTC)
        mentions: Counter[str] = Counter()
        recent: Counter[str] = Counter()
        sources_by_term: dict[str, set[str]] = defaultdict(set)
        examples: dict[str, list[str]] = defaultdict(list)
        for item in self._items:
            stamp = item.published_at or item.fetched_at
            is_recent = stamp is not None and (now - stamp) <= self.recency_window
            for term in set(extract_terms(item.title)):
                mentions[term] += 1
                sources_by_term[term].add(item.source_id)
                if is_recent:
                    recent[term] += 1
                if len(examples[term]) < 3:
                    examples[term].append(item.title)
        topics: list[TrendingTopic] = []
        for term, count in mentions.items():
            if count < 2:
                continue  # a single mention is a topic, not a trend
            distinct_sources = len(sources_by_term[term])
            score = float(count + 2 * (distinct_sources - 1) + recent[term])
            topics.append(TrendingTopic(
                term=term,
                score=score,
                mentions=count,
                sources=tuple(sorted(sources_by_term[term])),
                examples=tuple(examples[term]),
            ))
        topics.sort(key=lambda t: (t.score, t.mentions), reverse=True)
        return topics[: max(0, limit)]

    def digest(self, limit: int = 10, now: datetime | None = None) -> dict:
        """Owner-facing radar digest: trending topics + source honesty."""
        return {
            "generated_at": (now or datetime.now(UTC)).isoformat(),
            "items_buffered": len(self._items),
            "trending": [t.to_dict() for t in self.trending(limit=limit, now=now)],
            "source_status": [
                {
                    "source_id": s.source_id,
                    "last_poll_at": s.last_poll_at.isoformat() if s.last_poll_at else None,
                    "last_error": s.last_error,
                    "items_seen": s.items_seen,
                }
                for s in self._status.values()
            ],
        }
