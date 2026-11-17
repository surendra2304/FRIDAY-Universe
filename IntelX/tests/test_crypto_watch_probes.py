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

Second battery (below): the 2026-11-17 shadow proof ran the definition
against the live feeds with the watch disabled and found three quality
defects the first battery could not see (verdict: machinery PROVEN,
alert quality NOT PROVEN — ~/workspace/int-crypto-shadow):

D1  venue_incident fired on commentary about a PAST incident — a
    CoinTelegraph interview ("Binance hack may push institutions to
    outside custody, FalconX exec says", about a 19-day-old hack)
    scored 3 and would have alerted. The opinion excludes covered
    "analysts say" but not the "exec says" form. Fixed with an
    exec/executive/ceo/cfo/founder "says" guard + the AI watch's
    interview guard.
D2  A real in-window incident scored 0: "Lighter suspends all
    withdrawals after $10.4 million crypto exploit" (CoinDesk).
    venue_incident's venue set lacked kraken (present in
    exchange_structure) and a withdrawal suspension at an unnamed
    venue matched nothing. Fixed: venue set aligned, event-first
    mirror added, and withdrawal-suspension branches that carry an
    incident on the suspension phrase itself.
D3  A daily roundup ("Here's what happened in crypto today") reached
    score 2 via a summary regulation mention — one keyword from a
    false alert. Fixed with digest/roundup excludes mirroring the AI
    watch's newsletter guard.

The shadow items are pinned verbatim (titles + the summaries recorded
in the shadow census), together with the guards that keep each
widening from over-firing: the Lighter follow-up story stays 0, an
exec-says headline ABOUT a suspension stays excluded, and a venue's
own incident report still fires.
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


# --- Shadow-proof battery (2026-11-17; D1–D3) -------------------------------
#
# (title, summary, expected score, expected excluded, expected scoring rules)
# The first four are the shadow proof's exact census items (summaries are
# the heads recorded in the census); the rest pin the widenings' edges.


def _shadow_item(title: str, summary: str) -> FeedItem:
    return FeedItem(
        url="https://example.com/x",
        title=title,
        summary=summary,
        published_at=NOW,
        publisher="Test",
        source_feed="https://feed.example/rss.xml",
    )


SHADOW_BATTERY = [
    # D1 — the shadow would-alert: interview commentary about a
    # 19-day-old hack. Was 3 via venue_incident; now hard-excluded by
    # the "exec says" opinion guard.
    (
        "Binance hack may push institutions to outside custody, FalconX exec says",
        "FalconX’s Joshua Lim says the Binance hack could push institutions "
        "to keep crypto off exchanges and change how large investors trade in 2027.",
        0, True, set(),
    ),
    # D2 — the shadow false negative: a live venue incident at an
    # unnamed venue. Was 0; the withdrawal-suspension branch now
    # carries it to the bar on venue_incident alone.
    (
        "Lighter suspends all withdrawals after $10.4 million crypto exploit",
        "The decentralized exchange blamed a leaked trading API key and said "
        "its smart contracts were unaffected, while investigators traced funds to Hyperliquid.",
        3, False, {"venue_incident"},
    ),
    # D2 guard — the follow-up/resolution twin must NOT fire: the
    # widening carries suspensions, not recoveries.
    (
        "Lighter recovers $5M after $10M exploit linked to compromised API keys",
        "Lighter restored withdrawals after recovering approximately $5 million "
        "in USDC, while blockchain analysts traced $10.4 million in funds moved during the exploit.",
        0, False, set(),
    ),
    # F1 (supervisor review, PR #876) — the withdrawal branches' block
    # stem must not match "blockchain": a product launch is not a venue
    # incident. The closed stem block(?:s|ed|ing)? keeps blocks /
    # blocked / blocking firing while this title scores 0. On the
    # pre-F1 branch this scored 3 via venue_incident.
    (
        "New blockchain withdrawals feature launches for DeFi protocol",
        "",
        0, False, set(),
    ),
    # D3 — the daily roundup: was 2 via summary regulation; now
    # hard-excluded before scoring.
    (
        "Here’s what happened in crypto today",
        "Need to know what happened in crypto today? Here is the latest news "
        "on daily trends and events impacting Bitcoin price, blockchain, DeFi, Web3 and crypto regulation.",
        0, True, set(),
    ),
    # D2 — kraken joins the venue set (it was already in
    # exchange_structure), venue-first order.
    (
        "Kraken halts withdrawals after security breach",
        "",
        3, False, {"venue_incident"},
    ),
    # D2 — event-first wire order fires via the mirrored branch.
    (
        "Hack forces Kraken to freeze deposits",
        "",
        3, False, {"venue_incident"},
    ),
    # D2 — suspension phrasing variants at unnamed venues.
    (
        "Crypto lender pauses withdrawals amid liquidity crunch",
        "",
        3, False, {"venue_incident"},
    ),
    (
        "Withdrawals suspended at major derivatives exchange",
        "",
        3, False, {"venue_incident"},
    ),
    # D1 x D2 — commentary ABOUT a suspension is still commentary:
    # the opinion guard wins over the suspension branch.
    (
        "FalconX exec says withdrawal suspensions may spread to other exchanges",
        "",
        0, True, set(),
    ),
    # D1 — the interview guard (mirrors the AI watch's).
    (
        "Interview: Binance CEO on the future of crypto exchanges",
        "",
        0, True, set(),
    ),
    # D3 — roundup by name, even with a regulation-heavy summary.
    (
        "Crypto weekly roundup: ETF flows, listings and regulation",
        "SEC and CFTC developments led the week in crypto regulation.",
        0, True, set(),
    ),
    # Guard — a venue's own incident report is not commentary and
    # still fires.
    (
        "Coinbase confirms outage, halts trading",
        "",
        3, False, {"venue_incident"},
    ),
]


@pytest.mark.parametrize(
    "title,summary,expected_score,expected_excluded,expected_rules",
    SHADOW_BATTERY,
    ids=[case[0] for case in SHADOW_BATTERY],
)
def test_crypto_shadow_battery(title, summary, expected_score, expected_excluded, expected_rules) -> None:
    score, reasons, excluded = score_item(WATCH, _shadow_item(title, summary))
    assert excluded is expected_excluded
    assert score == expected_score
    scoring_rules = {r.split(":", 1)[0] for r in reasons if not r.startswith("excluded:")}
    assert scoring_rules == expected_rules
    if expected_excluded:
        assert reasons and all(r.startswith("excluded:") for r in reasons)


def test_crypto_patterns_fix_keeps_watch_disabled() -> None:
    # The D1–D3 fix changes patterns only — never the flag. Enablement
    # still waits on a post-fix shadow soak + coordinator decision.
    assert WATCH.enabled is False
    assert WATCH.min_score == 3
