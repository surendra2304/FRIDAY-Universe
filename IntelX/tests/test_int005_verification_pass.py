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


# ── TASK-INT-033 regression tests ───────────────────────────────────────────
# Live root cause (run lr_6d6a7103193348adb29bd4e8, query "latest AI model
# releases", 2026-11-23): the served qwen draft degraded on
# synthesis_entailment_unverified although every quote was verbatim and
# every claim was supported. Three tokenisation defects in
# statement_support, each pinned below with the live shape. The U+2011
# in the fixtures is the non-breaking hyphen exactly as the source page
# serves it.

def test_support_accepts_sentence_final_entity():
    # Defect 1: the statement-final entity carried its sentence period
    # ("Google."), and the source — concatenated table cells — contains
    # no literal "Google." substring. The period is punctuation, not
    # part of the entity.
    source_text = (
        "AI Model Release Calendar: Latest AI Model Releases by Date. "
        "Nov. 23, 2026GLM-5.4Z.aiGeneral / Reasoning / Coding"
        "Nov. 18, 2026Gemini 4 NeonGoogleGeneral / Reasoning / Coding"
    )
    ok, reason = statement_support(
        "The latest AI model releases include Gemini 4 Neon from Google.",
        source_text)
    assert ok, reason


def test_support_accepts_unicode_hyphen_entity():
    # Defect 2: the source spells the model name with a non-breaking
    # hyphen (U+2011) while the model writes an ASCII hyphen. The two
    # spellings are the same entity.
    source_text = (
        "AI Model Release Calendar: November 2026 releases. "
        "Nov. 17, 2026GPT‑6.2 AstraOpenAIGeneral / Reasoning / Coding. "
        "The calendar lists models released in November 2026."
    )
    ok, reason = statement_support(
        "OpenAI released GPT-6.2 Astra on November 17, 2026.", source_text)
    assert ok, reason


def test_support_accepts_glued_table_coverage():
    # Defect 3: the coverage leg required exact token-vocabulary
    # membership, but the source text is concatenated table cells, so
    # the vocabulary holds glued tokens ("AstraOpenAI") that never equal
    # the statement's clean words ("astra"). Containment is the check.
    source_text = (
        "AI Model Release Calendar: November 2026. "
        "Nov. 17, 2026GPT‑6.2 AstraOpenAIGeneral / Reasoning / Coding"
        "Nov. 17, 2026GPT‑6.2 SolOpenAIGeneral / Reasoning / Coding. "
        "Models released in November 2026."
    )
    ok, reason = statement_support(
        "OpenAI released GPT-6.2 Astra and GPT-6.2 Sol on November 17, 2026.",
        source_text)
    assert ok, reason


# The exact draft the live gateway served in probe B (2026-11-23 ~19:12
# IST) and the verbatim quotes it carried, against a source document
# shaped like the live calendar page. On the pre-fix screen this draft
# degrades with synthesis_entailment_unverified (findings 0 and 2); with
# the fix it returns SUCCESS.
_LIVE_CALENDAR_TEXT = (
    "AI Model Release Calendar: Latest AI Model Releases by Date. "
    "This page lists the latest AI model releases in November 2026, "
    "including the models released this month. "
    "Nov. 23, 2026GLM-5.4Z.aiGeneral / Reasoning / Coding"
    "Nov. 18, 2026Ideogram 4.6Ideogram AIImage"
    "Nov. 18, 2026Gemini 4 NeonGoogleGeneral / Reasoning / Coding "
    "Nov. 9, 2026Claude Fable 5.2AnthropicGeneral / Reasoning / Coding"
    "Nov. 9, 2026Claude Mythos 5.2AnthropicGeneral / Reasoning / Cybersecurity "
    "Nov. 17, 2026GPT‑6.2 AstraOpenAIGeneral / Reasoning / Coding"
    "Nov. 17, 2026GPT‑6.2 SolOpenAIGeneral / Reasoning / Coding"
)
_LIVE_CALENDAR_DOC = {"source_id": "cal1", "title": "AI Model Release Calendar",
                      "url": "https://www.scriptbyai.com/ai-model-release-calendar/",
                      "text": _LIVE_CALENDAR_TEXT}
_LIVE_DRAFT_STATEMENTS = [
    ("The latest AI model releases in November 2026 include GLM-5.4 "
     "from Z.ai and Gemini 4 Neon from Google.",
     "Nov. 23, 2026GLM-5.4Z.aiGeneral / Reasoning / Coding"
     "Nov. 18, 2026Ideogram 4.6Ideogram AIImage"
     "Nov. 18, 2026Gemini 4 NeonGoogleGeneral / Reasoning / Coding"),
    ("Anthropic released Claude Fable 5.2 and Claude Mythos 5.2 "
     "on November 9, 2026.",
     "Nov. 9, 2026Claude Fable 5.2AnthropicGeneral / Reasoning / Coding"
     "Nov. 9, 2026Claude Mythos 5.2AnthropicGeneral / Reasoning / Cybersecurity"),
    ("OpenAI released GPT-6.2 Astra and GPT-6.2 Sol on November 17, 2026.",
     "Nov. 17, 2026GPT‑6.2 AstraOpenAIGeneral / Reasoning / Coding"
     "Nov. 17, 2026GPT‑6.2 SolOpenAIGeneral / Reasoning / Coding"),
]


async def test_synthesis_accepts_captured_live_draft():
    draft = GroundedDraft(
        findings=[GroundedFinding(statement=s, source_id="cal1", quote=q)
                  for s, q in _LIVE_DRAFT_STATEMENTS],
        insufficient_evidence=False,
    )
    result = await synthesize_grounded(
        "What are the latest AI model releases?",
        [_LIVE_CALENDAR_DOC],
        gateway=_StubGateway(draft),
    )
    assert result["status"] == "SUCCESS", result.get("error")
    assert result["semantic_entailment_verified"] is True
    assert len(result["findings"]) == 3
    assert all(f["entailment_verified"] is True for f in result["findings"])


# ── synthesize_grounded gate tests ──────────────────────────────────────────

class _CapturingGateway:
    """Records the messages synthesize_grounded sends; returns a valid draft."""

    def __init__(self, draft):
        self._draft = draft
        self.messages = None

    async def complete(self, **kwargs):
        self.messages = kwargs["messages"]
        return SimpleNamespace(provider="stub", parsed=self._draft)


_SYNTH_SENTENCE = (
    "The committee reviewed the published evidence and confirmed the "
    "assessment remains unchanged for the evaluated intake level. "
)


def _long_doc(source_id, chars=6_500):
    text = (_SYNTH_SENTENCE * 60)[:chars]
    return {
        "source_id": source_id,
        "title": "Assessment of the evaluated intake level for the substance under review",
        "url": "https://example.org/research/assessment-evaluated-intake-level-substance-review",
        "text": text,
    }


async def test_synthesis_prompt_stays_under_groq_guard():
    """TASK-INF-026: the full-budget synthesis prompt must estimate under
    Inference's 7,000-token Groq guard (calibrated estimator, 2.6
    chars/token). The 16,000-char budget estimated at ~7,051 tokens and
    diverted every synthesis to the fallback ladder (live 2026-11-23).
    The gateway estimator counts the system text twice (instruction +
    system message) and the gateway appends the JSON-schema suffix to
    the user message, so both are included here."""
    import json

    docs = [_long_doc(f"doc{i}") for i in range(1, 6)]
    statement = _SYNTH_SENTENCE.strip()
    quote = "The committee reviewed the published evidence and confirmed"
    gateway = _CapturingGateway(_draft(statement, quote=quote, source_id="doc1"))
    result = await synthesize_grounded(
        "What did the committee conclude about the evaluated intake level?",
        docs,
        gateway=gateway,
    )
    assert result["status"] == "SUCCESS"
    system_msg, user_msg = gateway.messages[0]["content"], gateway.messages[1]["content"]
    supplied = json.loads(user_msg)["source_documents"]
    assert sum(len(d["text"]) for d in supplied) == 14_000  # budget binds
    suffix = (
        "Return ONLY the final JSON object matching this schema, without analysis: "
        + json.dumps(GroundedDraft.model_json_schema())
    )
    estimate = (len(system_msg) * 2 + len(user_msg) + len(suffix)) * 5 // 13
    assert estimate <= 7_000, f"synthesis prompt estimates {estimate} tokens, over the Groq guard"


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
