"""TASK-VOI-025 — desktop/CLI VAD default consistency.

The two voice entry paths disagreed on the VAD start-of-speech default:

- CLI/desktop session path (``python -m friday --voice`` ->
  ``GeminiLiveVoiceSession``) read ``config.py``'s
  ``voice_vad_start_sensitivity``, whose default was LOW.
- LiveKit worker path (``friday/voice/livekit_worker.py``)
  defaulted HIGH (TASK-VOI-024 precautionary default).

The single shared default is now LOW, defined once in
``friday/core/config.py`` as ``VOICE_VAD_START_SENSITIVITY_DEFAULT``
and read by both paths. These tests pin the agreement: with no env
override both paths resolve to LOW, and the explicit HIGH override
still works on each path (session env var for the session path,
``FRIDAY_VOICE_AAD_START_SENSITIVITY=high`` for the worker path).

TASK-VOI-032 (2026-11-24) flipped the shared default HIGH -> LOW:
the VOI-024 HIGH revert rested on the transcript-gap correlation,
whose mechanism VOI-024 itself convicted as send-path pacing
(fixed), not sensitivity; and the AAD sensitivity is the only
effective interruption gate on the deployed realtime_llm path.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.core.config import (
    VOICE_VAD_START_SENSITIVITY_DEFAULT,
    Settings,
    get_settings,
)
from friday.voice import livekit_worker as w
from friday.voice.gemini_live_session import GeminiLiveVoiceSession

pytestmark = pytest.mark.skipif(
    w.genai_types is None, reason="genai SDK types unavailable"
)

_TYPES = w.genai_types

_VAD_ENV_VARS = (
    "FRIDAY_VOICE_VAD_START_SENSITIVITY",
    "VOICE_VAD_START_SENSITIVITY",
    "voice_vad_start_sensitivity",
)


def _clear_vad_env(monkeypatch):
    for name in _VAD_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", raising=False)


def test_shared_default_is_low():
    """The one shared default both paths read is LOW (TASK-VOI-032)."""
    assert VOICE_VAD_START_SENSITIVITY_DEFAULT == "LOW"


def test_config_default_start_sensitivity_is_low(monkeypatch):
    """No env override -> Settings resolves the shared default LOW."""
    _clear_vad_env(monkeypatch)
    assert Settings().voice_vad_start_sensitivity == "LOW"


def test_session_default_start_sensitivity_is_low(monkeypatch):
    """No env override -> the CLI/desktop session resolves LOW."""
    _clear_vad_env(monkeypatch)
    get_settings(reload=True)
    session = GeminiLiveVoiceSession(api_key="test-api-key")
    assert session.vad_start_sensitivity == "LOW"


def test_worker_default_start_sensitivity_is_low(monkeypatch):
    """No env override -> the LiveKit worker resolves LOW."""
    _clear_vad_env(monkeypatch)
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_LOW


def test_both_paths_agree_on_default(monkeypatch):
    """The consistency property itself: both paths, one default."""
    _clear_vad_env(monkeypatch)
    get_settings(reload=True)
    session = GeminiLiveVoiceSession(api_key="test-api-key")
    assert session.vad_start_sensitivity == (
        VOICE_VAD_START_SENSITIVITY_DEFAULT
    )
    assert (
        w._start_sensitivity()
        == _TYPES.StartSensitivity.START_SENSITIVITY_LOW
    )


def test_low_override_still_available_on_session_path(monkeypatch):
    """Explicit LOW still works on the session path via its env var."""
    _clear_vad_env(monkeypatch)
    monkeypatch.setenv("FRIDAY_VOICE_VAD_START_SENSITIVITY", "low")
    get_settings(reload=True)
    assert Settings().voice_vad_start_sensitivity == "low"
    session = GeminiLiveVoiceSession(api_key="test-api-key")
    assert session.vad_start_sensitivity == "low"


def test_low_override_still_available_on_worker_path(monkeypatch):
    """Explicit LOW still works on the worker path via its env var."""
    _clear_vad_env(monkeypatch)
    monkeypatch.setenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", "low")
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_LOW


def test_high_override_still_available_on_session_path(monkeypatch):
    """Rollback (TASK-VOI-032): explicit HIGH still works on the
    session path via its env var, if transcripts ever regress."""
    _clear_vad_env(monkeypatch)
    monkeypatch.setenv("FRIDAY_VOICE_VAD_START_SENSITIVITY", "high")
    get_settings(reload=True)
    assert Settings().voice_vad_start_sensitivity == "high"
    session = GeminiLiveVoiceSession(api_key="test-api-key")
    assert session.vad_start_sensitivity == "high"


def test_high_override_still_available_on_worker_path(monkeypatch):
    """Rollback (TASK-VOI-032): explicit HIGH still works on the
    worker path via its env var."""
    _clear_vad_env(monkeypatch)
    monkeypatch.setenv("FRIDAY_VOICE_AAD_START_SENSITIVITY", "high")
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_HIGH
