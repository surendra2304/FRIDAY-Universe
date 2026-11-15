"""TASK-INT-009 verification-pass gap tests.

Base layer (TASK-INT-005 crew, tests/test_int005_verification_pass.py):
the verbatim quote gate, the deterministic entailment screen
(``statement_support``) and the page-chrome filter. This file pins the
gaps INT-009 closed on top of that base:

1. Snapshot-vs-live divergence (the audit's Bruker failure mode): a quote
   is re-verified against the cited source AS RETRIEVED at verification
   time — never only against the synthesis snapshot. A quote that is
   absent from the retrieved page, or whose source cannot be retrieved,
   downgrades the finding; it never passes it.
2. The re-audit classifier (``reaudit_finding``) that the re-audit hook
   (scripts/reaudit_live_research.py) applies to stored runs: boilerplate
   is NON_CLAIM and leaves the accuracy denominator; Bruker-class claims
   are UNSUPPORTED; unretrievable sources are UNVERIFIABLE.
3. Corroboration surfacing: findings carry ``single_source`` and
   ``independently_verified`` explicitly (INT-005 §6 item 4).
"""
import hashlib
from types import SimpleNamespace

from intelx.api.grounded_live_research import (
    reaudit_finding,
    reverify_findings_against_texts,
)
from intelx.api.live_research_task import collect_live_brief

URL = "https://www.who.int/example"
PAGE_TEXT = (
    "The aspartame safety assessment concluded that aspartame is safe "
    "within the acceptable daily intake of 0-40 mg/kg body weight for "
    "aspartame consumers in many countries."
)
QUOTE = ("aspartame is safe within the acceptable daily intake of "
         "0-40 mg/kg body weight for aspartame")
STATEMENT = ("The aspartame safety assessment concluded that aspartame "
             "is safe within a daily intake of 40 mg/kg of body weight.")

# The Bruker failure mode, as fixtures: the stored quote comes from a
# different catalogue text; the live cited page (specialty solids probes)
# contains none of it.
BRUKER_QUOTE = ("specialized solid-state NMR systems for in-situ and "
                "operando research on energy storage materials")
BRUKER_STATEMENT = ("Bruker provides specialized solid-state NMR probes "
                    "designed for in-situ and operando research on energy "
                    "storage materials, including batteries and "
                    "supercapacitors.")
BRUKER_LIVE_PAGE = (
    "Specialty solids probes for high-resolution solid-state NMR. "
    "These probes are designed for single crystals, powders and oriented "
    "samples, with static and magic-angle spinning options."
)
BRUKER_URL = "https://www.bruker.com/example-specialty-probes"


def _finding(statement=STATEMENT, quote=QUOTE, url=URL):
    return {"statement": statement, "quote": quote,
            "citations": [{"source_id": "s1", "source_title": "Aspartame assessment",
                           "source_url": url}]}


# ── reverify_findings_against_texts (pure) ─────────────────────────────────

def test_reverify_keeps_quote_found_in_live_text():
    kept, downgraded = reverify_findings_against_texts(
        [_finding()], {URL: PAGE_TEXT})
    assert len(kept) == 1 and not downgraded
    assert kept[0]["live_quote_reverified"] is True


def test_reverify_downgrades_bruker_style_divergence():
    finding = _finding(BRUKER_STATEMENT, BRUKER_QUOTE, BRUKER_URL)
    kept, downgraded = reverify_findings_against_texts(
        [finding], {BRUKER_URL: BRUKER_LIVE_PAGE})
    assert not kept and len(downgraded) == 1
    assert downgraded[0]["downgrade_reason"] == "quote_not_in_live_source"
    assert downgraded[0]["live_quote_reverified"] is False


def test_reverify_downgrades_when_source_not_retrievable():
    kept, downgraded = reverify_findings_against_texts(
        [_finding()], {URL: None})
    assert not kept and len(downgraded) == 1
    assert downgraded[0]["downgrade_reason"] == "quote_reverification_unavailable"
    # A URL missing from the retrieval map is equally unverifiable.
    kept2, downgraded2 = reverify_findings_against_texts([_finding()], {})
    assert not kept2 and len(downgraded2) == 1
    assert downgraded2[0]["downgrade_reason"] == "quote_reverification_unavailable"


# ── reaudit_finding (pure classifier behind the re-audit hook) ─────────────

def test_reaudit_boilerplate_is_non_claim():
    title = "Eat less, live longer? The science of fasting and longevity"
    result = reaudit_finding(
        {"statement": title, "quote": title,
         "citations": [{"source_title": title, "source_url": "https://example.org/a"}]},
        live_text=None)
    assert result["classification"] == "NON_CLAIM"
    assert result["verdict"] == "BOILERPLATE"


def test_reaudit_bruker_claim_is_unsupported():
    result = reaudit_finding(
        _finding(BRUKER_STATEMENT, BRUKER_QUOTE, BRUKER_URL), BRUKER_LIVE_PAGE)
    assert result["classification"] == "CLAIM"
    assert result["verdict"] == "UNSUPPORTED"
    assert result["reasons"] == ["quote_not_in_live_source"]
    assert result["single_source"] is True


def test_reaudit_unretrievable_source_is_unverifiable():
    result = reaudit_finding(_finding(), None)
    assert result["verdict"] == "UNVERIFIABLE"


def test_reaudit_clean_claim_is_verified():
    result = reaudit_finding(_finding(), PAGE_TEXT)
    assert result["verdict"] == "VERIFIED"
    assert result["single_source"] is True


def test_reaudit_coverage_failure_is_partial():
    statement = ("The aspartame safety assessment concluded that aspartame "
                 "is safe, and consumption rose 47 percent in 2025.")
    result = reaudit_finding(_finding(statement), PAGE_TEXT)
    assert result["verdict"] == "PARTIAL"
    assert result["reasons"][0].startswith("coverage:unsupported_number:")


# ── collect_live_brief live re-verification (integration) ──────────────────

P1 = ("The aspartame safety assessment concluded that aspartame is safe "
      "within the acceptable daily intake of 0-40 mg/kg body weight for "
      "aspartame consumers.")
P2 = ("The assessment of aspartame safety reviewed aspartame studies "
      "from many countries over several decades of published research.")
HTML = f"<html><body><p>{P1}</p><p>{P2}</p></body></html>"
HTML_DIVERGED = ("<html><body><p>Site navigation and product overview "
                 "for specialty solids probes and accessories.</p>"
                 "<p>These probes are designed for single crystals, "
                 "powders and oriented samples in laboratories.</p>"
                 "</body></html>")


class _Search:
    def __init__(self, urls):
        self._urls = urls

    async def fetch(self, query, max_results=5):
        return [SimpleNamespace(url=u, title="Aspartame assessment") for u in self._urls]


class _Fetch:
    """First fetch per URL serves the collection page; later fetches (the
    live re-verification retrieval) serve ``second`` or fail."""

    def __init__(self, pages, second=None, fail_second=False):
        self._pages = pages
        self._second = second or {}
        self._fail_second = fail_second
        self.calls = {}

    async def fetch(self, url, max_bytes=1_000_000):
        self.calls[url] = self.calls.get(url, 0) + 1
        if self.calls[url] >= 2:
            if self._fail_second:
                raise RuntimeError("fetch failed")
            html = self._second.get(url, self._pages[url])
        else:
            html = self._pages[url]
        return SimpleNamespace(status_code=200, content_type="text/html",
                               final_url=url, content=html.encode())


def _sid(url):
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _draft(findings):
    async def _synth(query, documents):
        return {"status": "SUCCESS", "findings": findings,
                "answer_kind": "source_attributed_model_draft",
                "quotes_verified": True, "semantic_entailment_verified": True,
                "synthesis_provider": "stub"}
    return _synth


def _draft_finding(url, statement=STATEMENT, quote=QUOTE):
    return {"statement": statement, "quote": quote,
            "status": "source_attributed_model_draft",
            "independently_verified": False, "single_source": True,
            "quote_verified": True, "entailment_verified": True,
            "citations": [{"source_id": _sid(url), "source_title": "Aspartame assessment",
                           "source_url": url}]}


async def test_brief_happy_path_marks_live_reverified():
    result = await collect_live_brief(
        "aspartame safety assessment", _Search([URL]),
        _Fetch({URL: HTML}), synthesize=_draft([_draft_finding(URL)]))
    assert result["status"] == "SUCCESS"
    assert result["quotes_verified"] is True
    assert "downgraded_findings" not in result
    finding = result["findings"][0]
    assert finding["live_quote_reverified"] is True
    assert finding["single_source"] is True
    assert finding["independently_verified"] is False


async def test_brief_diverged_live_page_downgrades_and_fails_closed():
    result = await collect_live_brief(
        "aspartame safety assessment", _Search([URL]),
        _Fetch({URL: HTML}, second={URL: HTML_DIVERGED}),
        synthesize=_draft([_draft_finding(URL)]))
    # The only draft finding failed live re-verification: no verified
    # brief is claimed; the extractive findings are returned labelled
    # unsynthesised (TASK-REL-016 semantics), and the downgrade is on
    # the record with its reason.
    assert result["status"] == "DEGRADED"
    assert result["answer_kind"] == "unsynthesised_raw_findings"
    assert result["quotes_verified"] is False
    assert result["live_reverification"] == {"checked": 1, "kept": 0, "downgraded": 1}
    downgraded = result["downgraded_findings"]
    assert len(downgraded) == 1
    assert downgraded[0]["downgrade_reason"] == "quote_not_in_live_source"
    assert all(f["status"] == "source_excerpt" for f in result["findings"])


async def test_brief_unavailable_reverification_downgrades():
    result = await collect_live_brief(
        "aspartame safety assessment", _Search([URL]),
        _Fetch({URL: HTML}, fail_second=True),
        synthesize=_draft([_draft_finding(URL)]))
    assert result["status"] == "DEGRADED"
    assert result["downgraded_findings"][0]["downgrade_reason"] == \
        "quote_reverification_unavailable"


async def test_brief_partial_downgrade_keeps_verified_findings():
    url2 = "https://example.org/second"
    html2 = ("<html><body><p>The aspartame safety assessment also covered "
             "aspartame exposure estimates for children and adults in "
             "the assessment report.</p></body></html>")
    quote2 = ("aspartame safety assessment also covered aspartame "
              "exposure estimates for children")
    statement2 = ("The aspartame safety assessment also covered aspartame "
                  "exposure estimates for children and adults.")
    result = await collect_live_brief(
        "aspartame safety assessment", _Search([URL, url2]),
        _Fetch({URL: HTML, url2: html2}, second={url2: HTML_DIVERGED}),
        synthesize=_draft([_draft_finding(URL),
                           _draft_finding(url2, statement2, quote2)]))
    assert result["status"] == "SUCCESS"
    assert result["quotes_verified"] is False
    assert result["live_reverification"] == {"checked": 2, "kept": 1, "downgraded": 1}
    assert len(result["findings"]) == 1
    assert result["findings"][0]["live_quote_reverified"] is True
    assert result["downgraded_findings"][0]["downgrade_reason"] == \
        "quote_not_in_live_source"


async def test_extractive_findings_surface_corroboration_flags():
    result = await collect_live_brief(
        "aspartame safety assessment", _Search([URL]), _Fetch({URL: HTML}))
    assert result["findings"], "expected extractive findings"
    for finding in result["findings"]:
        assert finding["independently_verified"] is False
        assert finding["single_source"] is True


def test_reaudit_script_imports_cleanly():
    import importlib.util
    import pathlib

    script = (pathlib.Path(__file__).resolve().parent.parent
              / "scripts" / "reaudit_live_research.py")
    spec = importlib.util.spec_from_file_location("reaudit_live_research", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.run_reaudit) and callable(module.main)
