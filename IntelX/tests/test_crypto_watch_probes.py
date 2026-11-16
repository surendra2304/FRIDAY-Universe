"""Regression battery for the crypto_market_structure watch definition.

The 21 headlines below are the probe battery from the TASK-INT-007
sandbox proof (issue #35; ~/workspace/intelx-watches-proof,
runs/crypto_market_structure/probes.json), scored with the engine's own
score_item(). The proof found two definition defects, both fixed here:

1. etf_decision's verb-before-ETF branch used the stem
   ``(approv|reject)s?\\b`` — the trailing ``s?\\b`` can never match
   "approves" / "approved" / "rejected" (an "e" follows the stem), so
   the canonical wire phrasing of an ETF decision scored regulation-only
   (2 < min_score 3) and never alerted. The branch now uses the bare
   stem, exactly as the ETF-first branch already did.
2. exchange_structure only matched listing-verb BEFORE venue, so
   venue-first headlines — the dominant wire order for listings and
   delistings ("Binance to delist three tokens next week") — scored 0.
   A mirrored venue-first alternative now covers them.

The battery also pins the cases that must NOT move: price-chatter
headlines stay excluded at 0, a regulation-only headline stays at 2
(below the bar), and every previously-firing phrasing keeps its score,
so the fixes cannot over-fire. The watch itself stays enabled=False —
enablement is gated on the PRO-001 outbox drainer, not on this battery.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from intelx.watches.engine import (
    WATCH_CRYPTO_MARKET_STRUCTURE,
    FeedItem,
    score_item,
)

UTC = timezone.utc
NOW = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)
WATCH = WATCH_CRYPTO_MARKET_STRUCTURE


def _item(title: str) -> FeedItem:
    return FeedItem(
        url="https://example.com/x",
        title=title,
        summary="",
        published_at=NOW,
        publisher="Test",
        source_feed="https://feed.example/rss.xml",
    )


# (title, expected score, expected excluded, expected scoring rules)
# Scores are the POST-FIX expectations; the proof's pre-fix scores are
# noted where the fix changed them (2 -> 5 for ETF verb-first,
# 0 -> 3 for venue-first listings/delistings).
BATTERY = [
    # etf_decision — verb BEFORE etf (canonical wire phrasing)
    ("SEC approves spot Bitcoin ETF in landmark decision", 5, False, {"etf_decision", "regulation"}),  # was 2
    ("SEC approved the first spot Bitcoin ETF", 5, False, {"etf_decision", "regulation"}),  # was 2
    ("SEC rejects spot Ethereum ETF application", 5, False, {"etf_decision", "regulation"}),
    ("SEC rejected the spot Ethereum ETF application", 5, False, {"etf_decision", "regulation"}),  # was 2
    # etf_decision — verb AFTER etf (already fired before the fix)
    ("Bitcoin ETF approved by SEC, trading starts Tuesday", 5, False, {"etf_decision", "regulation"}),
    ("Spot Ethereum ETF approval granted by SEC", 5, False, {"etf_decision", "regulation"}),
    ("ETF decision delayed again as SEC extends review", 5, False, {"etf_decision", "regulation"}),
    ("BlackRock ETF filing for Solana fund confirmed", 3, False, {"etf_decision"}),
    # exchange_structure — venue-first (missed before the fix)
    ("Coinbase lists new token for US customers", 3, False, {"exchange_structure"}),  # was 0
    ("Binance to delist three tokens next week", 3, False, {"exchange_structure"}),  # was 0
    ("Binance announces delisting of three tokens", 3, False, {"exchange_structure"}),  # was 0
    ("Coinbase to delist two tokens in December", 3, False, {"exchange_structure"}),  # was 0
    ("Binance will list a new token on Friday", 3, False, {"exchange_structure"}),  # was 0
    # exchange_structure — verb-first / leverage (already fired)
    ("Binance delisting notice: three pairs removed as exchange changes margin rules", 3, False, {"exchange_structure"}),
    ("New listing on Binance announced for Friday", 3, False, {"exchange_structure"}),
    ("Kraken reduces leverage limits for EU margin traders", 3, False, {"exchange_structure"}),
    # venue_incident (untouched by the fix)
    ("Binance halts withdrawals after suspected hack", 3, False, {"venue_incident"}),
    ("Major exchange outage knocks trading offline for hours", 3, False, {"venue_incident"}),
    # regulation alone stays below the bar
    ("CFTC chair warns on prediction markets in speech", 2, False, {"regulation"}),
    # price chatter stays hard-excluded at 0 (the fix must not over-fire)
    ("Analysts say Bitcoin could reach $200K this cycle", 0, True, set()),
    ("Bitcoin price prediction: bulls eye $150K", 0, True, set()),
]


@pytest.mark.parametrize(
    "title,expected_score,expected_excluded,expected_rules",
    BATTERY,
    ids=[case[0] for case in BATTERY],
)
def test_crypto_probe_battery(title, expected_score, expected_excluded, expected_rules) -> None:
    score, reasons, excluded = score_item(WATCH, _item(title))
    assert excluded is expected_excluded
    assert score == expected_score
    scoring_rules = {r.split(":", 1)[0] for r in reasons if not r.startswith("excluded:")}
    assert scoring_rules == expected_rules
    if expected_excluded:
        assert reasons and all(r.startswith("excluded:") for r in reasons)


def test_crypto_watch_stays_disabled_pending_drainer() -> None:
    # Pattern fixes do not enable the watch: enablement waits on the
    # PRO-001 outbox drainer + coordinator decision (INT-007 NO-GO).
    assert WATCH.enabled is False
    assert WATCH.min_score == 3
