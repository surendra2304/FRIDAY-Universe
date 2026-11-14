"""TASK-VOI-005 — Gemini key resolution must survive a bad probe window.

Owner live voice test #2, 2026-11-15 02:30 IST (FRIDAY-Voice journal,
job AJ_kEpwTnRbRaPn, room friday-7947e18b): the owner was served by the
Groq pipeline — Whisper STT + gpt-oss-120b + EdgeTTS — and described it
as "like Google voice search". Gemini was never attempted: the key
resolution round ended "no valid key among 3 candidates" without ONE
probe verdict ever being logged. The pre-fix round gave the first
candidate the whole shared deadline and BROKE on a timeout, so a single
slow/hung probe condemned the job; the same failure had already killed
the boot warm-up three hours earlier (23:43:49, "no valid key among 1
candidates"), and nothing ever re-resolved in the background.

These tests pin the rework:

- each candidate gets its own bounded budget; a timeout marks the
  candidate unjudged and the round CONTINUES;
- a transport failure is inconclusive (the key is unjudged), distinct
  from an auth rejection (the key is dead);
- if nothing verifies but something was unjudged, the first unjudged
  candidate comes back as a TENTATIVE key — never cached as verified,
  never negative-cached — so the Live session (and the TASK-VOI-004
  recovery ladder behind it) judges the key instead of the probe
  window judging the whole call;
- the candidate set is every pool key, healthy first — a key benched
  by the chat path's quota accounting is still a voice candidate;
- the background key keeper resolves while keyless and stands down
  while a verified key is fresh.
"""

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as worker  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_key_cache():
    saved = dict(worker._KEY_CACHE)
    worker._KEY_CACHE.update(
        {
            "key": None,
            "ts": 0.0,
            "failed_ts": 0.0,
            "tentative_key": None,
            "tentative_ts": 0.0,
        }
    )
    yield
    worker._KEY_CACHE.clear()
    worker._KEY_CACHE.update(saved)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# A slow probe can no longer kill the round (the 2026-11-15 defect)
# ---------------------------------------------------------------------------


def test_probe_timeout_moves_to_next_candidate(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["slow-key", "good-key"])
    monkeypatch.setattr(worker, "_KEY_PROBE_PER_CANDIDATE_S", 0.2)
    calls = []

    def fake_probe(key):
        calls.append(key)
        if key == "slow-key":
            time.sleep(2.0)  # outlives its per-candidate budget
        return True

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", fake_probe)
    assert _run(worker._gemini_best_key()) == "good-key"
    assert calls == ["slow-key", "good-key"]
    assert worker._cached_gemini_key() == "good-key"


def test_inconclusive_probe_moves_to_next_candidate(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["dark-key", "good-key"])
    calls = []

    def fake_probe(key):
        calls.append(key)
        if key == "dark-key":
            raise worker._ProbeInconclusive("connecterror: connection reset")
        return True

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", fake_probe)
    assert _run(worker._gemini_best_key()) == "good-key"
    assert calls == ["dark-key", "good-key"]
    # a verified key clears any tentative bookkeeping
    assert worker._cached_tentative_key() is None


# ---------------------------------------------------------------------------
# Tentative keys: unjudged is not dead, and not verified either
# ---------------------------------------------------------------------------


def test_all_inconclusive_returns_tentative_not_verified(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1", "k2"])
    calls = []

    def inconclusive(key):
        calls.append(key)
        raise worker._ProbeInconclusive("readtimeout")

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", inconclusive)
    assert _run(worker._gemini_best_key()) == "k1"
    # offered, but NOT as a verified key, and NOT negative-cached
    assert worker._cached_gemini_key() is None
    assert worker._cached_tentative_key() == "k1"
    assert worker._KEY_CACHE["failed_ts"] == 0.0
    # a second job inside the tentative window reuses it without probing
    calls.clear()
    assert _run(worker._gemini_best_key()) == "k1"
    assert calls == []


def test_all_auth_rejected_is_a_hard_failure(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1", "k2"])
    monkeypatch.setattr(worker, "_probe_gemini_key_sync", lambda k: False)
    assert _run(worker._gemini_best_key()) is None
    assert worker._cached_tentative_key() is None
    assert worker._KEY_CACHE["failed_ts"] != 0.0  # negative cache earned


def test_probe_classifies_transport_errors_as_inconclusive(monkeypatch):
    """The probe itself: a connection-class failure raises
    _ProbeInconclusive; an API-level error still counts as key-valid;
    an auth failure still counts as key-dead."""
    import google.genai as genai

    class _Boom:
        def __init__(self, exc):
            self._exc = exc

        @property
        def models(self):
            raise self._exc

    def client_raising(exc):
        return lambda api_key: _Boom(exc)

    monkeypatch.setattr(genai, "Client", client_raising(ConnectionError("connection reset by peer")))
    with pytest.raises(worker._ProbeInconclusive):
        worker._probe_gemini_key_sync("k")

    monkeypatch.setattr(
        genai, "Client", client_raising(RuntimeError("503 UNAVAILABLE: high demand"))
    )
    assert worker._probe_gemini_key_sync("k") is True

    monkeypatch.setattr(
        genai, "Client", client_raising(RuntimeError("API_KEY_INVALID"))
    )
    assert worker._probe_gemini_key_sync("k") is False


# ---------------------------------------------------------------------------
# Candidate set: every pool key, healthy first
# ---------------------------------------------------------------------------


def test_pool_keys_include_benched_keys_healthy_first(monkeypatch):
    try:
        import importlib

        # importlib, not `from friday.auth import credential_pool`: the
        # package __init__ re-exports the singleton under the same name,
        # shadowing the submodule.
        pool_mod = importlib.import_module("friday.auth.credential_pool")
    except Exception:
        pytest.skip("credential pool not importable in this environment")

    class _Cred:
        def __init__(self, key, healthy):
            self.api_key = key
            self._healthy = healthy

        def is_healthy(self, *args):
            return self._healthy

    fake_pool = SimpleNamespace(
        credentials=[
            _Cred("benched-1", False),
            _Cred("healthy-1", True),
            _Cred("benched-2", False),
        ]
    )
    monkeypatch.setattr(pool_mod, "credential_pool", fake_pool)
    assert worker._gemini_pool_keys() == ["healthy-1", "benched-1", "benched-2"]


# ---------------------------------------------------------------------------
# Fallback pipeline STT: no per-utterance language re-detection
# ---------------------------------------------------------------------------


def test_groq_pipeline_stt_is_pinned_to_english(monkeypatch):
    """2026-11-15: detect_language=True turned the owner's 'Hello' into
    Italian and his Telugu into Tamil script. The pipeline is
    English-out by design; its STT must be pinned to English."""
    captured = {}

    class _FakeSTT:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class _FakeLLM:
        def __init__(self, **kwargs):
            pass

    class _FakeEdgeTTS:
        def __init__(self, voice=None):
            self.voice = voice

    fake_groq = SimpleNamespace(STT=_FakeSTT, LLM=_FakeLLM, TTS=object)
    monkeypatch.setattr(worker, "GROQ_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_groq_key", lambda: "gsk_test")
    monkeypatch.setattr(worker, "_lk_groq", fake_groq)
    monkeypatch.setattr(worker, "_orpheus_ok", lambda: False)
    monkeypatch.setattr(worker, "EDGE_TTS_AVAILABLE", True)
    monkeypatch.setattr(worker, "EdgeTTS", _FakeEdgeTTS)

    parts, reason = _run(worker._try_groq_pipeline())
    assert parts is not None, reason
    assert captured.get("language") == "en"
    assert not captured.get("detect_language")


# ---------------------------------------------------------------------------
# The background key keeper
# ---------------------------------------------------------------------------


def test_keeper_step_resolves_when_keyless_then_stands_down(monkeypatch):
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1"])
    probes = []
    monkeypatch.setattr(worker, "_probe_gemini_key_sync", lambda k: probes.append(k) or True)
    assert worker._key_keeper_step() == "resolved"
    assert worker._cached_gemini_key() == "k1"
    assert worker._key_keeper_step() == "fresh"
    assert probes == ["k1"]  # the second step probed nothing


def test_keeper_step_reports_cooling_and_tentative(monkeypatch):
    worker._KEY_CACHE.update({"failed_ts": time.time()})
    assert worker._key_keeper_step() == "cooling"

    worker._KEY_CACHE.update({"failed_ts": 0.0})
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1"])

    def inconclusive(key):
        raise worker._ProbeInconclusive("connecterror")

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", inconclusive)
    assert worker._key_keeper_step() == "tentative"
    assert worker._cached_gemini_key() is None
