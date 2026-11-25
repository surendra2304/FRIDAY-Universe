"""TASK-IG2-FRD-03 — delegated lead-generation errand tests.

Fake fetcher only (no network): parsing, dedupe, table rendering, the
SSRF guard, same-host pagination, and the no-outreach surface.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.autonomous.lead_generation import (  # noqa: E402
    Lead, LeadGenError, _clean_phone, _default_fetcher, dedupe_leads,
    parse_listing_page, render_table, run_lead_generation)

_PAGE1 = """
<html><body>
<div class="listing-card"><h3>Acme Insurance</h3>
  <a href="tel:+97140000001">call</a><a href="mailto:hi@acme.example">mail</a>
  <p>Call +971 4 000 0001 for quotes</p></div>
<div class="listing-card"><h3>Beta Insurance</h3><p>+971 4 000 0002</p></div>
<a class="next" href="/cat/insurance?page=2">Next</a>
</body></html>"""
_PAGE2 = """
<html><body>
<div class="listing-card"><h3>Acme Insurance</h3>
  <a href="https://acme.example">site</a></div>
<div class="listing-card"><h3>Gamma Insurance</h3><p>+971 4 000 0003</p></div>
</body></html>"""


def _fetcher(url: str) -> str:
    return _PAGE2 if "page=2" in url else _PAGE1


def test_parse_extracts_contacts_from_listing_blocks():
    leads, nxt = parse_listing_page(_PAGE1, "https://dir.example/cat", "insurance")
    assert [lead.name for lead in leads] == ["Acme Insurance", "Beta Insurance"]
    assert leads[0].email == "hi@acme.example" and leads[0].phone
    assert nxt.endswith("page=2")


def test_dedupe_merges_by_email_and_fills_blanks():
    merged = dedupe_leads([
        Lead(name="Acme", email="hi@acme.example"),
        Lead(name="Acme Insurance", email="hi@acme.example", website="https://acme.example"),
        Lead(name="Other", phone="123"),
    ])
    assert len(merged) == 2 and merged[0].website == "https://acme.example"


def test_run_follows_same_host_pagination_and_dedupes(monkeypatch):
    monkeypatch.setattr(
        "friday.autonomous.lead_generation.check_url_allowed", lambda url: None)
    result = run_lead_generation("https://dir.example/cat/insurance", "insurance",
                                 fetcher=_fetcher)
    assert result.pages_fetched == 2
    assert [lead.name for lead in result.leads] == [
        "Acme Insurance", "Beta Insurance", "Gamma Insurance"]


def test_table_renders_markdown_and_csv():
    leads = [Lead(name="Acme", phone="1", email="a@b.example", category="insurance")]
    md = render_table(leads, "markdown")
    assert "| Acme |" in md and "insurance" in md
    csv_text = render_table(leads, "csv")
    assert csv_text.splitlines()[0].startswith("name,phone,email")


def test_ssrf_guard_refuses_local_and_odd_ports():
    from friday.autonomous.lead_generation import check_url_allowed
    assert check_url_allowed("file:///etc/passwd") is not None
    assert check_url_allowed("http://localhost/admin") is not None
    assert check_url_allowed("https://example.com:8080/x") is not None
    with pytest.raises(LeadGenError):
        run_lead_generation("http://127.0.0.1/admin", fetcher=_fetcher)


def test_engine_has_no_outreach_surface():
    import friday.autonomous.lead_generation as mod
    names = [n.lower() for n in dir(mod)]
    assert not any("send" in n or "smtp" in n or "call_" in n for n in names)


# TASK-IG2-FRD-03-FIX-01 — live-failure regressions (FRD-054, 2026-11-25):
# the JaRanks probe returned 65 rows with 0 phones/emails and nav junk
# ("JaRanks", "Home", "How we chose", "Profile") as leads, and FindYello
# 403'd the fetcher's bot User-Agent.

_JUNK_PAGE = """
<html><body>
<nav><div class="menu-item"><a href="/home">Home</a></div>
<div class="nav-item">JaRanks</div>
<a class="nav-item" href="/how">How we chose</a></nav>
<header><div class="listing-card"><h3>Site Header Co</h3>
<p>Call +1 555 000 0001</p></div></header>
<div class="listing-card"><h3>Real Business</h3><p>Call 876-555-0100</p></div>
<div class="listing-card"><h3>Name Only Co</h3>
<p>Just a description, no contact.</p></div>
<div class="listing-card"><h3>Dated Co</h3><p>Updated 2026-11-25</p></div>
<footer><div class="item">The JaRanks newsletter</div></footer>
</body></html>"""


def test_parse_drops_chrome_and_contactless_blocks():
    leads, _ = parse_listing_page(_JUNK_PAGE, "https://dir.example/cat", "general")
    assert [lead.name for lead in leads] == ["Real Business"]
    assert leads[0].phone == "876-555-0100"


def test_parse_contact_filter_is_explicitly_opt_out():
    leads, _ = parse_listing_page(_JUNK_PAGE, "https://dir.example/cat", "general",
                                  require_contact=False)
    names = [lead.name for lead in leads]
    assert "Real Business" in names and "Name Only Co" in names
    assert "Home" not in names and "JaRanks" not in names


def test_clean_phone_rejects_dates_and_fragments():
    assert _clean_phone("2026-11-25") == ""
    assert _clean_phone("20261125") == ""
    assert _clean_phone("123") == ""
    assert _clean_phone("") == ""
    assert _clean_phone("876-906-3284") == "876-906-3284"
    assert _clean_phone("+1 555 000 0001") == "+1 555 000 0001"


_JARANKS_LIST = """
<html><body>
<header><div class="nav-item"><a href="/about">JaRanks</a></div>
<div class="menu-item"><a href="/">Home</a></div></header>
<nav><a class="nav-item" href="/how">How we chose</a></nav>
<main>
<article class="listing-card"><h2>British Caribbean Insurance Company Ltd. (BCIC)</h2>
<p>BCIC offers motor, property and liability insurance.</p>
<a href="https://jaranks.example/profiles/bcic">View profile</a></article>
<article class="listing-card"><h2>Covenant Insurance Brokers</h2>
<p>Motor, home and product liability insurance.</p>
<a href="https://jaranks.example/profiles/covenant">View profile</a></article>
</main>
<footer><div class="footer-item"><a href="/newsletter">The JaRanks newsletter</a></div></footer>
</body></html>"""

_JARANKS_DETAIL = {
    "https://jaranks.example/profiles/bcic": (
        "<html><body><h1>BCIC</h1>"
        "<a href=\"tel:+18767650100\">876-765-0100</a>"
        "<a href=\"mailto:info@bcic.example\">info@bcic.example</a>"
        "</body></html>"),
    "https://jaranks.example/profiles/covenant": (
        "<html><body><h1>Covenant</h1><p>Phone: 876-765-0200</p></body></html>"),
}


def test_run_enriches_contactless_leads_from_detail_pages(monkeypatch):
    monkeypatch.setattr(
        "friday.autonomous.lead_generation.check_url_allowed", lambda url: None)
    seen: list[str] = []

    def fetcher(url: str) -> str:
        seen.append(url)
        return _JARANKS_DETAIL.get(url, _JARANKS_LIST)

    result = run_lead_generation(
        "https://jaranks.example/lists/best-insurance-brokers-in-jamaica",
        "insurance", fetcher=fetcher)
    assert result.pages_fetched == 1
    names = [lead.name for lead in result.leads]
    assert names == ["British Caribbean Insurance Company Ltd. (BCIC)",
                     "Covenant Insurance Brokers"]
    assert result.leads[0].phone == "+18767650100"
    assert result.leads[0].email == "info@bcic.example"
    assert result.leads[1].phone == "876-765-0200"
    assert "Home" not in names and "JaRanks" not in names
    # both detail pages were fetched, both on the directory's host
    assert "https://jaranks.example/profiles/bcic" in seen
    assert "https://jaranks.example/profiles/covenant" in seen


def test_run_never_follows_off_host_detail_links(monkeypatch):
    monkeypatch.setattr(
        "friday.autonomous.lead_generation.check_url_allowed", lambda url: None)
    seen: list[str] = []
    page = """
    <html><body>
    <div class="listing-card"><h3>Off Host Co</h3>
    <a href="https://elsewhere.example/profile">View profile</a></div>
    </body></html>"""

    def fetcher(url: str) -> str:
        seen.append(url)
        return page

    result = run_lead_generation("https://dir.example/cat", "general", fetcher=fetcher)
    assert result.leads == []
    assert seen == ["https://dir.example/cat"]


def test_default_fetcher_sends_browser_headers(monkeypatch):
    seen: dict = {}

    class FakeResp:
        text = "<html></html>"

        def raise_for_status(self) -> None:
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> bool:
            return False

        def get(self, url, headers=None):
            seen["headers"] = headers
            return FakeResp()

    monkeypatch.setattr("httpx.Client", FakeClient)
    assert _default_fetcher("https://dir.example/x") == "<html></html>"
    ua = seen["headers"]["User-Agent"]
    assert "Mozilla" in ua and "Chrome" in ua
    assert "FRIDAY-LeadGen" not in ua
