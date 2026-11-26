"""TASK-VOI-012: STT fleet vocabulary + dropped-turn guard.

Pins the three layered defences against the FRD-005 re-run failure
(run 20261116-075300: "check Stratex for me" transcribed as "check
Stray Kids for me", delegation grounded on the mishearing):

- ``_input_transcription_config``: the Gemini Live API's real biasing
  surface — AudioTranscriptionConfig.custom_vocabulary carrying the
  fleet roster — with a defensive fallback when the installed genai
  SDK predates the field (a build failure here would mute the call:
  _build_realtime_model turns exceptions into "no voice").
- ``_realtime_input_config``: Gemini's automatic activity detection
  pinned explicitly (start LOW, end HIGH, prefix 200 ms, silence
  1200 ms — TASK-VOI-042 raised it from 500 ms so a mid-sentence
  pause stops splitting utterances into answered fragments,
  activity handling NO_INTERRUPTION — TASK-VOI-043 (d) replaced
  START_OF_ACTIVITY_INTERRUPTS so her answer is never cut by user
  activity) instead of the API-surface
  defaults, with None (pass nothing) as the degradation.
- ``_correct_fleet_terms``: the conservative post-STT correction map
  for the text the WORKER consumes (watchdog re-ask + rebuilt-session
  context) — whole-phrase, word-boundary, attested/non-word
  mishearings only; ordinary English words are never rewritten.
- ``_turn_unanswered_in_listening``: the dropped-turn guard predicate
  — a final transcript pending while the agent sits in "listening"
  (the wedge detector requires thinking/speaking, so this signature
  had NO recovery trigger before VOI-012).
- ``_build_realtime_model``: both new kwargs reach RealtimeModel, and
  a plugin generation that rejects an optional kwarg loses the option,
  not the call.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402

genai_types_real = pytest.importorskip("google.genai.types")


# ---------- _correct_fleet_terms ----------

@pytest.mark.parametrize(
    "raw, expected",
    [
        # the attested FRD-005 mishearing
        ("Friday, check Stray Kids for me", "Friday, check Stratex for me"),
        ("check stray kids for me", "check Stratex for me"),
        ("STRAY KIDS", "Stratex"),
        ("ask stray tex about the position", "ask Stratex about the position"),
        ("what does stratix say", "what does Stratex say"),
        ("show me the vyral x uploads", "show me the VyralX uploads"),
        ("viral ex channel stats", "VyralX channel stats"),
        ("intel ex flagged a threat", "IntelX flagged a threat"),
        ("ask intel x", "ask IntelX"),
        ("is sentinal up", "is Sentinel up"),
        ("memorah, what did I say", "Memora, what did I say"),
        # several rules in one utterance
        (
            "check stray kids and ask memorah",
            "check Stratex and ask Memora",
        ),
    ],
)
def test_correction_map_known_mishearings(raw, expected):
    assert w._correct_fleet_terms(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        # ordinary English words are NEVER rewritten
        "I surrender, enough for today",
        "this viral video is about memory",
        "the forge is hot today",
        "check the strategy for me",
        "what is the sentinel value in this array",
        # word boundaries: no partial-token rewrites
        "stray kidsx is not a thing",
        "memorandum on the desk",
        # already-correct text passes through byte-identical
        "check Stratex for me",
        "ask Memora and IntelX, then tell Surendra",
        "",
    ],
)
def test_correction_map_leaves_other_speech_untouched(raw):
    assert w._correct_fleet_terms(raw) == raw


# ---------- _input_transcription_config ----------

def test_transcription_config_none_without_genai_types(monkeypatch):
    monkeypatch.setattr(w, "genai_types", None)
    assert w._input_transcription_config() is None


def test_transcription_config_carries_fleet_vocabulary(monkeypatch):
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    cfg = w._input_transcription_config()
    assert cfg is not None
    vocab = list(cfg.custom_vocabulary)
    assert vocab == list(w._FLEET_VOCABULARY)
    for name in (
        "Stratex", "Memora", "Futuris", "IntelX", "VyralX", "Cortex",
        "Sentinel", "Forge", "Inference", "FRIDAY", "Surendra",
    ):
        assert name in vocab
    # Google's guidance: best results with up to ~100 terms.
    assert len(vocab) <= 100


def test_transcription_config_pins_en_in_by_default(monkeypatch):
    # TASK-VOI-042 (P0): the owner's English was transcribed in
    # Hindi/Telugu script while language_codes stayed unset
    # (auto-detect). The transcription now pins the effective
    # session language — en-IN unless FRIDAY_VOICE_LANGUAGE says
    # otherwise — so English speech cannot be re-scripted.
    monkeypatch.delenv("FRIDAY_VOICE_LANGUAGE", raising=False)
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    cfg = w._input_transcription_config()
    assert cfg is not None
    assert list(cfg.language_codes) == ["en-IN"]
    assert list(cfg.custom_vocabulary) == list(w._FLEET_VOCABULARY)


def test_transcription_config_follows_the_profile(monkeypatch):
    monkeypatch.setenv("FRIDAY_VOICE_LANGUAGE", "te-IN")
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    cfg = w._input_transcription_config()
    assert list(cfg.language_codes) == ["te-IN"]


def test_transcription_config_junk_env_falls_back_to_en_in(monkeypatch):
    monkeypatch.setenv("FRIDAY_VOICE_LANGUAGE", "klingon")
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    cfg = w._input_transcription_config()
    assert list(cfg.language_codes) == ["en-IN"]


def test_transcription_config_degrades_on_old_sdk(monkeypatch):
    class StrictConfig:
        def __init__(self, **kwargs):
            if "custom_vocabulary" in kwargs:
                raise TypeError("unexpected keyword 'custom_vocabulary'")
            self.kwargs = kwargs

    fake = SimpleNamespace(AudioTranscriptionConfig=StrictConfig)
    monkeypatch.setattr(w, "genai_types", fake)
    cfg = w._input_transcription_config()
    assert isinstance(cfg, StrictConfig)
    assert cfg.kwargs == {}


def test_transcription_config_drops_only_the_pin_on_old_sdk(monkeypatch):
    # TASK-VOI-042 ladder, rung 2: an SDK that knows the vocabulary
    # but predates language_codes keeps the biasing and loses only
    # the pin — the call still goes through.
    class PinlessConfig:
        def __init__(self, **kwargs):
            if "language_codes" in kwargs:
                raise TypeError("unexpected keyword 'language_codes'")
            self.kwargs = kwargs

    fake = SimpleNamespace(AudioTranscriptionConfig=PinlessConfig)
    monkeypatch.setattr(w, "genai_types", fake)
    cfg = w._input_transcription_config()
    assert isinstance(cfg, PinlessConfig)
    assert cfg.kwargs == {"custom_vocabulary": list(w._FLEET_VOCABULARY)}


# ---------- _realtime_input_config ----------

def test_realtime_config_none_without_genai_types(monkeypatch):
    monkeypatch.setattr(w, "genai_types", None)
    assert w._realtime_input_config() is None


def test_realtime_config_none_when_types_missing(monkeypatch):
    monkeypatch.setattr(w, "genai_types", SimpleNamespace())
    assert w._realtime_input_config() is None


def test_realtime_config_pins_aad(monkeypatch):
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    cfg = w._realtime_input_config()
    assert cfg is not None
    aad = cfg.automatic_activity_detection
    assert aad.start_of_speech_sensitivity == (
        genai_types_real.StartSensitivity.START_SENSITIVITY_LOW
    )
    assert aad.end_of_speech_sensitivity == (
        genai_types_real.EndSensitivity.END_SENSITIVITY_HIGH
    )
    assert aad.prefix_padding_ms == 200
    # TASK-VOI-042: 1200 ms, not 500 — the owner's sentences were
    # split into finals at a half-second pause and answered as
    # fragments (2026-11-25 live test). FRIDAY_VOICE_AAD_SILENCE_MS
    # still overrides (see test_realtime_config_env_overrides).
    assert aad.silence_duration_ms == 1200
    # TASK-VOI-043 (d): NO_INTERRUPTION is the deliberate default —
    # START_OF_ACTIVITY_INTERRUPTS let the owner's own continuation
    # cut her answer off mid-sentence. Barge-in is restored only via
    # FRIDAY_VOICE_AAD_ACTIVITY_HANDLING=start_of_activity_interrupts
    # (pinned in test_voice_noise_interruption_voi032.py).
    assert cfg.activity_handling == (
        genai_types_real.ActivityHandling.NO_INTERRUPTION
    )


def test_realtime_config_env_overrides(monkeypatch):
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    monkeypatch.setenv("FRIDAY_VOICE_AAD_SILENCE_MS", "900")
    monkeypatch.setenv("FRIDAY_VOICE_AAD_PREFIX_PADDING_MS", "120")
    aad = w._realtime_input_config().automatic_activity_detection
    assert aad.silence_duration_ms == 900
    assert aad.prefix_padding_ms == 120


# ---------- _turn_unanswered_in_listening ----------

def _turn(**over):
    base = {
        "pending_since": 100.0,
        "state": "listening",
        "last_assistant_ts": 0.0,
        "reask_for": None,
    }
    base.update(over)
    return base


def test_guard_fires_for_dropped_turn():
    assert w._turn_unanswered_in_listening(_turn(), now=131.0) is True


def test_guard_silent_before_threshold():
    assert w._turn_unanswered_in_listening(_turn(), now=110.0) is False


def test_guard_silent_while_agent_busy():
    # thinking/speaking is the wedge detector's territory (a slow tool
    # call must never be mistaken for a dropped turn)
    for state in ("thinking", "speaking", "initializing"):
        assert w._turn_unanswered_in_listening(_turn(state=state), now=200.0) is False


def test_guard_silent_when_answered():
    turn = _turn(last_assistant_ts=120.0)
    assert w._turn_unanswered_in_listening(turn, now=200.0) is False


def test_guard_silent_without_pending():
    assert w._turn_unanswered_in_listening(_turn(pending_since=None), now=200.0) is False


def test_guard_fires_once_per_pending_turn():
    turn = _turn(reask_for=100.0)
    assert w._turn_unanswered_in_listening(turn, now=200.0) is False
    # a NEW final transcript (new pending_since) may fire again
    turn = _turn(pending_since=300.0, reask_for=100.0)
    assert w._turn_unanswered_in_listening(turn, now=400.0) is True


# ---------- _build_realtime_model wiring ----------

class _FakeRealtimeModel:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeRealtimeModel.instances.append(self)


def _fake_google(model_cls):
    return SimpleNamespace(realtime=SimpleNamespace(RealtimeModel=model_cls))


@pytest.fixture
def _model_env(monkeypatch):
    _FakeRealtimeModel.instances = []
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    monkeypatch.setattr(w, "_voice_language", lambda: None)
    return _FakeRealtimeModel


def test_build_passes_biasing_and_aad_kwargs(monkeypatch, _model_env):
    monkeypatch.setattr(w, "_lk_google", _fake_google(_model_env))
    model = w._build_realtime_model("key-1", "instructions")
    assert model is not None
    kwargs = _model_env.instances[-1].kwargs
    assert list(kwargs["input_audio_transcription"].custom_vocabulary) == list(
        w._FLEET_VOCABULARY
    )
    aad = kwargs["realtime_input_config"].automatic_activity_detection
    assert aad.silence_duration_ms == 1200
    assert "language" not in kwargs


def test_build_pins_language_and_transcription_by_default(monkeypatch):
    # TASK-VOI-042: with the REAL _voice_language (no mock) the
    # model carries language="en-IN" and the transcription carries
    # language_codes=["en-IN"] — the two halves of the (a) pin,
    # proven against the real genai SDK types.
    _FakeRealtimeModel.instances = []
    monkeypatch.setattr(w, "genai_types", genai_types_real)
    monkeypatch.setattr(w, "_lk_google", _fake_google(_FakeRealtimeModel))
    monkeypatch.delenv("FRIDAY_VOICE_LANGUAGE", raising=False)
    model = w._build_realtime_model("key-1", "instructions")
    assert model is not None
    kwargs = _FakeRealtimeModel.instances[-1].kwargs
    assert kwargs["language"] == "en-IN"
    assert list(kwargs["input_audio_transcription"].language_codes) == ["en-IN"]


def test_build_drops_rejected_optional_kwarg_not_the_call(monkeypatch, _model_env):
    class PickyModel:
        def __init__(self, **kwargs):
            if "realtime_input_config" in kwargs:
                raise TypeError("unexpected keyword 'realtime_input_config'")
            self.kwargs = kwargs
            _FakeRealtimeModel.instances.append(self)

    monkeypatch.setattr(w, "_lk_google", _fake_google(PickyModel))
    model = w._build_realtime_model("key-1", "instructions")
    assert model is not None
    kwargs = _FakeRealtimeModel.instances[-1].kwargs
    assert "realtime_input_config" not in kwargs
    # the other VOI-012 option survived the drop
    assert "input_audio_transcription" in kwargs


def test_build_returns_none_when_plugin_rejects_everything(monkeypatch, _model_env):
    class HostileModel:
        def __init__(self, **kwargs):
            raise TypeError("no kwargs accepted at all")

    monkeypatch.setattr(w, "_lk_google", _fake_google(HostileModel))
    assert w._build_realtime_model("key-1", "instructions") is None


# ---------- _session_turn_kwargs ----------

def test_session_turn_kwargs_wait_for_a_complete_sentence():
    # TASK-VOI-042 (b): min endpointing 1.0 s (was 0.5) — the
    # session waits a full second of quiet before treating a turn
    # as complete, so a mid-sentence pause does not split one
    # utterance into answered fragments. Max 3.0 s bounds the wait;
    # real barge-in stays enabled.
    kwargs = w._session_turn_kwargs()
    assert kwargs["turn_detection"] == "realtime_llm"
    assert kwargs["min_endpointing_delay"] == 1.0
    assert kwargs["max_endpointing_delay"] == 3.0
    assert kwargs["allow_interruptions"] is True
    assert kwargs["min_interruption_duration"] == 0.8
    assert kwargs["resume_false_interruption"] is True
    assert kwargs["false_interruption_timeout"] == 1.0


# ---------- integration pins (source-level) ----------

def test_worker_wiring_points_present():
    src = Path(w.__file__).read_text(encoding="utf-8")
    # the correction reaches the watchdog's pending text
    assert 'turn["pending_text"] = corrected' in src
    # the guard runs inside the watchdog poll and re-asks on the session
    assert "_turn_unanswered_in_listening(turn, time.time())" in src
    assert "sess.generate_reply(user_input=pending_text)" in src
    # the greeting path and VOI-010's session shape are untouched;
    # the session knobs ride through _session_turn_kwargs (VOI-042)
    assert "**_session_turn_kwargs()" in src
    assert '"turn_detection": "realtime_llm"' in src
    assert '"allow_interruptions": True' in src
    # instruction priming carries the attested mishearing
    assert "Stray Kids" in w.BASE_INSTRUCTIONS
    assert "Surendra" in w.BASE_INSTRUCTIONS
