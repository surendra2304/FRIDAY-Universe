"""
Unit tests for Multi-Provider Fallback Chain.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.ai_universe_client import AIUniverseResponse
from app.providers.direct import DirectProvider
from app.providers.provider_chain import (
    ProviderChain,
    ProviderChainResult,
    ProviderTier,
)


@pytest.mark.asyncio
async def test_provider_chain_ai_universe_success():
    mock_ai = MagicMock()
    mock_ai.ask = AsyncMock(
        return_value=AIUniverseResponse(
            answer="print('Generated via AI Universe')",
            confidence=0.95,
            unresolved_disagreements=[],
            key_evidence=[],
            run_id="run_999",
        )
    )
    chain = ProviderChain(primary_client=mock_ai)

    result = await chain.synthesize_file("main.py", "Create CLI tool")
    assert result.tier_used == ProviderTier.AI_UNIVERSE
    assert result.confidence == 0.95
    assert result.code == "print('Generated via AI Universe')"


@pytest.mark.asyncio
async def test_provider_chain_falls_back_to_direct_on_low_confidence():
    mock_ai = MagicMock()
    mock_ai.ask = AsyncMock(
        return_value=AIUniverseResponse(
            answer="partial code",
            confidence=0.50,  # Below 0.70 threshold
            unresolved_disagreements=[],
            key_evidence=[],
            run_id="run_low",
        )
    )
    fallback_prov = DirectProvider(
        mock_mode=True,
        mock_response="### File: main.py\n```python\nprint('Direct Provider Code')\n```",
    )
    chain = ProviderChain(primary_client=mock_ai, fallback_provider=fallback_prov)

    result = await chain.synthesize_file("main.py", "Create CLI tool")
    assert result.tier_used == ProviderTier.DIRECT
    assert "Direct Provider Code" in result.code


@pytest.mark.asyncio
async def test_provider_chain_falls_back_to_template_on_network_failure():
    mock_ai = MagicMock()
    mock_ai.ask = AsyncMock(side_effect=RuntimeError("Connection refused"))
    chain = ProviderChain(primary_client=mock_ai, fallback_provider=None)

    result = await chain.synthesize_file("index.html", "Create portfolio website")
    assert result.tier_used == ProviderTier.TEMPLATE
    assert "<!DOCTYPE html>" in result.code


def test_calculate_provenance():
    results = [
        ProviderChainResult(filename="main.py", code="...", tier_used=ProviderTier.AI_UNIVERSE),
        ProviderChainResult(
            filename="test_main.py", code="...", tier_used=ProviderTier.AI_UNIVERSE
        ),
        ProviderChainResult(filename="index.html", code="...", tier_used=ProviderTier.TEMPLATE),
    ]
    prov = ProviderChain.calculate_provenance(results)
    assert prov["ai_universe_percentage"] == 66.7
    assert prov["template_percentage"] == 33.3
    assert "Generated via:" in prov["summary"]
