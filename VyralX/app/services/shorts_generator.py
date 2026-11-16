"""VyralX long-form -> Shorts repurposing, LOCAL mode only (TASK-IG2-VYR-04).

Pattern adapted from Anil-matcha/AI-Youtube-Shorts-Generator (MIT;
spec card ``anil-matcha-ai-youtube-shorts-generator.md``, IG source
DelZub4u74G): rank highlight windows from a long video's transcript on
named virality signals, de-duplicate overlapping windows, and emit
9:16 vertical-crop plans for each surviving clip.

BINDING MODE RULE (owner FREE-only rule): the upstream project's
default ``--mode api`` routes download/transcription/ranking/cropping
through a paid MuAPI key. That mode is REJECTED here — requesting it
raises. Only the local path exists: local files / yt-dlp downloads
already on disk, a timed transcript supplied by the caller (produced
off-peak by tiny/base faster-whisper where available — never a
resident service on the ~956MB fleet), deterministic ranking in this
module (no paid LLM call), and ffmpeg crop plans that are built, not
executed, until review.

Every clip plan carries ``status="pending_review"`` and
``privacy="unlisted"`` — VyralX publishes nothing from here, and
Shorts are <60s by construction (``MAX_CLIP_SECONDS``).
No network. Python 3.10, stdlib only.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

GENERATOR_VERSION = "ig2-vyr04-1"
MAX_CLIP_SECONDS = 59.0
MIN_CLIP_SECONDS = 8.0
TARGET_WIDTH, TARGET_HEIGHT = 1080, 1920  # 9:16

_HOOK_MARKERS = ("nobody", "secret", "never", "actually", "hidden", "truth",
                 "wrong", "watch", "stop", "look", "wait")
_EMOTION_MARKERS = ("amazing", "incredible", "shocking", "terrified", "love",
                    "hate", "laugh", "cry", "furious", "stunned", "wow")
_QUOTABLE_MAX_WORDS = 14


class PaidModeRejected(ValueError):
    """Raised when the paid MuAPI ``api`` mode is requested."""


def ensure_local_mode(mode: str) -> str:
    """Return ``"local"`` or raise — the only mode this module ships."""
    m = str(mode or "local").strip().lower()
    if m == "api":
        raise PaidModeRejected(
            "mode='api' uses the paid MuAPI service and is rejected under "
            "the FREE-only rule; use mode='local'")
    if m != "local":
        raise ValueError(f"unknown mode {mode!r}; only 'local' exists")
    return m


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(text or "").lower())


def score_window(words: list[str], *, is_opening: bool = False) -> dict[str, Any]:
    """Deterministic virality heuristic over one candidate window.

    Named components (arguable by design, like format_clone.score_hook):
    hook (curiosity markers / second person / question), emotion,
    quotable (a short self-contained line), story_peak (turn markers).
    This is a ranking heuristic, NOT a virality predictor — no outcome
    data exists to fit one, and the result says so.
    """
    text = " ".join(words)
    n = max(len(words), 1)
    hook = min(1.0, (sum(text.count(m) for m in _HOOK_MARKERS) * 0.3
                     + (0.25 if "?" in text or "you" in words else 0.0)
                     + (0.2 if is_opening else 0.0)))
    emotion = min(1.0, sum(text.count(m) for m in _EMOTION_MARKERS) * 0.35)
    quotable = 1.0 if 4 <= len(words) <= _QUOTABLE_MAX_WORDS and (
        "!" in text or "?" in text or emotion > 0) else 0.4 if len(words) <= 20 else 0.1
    story = min(1.0, sum(text.count(m) for m in
                         ("but", "then", "suddenly", "finally", "because")) * 0.25)
    total = round(0.35 * hook + 0.25 * emotion + 0.2 * quotable + 0.2 * story, 4)
    return {"viral_score": total, "hook": round(hook, 3),
            "emotion": round(emotion, 3), "quotable": round(quotable, 3),
            "story_peak": round(story, 3), "is_prediction": False,
            "basis": "deterministic heuristic over transcript words; "
                     "no measured outcome data backs it"}


def candidate_windows(timed_words: list[dict[str, Any]], *,
                      window_seconds: float = 30.0,
                      step_seconds: float = 10.0) -> list[dict[str, Any]]:
    """Sliding windows over timed words, clipped to Shorts limits."""
    if not timed_words:
        return []
    end_t = float(timed_words[-1]["end"])
    out, start = [], 0.0
    while start < end_t:
        stop = min(start + window_seconds, end_t)
        seg = [w for w in timed_words if start <= float(w["start"]) < stop]
        if seg and stop - start >= MIN_CLIP_SECONDS:
            words = [str(w["word"]) for w in seg]
            sc = score_window(words, is_opening=start == 0.0)
            out.append({"start": round(start, 2), "end": round(stop, 2),
                        "duration": round(stop - start, 2),
                        "text": " ".join(words),
                        "hook_line": " ".join(words[:10]), **sc})
        start += step_seconds
    return out


def dedupe_windows(windows: list[dict[str, Any]], *,
                   overlap_fraction: float = 0.5) -> list[dict[str, Any]]:
    """Greedy score-ordered de-duplication of overlapping highlights."""
    kept: list[dict[str, Any]] = []
    for w in sorted(windows, key=lambda x: -x["viral_score"]):
        dup = False
        for k in kept:
            overlap = max(0.0, min(w["end"], k["end"]) - max(w["start"], k["start"]))
            if overlap / max(min(w["duration"], k["duration"]), 0.01) >= overlap_fraction:
                dup = True
                break
        if not dup:
            kept.append(w)
    return sorted(kept, key=lambda x: x["start"])


def vertical_crop_plan(clip: dict[str, Any], *, source_width: int = 1920,
                       source_height: int = 1080,
                       face_center_x: float | None = None) -> dict[str, Any]:
    """9:16 crop plan (ffmpeg argv built, never executed here).

    ``face_center_x`` (0..1, from an off-peak face pass) centres the
    crop on the speaker; without it the crop is centre-weighted.
    """
    crop_w = int(source_height * 9 / 16)
    frac = 0.5 if face_center_x is None else min(max(face_center_x, 0.0), 1.0)
    x = int(min(max(frac * source_width - crop_w / 2, 0), source_width - crop_w))
    vf = (f"crop={crop_w}:{source_height}:{x}:0,"
          f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}")
    return {"filter": vf, "width": TARGET_WIDTH, "height": TARGET_HEIGHT,
            "aspect": "9:16", "face_tracked": face_center_x is not None,
            "ffmpeg_args": ["-ss", str(clip["start"]), "-to", str(clip["end"]),
                            "-vf", vf]}


def generate_shorts(transcript: dict[str, Any], *, mode: str = "local",
                    lane: str = "space_science", max_clips: int = 5,
                    face_track: dict[str, Any] | None = None) -> dict[str, Any]:
    """Full local pipeline: transcript -> ranked, deduped Shorts plans.

    ``transcript`` = ``{"duration_seconds": float, "timed_words":
    [{"word","start","end"}...], "source": str}``. An empty transcript
    is an honest empty result, never invented clips.
    """
    ensure_local_mode(mode)
    words = transcript.get("timed_words") or []
    if not words:
        return {"version": GENERATOR_VERSION, "mode": "local",
                "available": False, "clips": [],
                "reason": "no timed transcript supplied; run the off-peak "
                          "tiny/base faster-whisper batch first"}
    ranked = dedupe_windows(candidate_windows(words))[:max_clips]
    clips = []
    for i, w in enumerate(ranked, 1):
        fc = (face_track or {}).get(f"{w['start']:.0f}")
        clips.append({"clip_id": f"short-{i:02d}", **w,
                      "crop": vertical_crop_plan(w, face_center_x=fc),
                      "lane": lane, "status": "pending_review",
                      "privacy": "unlisted", "publish": False})
    return {"version": GENERATOR_VERSION, "mode": "local", "available": True,
            "source": transcript.get("source", ""), "clips": clips,
            "publishes_anything": False}


def batch_generate(transcripts: Iterable[dict[str, Any]], **kw: Any) -> list[dict[str, Any]]:
    """Batch over a URL/file list's transcripts (JSON-out per source)."""
    return [generate_shorts(t, **kw) for t in transcripts]
