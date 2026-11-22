"""TASK-INT-005 verification pass tests.

The fact-check audit of stored research (IntelX/FACT_CHECK_AUDIT_INT005.md)
measured 24/27 stored claims fully verified (88.9%, below the 90%
standard). These tests pin the two pipeline fixes:

1. synthesize_grounded now screens every draft statement for support in
   its cited source text (numbers / named entities / content coverage)
   and fails closed with "synthesis_entailment_unverified"; a clean draft
   reports semantic_entailment_verified=True truthfully.
2. collect_live_brief never promotes page chrome (page title, breadcrumb,
   "Skip to main content") to a finding.
"""
from types import SimpleNamespace

import pytest

from intelx.api.grounded_live_research import (
    GroundedDraft,
    GroundedFinding,
    statement_support,
    synthesize_grounded,
)
from intelx.api.live_research_task import collect_live_brief

WHO_TEXT = (
    "The Joint Expert Committee on Food Additives concluded that the data "
    "evaluated indicated no sufficient reason to change the previously "
    "established acceptable daily intake of 0-40 mg/kg body weight for "
    "aspartame. The committee therefore reaffirmed that it is safe for a "
    "person to consume within this limit per day."
)
WHO_QUOTE = (
    "no sufficient reason to change the previously established acceptable "
    "daily intake of 0-40 mg/kg body weight for aspartame"
)
WHO_DOC = {"source_id": "who1", "title": "Aspartame assessment",
           "url": "https://www.who.int/example", "text": WHO_TEXT}


class _StubGateway:
    """Returns one fixed parsed draft, like GroundedInferenceGateway."""

    def __init__(self, draft):
        self._draft = draft

    async def complete(self, **_kwargs):
        return SimpleNamespace(provider="stub", parsed=self._draft)


def _draft(statement, quote=WHO_QUOTE, source_id="who1"):
    return GroundedDraft(
        findings=[GroundedFinding(statement=statement, source_id=source_id, quote=quote)],
        insufficient_evidence=False,
    )


# ── statement_support unit tests ────────────────────────────────────────────

def test_support_accepts_supported_statement():
    ok, reason = statement_support(
        "The Joint Expert Committee on Food Additives reaffirmed that "
        "aspartame is safe to consume within a daily limit of 40 mg/kg "
        "of body weight.", WHO_TEXT)
    assert ok and reason == "supported"


def test_support_rejects_invented_number():
    ok, reason = statement_support(
        "Aspartame intake rose by 47 percent in 2025 across all markets.",
        WHO_TEXT)
    assert not ok and reason.startswith("unsupported_number:")


def test_support_rejects_invented_entity():
    ok, reason = statement_support(
        "The committee said Samsung announced a new aspartame facility.",
        WHO_TEXT)
    assert not ok and reason.startswith("unsupported_entity:")


def test_support_rejects_bruker_style_claim():
    # The audit's UNSUPPORTED finding: statement vocabulary absent from the
    # cited page's actual text (specialty probes page, no operando /
    # batteries / supercapacitors content).
    page_text = (
        "Specialty solids probes for high-resolution solid-state NMR. "
        "These probes are designed for single crystals, powders and "
        "oriented samples, with static and magic-angle spinning options."
    )
    ok, _reason = statement_support(
        "Bruker provides specialized solid-state NMR probes designed for "
        "in-situ and operando research on energy storage materials, "
        "including batteries and supercapacitors.", page_text)
    assert not ok


# ── synthesize_grounded gate tests ──────────────────────────────────────────

async def test_synthesis_success_marks_entailment_verified():
    result = await synthesize_grounded(
        "What does the WHO say about aspartame?",
        [WHO_DOC],
        gateway=_StubGateway(_draft(
            "The Joint Expert Committee on Food Additives reaffirmed that "
            "aspartame is safe to consume within a daily limit of 40 mg/kg "
            "of body weight.")),
    )
    assert result["status"] == "SUCCESS"
    assert result["quotes_verified"] is True
    assert result["semantic_entailment_verified"] is True
    finding = result["findings"][0]
    assert finding["quote_verified"] is True
    assert finding["entailment_verified"] is True


async def test_synthesis_degrades_on_unentailed_statement():
    result = await synthesize_grounded(
        "What does the WHO say about aspartame?",
        [WHO_DOC],
        gateway=_StubGateway(_draft(
            "The Joint Expert Committee on Food Additives reaffirmed that "
            "aspartame is safe, and global consumption rose 47 percent "
            "in 2025.")),
    )
    assert result["status"] == "DEGRADED"
    assert result["error"] == "synthesis_entailment_unverified"
    # TASK-INT-018: the failure degrades, but the extractive excerpts are
    # preserved — verbatim WHO passages, labelled raw, never a brief.
    assert result["answer_kind"] == "unsynthesised_raw_findings"
    assert result["question_answered"] is False
    assert result["findings"]
    assert all(f["status"] == "source_excerpt" for f in result["findings"])
    assert all(f["quote"] in WHO_TEXT for f in result["findings"])
    assert all(f["citations"][0]["source_id"] == "who1" for f in result["findings"])


# ── collect_live_brief chrome filter tests ──────────────────────────────────

TITLE = ("Eat less, live longer? The science of fasting and longevity "
         "- USC Leonard Davis School of Gerontology")
REAL_1 = ("Researchers studying intermittent fasting report that fasting "
          "periods change how cells handle energy and stress over time.")
REAL_2 = ("Intermittent fasting has been studied for longevity effects "
          "in several controlled trials with human participants.")
HTML = f"""<html><body>
<h1>{TITLE}</h1>
<p>Home » Eat less, live longer? The science of fasting and longevity</p>
<p>Skip to main content. Intermittent fasting and longevity research continues to grow.</p>
<p>{REAL_1}</p>
<p>{REAL_2}</p>
</body></html>"""


class _Search:
    async def fetch(self, query, max_results=5):
        return [SimpleNamespace(url="https://example.org/article", title=TITLE)]


class _Fetch:
    async def fetch(self, url, max_bytes=1_000_000):
        return SimpleNamespace(status_code=200, content_type="text/html",
                               final_url=url, content=HTML.encode())


async def test_brief_never_promotes_chrome_to_findings():
    result = await collect_live_brief(
        "intermittent fasting longevity research", _Search(), _Fetch())
    statements = [f["statement"] for f in result["findings"]]
    assert statements, "expected the real paragraphs to survive"
    assert all("Skip to main content" not in s for s in statements)
    assert all(not s.startswith("Home »") for s in statements)
    assert all(TITLE not in s for s in statements)
    assert set(statements) == {REAL_1, REAL_2}


async def test_brief_keeps_real_paragraphs_when_no_chrome():
    class _FetchClean:
        async def fetch(self, url, max_bytes=1_000_000):
            html = f"<html><body><p>{REAL_1}</p><p>{REAL_2}</p></body></html>"
            return SimpleNamespace(status_code=200, content_type="text/html",
                                   final_url=url, content=html.encode())

    result = await collect_live_brief(
        "intermittent fasting longevity research", _Search(), _FetchClean())
    statements = {f["statement"] for f in result["findings"]}
    assert statements == {REAL_1, REAL_2}
