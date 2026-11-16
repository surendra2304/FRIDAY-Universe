"""TASK-VOI-010: the greeting must not wait for memory recall.

Pins the decoupled greeting path's contract:

- ``_memory_block_now``: a landed recall is used exactly as before; a
  pending one reports pending (the caller starts the session without
  it and arranges async delivery) instead of blocking; a failed one
  degrades to no block — never an exception into the greeting path.
- ``_inject_memory_block``: late memory reaches the live session
  through whatever surface this livekit-agents generation offers
  (``agent.update_instructions`` first, chat-context append second);
  a missing or refusing surface degrades to None — never an exception,
  never a disrupted call.
- The key keeper refreshes the verified-key cache BEFORE it expires
  (TASK-VOI-010 wired ``_verified_key_remaining_s`` into the keeper
  step), and a failed or inconclusive refresh never poisons the
  still-valid cache it was protecting.
- The entrypoint source no longer gathers the recall task into the
  greeting path (a refactor must not silently re-serialise it).
"""
import asyncio
import inspect
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


@pytest.fixture(autouse=True)
def _preserve_key_cache():
    saved = dict(w._KEY_CACHE)
    yield
    w._KEY_CACHE.clear()
    w._KEY_CACHE.update(saved)


# ---------- _memory_block_now ----------

async def _value(v):
    return v


async def _boom():
    raise RuntimeError("recall exploded")


def test_memory_block_now_returns_landed_block():
    async def main():
        task = asyncio.ensure_future(_value("the block"))
        await task
        return w._memory_block_now(task)

    block, pending = asyncio.run(main())
    assert (block, pending) == ("the block", False)


def test_memory_block_now_pending_task_does_not_block():
    async def main():
        gate = asyncio.Event()

        async def slow():
            await gate.wait()
            return "late block"

        task = asyncio.ensure_future(slow())
        await asyncio.sleep(0)  # let it start, not finish
        result = w._memory_block_now(task)
        gate.set()
        await task
        return result

    block, pending = asyncio.run(main())
    assert (block, pending) == ("", True)


def test_memory_block_now_failed_task_degrades_to_empty():
    async def main():
        task = asyncio.ensure_future(_boom())
        try:
            await task
        except RuntimeError:
            pass
        return w._memory_block_now(task)

    block, pending = asyncio.run(main())
    assert (block, pending) == ("", False)


def test_memory_block_now_none_task():
    assert w._memory_block_now(None) == ("", False)


# ---------- _inject_memory_block ----------

class _FakeCtx:
    def __init__(self):
        self.messages = []

    def add_message(self, role=None, content=None):
        self.messages.append((role, content))


class _FakeAgentWithUpdate:
    def __init__(self):
        self.updated = []
        self.chat_ctx = _FakeCtx()

    async def update_instructions(self, instructions):
        self.updated.append(instructions)


class _FakeAgentCtxOnly:
    def __init__(self):
        self.chat_ctx = _FakeCtx()


class _Bare:
    pass


def test_inject_prefers_update_instructions():
    agent = _FakeAgentWithUpdate()
    mechanism = asyncio.run(
        w._inject_memory_block(object(), agent, "BLOCK", "FULL INSTRUCTIONS")
    )
    assert mechanism == "agent.update_instructions"
    assert agent.updated == ["FULL INSTRUCTIONS"]
    assert agent.chat_ctx.messages == []  # first surface wins; no double injection


def test_inject_falls_back_to_chat_ctx():
    agent = _FakeAgentCtxOnly()
    mechanism = asyncio.run(w._inject_memory_block(object(), agent, "BLOCK", "FULL"))
    assert mechanism == "chat_ctx.add_message"
    assert agent.chat_ctx.messages == [("system", ["BLOCK"])]


def test_inject_no_surface_returns_none():
    assert asyncio.run(w._inject_memory_block(object(), _Bare(), "BLOCK", "FULL")) is None


def test_inject_empty_block_is_noop():
    agent = _FakeAgentWithUpdate()
    assert asyncio.run(w._inject_memory_block(object(), agent, "", "FULL")) is None
    assert agent.updated == []


def test_inject_refusing_surface_falls_through():
    class _Refusing:
        def __init__(self):
            self.chat_ctx = _FakeCtx()

        def update_instructions(self, instructions):
            raise RuntimeError("session closed")

    agent = _Refusing()
    mechanism = asyncio.run(w._inject_memory_block(object(), agent, "BLOCK", "FULL"))
    assert mechanism == "chat_ctx.add_message"
    assert agent.chat_ctx.messages == [("system", ["BLOCK"])]


def test_injection_mechanisms_order():
    agent = _FakeAgentWithUpdate()
    names = [name for name, _apply in w._injection_mechanisms(object(), agent)]
    assert names == ["agent.update_instructions", "chat_ctx.add_message"]
    assert w._injection_mechanisms(object(), _Bare()) == []


# ---------- keeper pre-expiry refresh (TASK-VOI-010) ----------

def _clear_cache():
    w._KEY_CACHE.update(
        {
            "key": None,
            "ts": 0.0,
            "failed_ts": 0.0,
            "tentative_key": None,
            "tentative_ts": 0.0,
        }
    )


def _stub_probe(monkeypatch, verdict):
    """verdict(key) -> True (verified), False (auth-rejected) or
    "unjudged" (raises _ProbeInconclusive, like a timeout/reset)."""
    probed = []
    monkeypatch.setattr(w, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(w, "_gemini_pool_keys", lambda: ["k1", "k2"])

    def fake_probe(key):
        probed.append(key)
        v = verdict(key)
        if v == "unjudged":
            raise w._ProbeInconclusive("readtimeout")
        return v

    monkeypatch.setattr(w, "_probe_gemini_key_sync", fake_probe)
    return probed


def test_keeper_stands_down_when_cache_comfortably_fresh(monkeypatch):
    _clear_cache()
    w._KEY_CACHE.update({"key": "k1", "ts": time.time()})
    probed = _stub_probe(monkeypatch, lambda key: True)
    assert w._key_keeper_step() == "fresh"
    assert probed == []  # no refresh round while the TTL is comfortable


def test_keeper_refreshes_before_expiry(monkeypatch):
    _clear_cache()
    # 200 s into the 240 s TTL: ~40 s remain — inside the refresh window.
    w._KEY_CACHE.update({"key": "k1", "ts": time.time() - 200.0})
    probed = _stub_probe(monkeypatch, lambda key: True)
    assert w._key_keeper_step() == "refreshed"
    assert probed == ["k1"]  # a real probe round ran despite the valid cache
    assert w._KEY_CACHE["key"] == "k1"
    assert w._verified_key_remaining_s() > 200.0  # TTL renewed


def test_failed_refresh_keeps_still_valid_key_and_cache(monkeypatch):
    _clear_cache()
    old_ts = time.time() - 200.0
    w._KEY_CACHE.update({"key": "k1", "ts": old_ts})
    _stub_probe(monkeypatch, lambda key: False)  # every candidate rejected
    assert w._key_keeper_step() == "refreshed"
    # The still-valid key survives; no negative cache, no tentative stamp.
    assert w._KEY_CACHE["key"] == "k1"
    assert w._KEY_CACHE["ts"] == old_ts
    assert w._KEY_CACHE["failed_ts"] == 0.0
    assert w._KEY_CACHE["tentative_key"] is None


def test_unjudged_refresh_keeps_verified_key(monkeypatch):
    _clear_cache()
    old_ts = time.time() - 200.0
    w._KEY_CACHE.update({"key": "k1", "ts": old_ts})
    _stub_probe(monkeypatch, lambda key: "unjudged")  # probes cannot judge
    assert w._key_keeper_step() == "refreshed"
    assert w._KEY_CACHE["key"] == "k1"
    assert w._KEY_CACHE["ts"] == old_ts
    assert w._KEY_CACHE["tentative_key"] is None


# ---------- the decoupling itself ----------

def test_entrypoint_no_longer_gathers_recall_into_the_greeting_path():
    src = inspect.getsource(w.entrypoint)
    assert "asyncio.gather(_memory_task, _key_task)" not in src
    assert "_memory_block_now(_memory_task)" in src
    assert "_deliver_memory_when_ready" in src
