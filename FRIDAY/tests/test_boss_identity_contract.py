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

    # asyncio.run (not get_event_loop().run_until_complete): the deprecated
    # pattern raised "no current event loop" whenever an earlier test in the
    # same process had already run asyncio.run() — e.g. any fast-path test
    # that dispatches through a fleet tool. asyncio.run is loop-safe here.
    return asyncio.run(_dispatch_command(message))


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


# ---------------------------------------------------------------------------
# TASK-BRAIN-002: deterministic memory (owner directive 2026-11-11 IST)
# "Remember this Boss: my favorite chai is masala chai and I review the
# fleet every morning at 9" used to be hijacked by the fleet-status
# fast-path (bare keyword 'fleet') and answered with a probe report.
# ---------------------------------------------------------------------------

STORE_SENTENCE = "Remember this Boss: my favorite chai is masala chai and I review the fleet every morning at 9"
STORED_FACT = "my favorite chai is masala chai and I review the fleet every morning at 9"


class _StubMemora:
    """Records facts and replays them — no external service needed."""

    def __init__(self) -> None:
        self.facts: list[str] = []
        self.recall_calls: list[str] = []

    def record_fact(self, agent_name, fact_text, category="preference", importance=0.95):
        self.facts.append(fact_text)
        return {"status": "success", "content_text": fact_text}

    def recall_memories(self, agent_name, query, limit=5):
        self.recall_calls.append(query)
        return [{"content_text": f} for f in self.facts]


@pytest.fixture()
def stub_memora(monkeypatch):
    stub = _StubMemora()

    def _factory(agent_name="friday"):
        import friday.memory.memora_client as mc

        return stub

    monkeypatch.setattr("friday.memory.memora_client.memora_client", stub, raising=True)
    # The server imports the client inside functions via
    # `from friday.memory.memora_client import memora_client`, so patching
    # the module attribute is enough.
    return stub


def test_memory_store_not_hijacked_by_fleet_status(stub_memora) -> None:
    result = _dispatch(STORE_SENTENCE)
    meta = result["metadata"]
    assert meta.get("memory_store") is True, result
    assert meta.get("fast_path") is not None
    assert stub_memora.facts == [STORED_FACT], stub_memora.facts
    # The old failure: a fleet probe report instead of a memory confirmation.
    assert "specialist agents up" not in result["reply"]
    assert "probe" not in result["reply"].lower()
    assert "locked in" in result["reply"].lower()
    assert "boss" in result["reply"].lower()


def test_memory_store_plain_remember(stub_memora) -> None:
    _dispatch("remember my birthday is on the twelfth of march")
    assert any("birthday" in f for f in stub_memora.facts)


def test_memory_recall_returns_stored_facts(stub_memora) -> None:
    _dispatch(STORE_SENTENCE)
    result = _dispatch("what do you remember about me")
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert meta.get("remembered_count", 0) >= 1
    assert "masala chai" in result["reply"]
    assert "boss" in result["reply"].lower()


def test_memory_recall_honest_when_empty(stub_memora) -> None:
    result = _dispatch("what do you remember about me")
    assert result["metadata"].get("memory_recall") is True
    assert result["metadata"].get("remembered_count") == 0
    assert "empty" in result["reply"].lower() or "don't have anything" in result["reply"].lower()


def test_recall_beats_remember_for_questions(stub_memora) -> None:
    _dispatch(STORE_SENTENCE)
    result = _dispatch("do you remember my chai preference")
    assert result["metadata"].get("memory_recall") is True
    assert "masala chai" in result["reply"]


def test_fleet_status_still_works(stub_memora) -> None:
    """The memory fast-path must not swallow genuine fleet questions."""
    result = _dispatch("how's the fleet?")
    assert result["metadata"].get("memory_store") is None
    assert result["metadata"].get("memory_recall") is None
    # (may answer via the fleet probe fast-path or the cognitive loop —
    # either way it must NOT claim to have stored a memory.)
