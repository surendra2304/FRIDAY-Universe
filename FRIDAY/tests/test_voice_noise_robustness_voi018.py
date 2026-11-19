"""TASK-VOI-018 — steady background noise must not interrupt FRIDAY.

Owner live test, 2026-11-17 ~21:06 IST (FRIDAY-Voice journal, Server 1,
worker MainPID 3029461): voice was ~50% better, but ordinary background
noise — a fan — kept stopping FRIDAY mid-answer. The journal shows the
shape plainly: from 21:06:56 her agent_state flipped
speaking->listening at 21:07:00, :02, :05, :08, :10, :13, :19 and :20 —
speech segments of ~1–4.6 s separated by ~1 s listening gaps, >=9
interruptions in ~37 s, each gap carrying a short fragment transcript
('FRIDAY', 'Hi.', 'Irena', single Telugu words). Non-speech room audio
was being scored as user turns.

Mechanism (code-proven): ``_realtime_input_config`` pinned Gemini
Live's automatic activity detection at START_SENSITIVITY_HIGH with
START_OF_ACTIVITY_INTERRUPTS (TASK-VOI-012) — maximum eagerness to
treat any detected activity as speech onset and interrupt the model's
turn. The VOI-016 RMS dead-input monitor is NOT in this path: it only
stamps energy timestamps, its verdict additionally requires zero
transcripts in the session's whole life, and it never truncates
playback.

Fix pinned here: start-of-speech sensitivity defaults to LOW — the
documented setting for noisy environments, which demands stronger
speech evidence before a start-of-speech commits — while everything
that makes a GENUINE barge-in work is untouched:

- activity_handling stays START_OF_ACTIVITY_INTERRUPTS (real speech
  still interrupts her);
- end-of-speech sensitivity stays HIGH and silence stays 500 ms
  (reply speed — the owner's #1 voice criterion — is not traded away);
- prefix padding stays 200 ms (a genuine barge-in keeps its first
  syllable);
- env FRIDAY_VOICE_AAD_START_SENSITIVITY=high restores the old
  behaviour as a rollback; any other/junk value resolved to LOW
  under VOI-018 (TASK-VOI-024: junk now resolves to HIGH — see
  the revert note below).

TASK-VOI-024 (2026-11-19) REVERTED the default to HIGH — the pins
below now assert the reverted contract. Reason: the transcript-gap
diagnosis found every transcript-positive session on record ran
HIGH and every zero-transcript run since the VOI-018 flip
(retests #14, #15B, #16) ran LOW, and the decisive A/B experiment
could not exonerate LOW (its LOW arm's send cadence collapsed —
the defect TASK-VOI-024's pacing fix addresses — so the clean
sensitivity test never occurred). HIGH is the precautionary
default again; LOW remains available as the explicit env
override (FRIDAY_VOICE_AAD_START_SENSITIVITY=low) if the fan
defect above returns with transcripts proven healthy. The
barge-in guards (activity handling, prefix padding, end
sensitivity, silence) are exactly as VOI-018 left them.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402

pytestmark = pytest.mark.skipif(
    w.genai_types is None, reason="genai SDK types unavailable"
)

_TYPES = w.genai_types


def _aad(monkeypatch, env=None):
    monkeypatch.delenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", raising=False)
    if env is not None:
        monkeypatch.setenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", env)
    cfg = w._realtime_input_config()
    assert cfg is not None
    return cfg.automatic_activity_detection


# ---------------------------------------------------------------------------
# The fan case: steady background noise must not register as a user turn
# ---------------------------------------------------------------------------


def test_default_start_sensitivity_is_high(monkeypatch):
    """No env override -> HIGH (TASK-VOI-024 revert): HIGH is the
    configuration of every transcript-positive session on record;
    the VOI-018 LOW default correlated perfectly with the
    zero-transcript runs that followed it. (On VOI-018/VOI-023
    code this is LOW and the test fails — that is the defect this
    revert removes.)"""
    aad = _aad(monkeypatch)
    assert aad.start_of_speech_sensitivity == (
        _TYPES.StartSensitivity.START_SENSITIVITY_HIGH
    )


def test_helper_default_is_high(monkeypatch):
    monkeypatch.delenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", raising=False)
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_HIGH


def test_junk_env_value_falls_back_to_high(monkeypatch):
    """A typo'd override must land on the default side — HIGH —
    never silently re-enable the suspect LOW setting."""
    aad = _aad(monkeypatch, env="loud")
    assert aad.start_of_speech_sensitivity == (
        _TYPES.StartSensitivity.START_SENSITIVITY_HIGH
    )


# ---------------------------------------------------------------------------
# The barge-in case: genuine owner speech must still interrupt her
# ---------------------------------------------------------------------------


def test_activity_handling_still_interrupts(monkeypatch):
    """Real speech still interrupts: activity handling is unchanged —
    only the EVIDENCE BAR for what counts as speech onset moved."""
    cfg = w._realtime_input_config()
    assert cfg.activity_handling == (
        _TYPES.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS
    )


def test_prefix_padding_keeps_first_syllable(monkeypatch):
    """200 ms of pre-onset audio is still included, so a genuine
    barge-in is not clipped while the server commits."""
    aad = _aad(monkeypatch)
    assert aad.prefix_padding_ms == 200


# ---------------------------------------------------------------------------
# Speed + rollback guards
# ---------------------------------------------------------------------------


def test_end_sensitivity_and_silence_unchanged(monkeypatch):
    """Turn finalization (reply speed) is NOT traded for noise
    robustness: end sensitivity stays HIGH, silence stays 500 ms."""
    aad = _aad(monkeypatch)
    assert aad.end_of_speech_sensitivity == (
        _TYPES.EndSensitivity.END_SENSITIVITY_HIGH
    )
    assert aad.silence_duration_ms == 500


def test_env_high_selects_high(monkeypatch):
    """FRIDAY_VOICE_AAD_START_SENSITIVITY=high selects HIGH
    explicitly (now also the default)."""
    aad = _aad(monkeypatch, env="high")
    assert aad.start_of_speech_sensitivity == (
        _TYPES.StartSensitivity.START_SENSITIVITY_HIGH
    )
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_HIGH


def test_env_override_selects_low(monkeypatch):
    """The env override still wins over the default:
    FRIDAY_VOICE_AAD_START_SENSITIVITY=low selects the VOI-018
    value exactly — the rollback path if the fan defect returns
    with transcripts proven healthy."""
    aad = _aad(monkeypatch, env="low")
    assert aad.start_of_speech_sensitivity == (
        _TYPES.StartSensitivity.START_SENSITIVITY_LOW
    )
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_LOW
