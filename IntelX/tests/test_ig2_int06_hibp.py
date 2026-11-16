"""Tests for TASK-IG2-INT-06 — HaveIBeenPwned breach checks (cluster #48).

Hermetic: fetching is injected. Pins the free-only contract: the Pwned
Passwords range check is a real k-anonymity lookup (only the 5-char
SHA-1 prefix is requested), and the email check without an API key
reports itself unavailable instead of fabricating 'no breaches'.
"""
from __future__ import annotations

import hashlib

import pytest

from intelx.osint.breach_check import (
    check_email_breaches,
    check_password_breach,
    parse_range_response,
)

# SHA-1("password") = 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8 (well-known)
KNOWN_SHA1 = "5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8"


def test_known_sha1_fixture_is_right():
    assert hashlib.sha1(b"password").hexdigest().upper() == KNOWN_SHA1


def test_parse_range_response():
    body = "0018A45C4D1DEF81644B54AB7F969B88D65:1\n1E4C9B93F3F0682250B6CF8331B7EE68FD8:9545824\n"
    assert parse_range_response(body, KNOWN_SHA1[5:]) == 9545824
    assert parse_range_response(body, "F" * 35) == 0


async def test_password_breach_found_and_only_prefix_leaves():
    seen: dict = {}

    async def fetch(url: str, headers: dict) -> tuple[int, str]:
        seen["url"] = url
        return 200, f"{KNOWN_SHA1[5:]}:9545824\nAAAA:3\n"

    result = await check_password_breach("password", fetch=fetch)
    assert result.found and result.occurrences == 9545824 and result.checked
    # k-anonymity: the request carries ONLY the 5-char prefix
    assert seen["url"].endswith("/range/5BAA6")
    assert KNOWN_SHA1 not in seen["url"]


async def test_password_not_found():
    async def fetch(url: str, headers: dict) -> tuple[int, str]:
        return 200, "0018A45C4D1DEF81644B54AB7F969B88D65:1\n"

    result = await check_password_breach("password", fetch=fetch)
    assert not result.found and result.occurrences == 0


async def test_password_api_error_raises_not_fabricates():
    async def fetch(url: str, headers: dict) -> tuple[int, str]:
        return 500, "oops"

    with pytest.raises(RuntimeError):
        await check_password_breach("password", fetch=fetch)


async def test_email_check_without_key_is_honestly_unavailable():
    async def fetch(url: str, headers: dict) -> tuple[int, str]:
        raise AssertionError("must not be called without a key")

    result = await check_email_breaches("a@example.com", fetch=fetch, api_key="")
    assert result.status == "unavailable"
    assert result.checked is False
    assert "paid" in result.reason and "never reported as" in result.reason
    assert result.breaches == ()


async def test_email_check_with_key_maps_404_and_200():
    async def fetch404(url: str, headers: dict) -> tuple[int, str]:
        assert headers.get("hibp-api-key") == "test-key"
        return 404, ""

    clean = await check_email_breaches("a@example.com", fetch=fetch404, api_key="test-key")
    assert clean.status == "no_breaches" and clean.checked

    async def fetch200(url: str, headers: dict) -> tuple[int, str]:
        return 200, '[{"Name": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04", "PwnCount": 152445165, "DataClasses": ["Email addresses", "Passwords"]}]'

    hit = await check_email_breaches("a@example.com", fetch=fetch200, api_key="test-key")
    assert hit.status == "breaches_found" and hit.checked
    assert hit.breaches[0]["name"] == "Adobe"
    assert hit.breaches[0]["pwn_count"] == 152445165
