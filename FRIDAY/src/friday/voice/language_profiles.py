"""TASK-IG-VOI-03 — Indian-language voice profiles for FRIDAY voice.

Source idea: reel DV563QjD0Ft — a tutorial on building and selling
AI voice agents to businesses, with Indian-language support as the
selling point. The implementable core for FRIDAY: make the session
language a first-class, configured profile instead of an emergent
behaviour, so the same Gemini Live stack can serve the owner
(Telugu/English mirroring, unchanged) or a business deployment
pinned to one Indian language.

What a profile does when configured (FRIDAY_VOICE_LANGUAGE):

1. The Gemini Live realtime model is built with the profile's
   BCP-47 language code, so recognition and speech are anchored to
   that language from the first word instead of drifting.
2. ``instruction_section()`` (appended by the TASK-IG-VOI-01
   optional-sections aggregator) tells the model the call's primary
   language, so replies start in it rather than waiting to mirror.

TASK-VOI-042 (P0, owner live test 2026-11-25 ~15:54 IST): the
default is no longer "unset means native mirroring". The owner's
own session ran unset, Gemini auto-detected, and his English was
transcribed in Hindi and Telugu script ("ए, पड़को।",
"Stratex స్పష్టంగా తెలుసు.") while she answered the fragments.
The P0 directive pins the owner's English (en-IN): with no
explicit FRIDAY_VOICE_LANGUAGE the effective language is en-IN —
the model language, the input-transcription language_codes, the
instruction section and the status file all read en-IN. An
explicit FRIDAY_VOICE_LANGUAGE still wins (business deployments
keep their pinned profile; a Telugu session is one env var away).
``configured_language()`` keeps its old meaning (the explicit
config, or None) so callers that need "was anything configured"
keep working; ``effective_language()`` is the session default.
Safety: if the deployed livekit google plugin generation predates
the ``language`` option, the worker catches the TypeError and builds
without it (see _build_realtime_model) — a profile can degrade to
today's mirroring, never to a dead call.

The profile table is data, not code paths: adding a language is one
row. Codes follow the Gemini Live BCP-47 list.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageProfile:
    code: str  # BCP-47, as passed to the Gemini Live session config
    name: str  # English display name
    native_name: str  # the language's own name for itself


PROFILES = {
    "en-IN": LanguageProfile("en-IN", "English (India)", "English"),
    "hi-IN": LanguageProfile("hi-IN", "Hindi", "हिन्दी"),
    "te-IN": LanguageProfile("te-IN", "Telugu", "తెలుగు"),
    "ta-IN": LanguageProfile("ta-IN", "Tamil", "தமிழ்"),
    "kn-IN": LanguageProfile("kn-IN", "Kannada", "ಕನ್ನಡ"),
    "ml-IN": LanguageProfile("ml-IN", "Malayalam", "മലയാളം"),
    "mr-IN": LanguageProfile("mr-IN", "Marathi", "मराठी"),
    "bn-IN": LanguageProfile("bn-IN", "Bengali", "বাংলা"),
    "gu-IN": LanguageProfile("gu-IN", "Gujarati", "ગુજરાતી"),
    "pa-IN": LanguageProfile("pa-IN", "Punjabi", "ਪੰਜਾਬੀ"),
    "ur-IN": LanguageProfile("ur-IN", "Urdu", "اردو"),
}

_BY_NAME = {}
for _profile in PROFILES.values():
    _BY_NAME[_profile.name.lower()] = _profile
    _BY_NAME[_profile.name.split(" ")[0].lower()] = _profile
    _BY_NAME[_profile.native_name] = _profile


def resolve(value: "str | None") -> "LanguageProfile | None":
    """Resolve an env value (code or name, any case) to a profile.

    Accepts "te-IN", "te_in", "TE-IN", "Telugu", "telugu". Unknown or
    empty values resolve to None — an unrecognised profile must never
    break session build; it simply means "no profile", i.e. today's
    native language mirroring."""
    raw = (value or "").strip()
    if not raw:
        return None
    code = raw.replace("_", "-")
    for known, profile in PROFILES.items():
        if code.lower() == known.lower():
            return profile
    return _BY_NAME.get(raw.lower()) or _BY_NAME.get(code.lower())


def configured_language(environ=None) -> "str | None":
    """The BCP-47 code from FRIDAY_VOICE_LANGUAGE, or None."""
    env = os.environ if environ is None else environ
    profile = resolve(env.get("FRIDAY_VOICE_LANGUAGE"))
    return profile.code if profile else None


# TASK-VOI-042: the owner's English is the session default. An
# unrecognised FRIDAY_VOICE_LANGUAGE falls back here too — a typo
# must never silently re-enable native mirroring (the 2026-11-25
# failure mode), it lands on the pinned default instead.
DEFAULT_CODE = "en-IN"


def effective_language(environ=None) -> str:
    """The session language: the configured profile, or en-IN.

    Always a code, never None — this is what the worker pins into
    the realtime model, the input-transcription language_codes, the
    instruction section and the status file."""
    return configured_language(environ) or DEFAULT_CODE


def instruction_section(environ=None) -> str:
    """The aggregator contract (TASK-IG-VOI-01): the effective
    language's section — TASK-VOI-042 pins the default to en-IN, so
    the section is present on every call and tells the model to
    speak primarily English (India) from the first word unless the
    user switches language mid-call."""
    env = os.environ if environ is None else environ
    profile = resolve(env.get("FRIDAY_VOICE_LANGUAGE")) or PROFILES[DEFAULT_CODE]
    return (
        f"LANGUAGE PROFILE: this call is configured for "
        f"{profile.name} ({profile.code}). Speak primarily in "
        f"{profile.name} from your first word unless the user "
        f"switches language mid-call; keep the same brevity and "
        f"confirmation rules."
    )
