"""Forget confirmations must never echo the forgotten content.

Production evidence (post-deploy proofs A, 2026-11-16, FRD-001 audit
prompt #19): "Forget the test code I gave you." deleted the record, but
the confirmation replied "Done, Boss — I've forgotten test code:
FRD001-BETA-9. from shared active memory." — restating the very content
the owner asked to forget, so it lived on in the conversation/audit
history (the #20-style follow-up "what was that test code again?" then
reproduced it from history). A forget confirmation that repeats the
forgotten content is self-defeating.

Contract pinned here, for BOTH forget confirmation surfaces:
- the chat fast path (``friday.api.server._dispatch_command``,
  memory_forget), shared and local-backend branches;
- the voice path (``friday.memory.voice_memory.handle_voice_memory`` —
  its return string is spoken aloud by the voice session).

On a successful delete the confirmation names the action and the
storage scope only: no verbatim span of the deleted record may appear
in the reply. The receipt metadata (forget_status, memory_id, success)
is unchanged, and the deletion itself still happens. Remember and
correction confirmations naming the (new) fact are by design and are
NOT covered here.
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit

FACT = 'my test code is "ZEBRA-QUARTZ-7319"'
MARKER = "ZEBRA-" + "QUARTZ-" + "7319"


class _FakeForgetClient:
    """forget_fact stub returning a deleted receipt WITH the record text,
    exactly like the real client — the surfaces under test must not
    render that text back to the owner."""

    def __init__(self, *, cloud: bool):
        self._cloud = cloud
        self.calls: list[tuple[str, str]] = []

    def forget_fact(self, agent_name: str, query: str, memory_id: str = "") -> dict:
        self.calls.append((agent_name, query))
        return {
            "status": "deleted",
            "id": "rec-7319",
            "content_text": FACT,
            "cloud": self._cloud,
        }


def _assert_no_echo(reply: str) -> None:
    assert MARKER not in reply
    assert "ZEBRA" not in reply
    assert FACT not in reply


# ---------------------------------------------------------------------------
# Chat fast path (friday.api.server._dispatch_command)
# ---------------------------------------------------------------------------

def test_chat_forget_shared_confirmation_does_not_echo(monkeypatch):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    fake = _FakeForgetClient(cloud=True)
    monkeypatch.setattr(module, "memora_client", fake)
    result = asyncio.run(_dispatch_command("forget my test code"))

    assert fake.calls, "forget_fact was never called"
    _assert_no_echo(result["reply"])
    assert "shared active memory" in result["reply"]
    # Receipt metadata unchanged: status + id still reported.
    assert result["metadata"]["forget_status"] == "deleted"
    assert result["metadata"]["memory_id"] == "rec-7319"
    assert result["metadata"]["success"] is True


def test_chat_forget_local_confirmation_does_not_echo(monkeypatch):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    fake = _FakeForgetClient(cloud=False)
    monkeypatch.setattr(module, "memora_client", fake)
    result = asyncio.run(_dispatch_command("forget my test code"))

    assert fake.calls, "forget_fact was never called"
    _assert_no_echo(result["reply"])
    assert "local memory backend" in result["reply"]
    assert result["metadata"]["forget_status"] == "deleted"
    assert result["metadata"]["memory_id"] == "rec-7319"
    assert result["metadata"]["memory_cloud"] is False


def test_chat_forget_end_to_end_local_store_deletes_without_echo(tmp_path, monkeypatch):
    """Real MemoraClient (local store): the fact is actually deleted and
    the live-shaped confirmation still carries none of its content."""
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module
    from friday.memory.memora_client import MemoraClient

    client = MemoraClient(local_db_path=str(tmp_path / "no_echo.db"), remote_enabled=False)
    monkeypatch.setattr(module, "memora_client", client)
    try:
        client.record_fact("friday", FACT, "owner_fact", 0.9)
        result = asyncio.run(_dispatch_command("forget my test code"))
        assert result["metadata"]["forget_status"] == "deleted", result
        _assert_no_echo(result["reply"])
        assert result["metadata"]["memory_id"]
        hits = client.recall_memories("friday", "test code", limit=5)
        assert not any(MARKER in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


# ---------------------------------------------------------------------------
# Voice path (friday.memory.voice_memory.handle_voice_memory) — spoken aloud
# ---------------------------------------------------------------------------

def test_voice_forget_confirmation_does_not_echo(monkeypatch):
    from friday.memory.voice_memory import handle_voice_memory
    import friday.memory.memora_client as module

    fake = _FakeForgetClient(cloud=True)
    monkeypatch.setattr(module, "memora_client", fake)
    reply = handle_voice_memory("forget about the test code")

    assert fake.calls, "forget_fact was never called"
    assert reply is not None
    _assert_no_echo(reply)
    assert "forgotten" in reply.lower()
    assert "active memory" in reply


def test_voice_forget_end_to_end_local_store(tmp_path, monkeypatch):
    from friday.memory.voice_memory import handle_voice_memory
    import friday.memory.memora_client as module
    from friday.memory.memora_client import MemoraClient

    client = MemoraClient(local_db_path=str(tmp_path / "no_echo_voice.db"), remote_enabled=False)
    monkeypatch.setattr(module, "memora_client", client)
    try:
        client.record_fact("friday", FACT, "owner_fact", 0.9)
        reply = handle_voice_memory("forget about the test code")
        assert reply is not None
        _assert_no_echo(reply)
        assert "forgotten" in reply.lower()
        hits = client.recall_memories("friday", "test code", limit=5)
        assert not any(MARKER in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)
