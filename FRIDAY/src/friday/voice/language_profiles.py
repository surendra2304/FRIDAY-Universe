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

What it deliberately does NOT do: with no profile configured the
worker behaves exactly as before — no language is passed and Gemini
Live mirrors the caller's language natively (TASK-VOI-009's design).
The owner's own line is untouched unless he sets the variable.

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


def instruction_section(environ=None) -> str:
    """The aggregator contract (TASK-IG-VOI-01): empty unless a
    profile is configured, so the owner's default instructions are
    byte-identical to before."""
    env = os.environ if environ is None else environ
    profile = resolve(env.get("FRIDAY_VOICE_LANGUAGE"))
    if profile is None:
        return ""
    return (
        f"LANGUAGE PROFILE: this call is configured for "
        f"{profile.name} ({profile.code}). Speak primarily in "
        f"{profile.name} from your first word unless the user "
        f"switches language mid-call; keep the same brevity and "
        f"confirmation rules."
    )
