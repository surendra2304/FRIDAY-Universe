"""TASK-VOI-032 — the background-noise interruption defect.

Owner live test, 2026-11-17 ~21:06 IST (FRIDAY-Voice journal, Server 1):
ordinary background noise — a fan — kept stopping FRIDAY mid-answer.
The journal shows the shape plainly: her agent_state flipped
speaking->listening at 21:07:00, :02, :05, :08, :10, :13, :19 and :20 —
speech segments of ~1-4.6 s separated by ~1 s listening gaps, >=9
interruptions in ~37 s, each gap carrying a short fragment transcript
('FRIDAY', 'Hi.', 'Irena', single Telugu words). Non-speech room audio
was being scored as user turns.

ROOT CAUSE (proven offline against the deployed pins,
livekit-agents 1.8.11 / livekit-plugins-google 1.8.10, google-genai
2.33.0 — the library behaviour below is exercised, not asserted
from source):

1. The deployed session runs turn_detection="realtime_llm", so
   Gemini's server-side automatic activity detection is the SOLE
   interruption arbiter. A server `server_content.interrupted`
   becomes a plugin `input_speech_started` event, which the
   activity turns into interrupt(source="audio_activity") —
   unconditionally, with no duration, transcript or energy check,
   and the interruption is terminal (no resume).
2. The worker's local interruption guards are INERT on this path:
   on_vad_inference_done ignores VAD events outright when
   turn_detection is realtime_llm, and _interrupt_by_audio_activity
   returns early while server-side turn detection is on — so
   min_interruption_duration=0.8, resume_false_interruption and
   false_interruption_timeout never gate anything. A 5 s VAD speech
   event (far past the 0.8 s floor) interrupts nothing under
   realtime_llm, while the same event DOES interrupt under "stt"
   (the control arm below proves the harness can see one).
3. The overlapping-speech escape hatch is unavailable: the Google
   realtime model's capabilities report supports_overlapping_speech
   False (and can_disable_turn_detection False), so the client
   cannot hand turn-taking to the local VAD either.
4. The send path stated no audio processing: the dashboard mic was
   published with setMicrophoneEnabled(true) and no capture
   options, so nothing upstream attenuated steady fan noise before
   it reached Gemini's detector.

FIX (this task): the AAD start-of-speech sensitivity default goes
back to LOW — the VOI-018 value, restored because VOI-024's own
diagnosis convicted send-path pacing, not sensitivity, as the
transcript-gap mechanism (and shipped the pacing fix), so the
correlation that motivated the HIGH revert has a proven
alternative cause; and because (2) leaves the sensitivity as the
only gate between fan noise and a truncated answer. The browser
mic additionally pins noise suppression / echo cancellation /
auto gain control explicitly at both enable sites (defence in
depth — best-effort browser processing, not the decider).
Genuine barge-in is untouched: activity handling stays
START_OF_ACTIVITY_INTERRUPTS, prefix padding 200 ms, end
sensitivity HIGH, silence 500 ms. Rollback stays one env var
away: FRIDAY_VOICE_AAD_START_SENSITIVITY=high (worker) /
FRIDAY_VOICE_VAD_START_SENSITIVITY=high (session path).

LIVE PROOF STILL OWED: the calm-vs-noise A/B (she finishes her
answers under fan noise, real barge-in still cuts in, transcripts
healthy under LOW) needs a calm window on S1 and coordinator
clearance — it is NOT claimed by this suite.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.core.config import VOICE_VAD_START_SENSITIVITY_DEFAULT
from friday.voice import livekit_worker as w  # noqa: E402

pytestmark = pytest.mark.skipif(w.genai_types is None, reason="genai SDK types unavailable")

_TYPES = w.genai_types
agents = pytest.importorskip("livekit.agents")


def _aad(monkeypatch, env=None):
    monkeypatch.delenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", raising=False)
    if env is not None:
        monkeypatch.setenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", env)
    cfg = w._realtime_input_config()
    assert cfg is not None
    return cfg.automatic_activity_detection


# ---------------------------------------------------------------------------
# The fix: the default is the noise-robust value again
# ---------------------------------------------------------------------------


def test_shared_default_is_low(monkeypatch):
    """The one shared default both voice paths read is LOW (VOI-032):
    the VOI-024 HIGH revert rested on the transcript-gap
    correlation, whose mechanism VOI-024 itself convicted as
    send-path pacing — fixed — not sensitivity."""
    assert VOICE_VAD_START_SENSITIVITY_DEFAULT == "LOW"


def test_default_start_sensitivity_is_low(monkeypatch):
    """No env override -> LOW: steady fan noise must not commit a
    start-of-speech, or FRIDAY stops mid-answer at a 1-4 s cadence
    (the 2026-11-17 journal shape)."""
    aad = _aad(monkeypatch)
    assert aad.start_of_speech_sensitivity == (_TYPES.StartSensitivity.START_SENSITIVITY_LOW)


def test_helper_default_is_low(monkeypatch):
    monkeypatch.delenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", raising=False)
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_LOW


def test_junk_env_value_falls_back_to_low(monkeypatch):
    """A typo'd override must land on the default side — LOW —
    never silently re-enable the suspect HIGH setting."""
    aad = _aad(monkeypatch, env="loud")
    assert aad.start_of_speech_sensitivity == (_TYPES.StartSensitivity.START_SENSITIVITY_LOW)


def test_env_high_restores_high_rollback(monkeypatch):
    """Rollback stays one env var away: =high restores the VOI-024
    value exactly, if transcripts ever regress under LOW."""
    aad = _aad(monkeypatch, env="high")
    assert aad.start_of_speech_sensitivity == (_TYPES.StartSensitivity.START_SENSITIVITY_HIGH)
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_HIGH


def test_env_low_selects_low(monkeypatch):
    aad = _aad(monkeypatch, env="low")
    assert aad.start_of_speech_sensitivity == (_TYPES.StartSensitivity.START_SENSITIVITY_LOW)


# ---------------------------------------------------------------------------
# Real barge-in and reply speed are NOT traded away
# ---------------------------------------------------------------------------


def test_activity_handling_still_interrupts(monkeypatch):
    """Real speech still interrupts: only the EVIDENCE BAR for what
    counts as speech onset moved."""
    cfg = w._realtime_input_config()
    assert cfg.activity_handling == (_TYPES.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS)


def test_prefix_padding_keeps_first_syllable(monkeypatch):
    aad = _aad(monkeypatch)
    assert aad.prefix_padding_ms == 200


def test_end_sensitivity_and_silence_unchanged(monkeypatch):
    """Turn finalization (reply speed) is NOT traded for noise
    robustness: end sensitivity stays HIGH, silence stays 500 ms."""
    aad = _aad(monkeypatch)
    assert aad.end_of_speech_sensitivity == (_TYPES.EndSensitivity.END_SENSITIVITY_HIGH)
    assert aad.silence_duration_ms == 500


# ---------------------------------------------------------------------------
# The defect mechanism, exercised against the deployed library
# ---------------------------------------------------------------------------


def _activity(monkeypatch):
    """A real AgentSession + AgentActivity built with the worker's
    exact session kwargs, on a dummy-key realtime model (model
    construction is local; no network, no room, no session start).
    """
    monkeypatch.delenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", raising=False)
    model = w._build_realtime_model("dummy-key-for-offline-probe", "You are FRIDAY.")
    assert model is not None
    session = w._build_session(
        llm=model,
        turn_detection="realtime_llm",
        min_endpointing_delay=0.5,
        max_endpointing_delay=3.0,
        allow_interruptions=True,
        min_interruption_duration=0.8,
        resume_false_interruption=True,
        false_interruption_timeout=1.0,
    )
    agent = agents.Agent(instructions="You are FRIDAY.")
    from livekit.agents.voice.agent_activity import AgentActivity

    return AgentActivity(agent, session)


def _vad_event(speech_duration=5.0):
    from livekit.agents.vad import VADEvent, VADEventType

    return VADEvent(
        type=VADEventType.INFERENCE_DONE,
        samples_index=0,
        timestamp=0.0,
        speech_duration=speech_duration,
        silence_duration=0.0,
        probability=0.95,
        raw_accumulated_silence=0.0,
    )


def test_deployed_session_is_server_turn_detection(monkeypatch):
    """The deployed shape, pinned: realtime_llm turn detection is
    on, overlapping speech is off (the Google model does not
    support it), and interruption-by-audio-activity is disabled —
    the server owns every interruption decision."""
    activity = _activity(monkeypatch)
    assert activity._turn_detection == "realtime_llm"
    assert activity._rt_turn_detection_enabled is True
    assert activity._rt_overlapping_speech_enabled is False
    assert activity._interruption_by_audio_activity_enabled is False


def test_vad_speech_event_does_not_interrupt_under_realtime_llm(monkeypatch):
    """THE INERT GATE: a 5 s VAD speech event — far past the 0.8 s
    min_interruption_duration floor — interrupts NOTHING while
    turn_detection is realtime_llm. The local VAD path never sees
    it, so the floor cannot protect FRIDAY from fan noise."""
    activity = _activity(monkeypatch)
    calls = []
    activity._interrupt_by_audio_activity = lambda *a, **k: calls.append(a)
    activity.on_vad_inference_done(_vad_event(speech_duration=5.0))
    assert calls == []


def test_vad_speech_event_interrupts_under_stt_control(monkeypatch):
    """Control arm: the SAME 5 s event under "stt" turn detection
    DOES interrupt — the harness can see an interruption, so the
    empty call list above is the library's realtime_llm branch,
    not a dead spy."""
    activity = _activity(monkeypatch)
    calls = []
    activity._interrupt_by_audio_activity = lambda *a, **k: calls.append(a)
    activity._turn_detection = "stt"
    activity.on_vad_inference_done(_vad_event(speech_duration=5.0))
    assert len(calls) == 1


def test_server_input_speech_started_interrupts_unconditionally(monkeypatch):
    """THE CUT: a server input_speech_started event (what Gemini's
    `interrupted` signal becomes) calls interrupt() with no
    duration, transcript or energy check in between — the fan
    noise that crosses the start-sensitivity threshold truncates
    her answer on the spot."""
    activity = _activity(monkeypatch)
    calls = []
    real_interrupt = activity.interrupt

    def _spy(*a, **k):
        calls.append(k)
        return real_interrupt(*a, **k)

    activity.interrupt = _spy
    activity._on_input_speech_started(agents.llm.InputSpeechStartedEvent())
    assert len(calls) == 1
    assert calls[0].get("source") == "audio_activity"


def test_overlapping_speech_arm_would_not_interrupt(monkeypatch):
    """The one library arm that would NOT cut her off on a server
    speech-started event — overlapping speech, where the model
    ends its own turn — is unavailable: the deployed Google model
    reports supports_overlapping_speech False, so this arm can
    never engage. (Documents why the fix had to be the AAD
    sensitivity, not a session flag.)"""
    activity = _activity(monkeypatch)
    calls = []
    real_interrupt = activity.interrupt

    def _spy(*a, **k):
        calls.append(k)
        return real_interrupt(*a, **k)

    activity.interrupt = _spy
    activity._rt_overlapping_speech_enabled = True
    activity._on_input_speech_started(agents.llm.InputSpeechStartedEvent())
    assert calls == []


# ---------------------------------------------------------------------------
# Send path: the dashboard mic states its audio processing
# ---------------------------------------------------------------------------

_VOICECALL = Path(__file__).resolve().parents[1] / "ui" / "components" / "VoiceCall.tsx"


def test_mic_capture_options_pinned():
    """Both setMicrophoneEnabled(true) sites pass the pinned
    capture options — noise suppression, echo cancellation, auto
    gain control — so steady fan noise is attenuated before it
    reaches Gemini's detector. (Best-effort browser processing;
    the AAD sensitivity above is the decider.)"""
    src = _VOICECALL.read_text()
    assert "noiseSuppression: true" in src
    assert "echoCancellation: true" in src
    assert "autoGainControl: true" in src
    assert src.count("setMicrophoneEnabled(true, MIC_CAPTURE_OPTIONS)") == 2
    # No bare enable left: every publish states its processing.
    assert "setMicrophoneEnabled(true)" not in src.replace("setMicrophoneEnabled(true, MIC_CAPTURE_OPTIONS)", "")
