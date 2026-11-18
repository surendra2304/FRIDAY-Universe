"""IntelX standing research watches — TASK-INT-007.

A *standing watch* is a narrow, always-on question IntelX keeps asking a
small set of high-signal feeds: "did something the owner would actually
want to know just happen?" A watch is NOT the news ingester (which files
everything into the research corpus). A watch emits at most a few alert
envelopes per day, and only for items that clear a deterministic
significance bar. Silence is the default state.

Design rules (see IntelX/docs/STANDING_WATCHES.md for the full design):

  * Dedupe is structural, not best-effort: every fetched item is
    fingerprinted (normalised URL, plus a normalised-title fingerprint
    for cross-posts) and recorded in a persistent seen-store. An item can
    alert at most once, ever.
  * Noise budget is explicit per watch: a significance threshold, a
    per-poll alert cap, and a per-day alert cap. Significant items that
    arrive over budget are marked ``suppressed_budget`` — counted and
    reported in the poll result, never drip-fed later.
  * First contact is a baseline: on a watch's first-ever poll, items
    older than ``baseline_max_age_hours`` are recorded silently so
    enabling a watch never floods the owner with history.
  * Alerts leave IntelX as envelopes on an outbox (JSONL). Delivery to
    the owner is owned by TASK-PRO-001 (Proactive FRIDAY), whose
    dedupe + quiet-hours (23:00-07:00 IST) rules apply downstream.
    Watch envelopes are never quiet-hours exempt.

This module is deliberately standard-library only: no database, no web
framework, no third-party imports. It runs inside the IntelX process
behind ``ENABLE_STANDING_WATCHES`` and standalone via
``python -m intelx.watches.run_once`` for proofs and operations.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

logger = logging.getLogger("intelx.watches")

IST = ZoneInfo("Asia/Kolkata")
STATE_VERSION = 1
ENVELOPE_SCHEMA = "intelx.watch_alert/1"
TRACKING_PARAMS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "referrer", "source",
    "cmpid", "ito", "outputType",
}
TITLE_DEDUPE_MIN_CHARS = 40  # shorter titles are too generic to cross-match
PRUNE_DAYS = 90


# ---------------------------------------------------------------------------
# Watch definitions (data, not code — tuning a watch never edits the engine)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeedSource:
    url: str
    publisher: str


@dataclass(frozen=True)
class ScoreRule:
    """One significance rule. ``where`` is "title" or "title_summary"."""

    name: str
    pattern: str
    weight: int
    where: str = "title"


@dataclass(frozen=True)
class WatchDefinition:
    id: str
    title: str
    owner_value: str  # why the owner would want this watch, in one line
    sources: tuple[FeedSource, ...]
    rules: tuple[ScoreRule, ...]
    excludes: tuple[str, ...]  # regexes; a title match hard-excludes the item
    min_score: int = 4
    max_alerts_per_poll: int = 1
    max_alerts_per_day: int = 3
    baseline_max_age_hours: int = 72
    poll_interval_seconds: int = 1800
    enabled: bool = False
    # Topic domain (TASK-INT-013): every watch declares exactly one domain
    # from intelx.watches.domains.DOMAINS. The domain is the subscription
    # unit for the Universe intel feed (TASK-INT-014) and is stamped on
    # every envelope. "general" is the undeclared fallback, not a home.
    domain: str = "general"


_AI_RELEASE_RULES = (
    ScoreRule(
        "release_language",
        r"\b(introducing|announcing|announces|now available|available today|"
        r"available now|launching|releasing|we(?:'re| are) releasing|"
        r"unveiling|open[- ]sourcing|open weights|say hello to|meet the new)\b",
        3,
    ),
    ScoreRule(
        "model_name_with_version",
        r"\b(gpt[-\s]?[0-9]|chatgpt[-\s]?[0-9]|claude\s+(opus|sonnet|haiku)\s+[0-9]|"
        r"claude\s+[0-9]|gemini\s+[0-9]|llama\s+[0-9]|qwen\s*[0-9]|"
        r"deepseek[-\s]?[rv]?[0-9]|grok\s*[0-9]|mistral\s+(large|medium|small))\b",
        3,
    ),
    ScoreRule(
        "developer_availability",
        r"\b(api|developers?|fine[- ]tuning|context window|open[- ]source|"
        r"pricing|per million tokens)\b",
        2,
        where="title_summary",
    ),
    ScoreRule("mentions_model", r"\bmodels?\b", 1),
)

_AI_EXCLUDES = (
    r"\bpodcast\b", r"\bwebinar\b", r"\brecap\b", r"\bnewsletter\b",
    r"\bsponsored\b", r"\bcareers?\b", r"\bhiring\b", r"\bconference\b",
    r"\bsummit\b", r"\bmeetup\b", r"\blivestream\b", r"\binterview\b",
)

WATCH_AI_MODEL_RELEASES = WatchDefinition(
    id="ai_model_releases",
    title="AI model releases",
    owner_value=(
        "FRIDAY and Inference run on Gemini/Groq/OpenRouter models; a new "
        "frontier model, an API change, or an open-weights drop can change "
        "what the fleet should route to — the owner hears about it the "
        "day it ships, not weeks later."
    ),
    sources=(
        FeedSource("https://openai.com/blog/rss.xml", "OpenAI Blog"),
        FeedSource("https://blog.google/technology/ai/rss/", "Google AI Blog"),
        FeedSource("https://huggingface.co/blog/feed.xml", "Hugging Face Blog"),
        # Anthropic is deliberately absent: it has discontinued its public
        # RSS (news/rss.xml, rss.xml, feed.xml, news/feed.xml all 404,
        # probed 2026-11-15 for TASK-INT-007). Claude-release coverage is
        # a known gap — see STANDING_WATCHES.md §5. The news ingester's
        # Anthropic entry carries the same dead URL.
    ),
    rules=_AI_RELEASE_RULES,
    excludes=_AI_EXCLUDES,
    min_score=4,
    max_alerts_per_poll=1,
    max_alerts_per_day=3,
    baseline_max_age_hours=72,
    poll_interval_seconds=1800,
    enabled=True,
    domain="ai_models",
)

WATCH_CRYPTO_MARKET_STRUCTURE = WatchDefinition(
    id="crypto_market_structure",
    title="Crypto market-structure changes",
    owner_value=(
        "Stratex trades Binance demo futures under a strict rulebook; ETF "
        "decisions, listing/delisting notices, leverage or margin rule "
        "changes, and stablecoin regulation change the ground it trades "
        "on. Price chatter is explicitly excluded — structure only."
    ),
    sources=(
        FeedSource("https://www.theblock.co/rss.xml", "The Block"),
        FeedSource("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk"),
        FeedSource("https://cointelegraph.com/rss", "CoinTelegraph"),
    ),
    rules=(
        ScoreRule(
            "etf_decision",
            r"\b(etf|etn)\b.*\b(approv|reject|delay|filing|launch)|\b(approv|reject).*\betf\b",
            3,
        ),
        ScoreRule(
            "exchange_structure",
            r"\b(delist|delisting|lists?|listing)\b.*\b(binance|coinbase|kraken|exchange)\b|"
            r"\b(binance|coinbase|kraken|exchange)\b.*\b(delist|delisting|lists?|listing)\b|"
            r"\b(leverage|margin)\b.*\b(change|limit|cap|rule|reduc|increas)",
            3,
        ),
        ScoreRule(
            "regulation",
            r"\b(sec|cftc|mica|stablecoin (act|law|bill)|regulat(or|ion|ory))\b",
            2,
            where="title_summary",
        ),
        ScoreRule(
            "venue_incident",
            # Venue set aligned with exchange_structure (kraken included).
            # Mirrored: event-first wire order ("Hack forces Kraken ...")
            # fires just as venue-first does. The withdrawal branches are
            # the D2 fix from the 2026-11-17 shadow proof: a withdrawal
            # suspension IS a venue incident even when the venue is not a
            # named one ("Lighter suspends all withdrawals ..." scored 0).
            # The block stem is closed (block/blocks/blocked/blocking):
            # block\w* also matched "blockchain" (supervisor F1, PR #876).
            r"\b(exchange|binance|coinbase|kraken)\b.*\b(halt|insolvency|breach|hack|outage)\b|"
            r"\b(halt|insolvency|breach|hack|outage)\b.*\b(exchange|binance|coinbase|kraken)\b|"
            r"\b(suspen\w*|halt\w*|paus\w*|freez\w*|frozen|block(?:s|ed|ing)?)\b[^.]{0,40}\bwithdrawals?\b|"
            r"\bwithdrawals?\b[^.]{0,40}\b(suspen\w*|halt\w*|paus\w*|freez\w*|frozen|block(?:s|ed|ing)?)\b",
            3,
        ),
    ),
    excludes=(
        r"\bprice (prediction|analysis|target)\b", r"\bcould (reach|hit|soar)\b",
        r"\banalysts? (say|says|predict)\b", r"\bwhale\b", r"\bmemecoin\b",
        # D1 (shadow proof 2026-11-17): commentary about PAST incidents is
        # not an incident — the FalconX interview ("Binance hack may push
        # institutions to outside custody, FalconX exec says") alerted at 3.
        # Same opinion-guard family as "analysts say" above, plus the AI
        # watch's interview guard.
        r"\b(execs?|executives?|ceo|cfo|founders?|co-founders?) (says|say)\b",
        r"\binterview\b",
        # D3 (shadow proof 2026-11-17): daily roundups reach score 2 via
        # summary regulation mentions and sit one keyword from a false
        # alert; exclude the digest forms outright, as the AI watch
        # excludes newsletters.
        r"\b(roundup|recap|newsletter|digest)\b",
        r"\bwhat happened in crypto today\b",
    ),
    min_score=3,
    max_alerts_per_poll=1,
    max_alerts_per_day=3,
    baseline_max_age_hours=72,
    poll_interval_seconds=1800,
    enabled=False,  # designed; enables after its own live proof (design doc §5)
    domain="markets",
)

WATCH_INDIA_TECH_REGULATORY = WatchDefinition(
    id="india_tech_regulatory",
    title="India tech & regulatory news",
    owner_value=(
        "The owner is India-based: DPDP rules, MeitY actions, RBI/SEBI "
        "digital rules, UPI changes, and app bans land directly on his "
        "projects and accounts. Only regulator/structure items pass; "
        "general tech news does not."
    ),
    sources=(
        # Fetch-verified at design time against the ingester's curated set;
        # re-verified live 2026-11-17 before enabling (all three feeds
        # serving fresh items).
        FeedSource("https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", "Times of India"),
        FeedSource("https://inc42.com/feed/", "Inc42"),
        FeedSource("https://yourstory.com/feed", "YourStory"),
    ),
    rules=(
        ScoreRule(
            "regulator_action",
            r"\b(meity|rbi|sebi|trai|cci|dpdp|ministry of electronics)\b",
            3,
        ),
        ScoreRule(
            "rule_change",
            r"\b(draft (bill|rules)|gazette|notification|compliance|mandator|"
            r"ban(s|ned)?|block(s|ed)?|takedown|licen[cs]e)\b",
            2,
            where="title_summary",
        ),
        ScoreRule(
            "payments_structure",
            r"\b(upi|npci|payment aggregator|kyc)\b.*\b(rule|limit|change|mandat|deadline)",
            3,
        ),
    ),
    excludes=(r"\bfunding\b", r"\braises?\b", r"\bstartup\b.*\b(launch|app)\b", r"\breview\b"),
    min_score=3,
    max_alerts_per_poll=1,
    max_alerts_per_day=2,
    baseline_max_age_hours=72,
    poll_interval_seconds=3600,
    enabled=True,  # live proof passed 2026-11-15/16: 1 alert + 1 cap-suppressed, dedupe exact, zero false positives (design doc §5)
    domain="india_regulatory",
)

WATCH_PLATFORM_POLICY = WatchDefinition(
    id="platform_policy",
    title="Creator-platform policy & monetisation changes",
    owner_value=(
        "VyralX publishes on YouTube and the owner's presence runs on "
        "Meta's platforms; partner-programme, monetisation, recommendation "
        "and community-guideline changes decide what she may post and "
        "whether it earns. Product launches and creator marketing do not "
        "pass — policy only."
    ),
    sources=(
        # Fetch-verified 2026-11-18 for TASK-INT-013 (both feeds serving
        # fresh items the same day).
        FeedSource("https://blog.youtube/rss/", "YouTube Official Blog"),
        FeedSource("https://about.fb.com/news/feed/", "Meta Newsroom"),
    ),
    rules=(
        ScoreRule(
            "policy_surface",
            r"\b(partner program(me)?|monetization|monetisation|community "
            r"guidelines|community standards|recommendation guidelines|"
            r"content polic\w+|copyright polic\w+|policies)\b",
            3,
        ),
        ScoreRule("recommendation_system", r"\brecommend\w*\b", 2),
        ScoreRule(
            "change_language",
            r"\b(chang(e|es|ing|ed)|updat(e|es|ing|ed)|new (rule|policy|"
            r"requirement|guideline)s?|eligibility|enforcement|"
            r"demonetiz\w+|demonetis\w+|takedown)\b",
            2,
            where="title_summary",
        ),
        ScoreRule(
            "platform_name",
            r"\b(youtube|instagram|facebook|meta|shorts|reels)\b",
            1,
        ),
    ),
    excludes=(
        r"\bsurvey\w*\b", r"\bpodcast\b", r"\bwebinar\b", r"\brecap\b",
        r"\bsponsored\b", r"\bcelebrat\w+\b", r"\bawards?\b",
    ),
    min_score=4,
    max_alerts_per_poll=1,
    max_alerts_per_day=2,
    baseline_max_age_hours=72,
    poll_interval_seconds=3600,
    enabled=False,  # designed (TASK-INT-013); enables after its own live proof
    domain="platforms_policy",
)

WATCH_FLEET_TOOLS = WatchDefinition(
    id="fleet_tools",
    title="Fleet tools & infrastructure changes",
    owner_value=(
        "Every agent in the Universe is Python on GitHub: CPython security "
        "releases, end-of-life notices and GitHub platform deprecations land "
        "directly on the fleet's runtime and CI. Language-summit talks, "
        "elections and pre-releases do not pass."
    ),
    sources=(
        # Fetch-verified 2026-11-18 for TASK-INT-013 (both feeds serving
        # fresh items the same day; Python Insider carried the 3.12.16
        # security release the fleet's cutover depends on).
        FeedSource("https://blog.python.org/feeds/posts/default", "Python Insider"),
        FeedSource("https://github.blog/feed/", "GitHub Blog"),
    ),
    rules=(
        ScoreRule(
            "security_event",
            r"\b(vulnerabilit\w+|authentication bypass|compromised|"
            r"security advisory|cve-\d{4})\b",
            3,
        ),
        ScoreRule(
            "platform_breaking",
            r"\b(deprecat\w+|sunset|breaking change|end[- ]of[- ]life)\b",
            3,
        ),
        ScoreRule("python_version", r"\bpython 3\.\d+(\.\d+)?\b", 2),
        ScoreRule(
            "release_event",
            r"\b(security (release|update|advisory|fix)|are out|"
            r"now available|is here|released|final release)\b",
            2,
            where="title_summary",
        ),
        ScoreRule(
            "infra_name",
            r"\b(python\.org|pypi|cpython|github)\b",
            1,
            where="title_summary",
        ),
    ),
    excludes=(
        r"\balpha\b", r"\bbeta\b", r"\bcandidate\b", r"\bpreview\b",
        r"\bsummit\b", r"\blightning talks\b", r"\belection\b",
        r"\bnominations?\b", r"\bsponsors?\b",
    ),
    min_score=4,
    max_alerts_per_poll=1,
    max_alerts_per_day=2,
    baseline_max_age_hours=72,
    poll_interval_seconds=3600,
    enabled=False,  # designed (TASK-INT-013); enables after its own live proof
    domain="tools_infra",
)

WATCH_WORLD_EVENTS = WatchDefinition(
    id="world_events",
    title="World events with fleet impact",
    owner_value=(
        "Submarine-cable cuts, large Internet or cloud outages, major cyber "
        "events, disasters and escalations can take fleet infrastructure, "
        "exchanges or the owner's connectivity down with no warning. Only "
        "events with that blast radius pass; general world news, opinion "
        "and sport do not."
    ),
    sources=(
        # Fetch-verified 2026-11-18 for TASK-INT-013 (feed serving fresh
        # items the same day). BBC World was the first choice but its feed
        # could not be verified from the build environment, so it is not
        # shipped on faith.
        FeedSource("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera"),
    ),
    rules=(
        ScoreRule(
            "infra_outage",
            r"\b(outage|blackout|internet shutdown|undersea cable|"
            r"submarine cable|data ?cent(re|er) fire|offline across)\b",
            3,
        ),
        ScoreRule(
            "cyber_event",
            r"\b(cyberattack|cyber attack|ransomware|internet disruption|ddos)\b",
            3,
        ),
        ScoreRule(
            "disaster",
            r"\b(earthquake|tsunami|hurricane|cyclone|typhoon|wildfire|floods?)\b",
            2,
        ),
        ScoreRule(
            "escalation",
            r"\b(missile strike|airstrikes?|blockade|invasion|"
            r"ceasefire\b[^.]{0,30}\bcollaps\w+)\b",
            2,
        ),
        ScoreRule(
            "impact_scale",
            r"\b(millions? (without|lose|left)|power grid|state of "
            r"emergency|evacuat\w+|death toll|without (power|internet|"
            r"electricity))\b",
            2,
            where="title_summary",
        ),
        ScoreRule("sanctions", r"\bsanctions\b", 2, where="title_summary"),
    ),
    excludes=(
        # Denials and commentary about an event are not the event (the
        # crypto watch's D1 lesson, applied here from day one).
        r"\brules out\b", r"\bdenies\b", r"\bdenied\b",
        r"\bopinion\b", r"\bpodcast\b", r"\binterview\b", r"\bexplainer\b",
    ),
    min_score=4,
    max_alerts_per_poll=1,
    max_alerts_per_day=2,
    baseline_max_age_hours=72,
    poll_interval_seconds=1800,
    enabled=False,  # designed (TASK-INT-013); enables after its own live proof
    domain="world_events",
)

WATCHES: dict[str, WatchDefinition] = {
    w.id: w
    for w in (
        WATCH_AI_MODEL_RELEASES,
        WATCH_CRYPTO_MARKET_STRUCTURE,
        WATCH_INDIA_TECH_REGULATORY,
        WATCH_PLATFORM_POLICY,
        WATCH_FLEET_TOOLS,
        WATCH_WORLD_EVENTS,
    )
}


# ---------------------------------------------------------------------------
# Feed items and parsing (RSS 2.0 + Atom, namespace-tolerant)
# ---------------------------------------------------------------------------


@dataclass
class FeedItem:
    url: str
    title: str
    summary: str
    published_at: datetime | None
    publisher: str
    source_feed: str


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(el: ET.Element, name: str) -> str:
    for child in el:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return _WS.sub(" ", text).strip()


def parse_feed(xml_bytes: bytes, source: FeedSource) -> list[FeedItem]:
    """Parse one RSS/Atom document into FeedItems. Never raises on bad XML."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        logger.warning("[Watch] Unparseable feed from %s", source.publisher)
        return []
    items: list[FeedItem] = []
    for el in root.iter():
        kind = _local(el.tag)
        if kind == "item":  # RSS 2.0
            url = _child_text(el, "link") or _child_text(el, "guid")
            title = _clean(_child_text(el, "title"))
            summary = _clean(_child_text(el, "description"))
            published = _parse_date(_child_text(el, "pubdate") or _child_text(el, "date"))
        elif kind == "entry":  # Atom
            url = ""
            for child in el:
                if _local(child.tag) == "link":
                    href = child.get("href") or ""
                    rel = child.get("rel") or "alternate"
                    if href and rel in ("alternate", ""):
                        url = href
                        break
                    url = url or href
            title = _clean(_child_text(el, "title"))
            summary = _clean(_child_text(el, "summary") or _child_text(el, "content"))
            published = _parse_date(
                _child_text(el, "published") or _child_text(el, "updated")
            )
        else:
            continue
        if url.startswith("http") and title:
            items.append(
                FeedItem(
                    url=url,
                    title=title,
                    summary=summary[:600],
                    published_at=published,
                    publisher=source.publisher,
                    source_feed=source.url,
                )
            )
    return items


# ---------------------------------------------------------------------------
# Fingerprints and dedupe
# ---------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    netloc = host
    if parts.port and parts.port not in (80, 443):
        netloc = f"{host}:{parts.port}"
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    query = urlencode(sorted(params))
    return urlunsplit((parts.scheme.lower() or "https", netloc, path, query, ""))


def url_fingerprint(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    return _WS.sub(" ", re.sub(r"[^a-z0-9 ]", " ", title.lower())).strip()


def title_fingerprint(title: str) -> str | None:
    """Cross-post dedupe key; None for titles too generic to trust."""
    norm = normalize_title(title)
    if len(norm) < TITLE_DEDUPE_MIN_CHARS:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Significance scoring (deterministic; every point is explained)
# ---------------------------------------------------------------------------


def score_item(watch: WatchDefinition, item: FeedItem) -> tuple[int, list[str], bool]:
    title_l = item.title.lower()
    for pattern in watch.excludes:
        if re.search(pattern, title_l):
            return 0, [f"excluded:{pattern}"], True
    haystacks = {"title": title_l, "title_summary": f"{title_l} {item.summary.lower()}"}
    score, reasons = 0, []
    for rule in watch.rules:
        if re.search(rule.pattern, haystacks[rule.where]):
            score += rule.weight
            reasons.append(f"{rule.name}:+{rule.weight}")
    return score, reasons, False


# ---------------------------------------------------------------------------
# Persistent seen-store (JSON file, atomic replace, pruned)
# ---------------------------------------------------------------------------


class SeenStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"version": STATE_VERSION, "watches": {}}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if loaded.get("version") == STATE_VERSION:
                    self.data = loaded
            except (json.JSONDecodeError, OSError):
                logger.warning("[Watch] Seen-store unreadable; starting fresh: %s", path)

    def section(self, watch_id: str) -> dict[str, Any]:
        return self.data["watches"].setdefault(
            watch_id, {"seen": {}, "title_fps": {}, "alerts_by_day": {}}
        )

    def mark(
        self,
        watch_id: str,
        item: FeedItem,
        status: str,
        *,
        fired_at: datetime | None = None,
    ) -> None:
        section = self.section(watch_id)
        fp = url_fingerprint(item.url)
        section["seen"][fp] = {
            "status": status,
            "title": item.title,
            "url": item.url,
            "first_seen": datetime.now(UTC).isoformat(),
            "fired_at": fired_at.isoformat() if fired_at else None,
        }
        tfp = title_fingerprint(item.title)
        if tfp:
            section["title_fps"][tfp] = fp
        if status == "alerted" and fired_at is not None:
            day = fired_at.astimezone(IST).date().isoformat()
            section["alerts_by_day"][day] = section["alerts_by_day"].get(day, 0) + 1

    def alerts_today(self, watch_id: str, now: datetime) -> int:
        day = now.astimezone(IST).date().isoformat()
        return int(self.section(watch_id)["alerts_by_day"].get(day, 0))

    def save(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=PRUNE_DAYS)
        for section in self.data["watches"].values():
            seen = section.get("seen", {})
            for fp in [
                fp
                for fp, rec in seen.items()
                if rec.get("status") not in ("alerted", "suppressed_budget")
                and (rec.get("first_seen") or "") < cutoff.isoformat()
            ]:
                del seen[fp]
            live = set(seen)
            section["title_fps"] = {
                t: f for t, f in section.get("title_fps", {}).items() if f in live
            }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)


# ---------------------------------------------------------------------------
# Alert outbox (JSONL envelopes for TASK-PRO-001 to drain and deliver)
# ---------------------------------------------------------------------------


class Outbox:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, envelope: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, ensure_ascii=False) + "\n")


def build_envelope(
    watch: WatchDefinition, item: FeedItem, score: int, reasons: list[str], now: datetime
) -> dict[str, Any]:
    fp = url_fingerprint(item.url)
    return {
        "schema": ENVELOPE_SCHEMA,
        "envelope_id": hashlib.sha256(f"{watch.id}:{fp}".encode()).hexdigest(),
        "dedupe_key": f"intelx.watch:{watch.id}:{fp[:16]}",
        "watch_id": watch.id,
        "domain": watch.domain,
        "severity": "info",
        "quiet_hours_exempt": False,
        "title": item.title,
        "summary": item.summary[:300],
        "url": item.url,
        "publisher": item.publisher,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "fired_at": now.isoformat(),
        "score": score,
        "score_reasons": reasons,
        "provenance": {
            "source_feed": item.source_feed,
            "fetched_at": now.isoformat(),
            "task": "TASK-INT-007",
        },
    }


# ---------------------------------------------------------------------------
# Fetching (injectable; stdlib default)
# ---------------------------------------------------------------------------


class Fetcher(Protocol):
    async def fetch(self, url: str) -> tuple[int, bytes]: ...


class UrllibFetcher:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def fetch(self, url: str) -> tuple[int, bytes]:
        return await asyncio.to_thread(self._fetch_sync, url)

    def _fetch_sync(self, url: str) -> tuple[int, bytes]:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "IntelX-Watch/1.0 (FRIDAY Universe; TASK-INT-007)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, b""
        except (urllib.error.URLError, TimeoutError, OSError):
            return 0, b""


# ---------------------------------------------------------------------------
# The watch service
# ---------------------------------------------------------------------------


@dataclass
class PollResult:
    watch_id: str
    fetched: int = 0
    duplicates: int = 0
    baselined: int = 0
    below_threshold: int = 0
    suppressed_budget: list[dict[str, Any]] = field(default_factory=list)
    alerted: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "watch_id": self.watch_id,
            "fetched": self.fetched,
            "duplicates": self.duplicates,
            "baselined": self.baselined,
            "below_threshold": self.below_threshold,
            "suppressed_budget": self.suppressed_budget,
            "alerted": self.alerted,
            "errors": self.errors,
        }


def default_state_path() -> Path:
    return Path(os.environ.get("INTELX_WATCH_STATE_PATH", "./data/watches/state.json"))


def default_outbox_path() -> Path:
    return Path(os.environ.get("INTELX_WATCH_OUTBOX_PATH", "./data/watches/outbox.jsonl"))


class WatchService:
    def __init__(
        self,
        *,
        state_path: Path | None = None,
        outbox_path: Path | None = None,
        fetcher: Fetcher | None = None,
    ) -> None:
        self.store = SeenStore(state_path or default_state_path())
        self.outbox = Outbox(outbox_path or default_outbox_path())
        self.fetcher = fetcher or UrllibFetcher()

    async def poll_once(
        self, watch: WatchDefinition, *, now: datetime | None = None
    ) -> PollResult:
        now = now or datetime.now(UTC)
        result = PollResult(watch_id=watch.id)
        section = self.store.section(watch.id)
        first_run = not section["seen"]

        items: list[FeedItem] = []
        for source in watch.sources:
            try:
                status, payload = await self.fetcher.fetch(source.url)
                if status != 200 or not payload:
                    result.errors.append(f"{source.publisher}: HTTP {status}")
                    continue
                items.extend(parse_feed(payload, source))
            except Exception as err:  # a dead feed must not kill the watch
                result.errors.append(f"{source.publisher}: {err!r}")
        result.fetched = len(items)

        baseline_cutoff = now - timedelta(hours=watch.baseline_max_age_hours)
        candidates: list[tuple[FeedItem, int, list[str]]] = []
        for item in items:
            fp = url_fingerprint(item.url)
            tfp = title_fingerprint(item.title)
            if fp in section["seen"] or (tfp and tfp in section["title_fps"]):
                result.duplicates += 1
                continue
            if first_run and (
                item.published_at is None or item.published_at < baseline_cutoff
            ):
                self.store.mark(watch.id, item, "baseline")
                result.baselined += 1
                continue
            score, reasons, excluded = score_item(watch, item)
            if excluded or score < watch.min_score:
                self.store.mark(
                    watch.id, item, "excluded" if excluded else "below_threshold"
                )
                result.below_threshold += 1
                continue
            candidates.append((item, score, reasons))

        candidates.sort(
            key=lambda c: c[0].published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        budget_left = watch.max_alerts_per_day - self.store.alerts_today(watch.id, now)
        allowance = max(0, min(watch.max_alerts_per_poll, budget_left))
        for idx, (item, score, reasons) in enumerate(candidates):
            if idx < allowance:
                envelope = build_envelope(watch, item, score, reasons, now)
                self.outbox.append(envelope)
                self.store.mark(watch.id, item, "alerted", fired_at=now)
                result.alerted.append(envelope)
            else:
                self.store.mark(watch.id, item, "suppressed_budget")
                result.suppressed_budget.append(
                    {"title": item.title, "url": item.url, "score": score}
                )
        self.store.save()
        logger.info(
            "[Watch:%s] fetched=%d alerted=%d suppressed=%d dup=%d baseline=%d below=%d",
            watch.id,
            result.fetched,
            len(result.alerted),
            len(result.suppressed_budget),
            result.duplicates,
            result.baselined,
            result.below_threshold,
        )
        return result


class WatchRunner:
    """Background loop over enabled watches; mirrors NewsIngester's shape."""

    def __init__(
        self,
        service: WatchService | None = None,
        *,
        domains: set[str] | None = None,
    ) -> None:
        self.service = service or WatchService()
        # TASK-INT-013: a runner can be scoped to a set of domains (e.g. a
        # second process that owns only the new domains while they prove
        # themselves). None = every domain, the historical behaviour.
        self.domains = domains
        self._task: asyncio.Task | None = None
        self._running = False

    async def _loop(self) -> None:
        enabled = [
            w
            for w in WATCHES.values()
            if w.enabled and (self.domains is None or w.domain in self.domains)
        ]
        logger.info(
            "[WatchRunner] Standing watches started: %s",
            ", ".join(w.id for w in enabled) or "(none enabled)",
        )
        while self._running:
            for watch in enabled:
                try:
                    await self.service.poll_once(watch)
                except Exception:
                    logger.exception("[WatchRunner] Poll failed for %s", watch.id)
            if self._running:
                await asyncio.sleep(min(w.poll_interval_seconds for w in enabled))

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        logger.info("[WatchRunner] Stopped.")


def with_overrides(watch: WatchDefinition, **overrides: Any) -> WatchDefinition:
    """Return a copy of a watch definition with config overrides (ops/proofs)."""
    return replace(watch, **overrides)
