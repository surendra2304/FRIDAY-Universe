"""TASK-VOI-025 — desktop/CLI VAD default consistency.

The two voice entry paths disagreed on the VAD start-of-speech default:

- CLI/desktop session path (``python -m friday --voice`` ->
  ``GeminiLiveVoiceSession``) read ``config.py``'s
  ``voice_vad_start_sensitivity``, whose default was LOW.
- LiveKit worker path (``friday/voice/livekit_worker.py``)
  defaulted HIGH (TASK-VOI-024 precautionary default).

The single shared default is now HIGH, defined once in
``friday/core/config.py`` as ``VOICE_VAD_START_SENSITIVITY_DEFAULT``
and read by both paths. These tests pin the agreement: with no env
override both paths resolve to HIGH, and the explicit LOW override
still works on each path (session env var for the session path,
``FRIDAY_VOICE_AAD_START_SENSITIVITY=low`` for the worker path).
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


def test_shared_default_is_high():
    """The one shared default both paths read is HIGH (TASK-VOI-024)."""
    assert VOICE_VAD_START_SENSITIVITY_DEFAULT == "HIGH"


def test_config_default_start_sensitivity_is_high(monkeypatch):
    """No env override -> Settings resolves the shared default HIGH."""
    _clear_vad_env(monkeypatch)
    assert Settings().voice_vad_start_sensitivity == "HIGH"


def test_session_default_start_sensitivity_is_high(monkeypatch):
    """No env override -> the CLI/desktop session resolves HIGH."""
    _clear_vad_env(monkeypatch)
    get_settings(reload=True)
    session = GeminiLiveVoiceSession(api_key="test-api-key")
    assert session.vad_start_sensitivity == "HIGH"


def test_worker_default_start_sensitivity_is_high(monkeypatch):
    """No env override -> the LiveKit worker resolves HIGH."""
    _clear_vad_env(monkeypatch)
    assert w._start_sensitivity() == _TYPES.StartSensitivity.START_SENSITIVITY_HIGH


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
        == _TYPES.StartSensitivity.START_SENSITIVITY_HIGH
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
