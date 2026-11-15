"""VyralX viral-pattern analysis & format cloning (TASK-IG-VYR-03).

The IG reference corpus cluster behind this module:

* DemU8amxpoC — **Hypit**: point an agent at a viral reel and it
  clones the *format* — footage structure, word-level captions,
  B-roll and effects anchored to WORDS instead of seconds — so you
  can swap topic/hook and render variants. Repo card verdict:
  **adapt** (its licence permits internal use; per-clone AI-footage
  spend is avoided — VyralX clones are code/$0 only).
* DSHEybFjsub — a pre-publish step that scores a short's hook
  against patterns from high-growth reels.
* DeyusrQMOmi — keyframe extraction (getkeyframes) as the analysis
  step behind winning-video breakdowns.

What this module implements, natively and deterministically:

* :func:`extract_keyframes` — scene-change keyframes from a local
  reference video via ffmpeg. Guarded: no ffmpeg or no file means an
  honest ``available=False`` result, never invented frames.
* :func:`build_format_template` — a word-anchored template from a
  reference's timed transcript: hook window, beat segmentation,
  caption density. The template captures STRUCTURE ONLY.
* :func:`score_hook` — a stated, deterministic heuristic scoring a
  candidate script's opening against the template's hook window.
  It is a heuristic, not a virality predictor; no outcome data
  exists to fit one (TASK-VYR-005/010), and the result says so.
* :func:`clone_format` / :func:`make_variants` — map a NEW script
  onto the template's word-anchored beats, producing render plans
  that stay ``pending_review``.

COPYRIGHT LINE (binding): a template never carries the reference's
footage, images, or words. Cloning structure is fine; reusing the
reference's actual media or script text would be a derivative work
and stays behind the TASK-VYR-004 licence gate, which this module
does not bypass.

No network. ffmpeg/ffprobe are optional external tools, probed at
call time. Python 3.10.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

CLONE_VERSION = "ig-vyr03-1"

# Stated hook-heuristic vocabularies. Small and explicit on purpose:
# the score must be arguable with, so every signal is named.
_CURIOSITY_MARKERS = (
    "nobody", "secret", "never", "actually", "real", "hidden",
    "watch", "wait", "stop", "look", "truth", "wrong",
)
_SECOND_PERSON = ("you", "your", "you're", "you'll")


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", str(text or ""))


# --------------------------------------------------------------------------- #
# Keyframe extraction (ffmpeg, guarded)
# --------------------------------------------------------------------------- #
def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def extract_keyframes(video_path: str | Path, out_dir: str | Path,
                      max_frames: int = 12,
                      scene_threshold: float = 0.35) -> dict[str, Any]:
    """Extract scene-change keyframes from a local video.

    Returns ``{"available": bool, "frames": [...], "reason": str}``.
    Any failure — missing tool, missing file, ffmpeg error — is an
    honest unavailable result; this function never fabricates frames.
    """
    video = Path(video_path)
    if not ffmpeg_available():
        return {"available": False, "frames": [],
                "reason": "ffmpeg not found on PATH"}
    if not video.exists():
        return {"available": False, "frames": [],
                "reason": f"video file not found: {video}"}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pattern = str(out / "keyframe_%03d.png")
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(video),
        "-vf", f"select='gt(scene,{scene_threshold})',scale=320:-1",
        "-frames:v", str(max_frames), "-vsync", "vfr", pattern,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "frames": [],
                "reason": f"ffmpeg failed to start: {exc}"}
    frames = sorted(str(p) for p in out.glob("keyframe_*.png"))
    if proc.returncode != 0:
        return {"available": False, "frames": [],
                "reason": f"ffmpeg exited {proc.returncode}: "
                          f"{proc.stderr.strip()[:200]}"}
    if not frames:
        # A static video legitimately has no scene changes; fall back
        # to the first frame so analysis still has one honest frame.
        first = out / "keyframe_000.png"
        cmd2 = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(video), "-frames:v", "1",
                "-vf", "scale=320:-1", str(first)]
        try:
            proc2 = subprocess.run(cmd2, capture_output=True, text=True,
                                   timeout=60)
            if proc2.returncode == 0 and first.exists():
                frames = [str(first)]
        except (OSError, subprocess.SubprocessError):
            pass
    return {"available": bool(frames), "frames": frames,
            "reason": "ok" if frames else "no frames could be extracted"}


def probe_video(video_path: str | Path) -> dict[str, Any]:
    """ffprobe facts for a local video (duration, size, fps)."""
    if shutil.which("ffprobe") is None:
        return {"available": False, "reason": "ffprobe not found on PATH"}
    video = Path(video_path)
    if not video.exists():
        return {"available": False,
                "reason": f"video file not found: {video}"}
    cmd = ["ffprobe", "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", str(video)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=60)
        data = json.loads(proc.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"available": False, "reason": f"ffprobe failed: {exc}"}
    fmt = data.get("format") or {}
    stream = next((s for s in data.get("streams") or []
                   if s.get("codec_type") == "video"), {})
    return {
        "available": True,
        "duration_seconds": float(fmt.get("duration") or 0) or None,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "reason": "ok",
    }


# --------------------------------------------------------------------------- #
# Word-anchored format templates
# --------------------------------------------------------------------------- #
def build_format_template(reference: dict[str, Any]) -> dict[str, Any]:
    """Build a word-anchored format template from a reference.

    ``reference``: ``{"duration_seconds": float, "timed_words":
    [{"word","start","end"}, ...]}`` — e.g. from a whisper-style
    transcript of the reference. Beats are word-index ranges split
    at the largest timing gaps (pauses), so the template is anchored
    to words, not seconds — the Hypit pattern. The reference's words
    themselves are NOT stored in the template, only counts and
    boundaries.
    """
    timed = reference.get("timed_words") or []
    duration = float(reference.get("duration_seconds") or 0)
    if not timed:
        raise ValueError("reference carries no timed_words; a template "
                         "cannot be built from nothing")
    words_total = len(timed)
    caption_density = (words_total / duration) if duration else None
    # Beat boundaries at the largest inter-word pauses (up to 5 beats).
    gaps = []
    for i in range(1, words_total):
        gap = float(timed[i].get("start") or 0) - float(
            timed[i - 1].get("end") or 0)
        gaps.append((gap, i))
    gaps.sort(reverse=True)
    cuts = sorted(i for _g, i in gaps[:4] if _g > 0.25)
    bounds = [0] + cuts + [words_total]
    beats = []
    for j in range(len(bounds) - 1):
        lo, hi = bounds[j], bounds[j + 1]
        role = "hook" if j == 0 else ("cta" if j == len(bounds) - 2
                                      else "body")
        beats.append({"beat": j, "role": role,
                      "word_start": lo, "word_end": hi,
                      "word_count": hi - lo})
    hook_end = float(timed[min(8, words_total) - 1].get("end") or 0)
    return {
        "kind": "format_template",
        "clone_version": CLONE_VERSION,
        "source_duration_seconds": duration or None,
        "words_total": words_total,
        "caption_density_wps": caption_density,
        "hook_window_seconds": round(hook_end, 2) or None,
        "beats": beats,
        "structure_only": True,
        "carries_reference_media": False,
        "carries_reference_words": False,
    }


# --------------------------------------------------------------------------- #
# Pre-publish hook scoring (stated heuristic)
# --------------------------------------------------------------------------- #
def score_hook(script_text: str,
               template: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score a script's opening hook. Deterministic heuristic.

    Components (each named in the result): question form, curiosity
    markers, second-person address, a concrete number, and hook
    length fit against the template's caption density (the hook
    should land inside the hook window). This is NOT a virality
    predictor — no outcome data exists to fit one (TASK-VYR-005).
    """
    words = _words(script_text)
    density = (template or {}).get("caption_density_wps") or 2.6
    window_words = max(4, int(round(3.0 * density)))  # ~3s of speech
    hook_words = words[:window_words]
    hook_text = " ".join(hook_words).casefold()
    checks = {
        "question_form": "?" in str(script_text or "")[:120]
        or hook_text.split(" ")[0] in ("how", "why", "what", "did",
                                       "have", "is", "are"),
        "curiosity_marker": any(m in hook_text
                                for m in _CURIOSITY_MARKERS),
        "second_person": any(w in hook_text.split()
                             for w in _SECOND_PERSON),
        "concrete_number": any(w.replace(",", "").isdigit()
                               for w in hook_words),
        "hook_present": len(words) >= 4,
    }
    weights = {"question_form": 0.25, "curiosity_marker": 0.25,
               "second_person": 0.2, "concrete_number": 0.15,
               "hook_present": 0.15}
    score = round(sum(weights[k] for k, ok in checks.items() if ok), 3)
    return {
        "score": score,
        "checks": checks,
        "hook_window_words": window_words,
        "hook_text": " ".join(hook_words),
        "basis": "stated heuristic — not a virality predictor "
                 "(no outcome data exists; TASK-VYR-005/010)",
    }


# --------------------------------------------------------------------------- #
# Cloning: map a new script onto the template's beats
# --------------------------------------------------------------------------- #
def clone_format(template: dict[str, Any], new_script: str,
                 topic: str = "") -> dict[str, Any]:
    """Map a NEW script onto the template's word-anchored beats.

    The new script's words are distributed across the template's
    beats in proportion to the beats' word counts. The plan carries
    only the new script's own words.
    """
    words = _words(new_script)
    if not words:
        raise ValueError("new_script must not be empty")
    beats = template.get("beats") or []
    if not beats:
        raise ValueError("template carries no beats")
    total_template = sum(b["word_count"] for b in beats) or 1
    segments = []
    cursor = 0
    for j, beat in enumerate(beats):
        if j == len(beats) - 1:
            take = len(words) - cursor
        else:
            take = int(round(len(words) * beat["word_count"]
                             / total_template))
            take = max(0, min(take, len(words) - cursor))
        text = " ".join(words[cursor:cursor + take])
        cursor += take
        segments.append({
            "beat": beat["beat"], "role": beat["role"],
            "word_start": cursor - take, "word_end": cursor,
            "text": text,
        })
    return {
        "kind": "format_clone_plan",
        "clone_version": CLONE_VERSION,
        "topic": topic,
        "segments": segments,
        "hook_score": score_hook(new_script, template),
        "status": "pending_review",
        "requires_approval": True,
        "publish": False,
    }


def make_variants(template: dict[str, Any],
                  scripts: Iterable[str]) -> list[dict[str, Any]]:
    """One clone plan per supplied script (topic/hook swaps)."""
    return [clone_format(template, s) for s in scripts]
