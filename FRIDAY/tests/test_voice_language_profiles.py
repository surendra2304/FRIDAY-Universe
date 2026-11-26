"""TASK-IG-VOI-03 — Indian-language voice profiles.

Source idea: reel DV563QjD0Ft (business AI voice agents with
Indian-language support). These tests pin:

- the profile table: the eleven launch profiles, well-formed BCP-47
  codes, resolvable by code or name in any case;
- the default contract (TASK-VOI-042, P0 2026-11-25): NO profile
  configured means the session language is en-IN — the model is
  built with language="en-IN" and the instruction section names
  English (India). Native mirroring was the 2026-11-25 failure
  (owner's English transcribed in Hindi/Telugu script); an explicit
  FRIDAY_VOICE_LANGUAGE still overrides the default, and junk
  values fall back to en-IN, never to mirroring;
- the configured path: the model is built with the profile's code;
- the degradation path: a plugin generation that rejects the
  language option builds without it instead of losing the call.

Worker tests need the livekit stack and skip where it is absent
(CI installs FRIDAY's requirements and runs them).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import language_profiles as lp  # noqa: E402


# ---------------------------------------------------------------------------
# Profile table + resolution (pure)
# ---------------------------------------------------------------------------

def test_eleven_indian_language_profiles_with_wellformed_codes():
    assert len(lp.PROFILES) == 11
    for code, profile in lp.PROFILES.items():
        assert re.fullmatch(r"[a-z]{2,3}-[A-Z]{2}", code), code
        assert profile.code == code
        assert profile.name and profile.native_name


@pytest.mark.parametrize("value,code", [
    ("te-IN", "te-IN"), ("te_in", "te-IN"), ("TE-IN", "te-IN"),
    ("Telugu", "te-IN"), ("telugu", "te-IN"),
    ("hi-IN", "hi-IN"), ("Hindi", "hi-IN"),
    ("en-IN", "en-IN"), ("English (India)", "en-IN"),
    (" ur-IN ", "ur-IN"),
])
def test_resolve_by_code_or_name(value, code):
    profile = lp.resolve(value)
    assert profile is not None and profile.code == code


@pytest.mark.parametrize("value", ["", None, "klingon", "xx-YY", "te"])
def test_unresolvable_values_mean_no_profile(value):
    assert lp.resolve(value) is None
    assert lp.configured_language({"FRIDAY_VOICE_LANGUAGE": value or ""}) is None


def test_configured_language_reads_the_env_name():
    assert lp.configured_language({"FRIDAY_VOICE_LANGUAGE": "ta-IN"}) == "ta-IN"
    assert lp.configured_language({}) is None


def test_effective_language_defaults_to_en_in():
    # TASK-VOI-042: unset, empty and junk all land on the pinned
    # default — never on None (mirroring was the failure mode).
    assert lp.effective_language({}) == "en-IN"
    assert lp.effective_language({"FRIDAY_VOICE_LANGUAGE": ""}) == "en-IN"
    assert lp.effective_language({"FRIDAY_VOICE_LANGUAGE": "klingon"}) == "en-IN"
    assert lp.effective_language({"FRIDAY_VOICE_LANGUAGE": "te-IN"}) == "te-IN"


def test_instruction_section_names_the_default_language():
    # TASK-VOI-042: the section is present on every call now — the
    # model is told English (India) from the first word unless the
    # user switches language mid-call.
    section = lp.instruction_section({})
    assert "English (India)" in section and "en-IN" in section
    assert "primarily" in section
    junk = lp.instruction_section({"FRIDAY_VOICE_LANGUAGE": "klingon"})
    assert "en-IN" in junk


def test_instruction_section_names_the_profile():
    section = lp.instruction_section({"FRIDAY_VOICE_LANGUAGE": "telugu"})
    assert "Telugu" in section and "te-IN" in section
    assert "primarily" in section


# ---------------------------------------------------------------------------
# Worker wiring (needs the livekit stack; CI runs these)
# ---------------------------------------------------------------------------

class _FakeRealtimeModel:
    calls: list = []
    reject_language = False

    def __init__(self, **kwargs):
        if type(self).reject_language and "language" in kwargs:
            raise TypeError("unexpected keyword argument 'language'")
        type(self).calls.append(kwargs)
        self.kwargs = kwargs


@pytest.fixture()
def fake_plugin(monkeypatch):
    pytest.importorskip("livekit.agents")
    from friday.voice import livekit_worker as worker

    _FakeRealtimeModel.calls = []
    _FakeRealtimeModel.reject_language = False
    monkeypatch.setattr(
        worker, "_lk_google",
        SimpleNamespace(realtime=SimpleNamespace(RealtimeModel=_FakeRealtimeModel)),
    )
    monkeypatch.setattr(
        worker, "genai_types",
        SimpleNamespace(HttpOptions=lambda **kw: object()),
    )
    return worker


def test_default_build_pins_en_in(fake_plugin, monkeypatch):
    # TASK-VOI-042: no profile configured pins en-IN — the model is
    # built with language="en-IN", never without a language.
    monkeypatch.delenv("FRIDAY_VOICE_LANGUAGE", raising=False)
    worker = fake_plugin
    assert worker._voice_language() == "en-IN"
    model = worker._build_realtime_model("key", "instructions")
    assert model is not None
    assert _FakeRealtimeModel.calls[0]["language"] == "en-IN"


def test_profile_build_passes_the_language_code(fake_plugin, monkeypatch):
    monkeypatch.setenv("FRIDAY_VOICE_LANGUAGE", "te-IN")
    worker = fake_plugin
    assert worker._voice_language() == "te-IN"
    model = worker._build_realtime_model("key", "instructions")
    assert model is not None
    assert _FakeRealtimeModel.calls[0]["language"] == "te-IN"


def test_plugin_without_language_option_degrades_not_dies(fake_plugin, monkeypatch):
    monkeypatch.setenv("FRIDAY_VOICE_LANGUAGE", "hi-IN")
    _FakeRealtimeModel.reject_language = True
    worker = fake_plugin
    model = worker._build_realtime_model("key", "instructions")
    assert model is not None
    assert len(_FakeRealtimeModel.calls) == 1
    assert "language" not in _FakeRealtimeModel.calls[0]


def test_build_failure_still_returns_none(fake_plugin, monkeypatch):
    monkeypatch.delenv("FRIDAY_VOICE_LANGUAGE", raising=False)

    class _Boom:
        def __init__(self, **kwargs):
            raise ValueError("no model for you")

    monkeypatch.setattr(
        fake_plugin, "_lk_google",
        SimpleNamespace(realtime=SimpleNamespace(RealtimeModel=_Boom)),
    )
    assert fake_plugin._build_realtime_model("key", "instructions") is None
