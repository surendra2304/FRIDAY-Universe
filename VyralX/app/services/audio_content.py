"""VyralX audio-content lane (TASK-IG2-VYR-01).

Pattern adapted from Podcastfy (Apache-2.0,
https://github.com/souzatharsis/podcastfy): source material in ->
two-host dialogue transcript -> per-turn TTS -> one audio episode out.
This is FRIDAY's own implementation of that pattern, written for
VyralX's lanes and constraints; no Podcastfy code is vendored.

Why a native port instead of the upstream package (per the spec card):

* upstream requires Python 3.11+; the fleet runs Python 3.10. This
  module is pure-stdlib Python 3.10 and has no import-time deps beyond
  VyralX's own compliance gate.
* upstream's FFmpeg/audio workload does not fit VyralX's ~180MB
  resident-service cap on the ~956MB fleet VMs, so this lane is a
  *batch/offline* pattern: it produces a dialogue script plus a TTS
  segment plan (a job manifest) that a batch runner executes
  off-fleet or post-ARM. Nothing here renders or uploads.
* upstream's default TTS is OpenAI (paid). Only FREE paths are
  allowed here: Microsoft Edge TTS (already a VyralX dependency) and
  Gemini TTS on the fleet's existing free-tier Gemini keys. Paid
  providers are rejected by name.

Lane rules (owner standing rules): lanes are space/science,
history/did-you-know and tech/AI explainers; money content is
STORIES only, never advice — every dialogue is screened with the
compliance gate's finance-advice finder and a tripping script
blocks the job. Episodes are English/global. Anything this lane
eventually publishes goes through VyralX's normal pipeline and
stays UNLISTED; this module itself publishes nothing.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from app.services import compliance_gate

AUDIO_CONTENT_VERSION = "ig2-vyr01-1"

#: VyralX content lanes (owner rules). Money is not a lane: money
#: *stories* ride the history lane and are advice-screened below.
ALLOWED_LANES = ("space_science", "history", "tech_ai")

#: Free TTS paths only. ``edge`` = Microsoft Edge TTS (no key);
#: ``gemini`` = Gemini TTS on existing free-tier fleet keys.
FREE_TTS_PROVIDERS = ("edge", "gemini")
PAID_TTS_PROVIDERS = ("openai", "elevenlabs")

#: Two distinct free Edge voices so the two hosts sound different.
EDGE_VOICES = {"host_a": "en-US-AriaNeural", "host_b": "en-US-GuyNeural"}
GEMINI_VOICES = {"host_a": "Kore", "host_b": "Puck"}

#: Podcastfy's two modes: short episodes and longform.
MODES = {
    "short": {"max_turns": 10, "target_minutes": (2.0, 5.0)},
    "longform": {"max_turns": 60, "target_minutes": (15.0, 35.0)},
}

_WORDS_PER_MINUTE = 150.0

_HOST_B_PROMPTS = (
    "Wait — can you break that down for me?",
    "That's wild. So what does that actually mean?",
    "Okay, but why does that matter?",
    "Give me the part most people get wrong.",
    "And what happened next?",
)


class AudioContentError(ValueError):
    """Raised when an audio-content job violates a lane/free rule."""


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def estimate_minutes(turns: Iterable[dict[str, Any]]) -> float:
    words = sum(len(str(t.get("text", "")).split()) for t in turns)
    return round(words / _WORDS_PER_MINUTE, 2)


def build_dialogue_script(
    source_text: str,
    topic: str,
    *,
    lane: str = "space_science",
    mode: str = "short",
) -> dict[str, Any]:
    """Turn source material into a two-host dialogue transcript.

    Deterministic template dialogue (the batch runner may replace
    turn text with an LLM pass upstream; the structure — alternating
    explainer/questioner turns chunked from the source — is the
    Podcastfy pattern being adopted). Raises AudioContentError on an
    unknown lane/mode, empty source, or a finance-advice hit.
    """
    if lane not in ALLOWED_LANES:
        raise AudioContentError(
            f"lane {lane!r} not in VyralX lanes {ALLOWED_LANES}")
    if mode not in MODES:
        raise AudioContentError(f"mode {mode!r} not in {tuple(MODES)}")
    sentences = _sentences(source_text)
    if not sentences:
        raise AudioContentError("source_text produced no sentences")

    max_turns = MODES[mode]["max_turns"]
    # Host B opens and prompts; Host A explains — strict alternation.
    turns: list[dict[str, Any]] = [{
        "speaker": "host_b",
        "text": f"Welcome back. Today we're digging into {topic} — "
                "where do we start?",
    }]
    prompt_idx = 0
    for sentence in sentences:
        if len(turns) >= max_turns - 1:
            break
        turns.append({"speaker": "host_a", "text": sentence})
        if len(turns) >= max_turns - 1:
            break
        turns.append({
            "speaker": "host_b",
            "text": _HOST_B_PROMPTS[prompt_idx % len(_HOST_B_PROMPTS)],
        })
        prompt_idx += 1
    outro_speaker = "host_a" if turns[-1]["speaker"] == "host_b" else "host_b"
    turns.append({
        "speaker": outro_speaker,
        "text": "That is genuinely fascinating — and that's our story "
                "for today.",
    })

    full_text = "\n".join(t["text"] for t in turns)
    hits = compliance_gate.find_finance_advice(full_text)
    if hits:
        raise AudioContentError(
            f"dialogue blocked by finance-advice screen: {hits}")

    minutes = estimate_minutes(turns)
    lo, hi = MODES[mode]["target_minutes"]
    return {
        "version": AUDIO_CONTENT_VERSION,
        "topic": topic,
        "lane": lane,
        "mode": mode,
        "turns": turns,
        "estimated_minutes": minutes,
        "within_target_window": lo <= minutes <= hi,
        "finance_advice_hits": [],
        "source": "podcastfy-pattern (Apache-2.0), FRIDAY-native port",
    }


def plan_tts_segments(
    script: dict[str, Any],
    *,
    provider: str = "edge",
) -> list[dict[str, Any]]:
    """One TTS segment per dialogue turn, free providers only."""
    if provider in PAID_TTS_PROVIDERS:
        raise AudioContentError(
            f"TTS provider {provider!r} is paid; free paths only "
            f"{FREE_TTS_PROVIDERS}")
    if provider not in FREE_TTS_PROVIDERS:
        raise AudioContentError(
            f"unknown TTS provider {provider!r}; free paths only "
            f"{FREE_TTS_PROVIDERS}")
    voices = EDGE_VOICES if provider == "edge" else GEMINI_VOICES
    return [{
        "index": i,
        "speaker": turn["speaker"],
        "voice": voices[turn["speaker"]],
        "provider": provider,
        "text": turn["text"],
        "paid": False,
    } for i, turn in enumerate(script["turns"])]


def build_audio_job(
    source_text: str,
    topic: str,
    *,
    lane: str = "space_science",
    mode: str = "short",
    provider: str = "edge",
) -> dict[str, Any]:
    """Full batch-job manifest: script + TTS plan, ready for a runner.

    The manifest is explicit that execution is batch/offline (never a
    resident fleet service) and that nothing is published by the job
    itself — output audio re-enters VyralX's normal review flow and
    any upload stays UNLISTED.
    """
    script = build_dialogue_script(
        source_text, topic, lane=lane, mode=mode)
    segments = plan_tts_segments(script, provider=provider)
    return {
        "version": AUDIO_CONTENT_VERSION,
        "kind": "vyralx.audio_content_job",
        "execution": "batch_offline",
        "resident_service": False,
        "fleet_note": (
            "Audio rendering runs off the resident VyralX service "
            "(~180MB cap): batch on the owner's machine or post-ARM. "
            "Upstream Podcastfy needs Python 3.11+; this native port "
            "runs on the fleet's Python 3.10."),
        "script": script,
        "tts_segments": segments,
        "tts_provider": provider,
        "paid_services_used": False,
        "publish": False,
        "privacy_if_published": "unlisted",
    }
