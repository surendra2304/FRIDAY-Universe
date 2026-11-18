"""Tests for IntelX watch topic domains (TASK-INT-013).

Owner decision 2026-11-18: IntelX researches everything the Universe works
in. These tests pin the domain layer: every watch declares a registered
domain, the three INT-007 watches keep their exact operational behaviour,
and the three new domain watches (platforms_policy, tools_infra,
world_events) ship disabled with scoring tuned on real headlines from the
feeds they will poll — alerting cases and, just as important, the
near-miss cases that must stay silent.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
from pathlib import Path

from intelx.watches import domains as domains_module
from intelx.watches.domains import (
    DOMAINS,
    domains_in_use,
    validate_watch_domains,
    watches_in_domain,
)
from intelx.watches.engine import (
    WATCHES,
    WATCH_AI_MODEL_RELEASES,
    WATCH_CRYPTO_MARKET_STRUCTURE,
    WATCH_FLEET_TOOLS,
    WATCH_INDIA_TECH_REGULATORY,
    WATCH_PLATFORM_POLICY,
    WATCH_WORLD_EVENTS,
    FeedItem,
    FeedSource,
    WatchRunner,
    WatchService,
    build_envelope,
    score_item,
    with_overrides,
)

NOW = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)


def item(title: str, summary: str = "", publisher: str = "Fixture") -> FeedItem:
    return FeedItem(
        url="https://example.com/story",
        title=title,
        summary=summary,
        published_at=NOW,
        publisher=publisher,
        source_feed="https://example.com/feed",
    )


# ---------------------------------------------------------------------------
# The domain registry itself
# ---------------------------------------------------------------------------


def test_every_watch_declares_a_registered_non_general_domain():
    assert validate_watch_domains(WATCHES) == []
    for watch in WATCHES.values():
        assert watch.domain in DOMAINS
        assert watch.domain != "general", f"{watch.id} has no declared domain"


def test_all_six_real_domains_are_in_use():
    assert domains_in_use(WATCHES) == [
        "markets",
        "ai_models",
        "india_regulatory",
        "platforms_policy",
        "tools_infra",
        "world_events",
    ]


def test_watches_in_domain_groups_correctly():
    assert [w.id for w in watches_in_domain("markets", WATCHES)] == [
        "crypto_market_structure"
    ]
    assert [w.id for w in watches_in_domain("platforms_policy", WATCHES)] == [
        "platform_policy"
    ]
    assert watches_in_domain("general", WATCHES) == []


def test_validate_watch_domains_names_unregistered_domains():
    rogue = with_overrides(WATCH_AI_MODEL_RELEASES, domain="not_a_domain")
    problems = validate_watch_domains({rogue.id: rogue})
    assert len(problems) == 1 and "not_a_domain" in problems[0]


# ---------------------------------------------------------------------------
# The INT-007 watches: domains added, behaviour untouched
# ---------------------------------------------------------------------------


def test_existing_watches_keep_operational_shape():
    ai = WATCH_AI_MODEL_RELEASES
    assert (ai.domain, ai.enabled, ai.min_score) == ("ai_models", True, 4)
    assert (ai.max_alerts_per_poll, ai.max_alerts_per_day) == (1, 3)
    assert ai.poll_interval_seconds == 1800

    crypto = WATCH_CRYPTO_MARKET_STRUCTURE
    assert (crypto.domain, crypto.enabled, crypto.min_score) == ("markets", False, 3)
    assert (crypto.max_alerts_per_poll, crypto.max_alerts_per_day) == (1, 3)

    india = WATCH_INDIA_TECH_REGULATORY
    assert (india.domain, india.enabled, india.min_score) == (
        "india_regulatory",
        True,
        3,
    )
    assert (india.max_alerts_per_poll, india.max_alerts_per_day) == (1, 2)
    assert india.poll_interval_seconds == 3600


def test_new_watches_ship_disabled_with_domains():
    assert (WATCH_PLATFORM_POLICY.enabled, WATCH_PLATFORM_POLICY.domain) == (
        False,
        "platforms_policy",
    )
    assert (WATCH_FLEET_TOOLS.enabled, WATCH_FLEET_TOOLS.domain) == (
        False,
        "tools_infra",
    )
    assert (WATCH_WORLD_EVENTS.enabled, WATCH_WORLD_EVENTS.domain) == (
        False,
        "world_events",
    )


# ---------------------------------------------------------------------------
# Scoring: real headlines from the verified feeds (2026-11-18)
# ---------------------------------------------------------------------------


def test_platform_policy_scoring():
    w = WATCH_PLATFORM_POLICY
    # Meta, 2026-11-17: a recommendation-system change for Instagram in
    # India — exactly what this watch exists for.
    score, _, excluded = score_item(
        w,
        item(
            "An Update on the Content We Recommend on Instagram in India",
            "We've strengthened the default protections behind what "
            "Instagram recommends in India.",
        ),
    )
    assert not excluded and score >= w.min_score

    # A monetisation/eligibility change is the other canonical alert.
    score, _, _ = score_item(
        w,
        item(
            "YouTube updates Partner Program eligibility requirements "
            "for monetization",
            "Creators must now meet new subscriber thresholds.",
        ),
    )
    assert score >= w.min_score

    # Product launches and chart news must stay silent.
    for title in (
        "Introducing Direct: An App Just for Messaging",
        "A change to YouTube's inclusion on the U.S. Billboard charts",
        "Muse Is Now Available in Australia: The World's First "
        "Personal AI Agent Built for Everyone",
    ):
        score, _, excluded = score_item(w, item(title))
        assert excluded or score < w.min_score, title

    # Survey content is hard-excluded even when it names a platform.
    _, _, excluded = score_item(
        w,
        item("94% of Singapore Small Business Owners Surveyed Say More "
             "AI Guidance Is Needed"),
    )
    assert excluded


def test_fleet_tools_scoring():
    w = WATCH_FLEET_TOOLS
    # Python Insider, 2026-10-26: the expedited security release line the
    # fleet's own Python versions ride on.
    score, _, excluded = score_item(
        w,
        item(
            "Python 3.15.2, 3.14.10, 3.13.18, 3.12.16 and 3.11.18 are out",
            "Five expedited security releases to distrust the compromised "
            "eMudhra intermediate CA keys.",
        ),
    )
    assert not excluded and score >= w.min_score

    # Python Insider, 2026-06-23: a python.org infrastructure compromise.
    score, _, _ = score_item(
        w,
        item(
            "Mitigated API authentication bypass for python.org "
            "download metadata",
            "Vulnerability mitigated in python.org with follow-up "
            "third-party audit from Trail of Bits",
        ),
    )
    assert score >= w.min_score

    # Noise from the same feeds must stay silent.
    for title, summary in (
        ("The Python Insider Blog Has Moved!",
         "Python Insider now lives at blog.python.org, backed by a Git repository."),
        ("Maintainers don't need more AI bug reports. They need fixes.",
         "In the Codename MDASH pilot, GitHub and Microsoft turned "
         "thousands of raw AI findings into 99 checked, private reports."),
    ):
        score, _, excluded = score_item(w, item(title, summary))
        assert excluded or score < w.min_score, title

    # Pre-releases are excluded by design: the fleet does not run alphas.
    _, _, excluded = score_item(
        w, item("Python 3.16.0 alpha 2 is now available")
    )
    assert excluded


def test_world_events_scoring():
    w = WATCH_WORLD_EVENTS
    # The canonical alert: infrastructure blast radius, stated in the title.
    score, _, excluded = score_item(
        w,
        item(
            "Undersea cable cut leaves millions without internet "
            "across West Africa",
            "Repair ships have been dispatched; traffic is rerouted.",
        ),
    )
    assert not excluded and score >= w.min_score

    # Disaster only alerts with an impact signal attached.
    score, _, _ = score_item(
        w,
        item(
            "Powerful earthquake strikes Taiwan",
            "Millions without power as a state of emergency is declared.",
        ),
    )
    assert score >= w.min_score
    score, _, _ = score_item(
        w, item("Earthquake recorded off the coast of Sumatra", "No damage reported.")
    )
    assert score < w.min_score

    # Al Jazeera, 2026-11-18: a DENIAL of an outage link is not an outage.
    _, _, excluded = score_item(
        w,
        item("Rubio rules out cyberattacks or links between tech outages"),
    )
    assert excluded

    # Ordinary world news from the same feed stays silent.
    for title in (
        "Waymo suspends driverless freeway rides across US after California ban",
        "How the Houthis fund war effort and tighten grip on Yemen",
        "Australia issues sanctions targeting Israeli settlers",
        "Board of Peace warns Gaza ceasefire faces imminent collapse "
        "without action",
    ):
        score, _, excluded = score_item(w, item(title))
        assert excluded or score < w.min_score, title


# ---------------------------------------------------------------------------
# Envelopes and the service, end to end
# ---------------------------------------------------------------------------


def test_envelope_carries_domain():
    envelope = build_envelope(
        WATCH_PLATFORM_POLICY,
        item("YouTube updates Partner Program eligibility requirements"),
        6,
        ["policy_surface:+3"],
        NOW,
    )
    assert envelope["domain"] == "platforms_policy"
    assert envelope["watch_id"] == "platform_policy"


PLATFORM_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Meta Newsroom fixture</title>
<item><title>An Update on the Content We Recommend on Instagram in India</title>
<link>https://example.com/recommend-update</link>
<description>We have strengthened the default protections behind what Instagram recommends.</description>
<pubDate>Tue, 17 Nov 2026 03:58:09 GMT</pubDate></item>
<item><title>Introducing Direct: An App Just for Messaging</title>
<link>https://example.com/direct-app</link>
<description>A new messaging app.</description>
<pubDate>Tue, 17 Nov 2026 01:00:48 GMT</pubDate></item>
</channel></rss>"""


class FakeFetcher:
    def __init__(self, mapping: dict[str, tuple[int, bytes]]) -> None:
        self.mapping = mapping

    async def fetch(self, url: str) -> tuple[int, bytes]:
        return self.mapping.get(url, (404, b""))


async def test_poll_alerts_with_domain_end_to_end(tmp_path: Path):
    # Fresh state, items ~28h old: inside the 72h baseline window, so the
    # first poll scores them live. The policy item must alert with its
    # domain stamped; the product launch must not.
    watch = with_overrides(
        WATCH_PLATFORM_POLICY,
        sources=(FeedSource("https://feed.example/meta.xml", "Meta Fixture"),),
    )
    service = WatchService(
        state_path=tmp_path / "state.json",
        outbox_path=tmp_path / "outbox.jsonl",
        fetcher=FakeFetcher({"https://feed.example/meta.xml": (200, PLATFORM_RSS)}),
    )
    result = await service.poll_once(watch, now=NOW)
    assert result.fetched == 2
    assert result.below_threshold == 1
    assert len(result.alerted) == 1
    envelope = result.alerted[0]
    assert envelope["domain"] == "platforms_policy"
    assert envelope["watch_id"] == "platform_policy"
    lines = (tmp_path / "outbox.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[0])["domain"] == "platforms_policy"

    # And the structural dedupe still holds across polls: nothing re-alerts.
    result2 = await service.poll_once(watch, now=NOW)
    assert result2.alerted == [] and result2.duplicates == 2


async def test_runner_domain_filter_scopes_the_loop():
    polled: list[str] = []

    class RecordingService:
        async def poll_once(self, watch):  # noqa: ANN001 - test stub
            polled.append(watch.id)

    runner = WatchRunner(
        service=RecordingService(), domains={"tools_infra", "world_events"}
    )
    original = dict(WATCHES)
    try:
        # Enable everything in a scratch registry view: the runner reads
        # the module-level WATCHES, so swap in enabled copies.
        import intelx.watches.engine as engine_module

        engine_module.WATCHES = {
            wid: with_overrides(w, enabled=True) for wid, w in original.items()
        }
        runner._running = True
        task = asyncio.create_task(runner._loop())
        await asyncio.sleep(0.2)
        runner._running = False
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    finally:
        import intelx.watches.engine as engine_module

        engine_module.WATCHES = original
    assert sorted(polled) == ["fleet_tools", "world_events"]


def test_domains_module_imports_engine_only_for_typing():
    # domains.py is the data layer: a runtime import of the engine would
    # create a cycle (engine definitions are what domains describe). The
    # engine may appear only inside the TYPE_CHECKING block.
    import ast

    path = Path(domains_module.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def imports_engine(node: ast.AST) -> bool:
        return any(
            isinstance(n, (ast.Import, ast.ImportFrom))
            and "engine" in ast.dump(n)
            for n in ast.walk(node)
        )

    for node in tree.body:
        if isinstance(node, ast.If):
            continue  # the TYPE_CHECKING block
        assert not imports_engine(node), f"runtime engine import: {ast.dump(node)[:80]}"
