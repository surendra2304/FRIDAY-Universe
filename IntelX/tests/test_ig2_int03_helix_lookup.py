"""Tests for TASK-IG2-INT-03 — Helix-style on-demand username lookup.

Hermetic: fetching is injected. Pins the spec-card constraints: approved-
subject gate, bounded sites/concurrency, control-probe discarding of
false positives, and confidence discipline (match alone never above LOW).
"""
from __future__ import annotations

import pytest

from intelx.osint.helix_lookup import (
    HARD_MAX_SITES,
    control_username_for,
    helix_lookup,
)
from intelx.osint.username import PLATFORMS, PlatformSpec

GITHUB = PlatformSpec("GitHub", "https://github.com/{u}")
KEYBASE = PlatformSpec("Keybase", "https://keybase.io/{u}")
TWO = (GITHUB, KEYBASE)


class FakeFetch:
    """routes: substring -> (status, body). Records every URL fetched."""

    def __init__(self, routes: dict[str, tuple[int, bytes]]) -> None:
        self.routes = routes
        self.urls: list[str] = []

    async def __call__(self, url: str) -> tuple[int, str, bytes]:
        self.urls.append(url)
        for key, (status, body) in self.routes.items():
            if key in url:
                return status, url, body
        return 404, url, b""


async def test_gate_rejects_unapproved_subject():
    fetch = FakeFetch({})
    with pytest.raises(PermissionError):
        await helix_lookup("someone", approved_subjects=["owner_named"], fetch=fetch, platforms=TWO)
    assert fetch.urls == []  # gate fires before any network traffic


async def test_found_hit_is_low_confidence_without_signals():
    fetch = FakeFetch({"github.com/alice": (200, b"<html>alice profile</html>")})
    report = await helix_lookup("alice", approved_subjects=["alice"], fetch=fetch, platforms=TWO)
    assert report.sites_checked == 2
    assert [h.platform for h in report.hits] == ["GitHub"]
    assert report.hits[0].confidence == "LOW"
    assert report.overall_confidence == "LOW"
    assert report.discarded == []


async def test_control_probe_discards_false_positive():
    # Platform "finds" everybody, including the impossible control name.
    fetch = FakeFetch({"github.com/": (200, b"<html>welcome</html>")})
    report = await helix_lookup("alice", approved_subjects=["alice"], fetch=fetch, platforms=(GITHUB,))
    assert report.hits == []
    assert len(report.discarded) == 1
    assert report.discarded[0]["platform"] == "GitHub"
    assert report.overall_confidence == "NONE"


async def test_control_username_is_deterministic_and_distinct():
    assert control_username_for("alice") == control_username_for("alice")
    assert control_username_for("alice") != control_username_for("bob")


async def test_cross_link_raises_to_medium_and_mutual_to_high():
    gh_body = b'<html>me: <a href="https://keybase.io/alice">keybase</a></html>'
    kb_body = b'<html>me: <a href="https://github.com/alice">github</a></html>'
    fetch = FakeFetch({
        "github.com/alice": (200, gh_body),
        "keybase.io/alice": (200, kb_body),
    })
    report = await helix_lookup("alice", approved_subjects=["alice"], fetch=fetch, platforms=TWO)
    by_platform = {h.platform: h for h in report.hits}
    assert by_platform["GitHub"].confidence == "HIGH"
    assert by_platform["Keybase"].confidence == "HIGH"


async def test_one_way_cross_link_is_medium_not_high():
    gh_body = b'<html><a href="https://keybase.io/alice">kb</a></html>'
    fetch = FakeFetch({
        "github.com/alice": (200, gh_body),
        "keybase.io/alice": (200, b"<html>alice</html>"),
    })
    report = await helix_lookup("alice", approved_subjects=["alice"], fetch=fetch, platforms=TWO)
    by_platform = {h.platform: h for h in report.hits}
    assert by_platform["GitHub"].confidence == "MEDIUM"
    assert by_platform["Keybase"].confidence == "LOW"


async def test_site_cap_is_enforced():
    fetch = FakeFetch({})
    report = await helix_lookup(
        "alice", approved_subjects=["alice"], fetch=fetch,
        platforms=PLATFORMS, max_sites=10_000,
    )
    assert report.sites_checked == min(len(PLATFORMS), HARD_MAX_SITES)


async def test_blocked_platform_is_unknown_not_absence():
    fetch = FakeFetch({"github.com/alice": (403, b"bot wall")})
    report = await helix_lookup("alice", approved_subjects=["alice"], fetch=fetch, platforms=(GITHUB,))
    assert report.hits == []
    assert len(report.unknown) == 1
