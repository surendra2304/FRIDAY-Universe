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
    Lead, LeadGenError, dedupe_leads, parse_listing_page, render_table,
    run_lead_generation)

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
