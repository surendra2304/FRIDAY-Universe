"""TASK-FRD-061 — lead verification pass tests (hermetic, no network).

Covers verify_lead statuses (verified / stale / unverifiable), the
could-not-tell vs dead distinction, finalize (stale dropped, unverifiable
kept), the verified table rendering, the engine wiring (verify opt-in,
default off), and the lead_generate tool end to end with fake fetchers.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.autonomous import lead_generation as lg  # noqa: E402
from friday.autonomous import lead_verification as lv  # noqa: E402
from friday.tools.builtin.lead_gen_tools import LeadGenerateTool  # noqa: E402

NOW = datetime(2026, 11, 25, 14, 0, tzinfo=timezone.utc)

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


def _ok_website(url: str):
    return True, "reachable"


def _dead_website(url: str):
    return False, "HTTP 404"


def _unreachable_website(url: str):
    return False, "could not reach to check (Timeout)"


def _resolves(host: str) -> bool:
    return True


def _unresolvable(host: str) -> bool:
    return False


def test_verify_lead_verified_when_all_routes_check_out():
    lead = lg.Lead(name="Acme", phone="+971 4 000 0001", email="hi@acme.example",
                   website="https://acme.example")
    result = lv.verify_lead(lead, website_checker=_ok_website, dns_resolver=_resolves, now=NOW)
    assert result["status"] == "verified"
    assert lead.status == "verified"
    assert lead.checked_at == "2026-11-25 14:00 IST"
    assert result["checks"]["website"]["result"] == "ok"
    assert result["checks"]["email"]["result"] == "ok"
    assert result["checks"]["phone"]["result"] == "ok"


def test_verify_lead_stale_when_website_dead():
    lead = lg.Lead(name="Dead Co", phone="+971 4 000 0001", email="hi@dead.example",
                   website="https://dead.example")
    result = lv.verify_lead(lead, website_checker=_dead_website, dns_resolver=_resolves, now=NOW)
    assert result["status"] == "stale"
    assert "HTTP 404" in result["reason"]


def test_verify_lead_stale_when_email_domain_does_not_resolve():
    lead = lg.Lead(name="Ghost Co", email="hi@no-such-domain.example")
    result = lv.verify_lead(lead, website_checker=_ok_website, dns_resolver=_unresolvable, now=NOW)
    assert result["status"] == "stale"
    assert "does not resolve" in result["reason"]


def test_verify_lead_stale_when_phone_implausible():
    lead = lg.Lead(name="Bad Phone Co", phone="abc")
    result = lv.verify_lead(lead, website_checker=_ok_website, dns_resolver=_resolves, now=NOW)
    assert result["status"] == "stale"


def test_verify_lead_unverifiable_when_no_routes_on_file():
    lead = lg.Lead(name="Nameless Co")
    result = lv.verify_lead(lead, website_checker=_ok_website, dns_resolver=_resolves, now=NOW)
    assert result["status"] == "unverifiable"
    assert "no contact routes" in result["reason"]


def test_verify_lead_unverifiable_not_stale_when_check_could_not_run():
    lead = lg.Lead(name="Flaky Co", website="https://flaky.example")
    result = lv.verify_lead(lead, website_checker=_unreachable_website, dns_resolver=_resolves, now=NOW)
    assert result["status"] == "unverifiable"
    assert "could not reach" in result["reason"]


def test_finalize_drops_stale_keeps_unverifiable():
    leads = [
        lg.Lead(name="Good", phone="+971 4 000 0001"),
        lg.Lead(name="Dead", website="https://dead.example"),
        lg.Lead(name="Unknown"),
    ]
    lv.verify_leads(leads, website_checker=_dead_website, dns_resolver=_resolves, now=NOW)
    # Good: phone plausible -> verified. Dead: website 404 -> stale.
    # Unknown: no routes -> unverifiable.
    assert [lead.status for lead in leads] == ["verified", "stale", "unverifiable"]
    final = lv.finalize_outreach_list(leads)
    assert [lead.name for lead in final["final"]] == ["Good", "Unknown"]
    assert [lead.name for lead in final["dropped"]] == ["Dead"]
    assert final["counts"] == {"verified": 1, "stale": 1, "unverifiable": 1, "unchecked": 0}
    kept = lv.finalize_outreach_list(leads, drop_stale=False)
    assert len(kept["final"]) == 3 and kept["dropped"] == []


def test_render_verification_table_marks_status_and_date():
    lead = lg.Lead(name="Acme", phone="+971 4 000 0001", email="hi@acme.example")
    lv.verify_lead(lead, website_checker=_ok_website, dns_resolver=_resolves, now=NOW)
    md = lv.render_verification_table([lead], "markdown")
    assert "verified" in md and "2026-11-25 14:00 IST" in md
    csv_text = lv.render_verification_table([lead], "csv")
    assert csv_text.splitlines()[0].startswith("name,phone,email,website,category,status,checked_at")


def test_engine_verify_opt_in_marks_every_lead(monkeypatch):
    monkeypatch.setattr(lg, "check_url_allowed", lambda url: None)
    result = lg.run_lead_generation(
        "https://dir.example/cat/insurance", "insurance",
        fetcher=_fetcher, verify=True, dns_resolver=_resolves,
    )
    assert len(result.leads) == 3
    assert all(lead.status == "verified" for lead in result.leads)
    assert all(lead.checked_at for lead in result.leads)


def test_engine_default_leaves_leads_unchecked(monkeypatch):
    monkeypatch.setattr(lg, "check_url_allowed", lambda url: None)
    result = lg.run_lead_generation(
        "https://dir.example/cat/insurance", "insurance", fetcher=_fetcher
    )
    assert all(lead.status == "unchecked" for lead in result.leads)


def test_tool_verifies_and_finalises(monkeypatch):
    monkeypatch.setattr(lg, "check_url_allowed", lambda url: None)
    monkeypatch.setattr(lg, "_default_fetcher", _fetcher)
    monkeypatch.setattr(lv, "_default_dns_resolver", _resolves)
    result = LeadGenerateTool().execute(
        directory_url="https://dir.example/cat/insurance", category="insurance"
    )
    assert result.is_error is False
    assert "3 verified" in result.content
    assert result.metadata["counts"]["verified"] == 3
    assert result.metadata["dropped"] == []
    assert "verified" in result.metadata["csv"]


def test_tool_verify_off_behaves_as_before(monkeypatch):
    monkeypatch.setattr(lg, "check_url_allowed", lambda url: None)
    monkeypatch.setattr(lg, "_default_fetcher", _fetcher)
    result = LeadGenerateTool().execute(
        directory_url="https://dir.example/cat/insurance", category="insurance", verify=False
    )
    assert result.is_error is False
    assert "verification skipped" in result.content
    assert result.metadata["count"] == 3
