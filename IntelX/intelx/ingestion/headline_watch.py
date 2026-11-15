"""INTELX — Standing real-time financial-headline watch (TASK-IG-INT-01).

Implements the pattern from the owner's reference corpus (item DaFMj_es1SH):
skip the economic calendar and follow real-time headline wires — FinancialJuice,
DeltaOne (Walter Bloomberg), Unusual Whales — before trading. The output is a
pre-trade news feed: a standing watch that polls free/public headline sources,
classifies each headline's likely market impact deterministically, dedupes by
fingerprint, and serves the newest market-moving headlines to consumers such
as Stratex.

Source honesty rules (binding):
  * Only free/public sources are polled. FinancialJuice publishes its wire as
    a public RSS feed (verified live 2026-11-15); FXStreet and Investing.com
    RSS are likewise public.
  * The named X/Twitter accounts have NO keyless feed. They are registered as
    ``x_account`` sources with ``active=False`` and an explicit reason, and
    the watch reports them as unavailable — it never fabricates their content.
    If X API credentials are ever configured, an adapter can flip them active
    without changing consumers.

Composition: fetching goes through the hardened ``HttpFetchConnector`` (SSRF
guard, robots, byte caps) exactly like ``news_ingester``; feed parsing mirrors
the ingester's RSS handling but keeps headlines in a bounded in-memory watch
buffer instead of the canonical research store — a headline wire is ephemeral
signal, not research evidence, and nothing here produces findings, so the
INT-008/009 citation gates are not bypassed: consumers receive the headline
text verbatim with its source URL and timestamp.

Python 3.10 compatible (production interpreter).
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable, Callable

logger = logging.getLogger("intelx.headline_watch")

UTC = timezone.utc

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeadlineSource:
    """One headline source. ``kind`` is ``rss`` or ``x_account``."""

    source_id: str
    name: str
    kind: str
    url: str = ""  # RSS/Atom feed URL for kind == "rss"
    handle: str = ""  # X handle for kind == "x_account"
    active: bool = True
    unavailable_reason: str = ""


# The three accounts named in the source video. FinancialJuice's wire is
# available keylessly over RSS; the two pure-X accounts are not.
X_ACCOUNT_REASON = (
    "X/Twitter has no keyless feed; reading this account requires paid X API "
    "credentials, which are not configured. Registered so the gap is explicit, "
    "never silently filled with invented headlines."
)

DEFAULT_SOURCES: list[HeadlineSource] = [
    HeadlineSource(
        source_id="financialjuice_rss",
        name="FinancialJuice (RSS wire)",
        kind="rss",
        url="https://www.financialjuice.com/feed.ashx?xy=rss",
    ),
    HeadlineSource(
        source_id="fxstreet_rss",
        name="FXStreet News (RSS)",
        kind="rss",
        url="https://www.fxstreet.com/rss/news",
    ),
    HeadlineSource(
        source_id="investing_rss",
        name="Investing.com News (RSS)",
        kind="rss",
        url="https://www.investing.com/rss/news.rss",
    ),
    HeadlineSource(
        source_id="financialjuice_x",
        name="FinancialJuice (@financialjuice)",
        kind="x_account",
        handle="financialjuice",
        active=False,
        unavailable_reason=X_ACCOUNT_REASON,
    ),
    HeadlineSource(
        source_id="deltaone_x",
        name="DeltaOne / Walter Bloomberg (@Deltaone)",
        kind="x_account",
        handle="Deltaone",
        active=False,
        unavailable_reason=X_ACCOUNT_REASON,
    ),
    HeadlineSource(
        source_id="unusual_whales_x",
        name="Unusual Whales (@unusual_whales)",
        kind="x_account",
        handle="unusual_whales",
        active=False,
        unavailable_reason=X_ACCOUNT_REASON,
    ),
]


# ---------------------------------------------------------------------------
# Impact classification (deterministic; heuristics are labelled as such)
# ---------------------------------------------------------------------------

# Tier-1 phrases: events that routinely move markets within minutes.
_TIER1_PHRASES = (
    "rate hike",
    "rate cut",
    "raises rates",
    "cuts rates",
    "interest rate decision",
    "fomc",
    "fed",
    "federal reserve",
    "central bank",
    "cpi",
    "inflation rate",
    "nonfarm payroll",
    "non-farm payroll",
    "jobs report",
    "gdp",
    "recession",
    "default",
    "bankruptcy",
    "trading halt",
    "circuit breaker",
    "etf approved",
    "etf approval",
    "sec sues",
    "sec charges",
    "hack",
    "exploit",
    "depeg",
    "liquidation",
    "margin call",
    "war",
    "ceasefire",
    "sanctions",
    "tariff",
    "emergency meeting",
    "intervention",
)

# Tier-2 phrases: market-relevant but usually slower-moving.
_TIER2_PHRASES = (
    "earnings",
    "guidance",
    "forecast",
    "outlook",
    "upgrade",
    "downgrade",
    "price target",
    "merger",
    "acquisition",
    "buyback",
    "dividend",
    "ipo",
    "whale",
    "etf inflow",
    "etf outflow",
    "reserves",
    "unemployment",
    "retail sales",
    "pmi",
    "yield",
    "treasury",
    "oil",
    "opec",
    "gold",
)

_ASSET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("BTC", re.compile(r"\b(bitcoin|btc)\b", re.I)),
    ("ETH", re.compile(r"\b(ethereum|eth)\b", re.I)),
    ("SOL", re.compile(r"\b(solana|sol)\b", re.I)),
    ("XRP", re.compile(r"\b(xrp|ripple)\b", re.I)),
    ("USD", re.compile(r"\b(dollar|usd|greenback)\b", re.I)),
    ("EUR", re.compile(r"\b(euro|eur)\b", re.I)),
    ("GBP", re.compile(r"\b(pound|sterling|gbp)\b", re.I)),
    ("JPY", re.compile(r"\b(yen|jpy)\b", re.I)),
    ("XAU", re.compile(r"\b(gold|xau)\b", re.I)),
    ("OIL", re.compile(r"\b(crude|wti|brent|oil)\b", re.I)),
    ("SPX", re.compile(r"\b(s&p|spx|nasdaq|dow jones)\b", re.I)),
]

_BULLISH_WORDS = ("surge", "rally", "jumps", "soars", "beats", "rises", "gains", "approval", "approved", "record high", "bullish")
_BEARISH_WORDS = ("plunge", "crashes", "falls", "drops", "misses", "declines", "lawsuit", "hack", "bearish", "record low", "warns", "warning")


@dataclass(frozen=True)
class ImpactAssessment:
    """Deterministic heuristic impact for one headline.

    ``direction`` is a lexical hint only (bullish/bearish/mixed/neutral) —
    it is a heuristic label, never a trading signal by itself.
    """

    score: int  # 0..100
    tier: str  # critical | high | medium | low
    assets: tuple[str, ...]
    direction: str
    matched_phrases: tuple[str, ...]


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Word-boundary pattern so e.g. 'war' never matches inside 'award'."""
    return re.compile(r"\b" + re.escape(phrase) + r"\b")


_TIER1_PATTERNS = tuple((p, _phrase_pattern(p)) for p in _TIER1_PHRASES)
_TIER2_PATTERNS = tuple((p, _phrase_pattern(p)) for p in _TIER2_PHRASES)
_BULLISH_PATTERNS = tuple(_phrase_pattern(w) for w in _BULLISH_WORDS)
_BEARISH_PATTERNS = tuple(_phrase_pattern(w) for w in _BEARISH_WORDS)


def classify_impact(title: str) -> ImpactAssessment:
    """Score a headline's likely market impact with transparent rules."""
    text = title.lower()
    score = 0
    matched: list[str] = []
    for phrase, pat in _TIER1_PATTERNS:
        if pat.search(text):
            score += 30
            matched.append(phrase)
    for phrase, pat in _TIER2_PATTERNS:
        if pat.search(text):
            score += 10
            matched.append(phrase)
    assets = tuple(sym for sym, pat in _ASSET_PATTERNS if pat.search(title))
    if assets:
        score += min(20, 5 * len(assets))
    score = min(100, score)
    if score >= 60:
        tier = "critical"
    elif score >= 35:
        tier = "high"
    elif score >= 15:
        tier = "medium"
    else:
        tier = "low"
    bull = any(pat.search(text) for pat in _BULLISH_PATTERNS)
    bear = any(pat.search(text) for pat in _BEARISH_PATTERNS)
    direction = "mixed" if (bull and bear) else "bullish" if bull else "bearish" if bear else "neutral"
    return ImpactAssessment(
        score=score,
        tier=tier,
        assets=assets,
        direction=direction,
        matched_phrases=tuple(matched),
    )


# ---------------------------------------------------------------------------
# Headlines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Headline:
    source_id: str
    source_name: str
    title: str
    url: str
    published_at: datetime | None
    fetched_at: datetime
    fingerprint: str
    impact: ImpactAssessment

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "fetched_at": self.fetched_at.isoformat(),
            "fingerprint": self.fingerprint,
            "impact": {
                "score": self.impact.score,
                "tier": self.impact.tier,
                "assets": list(self.impact.assets),
                "direction": self.impact.direction,
                "matched_phrases": list(self.impact.matched_phrases),
            },
        }


def headline_fingerprint(source_id: str, title: str, url: str) -> str:
    """Stable dedupe key: source + normalised title (+ guid-like URL tail)."""
    norm_title = re.sub(r"\s+", " ", title.strip().lower())
    return hashlib.sha256(f"{source_id}|{norm_title}|{url.strip()}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Feed parsing (RSS 2.0 + Atom), mirroring news_ingester behaviour
# ---------------------------------------------------------------------------

_ATOM = "{http://www.w3.org/2005/Atom}"


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_feed(xml_text: str, source: HeadlineSource, fetched_at: datetime) -> list[Headline]:
    """Parse an RSS/Atom document into Headline objects (newest first kept)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"unparseable feed from {source.source_id}: {exc}") from exc

    items: list[tuple[str, str, datetime | None]] = []
    if root.tag.endswith("feed"):  # Atom
        for entry in root.iter(f"{_ATOM}entry"):
            title = (entry.findtext(f"{_ATOM}title") or "").strip()
            link = ""
            for link_el in entry.findall(f"{_ATOM}link"):
                if link_el.get("rel") in (None, "alternate"):
                    link = link_el.get("href", "")
                    break
            when = entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated")
            if title:
                items.append((html.unescape(title), link.strip(), _parse_date(when)))
    else:  # RSS 2.0 / RDF
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            when = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date")
            if title:
                items.append((html.unescape(title), link, _parse_date(when)))

    headlines: list[Headline] = []
    for title, link, published in items:
        headlines.append(
            Headline(
                source_id=source.source_id,
                source_name=source.name,
                title=title,
                url=link,
                published_at=published,
                fetched_at=fetched_at,
                fingerprint=headline_fingerprint(source.source_id, title, link),
                impact=classify_impact(title),
            )
        )
    return headlines


# ---------------------------------------------------------------------------
# The watch
# ---------------------------------------------------------------------------

FetchText = Callable[[str], Awaitable[str]]


async def _default_fetch_text(url: str) -> str:
    """Fetch feed text through the hardened connector (SSRF/robots/caps)."""
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    if result.status_code != 200:
        raise RuntimeError(f"feed fetch returned HTTP {result.status_code} for {url}")
    return result.content.decode("utf-8", errors="replace")


@dataclass
class SourceStatus:
    source_id: str
    active: bool
    last_poll_at: datetime | None = None
    last_error: str = ""
    headlines_seen: int = 0
    headlines_new: int = 0


class HeadlineWatch:
    """Polls headline sources, dedupes, and serves a pre-trade headline feed.

    Usage:
        watch = HeadlineWatch()
        new = await watch.poll_once()          # one sweep over active sources
        feed = watch.latest(limit=20, min_score=35)   # Stratex-facing query
        async for batch in watch.run(interval_s=60):  # standing loop
            ...
    """

    def __init__(
        self,
        sources: list[HeadlineSource] | None = None,
        fetch_text: FetchText | None = None,
        buffer_size: int = 500,
        seen_size: int = 5000,
    ) -> None:
        self.sources = list(sources) if sources is not None else list(DEFAULT_SOURCES)
        self._fetch_text = fetch_text or _default_fetch_text
        self._buffer_size = buffer_size
        self._seen_size = seen_size
        self._seen: dict[str, None] = {}
        self._buffer: list[Headline] = []
        self._subscribers: list[Callable[[list[Headline]], Awaitable[None] | None]] = []
        self.status: dict[str, SourceStatus] = {
            s.source_id: SourceStatus(source_id=s.source_id, active=s.active) for s in self.sources
        }

    # -- introspection ------------------------------------------------------
    def source_report(self) -> list[dict[str, Any]]:
        """Per-source state, including WHY inactive sources are inactive."""
        report = []
        for s in self.sources:
            st = self.status[s.source_id]
            report.append(
                {
                    "source_id": s.source_id,
                    "name": s.name,
                    "kind": s.kind,
                    "active": s.active,
                    "unavailable_reason": s.unavailable_reason if not s.active else "",
                    "last_poll_at": st.last_poll_at.isoformat() if st.last_poll_at else None,
                    "last_error": st.last_error,
                    "headlines_seen": st.headlines_seen,
                    "headlines_new": st.headlines_new,
                }
            )
        return report

    def subscribe(self, callback: Callable[[list[Headline]], Awaitable[None] | None]) -> None:
        self._subscribers.append(callback)

    # -- polling ------------------------------------------------------------
    async def _poll_source(self, source: HeadlineSource, now: datetime) -> list[Headline]:
        st = self.status[source.source_id]
        st.last_poll_at = now
        if not source.active:
            return []
        if source.kind == "x_account":
            st.last_error = source.unavailable_reason or X_ACCOUNT_REASON
            return []
        try:
            xml_text = await self._fetch_text(source.url)
            parsed = parse_feed(xml_text, source, now)
        except Exception as exc:  # one bad source must not kill the sweep
            st.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("headline watch: source %s failed: %s", source.source_id, st.last_error)
            return []
        st.last_error = ""
        st.headlines_seen += len(parsed)
        fresh: list[Headline] = []
        for h in parsed:
            if h.fingerprint in self._seen:
                continue
            self._seen[h.fingerprint] = None
            fresh.append(h)
        st.headlines_new += len(fresh)
        return fresh

    async def poll_once(self) -> list[Headline]:
        """One sweep over all sources; returns only NEW headlines."""
        now = datetime.now(UTC)
        batches = await asyncio.gather(*(self._poll_source(s, now) for s in self.sources))
        fresh = [h for batch in batches for h in batch]
        fresh.sort(key=lambda h: h.published_at or h.fetched_at, reverse=True)
        if fresh:
            self._buffer = (fresh + self._buffer)[: self._buffer_size]
            # bound the seen-set (insertion-ordered dict)
            while len(self._seen) > self._seen_size:
                self._seen.pop(next(iter(self._seen)))
            for cb in self._subscribers:
                try:
                    out = cb(fresh)
                    if asyncio.iscoroutine(out):
                        await out
                except Exception:  # a consumer must not break the watch
                    logger.exception("headline watch subscriber failed")
        return fresh

    async def run(self, interval_s: float = 60.0, max_sweeps: int | None = None):
        """Standing poll loop; yields each sweep's new headlines."""
        sweeps = 0
        while max_sweeps is None or sweeps < max_sweeps:
            fresh = await self.poll_once()
            yield fresh
            sweeps += 1
            if max_sweeps is None or sweeps < max_sweeps:
                await asyncio.sleep(interval_s)

    # -- consumer query -------------------------------------------------------
    def latest(self, limit: int = 20, min_score: int = 0, asset: str | None = None) -> list[Headline]:
        """Newest buffered headlines at/above an impact floor (Stratex feed)."""
        out = []
        for h in self._buffer:
            if h.impact.score < min_score:
                continue
            if asset and asset.upper() not in h.impact.assets:
                continue
            out.append(h)
            if len(out) >= limit:
                break
        return out


__all__ = [
    "DEFAULT_SOURCES",
    "Headline",
    "HeadlineSource",
    "HeadlineWatch",
    "ImpactAssessment",
    "SourceStatus",
    "classify_impact",
    "headline_fingerprint",
    "parse_feed",
]
