"""Tests for TASK-IG-INT-04 — OSINT public-footprint lookups + audit.

Hermetic: fetching is injected. Fixtures mirror the real public responses
(Gravatar behaviour verified live 2026-11-15: unknown email -> 404 with
?d=404; GitHub profile 200/404 semantics).
"""

from __future__ import annotations

import json

import pytest

from intelx.osint.audit import FootprintAudit
from intelx.osint.email import check_email
from intelx.osint.phone import parse_phone
from intelx.osint.username import PLATFORMS, check_username

GRAVATAR_PROFILE = json.dumps(
    {
        "entry": [
            {
                "displayName": "Test Person",
                "aboutMe": "Security researcher. Verbatim about text.",
                "urls": [{"title": "Blog", "value": "https://example.com/blog"}],
            }
        ]
    }
).encode()


class FakeFetch:
    def __init__(self, routes: dict[str, tuple[int, bytes]]) -> None:
        self.routes = routes

    async def __call__(self, url: str) -> tuple[int, str, bytes]:
        for key, (status, body) in self.routes.items():
            if key in url:
                return status, url, body
        return 404, url, b""


# -- phone --------------------------------------------------------------------


def test_parse_indian_mobile() -> None:
    info = parse_phone("+91 98765 43210")
    assert info.valid_format
    assert info.e164 == "+919876543210"
    assert info.country_iso == "IN"
    assert info.national_number == "9876543210"


def test_parse_us_number_and_00_prefix() -> None:
    info = parse_phone("001 (202) 555-0123")
    assert info.valid_format
    assert info.country_iso == "US/CA"
    assert info.e164 == "+12025550123"


def test_parse_invalid_numbers_report_problems() -> None:
    short = parse_phone("+91 123")
    assert not short.valid_format
    assert short.problems
    unknown = parse_phone("+9991234567")
    assert not unknown.valid_format
    assert any("calling code" in p for p in unknown.problems)


def test_carrier_lookup_is_honestly_unavailable() -> None:
    info = parse_phone("+919876543210")
    assert "unavailable" in info.carrier_lookup
    assert "not guessed" in info.carrier_lookup


# -- username -------------------------------------------------------------------


async def test_username_three_state_verdicts() -> None:
    fetch = FakeFetch(
        {
            "github.com": (200, b"<html>profile</html>"),
            "gitlab.com": (404, b""),
            "keybase.io": (403, b"blocked"),
            "reddit.com": (200, b"<html>nobody on reddit goes by that name</html>"),
        }
    )
    hits = {h.platform: h for h in await check_username("someone", fetch=fetch)}
    assert hits["GitHub"].status == "found"
    assert hits["GitLab"].status == "not_found"
    assert hits["Keybase"].status == "unknown"  # a block is not an absence
    assert hits["Reddit"].status == "not_found"  # marker inside a 200 page


async def test_username_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        await check_username("bad name!", fetch=FakeFetch({}))


async def test_username_covers_curated_platforms() -> None:
    assert len(PLATFORMS) >= 10
    names = {p.name for p in PLATFORMS}
    assert {"GitHub", "GitLab", "Reddit", "Bluesky"} <= names


# -- email ------------------------------------------------------------------------


async def test_email_gravatar_found_with_verbatim_profile() -> None:
    fetch = FakeFetch({"avatar/": (200, b"img"), ".json": (200, GRAVATAR_PROFILE)})
    fp = await check_email("Person@Example.com", fetch=fetch)
    assert fp.email == "person@example.com"  # normalised
    assert fp.gravatar.exists
    assert fp.gravatar.display_name == "Test Person"
    assert fp.gravatar.about == "Security researcher. Verbatim about text."
    assert fp.gravatar.linked_urls == [{"title": "Blog", "value": "https://example.com/blog"}]
    assert "NOT checked" in fp.breach_check


async def test_email_gravatar_absent() -> None:
    fetch = FakeFetch({"avatar/": (404, b"")})
    fp = await check_email("ghost@example.com", fetch=fetch)
    assert not fp.gravatar.exists
    assert fp.gravatar.display_name == ""


async def test_email_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        await check_email("not-an-email", fetch=FakeFetch({}))


# -- audit -------------------------------------------------------------------------


async def test_audit_composes_and_names_unavailable_surfaces() -> None:
    fetch = FakeFetch({"github.com": (200, b"ok"), "avatar/": (404, b"")})
    audit = FootprintAudit(fetch=fetch)
    report = await audit.run(username="someone", email="ghost@example.com", phone="+91 98765 43210")
    assert report["sections"]["phone"]["country_iso"] == "IN"
    assert report["sections"]["email"]["gravatar"]["exists"] is False
    sections = {u["section"] for u in report["unavailable"]}
    assert sections == {"dark_web_search", "breach_database_check", "carrier_line_type_lookup"}
    dark = next(u for u in report["unavailable"] if u["section"] == "dark_web_search")
    assert "NOT checked" in dark["reason"]
    assert "means nothing" in report["coverage_note"]


async def test_audit_requires_a_subject() -> None:
    with pytest.raises(ValueError):
        await FootprintAudit(fetch=FakeFetch({})).run()
