"""TASK-VOI-009 — Gemini Live is the ONLY voice AI; the Groq pipeline is gone.

Owner directive 2026-11-15: "Gemini is the only AI for voice and remove
groq." The worker's provider path 2 (Whisper STT -> Groq LLM -> EdgeTTS,
or Groq Orpheus TTS when its terms probe passed) is deleted, the
TASK-VOI-004 ladder's Groq failover rung is deleted, and every fixed
line is a pre-recorded WAV shipped under voice/audio/.

This file replaces FRIDAY/tests/test_orpheus_terms_fallback.py, whose
subject (the Orpheus/EdgeTTS fallback machinery) no longer exists:

- CARRIED VERBATIM (unrelated to the fallback; same names, same
  bodies): test_voice_model_honors_explicit_live_model_override,
  test_gemini_key_probe_uses_current_flash_model,
  test_loop_block_reports_are_filtered.
- CONVERTED to the Gemini-only contract (below): the Orpheus selection
  tests, the probe tests, the pipeline-degradation test and the
  EdgeTTS-adapter tests. Their subjects are deleted code, so the
  assertions now pin the stronger fact — the machinery is ABSENT, the
  adapter module is gone, and the fixed lines are recordings with a
  working playback path and an honest unavailable path.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as worker  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Carried verbatim from test_orpheus_terms_fallback.py (unrelated pins)
# ---------------------------------------------------------------------------


def test_voice_model_honors_explicit_live_model_override(monkeypatch):
    monkeypatch.setenv("FRIDAY_VOICE_LIVE_MODEL", "gemini-3.8-live")
    assert worker._voice_model() == "gemini-3.8-live"


def test_gemini_key_probe_uses_current_flash_model():
    """TASK-VOI-020 + TASK-VOI-021: the probe's stage-1 ping runs on
    the Flash-Lite model (gemini-3.5-flash-lite, the current
    Flash-Lite id — free tier 15 RPM / 500 RPD), NOT the current
    voice Flash model — stage 1 only classifies the key, and its
    pings must not drain the Flash model's ~20/day free-tier bucket.
    (The pin previously asserted gemini-3.8-flash; that target is
    the defect that condemned every key at re-acceptance #12. The
    legacy gemini-2.5-flash-lite alias is not pinned: it routes to
    gemini-3.5-flash-lite from 2026-12-01.)"""
    with mock.patch("google.genai.Client") as client_class:
        worker._probe_gemini_key_sync("test-gemini-key")
    client_class.assert_called_once_with(api_key="test-gemini-key")
    client_class.return_value.models.generate_content.assert_called_once_with(
        model="gemini-3.5-flash-lite",
        contents="ping",
    )


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


# ---------------------------------------------------------------------------
# The removed machinery stays removed
# ---------------------------------------------------------------------------

_REMOVED_SURFACE = (
    "_try_groq_pipeline", "_groq_key", "_llm_chat_model", "_fallback_tts",
    "_probe_orpheus_tts", "_orpheus_ok", "_edge_voice", "_ORPHEUS_CACHE",
    "GROQ_PLUGIN_AVAILABLE", "EDGE_TTS_AVAILABLE", "_lk_groq", "EdgeTTS",
)


def test_worker_exposes_no_removed_provider_surface():
    for name in _REMOVED_SURFACE:
        assert not hasattr(worker, name), f"worker still exposes {name}"


def test_worker_source_has_no_removed_serving_references():
    """Code-shaped references to the deleted providers must not exist
    in the worker source. (Prose mentions inside comments/docstrings
    that are explicitly marked as removed history are fine and are not
    matched by these code-shaped tokens.)"""
    source = Path(worker.__file__).read_text(encoding="utf-8")
    for token in (
        "livekit.plugins import groq",
        "_lk_groq",
        "whisper-large",
        "orpheus-v1-english",
        "api.groq.com",
        "edge_tts_adapter",
        "import edge_tts",
        "gpt-oss",
        "no-provider",
    ):
        assert token not in source, f"worker source still references {token!r}"


def test_edge_tts_adapter_module_is_deleted():
    adapter = (
        Path(__file__).resolve().parents[1]
        / "src" / "friday" / "voice" / "edge_tts_adapter.py"
    )
    assert not adapter.exists()


def test_instructions_have_no_english_out_variant():
    """The english_out instruction variant existed only for the Groq
    pipeline's English-only TTS; Gemini Live mirrors the caller's
    language natively, so the variant must not come back."""
    with pytest.raises(TypeError):
        worker._instructions(english_out=True)  # the TypeError IS the test
    assert "mirroring a mix" in worker._instructions()


# ---------------------------------------------------------------------------
# Fixed lines: shipped recordings, valid and audible
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(worker._FIXED_LINES))
def test_fixed_line_wavs_are_valid_playable_pcm(name):
    path = worker._fixed_line_path(name)
    assert path.exists(), f"missing shipped fixed line {path}"
    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 24000
        frames = wav.getnframes()
        raw = wav.readframes(frames)
    duration = frames / 24000.0
    assert 2.0 <= duration <= 20.0, f"{name} duration {duration:.2f}s out of bounds"
    # not silence: peak amplitude must be a real voice level
    import struct

    samples = struct.unpack(f"<{len(raw) // 2}h", raw)
    assert max(abs(s) for s in samples) > 1000


def test_read_fixed_line_roundtrip():
    raw, rate, duration = worker._read_fixed_line("voice_unavailable")
    assert rate == 24000
    assert len(raw) == pytest.approx(int(duration * rate) * 2, abs=4)
    assert duration > 3.0  # the notice is a full sentence, not a beep


def test_read_fixed_line_missing_raises():
    with pytest.raises(Exception):
        worker._read_fixed_line("no_such_line")


def test_preload_fixed_lines_runs_clean():
    worker._preload_fixed_lines()  # must not raise on the shipped set


# ---------------------------------------------------------------------------
# Fixed-line playback + the unavailable notice path
# ---------------------------------------------------------------------------


class _FakeAudioSource:
    def __init__(self, rate, channels):
        self.rate = rate
        self.frames = []

    def capture_frame(self, frame):
        self.frames.append(frame)
        return None

    async def aclose(self):
        pass


class _FakeTrack:
    sid = "TR_fake"

    @staticmethod
    def create_audio_track(name, source):
        track = _FakeTrack()
        track.name = name
        track.source = source
        return track


class _FakeParticipant:
    def __init__(self):
        self.published = []
        self.unpublished = []

    async def publish_track(self, track, options):
        self.published.append((track, options))
        return SimpleNamespace(sid=track.sid)

    async def unpublish_track(self, sid):
        self.unpublished.append(sid)


def _fake_rtc():
    return SimpleNamespace(
        AudioSource=_FakeAudioSource,
        LocalAudioTrack=_FakeTrack,
        TrackPublishOptions=lambda **kw: SimpleNamespace(**kw),
        TrackSource=SimpleNamespace(SOURCE_MICROPHONE="microphone"),
        AudioFrame=lambda **kw: SimpleNamespace(**kw),
    )


def test_play_fixed_line_publishes_the_recording(monkeypatch):
    monkeypatch.setattr(worker, "_rtc", _fake_rtc())
    participant = _FakeParticipant()
    room = SimpleNamespace(local_participant=participant)
    assert _run(worker._play_fixed_line(room, "greeting")) is True
    assert len(participant.published) == 1
    track, _options = participant.published[0]
    # the whole greeting was queued in 20 ms frames, then unpublished
    total = sum(f.samples_per_channel for f in track.source.frames)
    _raw, _rate, duration = worker._read_fixed_line("greeting")
    assert total == pytest.approx(int(duration * 24000), abs=480)
    assert participant.unpublished == ["TR_fake"]


def test_play_fixed_line_missing_file_fails_honestly(monkeypatch, tmp_path):
    monkeypatch.setattr(worker, "_rtc", _fake_rtc())
    monkeypatch.setattr(worker, "_FIXED_LINE_DIR", tmp_path)
    room = SimpleNamespace(local_participant=_FakeParticipant())
    assert _run(worker._play_fixed_line(room, "greeting")) is False


def test_announce_unavailable_plays_the_notice(monkeypatch):
    played = []

    async def _fake_play(room, name):
        played.append(name)
        return True

    monkeypatch.setattr(worker, "_play_fixed_line", _fake_play)
    room = SimpleNamespace(remote_participants={"owner": object()})
    _run(worker._announce_unavailable(room))
    assert played == ["voice_unavailable"]


def test_announce_unavailable_without_participant_does_not_hang(monkeypatch):
    played = []

    async def _fake_play(room, name):
        played.append(name)
        return True

    monkeypatch.setattr(worker, "_play_fixed_line", _fake_play)

    class _JumpClock:
        def __init__(self):
            self.calls = 0

        def time(self):
            self.calls += 1
            return 0.0 if self.calls <= 1 else 1e12

    monkeypatch.setattr(worker, "time", _JumpClock())
    room = SimpleNamespace(remote_participants={})
    _run(worker._announce_unavailable(room))
    assert played == []  # nobody to hear it; logged instead of hanging
