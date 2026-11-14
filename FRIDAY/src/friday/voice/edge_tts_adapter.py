"""edge_tts_adapter.py — a LiveKit TTS provider backed by keyless Edge TTS.

The Groq orpheus TTS is broken on the fleet key ('model_terms_required' —
the org admin has not accepted the canopylabs model terms), so the worker's
fixed-line greeting and every groq-pipeline reply dies with a 400 and the
owner hears silence. edge-tts reaches the service from both the sandbox and
Server 1 (28,800-byte probe), needs no key, and speaks en-IN natively (the
owner's locale). This adapter plugs it into AgentSession.tts.

Self-test: python edge_tts_adapter.py
"""
import asyncio
import os
import subprocess
import tempfile
import time

from livekit.agents.tts import ChunkedStream, TTS, TTSCapabilities

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

_SAMPLE_RATE = 24000
_NUM_CHANNELS = 1

# Progressive decode (voice-latency fix, 2026-11-14): the adapter used to
# buffer the ENTIRE mp3, transcode it in one ffmpeg run, and only then push
# audio — time-to-first-audio was the full synthesis download plus the full
# transcode, and playout arrived in one burst per sentence. MP3 frames
# decode independently of later bytes, so once enough new mp3 has arrived
# we decode the accumulated prefix and push only the PCM that is new. The
# final decode (strict, whole-buffer) still settles the tail and preserves
# the historical failure contract: undecodable audio raises before the
# emitter is touched when nothing was ever pushed.
_PREFIX_MIN_NEW_BYTES = 8192
_PREFIX_MIN_INTERVAL_S = 0.35


def _ffmpeg_exe() -> str | None:
    """ffmpeg resolution order: PATH, then the static-ffmpeg wheel bundled
    binary (Server 1 has no system ffmpeg; static_ffmpeg ships one and is
    a worker-venv dependency since TASK-VOICE-E2E-003)."""
    import shutil

    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            from static_ffmpeg import add_paths

            add_paths()
            exe = shutil.which("ffmpeg")
        except Exception:
            exe = None
    return exe


def _mp3_to_pcm(data: bytes) -> bytes | None:
    """mp3 bytes -> s16le PCM via ffmpeg (strict: clean exit + output)."""
    exe = _ffmpeg_exe()
    if exe is None:
        return None

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        tf.write(data)
        path = tf.name
    try:
        out = subprocess.run(
            [exe, "-i", path, "-f", "s16le", "-ac", "1",
             "-ar", str(_SAMPLE_RATE), "-"],
            capture_output=True, timeout=30,
        )
        return out.stdout if out.returncode == 0 and out.stdout else None
    finally:
        os.unlink(path)


def _mp3_prefix_to_pcm(data: bytes) -> bytes | None:
    """Decode a possibly TRUNCATED mp3 prefix, tolerantly.

    ffmpeg may exit non-zero on a stream cut mid-frame while still having
    produced valid PCM for every complete frame; for a prefix that output
    is exactly what progressive playout needs, so any non-empty stdout
    counts. Returns None when ffmpeg is missing or produced nothing —
    the caller then simply waits for more bytes (the strict final decode
    remains the authority on undecodable audio).
    """
    exe = _ffmpeg_exe()
    if exe is None:
        return None

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        tf.write(data)
        path = tf.name
    try:
        out = subprocess.run(
            [exe, "-i", path, "-f", "s16le", "-ac", "1",
             "-ar", str(_SAMPLE_RATE), "-"],
            capture_output=True, timeout=30,
        )
        return out.stdout if out.stdout else None
    finally:
        os.unlink(path)


class _EdgeChunkedStream(ChunkedStream):
    def __init__(self, *, tts, input_text, conn_options, voice):
        super().__init__(tts=tts, input_text=input_text,
                         conn_options=conn_options)
        self._voice = voice

    async def _run(self, output_emitter) -> None:
        communicate = edge_tts.Communicate(self.input_text, self._voice)
        mp3 = bytearray()
        pushed_pcm = 0
        initialized = False
        last_decode_at = 0.0
        last_decode_len = 0

        def _emit_new(pcm: bytes) -> None:
            """Push only the PCM beyond what earlier decodes already sent.

            Prefix property: decoding a longer mp3 prefix yields the
            earlier PCM as a strict prefix (frames never depend on later
            bytes), so the delta is exactly the newly audible audio.
            """
            nonlocal pushed_pcm, initialized
            if len(pcm) <= pushed_pcm:
                return
            if not initialized:
                output_emitter.initialize(
                    request_id=str(id(self)),
                    sample_rate=_SAMPLE_RATE,
                    num_channels=_NUM_CHANNELS,
                    mime_type="audio/pcm",
                )
                initialized = True
            # push() re-chunks raw PCM into frame_size_ms frames itself
            output_emitter.push(pcm[pushed_pcm:])
            pushed_pcm = len(pcm)

        async def _decode_prefix() -> None:
            """Best-effort early decode of the mp3 received so far."""
            nonlocal last_decode_at, last_decode_len
            # ffmpeg is a blocking subprocess; keep it off the audio loop.
            pcm = await asyncio.to_thread(_mp3_prefix_to_pcm, bytes(mp3))
            last_decode_at = time.monotonic()
            last_decode_len = len(mp3)
            if pcm:
                _emit_new(pcm)

        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and chunk.get("data"):
                mp3.extend(chunk["data"])
                if (
                    len(mp3) - last_decode_len >= _PREFIX_MIN_NEW_BYTES
                    and time.monotonic() - last_decode_at >= _PREFIX_MIN_INTERVAL_S
                ):
                    await _decode_prefix()

        if not mp3:
            raise RuntimeError("Edge TTS returned no audio bytes")

        # Strict whole-buffer decode settles the tail (and any prefix the
        # tolerant decoder skipped). Failure contract unchanged: if no
        # audio was ever pushed and the audio cannot be decoded, raise
        # BEFORE the emitter is initialized.
        pcm = await asyncio.to_thread(_mp3_to_pcm, bytes(mp3))
        if not pcm:
            if initialized:
                # Partial audio already played; a dead tail must not turn
                # a heard reply into a session error.
                output_emitter.flush()
                return
            raise RuntimeError(
                "Edge TTS audio could not be decoded; ffmpeg is unavailable or conversion failed"
            )
        _emit_new(pcm)
        output_emitter.flush()


class EdgeTTS(TTS):
    """Keyless, network-backed TTS (Microsoft Edge neural voices) for AgentSession.tts."""

    def __init__(self, voice: str = "en-IN-NeerjaNeural") -> None:
        if not EDGE_TTS_AVAILABLE:
            raise RuntimeError("edge-tts not installed on this host")
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=_SAMPLE_RATE,
            num_channels=_NUM_CHANNELS,
        )
        self.voice = voice

    def synthesize(self, text: str, *, conn_options=None) -> ChunkedStream:
        if conn_options is None:
            from livekit.agents import APIConnectOptions
            conn_options = APIConnectOptions()
        return _EdgeChunkedStream(
            tts=self, input_text=text, conn_options=conn_options,
            voice=self.voice)


async def _self_test() -> None:
    t = EdgeTTS()
    stream = t.synthesize("Namaskaram. This is FRIDAY, here and ready to listen.")
    audio = await stream.collect()
    data = getattr(audio, "data", None)
    if data is not None:
        total = len(data)
    else:
        total = sum(len(f.data) for f in audio)
    print("SELF_TEST", "OK" if total > 0 else "FAIL", total, "PCM bytes")


if __name__ == "__main__":
    asyncio.run(_self_test())
