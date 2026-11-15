"""TASK-INT-006 — owner-briefing format for IntelX delivered research.

Contract under test (intelx/core/owner_briefing.py, wired into
collect_live_brief and export_text_citations):
- headline answer first, plain confidence with measured basis, cited
  evidence, and mechanically derived "what would change this conclusion";
- confidence caps at Moderate (attribution is verified, facts are not)
  and drops to Low for single-domain drafts, raw excerpts, failed
  synthesis, disputed or inference-only stored findings;
- the stored export's [C:]/[S:] citation-token contract is preserved.
"""
from types import SimpleNamespace

import pytest

from intelx.api.live_research_task import collect_live_brief
from intelx.core.owner_briefing import (
    assess_live_briefing,
    distinct_domains,
    registrable_domain,
)
from intelx.core.report import export_text_citations

QUERY = "solid state batteries progress"

_DOC_A = (
    "Solid state batteries have moved from laboratory cells toward pilot "
    "production lines this year. Manufacturers report that solid state "
    "battery progress now centres on sulfide electrolytes and dry coating."
)
_DOC_B = (
    "Independent testing shows solid state batteries retaining strong "
    "cycle life in recent trials. Analysts tracking solid state battery "
    "progress caution that cost remains the main barrier to scale."
)


class _Search:
    def __init__(self, results):
        self._results = results

    async def fetch(self, query, max_results=10):
        return self._results


class _Fetch:
    def __init__(self, docs):
        self._docs = docs

    async def fetch(self, url, max_bytes=1_000_000):
        return SimpleNamespace(
            status_code=200, content_type="text/plain",
            final_url=url, content=self._docs[url].encode(),
        )


def _candidate(url, title):
    return SimpleNamespace(url=url, title=title)


async def _draft_synthesize(query, documents):
    findings = []
    for doc in documents[:2]:
        quote = doc["text"].split(". ")[0].strip() + "."
        findings.append({
            "statement": f"Finding from {doc['title']}: the source reports "
                         f"measured progress on the question.",
            "quote": quote,
            "status": "source_attributed_model_draft",
            "independently_verified": False,
            "citations": [{"source_id": doc["source_id"],
                           "source_title": doc["title"],
                           "source_url": doc["url"]}],
        })
    return {"status": "SUCCESS", "findings": findings,
            "answer_kind": "source_attributed_model_draft",
            "quotes_verified": True, "semantic_entailment_verified": False,
            "synthesis_provider": "inference"}


def _two_domain_setup():
    search = _Search([
        _candidate("https://journal-a.org/battery-paper", "Battery Journal"),
        _candidate("https://news-b.com/battery-story", "Battery News"),
    ])
    fetch = _Fetch({
        "https://journal-a.org/battery-paper": _DOC_A,
        "https://news-b.com/battery-story": _DOC_B,
    })
    return search, fetch


# ── domain helpers ──────────────────────────────────────────────────────

def test_registrable_domain_normalisation():
    assert registrable_domain("https://www.bbc.co.uk/news/x") == "bbc.co.uk"
    assert registrable_domain("https://news.google.com/rss/a") == "google.com"
    assert distinct_domains(
        ["https://www.example.com/a", "https://example.com/b",
         "https://other.org/c"]) == ["example.com", "other.org"]


# ── live brief path ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_live_draft_two_domains_is_moderate_and_headline_first():
    search, fetch = _two_domain_setup()
    result = await collect_live_brief(QUERY, search, fetch,
                                      synthesize=_draft_synthesize)
    assert result["status"] == "SUCCESS"
    text = result["text_response"]
    headline = result["findings"][0]["statement"]
    assert text.startswith(headline)
    assert "Confidence: Moderate" in text
    assert "verified verbatim" in text
    assert "caps at Moderate" in text
    assert "What would change this conclusion:" in text
    # Retired disclaimer-first headers are gone from the delivered text.
    assert "quotations checked, claims not independently verified" not in text
    assert "Retrieved-source excerpts —" not in text
    briefing = result["briefing"]
    assert briefing["headline"] == headline
    assert briefing["confidence_level"] == "Moderate"
    assert briefing["change_conditions"]


@pytest.mark.asyncio
async def test_live_draft_single_domain_is_low_with_named_condition():
    search = _Search([
        _candidate("https://journal-a.org/one", "Battery Journal"),
        _candidate("https://journal-a.org/two", "Battery Journal"),
    ])
    fetch = _Fetch({
        "https://journal-a.org/one": _DOC_A,
        "https://journal-a.org/two": _DOC_B,
    })
    result = await collect_live_brief(QUERY, search, fetch,
                                      synthesize=_draft_synthesize)
    assert result["briefing"]["confidence_level"] == "Low"
    conditions = " ".join(result["briefing"]["change_conditions"])
    assert "single domain (journal-a.org)" in conditions


@pytest.mark.asyncio
async def test_live_excerpts_without_synthesis_are_low_and_labelled():
    search, fetch = _two_domain_setup()
    result = await collect_live_brief(QUERY, search, fetch)
    assert result["answer_kind"] == "source_excerpts"
    assert result["briefing"]["confidence_level"] == "Low"
    assert result["text_response"].startswith(
        "Strongest retrieved passage (verbatim — not a synthesised answer):")
    assert "no synthesis was run" in result["briefing"]["confidence_basis"]


@pytest.mark.asyncio
async def test_live_synthesis_failure_keeps_excerpts_and_states_no_conclusion():
    async def failing_synthesize(query, documents):
        return {"status": "DEGRADED",
                "error": "question_evidence_insufficient", "findings": []}

    search, fetch = _two_domain_setup()
    result = await collect_live_brief(QUERY, search, fetch,
                                      synthesize=failing_synthesize)
    assert result["status"] == "DEGRADED"
    assert result["answer_kind"] == "unsynthesised_raw_findings"
    assert result["findings"]  # REL-016: evidence is never discarded
    assert result["briefing"]["confidence_level"] == "Low"
    assert result["text_response"].startswith("No conclusion — synthesis failed")
    assert "Synthesis failed (question_evidence_insufficient)" in \
        result["briefing"]["confidence_basis"]


def test_live_assessment_never_emits_high():
    for kind, status, quotes in [
        ("source_attributed_model_draft", "succeeded", True),
        ("source_excerpts", "not_attempted", False),
        ("unsynthesised_raw_findings", "failed", False),
    ]:
        a = assess_live_briefing(
            answer_kind=kind, synthesis_status=status,
            synthesis_error_reason="x" if status == "failed" else None,
            quotes_verified=quotes,
            source_urls=["https://a.org/1", "https://b.com/2"],
            findings_count=2)
        assert a.level in ("Moderate", "Low")


# ── stored export path ──────────────────────────────────────────────────

def _stored_fixture():
    findings = [
        {
            "statement": "Sodium battery energy density reached 160 Wh/kg in 2025.",
            "status": "verified",
            "confidence": 0.95,
            "claim_ids": ["claim-7890"],
            "citations": [
                {"source_title": "Battery Research Journal",
                 "source_url": "https://example.com/paper"}
            ],
        },
        {
            "statement": "Solid state packs entered pilot production this year.",
            "status": "verified",
            "confidence": 0.9,
            "claim_ids": ["claim-7891"],
            "citations": [
                {"source_title": "Cell Weekly",
                 "source_url": "https://cellweekly.net/pilot"}
            ],
        },
    ]
    sources = [
        {"id": "src-01", "title": "Battery Research Journal",
         "location": "https://example.com/paper"},
        {"id": "src-02", "title": "Cell Weekly",
         "location": "https://cellweekly.net/pilot"},
    ]
    return findings, sources


def test_stored_export_headline_first_moderate_and_tokens_preserved():
    from intelx.agents.citations import CitationValidator

    findings, sources = _stored_fixture()
    text = export_text_citations(findings, sources)
    assert text.startswith(
        "Sodium battery energy density reached 160 Wh/kg in 2025.")
    assert "Confidence: Moderate" in text
    assert "### Key Findings with Citations" in text
    assert "### What Would Change This Conclusion" in text
    assert "### Sources & Evidence References" in text
    assert "[C:claim-78" in text
    validator = CitationValidator()
    assert validator.validate(
        text, {"src-01", "src-02"}, {"claim-7890", "claim-7891"}).valid


def test_stored_export_disputed_finding_is_low():
    findings, sources = _stored_fixture()
    findings[1]["status"] = "disputed"
    text = export_text_citations(findings, sources)
    assert "Confidence: Low" in text
    assert "disputed" in text


def test_stored_export_inference_only_is_low_and_headline_prefixed():
    findings = [{
        "statement": "Cost parity is expected by 2027.",
        "status": "inference",
        "confidence": 0.5,
        "claim_ids": [],
    }]
    text = export_text_citations(findings, [])
    assert text.startswith("[Inference] Cost parity is expected by 2027.")
    assert "Confidence: Low" in text


def test_stored_export_empty_findings_stays_valid():
    text = export_text_citations([], [])
    assert "No findings were produced" in text
    assert "Confidence: Low" in text
