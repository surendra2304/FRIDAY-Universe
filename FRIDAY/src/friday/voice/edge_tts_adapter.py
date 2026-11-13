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
import io
import os
import subprocess
import tempfile

from livekit.agents.tts import ChunkedStream, TTS, TTSCapabilities

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

_SAMPLE_RATE = 24000
_NUM_CHANNELS = 1


def _mp3_to_pcm(data: bytes) -> bytes | None:
    """mp3 bytes -> s16le PCM via ffmpeg.

    ffmpeg resolution order: PATH, then the static-ffmpeg wheel bundled
    binary (Server 1 has no system ffmpeg; static_ffmpeg ships one and is
    a worker-venv dependency since TASK-VOICE-E2E-003).
    """
    import shutil

    exe = shutil.which("ffmpeg")
    if exe is None:
        try:
            from static_ffmpeg import add_paths

            add_paths()
            exe = shutil.which("ffmpeg")
        except Exception:
            exe = None
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


class _EdgeChunkedStream(ChunkedStream):
    def __init__(self, *, tts, input_text, conn_options, voice):
        super().__init__(tts=tts, input_text=input_text,
                         conn_options=conn_options)
        self._voice = voice

    async def _run(self, output_emitter) -> None:
        communicate = edge_tts.Communicate(self.input_text, self._voice)
        mp3 = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3.write(chunk["data"])
        audio = mp3.getvalue()
        if audio:
            # ffmpeg is a blocking subprocess; keep it off LiveKit's audio loop.
            pcm = await asyncio.to_thread(_mp3_to_pcm, audio)
            if pcm:
                output_emitter.initialize(
                    request_id=str(id(self)),
                    sample_rate=_SAMPLE_RATE,
                    num_channels=_NUM_CHANNELS,
                    mime_type="audio/pcm",
                )
                # push() re-chunks raw PCM into frame_size_ms frames itself
                output_emitter.push(pcm)
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
