"""TASK-INT-056: synthesis-failure path preserves extractive excerpts.

When the synthesis provider fails (ProviderError / StructuredOutputError),
SynthesizerAgent.execute must return normally with the verified claims as
extractive excerpts — executive answer, findings grounded to the input claim
IDs, overall confidence Low, execution mode SYNTHESIS FAILED / EXTRACTIVE
FALLBACK, and a degradation entry. The success path and the
insufficient-evidence path are unchanged.
"""

from types import SimpleNamespace

import pytest

from intelx.agents.synthesizer import DraftFinding, DraftReport, SynthesizerAgent
from intelx.core.errors import ProviderError, StructuredOutputError
from intelx.models.gateway import ModelGateway
from intelx.models.types import Usage


def _claims():
    return [
        {
            "id": "c1",
            "text": "Silicon-graphite composite anodes reached 420 Wh/kg energy density.",
            "confidence": 0.9,
        },
        {
            "id": "c2",
            "text": "Sodium-ion cathodes achieved 160 Wh/kg energy density.",
            "confidence": 0.8,
        },
    ]


class FailingGateway(ModelGateway):
    """Gateway stub whose provider call always raises the given error."""

    def __init__(self, error: Exception):
        super().__init__()
        self._error = error

    async def complete(self, messages, **kwargs):
        raise self._error


class SucceedingGateway(ModelGateway):
    """Gateway stub returning a fixed LLM draft grounded to claim c1."""

    async def complete(self, messages, **kwargs):
        draft = DraftReport(
            executive_answer="Test synthesis answer.",
            key_findings=[
                DraftFinding(
                    statement="Silicon-graphite composite anodes reached 420 Wh/kg energy density.",
                    confidence=0.9,
                    confidence_label="High",
                    claim_ids=["c1"],
                )
            ],
            gaps=[],
        )
        return SimpleNamespace(
            parsed=draft,
            text=draft.model_dump_json(),
            usage=Usage(),
            provider="test",
            model="test-model",
        )


@pytest.mark.asyncio
async def test_provider_error_returns_extractive_excerpts():
    """ProviderError: execute returns normally with the claim excerpts."""
    agent = SynthesizerAgent(
        gateway=FailingGateway(ProviderError("provider down (test stub)"))
    )
    result = await agent.execute(
        objective="Compare anode energy densities", claims=_claims()
    )

    assert "Synthesis failed (ProviderError)" in result.executive_summary
    assert "420 Wh/kg" in result.executive_summary
    assert "160 Wh/kg" in result.executive_summary
    assert result.overall_confidence_label == "Low"
    assert {f.statement for f in result.findings} == {
        "Silicon-graphite composite anodes reached 420 Wh/kg energy density.",
        "Sodium-ion cathodes achieved 160 Wh/kg energy density.",
    }
    assert {tuple(f.claim_ids) for f in result.findings} == {("c1",), ("c2",)}
    assert any("ProviderError" in gap for gap in result.gaps)
    assert "SYNTHESIS FAILED / EXTRACTIVE FALLBACK" in result.report_markdown
    assert "Synthesis provider failed (ProviderError)" in result.report_markdown
    assert "420 Wh/kg" in result.report_markdown


@pytest.mark.asyncio
async def test_structured_output_error_returns_extractive_excerpts():
    """StructuredOutputError is a model failure too: same fallback."""
    agent = SynthesizerAgent(
        gateway=FailingGateway(
            StructuredOutputError("schema validation failed (test stub)")
        )
    )
    result = await agent.execute(
        objective="Compare anode energy densities", claims=_claims()
    )

    assert "Synthesis failed (StructuredOutputError)" in result.executive_summary
    assert result.overall_confidence_label == "Low"
    assert {f.statement for f in result.findings} == {
        "Silicon-graphite composite anodes reached 420 Wh/kg energy density.",
        "Sodium-ion cathodes achieved 160 Wh/kg energy density.",
    }
    assert "SYNTHESIS FAILED / EXTRACTIVE FALLBACK" in result.report_markdown


@pytest.mark.asyncio
async def test_provider_error_with_no_claims_keeps_insufficient_evidence_path():
    """No claims: the insufficient-evidence path runs; the gateway is never called."""
    agent = SynthesizerAgent(
        gateway=FailingGateway(ProviderError("provider down (test stub)"))
    )
    result = await agent.execute(
        objective="Compare anode energy densities", claims=[]
    )

    assert "INSUFFICIENT EVIDENCE" in result.executive_summary
    assert result.overall_confidence_label == "Very low"
    assert "SYNTHESIS FAILED" not in result.report_markdown


@pytest.mark.asyncio
async def test_succeeding_gateway_uses_llm_draft():
    """Success path unchanged: the LLM draft is returned as before."""
    agent = SynthesizerAgent(gateway=SucceedingGateway())
    result = await agent.execute(
        objective="Compare anode energy densities", claims=_claims()
    )

    assert result.executive_summary == "Test synthesis answer."
    assert [f.statement for f in result.findings] == [
        "Silicon-graphite composite anodes reached 420 Wh/kg energy density."
    ]
    assert result.overall_confidence_label == "High"
    assert "SYNTHESIS FAILED" not in result.report_markdown
