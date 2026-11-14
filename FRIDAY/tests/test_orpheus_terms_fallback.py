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

import logging
import os
import sys
import time
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


def test_voice_model_honors_explicit_live_model_override(monkeypatch):
    monkeypatch.setenv("FRIDAY_VOICE_LIVE_MODEL", "gemini-3.8-live")
    assert worker._voice_model() == "gemini-3.8-live"


def test_gemini_key_probe_uses_current_flash_model():
    with mock.patch("google.genai.Client") as client_class:
        worker._probe_gemini_key_sync("test-gemini-key")
    client_class.assert_called_once_with(api_key="test-gemini-key")
    client_class.return_value.models.generate_content.assert_called_once_with(
        model="gemini-3.8-flash",
        contents="ping",
    )


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
@pytest.mark.parametrize("verdict", [True, False])
async def test_probe_uses_fresh_cache_without_http(verdict):
    """A fresh cached verdict is returned with NO live Groq call.

    Regression (2026-11-14): the probe made a live HTTP call (15 s
    timeout) on every job's critical path even though consumers only
    trust a 5-minute cache — pure added dead air before the greeting.
    """
    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise AssertionError("probe must not call Groq with a fresh cache")

    with mock.patch.object(worker, "_ORPHEUS_CACHE", {"ok": verdict, "ts": time.time()}), \
         mock.patch.object(worker, "GROQ_PLUGIN_AVAILABLE", True), \
         mock.patch.object(worker, "_groq_key", return_value="gsk_test"), \
         mock.patch.object(worker.httpx, "AsyncClient", _Client):
        ok = await worker._probe_orpheus_tts()
    assert ok is verdict


def test_loop_block_reports_are_filtered():
    """'event loop blocked' reports are dropped at the real 1.8.x logger.

    Regression (2026-11-14): livekit-agents 1.8.x emits every framework
    record through the single 'livekit.agents' logger, so the worker's
    setLevel on 'livekit.agents.telemetry.loop_monitor' never matched and
    the multi-KB stall reports kept blocking the audio loop (1,400 ms in
    the production journal) with their own formatting.
    """
    filters = [
        f for f in logging.getLogger("livekit.agents").filters
        if isinstance(f, worker._LoopBlockReportFilter)
    ]
    assert filters, "loop-block filter not installed on the livekit.agents logger"
    flt = filters[0]

    def _record(level, msg):
        return logging.LogRecord(
            "livekit.agents", level, __file__, 1, msg, (), None,
        )

    assert flt.filter(_record(
        logging.WARNING, "event loop blocked for 250ms at \"/x.py\", line 1",
    )) is False
    assert flt.filter(_record(logging.ERROR, "session error: boom")) is True
    assert flt.filter(_record(logging.WARNING, "worker registered")) is True


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


@pytest.mark.asyncio
async def test_edge_tts_pushes_first_audio_before_stream_ends(monkeypatch):
    """Progressive decode: PCM is pushed while mp3 is still arriving.

    Regression (2026-11-14): the adapter buffered the whole mp3 and ran
    one whole-buffer transcode before pushing anything, so the first
    audible frame waited for the full synthesis download + transcode.
    PCM here is a prefix-consistent function of the mp3 length, exactly
    the property real mp3 frame decoding has.
    """
    events: list = []

    class _Communicate:
        def __init__(self, text, voice):
            pass

        async def stream(self):
            for i in range(3):
                events.append(("chunk", i))
                yield {"type": "audio", "data": b"m" * 9000}

    class _Emitter:
        def __init__(self):
            self.initialized = False
            self.pushes: list[int] = []
            self.flushed = False

        def initialize(self, **kwargs):
            self.initialized = True

        def push(self, data):
            events.append(("push", len(data)))
            self.pushes.append(len(data))

        def flush(self):
            self.flushed = True

    def _fake_pcm(data: bytes) -> bytes:
        return b"P" * (len(data) // 9000 * 4800)

    monkeypatch.setattr(edge_adapter.edge_tts, "Communicate", _Communicate)
    monkeypatch.setattr(edge_adapter, "_mp3_prefix_to_pcm", _fake_pcm)
    monkeypatch.setattr(edge_adapter, "_mp3_to_pcm", _fake_pcm)
    stream = edge_adapter._EdgeChunkedStream(
        tts=object(), input_text="hello", conn_options=object(),
        voice="en-IN-NeerjaNeural",
    )
    emitter = _Emitter()

    await stream._run(emitter)

    assert emitter.initialized
    assert emitter.flushed
    assert len(emitter.pushes) >= 2, "audio must arrive in more than one push"
    assert sum(emitter.pushes) == 14400
    first_push = next(i for i, e in enumerate(events) if e[0] == "push")
    last_chunk = max(i for i, e in enumerate(events) if e[0] == "chunk")
    assert first_push < last_chunk, "first audio must be pushed before the mp3 stream ends"


def test_edge_voice_env_override():
    """FRIDAY_EDGE_TTS_VOICE is respected, default en-IN (owner locale)."""
    with mock.patch.dict(os.environ, {"FRIDAY_EDGE_TTS_VOICE": "en-US-AriaNeural"}, clear=False):
        assert worker._edge_voice() == "en-US-AriaNeural"
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FRIDAY_EDGE_TTS_VOICE", None)
        assert worker._edge_voice() == "en-IN-NeerjaNeural"
