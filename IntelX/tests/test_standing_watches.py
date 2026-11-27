"""Tests for IntelX standing research watches (TASK-INT-007).

The watch engine is standard-library only, so these tests import it
directly and drive it with a fake fetcher — no network, no database.
The live-fire proof against the real feeds is recorded on issue #35.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from pathlib import Path

from intelx.watches.engine import (
    WATCHES,
    WATCH_AI_MODEL_RELEASES,
    WATCH_CRYPTO_MARKET_STRUCTURE,
    FeedSource,
    WatchService,
    normalize_url,
    parse_feed,
    score_item,
    url_fingerprint,
    with_overrides,
)

NOW = datetime(2026, 11, 15, 8, 0, tzinfo=UTC)

RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Example RSS</title>
<item><title>Introducing GPT-9 Turbo for developers via the API</title>
<link>https://example.com/gpt9-turbo</link>
<description>The newest model is here.</description>
<pubDate>Sat, 15 Nov 2026 06:00:00 GMT</pubDate></item>
<item><title>Claude Opus 9.1 is now available in the API</title>
<link>https://example.com/claude-opus-91</link>
<description>Our most capable model yet.</description>
<pubDate>Sat, 15 Nov 2026 05:00:00 GMT</pubDate></item>
<item><title>Our podcast: a conversation about AI safety</title>
<link>https://example.com/podcast-12</link>
<description>Listen in.</description>
<pubDate>Sat, 15 Nov 2026 04:00:00 GMT</pubDate></item>
<item><title>How we built our new office</title>
<link>https://example.com/office</link>
<description>Desks and plants.</description>
<pubDate>Sat, 15 Nov 2026 03:00:00 GMT</pubDate></item>
<item><title>Weekly research notes</title>
<link>https://example.com/notes-oct</link>
<description>Old post from October.</description>
<pubDate>Wed, 01 Oct 2026 03:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Example Atom</title>
<entry><title>Gemini 9 now available to developers everywhere</title>
<link href="https://example.org/gemini-9"/>
<summary>Try it in the API today.</summary>
<published>2026-11-15T04:00:00Z</published></entry>
</feed>"""

CROSSPOST_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Syndication</title>
<item><title>Introducing GPT-9 Turbo for developers via the API</title>
<link>https://mirror.example.net/story/12345</link>
<description>Same announcement, syndicated.</description>
<pubDate>Sat, 15 Nov 2026 07:00:00 GMT</pubDate></item>
</channel></rss>"""


class FakeFetcher:
    def __init__(self, mapping: dict[str, tuple[int, bytes]]) -> None:
        self.mapping = mapping

    async def fetch(self, url: str) -> tuple[int, bytes]:
        return self.mapping.get(url, (404, b""))


def fixture_watch(fetcher_map_extra: dict | None = None):
    return with_overrides(
        WATCH_AI_MODEL_RELEASES,
        sources=(
            FeedSource("https://feed.example/rss.xml", "Example RSS"),
            FeedSource("https://feed.example/atom.xml", "Example Atom"),
        ),
    )


def fixture_fetcher() -> FakeFetcher:
    return FakeFetcher(
        {
            "https://feed.example/rss.xml": (200, RSS_FEED),
            "https://feed.example/atom.xml": (200, ATOM_FEED),
        }
    )


def make_service(tmp_path: Path, fetcher: FakeFetcher) -> WatchService:
    return WatchService(
        state_path=tmp_path / "state.json",
        outbox_path=tmp_path / "outbox.jsonl",
        fetcher=fetcher,
    )


def poll(service: WatchService, watch, now: datetime = NOW):
    return asyncio.run(service.poll_once(watch, now=now))


# --- parsing -----------------------------------------------------------------


def test_parse_rss_items() -> None:
    items = parse_feed(RSS_FEED, FeedSource("https://feed.example/rss.xml", "Example RSS"))
    assert len(items) == 5
    assert items[0].title.startswith("Introducing GPT-9")
    assert items[0].published_at == datetime(2026, 11, 15, 6, 0, tzinfo=UTC)
    assert items[0].publisher == "Example RSS"


def test_parse_atom_items() -> None:
    items = parse_feed(ATOM_FEED, FeedSource("https://feed.example/atom.xml", "Example Atom"))
    assert len(items) == 1
    assert items[0].url == "https://example.org/gemini-9"
    assert items[0].published_at == datetime(2026, 11, 15, 4, 0, tzinfo=UTC)


def test_parse_garbage_returns_empty() -> None:
    assert parse_feed(b"not xml at all", FeedSource("https://x", "X")) == []


# --- fingerprints --------------------------------------------------------------


def test_normalize_url_strips_tracking_and_fragment() -> None:
    messy = "HTTPS://Example.COM/Post/?utm_source=tw&ref=hn&keep=1#frag"
    assert normalize_url(messy) == "https://example.com/Post?keep=1"


def test_fingerprint_stable_across_tracking_params() -> None:
    a = url_fingerprint("https://example.com/gpt9-turbo?utm_campaign=x")
    b = url_fingerprint("https://example.com/gpt9-turbo/")
    assert a == b


# --- scoring -------------------------------------------------------------------


def _item(title: str, summary: str = ""):
    from intelx.watches.engine import FeedItem

    return FeedItem(
        url="https://example.com/x",
        title=title,
        summary=summary,
        published_at=NOW,
        publisher="Test",
        source_feed="https://feed.example/rss.xml",
    )


def test_score_release_title_passes() -> None:
    score, reasons, excluded = score_item(
        WATCH_AI_MODEL_RELEASES, _item("Introducing GPT-9 Turbo for developers via the API")
    )
    assert not excluded and score >= WATCH_AI_MODEL_RELEASES.min_score
    assert any(r.startswith("release_language") for r in reasons)


def test_score_podcast_is_excluded() -> None:
    _, _, excluded = score_item(
        WATCH_AI_MODEL_RELEASES, _item("Our podcast: a conversation about AI safety")
    )
    assert excluded


def test_score_plain_post_below_threshold() -> None:
    score, _, excluded = score_item(
        WATCH_AI_MODEL_RELEASES, _item("How we built our new office", "Desks and plants.")
    )
    assert not excluded and score < WATCH_AI_MODEL_RELEASES.min_score


# --- poll semantics --------------------------------------------------------------


def test_first_poll_alerts_once_suppresses_rest(tmp_path: Path) -> None:
    service = make_service(tmp_path, fixture_fetcher())
    result = poll(service, fixture_watch())
    assert result.fetched == 6
    assert len(result.alerted) == 1  # per-poll cap is 1
    assert result.alerted[0]["title"].startswith("Introducing GPT-9")
    assert len(result.suppressed_budget) == 2  # Claude + Gemini wait, counted
    assert result.baselined == 1  # the October post, silently recorded
    assert result.below_threshold == 2  # podcast (excluded) + office post
    env = result.alerted[0]
    assert env["schema"] == "intelx.watch_alert/1"
    assert env["dedupe_key"].startswith("intelx.watch:ai_model_releases:")
    # TASK-INT-015 supersedes the v1 pin that stood here (quiet_hours_exempt
    # False / severity "info" for every alert): the owner's alert policy —
    # instant for big breaks, digest for the rest — makes a frontier release
    # like this fixture (score 8, over the watch's instant bar of 6)
    # instant-class by design. Digest-class envelopes keep the v1 values;
    # they are pinned in test_int015_alert_policy.py.
    assert env["alert_class"] == "instant"
    assert env["quiet_hours_exempt"] is True
    assert env["severity"] == "high"
    assert env["score"] >= WATCH_AI_MODEL_RELEASES.min_score


def test_second_poll_is_silent_and_state_persists(tmp_path: Path) -> None:
    fetcher = fixture_fetcher()
    poll(make_service(tmp_path, fetcher), fixture_watch())
    # A brand-new service over the same state file must see the same world.
    result = poll(make_service(tmp_path, fetcher), fixture_watch())
    assert result.alerted == []
    assert result.suppressed_budget == []
    assert result.duplicates == 6


def test_title_fingerprint_catches_crosspost(tmp_path: Path) -> None:
    fetcher = fixture_fetcher()
    poll(make_service(tmp_path, fetcher), fixture_watch())
    fetcher.mapping["https://feed.example/rss.xml"] = (200, CROSSPOST_RSS)
    result = poll(make_service(tmp_path, fetcher), fixture_watch())
    assert result.alerted == []
    assert result.duplicates >= 1  # same long title, different URL/publisher


def test_daily_budget_blocks_later_polls(tmp_path: Path) -> None:
    watch = with_overrides(
        fixture_watch(), max_alerts_per_poll=5, max_alerts_per_day=1
    )
    fetcher = fixture_fetcher()
    service = make_service(tmp_path, fetcher)
    first = poll(service, watch)
    assert len(first.alerted) == 1  # daily cap, not the per-poll cap of 5
    extra = RSS_FEED.replace(b"gpt9-turbo", b"gpt10-ultra").replace(
        b"Introducing GPT-9 Turbo", b"Introducing GPT-10 Ultra"
    )
    fetcher.mapping["https://feed.example/rss.xml"] = (200, extra)
    second = poll(service, watch)
    assert second.alerted == []
    assert any("GPT-10" in s["title"] for s in second.suppressed_budget)


def test_feed_error_does_not_kill_poll(tmp_path: Path) -> None:
    fetcher = fixture_fetcher()
    fetcher.mapping["https://feed.example/atom.xml"] = (500, b"")
    result = poll(make_service(tmp_path, fetcher), fixture_watch())
    assert any("HTTP 500" in e for e in result.errors)
    assert result.fetched == 5  # the healthy feed still processed


def test_enabled_watch_set_is_pinned() -> None:
    # Exactly the watches with a passed live proof may be enabled
    # (STANDING_WATCHES.md §5). india_tech_regulatory passed its proof
    # 2026-11-15/16; crypto_market_structure has not, so it stays off.
    enabled = {w.id for w in WATCHES.values() if w.enabled}
    assert enabled == {"ai_model_releases", "india_tech_regulatory"}
    assert WATCHES["crypto_market_structure"].enabled is False


def test_outbox_is_jsonl(tmp_path: Path) -> None:
    service = make_service(tmp_path, fixture_fetcher())
    poll(service, fixture_watch())
    lines = (tmp_path / "outbox.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert envelope["watch_id"] == "ai_model_releases"
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    seen = state["watches"]["ai_model_releases"]["seen"]
    assert sum(1 for r in seen.values() if r["status"] == "alerted") == 1


# --- suppression ordering (TASK-INT-879) ---------------------------------------
#
# The INT-876 soak's day-7 anomaly: a score-5 item (UK FCA DeFi rules) was
# suppressed by budget while a newer score-3 item (Binance withdrawals
# restored) alerted. Budget allocation is now score-first — the highest
# score takes the per-poll slot — with ties broken newest-first (the v1
# behaviour within equal scores). The burst below replays the exact day-7
# items, with their live scores, against the crypto watch.

CRYPTO_BURST_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Crypto burst</title>
<item><title>Binance says customer withdrawals are fully restored, four weeks after the $6.3 billion hack</title>
<link>https://example.com/binance-restored</link>
<description>Withdrawals are fully restored.</description>
<pubDate>Fri, 27 Nov 2026 04:45:47 GMT</pubDate></item>
<item><title>UK regulator plans tighter DeFi rules, citing $6.3B Binance hack: Report</title>
<link>https://example.com/uk-defi-rules</link>
<description>The UK regulator plans tighter DeFi rules.</description>
<pubDate>Thu, 26 Nov 2026 18:00:00 GMT</pubDate></item>
<item><title>South Korean crypto exchange Bithumb warns of phishing after deeper October breach probe</title>
<link>https://example.com/bithumb-phishing</link>
<description>Bithumb warns of phishing after a deeper probe.</description>
<pubDate>Wed, 25 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""

CRYPTO_INSTANT_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Crypto instant burst</title>
<item><title>SEC approves spot Bitcoin ETF as Binance lists new margin contracts</title>
<link>https://example.com/sec-etf-binance</link>
<description>The SEC approved the ETF as Binance lists new contracts.</description>
<pubDate>Wed, 25 Nov 2026 09:00:00 GMT</pubDate></item>
<item><title>Binance says customer withdrawals are fully restored, four weeks after the $6.3 billion hack</title>
<link>https://example.com/binance-restored</link>
<description>Withdrawals are fully restored.</description>
<pubDate>Fri, 27 Nov 2026 04:45:47 GMT</pubDate></item>
</channel></rss>"""

BURST_NOW = datetime(2026, 11, 27, 8, 0, tzinfo=UTC)


def crypto_burst_watch():
    return with_overrides(
        WATCH_CRYPTO_MARKET_STRUCTURE,
        sources=(FeedSource("https://feed.example/crypto.xml", "Crypto Burst"),),
    )


def crypto_burst_fetcher(feed: bytes = CRYPTO_BURST_RSS) -> FakeFetcher:
    return FakeFetcher({"https://feed.example/crypto.xml": (200, feed)})


def test_burst_item_scores_are_pinned() -> None:
    # The fixture's scores are the day-7 live scores (INT-877 §2): the UK
    # item scores 5 (regulation 2 + venue_incident 3), the other two 3
    # (venue_incident). If a rule changes, this fails first, loudly.
    items = parse_feed(
        CRYPTO_BURST_RSS, FeedSource("https://feed.example/crypto.xml", "Crypto Burst")
    )
    assert len(items) == 3
    scores = {item.title: score_item(WATCH_CRYPTO_MARKET_STRUCTURE, item)[0] for item in items}
    assert scores["UK regulator plans tighter DeFi rules, citing $6.3B Binance hack: Report"] == 5
    assert scores["Binance says customer withdrawals are fully restored, four weeks after the $6.3 billion hack"] == 3
    assert scores["South Korean crypto exchange Bithumb warns of phishing after deeper October breach probe"] == 3


def test_burst_highest_score_alerts_despite_newer_lower_score(tmp_path: Path) -> None:
    # Day-7 replay: the older score-5 UK item must take the single slot
    # ahead of the newer score-3 Binance item. Under the old newest-first
    # sort this test fails (the score-3 item alerts instead).
    service = make_service(tmp_path, crypto_burst_fetcher())
    result = poll(service, crypto_burst_watch(), now=BURST_NOW)
    assert result.fetched == 3
    assert len(result.alerted) == 1
    assert result.alerted[0]["title"].startswith("UK regulator")
    assert result.alerted[0]["score"] == 5
    suppressed = {s["title"] for s in result.suppressed_budget}
    assert len(suppressed) == 2
    assert any(t.startswith("Binance says") for t in suppressed)
    assert any(t.startswith("South Korean") for t in suppressed)


def test_burst_equal_scores_break_ties_newest_first(tmp_path: Path) -> None:
    # Both candidates score 3; the newer one keeps the v1 behaviour and
    # takes the slot. Guards against overcorrecting into score-only order.
    feed = CRYPTO_BURST_RSS.replace(
        b"<item><title>UK regulator plans tighter DeFi rules, citing $6.3B Binance hack: Report</title>\n<link>https://example.com/uk-defi-rules</link>\n<description>The UK regulator plans tighter DeFi rules.</description>\n<pubDate>Thu, 26 Nov 2026 18:00:00 GMT</pubDate></item>\n",
        b"",
    )
    service = make_service(tmp_path, crypto_burst_fetcher(feed))
    result = poll(service, crypto_burst_watch(), now=BURST_NOW)
    assert result.fetched == 2
    assert len(result.alerted) == 1
    assert result.alerted[0]["title"].startswith("Binance says")
    assert result.alerted[0]["score"] == 3
    assert len(result.suppressed_budget) == 1
    assert result.suppressed_budget[0]["title"].startswith("South Korean")


def test_burst_instant_class_never_loses_slot_to_digest(tmp_path: Path) -> None:
    # Score-8 instant item (etf_decision 3 + exchange_structure 3 +
    # regulation 2; over the watch's instant bar of 6) is the oldest; the
    # newer score-3 digest item must not take its slot.
    service = make_service(tmp_path, crypto_burst_fetcher(CRYPTO_INSTANT_RSS))
    result = poll(service, crypto_burst_watch(), now=BURST_NOW)
    assert result.fetched == 2
    assert len(result.alerted) == 1
    assert result.alerted[0]["title"].startswith("SEC approves")
    assert result.alerted[0]["score"] == 8
    assert result.alerted[0]["alert_class"] == "instant"
    assert result.alerted_instant == 1
    assert len(result.suppressed_budget) == 1
    assert result.suppressed_budget[0]["title"].startswith("Binance says")
