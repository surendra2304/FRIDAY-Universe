"""TASK-REL-007B regression tests: chat persistence + dispatch timeout.

Round 1 (2026-11-14) production evidence: a coding task produced NO reply
after >2 minutes and the user message was MISSING from the restored
session transcript afterwards. Root causes pinned by these tests:

* ``execute_command`` logged the conversation only AFTER
  ``_dispatch_command`` returned — a hung turn persisted nothing.
* The chat path had no overall timeout (the final fallback runs
  ``agent.process_message`` in an executor with no bound; the Forge
  upstream alone allows 210s).

The fix: persist-first entries (begin before dispatch, finalize in place)
and an ``asyncio.wait_for`` budget (``FRIDAY_CHAT_TIMEOUT_SECONDS``,
default 120s) that returns an honest timeout reply.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from friday.api import server
from friday.api.server import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _preserve_history():
    saved = list(server._conversation_history)
    server._conversation_history.clear()
    yield
    server._conversation_history.clear()
    server._conversation_history.extend(saved)


def _history(client: TestClient) -> list[dict]:
    resp = client.get("/api/v1/conversation/history", params={"limit": 50})
    assert resp.status_code == 200
    body = resp.json()
    return body.get("entries") or body.get("history") or body.get("items") or []


def _find(client: TestClient, user_input: str) -> dict | None:
    for e in _history(client):
        if e.get("user_input") == user_input:
            return e
    return None


# ------------------------------------------------------------------ timeout


def test_slow_dispatch_returns_timeout_reply_and_keeps_user_message(client, monkeypatch):
    """The round-1 hang: dispatch never returns -> bounded honest reply,
    and the user message is in the history the console restores from."""

    async def _hang(command: str, *, boss_verified: bool = False):
        await asyncio.sleep(30)
        return {"reply": "too late", "metadata": {}}

    monkeypatch.setattr(server, "_dispatch_command", _hang)
    monkeypatch.setattr(server, "_chat_timeout_seconds", lambda: 0.3)

    start = time.monotonic()
    resp = client.post("/api/command", json={"command": "write the palindrome function"})
    elapsed = time.monotonic() - start

    assert elapsed < 10, f"chat turn was not bounded (took {elapsed:.1f}s)"
    body = resp.json()
    assert "still running" in (body.get("reply") or "")
    assert "<tool" not in (body.get("reply") or "")

    entry = _find(client, "write the palindrome function")
    assert entry is not None, "user message lost from conversation history"
    assert entry["status"] == "failed"
    assert "still running" in entry["friday_reply"]


# -------------------------------------------------------------- persist-first


def test_user_message_is_persisted_before_dispatch_completes(client, monkeypatch):
    """While dispatch is still running, the history already holds the
    user's message as a pending entry (transcript can never lose it)."""
    observed: dict = {}

    async def _spy(command: str, *, boss_verified: bool = False):
        current = [e for e in server._conversation_history if e.user_input == command]
        observed["during"] = [(e.status, e.friday_reply) for e in current]
        return {"reply": "done and dusted", "metadata": {}}

    monkeypatch.setattr(server, "_dispatch_command", _spy)

    resp = client.post("/api/command", json={"command": "a normal quick ask"})
    assert resp.status_code == 200
    assert observed["during"] == [("pending", "")], (
        f"expected exactly one pending entry during dispatch, saw {observed['during']}"
    )

    entry = _find(client, "a normal quick ask")
    assert entry is not None
    assert entry["status"] == "success"
    assert entry["friday_reply"] == "done and dusted"
    # exactly one entry for the turn (finalize mutates, never duplicates)
    assert len([e for e in _history(client) if e.get("user_input") == "a normal quick ask"]) == 1


def test_dispatch_exception_still_keeps_user_message(client, monkeypatch):
    async def _boom(command: str, *, boss_verified: bool = False):
        raise RuntimeError("dispatch exploded")

    monkeypatch.setattr(server, "_dispatch_command", _boom)

    resp = client.post("/api/command", json={"command": "message that must survive"})
    assert resp.status_code >= 500
    entry = _find(client, "message that must survive")
    assert entry is not None, "user message lost when dispatch raised"
    assert entry["status"] == "failed"


# ------------------------------------------------------------------ timeout config


def test_chat_timeout_seconds_parsing(monkeypatch):
    monkeypatch.delenv("FRIDAY_CHAT_TIMEOUT_SECONDS", raising=False)
    assert server._chat_timeout_seconds() == 120.0
    monkeypatch.setenv("FRIDAY_CHAT_TIMEOUT_SECONDS", "45")
    assert server._chat_timeout_seconds() == 45.0
    monkeypatch.setenv("FRIDAY_CHAT_TIMEOUT_SECONDS", "not-a-number")
    assert server._chat_timeout_seconds() == 120.0
    monkeypatch.setenv("FRIDAY_CHAT_TIMEOUT_SECONDS", "99999")
    assert server._chat_timeout_seconds() == 600.0
    monkeypatch.setenv("FRIDAY_CHAT_TIMEOUT_SECONDS", "1")
    assert server._chat_timeout_seconds() == 5.0
