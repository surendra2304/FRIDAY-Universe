"""TASK-IG-FRD-007 — offline fallback tests (Project NOMAD miniature)."""

from __future__ import annotations

import os

import pytest

from friday.core.exceptions import LLMProviderError
from friday.core.types import Message, Role
from friday.llm.base import BaseLLMProvider
from friday.llm.fallback_chain_provider import FallbackChainLLMProvider
from friday.llm.offline_fallback import (
    OFFLINE_LABEL,
    LocalKnowledgeStore,
    OfflineFallbackProvider,
    offline_fallback_enabled,
)


def _store(tmp_path):
    store = LocalKnowledgeStore(path=str(tmp_path / "kb.json"))
    store.cache_answer(
        "What is the capital of France?",
        "The capital of France is Paris.",
        source="test",
    )
    store.ingest_facts([{"fact_text": "The fleet standup happens at 9am IST."}])
    return store


def _provider(tmp_path):
    return OfflineFallbackProvider(store=_store(tmp_path))


def _user(text):
    return [Message(role=Role.USER, content=text)]


def test_store_search_hit_and_miss(tmp_path):
    store = _store(tmp_path)
    hit = store.search("capital of France")
    assert hit is not None and "Paris" in hit["answer"]
    assert store.search("quantum entanglement lecture notes") is None
    fact = store.search("when is the fleet standup")
    assert fact is not None and "9am" in fact["answer"]


def test_provider_hit_is_labelled_cached(tmp_path):
    msg = _provider(tmp_path).generate(_user("What is the capital of France?"))
    assert msg.content.startswith(OFFLINE_LABEL)
    assert "Paris" in msg.content
    assert msg.metadata["offline_fallback"] is True
    assert msg.metadata["cached"] is True


def test_provider_miss_is_honest_unavailable(tmp_path):
    msg = _provider(tmp_path).generate(_user("Explain black hole entropy in detail"))
    assert msg.content.startswith(OFFLINE_LABEL)
    assert "nothing cached" in msg.content
    assert "won't guess" in msg.content
    assert msg.metadata["cached"] is False


def test_provider_uses_last_user_message(tmp_path):
    messages = [
        Message(role=Role.USER, content="unrelated earlier question"),
        Message(role=Role.ASSISTANT, content="some answer"),
        Message(role=Role.USER, content="What is the capital of France?"),
    ]
    msg = _provider(tmp_path).generate(messages)
    assert "Paris" in msg.content


class _DeadProvider(BaseLLMProvider):
    @property
    def provider_name(self):
        return "dead"

    def generate(self, messages, tools=None):
        raise LLMProviderError("network unreachable")


def test_chain_falls_through_to_offline(tmp_path):
    chain = FallbackChainLLMProvider([_DeadProvider(model="x"), _provider(tmp_path)])
    msg = chain.generate(_user("What is the capital of France?"))
    assert "Paris" in msg.content
    assert msg.metadata.get("offline_fallback") is True


def test_env_gate(monkeypatch):
    monkeypatch.delenv("FRIDAY_OFFLINE_FALLBACK", raising=False)
    assert offline_fallback_enabled() is False
    monkeypatch.setenv("FRIDAY_OFFLINE_FALLBACK", "on")
    assert offline_fallback_enabled() is True
    monkeypatch.setenv("FRIDAY_OFFLINE_FALLBACK", "off")
    assert offline_fallback_enabled() is False


def test_store_persistence(tmp_path):
    path = str(tmp_path / "kb.json")
    LocalKnowledgeStore(path=path).cache_answer("q one two three", "answer body")
    reloaded = LocalKnowledgeStore(path=path)
    assert len(reloaded) == 1
    assert reloaded.search("one two three") is not None


def test_ingest_skips_empty_records(tmp_path):
    store = LocalKnowledgeStore(path=str(tmp_path / "kb.json"))
    added = store.ingest_facts([{"fact_text": "  "}, {"nope": 1}, {"content": "Real fact here."}])
    assert added == 1
