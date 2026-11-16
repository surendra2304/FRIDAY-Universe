"""VyralX short-video assembly plan (TASK-IG2-VYR-08).

Pattern adapted from MoneyPrinterTurbo (MIT,
https://github.com/harry0703/MoneyPrinterTurbo): topic in -> script ->
per-scene stock-footage match -> free voiceover -> subtitles ->
background music -> composite short out, in 9:16 / 16:9 / 1:1, with
batch generation. This is FRIDAY's own implementation of that stage
pattern; no MoneyPrinterTurbo code is vendored.

Why a native port instead of the upstream package (per the spec card):

* upstream requires Python 3.11+; the fleet runs Python 3.10. This
  module is pure-stdlib Python 3.10.
* upstream's Streamlit + MoviePy/FFmpeg stack does not fit VyralX's
  ~180MB resident-service cap on the ~956MB fleet VMs, so — like the
  TASK-IG2-VYR-01 audio lane — this module produces an *assembly
  plan* (a job manifest) that a batch runner executes off-fleet or
  post-ARM. Nothing here renders, downloads or uploads.
* upstream's free path is kept and its paid paths are closed off:
  script providers are the fleet's existing free-tier LLM keys,
  stock comes from the free Pexels/Pixabay/Coverr APIs or local
  media, voiceover is Microsoft Edge TTS (free, no key — already a
  VyralX dependency), subtitles come from Edge word boundaries or a
  local Whisper pass, and music is local-library only.

Owner rules enforced here: Shorts are <60s (a ``short`` plan whose
script estimates at 60s or longer is rejected, not silently
trimmed); money content is stories only — scripts are screened with
the compliance gate's finance-advice finder; anything the batch
runner eventually publishes re-enters VyralX's normal pipeline and
stays UNLISTED.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from app.services import compliance_gate

ASSEMBLY_VERSION = "ig2-vyr08-1"

#: MoneyPrinterTurbo's three output shapes.
FORMATS = {
    "vertical": {"aspect": "9:16", "width": 1080, "height": 1920},
    "landscape": {"aspect": "16:9", "width": 1920, "height": 1080},
    "square": {"aspect": "1:1", "width": 1080, "height": 1080},
}

#: A Short must stay under 60 seconds (owner rule).
SHORT_MAX_SECONDS = 60.0
_WORDS_PER_MINUTE = 150.0
#: One scene per narration chunk; caps keep a plan reviewable.
MAX_SCENES = 30
_SCENE_WORDS = 18

#: Free script-provider fallback chain (fleet free-tier keys only).
SCRIPT_PROVIDERS = ("gemini", "groq", "openrouter")
#: Free stock-footage fallback chain, local media last.
STOCK_PROVIDERS = ("pexels", "pixabay", "coverr", "local")
#: Voiceover is Edge TTS only — free, no key, already a VyralX dep.
FREE_TTS_PROVIDERS = ("edge",)
PAID_TTS_PROVIDERS = ("openai", "elevenlabs", "azure")
EDGE_VOICE = "en-US-GuyNeural"
#: Subtitle sources: TTS word boundaries first, local Whisper second.
SUBTITLE_SOURCES = ("edge_word_boundary", "local_whisper")

_STOPWORDS = frozenset(
    "the a an and or but of to in on for with is are was were be been "
    "it its this that these those as at by from has have had not no "
    "you your we our they their he she his her".split())


class AssemblyError(ValueError):
    """Raised when an assembly plan violates a format/free rule."""


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def estimate_seconds(text: str) -> float:
    words = len(str(text or "").split())
    return round(words / _WORDS_PER_MINUTE * 60.0, 2)


def _footage_query(sentence: str) -> str:
    words = [w.strip(".,!?;:'\"").lower() for w in sentence.split()]
    keywords = [w for w in words if w and w not in _STOPWORDS]
    return " ".join(keywords[:3]) or "b-roll footage"


def segment_script(script: str) -> list[dict[str, Any]]:
    """Split a narration script into scenes (MoneyPrinterTurbo's
    script-to-clips step): one scene per sentence, long sentences
    chunked, each with its own footage query and duration estimate."""
    sentences = _sentences(script)
    if not sentences:
        raise AssemblyError("script produced no sentences")
    scenes: list[dict[str, Any]] = []
    start = 0.0
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), _SCENE_WORDS):
            chunk = " ".join(words[i:i + _SCENE_WORDS])
            seconds = estimate_seconds(chunk)
            scenes.append({
                "index": len(scenes),
                "narration": chunk,
                "footage_query": _footage_query(chunk),
                "stock_providers": list(STOCK_PROVIDERS),
                "start_s": round(start, 2),
                "duration_s": seconds,
            })
            start += seconds
            if len(scenes) >= MAX_SCENES:
                return scenes
    return scenes


def build_assembly_plan(
    topic: str,
    script: str,
    *,
    fmt: str = "vertical",
    kind: str = "short",
    tts_provider: str = "edge",
    subtitle_source: str = "edge_word_boundary",
    music_track: str | None = None,
) -> dict[str, Any]:
    """Build one MoneyPrinterTurbo-pattern assembly plan.

    Raises AssemblyError on an unknown format/kind/provider, a paid
    TTS provider, an empty script, a finance-advice hit, or a
    ``short`` whose estimated runtime is not <60s.
    """
    if fmt not in FORMATS:
        raise AssemblyError(f"format {fmt!r} not in {tuple(FORMATS)}")
    if kind not in ("short", "standard"):
        raise AssemblyError(f"kind {kind!r} not in ('short', 'standard')")
    if tts_provider in PAID_TTS_PROVIDERS:
        raise AssemblyError(
            f"TTS provider {tts_provider!r} is paid; free paths only "
            f"{FREE_TTS_PROVIDERS}")
    if tts_provider not in FREE_TTS_PROVIDERS:
        raise AssemblyError(
            f"unknown TTS provider {tts_provider!r}; free paths only "
            f"{FREE_TTS_PROVIDERS}")
    if subtitle_source not in SUBTITLE_SOURCES:
        raise AssemblyError(
            f"subtitle source {subtitle_source!r} not in {SUBTITLE_SOURCES}")
    if not str(topic or "").strip():
        raise AssemblyError("topic is empty")

    hits = compliance_gate.find_finance_advice(str(script or ""))
    if hits:
        raise AssemblyError(f"script blocked by finance-advice screen: {hits}")

    scenes = segment_script(script)
    total = round(sum(s["duration_s"] for s in scenes), 2)
    if kind == "short" and total >= SHORT_MAX_SECONDS:
        raise AssemblyError(
            f"short estimates {total}s; Shorts must be <{SHORT_MAX_SECONDS:.0f}s "
            "— shorten the script or use kind='standard'")

    shape = FORMATS[fmt]
    return {
        "version": ASSEMBLY_VERSION,
        "kind_of_job": "vyralx.short_video_assembly",
        "topic": topic,
        "content_kind": kind,
        "execution": "batch_offline",
        "resident_service": False,
        "fleet_note": (
            "Rendering (FFmpeg/MoviePy) runs off the resident VyralX "
            "service (~180MB cap): batch on the owner's machine or "
            "post-ARM. Upstream MoneyPrinterTurbo needs Python 3.11+; "
            "this native port runs on the fleet's Python 3.10."),
        "stages": [
            {"stage": "script", "providers": list(SCRIPT_PROVIDERS),
             "paid": False},
            {"stage": "footage_match", "providers": list(STOCK_PROVIDERS),
             "paid": False},
            {"stage": "voiceover", "provider": tts_provider,
             "voice": EDGE_VOICE, "paid": False},
            {"stage": "subtitles", "source": subtitle_source, "paid": False},
            {"stage": "music", "source": "local_library",
             "track": music_track, "duck_under_voice": True, "paid": False},
            {"stage": "composite", "engine": "ffmpeg_plan_only",
             "width": shape["width"], "height": shape["height"],
             "aspect": shape["aspect"]},
        ],
        "scenes": scenes,
        "estimated_seconds": total,
        "is_short": kind == "short",
        "under_60s": total < SHORT_MAX_SECONDS,
        "finance_advice_hits": [],
        "paid_services_used": False,
        "publish": False,
        "privacy_if_published": "unlisted",
        "source": "moneyprinterturbo-pattern (MIT), FRIDAY-native port",
    }


def build_batch(
    items: Iterable[dict[str, Any]],
    **plan_kwargs: Any,
) -> list[dict[str, Any]]:
    """MoneyPrinterTurbo's batch generation, plan-level: one plan per
    unique topic (exact-topic duplicates are dropped, order kept)."""
    seen: set[str] = set()
    plans: list[dict[str, Any]] = []
    for item in items:
        topic = str(item.get("topic", "")).strip()
        if not topic or topic.lower() in seen:
            continue
        seen.add(topic.lower())
        plans.append(build_assembly_plan(
            topic, str(item.get("script", "")), **plan_kwargs))
    return plans
