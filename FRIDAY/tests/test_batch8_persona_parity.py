"""Checklist A8 (MASTER_COMPLETION_CHECKLIST) — Batch 8, ZAI Agent 2.

Parity test: the chat system message and the voice system instruction must
both carry every key phrase from the shared Boss contract. If either path
drops a rule, this test fails — preventing the two surfaces from drifting
apart in how FRIDAY identifies itself.

This is the lock that makes A8 ("personality consistency across chat AND
voice") durable: a future edit to one path that forgets the contract is
caught here, not in production.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class TestPersonaParity:
    """A8: chat and voice must carry the same Boss contract."""

    @pytest.fixture()
    def chat_prompt(self) -> str:
        from friday.agent.prompts import build_system_message
        from friday.core.config import Settings

        msg = build_system_message(Settings())
        return msg.content or ""

    @pytest.fixture()
    def voice_prompt(self) -> str:
        # The voice path builds its instruction inside GeminiLiveVoiceSession.
        # We extract just the text via the builder, without connecting.
        from friday.voice.gemini_live_session import GeminiLiveVoiceSession

        session = GeminiLiveVoiceSession.__new__(GeminiLiveVoiceSession)  # bypass __init__
        content = session._build_system_instruction()
        return content.parts[0].text if content and content.parts else ""

    @pytest.mark.parametrize("phrase", __import__("friday.persona.contract", fromlist=["contract_key_phrases"]).contract_key_phrases())
    def test_chat_carries_contract_phrase(self, chat_prompt: str, phrase: str) -> None:
        assert phrase in chat_prompt, f"chat prompt missing contract phrase: {phrase!r}"

    @pytest.mark.parametrize("phrase", __import__("friday.persona.contract", fromlist=["contract_key_phrases"]).contract_key_phrases())
    def test_voice_carries_contract_phrase(self, voice_prompt: str, phrase: str) -> None:
        assert phrase in voice_prompt, f"voice prompt missing contract phrase: {phrase!r}"

    def test_contract_module_is_the_single_source(self) -> None:
        """The shared contract module must exist and export its parts."""
        from friday.persona.contract import (
            BOSS_TITLE,
            boss_contract_lines,
            boss_contract_text,
            contract_key_phrases,
            owner_name,
        )

        assert BOSS_TITLE == "Boss"
        lines = boss_contract_lines()
        assert len(lines) >= 6
        assert all(isinstance(line, str) and line for line in lines)
        assert "Fully Responsive Intelligent Digital Assistant" in boss_contract_text()
        phrases = contract_key_phrases()
        assert len(phrases) >= 6
        # owner_name defaults to Surendra when settings don't override.
        assert owner_name()


class TestPersonaContractContent:
    """A8: the contract content is correct and self-consistent."""

    def test_no_third_party_attribution(self) -> None:
        from friday.persona.contract import boss_contract_text

        text = boss_contract_text()
        # The contract must never attribute FRIDAY to a third party.
        for banned in ("Google", "OpenAI", "Anthropic", "Mistral", "Groq", "OpenRouter"):
            assert banned not in text, f"contract mentions third-party {banned!r}"

    def test_boss_title_is_owner_chosen(self) -> None:
        from friday.persona.contract import BOSS_TITLE

        # Owner directive 2026-11-11: the title is "Boss", not "sir" or "master".
        assert BOSS_TITLE == "Boss"
