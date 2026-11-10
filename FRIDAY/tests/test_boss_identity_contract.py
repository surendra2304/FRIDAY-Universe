"""TASK-BRAIN-001 (owner directive 2026-11-11 IST): FRIDAY must recognise
Surendra as Boss — instantly, warmly, and without ever arguing.

The old system prompt literally banned the word 'Boss' ("Never use
sycophantic titles like 'Boss'"), so the live Gemini brain answered the
owner's "I am Surendra and I am your boss" with an argument about being an
AI with no boss, and once even misrouted the sentence to a portfolio
answer. These tests pin the fix at both layers:

1. the deterministic fast-path in the chat router (guaranteed reply, no
   LLM in the loop, so the owner's exact test sentence can never
   misroute again), and
2. the system prompt contract (the ban is gone; the Boss contract is in).
"""

from __future__ import annotations

import asyncio

import pytest


def _dispatch(message: str) -> dict:
    from friday.api.server import _dispatch_command

    return asyncio.get_event_loop().run_until_complete(_dispatch_command(message))


@pytest.mark.parametrize(
    "message",
    [
        "I am Surendra and I am your boss",
        "i'm your boss",
        "I am your boss",
        "who is your boss",
        "do you have a boss",
        "you don't have a boss",
        "you are just an ai",
        "call me boss",
    ],
)
def test_boss_assertions_are_affirmed(message: str) -> None:
    result = _dispatch(message)
    reply = result["reply"].lower()
    assert "boss" in reply, f"no Boss affirmation for {message!r}: {result['reply']!r}"
    assert "i am an ai" not in reply
    assert "i'm an ai" not in reply
    assert "don't have a boss" not in reply.replace("you don't have a boss", "")
    assert "as an ai" not in reply
    assert result["metadata"].get("boss_identity") is True
    # The old failure mode: identity sentences misrouted to portfolio talk.
    assert "portfolio" not in reply


def test_boss_question_names_surendra() -> None:
    result = _dispatch("who is your boss")
    assert "surendra" in result["reply"].lower()


def test_system_prompt_boss_contract() -> None:
    from friday.agent.prompts import get_default_system_prompt
    from friday.core.config import get_settings

    prompt = get_default_system_prompt(get_settings())
    # The ban is gone.
    assert "never use sycophantic titles" not in prompt.lower()
    # The contract is in.
    assert "boss" in prompt.lower()
    assert "never say" in prompt.lower() or "never argue" in prompt.lower()


def test_persona_block_mentions_boss() -> None:
    from friday.persona.friday import FRIDAY_TEXT_BLOCK, FRIDAY_VOICE_BLOCK

    assert "Boss" in FRIDAY_TEXT_BLOCK
    assert "Boss" in FRIDAY_VOICE_BLOCK


def test_voice_prompt_boss_contract() -> None:
    """The Gemini Live spoken persona carries the same contract."""
    from unittest.mock import patch

    from friday.voice.gemini_live_session import GeminiLiveVoiceSession

    session = GeminiLiveVoiceSession.__new__(GeminiLiveVoiceSession)
    with patch("friday.voice.gemini_live_session.get_settings") as gs:
        gs.return_value.user_name = "Surendra"
        gs.return_value.persona = "friday"
        instruction = session._build_system_instruction()
    text = instruction.parts[0].text
    assert "boss" in text.lower()
    assert "never use sycophantic titles" not in text.lower()
