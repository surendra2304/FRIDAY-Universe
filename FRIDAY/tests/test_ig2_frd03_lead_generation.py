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
<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-4 border-b border-hairline py-8 md:gap-x-8 md:py-10">
<div class="inline-block w-[1.24em] text-left whitespace-nowrap">1.</div>
<div class="min-w-0 flex-1"><div class="flex items-start justify-between gap-4">
<div class="min-w-0 flex-1">
<h2 class="font-display text-subheading font-bold text-ink md:text-heading [text-wrap:balance]"><a class="underline-offset-[0.18em] hover:underline" href="/profile/british-caribbean-insurance-company-ltd-bcic">British Caribbean Insurance Company Ltd. (BCIC)</a></h2>
<div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-body-sm text-slate"><span>Kingston</span></div>
</div></div>
<div class="mt-4 max-w-[64ch] text-body text-ink">BCIC offers motor, property and liability insurance.</div>
<div class="mt-5 flex flex-wrap items-center gap-2"><span>Motor</span></div>
</div></div>
<div class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-4 border-b border-hairline py-8 md:gap-x-8 md:py-10">
<div class="inline-block w-[1.24em] text-left whitespace-nowrap">2.</div>
<div class="min-w-0 flex-1"><div class="flex items-start justify-between gap-4">
<div class="min-w-0 flex-1">
<h2 class="font-display text-subheading font-bold text-ink md:text-heading [text-wrap:balance]"><a class="underline-offset-[0.18em] hover:underline" href="/profile/covenant-insurance-brokers">Covenant Insurance Brokers</a></h2>
<div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-body-sm text-slate"><span>Kingston</span></div>
</div></div>
<div class="mt-4 max-w-[64ch] text-body text-ink">Motor, home and product liability insurance.</div>
<div class="mt-5 flex flex-wrap items-center gap-2"><span>Motor</span></div>
</div></div>
</main>
<h2>How we chose</h2><p>JaRanks orders this list editorially.</p>
<footer><div class="footer-item"><a href="/newsletter">The JaRanks newsletter</a></div></footer>
</body></html>"""

_JARANKS_DETAIL = {
    "https://jaranks.example/profile/british-caribbean-insurance-company-ltd-bcic": (
        "<html><body><h1>BCIC</h1>"
        "<a href=\"tel:+18767650100\">876-765-0100</a>"
        "<a href=\"mailto:info@bcic.example\">info@bcic.example</a>"
        "</body></html>"),
    "https://jaranks.example/profile/covenant-insurance-brokers": (
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
    assert "How we chose" not in names
    # both detail pages were fetched, both on the directory's host, and the
    # relative profile links were joined to absolute URLs
    assert "https://jaranks.example/profile/british-caribbean-insurance-company-ltd-bcic" in seen
    assert "https://jaranks.example/profile/covenant-insurance-brokers" in seen
    assert result.leads[0].website == "https://jaranks.example/profile/british-caribbean-insurance-company-ltd-bcic"


def test_parse_joins_relative_detail_links():
    html = ('<div class="listing-card"><h3>Acme</h3><p>+971 4 000 0001</p>'
            '<a href="/profiles/acme">Profile</a></div>')
    leads, _ = parse_listing_page(html, "https://dir.example/cat", "general")
    assert leads[0].website == "https://dir.example/profiles/acme"


def test_parse_void_elements_do_not_swallow_siblings():
    # An <img> inside a listing block has no end tag: it must not inflate
    # the block depth, or the block swallows every following sibling.
    html = ('<div class="listing-card"><h3>Acme</h3><img src="/x.png">'
            '<p>Call 876-555-0100</p></div><div class="listing-card"><h3>Beta</h3>'
            '<p>Call 876-555-0200</p></div>')
    leads, _ = parse_listing_page(html, "https://dir.example/cat", "general")
    assert [lead.name for lead in leads] == ["Acme", "Beta"]
    assert leads[0].phone == "876-555-0100" and leads[1].phone == "876-555-0200"


def test_heading_fallback_runs_when_only_empty_image_blocks_exist():
    # A "rounded-card" logo div opens an (empty) hinted block; the heading
    # fallback must still run for the real listings.
    html = ('<html><body>'
            '<div class="relative block rounded-card"><img src="/logo.png"></div>'
            '<h2><a href="/profile/acme">Acme Insurance</a></h2>'
            '<p>Call 876-555-0100 for quotes</p>'
            '</body></html>')
    leads, _ = parse_listing_page(html, "https://dir.example/cat", "general")
    assert [lead.name for lead in leads] == ["Acme Insurance"]
    assert leads[0].phone == "876-555-0100"
    assert leads[0].website == "https://dir.example/profile/acme"


def test_heading_sections_do_not_adopt_trailing_body_links():
    # A footer link trailing the last heading section is not that
    # section's detail link — only links inside the heading itself count.
    html = ('<html><body><h2>How we chose</h2><p>Editorial note.</p>'
            '<footer><a href="/newsletter">Newsletter</a></footer></body></html>')
    leads, _ = parse_listing_page(html, "https://dir.example/cat", "general",
                                  require_contact=False)
    assert [lead.name for lead in leads] == ["How we chose"]
    assert leads[0].website == ""


def test_parse_unions_hint_and_heading_blocks_without_doubling():
    # A page with a hinted card AND a heading listing returns both, once
    # each — the heading duplicate of the card merges in parse.
    html = ('<html><body>'
            '<div class="listing-card"><h3>Hinted Co</h3><p>Call 876-555-0100</p></div>'
            '<h2><a href="/profile/headed">Headed Co</a></h2>'
            '<p>Call 876-555-0200 for quotes</p>'
            '</body></html>')
    leads, _ = parse_listing_page(html, "https://dir.example/cat", "general")
    assert [lead.name for lead in leads] == ["Hinted Co", "Headed Co"]
    assert leads[1].website == "https://dir.example/profile/headed"


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
