"""TASK-VOI-003 — voice session pinning, key cache, watchdog, brain budget.

The 2026-11-14 machine-run Gemini Live call wedged on its first
function-calling turn while a second job in the same worker process
re-ran the full serial key-probe chain. These tests pin the fixes:

- the verified Gemini key is resolved once per process (cached,
  single-flight, concurrent probes under one deadline, negative cache);
- _try_gemini_realtime never runs a private serial probe round and
  reports the key it used, so the entrypoint can pin it for the job;
- the stuck-turn watchdog decision is a pure function of turn state;
- a rebuilt session's instructions carry the conversation context and
  a do-not-greet-again instruction;
- the voice brain bridge gives a slow brain 60 s, not 230 s, so a
  function-calling turn completes (possibly as "unconfirmed") instead
  of wedging the call.
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as worker  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_key_cache():
    saved = dict(worker._KEY_CACHE)
    worker._KEY_CACHE.update({"key": None, "ts": 0.0, "failed_ts": 0.0})
    yield
    worker._KEY_CACHE.clear()
    worker._KEY_CACHE.update(saved)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Verified-key cache + single-flight resolution
# ---------------------------------------------------------------------------


def test_cached_key_is_returned_without_probing(monkeypatch):
    worker._KEY_CACHE.update({"key": "cached-key", "ts": time.time(), "failed_ts": 0.0})
    probes = []
    monkeypatch.setattr(
        worker, "_probe_gemini_key_sync", lambda k: probes.append(k) or True
    )
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    assert _run(worker._gemini_best_key()) == "cached-key"
    assert probes == []


def test_resolution_probes_and_caches_first_valid_key(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["dead-key", "good-key"])
    calls = []

    def fake_probe(key):
        calls.append(key)
        return key == "good-key"

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", fake_probe)
    assert _run(worker._gemini_best_key()) == "good-key"
    assert set(calls) == {"dead-key", "good-key"}  # both candidates probed
    # second call is served from the cache: no new probes
    calls.clear()
    assert _run(worker._gemini_best_key()) == "good-key"
    assert calls == []


def test_resolution_stops_at_first_valid_key(monkeypatch):
    """Sequential probing (TASK-VOI-003 follow-up): once a candidate
    verifies, later candidates are never probed — the concurrent round
    this replaced starved all three probes on the saturated voice host
    (live evidence 2026-11-14 21:42/21:45 IST)."""
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["good-key", "untouched-key"])
    calls = []
    monkeypatch.setattr(
        worker, "_probe_gemini_key_sync", lambda k: calls.append(k) or True
    )
    assert _run(worker._gemini_best_key()) == "good-key"
    assert calls == ["good-key"]


def test_failed_resolution_is_negatively_cached(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1", "k2"])
    calls = []
    monkeypatch.setattr(
        worker, "_probe_gemini_key_sync", lambda k: calls.append(k) or False
    )
    assert _run(worker._gemini_best_key()) is None
    first_round = len(calls)
    assert first_round == 2
    # a burst of concurrent jobs must not multiply the probe load
    assert _run(worker._gemini_best_key()) is None
    assert len(calls) == first_round


def test_expired_negative_cache_allows_reprobe(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1"])
    worker._KEY_CACHE.update(
        {"key": None, "ts": 0.0, "failed_ts": time.time() - worker._KEY_NEGATIVE_TTL_S - 1}
    )
    monkeypatch.setattr(worker, "_probe_gemini_key_sync", lambda k: True)
    assert _run(worker._gemini_best_key()) == "k1"


def test_concurrent_resolution_is_single_flight(monkeypatch):
    """Two jobs resolving at the same time share ONE probe round."""
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["only-key"])
    calls = []

    def slow_probe(key):
        calls.append(key)
        time.sleep(0.3)
        return True

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", slow_probe)

    async def both():
        return await asyncio.gather(worker._gemini_best_key(), worker._gemini_best_key())

    first, second = _run(both())
    assert first == second == "only-key"
    assert calls == ["only-key"]  # exactly one probe happened


# ---------------------------------------------------------------------------
# _try_gemini_realtime: no private probe round; reports the pinned key
# ---------------------------------------------------------------------------


def test_try_gemini_realtime_uses_given_key_and_reports_it(monkeypatch):
    sentinel_model = object()
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_build_realtime_model", lambda k, i: sentinel_model)
    model, key = _run(worker._try_gemini_realtime("instr", verified_key="pinned-key"))
    assert model is sentinel_model
    assert key == "pinned-key"


def test_try_gemini_realtime_without_key_relies_on_cached_resolution(monkeypatch):
    """verified_key=None must go through the shared (cached) resolution —
    never a private serial probe round of its own."""
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_build_realtime_model", lambda k, i: object())
    worker._KEY_CACHE.update({"key": "warm-key", "ts": time.time(), "failed_ts": 0.0})
    probes = []
    monkeypatch.setattr(
        worker, "_probe_gemini_key_sync", lambda k: probes.append(k) or True
    )
    model, key = _run(worker._try_gemini_realtime("instr", verified_key=None))
    assert model is not None
    assert key == "warm-key"
    assert probes == []


def test_try_gemini_realtime_returns_none_pair_when_no_key(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)

    async def no_key():
        return None

    monkeypatch.setattr(worker, "_gemini_best_key", no_key)
    assert _run(worker._try_gemini_realtime("instr", verified_key=None)) == (None, None)


# ---------------------------------------------------------------------------
# Watchdog decision + context carry-over
# ---------------------------------------------------------------------------


def test_turn_wedged_only_when_stuck_thinking_or_speaking():
    now = 1000.0
    base = {"pending_since": now - 90.0, "state": "thinking"}
    assert worker._turn_wedged(base, now) is True
    assert worker._turn_wedged({**base, "state": "speaking"}, now) is True
    # responsive again -> not wedged, whatever the clock says
    assert worker._turn_wedged({**base, "state": "listening"}, now) is False
    # no pending turn -> never wedged
    assert worker._turn_wedged({"pending_since": None, "state": "thinking"}, now) is False
    # a slow-but-legitimate turn inside the threshold -> not wedged
    assert worker._turn_wedged({"pending_since": now - 30.0, "state": "thinking"}, now) is False


def test_context_block_carries_transcript_and_forbids_greeting():
    transcript = [
        ("user", "What time is it in London?"),
        ("assistant", "It is currently 3:05 PM in London, Boss."),
        ("user", "Remember that my favourite colour is teal."),
    ]
    block = worker._context_block(transcript)
    assert "do NOT greet again" in block
    assert "user: What time is it in London?" in block
    assert "assistant: It is currently 3:05 PM in London, Boss." in block
    assert "teal" in block
    assert worker._context_block([]) == ""


def test_context_block_limits_to_recent_items():
    transcript = [("user", f"line {i}") for i in range(30)]
    block = worker._context_block(transcript, limit=5)
    assert "line 29" in block
    assert "line 24" not in block


# ---------------------------------------------------------------------------
# Brain bridge budget
# ---------------------------------------------------------------------------


def test_brain_bridge_timeout_is_voice_sized():
    from friday.voice import brain_bridge

    assert brain_bridge.BRAIN_TIMEOUT_S == 60.0


def test_brain_bridge_passes_the_budget_to_the_http_call():
    import httpx
    from friday.voice.brain_bridge import VoiceBrainBridge

    seen = {}

    class _Resp:
        status_code = 200

        async def aiter_bytes(self):
            yield b'{"reply": "Done, Boss.", "metadata": {}}'

    class _StreamCtx:
        async def __aenter__(self):
            return _Resp()

        async def __aexit__(self, *exc):
            return False

    class _Client:
        def stream(self, method, url, json=None, headers=None, timeout=None):
            seen["timeout"] = timeout
            return _StreamCtx()

    bridge = VoiceBrainBridge(client=_Client())
    result = _run(bridge.execute("Remember that my favourite colour is teal."))
    assert result["state"] == "answered"
    assert seen["timeout"] == 60.0
    # httpx import kept for parity with the module's own dependency
    assert httpx.TimeoutException is not None
