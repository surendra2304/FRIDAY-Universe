"""Regression tests for the orpheus terms-failure fallback (TASK-VOICE-E2E-003).

Live root cause 2026-11-13: Groq orpheus TTS answers 400
'model_terms_required' on the fleet key (org admin has not accepted the
canopylabs model terms), so every voice call dispatched fine, the agent
state machine reached 'speaking', and ZERO audible frames reached the
owner. These tests pin the fallback contract:

- unprobed orpheus => _fallback_tts must NOT be orpheus
- probed-dead orpheus => EdgeTTS is used
- probed-alive orpheus => orpheus is used
- groq pipeline: orpheus dead => edge TTS in the parts tuple
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as worker  # noqa: E402
from friday.voice import edge_tts_adapter as edge_adapter  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_cache():
    """Every test starts from an unprobed cache and restores it after."""
    saved = dict(worker._ORPHEUS_CACHE)
    worker._ORPHEUS_CACHE["ok"] = None
    worker._ORPHEUS_CACHE["ts"] = 0.0
    yield
    worker._ORPHEUS_CACHE.clear()
    worker._ORPHEUS_CACHE.update(saved)


class _FakeOrpheusTTS:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeEdgeTTS:
    def __init__(self, voice="en-IN-NeerjaNeural"):
        self.voice = voice


def test_unprobed_orpheus_is_not_selected():
    """Unprobed (fresh job, probe failed to run) must never pick orpheus."""
    with mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", True), \
         mock.patch.object(worker, "_groq_key", return_value="gsk_test"), \
         mock.patch.object(worker, "_lk_groq") as fake_groq, \
         mock.patch.object(worker, "EDGE_TTS_AVAILABLE", True), \
         mock.patch.object(worker, "EdgeTTS", _FakeEdgeTTS):
        fake_groq.TTS = _FakeOrpheusTTS
        tts = worker._fallback_tts()
    assert not isinstance(tts, _FakeOrpheusTTS), "unprobed orpheus selected — silent dead air risk"
    assert isinstance(tts, _FakeEdgeTTS)


def test_dead_orpheus_falls_back_to_edge():
    """Probed and dead (400 terms) => EdgeTTS speaks."""
    with mock.patch.object(worker, "_ORPHEUS_CACHE", {"ok": False, "ts": 1e18}), \
         mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", True), \
         mock.patch.object(worker, "_groq_key", return_value="gsk_test"), \
         mock.patch.object(worker, "_lk_groq") as fake_groq, \
         mock.patch.object(worker, "EDGE_TTS_AVAILABLE", True), \
         mock.patch.object(worker, "EdgeTTS", _FakeEdgeTTS):
        fake_groq.TTS = _FakeOrpheusTTS
        tts = worker._fallback_tts()
    assert isinstance(tts, _FakeEdgeTTS)


def test_live_orpheus_is_preferred():
    """Probed and alive => orpheus (the better voice) is used."""
    with mock.patch.object(worker, "_ORPHEUS_CACHE", {"ok": True, "ts": 1e18}), \
         mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", True), \
         mock.patch.object(worker, "_groq_key", return_value="gsk_test"), \
         mock.patch.object(worker, "_lk_groq") as fake_groq, \
         mock.patch.object(worker, "EDGE_TTS_AVAILABLE", True), \
         mock.patch.object(worker, "EdgeTTS", _FakeEdgeTTS):
        fake_groq.TTS = _FakeOrpheusTTS
        tts = worker._fallback_tts()
    assert isinstance(tts, _FakeOrpheusTTS)


def test_no_providers_returns_none():
    """Both dead => None (the entrypoint then refuses the job honestly)."""
    with mock.patch.object(worker, "_ORPHEUS_CACHE", {"ok": False, "ts": 1e18}), \
         mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", False), \
         mock.patch.object(worker, "EDGE_TTS_AVAILABLE", False):
        assert worker._fallback_tts() is None


@pytest.mark.asyncio
async def test_probe_rejects_400_terms_response():
    """The probe treats a 400 'model_terms_required' body as dead."""
    class _Resp:
        status_code = 400
        text = '{"error":{"code":"model_terms_required"}}'

    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return _Resp()

    with mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", True), \
         mock.patch.object(worker, "_groq_key", return_value="gsk_test"), \
         mock.patch.object(worker.httpx, "AsyncClient", _Client):
        ok = await worker._probe_orpheus_tts()
    assert ok is False
    assert worker._ORPHEUS_CACHE["ok"] is False


@pytest.mark.asyncio
async def test_probe_accepts_200():
    """A 200 response marks orpheus alive and caches it."""
    class _Resp:
        status_code = 200
        text = ""

    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return _Resp()

    with mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", True), \
         mock.patch.object(worker, "_groq_key", return_value="gsk_test"), \
         mock.patch.object(worker.httpx, "AsyncClient", _Client):
        ok = await worker._probe_orpheus_tts()
    assert ok is True
    assert worker._ORPHEUS_CACHE["ok"] is True


def test_groq_pipeline_uses_edge_when_orpheus_dead():
    """The full groq pipeline path degrades to edge TTS, not a dead orpheus."""
    # _try_groq_pipeline is async; run it in a fresh event loop.
    import asyncio
    with mock.patch.object(worker, "_ORPHEUS_CACHE", {"ok": False, "ts": 1e18}), \
         mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", True), \
         mock.patch.object(worker, "_groq_key", return_value="gsk_test"), \
         mock.patch.object(worker, "_lk_groq") as fake_groq2, \
         mock.patch.object(worker, "EDGE_TTS_AVAILABLE", True), \
         mock.patch.object(worker, "EdgeTTS", _FakeEdgeTTS), \
         mock.patch.object(worker, "_llm_chat_model", return_value="openai/gpt-oss-120b"):
        fake_groq2.STT = lambda **kw: object()
        fake_groq2.LLM = lambda **kw: object()
        parts, reason = asyncio.run(worker._try_groq_pipeline())
    assert parts is not None
    stt, llm, tts = parts
    assert isinstance(tts, _FakeEdgeTTS), "pipeline would ship a dead orpheus TTS"
    assert reason is None


@pytest.mark.asyncio
async def test_edge_tts_refuses_empty_audio_and_decode_failure(monkeypatch):
    class _Emitter:
        def __init__(self):
            self.initialized = False
            self.pushed = False
            self.flushed = False

        def initialize(self, **kwargs):
            self.initialized = True

        def push(self, data):
            self.pushed = True

        def flush(self):
            self.flushed = True

    class _Communicate:
        chunks = []

        def __init__(self, text, voice):
            pass

        async def stream(self):
            for chunk in self.chunks:
                yield chunk

    monkeypatch.setattr(edge_adapter.edge_tts, "Communicate", _Communicate)
    stream = edge_adapter._EdgeChunkedStream(
        tts=object(), input_text="hello", conn_options=object(),
        voice="en-IN-NeerjaNeural",
    )
    emitter = _Emitter()

    with pytest.raises(RuntimeError, match="returned no audio"):
        await stream._run(emitter)
    assert not emitter.initialized
    assert not emitter.pushed
    assert not emitter.flushed

    _Communicate.chunks = [{"type": "audio", "data": b"fake-mp3"}]
    monkeypatch.setattr(edge_adapter, "_mp3_to_pcm", lambda data: None)
    with pytest.raises(RuntimeError, match="could not be decoded"):
        await stream._run(emitter)
    assert not emitter.initialized
    assert not emitter.pushed
    assert not emitter.flushed


@pytest.mark.asyncio
async def test_edge_tts_emits_pcm_after_threaded_conversion(monkeypatch):
    class _Communicate:
        def __init__(self, text, voice):
            pass

        async def stream(self):
            yield {"type": "audio", "data": b"fake-mp3"}

    class _Emitter:
        def __init__(self):
            self.initialized = False
            self.data = None
            self.flushed = False

        def initialize(self, **kwargs):
            self.initialized = True

        def push(self, data):
            self.data = data

        def flush(self):
            self.flushed = True

    monkeypatch.setattr(edge_adapter.edge_tts, "Communicate", _Communicate)
    monkeypatch.setattr(edge_adapter, "_mp3_to_pcm", lambda data: b"pcm-data")
    stream = edge_adapter._EdgeChunkedStream(
        tts=object(), input_text="hello", conn_options=object(),
        voice="en-IN-NeerjaNeural",
    )
    emitter = _Emitter()

    await stream._run(emitter)

    assert emitter.initialized
    assert emitter.data == b"pcm-data"
    assert emitter.flushed


def test_edge_voice_env_override():
    """FRIDAY_EDGE_TTS_VOICE is respected, default en-IN (owner locale)."""
    with mock.patch.dict(os.environ, {"FRIDAY_EDGE_TTS_VOICE": "en-US-AriaNeural"}, clear=False):
        assert worker._edge_voice() == "en-US-AriaNeural"
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FRIDAY_EDGE_TTS_VOICE", None)
        assert worker._edge_voice() == "en-IN-NeerjaNeural"
