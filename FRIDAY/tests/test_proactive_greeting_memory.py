"""TASK-MEM-003: proactive memory across sessions.

"FRIDAY uses memory proactively across sessions — remembers the owner's
preferences, references past conversations." The reactive side (recall on
request, recalled memories in the LLM context, RememberFactTool) is merged.
The proactive side is pinned here: when the owner returns and greets FRIDAY,
FRIDAY volunteers a short reference to what it remembers — unprompted.

Rules:
- recall failure NEVER breaks the greeting (a plain greeting is fine);
- the memory line names actual recalled content (never invented);
- recall is attempted on greeting only (no extra latency elsewhere).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit]

from friday.agent.agent import FridayAgent
from friday.core.config import Settings


def _make_agent() -> FridayAgent:
    return FridayAgent(settings=Settings(env="testing"))


class TestProactiveGreetingMemory:
    def test_greeting_references_a_remembered_fact(self) -> None:
        from friday.memory import memora_client as mc

        with patch.object(
            mc.memora_client, "recall_memories",
            return_value=[{"content_text": "Owner prefers research briefs with citations."}],
        ):
            agent = _make_agent()
            response = agent.process_message("hello friday")
        assert "Since we last talked, I still remember this" in response.content
        assert "research briefs with citations" in response.content
        assert response.metadata.get("proactive_memory") is True
        assert response.metadata.get("remembered_count") == 1

    def test_greeting_without_memories_stays_clean(self) -> None:
        from friday.memory import memora_client as mc

        with patch.object(mc.memora_client, "recall_memories", return_value=[]):
            agent = _make_agent()
            response = agent.process_message("hello friday")
        assert "Since we last talked" not in response.content
        assert response.metadata.get("proactive_memory") is False
        assert response.content.strip()  # still a real greeting

    def test_recall_failure_never_breaks_the_greeting(self) -> None:
        from friday.memory import memora_client as mc

        with patch.object(
            mc.memora_client, "recall_memories",
            side_effect=ConnectionError("memora down"),
        ):
            agent = _make_agent()
            response = agent.process_message("hey friday")
        assert response.content.strip()
        assert "Since we last talked" not in response.content
        assert response.metadata.get("greeting_fast_path") is True

    def test_remembered_line_is_truncated_not_dumped(self) -> None:
        from friday.memory import memora_client as mc

        long_fact = "Owner likes " + "very detailed " * 40 + "reports."
        with patch.object(
            mc.memora_client, "recall_memories",
            return_value=[{"content_text": long_fact}],
        ):
            agent = _make_agent()
            response = agent.process_message("hi friday")
        remembered_line = response.content.split("I still remember this:")[1]
        assert len(remembered_line) < 200  # one short line, not a dump

    def test_short_noise_memories_are_ignored(self) -> None:
        from friday.memory import memora_client as mc

        with patch.object(
            mc.memora_client, "recall_memories",
            return_value=[{"content_text": "ok"}, {"content_text": ""}],
        ):
            agent = _make_agent()
            response = agent.process_message("hello")
        assert "Since we last talked" not in response.content


class TestServerGreetingProactiveMemory:
    """The /api/chat ladder's own greeting short-circuit volunteers memory too."""

    def _chat(self, monkeypatch, message):
        from fastapi.testclient import TestClient
        from friday.api import server as srv
        from friday.memory import memora_client as mc

        with patch.object(
            mc.memora_client, "recall_memories",
            return_value=[{"content_text": "Owner prefers research briefs with citations."}],
        ):
            client = TestClient(srv.app)
            return client.post(
                "/api/chat",
                json={"message": message},
                headers={"Origin": "http://testserver"},
            )

    def test_chat_greeting_includes_remembered_line(self, monkeypatch) -> None:
        monkeypatch.delenv("FRIDAY_API_KEY", raising=False)
        monkeypatch.delenv("FRIDAY_UNIVERSE_API_KEY", raising=False)
        monkeypatch.delenv("RENDER", raising=False)
        response = self._chat(monkeypatch, "hello friday")
        assert response.status_code == 200
        body = response.json()
        assert "Since we last talked, I still remember this" in body["reply"]
        assert "research briefs with citations" in body["reply"]
        assert body["metadata"].get("proactive_memory") is True

    def test_chat_greeting_clean_when_nothing_remembered(self, monkeypatch) -> None:
        from fastapi.testclient import TestClient
        from friday.api import server as srv
        from friday.memory import memora_client as mc

        monkeypatch.delenv("FRIDAY_API_KEY", raising=False)
        monkeypatch.delenv("FRIDAY_UNIVERSE_API_KEY", raising=False)
        monkeypatch.delenv("RENDER", raising=False)
        with patch.object(mc.memora_client, "recall_memories", return_value=[]):
            client = TestClient(srv.app)
            response = client.post(
                "/api/chat",
                json={"message": "hello"},
                headers={"Origin": "http://testserver"},
            )
        body = response.json()
        assert "Since we last talked" not in body["reply"]
        assert body["reply"].strip()
        assert body["metadata"].get("proactive_memory") is False
